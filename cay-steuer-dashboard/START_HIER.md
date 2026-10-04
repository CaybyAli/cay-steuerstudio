# Cay Steuerstudio 0.4.0 – Update und EÜR 2025

Stand: 04.10.2026. Lokales Dashboard für deine betrieblichen und privaten Unterlagen.

## Update mit bestehender Datenablage

1. In der bisherigen Anwendung **Mehr → Sicherung → Sicherung herunterladen** wählen. Den dort angezeigten Datenpfad notieren.
2. Das alte schwarze Programmfenster mit **Strg+C** schließen. Alte Dashboard-Tabs schließen.
3. Dieses ZIP vollständig in einen neuen Programmordner entpacken, zum Beispiel `D:\Cay-Steuerstudio-0.4.0`. Nicht direkt im ZIP starten.
4. **EINRICHTEN_WINDOWS.bat** einmal ausführen, danach **START_WINDOWS.bat**. Python 3.10 oder neuer ist erforderlich. KI-Modelle werden nicht erneut heruntergeladen.
5. Den Browser mit **Strg+F5** neu laden. Unten links muss **0.4.0 · Update 04.10.2026** stehen.
6. Unter **Mehr → Sicherung** denselben Datenpfad und vorhandene Buchungen kontrollieren. Standard: `%LOCALAPPDATA%\CaySteuerstudio\data`. Eine zuvor aktivierte andere Datenablage wird weiterhin verwendet.

Falls die Ablage leer erscheint, zuerst die Datenpfade vergleichen. **ALTE_DATEN_UEBERNEHMEN_WINDOWS.bat** nur für einen bisher nicht übernommenen alten Ordner verwenden; es führt keine zwei Datenbestände zusammen. Eine Wiederherstellung erfolgt in einen neuen Ordner.

Das Programmfenster bleibt geöffnet. Die normale Adresse ist `http://127.0.0.1:8765`.
Das Update enthält keine privaten Steuer-PDFs oder Nutzerdatenbank. Bereits gespeicherte Originale bleiben in deiner Datenablage.

## Damit jetzt arbeiten

1. **Arbeitsjahr 2025 → EÜR vorbereiten** öffnen. Über **Steuerstatus 2025** den belegten Jahresstatus prüfen. Die Anwendung leitet ihn nicht aus einer Erstattung oder den Angaben für 2024 ab.
2. Im Reiter **Zahlungen** die offenen Positionen bearbeiten. Vorhandene Belege lassen sich über **Zahlung / Belege** verknüpfen. „Privat / Eigenübertrag“ folgt deiner gespeicherten Einordnung; unter **Alle** kannst du diese Positionen ebenfalls kontrollieren.
3. Bei **Zuordnen** die EÜR-Position, den betrieblichen Anteil, den abziehbaren Nettoteil und den belegten Steuerbetrag angeben. Die Beleggrundlage begründen und ausdrücklich bestätigen. Unbekannte Steuerbeträge bleiben zunächst offen; `0,00` bedeutet eine bewusst geprüfte Null.
4. Optional **3 KI prüfen → EÜR-Prüfung starten**. Der voreingestellte Auftrag reicht als Einstieg. Zusätzliche Vorjahresunterlagen, insbesondere das Anlageverzeichnis, gezielt auswählen. Aktuelle Jahresunterlagen außer Kontoauszügen sowie verknüpfte Rechnungen werden automatisch gelesen.
5. Bei **Im Formular prüfen** wird ein Vorschlag angezeigt. Erst deine Bestätigung speichert ihn. Ungeklärte oder unterschiedliche Vorschläge am Original prüfen. Bestehende Zahlungen werden von den Modellen nicht geändert.
6. Unter **Ergänzungen & AfA** ermittelte Werte ohne neue Bankzahlung erfassen. AfA anhand des wirklichen Anlagenachweises 2025 eintragen. Die AfA-Summe aus der EÜR 2024 allein reicht dafür nicht.
7. **Jahrescheck** bearbeiten. **Auswertung** zeigt bestätigte Positionen, Einzelansätze und offene Punkte. **CSV mit Einzelansätzen** exportiert auch den Zahlungsabgleich. **Drucken / als PDF speichern** nutzt den Druckdialog deines Browsers.

Du kannst manuell zuordnen und rechnen, während die KI arbeitet. Ändert sich dabei die Datenbasis, wird der bisherige KI-Bericht als veraltet gekennzeichnet.

## So entstehen die Beträge

- Für jede bestätigte Zahlung wird der betriebliche Anteil centgenau kaufmännisch gerundet. Von diesem Anteil wird die eingetragene, belegte Umsatzsteuer abgetrennt.
- Das USt-Feld enthält **nur die Umsatzsteuer des betrieblichen Zahlungsanteils**, nicht automatisch die gesamte Steuer einer gemischten Rechnung. Es ist kein Steuersatzrechner.
- Vereinnahmte USt wird separat in Zeile 17, gezahlte abziehbare Vorsteuer in Zeile 57 angesetzt. Nicht abziehbare oder ausländische Umsatzsteuer nicht als Vorsteuer in dieses Feld eingeben.
- USt-Erstattungen vom Finanzamt (Zeile 18), USt-Zahlungen ans Finanzamt (Zeile 58), Kleinunternehmer-Einnahmen (Zeile 12) und umsatzsteuerfreie/nicht steuerbare Einnahmen (Zeile 16) werden ohne erneute USt-Abspaltung erfasst.
- Bei geschäftlicher Bewirtung wird hier ein Abzugsanteil von 70 % des betrieblichen Betrags ohne abziehbare Vorsteuer verwendet. Die Voraussetzungen und die Höhe eines möglichen Vorsteuerabzugs sind getrennt zu prüfen. Der nicht abziehbare Nettoteil wird im Bericht separat ausgewiesen.
- Eingänge auf einer Ausgabenposition mindern diese Ausgabe, Ausgänge auf einer Einnahmenposition mindern diese Einnahme. Nur für begründete Erstattungen/Stornos verwenden.
- Bei **Anschaffung** bleibt der Nettobetrag aus den laufenden Ausgaben heraus. Abziehbare Vorsteuer wird separat angesetzt. Die AfA kommt anschließend aus dem bestätigten Anlageneintrag. Keine doppelte Erfassung desselben Nettokaufpreises als Ausgabe und AfA.
- Ergänzungen enthalten bereits den ermittelten steuerlichen Betrag. Jahreswechsel-Korrekturen, Sachentnahmen und Pauschalen müssen mit Quelle/Berechnung dokumentiert werden. Verknüpfte Beleggrundlagen werden auf Änderungen überwacht.

Beispiel mit ausschließlich synthetischen Zahlen: betriebliche Softwarezahlung 119,00 €, darin 19,00 € abziehbare Vorsteuer → 100,00 € EDV + 19,00 € Vorsteuer. Bei einer geschäftlichen Bewirtung mit denselben Beträgen und erfüllten Voraussetzungen: 70,00 € abziehbarer Nettoteil + 19,00 € Vorsteuer; 30,00 € Nettoteil separat nicht abziehbar.

## Was der KI-Fortschritt bedeutet

**Schritt beantwortet** heißt: Eine vollständige, formal geprüfte Antwort des lokalen Modells wurde gespeichert. Es ist keine steuerliche Freigabe.

Die Leser erhalten sämtliche Zeichen des gespeicherten Dokumenttexts in Abschnitten. Unter **Auftrag und gelesene Textabschnitte** stehen Umfang und Lesefortschritt. Extrahierter oder manuell eingetragener Text ist keine vollständige visuelle Prüfung der Originaldatei. Scans ohne Text sind ausdrücklich als solche erkennbar; den Text bei der Unterlage ergänzen. Die Zuordnungsvorschläge verwenden Zusammenfassungen der verknüpften oder ausdrücklich zusätzlich ausgewählten Dokumente.

Arbeiter und Prüfer sehen die Antworten des jeweils anderen nicht. Der Koordinator erhält danach beide Vorschläge pro Zahlung. Unterschiede in Position oder Steuerbetrag werden zusätzlich durch das Programm markiert. Modelle können trotzdem irren.

Bei einem Abbruch: Ollama prüfen und **Prüfung fortsetzen** wählen. Fertige Schritte werden nicht wiederholt. Haben sich Daten oder Modelle geändert, ist eine neue Prüfung erforderlich. Ein zu großer Kontext wird nicht still gekürzt; den Auftrag kürzen oder das Kontextfenster unter Einstellungen erhöhen. Die verfügbare GPU-/RAM-Kapazität muss dafür ausreichen.

## Speicherverhalten und Grenzen

Eingaben in den EÜR-Formularen werden als Entwürfe gespeichert. Gesicherte Entwürfe lassen sich im EÜR-Bereich und in der Übersicht fortsetzen. Nach Wiederaufnahme ist eine neue Bestätigung erforderlich. Geänderte Zahlungen, verknüpfte Belege oder Steuerprofile führen dazu, dass betroffene Ansätze bis zur erneuten Bestätigung aus der Berechnung genommen werden. Ein geänderter Jahresstand setzt den Jahrescheck zurück. Die Sicherung enthält auch EÜR-Zuordnungen, Anlagen und KI-Schritte.

Die Auswertung bleibt ein **Arbeitsentwurf aus bestätigten Positionen**, gegebenenfalls mit offenem Rest. Die Differenz ist vor weiteren steuerlichen Gewinnkorrekturen. Es sind nicht sämtliche EÜR-Felder, besonderen Kfz-Fälle, Anlage SZ, Entnahmen/Einlagen und Gewinnkorrekturen umgesetzt. Die Vollständigkeit deiner tatsächlichen Konten, Zahlungen und Unterlagen kann das Programm nicht automatisch feststellen. Keine Berechnung oder Übermittlung der Umsatzsteuer-, Gewerbesteuer- oder Einkommensteuererklärung.

Die Formularzuordnung ist auf **2025** beschränkt. Andere Jahre sind dafür gesperrt, bis ihre Zuordnung gesondert eingerichtet und geprüft wurde.

Amtliche Grundlage für die Positionsauswahl: [ELSTER – Anleitung zur Anlage EÜR 2025](https://www.elster.de/elsterweb/helpGlobal?themaGlobal=help_euer_ufa_77_2025). Die Anwendung prüft die steuerlichen Voraussetzungen einzelner Ansätze nicht automatisch.

## Bereits vorhandene Jahresprüfungen

Die frühere **Jahr prüfen**-Funktion im KI-Chat bleibt eine Prüfung gespeicherter Buchungsangaben. Sie ist von der neuen EÜR-Bearbeitung getrennt. Alte Ergebnisse werden dadurch nicht nachträglich zu einer fertigen EÜR.

## Deinen Gemma-Abbruch aus 0.3.7 fortsetzen

Nach dem Update **Arbeitsjahr 2025 → KI-Chat** öffnen und bei deiner vorhandenen abgebrochenen Jahresprüfung **Prüfung fortsetzen** wählen. **Du brauchst keine neue Jahresprüfung und keinen erneuten Kontoauszug-Upload.** Der fertig gespeicherte Arbeiterstand wird übernommen. Voraussetzung: Seit dem Abbruch wurden keine relevanten Buchungen, Quellen, Profile oder Modelle geändert. Bei geänderten Daten erklärt die Anwendung, warum eine neue Prüfung nötig ist.

Der Fehler „Die KI-Rückmeldung ist leer oder zu lang“ kam aus einer zu strengen Hinweisprüfung:

- **Kein weiterer Hinweis:** Ein leerer Zusatzkommentar beendet den Lauf nicht mehr. Die Anzeige sagt ausdrücklich, dass kein zusätzlicher Hinweis angegeben wurde; daraus wird keine steuerliche Freigabe.
- **Langer vollständiger Kommentar:** Der Originaltext wird vollständig gespeichert. Die bisherige Grenze von 500 Zeichen führt nicht mehr zum Abbruch.
- **Prüfbedarf:** Ein konkreter Grund bleibt erforderlich. Fehlen Buchungen, sind Zuordnungen doppelt oder passt das Antwortformat nicht, wird keine vollständige Prüfung vorgetäuscht.
- **Kleinere Abschnitte:** Ein nach Wiederholung weiterhin ungültiger Abschnitt wird automatisch geteilt, bei Bedarf bis auf eine einzelne Buchung. Fertige Abschnitte werden nicht erneut angefordert.

Die Box zeigt jetzt **Arbeiter**, **Prüfer** und **Zusammenfassung** getrennt. Bei deinem gemeldeten Stand lautet das: **Arbeiter 106 von 106 – abgeschlossen; Prüfer 0 von 106 – unterbrochen; Zusammenfassung – wartet.** Die missverständliche gemeinsame Anzeige „0 von 106“ entfällt.

## Eine neue Jahresprüfung starten

1. **Arbeitsjahr 2025 → KI-Chat → Jahr 2025 prüfen** wählen. Ollama muss laufen und die drei Modelle müssen unter **Mehr → Einstellungen** ausgewählt sein. Du musst weder Buchungen neu eintragen noch Kontoauszüge erneut hochladen.
2. Die Box **Zahlungen 2025** zeigt die vom Programm berechneten betrieblichen Einnahmen, Ausgaben und den Zahlungssaldo. Grundlage sind dieselben aktiven, als betrieblich eingeordneten Zahlungen wie auf der Übersicht. Die KI berechnet diese Summen nicht selbst.
3. Arbeiter und unabhängiger Prüfer erhalten alle gespeicherten Buchungen des ausgewählten Zahlungsjahres in kleinen Abschnitten. Der Fortschritt nennt Rolle und Abschnitt; fertige Rückmeldungen werden sofort gespeichert. Der Koordinator fasst anschließend die nächsten Schritte zusammen.
4. **Zahlungen und Prüfpunkte** öffnen. Zuerst siehst du Zahlungen mit offenen Punkten, nach Monaten geordnet. Unter **Alle** bleiben auch die übrigen Zahlungen erreichbar. Über **Zahlung öffnen** kannst du Einordnung, Notizen und Belegverknüpfung bearbeiten.
5. Bei Antwortlimit oder Unterbrechung **Prüfung fortsetzen** wählen. Fertige Abschnitte werden nicht erneut gelesen. Das gilt auch nach dem Schließen und Neustarten der Anwendung. Wurden inzwischen Zahlungen, relevante Quellen, Steuerprofil oder Modelle verändert, eine **neue Prüfung mit dem aktuellen Stand** starten.

**Dein Screenshot:** 810,82 € betriebliche Einnahmen − 965,23 € betriebliche Ausgaben = **−154,41 € Zahlungssaldo**. Diese Zahlen wurden nur als Testbeispiel verwendet, nicht in deine Anwendung eingetragen. Solange du den Datenbestand nicht änderst, müssen Übersicht und neue Jahresprüfung dieselben betrieblichen Summen zeigen. Die 41 offenen Zahlungen aus dem Screenshot sind eine Prüfliste, kein zusätzlicher Geldbetrag und nicht automatisch 41 fehlende Rechnungen.

Die neuen Hinweise unterscheiden **kein gesonderter Beleg verknüpft**, **Nutzerangabe „Kein Beleg“** und **Beleg verknüpft, Inhalt noch nicht geprüft**. Ein technisch nicht gelesener Beleg wird nicht als nachweislich fehlende Datei bezeichnet. Private Zahlungen und Eigenüberträge werden getrennt gezählt; gemischte Zahlungen werden separat und vor einer steuerlichen Anteilsberechnung angezeigt.

Alte Jahresantworten können falsche Euro-Summen enthalten. Sie bleiben gespeichert, sind deutlich gekennzeichnet und eingeklappt. Starte einmal die neue Jahresprüfung. Sie kann einen in 0.3.6 abgebrochenen Chat nicht in einzelne gespeicherte Abschnitte zurückverwandeln; die neue Fortsetzung gilt für ab 0.3.7 gestartete Prüfungen.

**Umfang:** Die Jahresprüfung prüft gespeicherte Buchungsangaben und Belegverknüpfungen. Sie liest nicht automatisch alle Originalbelege vollständig und erstellt keine fertige EÜR oder ELSTER-Zeilenzuordnung. Der Zahlungssaldo ist noch kein abschließend geprüfter steuerlicher Gewinn oder Verlust. Es wird nichts an das Finanzamt gesendet.

## 2. Deinen vorhandenen Auszug weiterbearbeiten

**Zahlungen → Kontoauszüge → Öffnen.** Falls eine Importvorschau erscheint: **Zahlungsliste bearbeiten**. Die Datei muss nicht erneut hochgeladen werden.

**Weiterhin enthalten für deinen Februar-Abgleich:** Eine Folgeseite mit derselben eindeutig erkennbaren Auszugsnummer und passenden Kontoangaben wird automatisch mitgerechnet. Du solltest beim betreffenden Auszug **PDF-Seiten 3, 4** zusammen sehen, statt einer gesonderten Gruppe „Weitere PDF-Seiten“.

Bei den gemeldeten Beträgen ergibt sich: **4,61 € + 42,21 € − 51,19 € = −4,37 €**. Die Abschlussbuchung beträgt dabei **−16,82 €**. Diese Werte sind ein Beispiel anhand der gemeldeten Liste, keine Änderung deiner Daten.

Steht bei der Abschlussbuchung noch ein Datumshinweis, vergleiche die angebotene **Originalzeile** mit dem PDF. Steht dort beispielsweise **27.02.**, verwende diesen Buchungstag statt des 28.02. aus dem Gebührenzeitraum. Über **Diese Originalzeile übernehmen** erfolgt die Korrektur erst nach deinem Klick; anschließend die Einordnung erneut bestätigen. Ohne sichere Fundstelle keine Daten nur zum passenden Saldo ändern.

Bereits gespeicherte KI-Hinweise bleiben unter **Hinweise des ursprünglichen Lesevorgangs** sichtbar. Notiere unter **Was hast du geprüft?** kurz deine tatsächliche Prüfung, z. B. „Abschlussbetrag und Buchungstag mit Originalzeile verglichen.“ Bei verbleibenden unbekannten Seiten bitte deren Originalkopf und Zahlungszeile prüfen; das Programm verbindet keine Seiten allein aufgrund gleicher Beträge.

Jeder offene Monat zeigt einen verständlichen Status:

| Anzeige | Bedeutung / nächster Schritt |
|---|---|
| **Kontrollwerte passen** | Die vorhandenen Bank-Kontrollwerte passen zur aktuellen Zahlungsliste. Einordnung und Original trotzdem prüfen. |
| **Abweichung ansehen** | „Was stimmt noch nicht?“ zeigt PDF-Werte, deine Summen und die genaue Differenz. |
| **Zahlungen abgleichen** | Eine Originalzeile fehlt, ist doppelt zugeordnet oder eine Angabe passt nicht. Direkt bei der Zahlung stehen Vergleich und Erklärung. |
| **Am Original prüfen** | Ausreichende Kontrollwerte fehlen. Das Programm behauptet keine vollständige rechnerische Prüfung. |

Beim Bankabgleich zählen auch private Zahlungen und echte, bereits anderweitig erfasste Bewegungen. „Keine eigene Zahlung“ ausgeschlossene Gebühren-Unterzeilen zählen nicht mit.

Beispiel: Anfang 152,99 € + Eingänge 10,00 € − Ausgänge 2,00 € = 160,99 €. Steht im gelesenen PDF-Endstand 161,99 €, zeigt die Tabelle **1,00 € Differenz**. Ursache kann eine fehlende Zahlung, ein falsches Vorzeichen oder ein falsch gelesener Kontrollwert sein; die Differenz allein beweist nicht, welche Ursache vorliegt.

Bei einem Auszug über mehrere Monate steht ausdrücklich dabei, dass die Kontrollwerte gemeinsam gelten. Es werden keine nicht vorhandenen Monatssalden erfunden.

## 3. Einen Monat fertigstellen

1. Je Zahlung **Privat** oder **Betrieblich** wählen. Bei Unsicherheit: **Mehr → Später klären**. Datum, Empfänger, Zweck und Notiz stehen unter **Details & Notiz**.
2. **PDF öffnen** oder die aufklappbaren Originalstellen zum Vergleichen verwenden. **Fehler prüfen** aktualisiert den ganzen Abgleich. Er läuft auch nach dem Speichern automatisch.
3. Stimmen die Zahlungen: unten **Ausgewählte Monate und Einordnung am Original geprüft** bestätigen.
4. Beim fertigen Monat **Diesen Monat freigeben** wählen. Ein anderer, unabhängiger Monat darf noch ungeklärt sein.
5. Der übernommene Monat verschwindet aus der offenen Prüfung. Seine Zahlungen stehen im Dashboard. Unter **übernommene Monate · Prüfverlauf** findest du den gespeicherten Abgleich wieder.

**Alle offenen Monate freigeben** ist möglich, wenn du alle verbliebenen Monate geprüft hast. Eine mögliche manuelle Doppelung öffnet zuerst einen Abgleich: vorhandene Zahlung verknüpfen, bewusst auslassen oder echte zusätzliche Zahlung bestätigen. Erst danach wird dieser ausgewählte Teil übernommen.

## 4. Trotz verbleibender Saldenabweichung übernehmen

Wenn du das Original selbst geprüft hast:

1. Im betroffenen Monat **Trotz Abweichung übernehmen · Original selbst geprüft** anhaken.
2. Unter **Was hast du geprüft?** kurz und konkret notieren, was du verglichen hast und was noch unklar bleibt (mindestens zehn Zeichen).
3. Den Original-Prüfhaken unten setzen und **Diesen Monat freigeben** wählen.

Die Abweichung wird dadurch nicht als behoben markiert. Zahlen, Zeitpunkt und Notiz bleiben im Prüfverlauf erhalten; bei übernommenen/verknüpften Zahlungen bleibt ein Hinweis. Freigeben bedeutet **im lokalen Dashboard speichern**, nicht ans Finanzamt senden.

Fehlende echte Originalzahlungen, falsche Quellenzuordnung, ungelesene Seiten, ungültige Beträge/Währungen oder ein falsches Konto können nicht mit diesem Haken übergangen werden. Die Anzeige nennt den noch nötigen Originalabgleich.

## 5. Die drei lokalen KIs fragen

Im Zahlenabgleich **3 KIs um Prüfhilfe bitten** wählen. Ollama muss laufen; die drei Rollen müssen unter **Mehr → Einstellungen** eingerichtet sein. Arbeiter und Prüfer sehen unabhängig denselben Ausschnitt, der Koordinator vergleicht anschließend beide Antworten. Dies kann einige Minuten dauern.

Die KI-Antworten sind zusätzliche Vorschläge, keine automatische Korrektur oder Freigabe. Die Rechenprüfung funktioniert ohne KI. Ist Ollama nicht erreichbar, bleiben die Differenz und die manuelle Bearbeitung verfügbar. Bei langen Auszügen erhält die KI höchstens 80 zugehörige Zahlungszeilen; der Rechenabgleich selbst umfasst alle zugeordneten Zeilen.

## 6. Falsche oder schon erfasste Zeilen auslassen

| Auswahl bei der Zahlung | Wirkung |
|---|---|
| **Auslassen → Schon erfasst / doppelt** | Echte Bankbewegung nicht erneut ins Dashboard übernehmen. Sie zählt weiter beim Bankabgleich mit. Ein vorhandener Eintrag wird nicht gelöscht. |
| **Auslassen → Keine eigene Zahlung** | Z. B. Gebühren-Unterposition oder zusätzlich gelesene Kopie ausschließen. Die tatsächliche Originalbuchung bleibt erforderlich. |

Beispiel: Abschluss 10 €, darunter 6 € Kontoführung + 4 € Buchungsposten → **einmal 10 €**. Separat gebuchte Gebühren bleiben eigene Zahlungen.

Unter **… ausgelassen · ansehen / rückgängig** kannst du offene Zeilen wieder aufnehmen. Fehlende bekannte Originalzahlungen lassen sich auch direkt im Prüfungshinweis zurückholen. Datum-/Betragskorrekturen aus einer vorgeschlagenen Originalzeile benötigen erneute Einordnung; Notizen bleiben erhalten.

## 7. Speichern, Papierkorb und historische Monate

- **Änderungen gespeichert** abwarten, bevor du den PC ausschaltest. Einordnungen, Notizen und Prüfhinweise werden schon vor der Freigabe als Entwurf gespeichert.
- Freigegebene Monate bleiben nach Neustart erhalten und werden nicht noch einmal importiert. Ihre Originalzeilen werden nicht durch einen alten Entwurf überschrieben. Weitere Bearbeitung dieser Zahlungen erfolgt im Dashboard.
- Nach der ersten Monatsfreigabe ist erneutes vollständiges KI-Lesen dieses Originals gesperrt, damit die bereits verwendeten Quellen nicht umsortiert werden. Offene Zeilen kannst du weiter bearbeiten und ergänzen.
- Unter **Kontoauszüge → Entfernen** kommt ein Upload in den Papierkorb. Bereits übernommene Zahlungen bleiben erhalten. **Papierkorb** ist oben bei Kontoauszügen und Unterlagen erreichbar.
- Beim erneuten Hochladen derselben entfernten PDF/CSV erscheint **Wiederherstellen & öffnen**. Es öffnet denselben gespeicherten Stand, ohne doppelte Zahlungen oder neue KI-Auswertung.
- Bei einem vollständig übernommenen PDF öffnet **Prüfverlauf** die gespeicherten Monatsfreigaben. **Original** öffnet den Auszug.

## Weitere Erfassung und Grenzen

CSV-Importe von Volksbank, N26 und FYRST, manuelle Bar-/Bankzahlungen, optionale Rechnungsdatei, „Kein Beleg“, Kontenarchiv und Darkmode bleiben vorhanden. Das Rechnungspapier kann nach der Übernahme an die jeweilige Zahlung angehängt werden. Eine private Bankbewegung braucht keinen betrieblichen Rechnungsbeleg; eine betriebliche Zahlung ohne Rechnung bleibt fachlich prüfbedürftig.

Die Anwendung bereitet Unterlagen vor. Sie erstellt weiterhin **keine fertige EÜR, Steuerberechnung, USt-Voranmeldung oder ELSTER-Übermittlung**. Ein grüner Bankabgleich bestätigt weder die steuerliche Absetzbarkeit noch Vorsteuer. Keine Verbindung zu echten Bankkonten und keine Banküberweisungen.

