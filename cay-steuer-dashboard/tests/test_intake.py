"""Critical intake invariants. Model responses are simulated; no Ollama needed."""
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app, banking, intake, intelligence, storage

TEXT='Kontoauszug April 2025\nAnfangssaldo 100,00 EUR\n03.04.2025 Softwareanbieter Abo -12,34 EUR\nEndsaldo 87,66 EUR'
ROW={'booked_on':'2025-04-03','amount':'-12,34','currency':'EUR','partner':'Softwareanbieter','purpose':'Abo','quote':'03.04.2025 Softwareanbieter Abo -12,34 EUR'}
PAGE={'page':1,'text':TEXT,'method':'pdf_text'}
READING={'rows':[ROW],'opening_balance':'100,00','closing_balance':'87,66','balance_quote':TEXT,'issues':[]}
PDF_AVAILABLE=all(importlib.util.find_spec(m) for m in ['pypdf','reportlab'])

def pdf_bytes(scan=False):
    from reportlab.pdfgen import canvas
    out=io.BytesIO();c=canvas.Canvas(out,pagesize=(595,842));c.setFont('Helvetica',13)
    for i,line in enumerate(TEXT.splitlines()):c.drawString(40,780-i*32,line)
    c.save()
    if not scan:return out.getvalue()
    import pypdfium2 as pdfium
    from reportlab.lib.utils import ImageReader
    pdf=pdfium.PdfDocument(out.getvalue());image=pdf[0].render(scale=2).to_pil()
    output=io.BytesIO();c=canvas.Canvas(output,pagesize=(595,842));c.drawImage(ImageReader(image),0,0,595,842);c.save();pdf.close();return output.getvalue()

class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.temp.name)/'data';app.initialize()
    def tearDown(self):
        app.DATA=self.old;self.temp.cleanup()
    def preview(self):
        raw=b'Buchungstag;Name Zahlungsbeteiligter;Verwendungszweck;Betrag;Waehrung\n03.04.2025;Softwareanbieter;Abo;-12,34;EUR\n'
        return banking.preview({'year':2025,'account_id':'account_volksbank','filename':'bank.csv','file_base64':base64.b64encode(raw).decode()})
    def upload_pdf(self):
        raw=pdf_bytes() if PDF_AVAILABLE else b'%PDF-1.4\n%%EOF\n'
        return intake.upload({'year':2025,'account_id':'account_volksbank','filename':'bank.pdf','file_base64':base64.b64encode(raw).decode()})['job']
    def read_pdf(self,reading=READING):
        j=self.upload_pdf()
        with patch.object(intake,'pdf_pages',return_value=[PAGE]),patch.object(intelligence,'call_model',side_effect=[READING,reading,{'summary':'Am Original prüfen'}]):
            intake.run_pdf(j['id'],['qwen','gemma','gpt-oss'])
        return intake.job(j['id'])
    def pdf_payload(self,j,**kw):
        return {'id':j['id'],'rows':j['result']['rows'],'checked':True,'confirm':True,**kw}
    def test_commit_requires_explicit_review(self):
        p=self.preview()
        with self.assertRaisesRegex(ValueError,'bestätigen'):banking.commit({'id':p['id']})
        self.assertEqual(app.state()['transactions'],[])
    def test_csv_review_survives_reupload_and_restart(self):
        p=self.preview();line=str(p['rows'][0]['line'])
        banking.save_preview({'id':p['id'],'edits':{line:{'scope':'private','review_note':'Persönliches Abo','choice':'create'}}})
        app.initialize()
        p2=self.preview();self.assertEqual(p2['id'],p['id']);self.assertEqual(p2['rows'][0]['scope'],'private')
        banking.commit({'id':p['id'],'checked':True})
        t=app.state()['transactions'][0];self.assertEqual(t['scope'],'private');self.assertIn('Persönliches Abo',t['notes'])
    def test_none_receipt_and_file_link_saved_atomically(self):
        p=self.preview();banking.commit({'id':p['id'],'checked':True});t=app.state()['transactions'][0]
        intake.save_evidence({'id':t['id'],'scope':'private','receipt_state':'none','receipt_note':'Private Zahlung'})
        app.initialize();t=app.state()['transactions'][0];self.assertEqual(t['receipt_state'],'none');self.assertEqual(t['receipt_note'],'Private Zahlung')
        with self.assertRaises(ValueError):intake.save_evidence({'id':t['id'],'receipt_filename':'x.exe','receipt_file_base64':base64.b64encode(b'invalid').decode()})
        self.assertEqual(app.state()['transactions'][0]['receipt_state'],'none')
        intake.save_evidence({'id':t['id'],'receipt_filename':'receipt.txt','receipt_file_base64':base64.b64encode(b'Originalbeleg').decode()})
        app.initialize();t=app.state()['transactions'][0];self.assertEqual(t['receipt_state'],'pending');self.assertEqual(len(t['document_ids']),1)
        self.assertTrue(t['bank_import_id'])
    def test_archive_account_preserves_old_dates_and_blocks_future(self):
        p=self.preview();banking.commit({'id':p['id'],'checked':True});a=banking.accounts()[0]
        with self.assertRaises(ValueError):banking.save_account({**a,'status':'closed'})
        banking.save_account({**a,'status':'closed','closed_on':'2026-09-30'})
        t=app.state()['transactions'][0];intake.save_evidence({'id':t['id'],'receipt_note':'Noch im Archiv erreichbar'})
        payload={'direction':'expense','amount':'1,00','partner':'Test','title':'Test','account_id':a['id'],'payment_method':'bank','paid_on':'2026-10-01'}
        with self.assertRaisesRegex(ValueError,'Kontozeitraums'):app.save_transaction(payload)
        app.save_transaction({**payload,'paid_on':'2024-04-03'})
        self.assertEqual(len(app.state()['transactions']),2)
    def test_cash_deposit_never_assumed_private(self):
        row={'partner':'Volksbank','purpose':'Bargeldeinzahlung','counterparty_iban':''}
        self.assertEqual(banking.row_classification(row,banking.accounts()[0],banking.accounts())[:2],('cash_deposit','unknown'))
    def test_pdf_source_validation_rejects_invented_rows_and_float(self):
        valid=intake.normalize_pdf_rows({'rows':[ROW]},PAGE,2025);self.assertEqual(valid[0]['amount_cents'],-1234)
        for edit in [{'amount':'-22,34'},{'booked_on':'2025-04-04'},{'currency':'USD'},{'amount':12.34},{'quote':'halluzinierte Quelle'}]:
            with self.subTest(edit=edit),self.assertRaises(ValueError):intake.normalize_pdf_rows({'rows':[{**ROW,**edit}]},PAGE,2025)
    def test_pdf_blind_readers_and_review_then_cent_booking(self):
        j=self.read_pdf();self.assertEqual(j['state'],'review');self.assertEqual(j['result']['difference_cents'],0)
        self.assertEqual(app.state()['transactions'],[])
        p=intake.save_pdf_review(self.pdf_payload(j));self.assertEqual(p['source_kind'],'pdf');self.assertTrue(p['pdf_checked'])
        self.assertEqual(intake.save_pdf_review(self.pdf_payload(j))['id'],p['id'])
        banking.commit({'id':p['id'],'checked':True});t=app.state()['transactions'][0]
        self.assertEqual((t['amount_cents'],t['direction']),(1234,'expense'));self.assertEqual(t['statement_document_id'],j['document_id']);self.assertEqual(t['document_ids'],[])
        removed=app.archive('documents',j['document_id']);self.assertEqual(removed['payments_preserved'],1)
        self.assertEqual(len(app.state()['transactions']),1)
        import recycle
        recycle.restore({'id':removed['id']})
    def test_pdf_disagreement_needs_documented_resolution(self):
        j=self.read_pdf({**READING,'rows':[{**ROW,'amount':'12,34'}]})
        self.assertTrue(j['result']['issues'])
        with self.assertRaisesRegex(ValueError,'Prüfpunkte'):intake.save_pdf_review(self.pdf_payload(j))
        p=intake.save_pdf_review(self.pdf_payload(j,review_note='Minuszeichen im Original ist eindeutig; Arbeiter stimmt.'));self.assertTrue(p['pdf_checked'])
    def test_pdf_balance_mismatch_cannot_be_overridden_by_note(self):
        j=self.read_pdf();rows=[{**j['result']['rows'][0],'amount':'12,34'}]
        with self.assertRaisesRegex(ValueError,'Saldenprüfung'):intake.save_pdf_review(self.pdf_payload(j,rows=rows,review_note='Ein langer Text genügt nicht.'))
        self.assertEqual(app.state()['transactions'],[])
    def test_pdf_balance_correction_needs_source(self):
        j=self.read_pdf()
        with self.assertRaisesRegex(ValueError,'Fundstelle'):intake.save_pdf_review(self.pdf_payload(j,opening_balance='20,00'))
        with self.assertRaisesRegex(ValueError,'nicht entfernen'):intake.save_pdf_review(self.pdf_payload(j,opening_balance=''))
    def test_pdf_incomplete_edit_survives_restart(self):
        j=self.read_pdf();rows=[{**ROW,'page':1,'amount':'-'}]
        with app.db() as con: before=con.execute('SELECT count(*) FROM audit').fetchone()[0]
        intake.save_pdf_review({'id':j['id'],'rows':rows,'review_note':'Zwischenstand'})
        with app.db() as con: self.assertGreater(con.execute('SELECT count(*) FROM audit').fetchone()[0],before)
        app.initialize();saved=intake.job(j['id']);self.assertEqual(saved['result']['rows'][0]['amount'],'-')
    def test_interrupted_job_keeps_original_and_partial_results(self):
        j=self.upload_pdf();intake.update(j['id'],state='running',pages_json=app.enc([PAGE]),result_json=app.enc({'rows':[ROW]}))
        app.initialize();j=intake.job(j['id']);self.assertEqual(j['state'],'error');self.assertTrue(j['result']['rows']);self.assertTrue(app.state()['documents'])
    def test_three_classifiers_are_blind_and_never_book(self):
        p=self.preview();line=p['rows'][0]['line'];jid=app.new_id()
        with app.db() as con:app.insert(con,'intake_jobs',{'id':jid,'kind':'classify','year':2025,'account_id':p['account']['id'],'import_id':p['id'],'state':'running','created_at':app.now(),'updated_at':app.now()})
        def answer(scope):return {'rows':[{'line':line,'scope':scope,'category':'Software & Abos','reason':'Vorschlag','question':''}]}
        calls=[]
        def model(name,system,content,limit):
            calls.append((name,content));return answer('business') if name=='qwen' else answer('private') if name=='gemma' else {'summary':'Widerspruch bleibt offen'}
        with patch.object(intelligence,'call_model',side_effect=model):intake.run_classification(jid,['qwen','gemma','gpt'])
        self.assertEqual(calls[0][1],calls[1][1]);r=banking.saved_preview(p['id'])['rows'][0];self.assertEqual(r['scope'],'unknown');self.assertFalse(r['ai']['agree']);self.assertEqual(app.state()['transactions'],[])
    def test_user_edit_wins_against_slow_classifier(self):
        p=self.preview();line=p['rows'][0]['line'];jid=app.new_id()
        with app.db() as con:app.insert(con,'intake_jobs',{'id':jid,'kind':'classify','year':2025,'account_id':p['account']['id'],'import_id':p['id'],'state':'running','created_at':app.now(),'updated_at':app.now()})
        def model(name,system,content,limit):
            if name=='gpt':
                banking.save_preview({'id':p['id'],'edits':{str(line):{'scope':'private','review_note':'Meine Entscheidung'}}});return {'summary':'Zusammenfassung'}
            return {'rows':[{'line':line,'scope':'business','category':'Software & Abos','reason':'Vorschlag','question':''}]}
        with patch.object(intelligence,'call_model',side_effect=model):intake.run_classification(jid,['qwen','gemma','gpt'])
        self.assertEqual(banking.saved_preview(p['id'])['rows'][0]['scope'],'private')
    def test_backup_contains_pdf_jobs_originals_and_review(self):
        j=self.read_pdf();raw=storage.backup_bytes();dest=Path(self.temp.name)/'restored';storage.verify_zip(raw,dest)
        with sqlite3.connect(dest/'steuerstudio.sqlite3') as con:
            self.assertEqual(con.execute('SELECT count(*) FROM intake_jobs').fetchone()[0],1)
            row=con.execute('SELECT stored_name,sha256 FROM documents WHERE id=?',(j['document_id'],)).fetchone()
        self.assertEqual(hashlib.sha256((dest/'originale'/row[0]).read_bytes()).hexdigest(),row[1])
    @unittest.skipUnless(PDF_AVAILABLE,'Development PDF dependencies absent')
    def test_real_text_pdf_extraction(self):
        pages=intake.pdf_pages(pdf_bytes());self.assertEqual(len(pages),1);self.assertEqual(pages[0]['method'],'pdf_text');self.assertIn('-12,34',pages[0]['text'])
    @unittest.skipUnless(PDF_AVAILABLE and importlib.util.find_spec('pypdfium2') and intake.tesseract_path(),'OCR not installed')
    def test_real_scan_pdf_local_ocr(self):
        pages=intake.pdf_pages(pdf_bytes(scan=True));self.assertTrue(pages[0]['method'].startswith('ocr'));self.assertIn('12,34',pages[0]['text']);self.assertIn('03.04.2025',pages[0]['text'])
if __name__=='__main__':unittest.main()
