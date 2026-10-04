# Cay Steuerstudio 0.4.0

Lokales Dashboard für YouTube/Twitch und private Steuerunterlagen. Stand: 03.10.2026.

**Start und Update:** [START_HIER.md](START_HIER.md). Das Paket vollständig in einen neuen Ordner entpacken, EINRICHTEN_WINDOWS.bat und anschließend START_WINDOWS.bat ausführen. Bestehende Daten liegen außerhalb des Programmordners und bleiben erhalten. Vorher die alte Version sichern und schließen.

## Weiterentwicklung mit Claude Code

Für den Wechsel: **GITHUB_START.md**. Der vollständige neue Auftrag steht in **CLAUDE_AUFTRAG.md**, technische Hintergründe und bekannte offene Fehler in **docs/UEBERGABE_0.4.0.md**. **CLAUDE.md** dient als Projekteinstieg.

## Neu in 0.4.0

- Eigener Bereich **EÜR vorbereiten**: Zahlungen zuordnen, Ergänzungen/AfA erfassen, Jahrescheck und nachvollziehbarer CSV-/Druckexport.
- Centgenaue Rechnung aus bestätigten Einzelansätzen. Umsatzsteuer, betrieblicher Anteil und begrenzt abziehbarer Nettoteil werden getrennt behandelt.
- Anschaffungen werden netto nicht sofort abgezogen. Geprüfte Jahres-AfA und Buchwertentwicklung werden im Anlageverzeichnis gespeichert; Vorjahres-AfA wird nicht automatisch fortgeschrieben.
- Die drei lokalen Modelle lesen gespeicherte Dokumenttexte abschnittsweise und erstellen Vorschläge pro betrieblicher/ungeklärter Zahlung. Beide Leser arbeiten unabhängig. Originalauftrag, Fortschritt, Antworten und Unterbrechungen bleiben gespeichert.
- Freie Fragen werden durch das Wort „EÜR“ nicht mehr automatisch in eine Jahresprüfung umgeleitet. Maximal 12.000 Zeichen; reicht der Modellkontext nicht, folgt eine verständliche Fehlermeldung statt stiller Kürzung.
- Geänderte Beleggrundlagen, Zahlungen oder Steuerprofile machen betroffene Bestätigungen ungültig. Entwürfe, Wiederaufnahme und Schutz gegen doppelte Speicherung sind integriert.
- Formularzuordnung für **2025**. Ausgewählte Einnahmen-/Ausgabenpositionen, kein vollständiger ELSTER-Formularsatz; weitere Gewinnkorrekturen und andere Erklärungen separat bearbeiten. Keine Übermittlung.

Die Anleitung **START_HIER.md** beschreibt das Update und den Arbeitsablauf. **TESTBERICHT.md** nennt die geprüften Abläufe und Grenzen.

## Aus 0.3.8 weiterhin enthalten


- Behebt den Abbruch von Gemma bei leeren Zusatzkommentaren zu `no_issue` und bei vollständigen Hinweisen über 500 Zeichen. Lange Hinweise bleiben ungekürzt erhalten. `review` ohne konkrete Begründung wird weiterhin nicht als abgeschlossene Rückmeldung übernommen.
- Leser verwenden ein festes JSON-Antwortschema mit erlaubten Buchungskennungen und Statuswerten. Die unabhängige Inhaltsprüfung bleibt zusätzlich bestehen.
- Nach zwei ungültigen Rückmeldungen wird ein Leserabschnitt automatisch halbiert, bei Bedarf bis zur Einzelbuchung. Aufteilung und fertige Schritte sind atomar gespeichert und überstehen Neustarts.
- Arbeiter, Prüfer und Zusammenfassung zeigen getrennte Fortschritte. Ein fertiger Arbeiterdurchlauf wird nicht mehr durch „Beide Leser: 0 von 106“ verdeckt.
- Bereits abgebrochene Jahresprüfungen aus 0.3.7 können mit dem unveränderten Daten- und Modellstand fortgesetzt werden. Keine erneute Erfassung und kein vollständiger Neustart nötig.

## Aus 0.3.7 weiterhin enthalten

- **Klare Geldbeträge:** Cent bleiben intern ganze Zahlen. An die KI gehen formatierte Euro-Beträge und eine feste Jahresübersicht. Die Jahresansicht zeigt Einnahmen, Ausgaben und Zahlungssaldo nach deiner Einordnung.
- **Alle gespeicherten Buchungen prüfen:** Zwei unabhängige Leser erhalten sämtliche aktiven Buchungen des Zahlungsjahres in kleinen Gruppen. Fehlende oder doppelte KI-Rückmeldungen werden abgewiesen und einmal kompakt wiederholt. Die Zusammenfassung kann erst nach vollständigen Rückmeldungen entstehen.
- **Nach Abbruch fortsetzen:** Abgeschlossene Abschnitte bleiben dauerhaft gespeichert. Nach Antwortlimit oder Neustart wird nur der offene Teil fortgesetzt. Geänderte Daten oder Modelle erfordern eine neue Prüfung; ältere Berichte bleiben als damaliger Stand erhalten.
- **Verständlicher Bericht:** Offene Punkte nach Monat, alle Zahlungen erreichbar, direkte Bearbeitung, gespeicherte Notizen und getrennte Leserhinweise. Fehlende Belegverknüpfung wird von nachweislich fehlendem Beleg unterschieden.
- **Alte falsche Antworten erkennen:** Frühere Jahresantworten mit begrenzter Datenauswahl sind markiert und eingeklappt. Der ursprüngliche Text bleibt erhalten.
- **Weniger erneutes Modellladen:** Ein Leser bleibt zwischen seinen Abschnitten kurz geladen; am Rollenwechsel wird er entladen. Verarbeitung bleibt nacheinander.

Die Jahresprüfung liest gespeicherte Buchungsangaben und Belegverknüpfungen; sie ersetzt keinen vollständigen Originalbelegabgleich und erstellt noch keine abgabefertige EÜR. Die bisherigen Bankimport-Reparaturen sind enthalten.

## Aus 0.3.6 weiterhin enthalten

- **Zusammengehörige Folgeseiten gemeinsam prüfen:** Auszugsnummer und Kontoangaben werden unabhängig vom Tabellenlayout gelesen. Eine eindeutig zugehörige Seite fließt auch bei bereits gespeicherten Entwürfen in den Abgleich ein. Gleicher Monat oder gleicher Betrag allein genügt nicht. Widersprüchliche Konto-, Währungs- oder Kontrollangaben bleiben offen.
- **Abschlussbuchungen konkret prüfen:** Datierte, ausdrücklich mit Soll/Haben gekennzeichnete PN-Zahlungszeilen können auch auf sonst unbekannten Folgeseiten als Originalnachweis dienen. Gebühren-Unterpositionen werden dadurch nicht zu eigenen Zahlungen. Datum und Betrag werden nur nach deinem Klick korrigiert; das Ende des Gebührenzeitraums ersetzt keinen Buchungstag.
- **Bestehende Arbeit erhalten:** Kein neuer Upload oder kompletter KI-Leselauf nötig. Einordnungen, Notizen und übernommene Monate bleiben erhalten. Frühere KI-Lesehinweise sind als solche gekennzeichnet; eine erledigte Originalprüfung hinterlässt keine veraltete Fehlermeldung am Freigabeknopf.
- **Abgeschlossene Prüfung:** Nach vollständiger Übernahme zeigt das Fenster den Prüfverlauf; überflüssige Freigabeknöpfe und Erfassungsaktionen bleiben ausgeblendet.

## Aus 0.3.5 weiterhin enthalten

- **Konkreter Zahlenabgleich je Auszug und Monat:** Anfangsstand, Eingänge, Ausgänge, errechneter Endstand und gelesener Bank-Endstand. Zusätzlich getrennte Umsatzsummen und genaue Differenzen. Die Prüfung verwendet den aktuellen Entwurf; fehlende Kontrollwerte erscheinen ausdrücklich als nicht erkannt.
- **Verständliche Hilfe:** fehlende oder mehrfach zugeordnete Originalzahlungen mit Datum, Betrag, Empfänger und Seite; mögliche Ursachen klar als Vermutung. Originalstellen der Kontrollwerte bleiben aufklappbar. Gemeinsame Auszugssummen mehrerer Monate werden nicht als einzelne Monatssalden ausgegeben.
- **Monate einzeln übernehmen:** Unter „Diesen Monat freigeben“ werden nur die ausgewählten Monate geprüft und übernommen. Bereits freigegebene Monate verschwinden aus der offenen Liste. Sie bleiben im Prüfverlauf und Dashboard erhalten. Ein Fehler in einem anderen Monat blockiert keine unabhängige Monatsfreigabe.
- **Bewusste Freigabe bei Salden-/Umsatzabweichung:** Original prüfen, „Trotz Abweichung übernehmen“ wählen und kurze Notiz hinterlegen. Der Zahlenvergleich und die Notiz bleiben dauerhaft gespeichert. Originalbetrag und Belegpflicht werden dadurch nicht geändert; fehlende echte Originalzahlungen oder unklare Quellenzuordnungen bleiben zu korrigieren.
- **Optionale lokale KI-Hilfe:** zwei unabhängige Erklärungen, danach Koordinator. Die drei konfigurierten Ollama-Modelle erhalten den Zahlenabgleich und Quellen. Sie können Vorschläge erklären, aber keine Zahlen ändern oder selbst freigeben. Ohne Ollama bleiben manuelle Prüfung und Import verfügbar.
- **Sicher weiterarbeiten:** atomare Monatsfreigaben, Schutz vor wiederholtem Import und veralteter Monatsvorschau; freigegebene Zeilen werden durch alte Entwürfe nicht überschrieben. Neustart sowie Papierkorb/Wiederherstellung behalten den Stand. In der Auszugsliste erscheint ein teilweise übernommenes Original nur einmal.

„Freigeben“ bedeutet in dieser Version **im lokalen Dashboard speichern**, keine Übermittlung an ELSTER.

## Aus 0.3.4 weiterhin enthalten

- Konkrete PDF-Fehlerhilfe direkt bei der betroffenen Zahlung: Seite, Datum, Betrag, mögliche Ursache und Vergleich mit tatsächlichen Originalzeilen. Datum/Betrag/Seite stehen nebeneinander; Unterschiede werden hervorgehoben.
- Erklärt unter anderem vertauschte Ein-/Auszahlungen, Wertstellung statt Buchungstag, falsche Seite und mehrdeutige Originalzuordnung. Mehrere Fehler werden gemeinsam angezeigt. Ohne verlässliche Originalzeile wird keine Korrektur erfunden.
- **Fehler prüfen** funktioniert vor der Freigabe. **Diese Originalzeile übernehmen** korrigiert nur nach deinem Klick; geänderte Finanzdaten benötigen erneute Einordnung. Notizen bleiben erhalten.
- Veraltete interne Zuordnungen blockieren eine eindeutig identische Originalzeile nicht mehr. Reparatur nur bei identischem vollständigem Text und gleichem Datum/Betrag; Mehrdeutigkeit und echte Abweichungen bleiben prüfpflichtig.
- Beim erneuten Upload derselben entfernten PDF/CSV erscheint **Wiederherstellen & öffnen**. Der gespeicherte Stand wird wiederverwendet; abgeschlossene Importe erzeugen keine neuen Zahlungen. Wiederholte Wiederherstellung nach verlorener Antwort bleibt einmalig.

## Aus 0.3.3 weiterhin enthalten

- Freigabe mit sichtbarem Prüfhaken und verständlicher Rückmeldung direkt am Knopf. Fehlerhafte Pflichtfelder öffnen sich zum Korrigieren; versteckte Felder blockieren nicht mehr kommentarlos.
- Je PDF-Zeile **Auslassen**: **Schon erfasst / doppelt** verhindert eine weitere Zahlung; **Keine eigene Zahlung** entfernt z. B. eine Gebührenaufschlüsselung aus den Zahlungsbeträgen. Ausgelassene Zeilen bleiben gespeichert und lassen sich vor Freigabe wieder aufnehmen.
- Echte Bankbewegungen bleiben bei der Kontostandsprüfung berücksichtigt, auch wenn sie schon manuell erfasst wurden. Eine tatsächlich gebuchte Zahlung lässt sich nicht als Gebührenhinweis aus einer erkannten Originaltabelle wegdrücken.
- Der Volksbank-Tabellenleser erkennt weitere Kontobezeichnungen desselben Layouts. Eine unbekannte Anhangsseite schickt nicht mehr die bereits erkannten Tabellen an die KI zurück. Kontrollsummen und Originalzeilen werden weiter geprüft.
- Markierte Gebührenaufschlüsselungen werden von selbständigen Zahlungen getrennt. Bei unsicherem Layout bleibt die Prüfung am Original nötig; Gesamtgebühr und echte einzelne Gebühren dürfen weiter erfasst werden.
- Bereits gespeicherte, noch nicht übernommene PDF-Importvorschauen lassen sich über **Zahlungsliste bearbeiten** wieder öffnen. Alte, dadurch ungültige Vorschauen können nicht versehentlich übernommen werden.

## Aus 0.3.2 weiterhin enthalten

- Durchgängig erneuerte Oberfläche: ruhige Jahresübersicht, klare Erfassung, nächste Aufgaben und letzte Zahlungen. Einheitliche Abstände, Schrift, helle Flächen und dunkles Design. Dezente Glasflächen nur im Rahmen und in Dialogleisten.
- Fünf Hauptwege: Übersicht, Zahlungen, Unterlagen, Aufgaben und KI-Chat. Seltene Einstellungen bleiben unter Mehr; der Papierkorb ist bei Kontoauszügen und Unterlagen direkt erreichbar.
- Aufgeräumte Formulare: optionale Chat-Anhänge und selten benötigte Einstellungen aufklappbar; Notizen und Entwürfe bleiben erhalten.
- PDF-Kontoauszüge öffnen nach dem Lesen eine breite Monatsprüfung: Datum, Empfänger, kurzer Zweck und Betrag. Vollständiger Seitentext und technische Angaben bleiben eingeklappt.
- Jede Zahlung per Klick als **Privat** oder **Betrieblich** einordnen. Unter **Mehr** stehen **Gemischt**, **Später klären** und **Eigener Übertrag**. Notizen sind optional; Änderungen werden als Entwurf gespeichert.
- **Diesen Monat freigeben** bzw. **Alle offenen Monate freigeben** übernimmt die geprüften Zahlungen direkt. Nur mögliche Doppelungen oder Zuordnungsprobleme benötigen noch einen Abgleich. Vor der Freigabe bleiben sie außerhalb der Zahlungssummen.
- Das unterstützte Volksbank-Format mit **VR-GiroBusiness** und **Bu-Tag Wert Vorgang** wird direkt aus dem PDF-Text gelesen: Soll/Haben, Cent-Beträge, Buchungstag, Überträge, Gebühren und Kontostand werden getrennt geprüft. Dafür sind die KI-Modelle optional; unbekannte Layouts verwenden weiterhin die unabhängigen KI-Lesungen.
- Eine nicht belegte KI-Zeile verwirft nicht mehr alle anderen Seiten. Offene Lesefehler bleiben sichtbar und verhindern eine vorschnelle Freigabe. Beim erneuten Lesen bleiben passende gespeicherte Einordnungen und Notizen erhalten.

## Aus 0.3.1 weiterhin enthalten

- Korrigierte PDF-Erkennung: leeres Öffnungskennwort wird geprüft; Bearbeitungsbeschränkungen allein sperren das Lesen nicht mehr. AES-Unterstützung über `pypdf[crypto]`.
- Bei echtem Öffnungskennwort: einmalige Eingabe ohne Speicherung oder Weitergabe an die KI. Originaldateien bleiben unverändert.
- Papierkorb für Dokumente und CSV-/PDF-Uploads, mit Wiederherstellung. Bereits bestätigte Zahlungen bleiben erhalten; laufende Auswertungen dürfen nach dem Entfernen keine Ergebnisse mehr zurückschreiben.
- Zahlungen und Kontoauszüge in einem Bereich, eine gemeinsame Auszugsliste, weniger doppelte Navigationswege. Ältere Dokument-Uploads bleiben auffindbar und direkt einlesbar.
- Ruhigere Startseite und „Mein Steuerjahr“ mit drei Vorbereitungsschritten. Heller Modus und Darkmode.

Vorhanden bleiben: manuelle Bar-/Bankerfassung, Aufgaben/Kalenderexport, drei lokale Ollama-Modelle, persistierter Chat, Fakten/Quellen, jahresspezifisches Steuerprofil, bereits gespeicherte Bescheide, Entwürfe und geprüfte Sicherung/Wiederherstellung.

Dieses Update enthält Programmdateien und Tests, keine privaten Steuer-PDFs oder gespeicherten Nutzerdaten. Bereits im Dashboard gespeicherte Bescheide bleiben in deiner bestehenden Datenablage. Tests des optionalen alten Bescheidpakets werden ohne diese privaten Dateien ausdrücklich übersprungen.

## Technisch

Python 3.10+, SQLite, lokaler HTTP-Server, HTML/CSS/JavaScript. Standarddatenpfad unter Windows: `%LOCALAPPDATA%\CaySteuerstudio\data`. Startet nur auf `127.0.0.1`. SQLite mit synchronen Schreibvorgängen; Originaldateien atomar geschrieben. Geldbeträge als Cent-INTEGER, Parsing mit Decimal. Importbuchungen schützen Originalbetrag, Datum, Richtung und Konto.

```sh
python app.py --no-browser
python -m unittest discover -s tests -q
node tests/frontend.test.cjs
```

Der erweiterte DOM-Test benötigt als Entwicklungsabhängigkeit `jsdom`: `node tests/dom_integration.cjs`. Zusätzliche PDF-Testfälle verwenden `reportlab`; der OCR-Test läuft bei vorhandenem Tesseract. Zur Anwendung selbst: `pip install -r requirements-pdf.txt`; für Scans zusätzlich Tesseract. Unter Windows helfen die enthaltenen Einrichtungsdateien.

## Grenzen

Keine fertige EÜR, Steuerberechnung, USt-Voranmeldung oder ELSTER-Übermittlung. Kein direkter Bankzugang, keine Überweisungen und kein Mehrbenutzersystem. Der Arbeitsplatz ist keine Zusage einer GoBD-zertifizierten Buchführung. Originale und fachliche Nachweise prüfen; drei übereinstimmende Modelle garantieren keine Richtigkeit. KI-Auswertungen benötigen funktionierendes lokales Ollama. Allgemeine Fotos/Briefe außerhalb des Kontoauszug-Eingangs benötigen bei fehlendem Text weiterhin Textergänzung.

Details: [DATENMODELL.md](DATENMODELL.md), [AUSBAUPLAN.md](AUSBAUPLAN.md), [TESTBERICHT.md](TESTBERICHT.md).
