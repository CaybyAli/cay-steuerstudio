# Browserprüfung mit synthetischen Daten

Die normale Anwendung benötigt Node/Playwright nicht. Für Entwickler: Aus dem Projektstamm `npm install` und anschließend `npx playwright install chromium` ausführen. Die bekannte Testumgebung verwendete Playwright 1.62.1 und Chromium unter Linux. Die lokale Windows-/Ollama-Installation des Nutzers wurde dort nicht ausgeführt.

Start: `npm run test:browser` beziehungsweise `node tests/euer_browser.cjs`.

Der Test startet `tests/euer_server.py` in einem neuen Verzeichnis unter `test-output/euer/`, erzeugt 106 synthetische Zahlungen und simuliert lokale Modellantworten sowie einen einmaligen Prüferabbruch. Der Produktionsstart verwendet diese Simulation nicht. Der Browser prüft EÜR-Zuordnung, ungültige Steuerbeträge, AfA, Ergänzungen, Jahrescheck, Entwurfswiederaufnahme, Export, KI-Unterbrechung/Resume, freien EÜR-Chat, Jahreswechsel der Ansicht und Neustart.

Optional:

- `CAY_TEST_PYTHON`: Pfad zum passenden Python-Interpreter. Sonst `python` unter Windows und `python3` auf anderen Plattformen.
- `CAY_TEST_CHROME`: Pfad zu einem vorhandenen geeigneten Chromium-Binary. Sonst verwendet Playwright seine installierte Browser-Version.

Ausgaben: Screenshots, Druck-PDF, CSV, Protokoll und `browser-result.json` unter `test-output/euer/`. Dieser Ordner ist in `.gitignore` ausgeschlossen. Er enthält ausschließlich Testdaten.

Backend: `python -m unittest discover -s tests -q` **aus dem Projektstamm**. Frontend-Grundtests: `node tests/frontend.test.cjs`.

`tests/dom_integration.cjs` ist ein älterer Test mit optionalem privaten Bescheidpaket und zusätzlicher jsdom-Abhängigkeit. Ohne dieses Paket überspringt er sich; für den neuen Browserablauf ist dieses Paket nicht erforderlich.
