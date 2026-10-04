"""Regression tests for openable encrypted PDFs and recoverable uploads."""
import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app, banking, intake, recycle, pdfio, intelligence
from test_intake import pdf_bytes, PAGE, READING

class PDFRecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.tmp.name)/'data';app.initialize()
    def tearDown(self):
        app.DATA=self.old;self.tmp.cleanup()
        for key in ['jid','token']:
            if hasattr(intake.RUN_CONTEXT,key):delattr(intake.RUN_CONTEXT,key)
    def encrypted(self,password='',algorithm='AES-256'):
        from pypdf import PdfReader,PdfWriter
        w=PdfWriter();w.append(PdfReader(io.BytesIO(pdf_bytes())))
        w.encrypt(user_password=password,owner_password='owner-only',algorithm=algorithm)
        output=io.BytesIO();w.write(output);return output.getvalue()
    def upload(self,raw=None):
        raw=raw or pdf_bytes()
        return intake.upload({'year':2025,'account_id':'account_volksbank','filename':'auszug.pdf','file_base64':base64.b64encode(raw).decode()})['job']
    def csv(self):
        return banking.preview({'year':2025,'account_id':'account_volksbank','filename':'auszug.csv','file_base64':base64.b64encode(b'Buchungstag;Name Zahlungsbeteiligter;Verwendungszweck;Betrag;Waehrung\n03.04.2025;Test;Abo;-12,34;EUR\n').decode()})
    def test_owner_restricted_pdfs_read_in_both_upload_paths(self):
        for algorithm in ['RC4-128','AES-128','AES-256']:
            with self.subTest(algorithm=algorithm):
                raw=self.encrypted(algorithm=algorithm)
                self.assertIn('Softwareanbieter',intake.pdf_pages(raw)[0]['text'])
                text,note=app.extract_text(raw,'.pdf');self.assertIn('Softwareanbieter',text)
                self.assertNotIn('geschützt',note)
                j=self.upload(raw)
                with app.db() as con:doc=con.execute('SELECT * FROM documents WHERE id=?',(j['document_id'],)).fetchone()
                self.assertEqual(raw,(app.DATA/'originale'/doc['stored_name']).read_bytes())
    def test_real_password_is_different_from_corrupt_or_missing_dependency(self):
        raw=self.encrypted('mein-testkennwort')
        for password in ['', 'falsch']:
            with self.assertRaises(pdfio.PDFPasswordRequired):intake.pdf_pages(raw,password)
        self.assertIn('Softwareanbieter',intake.pdf_pages(raw,'mein-testkennwort')[0]['text'])
        self.assertIn('Öffnungskennwort',app.extract_text(raw,'.pdf')[1])
        with self.assertRaisesRegex(ValueError,'erneut von der Bank'):pdfio.open_reader(b'%PDF- kaputt')
        from pypdf.errors import DependencyError
        with patch('pypdf.PdfReader',side_effect=DependencyError('missing')):
            with self.assertRaisesRegex(ValueError,'EINRICHTEN'):pdfio.open_reader(raw)
    def test_running_password_never_saved(self):
        raw=self.encrypted('nicht-speichern');j=self.upload(raw)
        class ImmediateThread:
            def __init__(self,target,**kw):self.target=target
            def start(self):self.target()
        with patch.object(intelligence,'role_models',return_value=(['q','g','o'],{})),patch.object(intelligence,'call_model',side_effect=[READING,READING,{'summary':'Prüfen'}]),patch('intake.threading.Thread',ImmediateThread):
            intake.start({'job_id':j['id'],'password':'nicht-speichern'})
        self.assertEqual(intake.job(j['id'])['state'],'review')
        with app.db() as con:
            text='\n'.join(con.iterdump())
        self.assertNotIn('nicht-speichern',text)
    def test_failed_pdf_remove_restore_and_reupload(self):
        raw=pdf_bytes();j=self.upload(raw);intake.update(j['id'],state='error',error='Testfehler')
        p=recycle.preview({'job_id':j['id']});r=recycle.remove({'job_id':j['id'],'token':p['token']})
        self.assertEqual(intake.jobs(2025),[]);self.assertEqual(app.state()['documents'],[])
        with self.assertRaisesRegex(ValueError,'Papierkorb'):self.upload(raw)
        with self.assertRaisesRegex(ValueError,'entfernt'):intake.start({'job_id':j['id']})
        app.initialize();self.assertEqual(len(recycle.items(2025)),1)
        recycle.restore({'id':r['id']});recycle.restore({'id':r['id']})
        self.assertEqual(self.upload(raw)['id'],j['id']);self.assertEqual(intake.job(j['id'])['state'],'error')
        self.assertEqual(recycle.items(2025),[])
    def test_csv_trash_blocks_reads_commits_and_duplicate_reupload(self):
        p=self.csv();r=recycle.remove({'import_id':p['id']})
        self.assertEqual(banking.status(2025)['imports'],[])
        for f in [lambda:banking.commit({'id':p['id'],'checked':True}),lambda:banking.saved_preview(p['id']),lambda:self.csv(),lambda:banking.save_preview({'id':p['id'],'edits':{}})]:
            with self.assertRaisesRegex(ValueError,'Papierkorb'):f()
        recycle.restore({'id':r['id']});self.assertEqual(self.csv()['id'],p['id'])
    def test_committed_pdf_preserves_payment_and_original(self):
        j=self.upload()
        with patch.object(intake,'pdf_pages',return_value=[PAGE]),patch.object(intelligence,'call_model',side_effect=[READING,READING,{'summary':'Prüfen'}]):intake.run_pdf(j['id'],['q','g','o'])
        j=intake.job(j['id']);p=intake.save_pdf_review({'id':j['id'],'rows':j['result']['rows'],'checked':True,'confirm':True})
        banking.commit({'id':p['id'],'checked':True});before=app.state()['transactions']
        preview=recycle.preview({'document_id':j['document_id']});self.assertEqual(preview['payments'],1)
        r=recycle.remove({'document_id':j['document_id'],'token':preview['token']})
        self.assertEqual(app.state()['transactions'],before)
        with app.db() as con:
            original=con.execute('SELECT original FROM bank_imports WHERE id=?',(p['id'],)).fetchone()[0]
        self.assertTrue(original.startswith(b'%PDF-'))
        recycle.restore({'id':r['id']});self.assertTrue(banking.saved_preview(p['id'])['already_imported'])
        self.assertEqual(app.state()['transactions'],before)
    def test_stale_preview_and_late_worker_cannot_remove_or_resurrect(self):
        j=self.upload();intake.update(j['id'],state='running',run_token='old')
        p=recycle.preview({'job_id':j['id']})
        intake.update(j['id'],state='review')
        with self.assertRaisesRegex(ValueError,'inzwischen'):recycle.remove({'job_id':j['id'],'token':p['token']})
        r=recycle.remove({'job_id':j['id']});recycle.restore({'id':r['id']})
        intake.RUN_CONTEXT.jid=j['id'];intake.RUN_CONTEXT.token='old'
        with self.assertRaises(intake.IntakeCancelled):intake.update(j['id'],state='complete')
    def test_late_classification_cannot_change_preview_after_removal(self):
        p=self.csv();jid=app.new_id()
        with app.db() as con:app.insert(con,'intake_jobs',{'id':jid,'kind':'classify','year':2025,'account_id':'account_volksbank','import_id':p['id'],'state':'running','run_token':'old','created_at':app.now(),'updated_at':app.now()})
        intake.RUN_CONTEXT.jid=jid;intake.RUN_CONTEXT.token='old'
        result={'rows':[{'line':p['rows'][0]['line'],'scope':'business','category':'Unsortiert','reason':'Test','question':''}]}
        def model(*args):
            if args[0]=='o':
                r=recycle.remove({'import_id':p['id']});recycle.restore({'id':r['id']});return {'summary':'Zu spät'}
            return result
        with patch.object(intelligence,'call_model',side_effect=model),self.assertRaises(intake.IntakeCancelled):intake.run_classification(jid,['q','g','o'])
        self.assertNotIn('ai',banking.saved_preview(p['id'])['rows'][0])
    def test_linked_receipt_remains_protected(self):
        d=app.create_document({'title':'Beleg','kind':'Rechnung','year':2025,'body':'Original'})
        app.save_transaction({'direction':'expense','amount':'1,00','paid_on':'2025-04-03','partner':'Test','title':'Test','document_ids':[d['id']]})
        with self.assertRaisesRegex(ValueError,'verknüpft'):recycle.remove({'document_id':d['id']})
    def test_old_false_warning_is_repaired_without_overwriting_manual_text(self):
        raw=self.encrypted();j=self.upload(raw)
        with app.db() as con:con.execute("UPDATE documents SET body='',extraction_note='Geschütztes PDF gespeichert. Bitte eine lesbare Fassung ergänzen.' WHERE id=?",(j['document_id'],))
        app.initialize()
        doc=app.state()['documents'][0];self.assertIn('Softwareanbieter',doc['body']);self.assertNotIn('Geschütztes',doc['extraction_note'])
        with app.db() as con:con.execute("UPDATE documents SET body='Vom Nutzer eingetragener Text',extraction_note='Geschütztes PDF gespeichert.' WHERE id=?",(j['document_id'],))
        app.initialize();self.assertEqual(app.state()['documents'][0]['body'],'Vom Nutzer eingetragener Text')

    def test_document_reupload_from_trash_does_not_duplicate_original(self):
        raw=pdf_bytes();payload={'title':'Original','kind':'Kontoauszug','year':2025,'filename':'auszug.pdf','file_base64':base64.b64encode(raw).decode()}
        d=app.create_document(payload);r=recycle.remove({'document_id':d['id']})
        with self.assertRaisesRegex(ValueError,'Papierkorb'):app.create_document(payload)
        recycle.restore({'id':r['id']});self.assertEqual(app.create_document(payload)['id'],d['id'])
