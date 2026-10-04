"""Source explanations and exact-file trash restore: no guessed or duplicate payments."""
import base64,copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,banking,intake,recycle,statements
from test_intake import pdf_bytes
from test_pdf_month_review import pages

class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.tmp.name)/'data';app.initialize()
    def tearDown(self):app.DATA=self.old;self.tmp.cleanup()
    def pdf_payload(self,raw=None):return {'year':2024,'account_id':'account_volksbank','filename':'Auszug.pdf','file_base64':base64.b64encode(raw or pdf_bytes()).decode()}
    def read(self,ps=None):
        j=intake.upload(self.pdf_payload())['job']
        with patch.object(intake,'pdf_pages',return_value=ps or pages()):intake.run_pdf(j['id'],[])
        return intake.job(j['id'])
    def review(self,j):return {'id':j['id'],'checked':True,'rows':[{**r,'scope':'private','reviewed':True} for r in j['result']['rows']]}
    def diagnosis(self,p):
        with self.assertRaises(intake.PDFReviewError) as cm:intake.check_pdf_review(p)
        self.assertEqual(cm.exception.details['kind'],'pdf_rows');return cm.exception.details['diagnostics']
    def test_sign_explanation_points_to_exact_payment_on_page_nine(self):
        ps=pages();ps[0]['page']=8;ps[1]['page']=9;ps[2]['page']=10;j=self.read(ps);p=self.review(j);p['rows'][8]['amount']='11,82'
        d=self.diagnosis(p)[0];self.assertEqual((d['index'],d['page']),(8,9));self.assertIn('vertauscht',d['explanation']);self.assertEqual(d['candidates'][0]['amount_cents'],-1182)
        with self.assertRaises(intake.PDFReviewError):intake.approve_pdf(p)
        self.assertEqual(app.state()['transactions'],[])
        p['rows'][8].update({k:v for k,v in d['candidates'][0].items() if k not in {'explanation','differences','match'}})
        self.assertTrue(intake.check_pdf_review(p)['ok']);self.assertEqual(intake.approve_pdf(p)['result']['imported'],10)
    def test_value_date_is_explained_not_silently_changed(self):
        j=self.read();p=self.review(j);p['rows'][-1]['booked_on']='2024-02-01';d=self.diagnosis(p)[0]
        self.assertIn('Wertstellung',d['explanation']);self.assertEqual(d['candidates'][0]['booked_on'],'2024-01-31');self.assertEqual(p['rows'][-1]['booked_on'],'2024-02-01')
    def test_incorrect_amount_and_page_are_compared_with_source(self):
        j=self.read();p=self.review(j);p['rows'][8]['page']=1;p['rows'][8]['amount']='-118,20';d=self.diagnosis(p)[0]
        self.assertIn('amount',d['candidates'][0]['differences']);self.assertIn('page',d['candidates'][0]['differences']);self.assertEqual(d['candidates'][0]['page'],2)
    def test_stale_internal_id_with_exact_unique_quote_is_repaired(self):
        j=self.read();p=self.review(j);p['rows'][0]['source_id']='old-hash-from-previous-reader'
        self.assertTrue(intake.check_pdf_review(p)['ok']);self.assertEqual(intake.approve_pdf(p)['result']['imported'],10)
    def test_stale_id_does_not_repair_wrong_amount_or_guessed_quote(self):
        j=self.read()
        for change in [{'amount':'-100,00'},{'quote':'irgendwo Einzahlung 100 Euro'}]:
            p=self.review(j);p['rows'][0].update(source_id='old-id',**change);self.assertTrue(self.diagnosis(p))
        self.assertEqual(app.state()['transactions'],[])
    def test_identical_repeated_originals_stay_ambiguous_without_reference(self):
        ps=pages();ps[0]['text']=ps[0]['text'].replace('                                  Übertrag auf Blatt 2', '08.01. 08.01. Einzahlung PN:2538 100,00 H\n              VOLKSBANK BEISPIEL\n              Filiale Beispiel/DE\n              08.01.2024/19:40 girocard GA 00000000/00000001/000001\n                                  Übertrag auf Blatt 2')
        j=self.read(ps);p=self.review(j);p['rows'][0]['source_id']='missing-hash';d=self.diagnosis(p)[0]
        self.assertGreaterEqual(len(d['candidates']),2);self.assertIn('Mehrere',d['explanation']);self.assertEqual(app.state()['transactions'],[])
    def test_multiple_invalid_rows_are_reported_together(self):
        j=self.read();p=self.review(j);p['rows'][0]['amount']='-100,00';p['rows'][8]['amount']='11,82'
        self.assertEqual([d['index'] for d in self.diagnosis(p)],[0,8])
    def test_no_reliable_candidate_is_explicit_and_never_invented(self):
        j=self.read();p=self.review(j);p['rows'].append({'page':2,'booked_on':'2024-01-01','amount':'-9,90','quote':'Entgelt Kontoführung 3101 9,90S','currency':'EUR','partner':'Kontoführung','purpose':'Entgelt','scope':'business','reviewed':True})
        d=self.diagnosis(p)[0];self.assertEqual(d['candidates'],[]);self.assertIn('Gebührenaufschlüsselung',d['explanation']);self.assertEqual(app.state()['transactions'],[])
    def test_changed_reference_can_offer_correct_new_original_without_reverting(self):
        j=self.read();p=self.review(j);correct=j['result']['rows'][1];p['rows'][0].update({k:correct[k] for k in ['booked_on','amount','quote','partner','purpose']})
        d=self.diagnosis(p)[0];self.assertTrue(any(c['source_id']==correct['source_id'] for c in d['candidates']))
    def test_pdf_reupload_offers_restore_preserves_draft_and_retries(self):
        raw=pdf_bytes();payload=self.pdf_payload(raw);j=intake.upload(payload)['job']
        with patch.object(intake,'pdf_pages',return_value=pages()):intake.run_pdf(j['id'],[])
        j=intake.job(j['id']);p=self.review(j);p['rows'][0]['review_note']='Meine private Einzahlung';intake.save_pdf_review(p)
        trash=recycle.remove({'job_id':j['id']})
        with self.assertRaises(recycle.UploadInTrash) as cm:intake.upload(payload)
        self.assertEqual(cm.exception.details['trash_id'],trash['id']);self.assertEqual(intake.jobs(2024),[])
        restored=intake.upload({**payload,'restore_trash_id':trash['id']});self.assertTrue(restored['restored']);self.assertEqual(restored['job']['id'],j['id']);self.assertEqual(restored['job']['result']['rows'][0]['review_note'],'Meine private Einzahlung')
        again=intake.upload({**payload,'restore_trash_id':trash['id']});self.assertEqual(again['job']['id'],j['id']);app.initialize();self.assertEqual(len(intake.jobs(2024)),1);self.assertEqual(len(app.state()['documents']),1)
    def test_csv_reupload_restores_same_preview_with_decisions(self):
        payload={'year':2025,'account_id':'account_volksbank','filename':'Auszug.csv','file_base64':base64.b64encode(b'Buchungstag;Name Zahlungsbeteiligter;Verwendungszweck;Betrag;Waehrung\n03.04.2025;Test;Abo;-12,34;EUR\n').decode()}
        p=intake.upload(payload)['preview'];banking.save_preview({'id':p['id'],'edits':{str(p['rows'][0]['line']):{'scope':'private','review_note':'Privates Abo','choice':'skip'}}});trash=recycle.remove({'import_id':p['id']})
        with self.assertRaises(recycle.UploadInTrash):intake.upload(payload)
        restored=intake.upload({**payload,'restore_trash_id':trash['id']});self.assertEqual(restored['preview']['id'],p['id']);self.assertEqual(restored['preview']['rows'][0]['review_note'],'Privates Abo');self.assertEqual(restored['preview']['rows'][0]['choice'],'skip')
        self.assertEqual(intake.upload({**payload,'restore_trash_id':trash['id']})['preview']['id'],p['id'])
    def test_confirmed_statement_restore_never_books_again(self):
        raw=pdf_bytes();payload=self.pdf_payload(raw);j=intake.upload(payload)['job']
        with patch.object(intake,'pdf_pages',return_value=pages()):intake.run_pdf(j['id'],[])
        j=intake.job(j['id']);result=intake.approve_pdf(self.review(j));before=app.state()['transactions'];trash=recycle.remove({'job_id':j['id']})
        restored=intake.upload({**payload,'restore_trash_id':trash['id']});self.assertTrue(banking.saved_preview(restored['job']['import_id'])['already_imported']);self.assertEqual(app.state()['transactions'],before)
        self.assertEqual(intake.approve_pdf(self.review(j))['result'],result['result'])
    def test_different_file_cannot_restore_an_unrelated_trash_item(self):
        raw=pdf_bytes();payload=self.pdf_payload(raw);j=intake.upload(payload)['job'];trash=recycle.remove({'job_id':j['id']})
        with self.assertRaises(ValueError):intake.upload({**payload,'file_base64':base64.b64encode(raw+b'\n% different file').decode(),'restore_trash_id':trash['id']})
        self.assertEqual(len(recycle.items(2024)),1);self.assertEqual(intake.jobs(2024),[])
    def test_failed_restore_followup_rolls_back_restore(self):
        raw=pdf_bytes();payload=self.pdf_payload(raw);j=intake.upload(payload)['job'];trash=recycle.remove({'job_id':j['id']})
        with patch.object(app,'create_document',side_effect=ValueError('Speichern fehlgeschlagen')),self.assertRaises(ValueError):intake.upload({**payload,'restore_trash_id':trash['id']})
        self.assertEqual(len(recycle.items(2024)),1);self.assertEqual(intake.jobs(2024),[])

    def test_resolved_source_error_does_not_require_a_redundant_free_text_note(self):
        j=self.read();intake.update(j['id'],result_json=app.enc({**j['result'],'issues':['Seite 1, Zahlung 1: Textnachweis fehlt.']}))
        self.assertEqual(intake.approve_pdf(self.review(j))['result']['imported'],10)
    def test_already_used_original_is_identified_in_comparison(self):
        j=self.read();p=self.review(j);correct=j['result']['rows'][1];p['rows'][0].update({k:correct[k] for k in ['booked_on','amount','quote','partner','purpose']})
        d=self.diagnosis(p)[0];candidate=next(c for c in d['candidates'] if c['source_id']==correct['source_id']);self.assertTrue(candidate['already_used'])
