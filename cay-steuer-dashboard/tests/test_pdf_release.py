"""Release regression: explicit exclusions, bank fees, legacy previews, retries."""
import base64,copy,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,banking,intake,intelligence,statements
from test_intake import pdf_bytes
from test_pdf_month_review import pages

class PDFReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.tmp.name)/'data';app.initialize()
    def tearDown(self):app.DATA=self.old;self.tmp.cleanup()
    def read(self,ps=None):
        j=intake.upload({'year':2024,'account_id':'account_volksbank','filename':'Auszug.pdf','file_base64':base64.b64encode(pdf_bytes()).decode()})['job']
        with patch.object(intake,'pdf_pages',return_value=ps or pages()):intake.run_pdf(j['id'],[])
        return intake.job(j['id'])
    def payload(self,j):return {'id':j['id'],'checked':True,'rows':[{**r,'scope':'private','reviewed':True} for r in j['result']['rows']]}
    def manual(self):return app.save_transaction({'direction':'income','scope':'private','amount':'100,00','paid_on':'2024-01-08','partner':'Privat','title':'Einzahlung','account_id':'account_volksbank','payment_method':'bank'})
    def test_skip_manual_keeps_statement_balance_and_never_duplicates(self):
        self.manual();j=self.read();p=self.payload(j);p['rows'][0].update(excluded=True,exclusion_reason='already_recorded',reviewed=False)
        r=intake.approve_pdf(p);self.assertTrue(r['committed']);self.assertEqual(r['result']['imported'],9);self.assertEqual(r['result']['skipped'],1)
        self.assertEqual(r,intake.approve_pdf(p));app.initialize();self.assertEqual(len(app.state()['transactions']),10)
        self.assertEqual(sum(t['amount_cents']*(1 if t['direction']=='income' else -1) for t in app.state()['transactions']),15299)
        self.assertTrue(intake.job(j['id'])['result']['rows'][0]['excluded'])
    def test_skip_all_books_nothing_and_retry_remains_idempotent(self):
        j=self.read();p=self.payload(j)
        for r in p['rows']:r.update(excluded=True,exclusion_reason='already_recorded',reviewed=False)
        res=intake.approve_pdf(p);self.assertEqual(res['result']['imported'],0);self.assertEqual(res['result']['skipped'],10)
        self.assertEqual(intake.approve_pdf(p),res);self.assertEqual(app.state()['transactions'],[])
    def test_false_fee_detail_can_be_removed_but_total_stays(self):
        j=self.read();p=self.payload(j);p['rows'].append({'page':2,'booked_on':'2024-01-31','amount':'-9,90','currency':'EUR','partner':'Kontoführung','purpose':'Gebührenanteil','quote':'Entgelt Kontoführung 3101 9,90S','excluded':True,'exclusion_reason':'not_payment'})
        r=intake.approve_pdf(p);self.assertEqual(r['result']['imported'],10)
        ts=app.state()['transactions'];self.assertEqual(len([t for t in ts if t['amount_cents']==1182]),1);self.assertFalse(any(t['amount_cents']==990 for t in ts))
        with app.db() as con:
            import json
            preview=json.loads(con.execute('SELECT preview_json FROM bank_imports').fetchone()[0]);self.assertEqual(preview['pdf_exclusions'][0]['reason'],'not_payment')
    def test_a_second_extraction_of_same_source_can_be_excluded(self):
        j=self.read();p=self.payload(j);p['rows'].append({**p['rows'][0],'excluded':True,'exclusion_reason':'not_payment'})
        self.assertEqual(intake.approve_pdf(p)['result']['imported'],10)
    def test_actual_table_payment_cannot_disappear_as_fee_detail(self):
        j=self.read();p=self.payload(j);p['rows'][0].update(excluded=True,exclusion_reason='not_payment')
        with self.assertRaisesRegex(ValueError,'echte Zahlung'):intake.approve_pdf(p)
        self.assertEqual(app.state()['transactions'],[])
    def test_reason_and_exclusion_type_must_be_explicit(self):
        j=self.read()
        for values in [{'excluded':True},{'excluded':'true','exclusion_reason':'not_payment'},{'excluded':True,'exclusion_reason':'delete'}]:
            p=self.payload(j);p['rows'][0].update(values)
            with self.subTest(values=values),self.assertRaises(ValueError):intake.approve_pdf(p)
        self.assertEqual(app.state()['transactions'],[])
    def test_exclusion_survives_restart_rereading_and_can_be_restored(self):
        j=self.read();p=self.payload(j);p['rows'][0].update(excluded=True,exclusion_reason='already_recorded');intake.save_pdf_review(p)
        app.initialize()
        with patch.object(intake,'pdf_pages',return_value=pages()):intake.run_pdf(j['id'],[])
        j=intake.job(j['id']);self.assertTrue(j['result']['rows'][0]['excluded']);p=self.payload(j);p['rows'][0].update(excluded=False,exclusion_reason='')
        self.assertEqual(intake.approve_pdf(p)['result']['imported'],10)
    def test_old_preview_can_reopen_blocks_stale_commit_and_keeps_link(self):
        self.manual();j=self.read();p=self.payload(j);result=intake.approve_pdf(p);iid=result['preview']['id'];row=result['preview']['rows'][0];choice='link:'+row['manual_matches'][0]['id']
        banking.save_preview({'id':iid,'edits':{'1':{'choice':choice,'review_note':'Schon manuell'}}})
        j=intake.reopen_pdf({'import_id':iid});self.assertEqual(j['state'],'review');self.assertEqual(j['result']['rows'][0]['choice'],choice)
        with self.assertRaisesRegex(ValueError,'PDF-Auszug zuerst'):banking.commit({'id':iid,'checked':True})
        # Opening the old import-history entry twice must still recover the review.
        j=intake.reopen_pdf({'import_id':iid});result=intake.approve_pdf(self.payload(j));self.assertEqual(result['result']['linked'],1);self.assertEqual(len(app.state()['transactions']),10)
        with self.assertRaisesRegex(ValueError,'bereits übernommen'):intake.reopen_pdf({'import_id':iid})
    def test_reopen_saved_skip_and_restore(self):
        self.manual();j=self.read();p=self.payload(j);result=intake.approve_pdf(p);iid=result['preview']['id']
        banking.save_preview({'id':iid,'edits':{'1':{'choice':'skip'}}});j=intake.reopen_pdf({'import_id':iid});self.assertTrue(j['result']['rows'][0]['excluded'])
        self.assertEqual(intake.approve_pdf(self.payload(j))['result']['skipped'],1);self.assertEqual(len(app.state()['transactions']),10)
    def test_unknown_appendix_does_not_send_table_to_llm_or_lose_coverage(self):
        j=self.read();ps=pages()[:2]+[{'page':3,'text':'Weitere Informationen der Bank ohne Zahlungsdaten.','method':'pdf_text'}]
        with patch.object(intake,'pdf_pages',return_value=ps),patch.object(intelligence,'call_model',side_effect=[{'rows':[]},{'rows':[]},{'summary':'Original prüfen'}]) as model:
            intake.run_pdf(j['id'],['a','b','c'])
        self.assertEqual(model.call_count,3);self.assertIn('Weitere Informationen',model.call_args_list[0].args[2]);self.assertNotIn('100,00 H',model.call_args_list[0].args[2])
        j=intake.job(j['id']);self.assertEqual(j['result']['difference_cents'],0);self.assertEqual(len(j['result']['balance_checks']),1);p=self.payload(j);p['rows'].pop()
        with self.assertRaisesRegex(ValueError,'echte Zahlung'):intake.approve_pdf(p)
        self.assertEqual(intake.approve_pdf(self.payload(j))['result']['imported'],10)
    def test_generic_fee_components_are_visible_exclusions_independent_fee_remains(self):
        text='''Anfangssaldo 100,00 EUR
30.04.2025 Abschluss -10,00 EUR
Entgeltaufstellung
Kontoführung 01.04.2025 bis 30.04.2025 6,00 EUR
Buchungsposten 01.04.2025 bis 30.04.2025 4,00 EUR
30.04.2025 Kartengebühr -2,00 EUR
Endsaldo 88,00 EUR'''
        ps={'page':1,'text':text,'method':'pdf_text'}
        lines=[text.splitlines()[i] for i in [1,3,4,5]]
        raw=[{'booked_on':'2025-04-30','amount':a,'currency':'EUR','partner':'Bank','purpose':'Gebühr','quote':q} for a,q in zip(['-10,00','-6,00','-4,00','-2,00'],lines)]
        rows,issues=intake.read_rows_with_issues({'rows':raw},ps,2025)
        self.assertEqual([r.get('excluded',False) for r in rows],[False,True,True,False]);self.assertEqual(sum(r['amount_cents'] for r in rows if not r.get('excluded')),-1200)
        j=self.read();intake.update(j['id'],year=2025,pages_json=app.enc([ps]),result_json=app.enc({'rows':rows,'issues':issues,'all_pages_read':True,'opening_cents':10000,'closing_cents':8800}))
        self.assertEqual(intake.approve_pdf(self.payload(intake.job(j['id'])))['result']['imported'],2)
        self.assertEqual(sum(t['amount_cents'] for t in app.state()['transactions']),1200)
    def test_product_label_and_explanation_only_page_are_not_ai_payments(self):
        ps=pages();ps[0]['text']=ps[0]['text'].replace('VR-GiroBusiness','Geschäftskonto')
        ps.append({'page':4,'text':'EUR-Konto Kontoauszug Nr. 1/2024\nBu-Tag Wert Vorgang\nEntgeltaufstellung\nKontoführung 9,90 EUR','method':'pdf_text'})
        result=statements.parse_document(ps);self.assertEqual(len(result['rows']),10);self.assertEqual(result['difference_cents'],0)
        with self.assertRaises(ValueError):intake.normalize_pdf_rows({'rows':[{'booked_on':'2024-01-31','amount':'-9,90','currency':'EUR','quote':'Kontoführung 9,90 EUR'}]},ps[-1],2024)

    def test_excluding_one_row_does_not_resolve_unrelated_warning(self):
        j=self.read();intake.update(j['id'],result_json=app.enc({**j['result'],'issues':['Seite 1: Leser unterscheiden sich beim Vorzeichen.']}))
        p=self.payload(j);p['rows'][0].update(excluded=True,exclusion_reason='already_recorded')
        with self.assertRaisesRegex(ValueError,'übrigen Prüfpunkte'):intake.approve_pdf(p)
        self.assertEqual(app.state()['transactions'],[])
