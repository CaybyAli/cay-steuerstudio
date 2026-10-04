# Testbericht · Cay Steuerstudio 0.4.0

Stand: 04.10.2026. Geprüft wurde der Programmstand mit synthetischen Daten. Es wurde keine echte EÜR des Nutzers berechnet oder übermittelt.

## Ergebnis

- **213 Python-Tests ausgeführt: 206 bestanden, 7 bewusst übersprungen.** Die sieben optionalen Tests benötigen ein privates Bescheidpaket, das nicht zum Release gehört.
- Frontend-Grundtests bestanden; JavaScript-Syntax und Python-Module geprüft.
- Browserablauf in Chromium mit **106 synthetischen Zahlungen** bestanden: 33 betriebliche und 73 private Testdatensätze, drei lesbare Testunterlagen.
- Update mit tatsächlichem **0.3.8-Programmcode** vorbereitet: 106 bestehende Zahlungen und fertige Arbeiterschritte blieben in 0.4.0 unverändert. Die vorhandene unterbrochene Jahresprüfung wurde fortgesetzt, ohne den fertigen Arbeiter nochmals aufzurufen. Danach beide Leser 106/106; Sicherung geprüft.

## Neu geprüfte Grenzen und Rechenfälle

- Dezimal-/Cent-Parsing, ungültige Werte, Null nur bei ausdrücklicher Eingabe, kaufmännische Anteilsrundung.
- Einnahmen/Ausgaben netto plus separat angesetzte USt; Erstattungen mit umgekehrtem Vorzeichen; kein Betrag aus KI-Jahressummen.
- Gemischter Aufwand, Bewirtung mit getrenntem Vorsteueransatz, nicht abziehbarer Nettoteil separat erhalten.
- Finanzamts-USt-Erstattung als voller eigener Ansatz, keine erneute USt-Abspaltung; Widerspruch zum Kleinunternehmerprofil wird bei betroffenen Ansätzen abgewiesen.
- Anschaffungsnetto wird nicht sofort als laufende Ausgabe gezählt. Manuelle Jahres-AfA, Buchwertentwicklung, Schutz vor mehrfacher Verknüpfung derselben Anschaffung und negative Restbuchwerte geprüft.
- Stale-Formular/Revision und geänderte Zahlung, Rechnung oder Steuerprofil werden erkannt. Quellenänderungen nehmen betroffene bestätigte Ansätze bis erneuter Bestätigung aus der Rechnung.
- Ergänzungen, negative Korrekturen, CSV-Textschutz, Neustart, Jahresisolation, Jahrescheck-Invalidierung und vollständige SQLite-Sicherung einschließlich EÜR-Tabellen.
- Wiederholte identische Übernahme einer Ergänzung mit Request-ID erzeugt keinen zweiten Ansatz; geänderte Wiederholung wird abgelehnt.
- Eine freie lange EÜR-Frage bleibt im freien Chat und erreicht beide Leser vollständig, sofern das konfigurierte Kontextfenster ausreicht.
- Alle Zeichen eines mehrteiligen gespeicherten Dokumenttexts erreichen Arbeiter und Prüfer. Der unabhängige Prüfer sieht die Arbeiterantwort nicht. Originalauftrag erreicht alle vorgesehenen Rollen.
- Unterbrechung, Neustart und Wiederaufnahme behalten fertige Schritte. Geänderte Quellen verhindern die Vermischung alter und neuer Auswertungen.
- Erfundenes wörtliches Dokumentzitat oder ungültige Modellposition wird nicht übernommen; unbekannte USt bleibt `null`.

## Im Browser bedient

Zahlungszuordnung mit Eingabe, abgewiesener USt über dem betrieblichen Zahlungsbetrag und anschließender gültiger Speicherung; Einnahme mit USt; Anschaffung mit verknüpfter AfA; Ergänzung/Tagespauschale; Jahrescheck; Entwurf schließen und wiederherstellen; CSV-Download und Druckexport; KI-Prüferabbruch und Fortsetzung nach Serverneustart; KI-Vorschlag im Formular ohne automatische Bestätigung; freie EÜR-Frage; bestehende Daten nach Neustart; gesperrte Formularzuordnung für andere Jahre.

Helle/dunkle Ansicht und kleines Browserfenster wurden geprüft. Die EÜR-Navigation wurde nach visueller Prüfung korrigiert. Keine JavaScript-Laufzeitfehler im bestandenen Ablauf. Die Druckansicht enthält Ansätze, Quellen und offene Punkte.

Reproduzierbarer neuer Browserablauf: `tests/euer_browser.cjs`, siehe `tests/README_BROWSER.md`. Produktionsmodelle werden darin gezielt simuliert.

## Was nicht nachgewiesen ist

Die tatsächliche Windows-Installation, GPU-Leistung, lokal installierte Qwen-/Gemma-/GPT-OSS-Versionen und die vollständigen Originalbelege des Nutzers wurden in dieser Umgebung nicht ausgeführt beziehungsweise neu geprüft. Keine Zusage vollständiger steuerlicher Richtigkeit oder Fehlerfreiheit. Nicht alle EÜR-Formularfelder und Gewinnkorrekturen sind umgesetzt. Der Arbeitsentwurf ersetzt keine vollständige Erklärung.

Die am 04.10.2026 neu gemeldeten Produktprobleme – starre Kategorien, gesperrtes importiertes Zahlungsdatum, zu viele Steuerfelder, dauerhafter Offen-Status bei „kein Beleg“ und die insgesamt zu komplexe Oberfläche – sind **noch offen** und im Auftrag für Claude Code konkret beschrieben. Die Übergabe soll ihre Umsetzung ermöglichen, nicht deren Erledigung behaupten.
