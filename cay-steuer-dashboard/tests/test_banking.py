import base64
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import banking
import intelligence
import storage


def test_iban(serial):
    bban='12345678'+str(serial).zfill(10)
    check=98-int(bban+'131400')%97
    return 'DE'+str(check).zfill(2)+bban


MAIN=test_iban(1)
TAX=test_iban(2)
OTHER=test_iban(3)


class BankingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=app.DATA
        app.DATA=Path(self.temp.name)/'data'
        app.initialize()
        for aid,number in [('account_n26',MAIN),('account_fyrst',TAX)]:
            account=next(a for a in banking.accounts() if a['id']==aid)
            banking.save_account({**account,'iban':number,'status':'active'})

    def tearDown(self):
        app.DATA=self.old
        self.temp.cleanup()

    def preview(self,text,account='account_n26',year=2025,encoding='utf-8',**options):
        return banking.preview({'year':year,'account_id':account,'filename':'Bank.csv','file_base64':base64.b64encode(text.encode(encoding)).decode(),'options':options})

    def n26(self,lines):
        return 'Date,Payee,Account number,Transaction type,Payment reference,Amount (EUR),Amount (Foreign Currency),Type Foreign Currency,Exchange Rate\n'+lines

    def fyr(self,lines):
        return 'Umsatzübersicht\nBuchungstag;Wert;Umsatzart;Begünstigter / Auftraggeber;Verwendungszweck;IBAN / Kontonummer;Betrag;Währung\n'+lines

    def test_cp1252_german_grouping_umlauts_and_integer(self):
        p=self.preview(self.fyr('03.04.2025;03.04.2025;Lastschrift;Müller;Software;;-1.234,56;EUR\n'),'account_fyrst',encoding='cp1252')
        self.assertEqual(p['encoding'],'cp1252')
        self.assertEqual(p['rows'][0]['amount_cents'],-123456)
        self.assertEqual(p['rows'][0]['partner'],'Müller')
        r=banking.commit({'checked':True,'id':p['id']})
        self.assertEqual(r['imported'],1)
        with app.db() as con:
            self.assertEqual(con.execute('SELECT typeof(amount_cents) FROM bank_rows').fetchone()[0],'integer')
            self.assertEqual(con.execute('SELECT typeof(amount_cents) FROM transactions').fetchone()[0],'integer')
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute('UPDATE transactions SET amount_cents=1.5')

    def test_n26_foreign_columns_never_replace_eur_amount(self):
        p=self.preview(self.n26('2025-04-03,Google,,Transfer,Abrechnung,12.34,999.99,USD,1.2\n'))
        self.assertEqual(p['rows'][0]['amount_cents'],1234)
        banking.commit({'checked':True,'id':p['id']})
        self.assertEqual(app.state()['transactions'][0]['amount_cents'],1234)

    def test_cash_entry_is_never_auto_linked_to_same_bank_amount(self):
        app.save_transaction({'direction':'expense','amount':'49,90','paid_on':'2025-04-03','partner':'Lidl','title':'Zutaten Video',
                              'payment_method':'cash','cash_source':'private_wallet','expense_kind':'video_purchase',
                              'business_purpose':'Rezeptvideo'})
        p=self.preview(self.n26('2025-04-03,Lidl,,Card,Einkauf,-49.90,,,\n'))
        self.assertEqual(p['rows'][0]['status'],'ready')
        self.assertEqual(p['rows'][0]['manual_matches'],[])

    def test_atm_withdrawal_remains_cash_movement_review(self):
        p=self.preview(self.n26('2025-04-03,Geldautomat,,Cash,Abhebung,-100.00,,,\n'))
        self.assertEqual(p['rows'][0]['classification'],'cash_withdrawal')
        self.assertEqual(p['rows'][0]['scope'],'unknown')

    def test_volksbank_bom_preamble_and_quoted_multiline(self):
        csv='\ufeffUmsätze\nBezeichnung Auftragskonto;IBAN Auftragskonto;Buchungstag;Valutadatum;Name Zahlungsbeteiligter;IBAN Zahlungsbeteiligter;Buchungstext;Verwendungszweck;Betrag;Waehrung\nGiro;;03.04.2025;04.04.2025;Beispiel;;Karte;"Abo; April\nRechnung 7";-49,90;EUR\n'
        p=self.preview(csv,'account_volksbank')
        self.assertEqual(p['errors'],[])
        self.assertEqual(p['rows'][0]['amount_cents'],-4990)
        self.assertIn('Rechnung 7',p['rows'][0]['purpose'])

    def test_import_is_idempotent_and_overlaps_deduplicated(self):
        first=self.n26('2025-04-03,A,,Card,Software,-49.90,,,\n')
        p=self.preview(first)
        r=banking.commit({'checked':True,'id':p['id']})
        self.assertEqual(banking.commit({'checked':True,'id':p['id']}),r)
        self.assertTrue(self.preview(first)['already_imported'])
        p=self.preview(first+'2025-04-04,B,,Card,Hardware,-99.90,,,\n')
        self.assertEqual([r['status'] for r in p['rows']],['duplicate','ready'])
        r=banking.commit({'checked':True,'id':p['id']})
        self.assertEqual((r['imported'],r['skipped']),(1,1))
        self.assertEqual(len(app.state()['transactions']),2)

    def test_same_day_identical_real_transactions_preserve_multiplicity(self):
        line='2025-04-03,A,,Card,Software,-0.10,,,\n'
        p=self.preview(self.n26(line+line))
        banking.commit({'checked':True,'id':p['id']})
        p=self.preview(self.n26(line+line+'2025-04-04,B,,Card,Abo,-0.20,,,\n'))
        self.assertEqual([r['status'] for r in p['rows']],['duplicate','duplicate','ready'])
        banking.commit({'checked':True,'id':p['id']})
        self.assertEqual(sum(t['amount_cents'] for t in app.state()['transactions']),40)

    def test_manual_entry_linked_without_double_counting(self):
        tid=app.save_transaction({'direction':'expense','amount':'49,90','paid_on':'2025-04-03','partner':'A','title':'Software','scope':'business'})['id']
        p=self.preview(self.n26('2025-04-03,A,,Card,Software,-49.90,,,\n'))
        self.assertEqual(p['rows'][0]['status'],'manual_review')
        with self.assertRaises(ValueError):
            banking.commit({'checked':True,'id':p['id']})
        r=banking.commit({'checked':True,'id':p['id'],'choices':{str(p['rows'][0]['line']):'link:'+tid}})
        self.assertEqual(r['linked'],1)
        self.assertEqual(len(app.state()['transactions']),1)
        self.assertIsNotNone(app.state()['transactions'][0]['bank_row_id'])

    def test_two_sides_auto_neutral_and_year_boundary(self):
        p=self.preview(self.n26(f'2025-12-31,Eigenes Steuerkonto,{TAX},Transfer,Steuerruecklage,-300.00,,,\n'))
        banking.commit({'checked':True,'id':p['id']})
        self.assertEqual(app.state()['transactions'][0]['scope'],'transfer')
        self.assertEqual(len(banking.status(2025)['unpaired']),1)
        p=self.preview(self.fyr(f'02.01.2026;02.01.2026;Überweisung;Eigenes Hauptkonto;Steuerrücklage;{MAIN};300,00;EUR\n'),'account_fyrst',2026,encoding='cp1252')
        banking.commit({'checked':True,'id':p['id']})
        self.assertEqual(len(banking.status(2025)['transfers']),1)
        self.assertEqual(len(banking.status(2026)['transfers']),1)
        self.assertTrue(all(t['scope']=='transfer' for t in app.state()['transactions']))
        c=intelligence.chat_context('Einnahmen Ausgaben',2025,[])
        self.assertNotIn('2025-12/business',c['totals_by_month_and_scope'])

    def test_tax_office_debit_not_neutral_or_automatically_deductible(self):
        p=self.preview(self.fyr('03.04.2025;03.04.2025;Lastschrift;Finanzamt;Steuerzahlung;;-100,00;EUR\n'),'account_fyrst',encoding='cp1252')
        banking.commit({'checked':True,'id':p['id']})
        self.assertEqual(app.state()['transactions'][0]['scope'],'unknown')
        self.assertEqual(banking.status(2025)['transfers'],[])

    def test_equal_amount_dates_without_ibans_require_review(self):
        p=self.preview(self.n26('2025-04-03,Transfer,,Transfer,Ruecklage,-100.00,,,\n'))
        banking.commit({'checked':True,'id':p['id']})
        p=self.preview(self.fyr('04.04.2025;04.04.2025;Überweisung;Transfer;Rücklage;;100,00;EUR\n'),'account_fyrst',encoding='cp1252')
        banking.commit({'checked':True,'id':p['id']})
        state=banking.status(2025)
        self.assertEqual(len(state['candidates']),1)
        self.assertEqual(state['transfers'],[])
        self.assertTrue(all(t['scope']=='unknown' for t in app.state()['transactions']))
        pair=state['candidates'][0]
        banking.confirm_pair({'outgoing_id':pair['outgoing']['id'],'incoming_id':pair['incoming']['id']})
        self.assertEqual(len(banking.status(2025)['transfers']),1)

    def test_wrong_counterparty_and_different_amounts_not_paired(self):
        p=self.preview(self.n26(f'2025-04-03,Supplier,{OTHER},Transfer,Invoice,-100.00,,,\n'))
        banking.commit({'checked':True,'id':p['id']})
        p=self.preview(self.fyr(f'04.04.2025;04.04.2025;Überweisung;Customer;Sales;{OTHER};100,00;EUR\n'),'account_fyrst',encoding='cp1252')
        banking.commit({'checked':True,'id':p['id']})
        self.assertEqual(banking.status(2025)['candidates'],[])

    def test_invalid_csv_stops_entire_commit_and_manual_mapping(self):
        p=self.preview(self.n26('2025-04-03,A,,Card,Valid,-49.90,,,\n2025-02-30,B,,Card,Invalid,-1.00,,,\n'))
        self.assertTrue(p['errors'])
        with self.assertRaises(ValueError):
            banking.commit({'checked':True,'id':p['id']})
        self.assertEqual(app.state()['transactions'],[])
        p=self.preview('Tag;Person;Summe\n03.04.2025;A;-49,90\n','account_volksbank',mapping={'date':0,'partner':1,'amount':2},header_row=0)
        self.assertEqual(p['errors'],[])
        self.assertEqual(p['rows'][0]['amount_cents'],-4990)

    def test_year_filter_and_preview_survive_restart(self):
        p=self.preview(self.n26('2025-12-31,A,,Card,2025,-1.00,,,\n2026-01-01,A,,Card,2026,-2.00,,,\n'))
        self.assertEqual(p['rows'][1]['status'],'outside_year')
        app.initialize()
        self.assertEqual(banking.saved_preview(p['id'])['rows'],p['rows'])
        result=banking.commit({'checked':True,'id':p['id']})
        self.assertEqual((result['imported'],result['skipped']),(1,1))

    def test_signed_amounts_exact_and_ambiguous_formats_rejected(self):
        for value,want in [('-1.234,56',-123456),('0,01',1),('1.000',100000),('(12,50)',-1250),('5,00-',-500)]:
            self.assertEqual(banking.signed_cents(value,'de'),want)
        for value in ['1e3','NaN','1,234.56','12,345']:
            with self.assertRaises(ValueError):
                banking.signed_cents(value,'de')
        with self.assertRaises(ValueError):
            banking.signed_cents('1.234','en')


if __name__=='__main__':
    unittest.main()
