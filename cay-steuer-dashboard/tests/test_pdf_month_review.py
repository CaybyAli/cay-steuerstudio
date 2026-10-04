"""Month approval and safe Volksbank table interpretation; synthetic customer data."""
import base64,io,json,re,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,intake,banking,statements,intelligence
from test_intake import pdf_bytes,PAGE,READING,ROW

def pages():
    data=(Path(__file__).parent/'fixtures/volksbank_layout.txt').read_text()
    parts=re.split(r'=== SEITE (\d+) ===\n',data)
    return [{'page':int(parts[i]),'text':parts[i+1],'method':'pdf_text'} for i in range(1,len(parts),2)]

class MonthReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.tmp.name)/'data';app.initialize()
    def tearDown(self):app.DATA=self.old;self.tmp.cleanup()
    def read(self,ps=None):
        j=intake.upload({'year':2024,'account_id':'account_volksbank','filename':'Januar.pdf','file_base64':base64.b64encode(pdf_bytes()).decode()})['job']
        with patch.object(intake,'pdf_pages',return_value=ps or pages()):intake.run_pdf(j['id'],[])
        return intake.job(j['id'])
    def payload(self,j):
        rows=[{**r,'scope':'private' if r['amount_cents']>0 else 'business','reviewed':True,'review_note':'Meine Einordnung'} for r in j['result']['rows']]
        return {'id':j['id'],'rows':rows,'checked':True}
    def test_exact_table_amounts_signs_fees_and_appendix(self):
        result=statements.parse_document(pages());self.assertEqual(len(result['rows']),10)
        self.assertEqual([r['amount_cents'] for r in result['rows']],[10000,-1000,5000,-5900,-1000,125000,1,100000,-1182,-215620])
        self.assertEqual(result['difference_cents'],0);self.assertTrue(result['balance_checks'][0]['totals_ok'])
        self.assertEqual(result['page_status'][-1]['state'],'notes')
        self.assertEqual(result['rows'][-1]['booked_on'],'2024-01-31');self.assertEqual(result['rows'][-1]['value_on'],'2024-02-01')
    def test_safe_quote_repair_with_correct_numeric_source(self):
        row=statements.parse_document(pages())['rows'][0]
        repaired=intake.normalize_pdf_rows({'rows':[{**row,'quote':'2024-01-08 Einzahlung 100,00 EUR'}]},pages()[0],2024)[0]
        self.assertEqual(repaired['quote'],row['quote'])
        with self.assertRaises(ValueError):intake.normalize_pdf_rows({'rows':[{**row,'amount':'-100,00'}]},pages()[0],2024)
        with self.assertRaises(ValueError):intake.normalize_pdf_rows({'rows':[{**row,'amount':'101,00'}]},pages()[0],2024)
    def test_reject_unknown_layout_and_malformed_dated_row(self):
        ps=pages();ps[0]['text']=ps[0]['text'].replace('100,00 H','100,00 ?');self.assertIsNone(statements.parse_document(ps))
        ps=pages();ps[1]['text']=ps[1]['text'].replace('EUR-Konto','USD-Konto');self.assertIsNone(statements.parse_document(ps))
    def test_reading_and_drafts_do_not_book(self):
        j=self.read();payload=self.payload(j);intake.save_pdf_review(payload)
        app.initialize();saved=intake.job(j['id']);self.assertEqual(saved['result']['rows'][0]['scope'],'private')
        self.assertEqual(app.state()['transactions'],[])
    def test_one_approval_persists_all_and_retries_are_idempotent(self):
        j=self.read();payload=self.payload(j);result=intake.approve_pdf(payload)
        self.assertTrue(result['committed']);self.assertEqual(result['result']['imported'],10)
        again=intake.approve_pdf(payload);self.assertEqual(result,again)
        app.initialize();rows=app.state()['transactions'];self.assertEqual(len(rows),10)
        self.assertEqual(sum(t['amount_cents'] for t in rows if t['direction']=='expense'),224702)
        self.assertTrue(all(t['scope']=='private' for t in rows if t['direction']=='income'))
        self.assertTrue(all(t['scope']=='business' for t in rows if t['direction']=='expense'))
    def test_every_payment_needs_explicit_choice_and_overall_check(self):
        j=self.read();payload=self.payload(j);payload['rows'][0]['reviewed']=False
        with self.assertRaisesRegex(ValueError,'jede Zahlung'):intake.approve_pdf(payload)
        payload=self.payload(j);payload['checked']=False
        with self.assertRaisesRegex(ValueError,'bestätigen'):intake.approve_pdf(payload)
        self.assertEqual(app.state()['transactions'],[])
    def test_cannot_drop_duplicate_or_change_a_source_payment(self):
        j=self.read()
        for change in ['drop','repeat','change']:
            payload=self.payload(j)
            if change=='drop':payload['rows'].pop()
            if change=='repeat':payload['rows'].append(payload['rows'][0])
            if change=='change':payload['rows'][0]['amount']='101,00'
            with self.subTest(change=change),self.assertRaises(ValueError):intake.approve_pdf(payload)
            self.assertEqual(app.state()['transactions'],[])
    def test_balance_and_turnover_mismatch_block_release(self):
        ps=pages();ps[0]['text']=ps[0]['text'].replace('2.400,01 H','2.401,01 H');j=self.read(ps)
        with self.assertRaisesRegex(ValueError,'Saldenprüfung'):intake.approve_pdf(self.payload(j))
        self.assertEqual(app.state()['transactions'],[])
    def test_two_months_have_separate_checks(self):
        ps=pages();ps.append({'page':4,'method':'pdf_text','text':'''VR-GiroBusiness
EUR-Konto Kontoauszug Nr. 2/2024 erstellt am 28.02.2024
Gesamtumsatz: 2,00 S 10,00 H
Bu-Tag Wert Vorgang
alter Kontostand 152,99 H
02.02. 02.02. Gutschrift PN:1 10,00 H
 Testkunde
03.02. 03.02. Kartenzahlung PN:1 2,00 S
 Testanbieter
neuer Kontostand vom 28.02.2024 160,99 H
'''})
        j=self.read(ps);self.assertEqual(len(j['result']['balance_checks']),2)
        self.assertEqual({r['booked_on'][:7] for r in j['result']['rows']},{'2024-01','2024-02'})
        self.assertEqual(intake.approve_pdf(self.payload(j))['result']['imported'],12)
    def test_manual_match_requires_extra_duplicate_choice(self):
        app.save_transaction({'direction':'income','scope':'private','amount':'100,00','paid_on':'2024-01-08','partner':'Privat','title':'Einzahlung','account_id':'account_volksbank','payment_method':'bank'})
        j=self.read();result=intake.approve_pdf(self.payload(j));self.assertTrue(result['needs_review'])
        self.assertEqual(len(app.state()['transactions']),1)
        row=next(r for r in result['preview']['rows'] if r['status']=='manual_review');self.assertTrue(row['manual_matches'])
        banking.commit({'id':result['preview']['id'],'checked':True,'choices':{str(row['line']):'link:'+row['manual_matches'][0]['id']}})
        self.assertEqual(len(app.state()['transactions']),10)
    def test_error_page_blocks_approval_even_when_some_rows_exist(self):
        j=self.read();intake.update(j['id'],result_json=app.enc({**j['result'],'all_pages_read':False}))
        with self.assertRaisesRegex(ValueError,'alle Seiten'):intake.approve_pdf(self.payload(j))
    def test_generic_bad_quote_keeps_other_rows_and_error_detail(self):
        bad={**ROW,'quote':'nicht vorhanden'}
        rows,issues=intake.read_rows_with_issues({'rows':[ROW,bad]},PAGE,2025)
        self.assertEqual(len(rows),2);self.assertTrue(rows[1]['proof_error']);self.assertTrue(issues)
    def test_retry_keeps_prior_user_scopes_and_notes(self):
        j=self.read();payload=self.payload(j)
        for row in payload['rows']:row.pop('amount_cents',None)
        intake.save_pdf_review(payload)
        with patch.object(intake,'pdf_pages',return_value=pages()):intake.run_pdf(j['id'],[])
        rows=intake.job(j['id'])['result']['rows'];self.assertEqual(rows[0]['scope'],'private');self.assertTrue(rows[0]['reviewed']);self.assertEqual(rows[0]['review_note'],'Meine Einordnung')
    def test_model_outage_does_not_discard_table_reading(self):
        j=self.read()
        with patch.object(intake,'pdf_pages',return_value=pages()),patch.object(intelligence,'call_model',side_effect=ValueError('offline')):intake.run_pdf(j['id'],['q','g','o'])
        j=intake.job(j['id']);self.assertEqual(j['state'],'review');self.assertEqual(len(j['result']['rows']),10);self.assertTrue(j['result']['ai_notice'])
    def test_generic_bad_quote_does_not_abort_following_page(self):
        j=self.read();ps=[PAGE,{**PAGE,'page':2}]
        wrong={**READING,'rows':[ROW,{**ROW,'quote':'Von der KI umformuliert'}]}
        with patch.object(intake,'pdf_pages',return_value=ps),patch.object(intelligence,'call_model',side_effect=[wrong,READING,READING,READING,{'summary':'Prüfen'}]):intake.run_pdf(j['id'],['q','g','o'])
        r=intake.job(j['id'])['result'];self.assertEqual(len(r['rows']),3);self.assertEqual(len(r['page_status']),2);self.assertTrue(r['all_pages_read']);self.assertTrue(r['rows'][1]['proof_error'])
    def test_generic_page_outage_is_saved_and_remaining_page_read(self):
        j=self.read();ps=[PAGE,{**PAGE,'page':2}]
        with patch.object(intake,'pdf_pages',return_value=ps),patch.object(intelligence,'call_model',side_effect=[ValueError('Leser offline'),READING,READING,{'summary':'Prüfen'}]):intake.run_pdf(j['id'],['q','g','o'])
        r=intake.job(j['id'])['result'];self.assertEqual(len(r['rows']),1);self.assertFalse(r['all_pages_read']);self.assertEqual(r['page_status'][0]['state'],'error')
    def test_three_pdf_classifiers_remain_blind_and_cannot_change_cents(self):
        j=self.read();calls=[]
        def model(name,system,content,limit):
            obj=json.loads(content);calls.append((name,content))
            if name=='o':return {'summary':'Unterschiedliche Einordnungen bleiben offen'}
            return {'rows':[{'line':r['line'],'scope':'business' if name=='q' else 'private','category':'Unsortiert','reason':'Test','question':''} for r in obj['rows']]}
        with patch.object(intake,'pdf_pages',return_value=pages()),patch.object(intelligence,'call_model',side_effect=model):intake.run_pdf(j['id'],['q','g','o'])
        self.assertEqual(calls[0][1],calls[1][1]);self.assertEqual(calls[3][1],calls[4][1]);r=intake.job(j['id'])['result']
        self.assertTrue(all(x['scope']=='unknown' for x in r['rows']));self.assertTrue(all(not x['reviewed'] for x in r['rows']));self.assertEqual(sum(x['amount_cents'] for x in r['rows']),15299)
