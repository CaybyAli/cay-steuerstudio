"""0.3.5: month checkpoints, cent reconciliation and explicit discrepancy review."""
import base64,copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,banking,intake,pdf_review,recycle,intelligence
from test_intake import pdf_bytes
from test_pdf_month_review import pages

FEB='''EUR-Konto Kontoauszug Nr. 2/2024 erstellt am 28.02.2024
Gesamtumsatz: 2,00 S 10,00 H
Bu-Tag Wert Vorgang
alter Kontostand 152,99 H
02.02. 02.02. Gutschrift PN:1 10,00 H
 Testkunde
03.02. 03.02. Kartenzahlung PN:1 2,00 S
 Testanbieter
neuer Kontostand vom 28.02.2024 160,99 H
'''
def two_months(bad=False):
    return pages()+[{'page':4,'text':FEB.replace('160,99 H','161,99 H') if bad else FEB,'method':'pdf_text'}]

class PartialPDFTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.tmp.name)/'data';app.initialize()
    def tearDown(self):app.DATA=self.old;self.tmp.cleanup()
    def read(self,ps=None):
        self.upload={'year':2024,'account_id':'account_volksbank','filename':'Monate.pdf','file_base64':base64.b64encode(pdf_bytes()).decode()}
        j=intake.upload(self.upload)['job']
        with patch.object(intake,'pdf_pages',return_value=ps or two_months()):intake.run_pdf(j['id'],[])
        return intake.job(j['id'])
    def payload(self,j,months=None):return {'id':j['id'],'rows':[{**r,'scope':'private','reviewed':True} for r in j['result']['rows']],'checked':True,'months':months or ['2024-01']}
    def test_good_month_commits_even_when_another_has_difference_or_invalid_row(self):
        j=self.read(two_months(True));p=self.payload(j);p['rows'][-1]['amount']='-20,00'
        result=intake.approve_pdf(p);self.assertTrue(result['result']['partial']);self.assertEqual(len(app.state()['transactions']),10)
        report=pdf_review.check({'id':j['id']})['review'];self.assertEqual([m['status'] for m in report['months']],['approved','blocked'])
        self.assertIsNone(intake.job(j['id'])['import_id'])
    def test_exact_values_and_turnover_even_if_end_balance_matches(self):
        ps=two_months();ps[-1]['text']=ps[-1]['text'].replace('10,00 H\nBu-Tag','11,00 H\nBu-Tag');j=self.read(ps)
        r=pdf_review.check(self.payload(j))['review'];c=r['checks'][1]
        self.assertEqual((c['opening_cents'],c['incoming_cents'],c['outgoing_cents'],c['calculated_closing_cents'],c['difference_cents'],c['credit_difference_cents']),(15299,1000,200,16099,0,100));self.assertTrue(c['mismatch'])
    def test_override_needs_explicit_consent_and_note_then_keeps_original_and_history(self):
        j=self.read(two_months(True));p=self.payload(j,['2024-02'])
        for override in ({},{'2024-02':{'accepted':True}},{'2024-02':{'note':'Original ausführlich verglichen'}}):
            with self.subTest(override=override),self.assertRaises(pdf_review.ReviewRequired) as cm:intake.approve_pdf({**p,'overrides':override})
            self.assertEqual(cm.exception.details['kind'],'pdf_reconciliation');self.assertEqual(app.state()['transactions'],[])
        p['overrides']={'2024-02':{'accepted':True,'note':'Original selbst geprüft, Kontrollwert bleibt unklar.'}}
        r=intake.approve_pdf(p);self.assertEqual(r['result']['imported'],2)
        a=pdf_review.approvals(j['id'])[0];self.assertEqual(a['report']['checks'][0]['difference_cents'],100);self.assertIn('unklar',a['note'])
        self.assertTrue(all('Abweichung' in t['notes'] for t in app.state()['transactions']))
        with app.db() as con:self.assertEqual(con.execute('SELECT original FROM bank_imports').fetchone()[0],base64.b64decode(self.upload['file_base64']))
    def test_restart_repeated_approval_and_same_original_never_double_book(self):
        j=self.read();p=self.payload(j);intake.approve_pdf(p);app.initialize()
        self.assertTrue(intake.approve_pdf(p)['already_approved']);self.assertEqual(len(app.state()['transactions']),10)
        j=intake.upload(self.upload)['job'];self.assertEqual(len(j['approvals']),1)
        r=intake.approve_pdf(self.payload(j,['2024-02']));self.assertFalse(r['result']['partial']);self.assertEqual(len(app.state()['transactions']),12)
        again=intake.approve_pdf(self.payload(j,['2024-02']));self.assertTrue(again['already_approved'])
        with app.db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM bank_imports').fetchone()[0],1)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM bank_rows').fetchone()[0],12)
            state,total=con.execute('SELECT state,result_json FROM bank_imports').fetchone();self.assertEqual(state,'committed');self.assertEqual(json.loads(total)['imported'],12)
    def test_two_approved_months_in_one_atomic_commit(self):
        j=self.read();r=intake.approve_pdf(self.payload(j,['2024-01','2024-02']));self.assertEqual(r['result']['imported'],12)
        self.assertEqual([a['result']['imported'] for a in pdf_review.approvals(j['id'])],[10,2])
    def test_wrong_account_rolls_back_all_selected_months_and_checkpoints(self):
        j=self.read();p=self.payload(j,['2024-01','2024-02']);banking.save_account({'id':'account_volksbank','name':'Volksbank','bank':'volksbank','role':'historical','status':'active','opened_on':'2024-01-15'})
        r=intake.approve_pdf(p);self.assertTrue(r['needs_review'])
        with self.assertRaises(ValueError):banking.commit({'id':r['preview']['id'],'checked':True})
        self.assertEqual(app.state()['transactions'],[]);self.assertEqual(pdf_review.approvals(j['id']),[])
    def test_missing_actual_payment_not_bypassed_with_balance_override(self):
        j=self.read();p=self.payload(j);p['rows'][0].update(excluded=True,exclusion_reason='not_payment');p['overrides']={'2024-01':{'accepted':True,'note':'Alles im Original geprüft.'}}
        with self.assertRaises(pdf_review.ReviewRequired) as cm:intake.approve_pdf(p)
        self.assertEqual(cm.exception.details['review']['months'][0]['missing'][0]['amount_cents'],10000)
        self.assertEqual(app.state()['transactions'],[])
    def test_excluded_fee_details_and_already_recorded_real_rows(self):
        j=self.read();p=self.payload(j);p['rows'][0].update(excluded=True,exclusion_reason='already_recorded');p['rows'].append({'page':2,'booked_on':'2024-01-31','amount':'-9,90','excluded':True,'exclusion_reason':'not_payment'})
        r=intake.approve_pdf(p);self.assertEqual((r['result']['imported'],r['result']['skipped']),(9,1));self.assertEqual(pdf_review.approvals(j['id'])[0]['report']['checks'][0]['difference_cents'],0)
    def test_partial_duplicate_preview_link_and_stale_commit(self):
        j=self.read();intake.approve_pdf(self.payload(j));t=app.save_transaction({'direction':'income','scope':'private','amount':'10,00','paid_on':'2024-02-02','partner':'Manuell','title':'Schon da','payment_method':'bank','account_id':'account_volksbank'})
        r=intake.approve_pdf(self.payload(intake.job(j['id']),['2024-02']));self.assertTrue(r['needs_review']);iid=r['preview']['id']
        banking.save_preview({'id':iid,'edits':{'11':{'choice':'link:'+t['id']}}});j=intake.reopen_pdf({'import_id':iid})
        with self.assertRaises(ValueError):banking.commit({'id':iid,'checked':True})
        r=intake.approve_pdf(self.payload(j,['2024-02']));self.assertEqual(r['result']['linked'],1);self.assertEqual(len(app.state()['transactions']),12)
    def test_stale_autosave_cannot_alter_committed_row_or_add_to_closed_month(self):
        j=self.read();p=self.payload(j);intake.approve_pdf(p);stale=copy.deepcopy(p);stale['rows'][0]['amount']='9999,00';stale['rows'][0]['scope']='business';intake.save_pdf_review(stale)
        saved=intake.job(j['id']);self.assertEqual(saved['result']['rows'][0]['amount'],'100,00');self.assertEqual(saved['result']['rows'][0]['scope'],'private')
        stale['rows'].append(copy.deepcopy(stale['rows'][0]))
        with self.assertRaises(ValueError):intake.save_pdf_review(stale)
    def test_trash_restore_keeps_approved_months_and_pending_draft(self):
        j=self.read();intake.approve_pdf(self.payload(j));j=intake.job(j['id']);p=self.payload(j);p['rows'][-1]['review_note']='Februar noch prüfen';intake.save_pdf_review(p)
        tid=recycle.remove({'job_id':j['id']})['id'];restored=intake.upload({**self.upload,'restore_trash_id':tid})['job'];self.assertEqual(len(restored['approvals']),1);self.assertEqual(restored['result']['rows'][-1]['review_note'],'Februar noch prüfen');self.assertEqual(len(app.state()['transactions']),10)
    def test_uncorroborated_or_missing_controls_never_shown_as_matching(self):
        ps=two_months();ps[-1]['text']='\n'.join(s for s in ps[-1]['text'].splitlines() if not any(v in s for v in ('Kontostand','Gesamtumsatz')));j=self.read(ps)
        r=pdf_review.check(self.payload(j))['review'];self.assertEqual(r['months'][1]['status'],'unverified');self.assertIsNone(r['checks'][1]['difference_cents'])
    def test_approved_months_cannot_be_reread(self):
        j=self.read();intake.approve_pdf(self.payload(j))
        with self.assertRaisesRegex(ValueError,'Monate übernommen'):intake.start({'job_id':j['id'],'use_ai':False})
        with self.assertRaisesRegex(ValueError,'Monate übernommen'):intake.run_pdf(j['id'],[])
    def test_shared_statement_controls_not_invented_per_month(self):
        ps=pages();ps[0]['text']=ps[0]['text'].replace('08.01. 08.01.','08.02. 08.02.');j=self.read(ps);r=pdf_review.check(self.payload(j))['review'];self.assertEqual(r['checks'][0]['months'],['2024-01','2024-02']);self.assertEqual(len(r['checks']),1)
    def test_local_readers_are_independent_and_never_modify_data(self):
        j=self.read(two_months(True));p=self.payload(j);before=copy.deepcopy(intake.job(j['id'])['result'])
        with patch.object(intelligence,'role_models',return_value=(['a','b','c'],{})),patch.object(intelligence,'call_model',return_value={'explanation':'Prüfe den Endstand im Original.'}) as model:
            r=pdf_review.explain({**p,'month':'2024-02'})
        self.assertEqual(model.call_count,3);self.assertEqual(model.call_args_list[0].args[2],model.call_args_list[1].args[2]);self.assertEqual(len(r['answers']),3);self.assertEqual(intake.job(j['id'])['result'],before);self.assertEqual(app.state()['transactions'],[])
    def test_local_reader_failure_remains_advice_only(self):
        j=self.read()
        with patch.object(intelligence,'role_models',return_value=(['a','b','c'],{})),patch.object(intelligence,'call_model',side_effect=ValueError('offline')):
            r=pdf_review.explain({**self.payload(j),'month':'2024-01'})
        self.assertTrue(all('error' in a for a in r['answers']));self.assertFalse(app.AI_LOCK.locked())
    def test_override_draft_survives_restart(self):
        j=self.read();p=self.payload(j);p['overrides']={'2024-02':{'accepted':True,'note':'Kontostand am Original geprüft.'}};intake.save_pdf_review(p);app.initialize();self.assertEqual(intake.job(j['id'])['result']['month_overrides'],p['overrides'])

    def test_failed_second_payment_rolls_back_first_payment_and_month_checkpoint(self):
        j=self.read();original=app.save_transaction;calls=[]
        def fail_later(*args,**kwargs):
            calls.append(1)
            if len(calls)==2:raise ValueError('Simulierter Schreibfehler')
            return original(*args,**kwargs)
        with patch.object(app,'save_transaction',side_effect=fail_later),self.assertRaisesRegex(ValueError,'Schreibfehler'):
            intake.approve_pdf(self.payload(j,['2024-01','2024-02']))
        self.assertEqual(app.state()['transactions'],[]);self.assertEqual(pdf_review.approvals(j['id']),[])
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM bank_rows').fetchone()[0],0)
        self.assertEqual(intake.approve_pdf(self.payload(j))['result']['imported'],10)
    def test_stale_preview_token_cannot_confirm_a_later_selection(self):
        j=self.read();t=app.save_transaction({'direction':'income','scope':'private','amount':'100,00','paid_on':'2024-01-08','partner':'Vorhanden','title':'Einlage','payment_method':'bank','account_id':'account_volksbank'})
        old=intake.approve_pdf(self.payload(j))['preview'];j=intake.reopen_pdf({'import_id':old['id']});new=intake.approve_pdf(self.payload(j))['preview']
        self.assertNotEqual(old['pdf_selection_token'],new['pdf_selection_token'])
        with self.assertRaisesRegex(ValueError,'nicht mehr aktuell'):banking.commit({'id':new['id'],'checked':True,'pdf_selection_token':old['pdf_selection_token'],'choices':{'1':'link:'+t['id']}})
        res=banking.commit({'id':new['id'],'checked':True,'pdf_selection_token':new['pdf_selection_token'],'choices':{'1':'link:'+t['id']}})
        self.assertEqual((res['imported'],res['linked']),(9,1));self.assertEqual(len(app.state()['transactions']),10)
        self.assertEqual(pdf_review.approvals(j['id'])[0]['rows'][0]['row']['choice'],'link:'+t['id'])
    def test_override_warning_is_preserved_on_linked_manual_payment(self):
        j=self.read(two_months(True));t=app.save_transaction({'direction':'income','scope':'private','amount':'10,00','paid_on':'2024-02-02','partner':'Vorhanden','title':'Einlage','notes':'Meine alte Notiz','payment_method':'bank','account_id':'account_volksbank'})
        p=self.payload(j,['2024-02']);p['overrides']={'2024-02':{'accepted':True,'note':'Original selbst geprüft, Differenz dokumentiert.'}}
        preview=intake.approve_pdf(p)['preview'];banking.commit({'id':preview['id'],'checked':True,'pdf_selection_token':preview['pdf_selection_token'],'choices':{'11':'link:'+t['id']}})
        saved=next(x for x in app.state()['transactions'] if x['id']==t['id']);self.assertIn('Meine alte Notiz',saved['notes']);self.assertIn('Mit Abweichung',saved['notes'])

if __name__=='__main__':unittest.main()
