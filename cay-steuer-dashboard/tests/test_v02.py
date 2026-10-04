import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import storage
import intelligence
import laws
import studio


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = app.DATA
        app.DATA = Path(self.temp.name) / 'data'
        storage.BACKUP_STATUS.update(state='idle', at='', external_at='', error='')
        app.initialize()

    def tearDown(self):
        deadline = time.monotonic()+3
        while app.AI_LOCK.locked() and time.monotonic()<deadline:
            time.sleep(.01)
        app.DATA = self.previous
        self.temp.cleanup()

    def tx(self, **kwargs):
        return app.save_transaction({'direction':'expense','amount':'49,90','paid_on':'2025-04-03','partner':'Test','title':'Software',**kwargs})

    def doc(self, **kwargs):
        return app.create_document({'title':'Testbeleg','kind':'Rechnung','year':2025,'body':'Rechnung: Streaming-Software 49,90 Euro. Zahlungsdatum 03.04.2025.',**kwargs})

    def test_committed_data_and_drafts_survive_process_exit(self):
        code = '''import sys,os;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import app,storage
app.DATA=Path(sys.argv[2]);app.initialize()
app.save_transaction({'direction':'expense','amount':'0,03','paid_on':'2025-04-01','partner':'Neustart','title':'Test'})
storage.save_draft({'key':'document-form:new','payload':{'title':'Entwurf','file_base64':'YWJj','filename':'a.txt'}})
os._exit(0)
'''
        subprocess.run([sys.executable,'-c',code,str(Path(app.__file__).parent),str(app.DATA)], check=True)
        app.initialize()
        self.assertEqual(app.state()['transactions'][0]['amount_cents'],3)
        self.assertEqual(storage.get_drafts()[0]['payload']['file_base64'],'YWJj')
        with app.db() as con:
            self.assertEqual(con.execute('PRAGMA synchronous').fetchone()[0],2)
            self.assertEqual(con.execute('PRAGMA journal_mode').fetchone()[0],'delete')

    def test_idempotency_commit_and_rollback(self):
        payload={'request_id':'a'*32,'amount':'49,90'}
        a=storage.cached_mutation('/api/transactions',payload,self.tx)
        b=storage.cached_mutation('/api/transactions',payload,self.tx)
        self.assertEqual(a,b)
        self.assertEqual(len(app.state()['transactions']),1)
        with self.assertRaises(ValueError):
            storage.cached_mutation('/api/transactions',{**payload,'amount':'50'},self.tx)
        def failure():
            self.tx(partner='Must roll back')
            raise ValueError('simulated crash before outer commit')
        with self.assertRaises(ValueError):
            storage.cached_mutation('/api/transactions',{'request_id':'b'*32},failure)
        self.assertEqual(len(app.state()['transactions']),1)

    def test_missing_known_database_never_creates_empty(self):
        (app.DATA/'steuerstudio.sqlite3').unlink()
        with self.assertRaises(ValueError):
            app.initialize()
        self.assertFalse((app.DATA/'steuerstudio.sqlite3').exists())

    def test_backup_external_copy_and_safe_restore(self):
        self.doc(filename='original.txt',file_base64=base64.b64encode(b'unchanged original').decode())
        self.tx()
        storage.save_draft({'key':'chat-form:new:2025','payload':{'question':'Noch nicht fertig'}})
        external=Path(self.temp.name)/'external'
        external.mkdir()
        app.save_settings({'backup_directory':str(external)})
        result=storage.snapshot()
        self.assertEqual(result['state'],'complete')
        raw=next(external.glob('*.zip')).read_bytes()
        restored=Path(self.temp.name)/'restored'
        checked=storage.verify_zip(raw,restored)
        self.assertEqual(checked['originals_checked'],1)
        con=sqlite3.connect(restored/'steuerstudio.sqlite3')
        self.assertEqual(con.execute('SELECT count(*) FROM drafts').fetchone()[0],1)
        self.assertGreater(con.execute('SELECT count(*) FROM legal_units').fetchone()[0],0)
        con.close()
        with self.assertRaises(ValueError):
            storage.verify_zip(raw,restored)
        external.rmdir() if not list(external.iterdir()) else None

    def test_corrupt_original_and_zip_paths_rejected(self):
        self.doc(filename='x.txt',file_base64=base64.b64encode(b'original').decode())
        d=app.state()['documents'][0]
        raw=app.backup_bytes()
        (app.DATA/'originale'/d['stored_name']).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            app.backup_bytes()
        result=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as before,zipfile.ZipFile(result,'w') as after:
            for name in before.namelist():
                after.writestr(name,b'wrong' if '/originale/' in name else before.read(name))
        with self.assertRaises(ValueError):
            storage.verify_zip(result.getvalue())
        result=io.BytesIO()
        with zipfile.ZipFile(result,'w') as z:
            z.writestr('../bad.txt','bad')
        with self.assertRaises(ValueError):
            storage.verify_zip(result.getvalue())

    def test_private_and_transfer_amounts_stay_separate(self):
        self.tx(scope='private')
        self.tx(scope='transfer',amount='100')
        self.tx(scope='business',amount='12,34')
        c=intelligence.chat_context('Ausgaben April 2025',2025,[])
        self.assertEqual(c['totals_by_month_and_scope']['2025-04/business']['expense_cents'],1234)
        self.assertEqual(c['totals_by_month_and_scope']['2025-04/private']['expense_cents'],4990)
        self.assertIn('Bereich',app.csv_bytes(2025).decode())

    def test_cash_meal_and_video_purchase_fields_are_persisted(self):
        meal=self.tx(payment_method='cash',cash_source='private_wallet',expense_kind='business_meal',
                     category='Geschäftsessen',business_purpose='Besprechung mit Sponsor',
                     meal_place='Stuttgart',meal_participants='Cay; Sponsor GmbH',
                     meal_occasion='Kooperation für Twitch',data_checked=True)
        video=self.tx(payment_method='cash',cash_source='private_wallet',expense_kind='video_purchase',
                      category='Videoproduktion',business_purpose='Zutaten für Rezeptvideo April',
                      scope='mixed',business_percent='80')
        rows={r['id']:r for r in app.state()['transactions']}
        self.assertEqual(rows[meal['id']]['payment_method'],'cash')
        self.assertEqual(rows[meal['id']]['cash_source'],'private_wallet')
        self.assertEqual(rows[meal['id']]['meal_participants'],'Cay; Sponsor GmbH')
        self.assertEqual(rows[video['id']]['business_percent'],80)
        self.assertIn('Zahlungsart',app.csv_bytes(2025).decode())

    def test_receipt_uploaded_with_transaction_is_saved_and_linked_atomically(self):
        raw=b'Lidl Rechnung\nZutaten fuer Aprilvideo 12,49 EUR'
        result=self.tx(partner='Lidl',title='Zutaten Aprilvideo',category='Videoproduktion',
                       receipt_filename='lidl-april.txt',receipt_title='Lidl April',
                       receipt_file_base64=base64.b64encode(raw).decode())
        state=app.state()
        self.assertEqual(len(state['transactions']),1)
        self.assertEqual(len(state['documents']),1)
        document=state['documents'][0]
        self.assertEqual(document['title'],'Lidl April')
        self.assertEqual(document['filename'],'lidl-april.txt')
        self.assertIn('Zutaten fuer Aprilvideo',document['body'])
        self.assertEqual(state['transactions'][0]['document_ids'],[document['id']])
        self.assertEqual((app.DATA/'originale'/document['stored_name']).read_bytes(),raw)
        # A repeated request with the same original must reuse the document, not create an orphan.
        again=self.tx(partner='Lidl',title='Zutaten Aprilvideo 2',category='Videoproduktion',
                      receipt_filename='lidl-april.txt',receipt_title='Lidl April',
                      receipt_file_base64=base64.b64encode(raw).decode())
        self.assertEqual(len(app.state()['documents']),1)
        self.assertEqual(app.state()['transactions'][1]['document_ids'],[document['id']])
        self.assertNotEqual(result['id'],again['id'])

    def test_receipt_failure_does_not_create_transaction(self):
        with self.assertRaises(ValueError):
            self.tx(receipt_filename='rechnung.docx',receipt_file_base64=base64.b64encode(b'nope').decode())
        self.assertEqual(app.state()['transactions'],[])
        self.assertEqual(app.state()['documents'],[])

    def test_pdf_account_statement_is_stored_as_readable_document_when_text_is_available(self):
        # A minimal invalid PDF still exercises the durable-original path; real text PDFs
        # are extracted by pypdf when the optional dependency is installed.
        result=app.create_document({'title':'Kontoauszug April 2025','kind':'Kontoauszug','year':2025,
                                    'filename':'konto-april.pdf','file_base64':base64.b64encode(b'%PDF-1.4').decode()})
        document=app.state()['documents'][0]
        self.assertEqual(result['id'],document['id'])
        self.assertEqual(document['kind'],'Kontoauszug')
        self.assertEqual(document['filename'],'konto-april.pdf')
        self.assertEqual((app.DATA/'originale'/document['stored_name']).read_bytes(),b'%PDF-1.4')

    def test_checked_special_cash_entries_require_explanation(self):
        with self.assertRaises(ValueError):
            self.tx(payment_method='cash',cash_source='private_wallet',expense_kind='business_meal',data_checked=True)
        with self.assertRaises(ValueError):
            self.tx(payment_method='cash',cash_source='private_wallet',expense_kind='video_purchase',data_checked=True)
        with self.assertRaises(ValueError):
            self.tx(payment_method='cash',cash_source='private_wallet',account_id='account_n26')

    def test_tasks_reentrant_and_no_invented_deadlines(self):
        self.assertEqual(studio.add_suggestions()['count'],8)
        self.assertEqual(studio.add_suggestions()['count'],0)
        self.assertTrue(all(not t['due_confirmed'] and not t['due_on'] for t in app.state()['tasks']))

    def test_facts_reopened_when_document_changes(self):
        did=self.doc()['id']
        intelligence.save_fact({'year':2025,'title':'Vertragspartner','value':'A','source_id':did,'source_note':'Seite 1','status':'confirmed'})
        d=app.state()['documents'][0]
        app.update_document(did,{**d,'body':'Korrigierter Originaltext zur Prüfung'})
        self.assertEqual(intelligence.facts()[0]['status'],'open')

    def test_law_download_versions_and_year_not_assumed(self):
        source={'id':'test','title':'Testgesetz','type':'xmlzip','url':'https://www.gesetze-im-internet.de/estg/xml.zip'}
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:
            z.writestr('test.xml','<dokumente><norm><metadaten><enbez>§ 1</enbez></metadaten><textdaten><text><Content><P>Geltender Testtext.</P></Content></text></textdaten></norm></dokumente>')
        parsed=laws.parse_source(source,data.getvalue())
        self.assertEqual(parsed[0],('§ 1','Geltender Testtext.'))
        self.assertFalse(laws.allowed('http://www.gesetze-im-internet.de/estg/'))
        self.assertFalse(laws.allowed('https://www.gesetze-im-internet.de.evil.test/'))
        self.assertFalse(laws.allowed('https://127.0.0.1/admin'))
        matches=laws.search('Umzug Kuppenheim',2025)
        self.assertTrue(matches)
        self.assertTrue(all(not m['year_checked'] for m in matches))

    def test_three_pass_chat_blind_review_persistence_and_no_mutations(self):
        self.doc()
        studio.add_suggestions()
        seen=[]
        models=['qwen3.8:27b','gemma4:31b','gpt-oss:20b']
        def fake(path,payload=None,timeout=5):
            if path=='/api/tags':
                return {'models':[{'name':m,'size':100,'digest':'test-'+m} for m in models]}
            seen.append(payload)
            response={'answer':'Bitte die Abgabeprotokolle für 2025 prüfen.','missing':['Fristnachweis'],'conflicts':['Status noch unbekannt'] if len(seen)==2 else [],'citations':[],'tasks':[{'title':'Protokolle sammeln','reason':'Abgabestand prüfen'}]}
            return {'message':{'content':json.dumps(response)}}
        with patch.object(app,'ollama',side_effect=fake):
            intelligence.start_chat({'question':'Welche Unterlagen fehlen für 2025?','year':2025,'document_ids':[]})
            deadline=time.monotonic()+5
            while app.AI_LOCK.locked() and time.monotonic()<deadline:
                time.sleep(.01)
        items=intelligence.chat_list(2025)
        self.assertEqual(items[0]['state'],'complete',items[0]['error'])
        self.assertEqual(len(seen),3)
        self.assertEqual(seen[0]['messages'][1],seen[1]['messages'][1])
        self.assertTrue(all(p['keep_alive']==0 for p in seen))
        self.assertIn('Status noch unbekannt',items[0]['coordinator_json']['conflicts'])
        self.assertEqual(len(app.state()['tasks']),8)
        app.initialize()
        self.assertEqual(intelligence.chat_list(2025)[0]['question'],items[0]['question'])

    def test_invented_citation_is_flagged_not_verified(self):
        normalized=intelligence.normalize_answer({'answer':'Test','citations':[{'source_id':'L:not-real','quote':'ausgedachte Quelle'}]}, {'sources':[]})
        self.assertEqual(normalized['citations'],[])
        self.assertEqual(normalized['citation_errors'],1)
        self.assertFalse(normalized['missing'])
        self.assertTrue(normalized['evidence_warnings'])


if __name__=='__main__':
    unittest.main()
