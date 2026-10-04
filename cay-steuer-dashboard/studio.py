"""Application services for the creator/private workspace."""
from __future__ import annotations
import json
import re
import threading
from pathlib import Path
import intelligence
import laws
import storage
import banking
import assessments
import taxprofile
import intake
import recycle
import euer
import euer_ai

A = None


def bind(core):
    global A
    A = core
    for module in [storage, intelligence, laws, banking, assessments, taxprofile, intake, recycle, euer, euer_ai]:
        module.bind(core)


def initialize():
    storage.initialize()
    intelligence.initialize()
    laws.initialize()
    assessments.initialize()
    taxprofile.initialize()
    with A.db() as con:
        cols = {r[1] for r in con.execute('PRAGMA table_info(transactions)')}
        additions = {'scope': "TEXT NOT NULL DEFAULT 'business'", 'business_percent': 'INTEGER',
                     'tax_note': "TEXT NOT NULL DEFAULT ''", 'vat_treatment': "TEXT NOT NULL DEFAULT 'unknown'",
                     # Payment evidence is separate from the tax/accounting scope.  This lets a
                     # cash purchase remain a business item without inventing a bank transaction.
                     'payment_method': "TEXT NOT NULL DEFAULT 'unknown'",
                     'cash_source': "TEXT NOT NULL DEFAULT ''",
                     'expense_kind': "TEXT NOT NULL DEFAULT 'standard'",
                     'business_purpose': "TEXT NOT NULL DEFAULT ''",
                     'meal_place': "TEXT NOT NULL DEFAULT ''",
                     'meal_participants': "TEXT NOT NULL DEFAULT ''",
                     'meal_occasion': "TEXT NOT NULL DEFAULT ''"}
        for name, typ in additions.items():
            if name not in cols:
                con.execute(f'ALTER TABLE transactions ADD COLUMN {name} {typ}')
    banking.initialize()
    intake.initialize()
    recycle.initialize()
    euer.initialize()
    euer_ai.initialize()


def extra_state():
    notices = assessments.status()
    return {'storage': storage.status(), 'facts': intelligence.facts(), 'drafts': [{'key':d['key'], 'updated_at':d['updated_at'], 'title':d['payload'].get('title') or d['payload'].get('question') or d['payload'].get('__form',d['key'])} for d in storage.get_drafts()],
            'bank_accounts': banking.accounts(), 'legal_status': dict(laws.STATUS), 'assessments':notices,
            'tax_profiles': taxprofile.all_profiles(), 'tax_profile_proposal': taxprofile.proposal(notices['cases'])}


def settings_values(payload):
    out = {}
    for key, limit in {'coordinator_model':200, 'backup_directory':1000, 'current_office':200,
                       'current_address':500, 'future_address':500, 'future_office':200,
                       'tax_number_current':100, 'tax_number_future':100}.items():
        if key in payload:
            out[key] = A.clean(payload[key], limit)
    if out.get('backup_directory'):
        p = Path(out['backup_directory']).expanduser()
        if not p.is_absolute() or not p.is_dir():
            raise ValueError('Bitte einen existierenden absoluten Sicherungsordner wählen, etwa E:\\Steuer-Sicherungen.')
        data = A.DATA.resolve()
        if p.resolve() == data or data in p.resolve().parents:
            raise ValueError('Die zusätzliche Sicherung muss außerhalb des Datenordners liegen.')
    for key in ['auto_legal_update', 'move_confirmed']:
        if key in payload:
            if not isinstance(payload[key], bool):
                raise ValueError('Ungültiger Schalter.')
            out[key] = payload[key]
    if 'move_on' in payload:
        out['move_on'] = A.valid_date(payload['move_on'])
    if payload.get('move_confirmed') and not payload.get('move_on'):
        raise ValueError('Bitte für einen bestätigten Umzug das tatsächliche Datum angeben.')
    if 'num_ctx' in payload:
        if str(payload['num_ctx']) not in {'8192','12288','16384'}:
            raise ValueError('Kontextgröße muss 8192, 12288 oder 16384 sein.')
        out['num_ctx'] = int(payload['num_ctx'])
    return out


def tx_values(payload):
    scope = payload.get('scope', 'business')
    if scope not in {'business', 'private', 'mixed', 'unknown', 'transfer'}:
        raise ValueError('Ungültiger Bereich.')
    percent = payload.get('business_percent')
    if percent in {'', None}:
        percent = None
    elif str(percent).isdigit() and 0 <= int(percent) <= 100:
        percent = int(percent)
    else:
        raise ValueError('Betrieblicher Anteil muss eine ganze Prozentzahl von 0 bis 100 sein.')
    if scope == 'private':
        percent = 0
    treatment = payload.get('vat_treatment', 'unknown')
    if treatment not in {'unknown', 'domestic', 'small', 'reverse_charge', 'foreign', 'none'}:
        raise ValueError('Ungültige Umsatzsteuereinordnung.')
    method = payload.get('payment_method') or ('bank' if payload.get('account_id') else 'unknown')
    # Older forms and the account selector may submit the visible default
    # "unknown" together with a bank account. The account is stronger evidence.
    if method == 'unknown' and payload.get('account_id'):
        method = 'bank'
    if method not in {'bank', 'cash', 'unknown'}:
        raise ValueError('Ungültige Zahlungsart.')
    cash_source = payload.get('cash_source', '') or ''
    if cash_source not in {'', 'private_wallet', 'business_cash', 'unknown'}:
        raise ValueError('Ungültige Bargeldquelle.')
    if method != 'cash' and cash_source == 'unknown':
        # Hidden cash fields on an older or bank form are harmless defaults.
        cash_source = ''
    expense_kind = payload.get('expense_kind', 'standard') or 'standard'
    if expense_kind not in {'standard', 'video_purchase', 'business_meal', 'other'}:
        raise ValueError('Ungültiger Ausgabentyp.')
    if expense_kind == 'business_meal' and payload.get('direction', 'expense') != 'expense':
        raise ValueError('Ein Geschäftsessen kann nur als Ausgabe erfasst werden.')
    if method == 'cash':
        if payload.get('account_id') or payload.get('bank_row_id'):
            raise ValueError('Barausgaben dürfen keinem Bankkonto oder Bankimport zugeordnet werden.')
        if cash_source == '':
            cash_source = 'unknown'
    elif method == 'bank':
        if not payload.get('account_id'):
            # A manually entered bank payment needs an account so it can later be
            # reconciled with the CSV. Imported records always provide one.
            raise ValueError('Für eine Bankzahlung bitte das Konto auswählen.')
        if cash_source:
            raise ValueError('Eine Bankzahlung kann keine Bargeldquelle haben.')
    else:
        if cash_source or payload.get('account_id') or payload.get('bank_row_id'):
            raise ValueError('Bei unbekannter Zahlungsart bitte Konto und Bargeldquelle leer lassen.')
    values = {
        'scope': scope, 'business_percent': percent,
        'tax_note': A.clean(payload.get('tax_note',''), 3000),
        'vat_treatment': treatment, 'payment_method': method,
        'cash_source': cash_source, 'expense_kind': expense_kind,
        'business_purpose': A.clean(payload.get('business_purpose',''), 2000),
        'meal_place': A.clean(payload.get('meal_place',''), 300),
        'meal_participants': A.clean(payload.get('meal_participants',''), 2000),
        'meal_occasion': A.clean(payload.get('meal_occasion',''), 1000),
    }
    if payload.get('data_checked') is True and expense_kind == 'business_meal':
        missing = [label for label, value in [('Ort', values['meal_place']), ('Teilnehmer', values['meal_participants']), ('Anlass', values['meal_occasion'])] if not value]
        if missing:
            raise ValueError('Geschäftsessen noch nicht vollständig: ' + ', '.join(missing) + ' eintragen oder Angabenprüfung abwählen.')
    if payload.get('data_checked') is True and expense_kind == 'video_purchase' and not values['business_purpose']:
        raise ValueError('Für einen Videoeinkauf bitte den konkreten Einsatz im Video angeben oder Angabenprüfung abwählen.')
    return {**values, **banking.transaction_values(payload, method=method), **intake.receipt_values(payload)}


def suggestions():
    with A.db() as con:
        cfg = A.settings(con)
    specs = [
        ('filing25', 2025, 'Abgabestand und Frist für 2025 jetzt klären', 'Vorhandene ELSTER-Protokolle, Beauftragung und Finanzamtsschreiben prüfen. Die allgemeine Frist für Pflichtfälle ohne Berater war 31.07.2026. Individuelle Frist und Folgen der Mandatskündigung bestätigen lassen. Nicht auf weitere Softwarefunktionen warten.'),
        ('vat', 2025, 'Umsatzsteuerstatus und Voranmeldungen belegen', 'Letzte Umsatzsteuervoranmeldung, Übermittlungsprotokoll, Jahreserklärung und ggf. Verzicht auf Kleinunternehmerregelung sichern. Quartalserstattungen allein reichen zur Einordnung nicht.'),
        ('carry', 2025, 'Fortgeführte Werte aus 2024 übernehmen', 'Vorhandene EÜR, Anlagenverzeichnis/AfA und offene Bescheide oder Einsprüche sichern. Alte Anschaffungen nicht erneut als Zahlung erfassen. Keine aufwendige Neuaufbereitung beim früheren Berater verlangen.'),
        ('bank', 2025, 'Konto und Plattformabrechnungen für 2025 abgleichen', 'Kontoauszüge, PayPal und Plattformabrechnungen sammeln. Monat für Monat tatsächliche Zahlungen erfassen, Belege zuordnen; Eigenüberträge getrennt halten. Bruttoerlöse, Plattformgebühren und Fremdwährung gesondert belegen.'),
        ('private', 2025, 'Private Unterlagen für 2025 sammeln', 'Lohnsteuerbescheinigungen, Kranken-/Pflegeversicherung, Studienunterlagen und ggf. BAföG-Bewilligungszeitraum sammeln. Die heutige Lebenssituation nicht ungeprüft auf frühere Jahre übertragen.'),
        ('samples', 2025, 'PR-Samples und Partnerschaften vollständig dokumentieren', 'Verträge, Produkte, Erhalt, nachvollziehbare Werte, Verwendung, Rückgabe und etwaige §37b-Bestätigung festhalten. Sachleistungen nicht als erfundene Bankzahlung eintragen. Steuerliche Würdigung bleibt zu prüfen.'),
        ('backup', 2026, 'Sicherung auf zweitem Datenträger testen', 'Einen geschützten Ordner auf einem anderen physischen Datenträger auswählen. Sicherung erstellen, Wiederherstellung prüfen und einen Probelauf nach Neustart durchführen.'),
        ('move', 2026, 'Umzug Stuttgart → Kuppenheim vorbereiten', 'Datum und neue Anschrift festhalten. Bei tatsächlicher Änderung über Mein ELSTER Änderung der Adresse mitteilen und Protokoll sichern. Alte/neue Steuernummer getrennt dokumentieren. Erwartetes Wohnsitzfinanzamt: Rastatt. Offene Bescheide und Einspruch im Blick behalten; Gewerbestandortänderung bei der Gemeinde gesondert klären.')
    ]
    with A.db() as con:
        existing = {r['entity_id'] for r in con.execute("SELECT entity_id FROM audit WHERE entity='starter_task'")}
    if cfg.get('filing_2025') == 'submitted':
        specs = [s for s in specs if s[0] != 'filing25']
    return [{'key': key, 'year': year, 'title': title, 'notes': note} for key,year,title,note in specs if key not in existing]


def add_suggestions():
    count = 0
    with A.WRITE_LOCK, A.db() as con:
        for item in suggestions():
            r = A.save_task({'title': item['title'], 'kind':'Unterlagen', 'year':item['year'], 'notes':item['notes'], 'due_confirmed':False, 'source_quote':'Startplan für Creator und private Unterlagen. Keine individuell bestätigte gesetzliche Frist.'})
            A.audit(con, 'create', 'starter_task', item['key'], after={'task_id':r['id']})
            count += 1
    return {'count': count}


def background():
    storage.background()
    def loop():
        last = ''
        while not storage.STOP.is_set():
            with A.db() as con:
                cfg = A.settings(con)
            day = A.date.today().isoformat()
            if cfg.get('auto_legal_update') and last != day:
                laws.start_update()
                last = day
            storage.STOP.wait(60)
    threading.Thread(target=loop, daemon=True).start()


def get_route(path, query):
    if path == "/api/euer":return euer.report(A.valid_year(query.get("year",["2025"])[0]))
    if path == "/api/euer/runs":return euer_ai.list_runs(A.valid_year(query.get("year",["2025"])[0]))
    if path == '/api/intake':
        return {'jobs':intake.jobs(A.valid_year(query.get('year',['2025'])[0])), 'capabilities':intake.capabilities(), 'trash':recycle.items(A.valid_year(query.get('year',['2025'])[0]))}
    if path == '/api/intake/job':
        return intake.job(query.get('id',[''])[0])
    if path == '/api/banking/preview':
        return banking.saved_preview(query.get('id',[''])[0])
    if path == '/api/banking':
        return banking.status(A.valid_year(query.get('year',['2025'])[0]))
    if path == '/api/drafts':
        return storage.get_drafts()
    if path == '/api/chat':
        return intelligence.chat_list(A.valid_year(query.get('year',['2025'])[0]))
    if path == '/api/chat/report':
        return intelligence.annual_report(query.get('id',[''])[0])
    if path == '/api/legal':
        return laws.overview()
    if path == '/api/legal/search':
        return laws.search(query.get('q',[''])[0], A.valid_year(query.get('year',['2025'])[0]), 10)
    if path == '/api/suggestions':
        return suggestions()
    if path == '/api/storage':
        return storage.status()
    return None


def post_route(path, payload):
    if path == "/api/euer/allocation":return storage.cached_mutation(path,payload,lambda:euer.save_allocation(payload))
    if path == "/api/euer/entry":return storage.cached_mutation(path,payload,lambda:euer.save_entry(payload))
    if path == "/api/euer/review":return storage.cached_mutation(path,payload,lambda:euer.save_review(payload))
    if path == "/api/euer/start":return euer_ai.start(payload)
    if path == "/api/euer/resume":return euer_ai.resume(payload)
    if path == '/api/trash/preview':return recycle.preview(payload)
    if path == '/api/trash/remove':return recycle.remove(payload)
    if path == '/api/trash/restore':return recycle.restore(payload)
    if path == '/api/intake/upload':
        return intake.upload(payload)
    if path == '/api/intake/start':
        return intake.start(payload)
    if path == '/api/intake/pdf-reconcile':return intake.pdf_review.check(payload)
    if path == '/api/intake/pdf-explain':return intake.pdf_review.explain(payload)
    if path == '/api/intake/pdf-check':return intake.check_pdf_review(payload)
    if path == '/api/intake/pdf-approve':return intake.approve_pdf(payload)
    if path == '/api/intake/pdf-reopen':return intake.reopen_pdf(payload)
    if path == '/api/intake/pdf-review':
        return intake.save_pdf_review(payload)
    if path == '/api/banking/review':
        return banking.save_preview(payload)
    if path == '/api/evidence':
        return intake.save_evidence(payload)
    if path == '/api/tax-profile':
        return taxprofile.save(payload)
    if path == '/api/assessments/import':
        return assessments.import_bundle()
    if path == '/api/banking/accounts':
        return banking.save_account(payload)
    if path == '/api/banking/preview':
        return banking.preview(payload)
    if path == '/api/banking/commit':
        return banking.commit(payload)
    if path == '/api/banking/transfer':
        return banking.confirm_pair(payload)
    if path == '/api/drafts':
        return storage.save_draft(payload)
    if path == '/api/chat':
        return intelligence.start_chat(payload)
    if path == '/api/chat/resume':
        return intelligence.resume_chat(payload)
    if path == '/api/facts':
        return intelligence.save_fact(payload)
    if path == '/api/legal/update':
        return laws.start_update(payload.get('source_ids'))
    if path == '/api/legal/review':
        return laws.review(payload)
    if path == '/api/suggestions/add':
        return add_suggestions()
    if path == '/api/snapshot':
        threading.Thread(target=storage.snapshot, daemon=True).start()
        return {'started':True}
    if path == '/api/restore/check':
        raw = A.base64.b64decode(payload.get('file_base64',''), validate=True)
        return storage.verify_zip(raw)
    return None
