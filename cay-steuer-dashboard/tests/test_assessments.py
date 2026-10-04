import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app, assessments, intelligence, laws, storage

class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.previous=app.DATA
        app.DATA=Path(self.temp.name)/'data'; app.initialize()
    def tearDown(self):
        app.DATA=self.previous; self.temp.cleanup()
    def tx(self,amount='100',paid='2024-01-08',title='Private Bargeldeinzahlung'):
        return app.save_transaction({'direction':'income','amount':amount,'paid_on':paid,'partner':'Eigene Mittel','title':title,'scope':'private','payment_method':'bank','account_id':'account_volksbank'})['id']
    def test_amount_lookup_and_citable_booking(self):
        older=self.tx(paid='2024-12-01'); newer=self.tx()
        with app.db() as con:
            con.execute('UPDATE transactions SET created_at=? WHERE id=?',('2026-09-28T10:00:00',older))
            con.execute('UPDATE transactions SET created_at=? WHERE id=?',('2026-09-28T11:00:00',newer))
        self.tx('50')
        context=intelligence.chat_context('Welche Buchung über 100 € habe ich zuletzt erfasst?',2024,[])
        self.assertEqual(context['transaction_selection'][0]['id'],newer)
        self.assertEqual(context['transaction_selection_info']['matches'],2)
        source=next(s for s in context['sources'] if s['id']=='T:'+newer)
        self.assertIn('Zugeordnete Dokumente: 0',source['text'])
        self.assertIn('Bankbewegung',source['text'])
        checked=intelligence.normalize_answer({'answer':'Gespeichert als Privat.','citations':[{'source_id':source['id'],'quote':'Zahlungsdatum: 08.01.2024'}]},context)
        self.assertEqual(checked['citation_errors'],0)
        self.assertEqual(len(checked['citations']),1)
        self.assertFalse(any(s['id'].startswith('L:') for s in context['sources']))
        self.assertEqual(intelligence.chat_context('Welche Buchung über 999 €?',2024,[])['transaction_selection'],[])
        self.assertEqual(intelligence.chat_context('Welche Buchung über 100 €?',2025,[])['transaction_selection'],[])
    def test_irrelevant_law_never_selected_for_year_bonus(self):
        with app.db() as con:
            con.execute('UPDATE legal_versions SET reviewed=1,valid_from=2024,valid_to=2026')
        self.assertEqual(laws.search('Private Bargeldeinzahlung 100 EUR',2024),[])
        self.assertTrue(laws.search('Umzug Kuppenheim',2025))
    @unittest.skipUnless(assessments.manifest(), 'Optionales privates Bescheidpaket ist nicht Teil des Programmupdates')
    def test_bundle_repeat_safe_preserves_transactions_and_settings(self):
        self.tx(); before=app.state()
        result=assessments.import_bundle()
        self.assertEqual(result['documents'],6)
        self.assertEqual(result['facts'],11)
        self.assertEqual(result['tasks'],5)
        self.assertTrue(assessments.import_bundle()['already_imported'])
        after=app.state()
        self.assertEqual(before['transactions'],after['transactions'])
        self.assertEqual(before['settings'],after['settings'])
        self.assertEqual(len(after['documents']),6)
        self.assertTrue(all(not t['due_on'] and not t['due_confirmed'] for t in after['tasks']))
        self.assertTrue(all(f['status']=='open' for f in after['facts']))
        self.assertIsNone(after['assessments']['available'])
        self.assertFalse(after['assessments']['cases'][0]['source_changed'])
        app.initialize()
        self.assertEqual(len(app.state()['documents']),6)
        self.assertEqual(len(app.state()['assessments']['cases']),1)
        self.assertEqual(storage.verify_zip(app.backup_bytes())['originals_checked'],6)
    @unittest.skipUnless(assessments.manifest(), 'Optionales privates Bescheidpaket ist nicht Teil des Programmupdates')
    def test_import_failure_rolls_back_rows_and_originals(self):
        with patch.object(intelligence,'save_fact',side_effect=ValueError('test interruption')):
            with self.assertRaises(ValueError): assessments.import_bundle()
        self.assertEqual(app.state()['documents'],[])
        self.assertEqual(app.state()['facts'],[])
        self.assertEqual(list((app.DATA/'originale').iterdir()),[])
        self.assertEqual(assessments.status()['cases'],[])
    @unittest.skipUnless(assessments.manifest(), 'Optionales privates Bescheidpaket ist nicht Teil des Programmupdates')
    def test_existing_pdf_reused_and_source_changes_marked(self):
        import base64
        item=assessments.manifest()['documents'][0]
        raw=(assessments.BUNDLE/item['file']).read_bytes()
        result=app.create_document({'title':'Mein ESt-Bescheid','year':2024,'kind':'Finanzamt','filename':'original.pdf','file_base64':base64.b64encode(raw).decode()})
        assessments.import_bundle()
        self.assertEqual(len(app.state()['documents']),6)
        d=next(d for d in app.state()['documents'] if d['id']==result['id'])
        self.assertIn('Gewinnerzielungsabsicht',d['body'])
        app.update_document(d['id'],{**d,'notes':'Später geändert'})
        self.assertTrue(assessments.status()['cases'][0]['source_changed'])
    @unittest.skipUnless(assessments.manifest(), 'Optionales privates Bescheidpaket ist nicht Teil des Programmupdates')
    def test_carryforwards_retrieved_for_2025_with_sources(self):
        assessments.import_bundle()
        ctx=intelligence.chat_context('Welche Verlustvorträge und welcher Gewerbeverlust aus 2024 sind für 2025 vorhanden?',2025,[])
        text='\n'.join(s['text'] for s in ctx['sources'])
        self.assertIn('4.195 EUR',text)
        self.assertIn('10.187 EUR',text)
        self.assertTrue(any(s['id'].startswith('F:') for s in ctx['sources']))
        self.assertTrue(any(s['id'].startswith('D:') and s['year']==2024 for s in ctx['sources']))
    def test_malformed_citation_and_duplicate_checklist(self):
        result=intelligence.normalize_answer({'answer':'Prüfen.','missing':['Unterlage','Unterlage'],'citations':[{'source_id':[],'quote':'unzulässig'}]}, {'sources':[]})
        self.assertEqual(result['missing'],['Unterlage'])
        self.assertEqual(result['citation_errors'],1)
        self.assertTrue(result['evidence_warnings'])

    @unittest.skipUnless(assessments.manifest(), 'Optionales privates Bescheidpaket ist nicht Teil des Programmupdates')
    def test_relevant_bescheid_summary_keeps_provisional_flag(self):
        assessments.import_bundle()
        ctx=intelligence.chat_context('Was muss ich wegen der Bescheide 2024 beachten?',2024,[])
        self.assertTrue(any('Gewinnerzielungsabsicht vorläufig' in s['text'] for s in ctx['sources']))
        self.assertLess(len(app.enc({'Frage':'Was muss ich wegen der Bescheide 2024 beachten?','Daten':ctx})+intelligence.SYSTEM),(8192-2700)*2-3200)
        ctx=intelligence.chat_context('Welche Verlustvorträge aus 2024 habe ich für 2025?',2025,[])
        self.assertTrue(any('4.195 EUR' in s['text'] for s in ctx['sources']))

    @unittest.skipUnless(assessments.manifest(), 'Optionales privates Bescheidpaket ist nicht Teil des Programmupdates')
    def test_three_models_context_budget_and_consolidated_checklist(self):
        assessments.import_bundle(); requests=[]
        models=['qwen3.8:27b','gemma4:31b','gpt-oss:20b']
        def fake(path,payload=None,timeout=5):
            if path=='/api/tags': return {'models':[{'name':m,'size':1,'digest':m} for m in models]}
            requests.append(payload)
            obj={'answer':'Dies ist ein langer Antworttext zur Prüfung. '*40,'missing':['Beleg prüfen'] if len(requests)<3 else [],'conflicts':[],'citations':[],'tasks':[]}
            return {'message':{'content':json.dumps(obj)}}
        with patch.object(app,'ollama',side_effect=fake):
            intelligence.start_chat({'question':'Was muss ich wegen der Bescheide 2024 beachten?','year':2024})
            deadline=time.monotonic()+5
            while app.AI_LOCK.locked() and time.monotonic()<deadline: time.sleep(.01)
        result=intelligence.chat_list(2024)[0]
        self.assertEqual(result['state'],'complete',result['error'])
        self.assertEqual(len(requests),3)
        self.assertEqual(result['coordinator_json']['missing'],[])
        self.assertEqual(requests[0]['messages'][1],requests[1]['messages'][1])
        for request in requests:
            self.assertLessEqual(sum(len(m['content']) for m in request['messages']),(8192-1600-900)*2)

if __name__=='__main__': unittest.main()
