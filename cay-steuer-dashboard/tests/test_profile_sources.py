import io
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import assessments
import intelligence
import laws
import storage
import taxprofile

class ProfileSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = app.DATA
        app.DATA = Path(self.temp.name) / 'data'
        app.initialize()

    def tearDown(self):
        self.wait_update()
        app.DATA = self.previous
        self.temp.cleanup()

    def wait_update(self):
        limit = time.monotonic() + 5
        event = threading.Event()
        while laws.LOCK.locked() and time.monotonic() < limit:
            event.wait(.01)
        self.assertFalse(laws.LOCK.locked())

    def xml(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as z:
            z.writestr('law.xml', '<dokumente><norm><metadaten><enbez>§ 20</enbez></metadaten><textdaten><P>Test für vereinnahmte Entgelte.</P></textdaten></norm></dokumente>')
        return out.getvalue()

    def test_year_isolation_restart_and_backup(self):
        taxprofile.save({'year': 2024, 'vat_status': 'regular', 'filing_status': 'submitted', 'personal_notes': 'Student 2025; Zeitraum prüfen.'})
        taxprofile.save({'year': 2025, 'vat_status': 'small', 'filing_status': 'open'})
        app.initialize()
        self.assertEqual(taxprofile.get(2024)['vat_status'], 'regular')
        self.assertEqual(taxprofile.get(2025)['vat_status'], 'small')
        self.assertEqual(taxprofile.get(2026)['vat_status'], 'unknown')
        self.assertEqual(app.state()['settings']['personal_notes'], 'Student 2025; Zeitraum prüfen.')
        target = Path(self.temp.name)/'restore'
        storage.verify_zip(app.backup_bytes(), target)
        import sqlite3
        with sqlite3.connect(target/'steuerstudio.sqlite3') as con:
            self.assertEqual(con.execute('SELECT vat_status FROM tax_profiles WHERE year=2024').fetchone()[0], 'regular')

    def test_legacy_settings_are_preserved_without_guessing_year(self):
        app.save_settings({'vat_status': 'regular', 'taxation': 'cash', 'filing_2025': 'submitted'})
        app.initialize()
        self.assertEqual(taxprofile.get(2025)['filing_status'], 'submitted')
        for year in [2024,2025,2026]:
            self.assertEqual(taxprofile.get(year)['vat_status'], 'unknown')
            self.assertEqual(taxprofile.get(year)['taxation'], 'unknown')
        self.assertEqual(app.state()['settings']['taxation'], 'cash')

    def test_invalid_profile_is_atomic(self):
        with self.assertRaises(ValueError):
            taxprofile.save({'year':2024,'vat_status':'invented','personal_notes':'Must not save'})
        self.assertEqual(taxprofile.all_profiles(), [])
        self.assertEqual(app.state()['settings']['personal_notes'], '')

    @unittest.skipUnless(assessments.manifest(), 'Optionales privates Bescheidpaket ist nicht Teil des Programmupdates')
    def test_proposal_requires_intact_imported_sources_and_does_not_auto_save(self):
        self.assertIsNone(app.state()['tax_profile_proposal'])
        assessments.import_bundle()
        self.assertEqual(app.state()['tax_profile_proposal']['year'], 2024)
        self.assertEqual(taxprofile.get(2024)['vat_status'], 'unknown')
        d = app.state()['documents'][0]
        app.update_document(d['id'], {**d, 'notes': 'Quelle verändert'})
        self.assertIsNone(app.state()['tax_profile_proposal'])

    def test_chat_uses_only_selected_year_and_citable_notes(self):
        taxprofile.save({'year':2024,'vat_status':'regular','personal_notes':'Student 2025; BAföG ungeklärt.'})
        c = intelligence.chat_context('Welchen Umsatzsteuerstatus und welche Notizen hast du?', 2025, [])
        self.assertEqual(c['profile']['vat_status'], 'unknown')
        self.assertNotIn('filing_2025', c['profile'])
        source = next(s for s in c['sources'] if s['id']=='P:2025')
        answer = intelligence.normalize_answer({'answer':'Gespeicherte Notiz.','citations':[{'source_id':'P:2025','quote':'Student 2025; BAföG ungeklärt.'}]}, c)
        self.assertEqual(len(answer['citations']),1)
        taxprofile.save({'year':2025,'vat_status':'regular'})
        self.assertNotEqual(taxprofile.source(2025,app.state()['settings']['personal_notes'])['source_hash'],source['source_hash'])

    def test_failure_survives_restart_preserves_archive_and_targeted_retry(self):
        with patch.object(laws,'download',return_value=self.xml()):
            laws.fetch_one(laws.CATALOG[0])
        before = laws.overview()
        with patch.object(laws,'download',side_effect=HTTPError('url',503,'unavailable',{},None)), patch.object(laws.time,'sleep'):
            laws.start_update(['estg']); self.wait_update()
        after = laws.overview()
        self.assertEqual(len(before['versions']),len(after['versions']))
        error = next(c for c in after['checks'] if c['source_id']=='estg')
        self.assertIn('503',error['error'])
        self.assertEqual(error['checked_at'],before['checks'][0]['checked_at'])
        app.initialize()
        self.assertEqual(laws.overview()['failed_count'],1)
        with patch.object(laws,'download',return_value=self.xml()) as download:
            laws.start_update(['estg']); self.wait_update()
            self.assertEqual([call.args[0]['id'] for call in download.call_args_list], ['estg'])
        self.assertEqual(laws.overview()['failed_count'],0)
        self.assertEqual(laws.overview()['downloaded_count'],1)
        self.assertEqual(len(laws.overview()['versions']),len(before['versions']))

    def test_download_retries_temporary_network_errors_but_not_denied_access(self):
        with patch.object(laws,'download',side_effect=[URLError(socket.gaierror('dns')),self.xml()]) as download, patch.object(laws.time,'sleep'):
            laws.fetch_one(laws.CATALOG[0]); self.assertEqual(download.call_count,2)
        with patch.object(laws,'download',side_effect=HTTPError('url',403,'denied',{},None)) as download:
            with self.assertRaises(HTTPError): laws.fetch_one(laws.CATALOG[0])
            self.assertEqual(download.call_count,1)
        with self.assertRaises(ValueError): laws.start_update(['https://example.com'])
