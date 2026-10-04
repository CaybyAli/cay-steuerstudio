# Cay Steuerstudio – Kontext für Claude Code

Dies ist der lokale Übergabestand **0.4.0** vom 04.10.2026. Der nächste Auftrag ist eine umfassende Vereinfachung und technische Überarbeitung für den Nutzer Cay / CaybyAli.

Lies zum Einstieg:

1. `CLAUDE_AUFTRAG.md` – vollständiger Nutzerauftrag und Abnahmekriterien.
2. `docs/UEBERGABE_0.4.0.md` – Architektur, Dateikarte, behobene und weiterhin offene Fehler.
3. `TESTBERICHT.md` – tatsächlich ausgeführte Tests und Grenzen.
4. Bei Bedarf `START_HIER.md`, `DATENMODELL.md`, anschließend den relevanten Code.

## Lokaler Betrieb

- Python 3.10+, Standardbibliothek, SQLite, Browser-Oberfläche. `dist/` ist gepflegter Quellcode und gehört ins Repository.
- `python app.py --no-browser` startet mit der vorhandenen Nutzerdatenablage. Für Entwicklung ausdrücklich einen separaten Testordner angeben: `python app.py --data-dir .qa/data --port 8766 --no-browser`.
- Windows: `EINRICHTEN_WINDOWS.bat`, dann `START_WINDOWS.bat`.
- Python-Tests **aus dem Projektstamm**: `python -m unittest discover -s tests -q`.
- Frontend-Grundtests: `node tests/frontend.test.cjs`.
- Browser-Ablauf: siehe `tests/README_BROWSER.md` (separate Entwicklungsabhängigkeiten, synthetische Daten).

## Zentrale Anforderungen

- Die bestehenden echten Buchungen, Originale, Einordnungen, Chat-Läufe und Sicherungen erhalten. Entwicklung mit separaten Testdaten. Migrationen müssen nachvollziehbar sein.
- Geldbeträge als Integer-Cent oder passende exakte Dezimalarithmetik; keine LLM-Summen als verbindliche Ergebnisse.
- Unbekannt bleibt unbekannt. Bestätigte Nutzerdaten, belegte Angaben und KI-Vorschläge unterscheiden. Keine erfundenen Steuerstatus oder Jahreswerte.
- Bestätigungen und Berichte nach Änderungen ihrer Grundlagen invalidieren; Audit und Importherkunft erhalten.
- Private Steuerdaten, Kontoauszüge, ELSTER-Zertifikate, Zugangsdaten und lokale Datenbanken nicht committen. Ein privates GitHub-Repository ist kein Ablageort für echte Belege. `.gitignore` ist eine Hilfe, keine vollständige Erkennung sensibler Inhalte.
- Die Anwendung arbeitet lokal. Claude Code ist das Entwicklungswerkzeug; die drei produktiven Assistenzmodelle laufen weiterhin über das lokale Ollama.
- UI auf Deutsch, ruhige hochwertige Gestaltung, einfache konkrete Aufgaben, wenige sichtbare Felder. Neue Fehlerbehebungen nicht als weitere konkurrierende Oberflächen anbauen.
- Der aktuelle EÜR-Bereich ist ein begrenzter Arbeitsentwurf für 2025. Kein kompletter Steuerberater, keine ELSTER-Übermittlung. Die neuen Nutzerbeschwerden sind noch nicht behoben; siehe Auftrag.
