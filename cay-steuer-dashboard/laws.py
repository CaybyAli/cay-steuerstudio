"""Versioned, allowlisted official sources. Downloads contain no user data."""
from __future__ import annotations
import hashlib
import io
import json
import re
import socket
import ssl
import threading
import time
import zipfile
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET

A = None
LOCK = threading.Lock()
STATUS = {'running': False, 'progress': '', 'errors': [], 'finished_at': ''}
HOSTS = {'www.gesetze-im-internet.de', 'www.bundesfinanzministerium.de',
         'finanzamt-bw.fv-bwl.de', 'www.elster.de', 'www.kuppenheim.de'}
# Published XML ZIP endpoints; availability is checked on the user's PC, never fabricated.
CATALOG = [{'id': key, 'title': title, 'url': f'https://www.gesetze-im-internet.de/{path}/xml.zip', 'type': 'xmlzip'} for key, title, path in [
    ('estg', 'Einkommensteuergesetz', 'estg'), ('ustg', 'Umsatzsteuergesetz', 'ustg_1980'),
    ('ao', 'Abgabenordnung', 'ao_1977'), ('gewstg', 'Gewerbesteuergesetz', 'gewstg'),
    ('estdv', 'Einkommensteuer-Durchführungsverordnung', 'estdv_1955'),
    ('ustdv', 'Umsatzsteuer-Durchführungsverordnung', 'ustdv_1980'), ('bafoeg', 'BAföG', 'baf_g')
]]
CATALOG += [
    {'id': 'bw_move', 'title': 'BW: Umzug und Finanzamt', 'type': 'html', 'url': 'https://finanzamt-bw.fv-bwl.de/,Lde/Startseite/Service/Ich%2Bbin%2Bumgezogen_%2BMuss%2Bich%2Bdem%2BFinanzamt%2Bmeine%2BAdressaenderung%2Bmitteilen_'},
    {'id': 'bw_office', 'title': 'Kuppenheim: zuständiges Finanzamt', 'type': 'html', 'url': 'https://www.kuppenheim.de/-/serviceportal-baden-wuerttemberg/einkommensteuer/vbid538'},
    {'id': 'bw_deadlines', 'title': 'BW: Abgabefristen', 'type': 'html', 'url': 'https://finanzamt-bw.fv-bwl.de/,Len/Deadlines'},
    {'id': 'bmf_invoice', 'title': 'BMF: E-Rechnung', 'type': 'html', 'url': 'https://www.bundesfinanzministerium.de/Content/DE/FAQ/e-rechnung.html'},
    {'id': 'elster_move', 'title': 'ELSTER: Änderung der Adresse', 'type': 'html', 'url': 'https://www.elster.de/eportal/formulare-leistungen/alleformulare/aenderungadresse'}
]
SEEDS = [
    ('bw_move', 'Planungshinweis zum Umzug, recherchiert am 27.09.2026', 'Bei einem Wechsel in einen anderen Finanzamtsbezirk ist grundsätzlich das Finanzamt des neuen Wohnorts für die Einkommensteuererklärung zuständig. Es fordert die Akten an. Weil noch Bescheide und Mitteilungen erwartet werden, sollte die neue Anschrift zeitnah mitgeteilt werden. Der konkrete Zuständigkeitswechsel und offene Vorgänge sind zu prüfen.'),
    ('bw_office', 'Zuständigkeit für Kuppenheim, recherchiert am 27.09.2026', 'Die Stadt Kuppenheim nennt für die Einkommensteuer das Finanzamt Rastatt. Das ist die erwartete neue Wohnsitzzuständigkeit. Stuttgart bleibt im Profil als derzeitiges Finanzamt, bis der tatsächliche Umzug und die Übernahme dokumentiert sind. Die genaue bisherige Dienststelle ist noch unbekannt.'),
    ('bw_deadlines', 'Status 2025 dringend klären, recherchiert am 27.09.2026', 'Für eine verpflichtende, nicht durch einen Steuerberater erstellte Jahreserklärung 2025 war die allgemeine Frist der 31.07.2026. Bei einem wirksamen Beratungsfall ist unter Berücksichtigung des Wochenendes regelmäßig der 01.03.2027 relevant. Individuelle Aufforderungen oder Verlängerungen können abweichen. Ob und welche Frist nach einer Mandatskündigung gilt, muss am tatsächlichen Fall geprüft werden. Keine automatische Fristfreigabe.'),
    ('bmf_invoice', 'Originalformat der E-Rechnung, recherchiert am 27.09.2026', 'Eine E-Rechnung benötigt ein strukturiertes elektronisches Format; eine einfache PDF ist nicht schon deshalb eine E-Rechnung. Original-XML und gegebenenfalls eingebettete XML einer ZUGFeRD-Datei sichern. Auch Kleinunternehmer müssen seit 2025 grundsätzlich E-Rechnungen empfangen können. Ausstellungspflichten, Ausnahmen und Übergänge gesondert prüfen. Dieses Steuerstudio validiert noch keine E-Rechnungen.'),
    ('elster_move', 'Adressmitteilung', 'Mein ELSTER bietet das Formular Änderung der Adresse. Die geplante Anschrift wird im Steuerstudio zunächst gespeichert; es erfolgt keine automatische Mitteilung an das Finanzamt. Nach tatsächlicher Änderung selbst übermitteln und das Protokoll ablegen.')
]
for _source in CATALOG:
    _source['web_url'] = _source['url'].removesuffix('xml.zip') if _source['type'] == 'xmlzip' else _source['url']


def bind(core):
    global A
    A = core


def initialize():
    with A.db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS legal_versions (
          id TEXT PRIMARY KEY, source_id TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
          retrieved_at TEXT NOT NULL, sha256 TEXT NOT NULL, raw BLOB NOT NULL,
          source_type TEXT NOT NULL, valid_from INTEGER, valid_to INTEGER,
          review_note TEXT NOT NULL DEFAULT '', reviewed INTEGER NOT NULL DEFAULT 0,
          UNIQUE(source_id,sha256));
        CREATE TABLE IF NOT EXISTS legal_units (
          id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES legal_versions(id),
          title TEXT NOT NULL, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS legal_checks (source_id TEXT PRIMARY KEY, checked_at TEXT NOT NULL, error TEXT NOT NULL DEFAULT '');
        ''')
        columns = {r[1] for r in con.execute('PRAGMA table_info(legal_checks)')}
        if 'attempted_at' not in columns:
            con.execute("ALTER TABLE legal_checks ADD COLUMN attempted_at TEXT NOT NULL DEFAULT ''")
        for source_id, title, body in SEEDS:
            ver = 'seed_' + source_id + '_20260927'
            source = next(x for x in CATALOG if x['id'] == source_id)
            con.execute('INSERT OR IGNORE INTO legal_versions (id,source_id,title,url,retrieved_at,sha256,raw,source_type,review_note) VALUES (?,?,?,?,?,?,?,?,?)',
                        (ver, source_id, source['title'], source['url'], '2026-09-27', hashlib.sha256(body.encode()).hexdigest(), body.encode(), 'redaktioneller Hinweis', 'Zusammenfassung ausgewählter amtlicher Hinweise, kein vollständiger Originaltext und keine individuelle steuerliche Freigabe.'))
            con.execute('INSERT OR IGNORE INTO legal_units VALUES (?,?,?,?)', (ver, ver, title, body))


def allowed(url):
    p = urlparse(url)
    return p.scheme == 'https' and p.hostname in HOSTS and p.port in {None, 443} and not p.username and not p.password


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError('Weiterleitung außerhalb der amtlichen Quellenliste abgelehnt.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript', 'svg'}:
            self.depth += 1
        elif not self.depth and tag in {'p', 'h1', 'h2', 'h3', 'li', 'div', 'br'}:
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript', 'svg'} and self.depth:
            self.depth -= 1
    def handle_data(self, data):
        if not self.depth:
            self.parts.append(data)


def parse_source(source, raw):
    if source['type'] == 'xmlzip':
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            files = [i for i in z.infolist() if i.filename.lower().endswith('.xml')]
            if len(files) != 1 or files[0].file_size > 30 * 1024**2:
                raise ValueError('Unerwartetes XML-Archiv.')
            xml = z.read(files[0])
        if b'<!ENTITY' in xml.upper():
            raise ValueError('XML mit externen Definitionen wird nicht verarbeitet.')
        root = ET.fromstring(xml)
        units = []
        for norm in root.findall('.//norm'):
            meta = norm.find('metadaten')
            title = ' '.join(''.join(meta.itertext()).split()) if meta is not None else source['title']
            body = '\n'.join(' '.join(''.join(p.itertext()).split()) for p in norm.findall('.//textdaten//P'))
            if not body:
                body = ' '.join(''.join(norm.itertext()).split())
            if body:
                units.append((title[:600], body))
        if not units:
            raise ValueError('Keine Normen erkannt. Quelle wird nicht als gelesen markiert.')
        return units
    parser = TextParser()
    parser.feed(raw.decode('utf-8', errors='replace'))
    body = re.sub(r'\n\s*\n+', '\n\n', ''.join(parser.parts)).strip()
    if len(body) < 200:
        raise ValueError('Kein ausreichender Quellentext erkannt.')
    return [(source['title'], body)]


def download(source):
    if not allowed(source['url']):
        raise ValueError('Quelle nicht erlaubt.')
    opener = build_opener(ProxyHandler({}), SafeRedirect())
    req = Request(source['url'], headers={'User-Agent': 'CaySteuerstudio/0.2.1 (official-source archive)'})
    with opener.open(req, timeout=25) as response:
        raw = response.read(15 * 1024**2 + 1)
    if len(raw) > 15 * 1024**2:
        raise ValueError('Quelle überschreitet 15 MB.')
    return raw


def retryable(error):
    if isinstance(error, HTTPError):
        return error.code in {408, 429, 500, 502, 503, 504}
    reason = getattr(error, 'reason', error)
    return not isinstance(reason, ssl.SSLError) and isinstance(reason, (TimeoutError, socket.gaierror, ConnectionError))


def error_reason(error):
    if isinstance(error, HTTPError):
        if error.code == 404: return 'Die amtliche Adresse wurde nicht gefunden (HTTP 404).'
        if error.code in {401, 403}: return f'Die amtliche Seite hat den automatischen Abruf abgelehnt (HTTP {error.code}).'
        if error.code == 429: return 'Die amtliche Seite begrenzt die Abrufe (HTTP 429). Später erneut versuchen.'
        return f'Die amtliche Seite meldet HTTP {error.code}. Später erneut versuchen.'
    reason = getattr(error, 'reason', error)
    if isinstance(reason, ssl.SSLError): return 'Die sichere Verbindung konnte nicht geprüft werden. Windows-Uhrzeit und Zertifikate prüfen.'
    if isinstance(reason, (TimeoutError, socket.timeout)): return 'Die amtliche Seite hat nicht rechtzeitig geantwortet. Erneut versuchen.'
    if isinstance(reason, socket.gaierror): return 'Die Internetadresse konnte nicht aufgelöst werden. Internetverbindung prüfen.'
    if isinstance(error, (zipfile.BadZipFile, ET.ParseError, UnicodeError)): return 'Die Antwort enthält keine lesbare Gesetzesdatei. Webseite öffnen und später erneut versuchen.'
    if isinstance(error, ValueError): return str(error)[:300]
    if isinstance(reason, OSError): return 'Verbindung oder lokale Speicherung fehlgeschlagen. Verbindung und freien Speicher prüfen.'
    return 'Die Quelle konnte nicht verarbeitet werden. Webseite öffnen und später erneut versuchen.'


def fetch_one(source):
    for attempt in range(2):
        try:
            raw = download(source)
            break
        except Exception as error:
            if attempt or not retryable(error): raise
            time.sleep(.5)
    units = parse_source(source, raw)
    digest = hashlib.sha256(raw).hexdigest()
    with A.WRITE_LOCK, A.db() as con:
        previous = con.execute('SELECT id FROM legal_versions WHERE source_id=? AND sha256=?', (source['id'], digest)).fetchone()
        if not previous:
            vid = A.new_id()
            A.insert(con, 'legal_versions', {'id': vid, 'source_id': source['id'], 'title': source['title'], 'url': source['url'], 'retrieved_at': A.now(), 'sha256': digest, 'raw': raw, 'source_type': source['type']})
            for title, body in units:
                A.insert(con, 'legal_units', {'id': A.new_id(), 'version_id': vid, 'title': title, 'body': body})
            A.audit(con, 'download', 'legal_version', vid, after={'source_id': source['id'], 'sha256': digest})
        con.execute('INSERT INTO legal_checks (source_id,checked_at,error,attempted_at) VALUES (?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET checked_at=excluded.checked_at,error=excluded.error,attempted_at=excluded.attempted_at', (source['id'], A.now(), '', A.now()))


def start_update(source_ids=None):
    selected = CATALOG
    if source_ids is not None:
        if not isinstance(source_ids, list) or not source_ids or any(not isinstance(x,str) for x in source_ids) or set(source_ids) - {s['id'] for s in CATALOG}:
            raise ValueError('Bitte mindestens eine bekannte amtliche Quelle auswählen.')
        selected = [s for s in CATALOG if s['id'] in source_ids]
    if not LOCK.acquire(False):
        return dict(STATUS)
    STATUS.update(running=True, progress='Startet …', errors=[], finished_at='')
    def run():
        try:
            for i, source in enumerate(selected):
                STATUS['progress'] = f"{i+1}/{len(selected)} · {source['title']}"
                try:
                    fetch_one(source)
                except Exception as error:
                    message = source['title'] + ': ' + error_reason(error) + ' Vorhandene Fassungen bleiben erhalten.'
                    STATUS['errors'].append(message)
                    with A.WRITE_LOCK, A.db() as con:
                        con.execute('INSERT INTO legal_checks (source_id,checked_at,error,attempted_at) VALUES (?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET error=excluded.error,attempted_at=excluded.attempted_at', (source['id'], '', message, A.now()))
        finally:
            STATUS.update(running=False, finished_at=A.now(), progress='Abruf beendet. Gespeicherte Texte stehen der KI zur Verfügung.')
            LOCK.release()
    threading.Thread(target=run, daemon=True).start()
    return dict(STATUS)


def overview():
    with A.db() as con:
        versions = A.rows(con, 'SELECT id,source_id,title,url,retrieved_at,sha256,source_type,valid_from,valid_to,review_note,reviewed,(SELECT count(*) FROM legal_units u WHERE u.version_id=v.id) AS units FROM legal_versions v ORDER BY retrieved_at DESC')
        checks = A.rows(con, 'SELECT * FROM legal_checks')
    downloaded = {v['source_id'] for v in versions if v['source_type'] != 'redaktioneller Hinweis'}
    return {'versions': versions, 'catalog': CATALOG, 'status': dict(STATUS), 'checks': checks,
            'downloaded_count': len(downloaded), 'failed_count': sum(bool(c['error']) for c in checks)}


def review(payload):
    vid = A.clean(payload.get('id'), 80)
    start = A.valid_year(payload.get('valid_from'))
    end = A.valid_year(payload.get('valid_to'))
    note = A.clean(payload.get('review_note'), 3000)
    if end < start or len(note) < 10:
        raise ValueError('Bitte gültigen Zeitraum und eine nachvollziehbare Fundstelle zur Anwendbarkeit angeben.')
    with A.WRITE_LOCK, A.db() as con:
        old = con.execute('SELECT id FROM legal_versions WHERE id=?', (vid,)).fetchone()
        if not old:
            raise ValueError('Fassung nicht gefunden.')
        con.execute('UPDATE legal_versions SET valid_from=?,valid_to=?,review_note=?,reviewed=1 WHERE id=?', (start, end, note, vid))
        A.audit(con, 'review', 'legal_version', vid, after={'from': start, 'to': end, 'note': note})
    return {'ok': True}


def search(query, year, limit=5):
    from retrieval import terms as query_terms, relevance
    terms = query_terms(query)
    synonyms = {'kleinunternehmer': ['umsatzsteuer', '§ 19'], 'sample': ['sach', 'einnahmen'], 'umzug': ['adress', 'wohnort'], 'kuppenheim': ['rastatt'], 'frist': ['abgabe', 'deadline'], 'eür': ['gewinn', '§ 4']}
    for term, extra in synonyms.items():
        if term in query.casefold():
            terms.update(extra)
    with A.db() as con:
        items = A.rows(con, 'SELECT u.id,u.title,u.body,v.url,v.retrieved_at,v.reviewed,v.valid_from,v.valid_to,v.review_note,v.source_type,v.source_id FROM legal_units u JOIN legal_versions v ON v.id=u.version_id')
    def score(x):
        text = (x['title'] + ' ' + x['body']).casefold()
        return relevance(terms, text)
    eligible = [x for x in items if not x['reviewed'] or x['valid_from'] <= year <= x['valid_to']]
    chosen = sorted(((score(x), x) for x in eligible), key=lambda pair: (pair[0], bool(pair[1]['reviewed']), pair[1]['retrieved_at']), reverse=True)
    out = []
    for s, x in chosen:
        if len(out) >= limit:
            break
        if s <= 0:
            continue
        text = x['body']
        positions = [text.casefold().find(t) for t in terms if t in text.casefold()]
        pos = max(0, min(positions, default=0) - 250)
        excerpt = text[pos:pos+1500]
        out.append({**x, 'body': excerpt, 'excerpt': len(text) > len(excerpt), 'year_checked': bool(x['reviewed'] and x['valid_from'] <= year <= x['valid_to'])})
    return out
