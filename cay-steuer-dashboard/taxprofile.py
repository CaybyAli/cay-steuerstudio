"""Year-specific tax settings. Never infer a year for legacy VAT fields."""
import hashlib

A = None
CHOICES = {'vat_status': {'unknown', 'small', 'regular'}, 'taxation': {'unknown', 'cash', 'accrual'}, 'filing_status': {'unknown', 'open', 'submitted'}}

def bind(core):
    global A
    A = core

def empty(year):
    return {'year': year, **{k: 'unknown' for k in CHOICES}, 'source_note': '', 'updated_at': ''}

def initialize():
    with A.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS tax_profiles (year INTEGER PRIMARY KEY, vat_status TEXT NOT NULL, taxation TEXT NOT NULL, filing_status TEXT NOT NULL, source_note TEXT NOT NULL, updated_at TEXT NOT NULL)')
        cfg = A.settings(con)
        if cfg.get('filing_2025', 'unknown') != 'unknown':
            row = {**empty(2025), 'filing_status': cfg['filing_2025'], 'source_note': 'Abgabestand aus der bisherigen Einstellung für 2025 übernommen; Nachweise prüfen.', 'updated_at': A.now()}
            con.execute('INSERT OR IGNORE INTO tax_profiles VALUES (:year,:vat_status,:taxation,:filing_status,:source_note,:updated_at)', row)

def all_profiles():
    with A.db() as con:
        return A.rows(con, 'SELECT * FROM tax_profiles ORDER BY year')

def get(year):
    return next((p for p in all_profiles() if p['year'] == year), empty(year))

def save(payload):
    year = A.valid_year(payload.get('year'))
    values = {'year': year}
    for key, choices in CHOICES.items():
        value = payload.get(key, 'unknown')
        if not isinstance(value, str) or value not in choices:
            raise ValueError('Ungültiger Steuerstatus.')
        values[key] = value
    values.update(source_note=A.clean(payload.get('source_note', ''), 2000), updated_at=A.now())
    notes = A.clean(payload.get('personal_notes', ''), 10000) if 'personal_notes' in payload else None
    with A.WRITE_LOCK, A.db() as con:
        old = get(year)
        con.execute('''INSERT INTO tax_profiles VALUES (:year,:vat_status,:taxation,:filing_status,:source_note,:updated_at)
            ON CONFLICT(year) DO UPDATE SET vat_status=excluded.vat_status,taxation=excluded.taxation,
            filing_status=excluded.filing_status,source_note=excluded.source_note,updated_at=excluded.updated_at''', values)
        if notes is not None:
            con.execute('INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('personal_notes', A.enc(notes)))
        if year == 2025:
            con.execute('INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('filing_2025', A.enc(values['filing_status'])))
        A.audit(con, 'update', 'tax_profile', str(year), old, values)
    return {'ok': True}

def proposal(cases):
    for case in cases:
        if case['id'] == 'bescheide-2024-20260924' and not case['source_changed']:
            return {'year': 2024, 'vat_status': 'regular', 'filing_status': 'submitted',
                    'source_note': 'Änderungsbescheide 2024 vom 24.09.2026, Finanzamt Stuttgart III: USt mit steuerpflichtigen Umsätzen und Vorsteuer. Erklärungen eingereicht; ESt-Prüfung und Gewinnerzielungsabsicht weiterhin offen. Ist-/Soll-Versteuerung nicht belegt.'}
    return None

def source(year, notes):
    p = get(year)
    labels = {'unknown': 'Noch zu klären', 'small': 'Kleinunternehmer', 'regular': 'Regelbesteuerung', 'cash': 'Ist-Versteuerung', 'accrual': 'Soll-Versteuerung', 'open': 'Noch offen', 'submitted': 'Abgegeben; inhaltliche Prüfung nicht bestätigt'}
    return {'id': 'P:' + str(year), 'title': f'Steuerprofil {year}', 'kind': 'Gespeicherte Nutzerangaben, keine fachliche Freigabe', 'year': year, 'excerpt': len(notes) > 1500,
            'text': f"Arbeitsjahr: {year}\nUmsatzsteuerstatus: {labels[p['vat_status']]}\nBesteuerungsart: {labels[p['taxation']]}\nErklärungen: {labels[p['filing_status']]}\nHerkunft: {p['source_note'] or 'Nicht angegeben'}\nJahresübergreifende Notizen (zeitliche Zuordnung prüfen): {notes[:1500]}",
            'source_hash': hashlib.sha256(A.enc([p, notes]).encode()).hexdigest()}
