# Technische Übergabe · Cay Steuerstudio 0.4.0

Stand: 04.10.2026. Dieser Stand ist eine lauffähige Weiterentwicklung der Version 0.3.8 und die Basis für den nächsten größeren Umbau. Die neuen Nutzerbeschwerden vom 04.10.2026 sind ausdrücklich **noch offen**. Der Nutzer möchte die weitere Entwicklung mit Claude Code übernehmen und dafür ein privates GitHub-Repository anlegen. Ein Remote wurde durch diese Übergabe nicht erstellt.

## Produkt und Daten

Lokale Python-Webanwendung für Creator-Einnahmen und zugehörige private Steuerunterlagen. Windows ist die Zielplattform. SQLite und Originaldateien liegen standardmäßig unter `%LOCALAPPDATA%\CaySteuerstudio\data`; ein aktivierter anderer Datenordner wird durch `storage.default_dir()` ermittelt. Git enthält Programmcode und synthetische Testfälle, keine produktive Datenbank oder echten Belege.

Der Arbeitsablauf umfasst CSV/PDF-Bankimport, lokalen OCR-Pfad für Kontoauszüge, Prüfung nach Monaten, Übernahme, manuelle Barzahlungen, Dokumente, Notizen, Aufgaben/Fristen, Papierkorb, Sicherungen, jahresbezogenes Steuerprofil, lokale Rechtsquellen sowie lokale KI-Unterstützung.

Die produktiven Assistenzrollen sind drei nacheinander aufgerufene Ollama-Modelle: Arbeiter, unabhängiger Prüfer, Koordinator. Modellnamen/Digests kommen aus der lokalen Installation. Die Entwicklung durch Claude Code ist davon getrennt. Kein Cloud-Zwang für den späteren Alltagsbetrieb.

**Nicht ableiten:** Eine Abbildung mit 106 Zahlungen ist keine mitgelieferte Nutzerdatenbank. Die Browserprüfung dieses Updates benutzt 106 synthetische Zahlungen (33 betrieblich, 73 privat). Diese Zahlen sind Testdaten, keine neu vorgenommene Einordnung des Nutzerbestands. Reale Belege wurden nicht für das Release in das Programm eingefügt.

## Was 0.4.0 tatsächlich ergänzt

- Eigenes EÜR-Arbeitsfenster mit Zuordnungen, Ergänzungen, manueller Jahres-AfA, Jahrescheck und CSV-/Druckexport.
- Geldrechnung ausschließlich in Integer-Cent. Betrieblicher Anteil kaufmännisch gerundet; eingegebene abziehbare/vereinnahmte USt abgetrennt; erst danach gegebenenfalls Nettokosten-Abzugsanteil. Erstattungen können eine bestehende Kosten-/Erlösposition mindern. Nicht abziehbarer Nettoteil separat ausgewiesen.
- Eine Anschaffung ist netto keine sofortige laufende Ausgabe. Geprüfte Jahres-AfA wird separat im Anlageneintrag erfasst. Keine automatische AfA-Berechnung aus geschätzter Nutzungsdauer oder bloßen Vorjahressummen.
- Quellen-Fingerprints verhindern die Weiterverwendung bestätigter Zuordnungen nach Änderungen von Zahlung, verknüpften Belegen oder Jahresprofil. Ergänzungen können Dokumentquellen verknüpfen; Anlagen eine zugehörige Anschaffungszahlung. Betroffene veraltete Ansätze bleiben bis erneuter Bestätigung aus den Summen heraus.
- Entwürfe und synchron gespeicherte EÜR-Mutationen mit Request-ID zum Schutz gegen doppelte Übernahme nach verlorener Antwort. Der Jahrescheck gilt nur für seinen Datenstand. Offene Bankimporte werden als Lücke ausgewiesen.
- EÜR-KI-Läufe mit gespeichertem vollständigem Auftrag und separaten Schritten. Alle Zeichen ausgewählter gespeicherter Dokumenttexte werden in Abschnitten an beide Leser übergeben. Für eine Zahlung erhalten die Leser Zusammenfassungen ihrer eigenen Lektüre von verknüpften oder zusätzlich ausgewählten Unterlagen. Der Prüfer bekommt keine Arbeiterantwort. Erst der Koordinator vergleicht beide Vorschläge. Unterschiede in Position/VAT werden auch programmatisch markiert.
- KI-Vorschläge landen zuerst im Prüfformular. Keine automatische Änderung einer Buchung/Zuordnung. Fehlender Belegtext oder nicht abgedeckte Originalbilder werden nicht als vollständig geprüft behauptet.
- Freie Chatfragen bleiben freie Fragen, auch mit dem Begriff „EÜR“. Die Jahresprüfung ist eine ausdrücklich ausgewählte Funktion. Neue Jahresprüfungs-Batches erhalten zusätzlich den Originalauftrag. Maximal 12.000 Textzeichen pro Frage, zusätzlich begrenzt durch das tatsächlich verfügbare Modell-Kontextfenster. Größere Modellkontexte sind nur bei ausreichender Hardware sinnvoll.

## Grenzen dieses Arbeitsstands

Die EÜR-Positionsauswahl gilt nur für das Formularjahr 2025. Sie deckt ausgewählte gewöhnliche Einnahmen-/Ausgabenpositionen ab. Weitere Gewinnkorrekturen, Teile der Kfz-Sachverhalte, Anlagen SZ/weitere Anlagen und die vollständigen Entnahmen-/Einlagenangaben sind nicht umgesetzt. Die angezeigte Differenz ist vor weiteren Gewinnkorrekturen. Keine vollständige Umsatzsteuer-, Gewerbesteuer- oder Einkommensteuererklärung; keine ELSTER-Übermittlung. Keine automatische Feststellung, ob tatsächlich alle Konten/Barzahlungen/Unterlagen erfasst sind.

Dokumenttext-Lektüre ist keine vollständige visuelle Originalprüfung. Rechnungs-PDFs benötigen lesbaren Text beziehungsweise manuelle Ergänzung; ein verlässlicher allgemeiner Rechnungs-OCR-Prozess ist nicht als universell verfügbar anzunehmen. Das bestehende PDF-/OCR-System ist vor allem auf Kontoauszüge ausgerichtet.

Die EÜR-Prüfung ersetzt weder die Klärung des Jahresprofils noch die fachliche Prüfung steuerlicher Voraussetzungen. User-Angaben und LLM-Vorschläge können sachlich falsch sein. Konkrete Befunde offenhalten, ohne organisatorische Eingaben in Endlosschleifen zu sperren.

## Neue, noch offene Beschwerden: Einstieg im Code

| Problem | Beobachtbare Ursache / Einstieg | Gewünschter nächster Zustand |
|---|---|---|
| Kategorien nicht frei änderbar | `app.py:CATEGORIES`, `dist/app.js:categories`; Backend-Prüfungen in `app.py`, `banking.py`, `intake.py` und Import-/Modellschemas | Persistente Kategorien mit stabilen IDs, eigener Verwaltung, Migration alter Namen; EÜR-Zuordnung getrennt halten |
| Importiertes „Bezahlt am“ nicht änderbar | `dist/banking.js:transactionForm` setzt `amount` und `paid_on` bei `bank_row_id` auf readonly. `app.save_transaction()` ruft `banking.protect_bank_transaction()` auf | Gezielter Korrekturweg mit Audit, unveränderter Rohquelle, stabiler Dublettenkennung und konsistenten Auswertungen |
| „Kein Beleg“ weiter offen | `dist/banking.js:needsEvidence` prüft betriebliche Zahlungen nur auf Dokumentlinks; `receipt_state==='none'` wird nicht zur organisatorischen Erledigung verwendet. `transactionEvidence` und `evidenceForm` halten pauschal „Prüfung offen“ | Erfassungsabschluss von belegbezogener und fachlicher Lücke unterscheiden; konkrete zustandsabhängige Zähler/Filter |
| Steuerbegriffe überfordern | Jahresprofil in `taxprofile.py`, Formularaufbau in `dist/app.js`/`features.js`, explizite EÜR-Eingaben in `dist/euer.js` | Einfache Tatsachenfragen, speicherbares Unbekannt, kontextabhängige Fachdetails und belegte Vorschläge |
| Zu viele Bereiche und Hinweise | Mehrere konkurrierende Views/Modal-Flows; globale Funktionsüberschreibungen über die gesamte Scriptreihenfolge | Zusammenhängende Navigation und ein klarer Weg pro Aufgabe; ruhiges Design mit weniger sichtbaren Pflichtentscheidungen |

Diese Beschwerden nicht als „in 0.4.0 bereits behoben“ ausgeben. Der aktuelle Updateauftrag wurde abgeschlossen; die grundlegende Vereinfachung ist der neue Claude-Auftrag.

## Dateikarte

| Datei / Bereich | Zuständigkeit / Hinweise |
|---|---|
| `app.py` | HTTP-Server, SQLite-Basisschema, Integer-Cent, Dokument-/Buchungs-/Aufgaben-CRUD, Originale, Audit, CSRF-/Origin-Prüfung, statische Dateiliste, Start |
| `studio.py` | Bindet Module an den Core; Schemaergänzungen, zusätzliche Zustandsdaten und API-Routing |
| `storage.py`, `maintenance.py` | Aktive Ablage, atomare Dateien, Entwürfe, Idempotenz, Anwendungssperre, Sicherung und Wiederherstellung |
| `banking.py` | Konten, Bank-Rohdaten, CSV-Vorschau/Übernahme, Dublettenschutz, Überträge, Schutz importierter Zahlungen |
| `intake.py`, `statements.py`, `pdfio.py`, `pdf_review.py` | PDF-/OCR-/Import-Schritte, Quellenabgleich, Kontrollsummen, Folgeseiten, Monatsfreigaben und Korrekturhilfen vor Übernahme |
| `recycle.py` | Archivieren/Wiederherstellen von Uploads; übernommene Zahlungen erhalten |
| `intelligence.py` | Freier Chat, Rollenmodelle, Modellaufruf/JSON-Prüfung, persistierte Chat-Schritte und Wiederaufnahme |
| `year_review.py`, `dist/annual.js` | Ausdrückliche Jahresprüfung aller aktiven Buchungsdatensätze; Cent-basierte Zahlungsübersicht, keine vollständige Belegprüfung |
| `euer.py` | Neue Zuordnungen/Ergänzungen/Anlagen, exakte Rechnung, Invalidierung, Jahrescheck, CSV |
| `euer_ai.py` | Unabhängige Textabschnitte/Einzelvorschläge, validierte Antworten, Fortschritt, Modelldigests und Resume |
| `taxprofile.py`, `assessments.py` | Jahresbezogene Statusangaben, optionales altes Bescheidpaket/Import. Private Bescheide sind nicht im Repository |
| `laws.py`, `retrieval.py` | Lokale amtliche Quellen mit Herkunft/zeitlicher Prüfung und Kontextauswahl |
| `dist/index.html` | Explizite Script-/Stylesheet-Reihenfolge; derzeit ruft `dist/euer.js` am Ende `start()` auf |
| `dist/app.js` | Basis-Views und Hilfsfunktionen, globale App-/Form-/Action-Logik |
| `dist/features.js`, `banking.js`, `intake.js`, `pdf-review.js`, `workspace.js`, `annual.js`, `euer.js` | Aufeinander aufbauende globale Wrapper; diese Kopplung bei Refactor beachten |
| `dist/style.css`, `features.css`, `intake.css`, `studio.css`, `euer.css` | Mehrere Designlagen; übergreifende Selektoren können Komponenten verändern. `nav` setzte EÜR-Tabs zunächst vertikal, inzwischen explizit korrigiert |
| `tests/` | Backend-Regressionen, Frontend-Grundtests und reproduzierbarer neuer Browser-Ablauf; synthetische Fixtures |

## Daten- und Integritätsregeln

`app.db()` ist verschachtelbar/threadbezogen; Mutationen nutzen `WRITE_LOCK`. KI-Aufrufe werden durch `AI_LOCK` serialisiert. Die alte SQLite- und Originalstruktur wird ergänzt, nicht ersetzt. Wiederholte Übernahmen und alte Formularstände sind bewusst abgesichert.

Neue Tabellen: `euer_allocations`, `euer_entries`, `euer_reviews`, `euer_runs`, `euer_steps`. Sie sind Teil der vollständigen SQLite-Sicherung. Geänderte Quellstände und Modellversionen verhindern die Vermischung alter und neuer Resume-Ergebnisse.

Eine Backend-Betragsprüfung darf nicht durch UI-Tricks umgangen werden. Umgekehrt ist ein bestehender Schutz kein Grund, einen nötigen Korrekturweg dauerhaft unmöglich zu machen. Den nächsten Entwurf über ein konsistentes Datenmodell lösen.

## Historie wichtiger Fehler und Gegenmaßnahmen

1. **Dokumenten-/Bankimport:** Mehrseitige Auszüge und Folgeseiten konnten falsch gruppiert werden. Gebühren-Unterpositionen sind keine zusätzlichen Bankbewegungen. Vergleich von Datum/Betrag/Soll-Haben und Seitenbezug muss nachvollziehbar bleiben. Tests in `test_pdf_*` decken mehrere Regressionen ab.
2. **Fehlende Originaldeckung:** Ein Modell kann eine plausible, aber nicht belegte Zeile liefern. Solche Angaben nicht nachträglich passend rechnen. Korrektur mit echter Fundstelle; Unklarheiten konkret anzeigen.
3. **Papierkorb:** Erneuter Upload einer archivierten Datei darf nicht in eine Sackgasse führen. Wiederherstellung verwendet den bestehenden Stand; bereits übernommene Zahlungen nicht doppelt erzeugen.
4. **KI-Jahresprüfung:** Vor 0.3.8 scheiterten leere oder lange Gemma-Kommentare unnötig; die Wiederaufnahme und adaptive Aufteilung wurden verbessert. Der fertige Arbeiter bleibt erhalten. Dokumentierte technische Tests sind keine Echttests der Nutzer-GPU.
5. **Falscher Modus:** Vor 0.4.0 löste das Wort „EÜR“ die Metadaten-Jahresprüfung aus. Ein dafür geschriebener freier EÜR-Auftrag konnte deshalb seinen Zweck nicht erfüllen. Routing ist jetzt ausdrücklich.
6. **Missverständlicher Umfang:** „106/106 beantwortet“ bedeutete beantwortete Datensätze, keine vollständig gelesenen Originalbelege. Umfang, Quelle und formale Antwortvollständigkeit von sachlicher Prüfung unterscheiden.
7. **Formularproblem in Entwicklung 0.4.0:** Ein verborgenes `name="id"` überschrieb die native Formulareigenschaft `form.id`. Speichern eines Anlageneintrags wurde so blockiert. Behoben durch `data-id` und gezielte Payload-Erzeugung. Browsertest enthält den Speichervorgang.
8. **Autosave/Export:** Neues EÜR-Formular wiederaufnehmen, Bestätigung erneuern, Snapshot/Revision prüfen. CSV mit formelsicheren Textspalten und Druckansicht ohne Navigation. Dynamisches UI nicht während einer Eingabe unkontrolliert neu rendern.

## Verifikation und Reproduktion

Siehe `TESTBERICHT.md` für die abgeschlossene Prüfung. Tests aus dem Projektstamm ausführen. Sieben optionale Tests setzen ein privates Bescheidpaket voraus und werden ohne dieses Paket übersprungen; das Paket nicht aus einem Nutzerprofil in Git kopieren.

Für Browserprüfungen erzeugt `tests/euer_server.py` selbst einen separaten synthetischen Bestand. Es simuliert Modellantworten und einen Prüferabbruch. Der Produktionsstart verwendet diese Simulation nicht. Für Tests echter Ollama-Modelle zusätzlich dokumentieren: Modellname/Digest, Kontextgröße, Quellumfang, Hardware, Dauer, Abbruch-/Resume-Ergebnis.

Vor Änderungen mit einer bestehenden Datenablage Sicherung anlegen und Rückweg prüfen. Kein Zurücksetzen der echten Datenbank für einen leichteren Test. Nach dem nächsten Umbau die übergreifenden Browser-Abläufe inklusive Migration erneut prüfen.
