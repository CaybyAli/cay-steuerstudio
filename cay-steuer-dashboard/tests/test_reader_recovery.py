"""Regression for the real 0.3.7 Gemma note validation failure."""
import json
from unittest.mock import patch
import unittest
import test_annual as fixtures
MODELS = fixtures.MODELS
import app
import intelligence as I
import year_review as Y


class ReaderRecoveryTests(unittest.TestCase):
    setUp = fixtures.AnnualTests.setUp
    tearDown = fixtures.AnnualTests.tearDown
    wait = fixtures.AnnualTests.wait
    tx = fixtures.AnnualTests.tx
    fake = fixtures.AnnualTests.fake
    start = fixtures.AnnualTests.start
    def test_empty_no_issue_comment_is_optional(self):
        payload={'buchungen':[{'ref':'B0001'}]}
        for value in ['', '   ', None]:
            result=Y.validate_rows({'checks':[{'ref':'B0001','status':'no_issue','note':value}]},payload)
            row=result['checks'][0]
            self.assertEqual(row['status'],'no_issue')
            self.assertTrue(row['note_defaulted'])
            self.assertIn('Kein zusätzlicher Hinweis',row['note'])
        self.assertTrue(Y.validate_rows({'checks':[{'ref':'B0001','status':'no_issue'}]},payload)['checks'][0]['note_defaulted'])

    def test_long_completed_comment_is_preserved_verbatim(self):
        text='Den betrieblichen Zusammenhang anhand der vorhandenen Rechnung prüfen. '*20
        payload={'buchungen':[{'ref':'B0001'}]}
        result=Y.validate_rows({'checks':[{'ref':'B0001','status':'review','note':text}]},payload)
        self.assertEqual(result['checks'][0]['note'],text.strip())
        self.assertFalse(result['checks'][0]['note_defaulted'])

    def test_review_without_reason_remains_an_error(self):
        payload={'buchungen':[{'ref':'B0001'}]}
        for value in ['', None, '  ']:
            with self.assertRaisesRegex(ValueError,'B0001.*keinen Grund'):
                Y.validate_rows({'checks':[{'ref':'B0001','status':'review','note':value}]},payload)
        with self.assertRaisesRegex(ValueError,'B0001.*Text'):
            Y.validate_rows({'checks':[{'ref':'B0001','status':'review','note':[]} ]},payload)

    def test_gemma_empty_and_long_comments_finish_without_losing_explanations(self):
        for i in range(18):self.tx(title=f'Payment {i}')
        long_note='Den Zweck der Zahlung mit der vorhandenen Unterlage vergleichen. '*12
        def gemma(path,payload=None,timeout=5):
            result=self.fake(path,payload,timeout)
            if path=='/api/chat' and payload['model']==MODELS[1]:
                obj=json.loads(result['message']['content'])
                for r in obj['checks']:
                    r['note']=None if r['ref']!='B0002' else long_note
                    r['status']='no_issue' if r['ref']!='B0002' else 'review'
                result['message']['content']=json.dumps(obj)
            return result
        with patch.object(app,'ollama',side_effect=gemma):jid=self.start()
        result=I.annual_report(jid)
        self.assertEqual(result['both_read'],18)
        self.assertEqual(result['rows'][1]['reviewer']['note'],long_note.strip())
        self.assertEqual(result['role_states'],{'worker':'complete','reviewer':'complete','coordinator':'complete'})
        for call in self.calls:
            if call['model'] in MODELS[:2]:
                self.assertEqual(call['format']['type'],'object')

    def test_bad_large_batch_is_split_and_every_ref_remains_required(self):
        for i in range(17):self.tx(title=f'Payment {i}')
        before=app.state()['transactions']
        def small_only(path,payload=None,timeout=5):
            result=self.fake(path,payload,timeout)
            if path=='/api/chat' and payload['model']==MODELS[1]:
                content=json.loads(payload['messages'][1]['content'])
                if len(content.get('buchungen',[]))>2:
                    result['message']['content']='{"checks":[]}'
            return result
        with patch.object(app,'ollama',side_effect=small_only):jid=self.start()
        report=I.annual_report(jid)
        self.assertEqual(I.chat_list(2025)[0]['state'],'complete')
        self.assertEqual(report['both_read'],17)
        self.assertEqual(before,app.state()['transactions'])
        self.assertTrue(any(s['state']=='split' for s in I.get_steps(jid)))
        refs=[c['ref'] for s in I.get_steps(jid) if s['role']=='reviewer' and s['state']=='complete'
              for c in json.loads(s['output_json'])['checks']]
        self.assertEqual(len(refs),len(set(refs)))
        self.assertEqual(len(refs),17)

    def test_singleton_failure_is_not_marked_checked_and_resume_keeps_worker(self):
        for i in range(10):self.tx(title=f'Payment {i}')
        def no_reason(path,payload=None,timeout=5):
            result=self.fake(path,payload,timeout)
            if path=='/api/chat' and payload['model']==MODELS[1]:
                obj=json.loads(result['message']['content'])
                for c in obj['checks']:
                    if c['ref']=='B0002':c.update(status='review',note='')
                result['message']['content']=json.dumps(obj)
            return result
        with patch.object(app,'ollama',side_effect=no_reason):jid=self.start()
        item=I.chat_list(2025)[0]
        self.assertEqual(item['state'],'error')
        self.assertIn('B0002',item['error'])
        self.assertEqual(item['annual']['reader_counts'],{'worker':10,'reviewer':1})
        self.assertEqual(item['annual']['role_states'],{'worker':'complete','reviewer':'error','coordinator':'pending'})
        before=[s['output_json'] for s in I.get_steps(jid) if s['state']=='complete']
        app.initialize();self.calls=[]
        with patch.object(app,'ollama',side_effect=self.fake):I.resume_chat({'id':jid});self.wait()
        self.assertEqual(I.annual_report(jid)['both_read'],10)
        self.assertFalse(any(c['model']==MODELS[0] for c in self.calls))
        after=[s['output_json'] for s in I.get_steps(jid) if s['state']=='complete']
        self.assertTrue(all(x in after for x in before))

    def test_split_survives_restart_before_child_runs(self):
        for i in range(4):self.tx(title=f'Payment {i}')
        def fail(path,payload=None,timeout=5):
            if path=='/api/chat' and payload['model']==MODELS[1]:raise ValueError('Connection interruption')
            return self.fake(path,payload,timeout)
        with patch.object(app,'ollama',side_effect=fail):jid=self.start()
        step=next(s for s in I.get_steps(jid) if s['role']=='reviewer')
        content=json.loads(step['input_json'])
        self.assertTrue(I.split_reader_step(jid,step,content,'Test split'))
        self.assertFalse(I.split_reader_step(jid,step,content,'Repeated split'))
        app.initialize();self.calls=[]
        with patch.object(app,'ollama',side_effect=self.fake):I.resume_chat({'id':jid});self.wait()
        self.assertEqual(I.chat_list(2025)[0]['state'],'complete')
        self.assertEqual(I.annual_report(jid)['both_read'],4)
        self.assertEqual([len(json.loads(c['messages'][1]['content'])['buchungen']) for c in self.calls if c['model']==MODELS[1]],[2,2])

    def test_program_without_private_bundle_keeps_existing_documents_and_case(self):
        import assessments
        from pathlib import Path
        doc=app.create_document({'title':'Synthetic existing notice','kind':'Finanzamt','year':2024,'body':'Synthetic notice'})['id']
        document=next(d for d in app.state()['documents'] if d['id']==doc)
        case={'id':'synthetic-case','title':'Synthetic existing case','year':2024,'document_date':'2024-12-31',
              'summary':'Synthetic only','documents':[{'id':doc,'title':document['title'],'source_hash':app.source_hash(document)}],
              'fact_ids':[],'task_ids':[]}
        with app.db() as con:
            app.insert(con,'assessment_imports',{'id':case['id'],'data_json':app.enc(case),'imported_at':app.now()})
        with patch.object(assessments,'BUNDLE',Path(self.temp.name)/'absent-private-bundle'):
            app.initialize()
            status=app.state()['assessments']
            self.assertIsNone(status['available'])
            self.assertEqual(status['cases'][0]['id'],case['id'])
            self.assertFalse(status['cases'][0]['source_changed'])
            self.assertEqual(next(d for d in app.state()['documents'] if d['id']==doc),document)
