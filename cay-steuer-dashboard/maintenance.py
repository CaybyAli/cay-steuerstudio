"""Interactive migration / restore. Always restore into a new directory."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import app
import storage


def activate(target):
    storage.atomic_write(storage.base_dir() / 'aktive-ablage.json', json.dumps({'path': str(target.resolve())}).encode())


def restore(raw, make_active=False):
    target = storage.base_dir() / ('wiederhergestellt-' + app.now().replace(':','').replace('+','_') + '-' + app.new_id()[:6])
    result = storage.verify_zip(raw, target)
    if make_active:
        activate(target)
    return target, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['restore', 'import'])
    parser.add_argument('--path', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print('Cay Steuerstudio bitte vollständig beenden. Vorhandene Daten werden nicht überschrieben.\n')
    try:
        current = storage.default_dir()
        storage.lock_instance(current)
        if args.action == 'restore':
            path = args.path or Path(input('Pfad zur Sicherungs-ZIP (aus Explorer kopieren): ').strip().strip('"'))
            if not path.is_file() or path.stat().st_size > 2 * 1024**3:
                raise ValueError('Bitte eine vorhandene ZIP-Sicherung bis 2 GB wählen.')
            raw = path.read_bytes()
        else:
            path = args.path or Path(input('Pfad zum ALTEN Ordner daten (Version 0.1): ').strip().strip('"'))
            if not (path / 'steuerstudio.sqlite3').is_file():
                raise ValueError('In diesem Ordner liegt keine Steuerstudio-Datenbank.')
            app.DATA = path.resolve()
            raw = storage.backup_bytes()
        checked = storage.verify_zip(raw)
        print('Prüfung erfolgreich:', checked['counts'], '| Originale:', checked['originals_checked'])
        if args.check_only:
            return 0
        target, result = restore(raw, False)
        print('\nWiederhergestellt in:', target)
        print('Deine bisherige Ablage bleibt bestehen. Die Ablagen werden nicht zusammengeführt.')
        choice = input('Diese geprüfte Ablage künftig beim Start verwenden? ja/nein: ').strip().casefold()
        if choice == 'ja':
            activate(target)
            print('Aktiviert. Jetzt START_WINDOWS.bat öffnen.')
        else:
            print('Nicht aktiviert. Die bisherige Ablage bleibt ausgewählt.')
        return 0
    except Exception as exc:
        print('Nicht abgeschlossen:', str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
