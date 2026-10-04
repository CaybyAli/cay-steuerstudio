"""Synthetic regression tests. Run: python -m unittest discover -s tests -v"""
import base64
import csv
import hashlib
import http.client
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_data = app.DATA
        app.DATA = Path(self.temp.name) / 'daten'
        app.initialize()

    def tearDown(self):
        app.DATA = self.old_data
        self.temp.cleanup()

    def doc(self, **overrides):
        return app.create_document({'title': 'Testbrief', 'kind': 'Finanzamt', 'year': 2025,
                    'received_date': '2026-09-18', 'body': 'Bitte Belege bis zum 15.10.2026 einreichen.', **overrides})['id']

    def tx(self, **overrides):
        return app.save_transaction({'direction': 'expense', 'amount': '49,90', 'paid_on': '2025-04-03',
                    'partner': 'Testpartner', 'title': 'Testkauf', **overrides})['id']

    def task(self, **overrides):
        return {'title': 'Belege einreichen', 'year': 2025, 'kind': 'Antwort', 'due_on': '2026-10-15',
                'prepare_on': '2026-10-01', 'due_confirmed': True, 'status': 'open', **overrides}

    def test_clean_workspace_and_unknown_tax_status(self):
        data = app.state()
        for key in ['documents', 'transactions', 'tasks']:
            self.assertEqual(data[key], [])
        for key in ['vat_status', 'taxation', 'filing_2025']:
            self.assertEqual(data['settings'][key], 'unknown')

    def test_exact_cents_and_german_grouping(self):
        for raw, expected in {'0,01': 1, '49,90': 4990, '1.249,90': 124990,
                              '1.000': 100000, '19.99': 1999, '€ 10,10': 1010}.items():
            with self.subTest(raw=raw):
                self.assertEqual(app.cents(raw), expected)
        for raw in ['0', '-1', 'NaN', 'Infinity', '2,345', '1e3', '10000001', '1.2.3,40', '1,000.00']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                app.cents(raw)

    def test_edit_archive_and_audit_do_not_double_count(self):
        tx_id = self.tx(amount='0,10')
        self.tx(amount='0,20')
        self.assertEqual(sum(t['amount_cents'] for t in app.state()['transactions']), 30)
        app.save_transaction({'direction': 'expense', 'amount': '1,30', 'paid_on': '2025-04-03',
                              'partner': 'Test', 'title': 'Korrektur'}, tx_id)
        self.assertEqual(sum(t['amount_cents'] for t in app.state()['transactions']), 150)
        app.archive('transactions', tx_id)
        self.assertEqual(sum(t['amount_cents'] for t in app.state()['transactions']), 20)
        with app.db() as con:
            log = app.rows(con, 'SELECT * FROM audit WHERE entity_id=? ORDER BY id', (tx_id,))
            self.assertEqual([x['action'] for x in log], ['create', 'update', 'archive'])
            self.assertEqual(json.loads(log[1]['before_json'])['amount_cents'], 10)

    def test_original_unchanged_after_text_edit_and_duplicate_upload(self):
        raw = b'Original receipt 49,90'
        payload = {'filename': '../../beleg.txt', 'file_base64': base64.b64encode(raw).decode(), 'body': ''}
        doc_id = self.doc(**payload)
        self.assertEqual(self.doc(**payload), doc_id)
        doc = app.state()['documents'][0]
        self.assertEqual(doc['filename'], 'beleg.txt')
        self.assertEqual(doc['sha256'], hashlib.sha256(raw).hexdigest())
        app.update_document(doc_id, {**doc, 'body': 'Korrigierter Lesetext'})
        self.assertEqual((app.DATA / 'originale' / doc['stored_name']).read_bytes(), raw)
        self.assertEqual(len(app.state()['documents']), 1)

    def test_multiple_receipts_and_archive_protection(self):
        a, b = self.doc(title='A'), self.doc(title='B')
        tx_id = self.tx(document_ids=[a, b, a])
        self.assertEqual(set(app.state()['transactions'][0]['document_ids']), {a, b})
        with self.assertRaises(ValueError):
            app.archive('documents', a)
        app.archive('transactions', tx_id)
        app.archive('documents', a)
        self.assertEqual(len(app.state()['documents']), 1)

    def test_invalid_edit_rolls_back(self):
        tx_id = self.tx()
        with self.assertRaises(ValueError):
            app.save_transaction({'direction': 'expense', 'amount': '99', 'paid_on': '2025-04-03',
                                  'partner': 'X', 'title': 'Y', 'document_ids': ['missing']}, tx_id)
        self.assertEqual(app.state()['transactions'][0]['amount_cents'], 4990)

    def test_bad_dates_years_and_foreign_currency_rejected(self):
        for day in ['2025-02-29', '2025-13-01', '20250403']:
            with self.subTest(day=day), self.assertRaises(ValueError):
                self.tx(paid_on=day)
        with self.assertRaises(ValueError):
            self.tx(currency='USD')
        for year in [True, 2025.5, '25', 2023]:
            with self.subTest(year=year), self.assertRaises(ValueError):
                app.valid_year(year)

    def test_source_change_invalidates_confirmed_deadline_and_analysis(self):
        doc_id = self.doc()
        app.save_task(self.task(source_id=doc_id))
        doc = app.state()['documents'][0]
        with app.db() as con:
            app.insert(con, 'analyses', {'id': app.new_id(), 'document_id': doc_id, 'source_hash': app.source_hash(doc),
                       'state': 'complete', 'worker_model': 'test', 'reviewer_model': 'test',
                       'created_at': app.now(), 'updated_at': app.now()})
        app.update_document(doc_id, {**doc, 'received_date': '2026-09-19'})
        self.assertEqual(app.state()['tasks'][0]['due_confirmed'], 0)
        self.assertEqual(app.analyses(doc_id)[0]['state'], 'outdated')
        self.assertNotIn(b'BEGIN:VEVENT', app.ics_bytes(2025))

    def test_task_proof_and_date_checks(self):
        for payload in [self.task(prepare_on='2026-10-16'), self.task(due_on=''), self.task(status='done')]:
            with self.assertRaises(ValueError):
                app.save_task(payload)
        app.save_task(self.task(status='done', proof='Versandprotokoll 15.10.2026'))
        self.assertEqual(app.state()['tasks'][0]['status'], 'done')

    def test_calendar_stable_uid_sequence_and_cancellation(self):
        payload = self.task(title='Änderung; Rückfragen, prüfen ' * 6)
        task_id = app.save_task(payload)['id']
        app.save_task(self.task(title='Unbestätigt', due_confirmed=False))
        first = app.ics_bytes(2025)
        self.assertIn(f'UID:{task_id}-due@cay-steuerstudio.local'.encode(), first)
        self.assertIn(b'DTSTART;VALUE=DATE:20261015', first)
        self.assertIn(b'DTSTART;VALUE=DATE:20261001', first)
        self.assertIn(b'TRIGGER:-P14D', first)
        self.assertNotIn('Unbestätigt'.encode(), first)
        self.assertTrue(all(len(line) <= 75 for line in first.split(b'\r\n')))
        first.decode('utf-8')
        app.save_task({**payload, 'due_on': '2026-10-20'}, task_id)
        self.assertIn(b'SEQUENCE:1', app.ics_bytes(2025))
        app.archive('tasks', task_id)
        cancelled = app.ics_bytes(2025)
        self.assertIn(b'SEQUENCE:2', cancelled)
        self.assertIn(b'STATUS:CANCELLED', cancelled)
        self.assertNotIn(b'BEGIN:VALARM', cancelled)

    def test_backup_restore_database_and_original_bytes(self):
        original = b'Original test receipt'
        doc_id = self.doc(filename='a.txt', file_base64=base64.b64encode(original).decode())
        self.tx(document_ids=[doc_id])
        app.save_task(self.task(source_id=doc_id))
        expected = app.state()
        restored = Path(self.temp.name) / 'restored'
        with zipfile.ZipFile(io.BytesIO(app.backup_bytes())) as z:
            z.extractall(restored)
        app.DATA = restored / 'daten'
        app.initialize()
        actual = app.state()
        for key in ['documents', 'transactions', 'tasks', 'settings']:
            self.assertEqual(actual[key], expected[key])
        self.assertEqual((app.DATA / 'originale' / actual['documents'][0]['stored_name']).read_bytes(), original)
        with app.db() as con:
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_csv_year_filter_decimal_amounts_and_formula_safety(self):
        self.tx(amount='1234,56', partner='=SUM(A1:A2)', title='@command')
        self.tx(paid_on='2026-04-03')
        rows = list(csv.reader(io.StringIO(app.csv_bytes(2025).decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][3:6], ['1234,56', "'=SUM(A1:A2)", "'@command"])

    def test_model_citations_and_invalid_dates(self):
        fake = {'summary': 'Test', 'facts': [{'label': 'A', 'value': 'B', 'quote': 'Bitte Belege'}],
                'deadlines': [{'title': 'Frist', 'date': '2026-99-99', 'quote': 'Erfundenes Zitat'}]}
        with patch.object(app, 'ollama', return_value={'message': {'content': json.dumps(fake)}}) as mock:
            result = app.read_pass('test-local', 'Bitte Belege bis zum 15.10.2026 einreichen.', True)
        self.assertTrue(result['facts'][0]['source_found'])
        self.assertFalse(result['deadlines'][0]['source_found'])
        self.assertEqual(result['deadlines'][0]['date'], '')
        self.assertEqual(mock.call_args.args[1]['options']['num_ctx'], 8192)

    def test_remote_models_excluded(self):
        fake = [{'name': 'local:8b', 'size': 100}, {'name': 'test-cloud', 'size': 100},
                {'name': 'remote', 'size': 100, 'remote_host': 'example.org'}, {'name': 'empty', 'size': 0}]
        with patch.object(app, 'ollama', return_value={'models': fake}):
            self.assertEqual(app.local_models(), ['local:8b'])

    def test_interrupted_analysis_fails_visibly_after_restart(self):
        doc_id = self.doc()
        with app.db() as con:
            app.insert(con, 'analyses', {'id': app.new_id(), 'document_id': doc_id, 'source_hash': 'x',
                       'state': 'running', 'worker_model': 'local', 'reviewer_model': 'local',
                       'created_at': app.now(), 'updated_at': app.now()})
        app.initialize()
        self.assertEqual(app.analyses(doc_id)[0]['state'], 'error')

    def test_private_and_sample_documents_are_not_cash_transactions(self):
        self.doc(kind='Privatunterlage')
        self.doc(kind='PR-Sample')
        self.assertEqual(len(app.state()['documents']), 2)
        self.assertEqual(app.state()['transactions'], [])

    def test_http_flow_security_and_static_assets(self):
        server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(method, path, payload=None, extra=None):
            con = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            headers = {'Content-Type': 'application/json', 'X-Cay-Token': app.TOKEN, **(extra or {})}
            con.request(method, path, body=json.dumps(payload).encode() if payload is not None else None, headers=headers)
            response = con.getresponse()
            result = response.status, dict(response.getheaders()), response.read()
            con.close()
            return result

        try:
            # Every asset referenced by the real entry page must be served, including
            # new feature styles. Otherwise the UI can render with missing styling.
            import re
            entry = request('GET', '/')[2].decode()
            assets = re.findall(r'(?:src|href)="(/[^"#]+)"', entry)
            for path in ['/', *dict.fromkeys(assets)]:
                status, headers, raw = request('GET', path)
                self.assertEqual(status, 200, path)
                if path.endswith('.css'):
                    self.assertIn('text/css', headers['Content-Type'])
                self.assertIn("default-src 'self'", headers['Content-Security-Policy'])
                if path == '/':
                    self.assertNotIn(b'__CAY_TOKEN__', raw)
                    self.assertIn(app.TOKEN.encode(), raw)
            for headers in [{'Origin': 'https://example.org'}, {'Host': 'example.org'}, {'Sec-Fetch-Site': 'cross-site'}]:
                self.assertEqual(request('GET', '/api/state', extra=headers)[0], 403)
            self.assertEqual(request('POST', '/api/settings', {}, {'X-Cay-Token': ''})[0], 403)
            self.assertEqual(request('GET', '/../../app.py')[0], 404)
            status, _, raw = request('POST', '/api/documents', {'title': 'API-Beleg', 'kind': 'Rechnung', 'year': 2025,
                    'filename': 'beleg.txt', 'file_base64': base64.b64encode(b'API original').decode()})
            self.assertEqual(status, 201)
            doc_id = json.loads(raw)['id']
            self.assertEqual(request('POST', '/api/transactions', {'direction': 'expense', 'amount': '29,99',
                        'paid_on': '2025-04-04', 'partner': 'Test', 'title': 'API-Test', 'document_ids': [doc_id]})[0], 201)
            self.assertEqual(request('GET', f'/api/documents/{doc_id}/file')[2], b'API original')
            self.assertEqual(json.loads(request('GET', '/api/state')[2])['transactions'][0]['amount_cents'], 2999)
            self.assertEqual(request('POST', '/api/transactions', {'amount': 'abc'})[0], 400)
            status, _, raw = request('GET', '/api/backup')
            self.assertEqual(status, 200)
            self.assertIn('daten/steuerstudio.sqlite3', zipfile.ZipFile(io.BytesIO(raw)).namelist())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


if __name__ == '__main__':
    unittest.main()
