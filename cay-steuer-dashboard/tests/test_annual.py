"""Annual completeness, money units and interruption regression tests."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import app
import intelligence as I
import year_review as Y

MODELS=['qwen3.8:27b','gemma4:31b','gpt-oss:20b']


class AnnualTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.old=app.DATA
        app.DATA=Path(self.temp.name)/'data'; app.initialize(); self.calls=[]

    def tearDown(self):
        self.wait();app.DATA=self.old;self.temp.cleanup()

    def wait(self):
        end=time.monotonic()+12
        while app.AI_LOCK.locked() and time.monotonic()<end: threading.Event().wait(.005)
        self.assertFalse(app.AI_LOCK.locked(),'background run did not finish')

    def tx(self,**kw):
        return app.save_transaction({'direction':'expense','amount':'12,99','paid_on':'2025-02-03',
                                    'partner':'Synthetic','title':'Test','scope':'private',**kw})['id']

    def fake(self,path,payload=None,timeout=5):
        if path=='/api/tags':return {'models':[{'name':m,'size':100,'digest':'synthetic-'+m} for m in MODELS]}
        self.calls.append(payload)
        content=json.loads(payload['messages'][1]['content'])
        if 'buchungen' in content:
            obj={'checks':[{'ref':r['ref'],'status':'no_issue','note':'Kein weiterer Hinweis zu den gespeicherten Angaben.'} for r in content['buchungen']]}
        else:
            obj={'answer':'Bitte die offenen Zuordnungen im Bericht prüfen. Keine fertige EÜR.','missing':[], 'conflicts':[], 'citations':[], 'tasks':[]}
        return {'done':True,'done_reason':'stop','message':{'content':json.dumps(obj)}}

    def start(self,q='Jahresprüfung EÜR 2025'):
        result=I.start_chat({'question':q,'year':2025,'document_ids':[],'mode':'annual'});self.wait();return result['id']

    def test_cent_formatting_integer_only(self):
        self.assertEqual(Y.euro(48422),'484,22 EUR')
        self.assertEqual(Y.euro(84555),'845,55 EUR')
        self.assertEqual(Y.euro(-36133),'-361,33 EUR')
        self.assertEqual(Y.euro(204000),'2.040,00 EUR')
        self.assertEqual(Y.euro(1),'0,01 EUR')
        with self.assertRaises(ValueError):Y.euro(1.1)

    def test_all_106_records_are_passed_to_both_independent_readers(self):
        self.tx(direction='income',amount='484,22',scope='business')
        self.tx(amount='845,55',scope='business')
        for i in range(104):self.tx(amount='2.040,00' if i==103 else '0,01',paid_on='2025-11-10',title=f'Private movement {i}')
        old=self.tx(paid_on='2024-02-03',amount='999,00')
        archived=self.tx(amount='888,00');app.archive('transactions',archived)
        before=app.state()['transactions']
        with patch.object(app,'ollama',side_effect=self.fake):jid=self.start()
        item=I.chat_list(2025)[0]
        self.assertEqual(item['state'],'complete',item['error'])
        report=I.annual_report(jid)
        self.assertEqual(report['both_read'],106)
        self.assertEqual(report['reader_counts'],{'worker':106,'reviewer':106})
        self.assertEqual(report['coverage']['unlinked_business_receipts'],2)
        self.assertEqual(report['open_count'],2)
        self.assertEqual(len({r['id'] for r in report['rows']}),106)
        self.assertNotIn(old,{r['id'] for r in report['rows']})
        self.assertNotIn(archived,{r['id'] for r in report['rows']})
        business=report['summary']['scopes'][0]
        self.assertEqual((business['income_cents'],business['expense_cents'],business['balance_cents']),(48422,84555,-36133))
        workers=[p['messages'][1]['content'] for p in self.calls if p['model']==MODELS[0]]
        reviewers=[p['messages'][1]['content'] for p in self.calls if p['model']==MODELS[1]]
        self.assertEqual(workers,reviewers)
        self.assertTrue(all('amount_cents' not in p and 'income_cents' not in p for p in workers))
        self.assertIn('484,22 EUR',''.join(workers));self.assertNotIn('48.422',''.join(workers))
        self.assertEqual(before,app.state()['transactions'])
        self.assertFalse(item['context_stale'])

    def test_generic_chat_money_units_are_unambiguous(self):
        self.tx(scope='business',amount='484,22')
        with patch.object(app,'ollama',side_effect=self.fake):jid=self.start('Welche Ausgaben habe ich im Februar?')
        item=I.chat_list(2025)[0];self.assertEqual(item['state'],'complete',item['error'])
        self.assertEqual(len(self.calls),3)
        for call in self.calls:
            raw=call['messages'][1]['content']
            self.assertNotIn('"expense_cents"',raw)
            self.assertIn('484,22 EUR',raw)

    def test_limit_retry_rejects_truncated_even_valid_json(self):
        replies=[{'done_reason':'length','message':{'content':'{"answer":"UNSAFE"}'}},
                 {'done_reason':'stop','message':{'content':'{"answer":"complete"}'}}]
        with patch.object(app,'ollama',side_effect=replies) as mock:
            out=I.call_model(MODELS[2],'short','short')
        self.assertEqual(out['answer'],'complete')
        first,second=mock.call_args_list
        self.assertGreater(second.args[1]['options']['num_predict'],first.args[1]['options']['num_predict'])
        self.assertEqual(second.args[1]['options']['num_ctx'],8192)
        self.assertEqual(second.args[1]['think'],'low')

    def test_twice_truncated_is_never_complete(self):
        with patch.object(app,'ollama',return_value={'done_reason':'length','message':{'content':'{"answer":"UNSAFE"}'}}) as mock:
            with self.assertRaisesRegex(I.ModelReplyError,'Keine Teilantwort'):I.call_model(MODELS[0],'short','short')
        self.assertEqual(mock.call_count,2)

    def test_resume_after_restart_keeps_worker_and_completed_reviewer_batches(self):
        for i in range(18):self.tx(title=f'Private {i}')
        reviewer_batches=0
        def broken(path,payload=None,timeout=5):
            nonlocal reviewer_batches
            if path=='/api/chat' and payload['model']==MODELS[1]:
                reviewer_batches+=1
                if reviewer_batches>=2:return {'done_reason':'length','message':{'content':'{"checks":[]}'}}
            return self.fake(path,payload,timeout)
        with patch.object(app,'ollama',side_effect=broken):jid=self.start()
        item=I.chat_list(2025)[0];self.assertEqual(item['state'],'error');self.assertTrue(item['can_resume'])
        report=I.annual_report(jid)
        self.assertEqual(report['reader_counts'],{'worker':18,'reviewer':8})
        previous_worker=[s['output_json'] for s in I.get_steps(jid) if s['role']=='worker']
        app.initialize();self.calls=[]
        with patch.object(app,'ollama',side_effect=self.fake):
            I.resume_chat({'id':jid});self.wait()
        self.assertEqual(I.chat_list(2025)[0]['state'],'complete',I.chat_list(2025)[0]['error'])
        self.assertTrue(all(c['model']!=MODELS[0] for c in self.calls))
        self.assertEqual(previous_worker,[s['output_json'] for s in I.get_steps(jid) if s['role']=='worker'])
        self.assertEqual(I.annual_report(jid)['both_read'],18)

    def test_complete_run_persistence_and_new_unselected_record_invalidates(self):
        self.tx()
        with patch.object(app,'ollama',side_effect=self.fake):jid=self.start()
        app.initialize();self.assertEqual(I.annual_report(jid)['both_read'],1)
        self.tx(title='Newly saved')
        self.assertTrue(I.chat_list(2025)[0]['context_stale'])
        self.assertTrue(I.annual_report(jid)['stale'])
        self.assertEqual(I.annual_report(jid)['summary']['count'],1)

    def test_changed_data_cannot_resume_old_run(self):
        self.tx()
        def fail(path,payload=None,timeout=5):
            if path=='/api/chat':raise ValueError('Test interruption')
            return self.fake(path,payload,timeout)
        with patch.object(app,'ollama',side_effect=fail):jid=self.start()
        self.tx(title='Changed dataset')
        with self.assertRaisesRegex(ValueError,'inzwischen geändert'):I.resume_chat({'id':jid})
        self.assertFalse(app.AI_LOCK.locked())

    def test_missing_and_duplicate_row_responses_are_rejected(self):
        payload={'buchungen':[{'ref':'B0001'},{'ref':'B0002'}]}
        for rows in [[],[{'ref':'B0001','status':'no_issue','note':'OK'}]*2,
                     [{'ref':'B0001','status':'no_issue','note':'48.422,00 EUR'}, {'ref':'B0002','status':'no_issue','note':'OK'}]]:
            with self.assertRaises(ValueError):Y.validate_rows({'checks':rows},payload)

    def test_linked_receipt_not_claimed_missing_and_private_needs_no_invoice(self):
        doc=app.create_document({'title':'Receipt','kind':'Rechnung','year':2025,'body':'Synthetic receipt'})['id']
        self.tx(scope='business',document_ids=[doc],vat_treatment='domestic',category='Software & Abos')
        self.tx(receipt_state='none')
        context=I.chat_context('EÜR 2025',2025,[],force_annual=True)
        report=Y.report(app,context,[])
        self.assertEqual(report['coverage']['linked_receipts'],1)
        self.assertEqual(report['coverage']['unlinked_business_receipts'],0)
        private=next(r for r in report['rows'] if r['scope']=='private')
        self.assertEqual(private['issues'],[])
        self.assertIn('Kein Betriebsrechnungsbeleg nötig',private['receipt_status'])
        self.assertEqual(report['coverage']['document_contents_read'],0)

    def test_empty_year_no_invented_bookings(self):
        with patch.object(app,'ollama',side_effect=self.fake):jid=self.start()
        item=I.chat_list(2025)[0];self.assertEqual(item['state'],'complete',item['error'])
        self.assertEqual(I.annual_report(jid)['summary']['count'],0)
        self.assertEqual(len(self.calls),1)

    def test_large_notes_are_explicit_excerpts_not_silently_full(self):
        self.tx(scope='business',notes='x'*10000,tax_note='y'*3000,business_purpose='z'*2000)
        context=I.chat_context('EÜR 2025',2025,[],force_annual=True)
        self.assertEqual(set(context['annual']['records'][0]['text_excerpts']),{'notes','tax_note','business_purpose'})
        groups=Y.batches(app,context,{'num_ctx':8192})
        self.assertEqual(len(groups),1)
        self.assertLess(len(Y.ROW_SYSTEM+app.enc(groups[0])),(8192-2600-1000)*2)

    def test_crash_marks_only_unfinished_step_pending_and_can_resume(self):
        self.tx()
        with patch.object(app,'ollama',side_effect=self.fake):jid=self.start()
        with app.db() as con:
            con.execute("UPDATE chat_runs SET state='running' WHERE id=?",(jid,))
            con.execute("UPDATE chat_steps SET state='running',output_json=NULL WHERE run_id=? AND role='coordinator'",(jid,))
        app.initialize()
        self.assertEqual(I.chat_list(2025)[0]['state'],'error')
        self.assertEqual([s['state'] for s in I.get_steps(jid)],['complete','complete','pending'])
        self.calls=[]
        with patch.object(app,'ollama',side_effect=self.fake):I.resume_chat({'id':jid});self.wait()
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0]['model'],MODELS[2])

    def test_preview_import_is_not_falsely_claimed_complete(self):
        import banking
        import base64
        raw='Date,Payee,Payment reference,Amount (EUR)\n2025-02-03,Test,Payment,-12.99\n'
        banking.preview({'year':2025,'account_id':'account_n26','filename':'test.csv','file_base64':base64.b64encode(raw.encode()).decode()})
        context=I.chat_context('EÜR 2025',2025,[],force_annual=True)
        self.assertEqual(context['annual']['coverage']['pending_imports'],1)
        self.assertEqual(context['annual']['summary']['count'],0)

    def test_no_money_hallucination_is_accepted_as_annual_final(self):
        self.tx()
        def wrong(path,payload=None,timeout=5):
            if path=='/api/chat' and payload['model']==MODELS[2]:
                return {'done_reason':'stop','message':{'content':json.dumps({'answer':'Einnahmen 48.422,00 EUR','missing':[],'conflicts':[],'citations':[],'tasks':[]})}}
            return self.fake(path,payload,timeout)
        with patch.object(app,'ollama',side_effect=wrong):jid=self.start()
        item=I.chat_list(2025)[0]
        self.assertEqual(item['state'],'error')
        self.assertIsNone(item['coordinator_json'])
        self.assertEqual(I.annual_report(jid)['both_read'],1)

    def test_fact_change_marks_snapshot_stale(self):
        self.tx()
        with patch.object(app,'ollama',side_effect=self.fake):jid=self.start()
        I.save_fact({'year':2025,'title':'Neuer belegter Fakt','value':'Synthetisch','source_note':'Testnotiz'})
        self.assertTrue(I.annual_report(jid)['stale'])

    def test_screenshot_totals_preserve_business_scope_and_year(self):
        self.tx(scope='business',direction='income',amount='810,82')
        self.tx(scope='business',amount='965,23')
        for scope in ['private','mixed','unknown','transfer']:
            self.tx(scope=scope,amount='100,00')
        self.tx(scope='business',paid_on='2024-12-31',amount='900,00')
        self.tx(scope='business',paid_on='2026-01-01',amount='800,00')
        before=app.state()['transactions']
        with patch.object(app,'ollama',side_effect=self.fake):jid=self.start()
        business=I.annual_report(jid)['summary']['scopes'][0]
        self.assertEqual((business['income_cents'],business['expense_cents'],business['balance_cents']),(81082,96523,-15441))
        self.assertEqual(I.annual_report(jid)['both_read'],6)
        self.assertEqual(before,app.state()['transactions'])

    def test_incomplete_row_schema_is_retried_without_accepting_partial_rows(self):
        self.tx();self.tx(title='Second payment')
        attempts=0
        def missing_row(path,payload=None,timeout=5):
            nonlocal attempts
            if path=='/api/chat' and payload['model']==MODELS[0]:
                attempts+=1
                if attempts==1:
                    return {'done':True,'done_reason':'stop','message':{'content':json.dumps({'checks':[{'ref':'B0001','status':'no_issue','note':'OK'}]})}}
            return self.fake(path,payload,timeout)
        with patch.object(app,'ollama',side_effect=missing_row):jid=self.start()
        self.assertEqual(attempts,2)
        self.assertEqual(I.annual_report(jid)['both_read'],2)
        self.assertEqual(I.chat_list(2025)[0]['state'],'complete')

    def test_reader_stays_loaded_between_batches_and_unloads_at_role_end(self):
        for i in range(9):self.tx(title=f'Payment {i}')
        with patch.object(app,'ollama',side_effect=self.fake):self.start()
        for model in MODELS[:2]:
            calls=[p for p in self.calls if p['model']==model]
            self.assertEqual([p['keep_alive'] for p in calls],['1m',0])
        self.assertEqual(self.calls[-1]['keep_alive'],0)


if __name__=='__main__':unittest.main()
