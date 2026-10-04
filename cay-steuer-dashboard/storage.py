"""Durable local storage, autosaved drafts and verified snapshots. No cloud writes."""
from __future__ import annotations
import hashlib
import io
import json
import os
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile
from pathlib import Path

A = None
BACKUP_LOCK = threading.Lock()
BACKUP_STATUS = {'state': 'idle', 'at': '', 'external_at': '', 'error': ''}
STOP = threading.Event()
INSTANCE_HANDLE = None


def bind(core):
    global A
    A = core


def base_dir():
    base = os.environ.get('LOCALAPPDATA') if os.name == 'nt' else os.environ.get('XDG_DATA_HOME')
    return Path(base or (Path.home() / '.local' / 'share')) / 'CaySteuerstudio'


def default_dir():
    config = base_dir() / 'aktive-ablage.json'
    if config.exists():
        value = json.loads(config.read_text(encoding='utf-8'))
        path = Path(value['path'])
        if not path.is_absolute():
            raise ValueError('Die gewählte Datenablage ist nicht verfügbar. Bitte den Datenträger und aktive-ablage.json prüfen. Es wird keine leere Datenbank angelegt.')
        return path
    return base_dir() / 'data'


def atomic_write(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('xb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
        if os.name != 'nt':
            fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    finally:
        temp.unlink(missing_ok=True)


def lock_instance(path):
    global INSTANCE_HANDLE
    path.mkdir(parents=True, exist_ok=True)
    handle = (path / '.instance.lock').open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            handle.write(b'0')
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise ValueError('Diese Datenablage ist bereits geöffnet. Bitte das vorhandene Steuerstudio verwenden.')
    INSTANCE_HANDLE = handle


def initialize():
    marker = A.DATA / 'ablage.json'
    with A.db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS drafts (
          key TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS requests (
          request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, response TEXT NOT NULL);
        ''')
        defaults = {'backup_directory': '', 'last_snapshot': '', 'external_snapshot': '',
                    'auto_legal_update': False, 'coordinator_model': 'gpt-oss:20b',
                    'num_ctx': 8192, 'current_office': 'Stuttgart – genaue Bezeichnung offen',
                    'current_address': '', 'future_address': '76456 Kuppenheim', 'move_on': '',
                    'future_office': 'Finanzamt Rastatt', 'move_confirmed': False,
                    'tax_number_current': '', 'tax_number_future': '', 'profile_scope': 'YouTube/Twitch und privat',
                    'schema_version': 2}
        for k, v in defaults.items():
            con.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (k, A.enc(v)))
        con.execute('UPDATE settings SET value=? WHERE key=?', ('2', 'schema_version'))
        for key, model in [('worker_model', 'qwen3.8:27b'), ('reviewer_model', 'gemma4:31b')]:
            con.execute('UPDATE settings SET value=? WHERE key=? AND value=?', (A.enc(model), key, '""'))
        columns = {r[1] for r in con.execute('PRAGMA table_info(analyses)')}
        for name, default in [('coordinator_model', "''"), ('coordinator_json', 'NULL'), ('progress', "''")]:
            if name not in columns:
                con.execute(f'ALTER TABLE analyses ADD COLUMN {name} TEXT DEFAULT {default}')
    if not marker.exists():
        atomic_write(marker, A.enc({'created_at': A.now(), 'workspace_id': A.new_id()}).encode())


def guard_existing():
    config = base_dir() / 'aktive-ablage.json'
    if config.exists() and Path(json.loads(config.read_text(encoding='utf-8'))['path']).resolve() == A.DATA.resolve() and not (A.DATA / 'steuerstudio.sqlite3').exists():
        raise ValueError('Die gewählte Datenbank fehlt. Bitte Datenträger prüfen oder WIEDERHERSTELLEN_WINDOWS.bat verwenden.')
    if (A.DATA / 'ablage.json').exists() and not (A.DATA / 'steuerstudio.sqlite3').exists():
        raise ValueError('Die bekannte Datenbank fehlt. Es wird keine leere Ablage erzeugt. Bitte Sicherung wiederherstellen oder den Datenpfad prüfen.')


def get_drafts():
    with A.db() as con:
        return [{'key': r['key'], 'payload': json.loads(r['payload']), 'updated_at': r['updated_at']}
                for r in con.execute('SELECT * FROM drafts ORDER BY updated_at DESC')]


def save_draft(payload):
    key = A.clean(payload.get('key'), 160)
    if not key or not isinstance(payload.get('payload'), dict):
        raise ValueError('Ungültiger Entwurf.')
    body = A.enc(payload['payload'])
    if len(body.encode()) > A.MAX_BODY:
        raise ValueError('Entwurf zu groß.')
    at = A.now()
    with A.WRITE_LOCK, A.db() as con:
        if payload.get('delete') is True:
            con.execute('DELETE FROM drafts WHERE key=?', (key,))
        else:
            con.execute('INSERT INTO drafts VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at', (key, body, at))
    with A.db() as con:
        row = con.execute('SELECT payload FROM drafts WHERE key=?', (key,)).fetchone()
        if not payload.get('delete') and (not row or row[0] != body):
            raise ValueError('Entwurf konnte nicht zurückgelesen werden.')
    return {'saved_at': at}


def cached_mutation(path, payload, operation):
    """Transaction insert and retry token commit atomically, including nested core writes."""
    rid = payload.get('request_id')
    if not rid:
        return operation()
    if not isinstance(rid, str) or not A.re.fullmatch(r'[a-zA-Z0-9_-]{16,80}', rid):
        raise ValueError('Ungültige Vorgangskennung.')
    fingerprint = hashlib.sha256((path + A.enc(payload)).encode()).hexdigest()
    with A.WRITE_LOCK, A.db() as con:
        previous = con.execute('SELECT * FROM requests WHERE request_id=?', (rid,)).fetchone()
        if previous:
            if previous['fingerprint'] != fingerprint:
                raise ValueError('Der Vorgang wurde inzwischen geändert. Bitte neu öffnen und erneut speichern.')
            return json.loads(previous['response'])
        result = operation()
        con.execute('INSERT INTO requests VALUES (?,?,?)', (rid, fingerprint, A.enc(result)))
    return result


def verify_zip(raw, destination=None):
    """Never extract paths supplied by an archive; verify DB and every original hash."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or len(names) > 40000 or sum(i.file_size for i in infos) > 4 * 1024**3:
            raise ValueError('Ungültige oder zu große Sicherung.')
        allowed = []
        for i in infos:
            parts = i.filename.split('/')
            if '\\' in i.filename or i.filename.startswith('/') or any(p in {'..', ''} for p in parts):
                raise ValueError('Unsichere Pfade in der Sicherung.')
            if i.filename == 'daten/steuerstudio.sqlite3' or (len(parts) == 3 and parts[:2] == ['daten', 'originale']):
                allowed.append(i.filename)
        if 'daten/steuerstudio.sqlite3' not in allowed:
            raise ValueError('Keine Steuerstudio-Datenbank gefunden.')
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            dbfile = Path(temp) / 'check.sqlite3'
            dbfile.write_bytes(z.read('daten/steuerstudio.sqlite3'))
            con = sqlite3.connect(dbfile)
            try:
                if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or con.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('Die Datenbankprüfung ist fehlgeschlagen.')
                originals = con.execute("SELECT stored_name,sha256 FROM documents WHERE stored_name<>''").fetchall()
                for name, expected in originals:
                    if Path(name).name != name or '\\' in name:
                        raise ValueError('Ungültiger Originalpfad.')
                    arc = 'daten/originale/' + name
                    if arc not in allowed or hashlib.sha256(z.read(arc)).hexdigest() != expected:
                        raise ValueError('Original fehlt oder Prüfsumme stimmt nicht: ' + name)
                if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='bank_imports'").fetchone():
                    for original, expected in con.execute('SELECT original,sha256 FROM bank_imports'):
                        if hashlib.sha256(original).hexdigest() != expected:
                            raise ValueError('Prüfsumme einer Original-CSV stimmt nicht.')
                counts = {t: con.execute('SELECT count(*) FROM ' + t).fetchone()[0] for t in ['documents', 'transactions', 'tasks']}
            finally:
                con.close()
            if destination:
                dest = Path(destination)
                if dest.exists():
                    raise ValueError('Zielordner existiert bereits. Wiederherstellung überschreibt keine Daten.')
                dest.mkdir(parents=True)
                try:
                    atomic_write(dest / 'steuerstudio.sqlite3', dbfile.read_bytes())
                    (dest / 'originale').mkdir()
                    for name, _ in originals:
                        atomic_write(dest / 'originale' / name, z.read('daten/originale/' + name))
                except Exception:
                    shutil.rmtree(dest)
                    raise
            return {'ok': True, 'counts': counts, 'originals_checked': len(originals)}


def backup_bytes():
    result = io.BytesIO()
    with A.WRITE_LOCK, A.db() as con:
        temp = A.DATA / ('snapshot-' + A.new_id() + '.sqlite3')
        target = sqlite3.connect(temp)
        try:
            con.backup(target)
            target.close()
            with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as z:
                z.write(temp, 'daten/steuerstudio.sqlite3')
                for row in con.execute("SELECT stored_name,sha256 FROM documents WHERE stored_name<>''"):
                    file = A.DATA / 'originale' / row['stored_name']
                    raw = file.read_bytes()
                    if hashlib.sha256(raw).hexdigest() != row['sha256']:
                        raise ValueError('Originaldatei verändert. Sicherung abgebrochen; Daten bitte prüfen.')
                    z.writestr('daten/originale/' + file.name, raw)
                z.writestr('WIEDERHERSTELLUNG.txt', 'Steuerstudio beenden. WIEDERHERSTELLEN_WINDOWS.bat starten und diese ZIP wählen. Wiederherstellung erfolgt in einen neuen Ordner. Sicherung enthält auch Chat, Entwürfe und Rechtsquellen; sie ist nicht verschlüsselt.\n')
        finally:
            target.close()
            temp.unlink(missing_ok=True)
    return result.getvalue()


def snapshot():
    if not BACKUP_LOCK.acquire(False):
        return dict(BACKUP_STATUS)
    BACKUP_STATUS.update(state='running', error='')
    try:
        raw = backup_bytes()
        verify_zip(raw)
        at = A.now()
        name = 'Cay-' + at.replace(':', '').replace('+', '_') + '-' + A.new_id()[:6] + '.zip'
        folder = A.DATA.parent / 'sicherungen'
        folder.mkdir(exist_ok=True)
        atomic_write(folder / name, raw)
        with A.WRITE_LOCK, A.db() as con:
            cfg = A.settings(con)
            con.execute('UPDATE settings SET value=? WHERE key=?', (A.enc(at), 'last_snapshot'))
        BACKUP_STATUS.update(state='complete', at=at)
        if cfg.get('backup_directory'):
            external = Path(cfg['backup_directory']).expanduser()
            if not external.is_dir():
                raise ValueError('Zusätzlicher Sicherungsordner ist nicht erreichbar. Lokale Sicherung ist vorhanden.')
            atomic_write(external / name, raw)
            if hashlib.sha256((external / name).read_bytes()).digest() != hashlib.sha256(raw).digest():
                raise ValueError('Zusätzliche Sicherung konnte nicht verifiziert werden.')
            with A.WRITE_LOCK, A.db() as con:
                con.execute('UPDATE settings SET value=? WHERE key=?', (A.enc(at), 'external_snapshot'))
            BACKUP_STATUS['external_at'] = at
        # Retain recent snapshots, one per day for 30 days, and one per month.
        files = sorted(folder.glob('Cay-*.zip'), reverse=True)
        keep, days, months = set(files[:48]), set(), set()
        for f in files:
            day, month = f.name[4:14], f.name[4:11]
            if day not in days and len(days) < 30:
                keep.add(f)
                days.add(day)
            if month not in months and len(months) < 12:
                keep.add(f)
                months.add(month)
        for f in files:
            if f not in keep:
                f.unlink()
    except Exception as exc:
        BACKUP_STATUS.update(state='error', error=str(exc)[:500])
    finally:
        BACKUP_LOCK.release()
    return dict(BACKUP_STATUS)


def background():
    def loop():
        last = -1
        while not STOP.is_set():
            try:
                with A.db() as con:
                    signature = tuple(con.execute('SELECT count(*),max(at) FROM audit').fetchone()) + tuple(con.execute('SELECT count(*),max(updated_at) FROM drafts').fetchone())
                if signature != last or BACKUP_STATUS['state'] == 'error':
                    snapshot()
                    last = signature
            except Exception:
                BACKUP_STATUS.update(state='error', error='Automatische Sicherung fehlgeschlagen. Bitte den Speicher prüfen.')
            STOP.wait(900)
    threading.Thread(target=loop, daemon=True).start()


def status():
    with A.db() as con:
        cfg = A.settings(con)
        latest = con.execute('SELECT max(at) FROM audit').fetchone()[0]
    return {'data_path': str(A.DATA), 'snapshot_path': str(A.DATA.parent / 'sicherungen'),
            'last_saved_at': latest, 'last_snapshot': cfg.get('last_snapshot', ''),
            'external_snapshot': cfg.get('external_snapshot', ''), 'backup': dict(BACKUP_STATUS),
            'draft_count': len(get_drafts()), 'sqlite_version': sqlite3.sqlite_version,
            'journal': 'DELETE / FULL'}
