"""Financial boundaries, persistence, routing and resumable independent readers."""
import csv
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import app
import euer as E
import euer_ai as EA
import intelligence as I
import taxprofile
import studio
import storage
import sqlite3

MODELS=['qwen3.8:27b','gemma4:31b','gpt-oss:20b']
class EuerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.temp.name)/'data';app.initialize();self.calls=[]
    def tearDown(self):
        self.wait();app.DATA=self.old;self.temp.cleanup()
    def wait(self):
        end=time.monotonic()+10
        while app.AI_LOCK.locked() and time.monotonic()<end:threading.Event().wait(.005)
        self.assertFalse(app.AI_LOCK.locked())
    def tx(self,**kw):
        return app.save_transaction({'direction':'expense','amount':'119,00','paid_on':'2025-02-03','partner':'Synthetic','title':'Software','scope':'business',**kw})['id']
    def profile(self,**kw):
        taxprofile.save({'year':2025,'vat_status':'regular','taxation':'cash','filing_status':'open',**kw})
    def allocation(self,key,**kw):
        r=next(r for r in E.report(2025)['rows'] if r['id']==key)
        return {'tx_id':key,'year':2025,'source_hash':r['source_hash'],'revision':r['revision'],'position':'50','business_percent':100,'deductible_percent':100,'vat':'19,00','note':'Rechnung vollständig geprüft. Synthetischer Test.','confirmed':True,**kw}
    def doc(self,**kw):
        return app.create_document({'title':'Synthetische Rechnung','kind':'Rechnung','year':2025,'body':'Belegtext: Netto 100,00; Umsatzsteuer 19,00; Brutto 119,00.',**kw})['id']
    def fake(self,path,payload=None,timeout=5):
        if path=='/api/tags':return {'models':[{'name':m,'size':100,'digest':'fake-'+m} for m in MODELS]}
        self.calls.append(payload);raw=json.loads(payload['messages'][1]['content'])
        if 'Abschnitt' in raw:obj={'note':'Synthetische Unterlage gelesen. Keine Übernahme von Vorjahreswerten.','quote':raw['Abschnitt']['text'][:60]}
        elif 'Zahlung' in raw:obj={'position':'50','vat':'19,00','note':'Zahlung anhand des Belegs prüfen.','question':''}
        else:obj={'answer':'Freie Frage blieb freie Frage.','missing':[],'conflicts':[],'citations':[],'tasks':[]}
        return {'done':True,'done_reason':'stop','message':{'content':json.dumps(obj)}}
    def start(self,**kw):
        result=EA.start({'year':2025,'question':'Prüfe genau diesen EÜR-Auftrag.','document_ids':[],**kw});self.wait();return result['id']
    def positions(self):return {p['code']:p['amount_cents'] for p in E.report(2025)['positions']}

    def test_strict_money_and_rounding(self):
        for raw,expected in [('0,00',0),('1.234,56',123456),('-1,23',-123),('12.34',1234),('1.234',123400),('42',4200)]:self.assertEqual(E.amount(raw,signed=True),expected)
        for raw in ['NaN','1e2','1,001','Infinity','1,234.56','',None,1.5,'+1,00']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):E.amount(raw)
        self.assertEqual(E.scaled(1,50),1);self.assertEqual(E.scaled(11901,50),5951)

    def test_net_vat_income_expense_and_refunds(self):
        self.profile();out=self.tx();inc=self.tx(direction='income',amount='238,00')
        E.save_allocation(self.allocation(out));E.save_allocation(self.allocation(inc,position='15',vat='38,00'))
        back=self.tx(direction='income',amount='59,50');E.save_allocation(self.allocation(back,vat='9,50'))
        self.assertEqual(self.positions(),{'15':20000,'17':3800,'50':5000,'57':950})
        r=E.report(2025);self.assertEqual(r['income_cents'],23800);self.assertEqual(r['expense_cents'],5950);self.assertEqual(r['balance_cents'],17850)
        self.assertEqual(next(t for t in app.state()['transactions'] if t['id']==out)['amount_cents'],11900)

    def test_business_share_and_meal_vat_not_cut_twice(self):
        self.profile();key=self.tx(amount='238,00',scope='mixed',business_percent=50)
        E.save_allocation(self.allocation(key,position='63',business_percent=50,deductible_percent=70,vat='19,00'))
        self.assertEqual(self.positions(),{'63':7000,'57':1900})
        with self.assertRaises(ValueError):E.save_allocation(self.allocation(key,position='63',deductible_percent=100))

    def test_private_and_transfers_are_visible_but_never_income(self):
        self.tx(scope='private',direction='income',amount='2000,00');self.tx(scope='transfer',amount='2000,00');self.tx(scope='unknown')
        r=E.report(2025);self.assertEqual(r['counts']['excluded'],2);self.assertEqual(r['counts']['open'],1);self.assertEqual(r['positions'],[])

    def test_vat_payment_whole_not_split_and_status_conflict(self):
        self.profile();key=self.tx(direction='income',amount='265,15')
        with self.assertRaises(ValueError):E.save_allocation(self.allocation(key,position='18'))
        E.save_allocation(self.allocation(key,position='18',vat='0,00'));self.assertEqual(self.positions(),{'18':26515})
        self.profile(vat_status='small');key2=self.tx()
        with self.assertRaises(ValueError):E.save_allocation(self.allocation(key2))
        with self.assertRaises(ValueError):E.save_allocation(self.allocation(key2,vat='120,00'))

    def test_missing_or_unconfirmed_amounts_never_default_zero(self):
        key=self.tx()
        for changes in [{'vat':None},{'business_percent':''},{'confirmed':False},{'note':''},{'vat':'119,01'},{'position':'not-real'}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):E.save_allocation(self.allocation(key,**changes))
        self.assertEqual(self.positions(),{})

    def test_changed_receipt_profile_or_transaction_invalidates(self):
        self.profile();doc=self.doc();key=self.tx(document_ids=[doc]);E.save_allocation(self.allocation(key));self.assertTrue(self.positions())
        app.update_document(doc,{'title':'Synthetische Rechnung','year':2025,'kind':'Rechnung','body':'Geänderter Belegtext.'})
        self.assertEqual(self.positions(),{});self.assertEqual(E.report(2025)['counts']['stale'],1)
        E.save_allocation(self.allocation(key));self.profile(taxation='accrual');self.assertEqual(self.positions(),{})

    def test_stale_form_revision_rejected_even_same_source(self):
        key=self.tx();old=self.allocation(key);E.save_allocation(old)
        with self.assertRaises(ValueError):E.save_allocation(old)
        new=self.allocation(key);new['source_hash']='wrong'
        with self.assertRaises(ValueError):E.save_allocation(new)

    def test_asset_not_immediately_expensed_afa_manual_and_invalidation(self):
        self.profile();key=self.tx(amount='1190,00');E.save_allocation(self.allocation(key,position='asset',vat='190,00'))
        self.assertEqual(self.positions(),{'57':19000});self.assertTrue(any('AfA' in x['text'] for x in E.report(2025)['open']))
        asset={'year':2025,'kind':'asset','position':'33','title':'Kamera','note':'Anlagennachweis, linear, geprüfte Jahres-AfA 2025.','confirmed':True,'opening':'0,00','additions':'1000,00','depreciation':'200,00','disposals':'0,00','acquired_on':'2025-02-03','tx_id':key}
        result=E.save_entry(asset);self.assertEqual(self.positions(),{'33':20000,'57':19000});self.assertEqual(E.entries(2025)[0]['closing_cents'],80000)
        with self.assertRaises(ValueError):E.save_entry(asset)
        E.save_allocation(self.allocation(key,position='asset',vat='190,00',note='Neue Quelle geprüft'))
        self.assertEqual(self.positions(),{'57':19000});self.assertTrue(E.report(2025)['entries'][0]['stale'])
        e=E.entries(2025)[0];E.save_entry({**asset,'id':result['id'],'revision':e['revision']});self.assertEqual(self.positions()['33'],20000)
        with self.assertRaises(ValueError):E.save_entry({**asset,'depreciation':'1001,00','tx_id':''})

    def test_supplements_signed_csv_formula_protection_and_persistence(self):
        self.profile();E.save_entry({'year':2025,'kind':'supplement','position':'66','title':'=1+1','amount':'60,00','note':'10 nachgewiesene Tage, Voraussetzungen geprüft.','confirmed':True})
        E.save_entry({'year':2025,'kind':'supplement','position':'50','title':'Korrektur','amount':'-10,00','note':'Korrektur mit Quellenbezug.','confirmed':True})
        self.assertEqual(E.report(2025)['expense_cents'],5000)
        content=E.csv_bytes(2025).decode('utf-8-sig');self.assertIn("'=1+1",content)
        before=E.report(2025);app.initialize();self.assertEqual(E.report(2025),before)
        self.assertEqual(E.entries(2024),[])

    def test_year_check_resets_on_data_change_and_future_year_is_blocked(self):
        self.profile();self.tx(scope='private');r=E.report(2025)
        E.save_review({'year':2025,'fingerprint':r['fingerprint'],**{k:True for k in E.CHECKS}})
        self.assertEqual(E.report(2025)['open'],[])
        self.tx(scope='private');self.assertEqual(E.report(2025)['checks'],{})
        with self.assertRaises(ValueError):E.save_review({'year':2025,'fingerprint':r['fingerprint']})
        self.assertFalse(E.report(2030)['supported'])
        with self.assertRaises(ValueError):E.save_entry({'year':2030})

    def test_free_euer_question_is_not_hijacked_and_long_prompt_retained(self):
        app.save_settings({'num_ctx':16384});self.tx();q='EÜR 2025: '+('Bitte diesen Arbeitsauftrag beachten. '*100)+' LETZTER SATZ'
        with patch.object(app,'ollama',side_effect=self.fake):
            result=I.start_chat({'year':2025,'question':q,'document_ids':[],'mode':'question'});self.wait()
        c=I.chat_list(2025)[0];self.assertIsNone(c['annual']);self.assertFalse(c['legacy_annual']);self.assertEqual(c['question'],q)
        readers=[json.loads(p['messages'][1]['content']) for p in self.calls if p['model'] in MODELS[:2]]
        self.assertEqual(len(readers),2);self.assertTrue(all(p['Frage']==q for p in readers))

    def test_all_text_characters_to_two_independent_readers_and_prompt_to_all(self):
        body='2024 Vorjahresbeleg. '+('Textinhalt mit Belegangaben. '*250)+' ENDE DES BELEGS'
        doc=self.doc(body=body,year=2024);key=self.tx(document_ids=[doc]);question='Originalauftrag: prüfe dieses Jahr ohne Vorjahreswerte zu kopieren.'
        before=app.state()['transactions']
        with patch.object(app,'ollama',side_effect=self.fake):jid=self.start(question=question,document_ids=[doc])
        run=EA.list_runs(2025)[0];self.assertEqual(run['state'],'complete',run['error']);self.assertEqual(run['done'],run['total'])
        for model in MODELS[:2]:
            reads=[json.loads(p['messages'][1]['content']) for p in self.calls if p['model']==model]
            self.assertEqual(''.join(p['Abschnitt']['text'] for p in reads if 'Abschnitt' in p),body)
            self.assertTrue(all('Unabhaengige_Vorschlaege' not in p for p in reads))
        self.assertTrue(all(json.loads(p['messages'][1]['content'])['Auftrag']==question for p in self.calls))
        self.assertEqual(app.state()['transactions'],before);self.assertEqual(self.positions(),{})
        self.assertEqual(run['suggestions'][0]['tx_id'],key)

    def test_interruption_resume_keeps_completed_worker_and_rejects_changed_source(self):
        self.tx();failed=[False]
        def broken(path,payload=None,timeout=5):
            if payload and payload.get('model')==MODELS[1] and not failed[0]:failed[0]=True;raise OSError('Disconnected')
            return self.fake(path,payload,timeout)
        with patch.object(app,'ollama',side_effect=broken):jid=self.start()
        self.assertEqual(EA.list_runs(2025)[0]['state'],'error');done_before=[s for s in EA.steps(jid) if s['state']=='complete'];self.assertEqual(len(done_before),1)
        app.initialize();self.calls=[]
        with patch.object(app,'ollama',side_effect=self.fake):EA.resume({'id':jid});self.wait()
        self.assertEqual(EA.list_runs(2025)[0]['state'],'complete');self.assertFalse(any(c['model']==MODELS[0] for c in self.calls))
        self.assertEqual(EA.steps(jid)[0],done_before[0])
        with app.db() as con:con.execute("UPDATE euer_runs SET state='error' WHERE id=?",(jid,))
        self.tx()
        with patch.object(app,'ollama',side_effect=self.fake),self.assertRaises(ValueError):EA.resume({'id':jid})
        self.assertFalse(app.AI_LOCK.locked())

    def test_invalid_model_output_never_accepted_unknown_vat_remains_null(self):
        with self.assertRaises(ValueError):EA.validate_doc({'note':'Etwas','quote':'Erfunden'},'Tatsächlicher Text')
        with self.assertRaises(ValueError):EA.validate_tx({'position':'999','vat':None,'note':'Unklar','question':'Beleg?'})
        self.assertIsNone(EA.validate_tx({'position':None,'vat':None,'note':'Unklar','question':'Beleg?'})['vat'])
        key=self.tx();old=self.allocation(key)
        self.doc(body='Neue Unterlage')
        with patch.object(app,'ollama',side_effect=self.fake):jid=self.start()
        E.save_allocation(old);self.assertTrue(EA.list_runs(2025)[0]['stale'])


    def test_receipt_and_profile_invalidate_supplements_and_backup_contains_euer(self):
        self.profile();doc=self.doc()
        payload={'year':2025,'kind':'supplement','position':'66','title':'Tagespauschale','amount':'60,00','note':'Prüfung dokumentiert','source_id':doc,'confirmed':True,'request_id':'synthetic-unique-request-0001'}
        first=studio.post_route('/api/euer/entry',payload);second=studio.post_route('/api/euer/entry',payload)
        self.assertEqual(first,second);self.assertEqual(len(E.entries(2025)),1)
        with self.assertRaises(ValueError):studio.post_route('/api/euer/entry',{**payload,'amount':'120,00'})
        restored=Path(self.temp.name)/'restore';storage.verify_zip(app.backup_bytes(),restored)
        with sqlite3.connect(restored/'steuerstudio.sqlite3') as con:
            self.assertEqual(con.execute('SELECT count(*) FROM euer_entries').fetchone()[0],1)
            self.assertEqual(con.execute('SELECT payload FROM euer_entries').fetchone()[0],app.enc({k:v for k,v in E.entries(2025)[0].items() if k not in {'id','year','revision'}}))
        app.update_document(doc,{'title':'Geänderter Nachweis','year':2025,'kind':'Rechnung','body':'Neue Werte'})
        self.assertEqual(self.positions(),{});self.assertTrue(E.report(2025)['entries'][0]['stale'])

    def test_meal_nondeductible_component_preserved_separately(self):
        key=self.tx();E.save_allocation(self.allocation(key,position='63',deductible_percent=70))
        r=E.report(2025);self.assertEqual(r['expense_cents'],8900);self.assertEqual(r['nondeductible'][0]['amount_cents'],3000)
        self.assertIn('Nicht abziehbarer Nettoteil',E.csv_bytes(2025).decode())

if __name__=='__main__':unittest.main()
