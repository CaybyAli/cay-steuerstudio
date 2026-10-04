"""Regression for a legacy draft: Feb 2026, pages 3/4, bank fee 16.82 EUR.

Synthetic source layout with the reported control amounts, no customer PDF.
"""
import base64
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app, intake, pdf_review, statements
from test_intake import pdf_bytes

MAIN='''VR-GiroBusiness
EUR-Konto Kontonummer 123456789
Kontoauszug Nr. 2/2026
erstellt am 28.02.2026 Blatt 1 von 2
IBAN: DE89 3704 0044 0532 0130 00
Gesamtumsatz: 51,19 S 42,21 H
neuer Kontostand vom 27.02.2026 4,37 S
Bu-Tag Wert Vorgang
alter Kontostand 4,61 H
03.02. 03.02. Entgelt/Auslagen PN:1 2,20 S
 Bankentgelt
09.02. 09.02. Überweisungsgutschr. PN:2 10,60 H
 Testperson
09.02. 09.02. Kartenzahlung PN:3 12,99 S
 Test-Abo
11.02. 11.02. Einzahlung PN:4 20,00 H
 Testbank
12.02. 12.02. Kartenzahlung PN:5 19,18 S
 Testanbieter
27.02. 27.02. Überweisungsgutschr. PN:6 11,61 H
 Testperson
Übertrag auf Blatt 2 12,45 H
'''
CONTINUATION='''VR-GiroBusiness
EUR-Konto Kontonummer 123456789
Kontoauszug Nr. 2/2026
erstellt am 28.02.2026 Blatt 2 von 2
Bu-Tag Vorgang
Übertrag von Blatt 1 12,45 H
27.02. Abschluss PN:905 16,82 S
 Entgelt Kontoführung 9,90 S
 Buchungsposten 6,92 S
 Abschluss vom 30.01.2026 bis 28.02.2026
neuer Kontostand vom 27.02.2026 4,37 S
'''

def pages():
    return [{'page':3,'text':MAIN,'method':'pdf_text'},
            {'page':4,'text':CONTINUATION,'method':'pdf_text'}]

def legacy_result(ps=None,day='2026-02-27',amount='-16,82'):
    ps=ps or pages();result=statements.parse_document([ps[0]])
    result['rows'].append({'page':4,'booked_on':day,'amount':amount,'currency':'EUR',
        'partner':'VR-Bank','purpose':'Abschluss PN:905','quote':'Von der KI umformulierter Abschluss',
        'scope':'private','reviewed':True,'review_note':'Meine erhaltene Notiz'})
    for row in result['rows']:row.update(scope='private',reviewed=True)
    result['issues'].append('Seite 4: Leser unterscheiden sich bei Anzahl, Datum oder Betrag.')
    result['page_status'].append({'page':4,'state':'read','count':1})
    return result

class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=app.DATA;app.DATA=Path(self.tmp.name)/'data';app.initialize()
    def tearDown(self):app.DATA=self.old;self.tmp.cleanup()
    def draft(self,ps=None,day='2026-02-27',amount='-16,82'):
        ps=ps or pages()
        j=intake.upload({'year':2026,'account_id':'account_volksbank','filename':'Februar.pdf',
            'file_base64':base64.b64encode(pdf_bytes()).decode()})['job']
        intake.update(j['id'],pages_json=app.enc(ps),result_json=app.enc(legacy_result(ps,day,amount)),state='review')
        return intake.job(j['id'])
    def test_legacy_draft_reconciles_both_pages_without_rereading_or_editing_rows(self):
        j=self.draft();before=copy.deepcopy(j['result']);review=pdf_review.check({'id':j['id']})['review']
        self.assertEqual(len(review['checks']),1);c=review['checks'][0]
        self.assertEqual(c['pages'],[3,4]);self.assertEqual(c['incoming_cents'],4221)
        self.assertEqual(c['outgoing_cents'],5119);self.assertEqual(c['calculated_closing_cents'],-437)
        self.assertEqual((c['difference_cents'],c['credit_difference_cents'],c['debit_difference_cents']),(0,0,0))
        self.assertEqual(review['months'][0]['status'],'ok');self.assertEqual(review['diagnostics'],[])
        self.assertEqual(c['page_links'][0]['page'],4)
        self.assertEqual(intake.job(j['id'])['result'],before)
    def test_fee_period_end_is_not_a_posting_date_and_correction_is_explicit(self):
        j=self.draft(day='2026-02-28');review=pdf_review.check({'id':j['id']})['review']
        self.assertEqual(review['checks'][0]['difference_cents'],0)
        self.assertEqual(review['months'][0]['status'],'blocked')
        c=review['diagnostics'][0]['candidates'][0]
        self.assertEqual(c['booked_on'],'2026-02-27');self.assertEqual(c['amount_cents'],-1682)
        self.assertIn('Abrechnungszeitraum',c['explanation'])
        self.assertEqual(intake.job(j['id'])['result']['rows'][-1]['booked_on'],'2026-02-28')
    def test_wrong_sign_is_not_accepted_just_to_match_other_controls(self):
        j=self.draft(amount='16,82');review=pdf_review.check({'id':j['id']})['review']
        self.assertEqual(review['checks'][0]['difference_cents'],-3364)
        self.assertIn('amount',review['diagnostics'][0]['candidates'][0]['differences'])
        self.assertEqual(review['months'][0]['status'],'blocked')
    def test_different_account_or_statement_never_attached_by_matching_amount(self):
        for old,new in [('123456789','987654321'),('Nr. 2/2026','Nr. 3/2026'),('EUR-Konto','USD-Konto')]:
            ps=pages();ps[1]['text']=ps[1]['text'].replace(old,new)
            checks=statements.known_document(ps)['balance_checks']
            with self.subTest(change=new):self.assertEqual(checks[0]['pages'],[3])
    def test_missing_statement_number_does_not_guess_from_date_or_balance(self):
        ps=pages();ps[1]['text']=ps[1]['text'].replace('Kontoauszug Nr. 2/2026','Kontoauszug')
        j=self.draft(ps);review=pdf_review.check({'id':j['id']})['review']
        self.assertEqual(review['checks'][0]['pages'],[3]);self.assertEqual(review['checks'][1]['key'],'other')
        self.assertIn('keinem Auszug',review['checks'][1]['explanation'])
    def test_other_iban_and_ambiguous_header_do_not_merge(self):
        for extra in ['IBAN: DE44 5001 0517 5407 3249 31','Kontoauszug Nr. 3/2026']:
            ps=pages();ps[1]['text']=ps[1]['text'].replace('Bu-Tag Vorgang',extra+'\nBu-Tag Vorgang')
            with self.subTest(extra=extra):self.assertEqual(statements.known_document(ps)['balance_checks'][0]['pages'],[3])
    def test_unsigned_fee_or_breakdown_does_not_become_a_proven_payment(self):
        page=pages()[1];self.assertEqual(len(statements.partial_page_rows(page)),1)
        page['text']=page['text'].replace('27.02. Abschluss PN:905 16,82 S','27.02. Abschluss PN:905 16,82')
        self.assertEqual(statements.partial_page_rows(page),[])
    def test_conflicting_original_control_does_not_disappear_when_pages_match(self):
        ps=pages();ps[1]['text']=ps[1]['text'].replace('4,37 S','9,37 S')
        j=self.draft(ps);review=pdf_review.check({'id':j['id']})['review']
        self.assertEqual(review['checks'][0]['pages'],[3]);self.assertNotEqual(review['months'][0]['status'],'ok')
    def test_single_date_row_in_old_table_header_is_not_silently_dropped(self):
        page=pages()[1];page['text']=page['text'].replace('Bu-Tag Vorgang','Bu-Tag Wert Vorgang')
        self.assertIsNone(statements.parse_page(page))
        self.assertEqual(statements.source_rows(page)[0]['amount_cents'],-1682)
    def test_deleting_real_fee_cannot_bypass_source_coverage(self):
        j=self.draft();rows=copy.deepcopy(j['result']['rows']);rows[-1].update(excluded=True,exclusion_reason='not_payment')
        review=pdf_review.check({'id':j['id'],'rows':rows})['review']
        self.assertEqual(review['months'][0]['missing'][0]['amount_cents'],-1682)
        self.assertEqual(review['months'][0]['status'],'blocked')
    def test_approve_existing_corrected_draft_once_and_keep_choices_notes_original(self):
        j=self.draft(day='2026-02-28');review=pdf_review.check({'id':j['id']})['review']
        corrected=review['diagnostics'][0]['candidates'][0]
        rows=copy.deepcopy(j['result']['rows']);rows[-1].update({k:corrected[k] for k in ('booked_on','amount','source_id','quote')})
        p={'id':j['id'],'rows':rows,'checked':True,'months':['2026-02'],
            'overrides':{'2026-02':{'note':'Abschluss im Original verglichen und Buchungstag korrigiert.'}}}
        intake.save_pdf_review(p);app.initialize()
        r=intake.approve_pdf(p);self.assertEqual(r['result']['imported'],7)
        app.initialize();tx=app.state()['transactions'];self.assertEqual(len(tx),7)
        self.assertEqual(sum(t['amount_cents']*(1 if t['direction']=='income' else -1) for t in tx),-898)
        self.assertTrue(all(t['scope']=='private' for t in tx))
        self.assertTrue(any('Meine erhaltene Notiz' in t['notes'] for t in tx))
        self.assertEqual(pdf_review.approvals(j['id'])[0]['report']['checks'][0]['pages'],[3,4])
        self.assertTrue(intake.approve_pdf(p)['already_approved']);self.assertEqual(len(app.state()['transactions']),7)

if __name__=='__main__':unittest.main()
