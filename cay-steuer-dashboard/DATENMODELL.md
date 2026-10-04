# Datenmodell und Importregeln · 0.3.6

## Konten und Bankimport

| Tabelle | Zweck / zentrale Felder |
|---|---|
| `bank_accounts` | Eigene Konten: ID, Bank, Rolle Haupt-/Steuer-/Altkonto, IBAN, Status geplant/aktiv/geschlossen, vorläufiger Bereich, Rücklagenquote als INTEGER |
| `bank_imports` | Original-CSV/PDF als BLOB, SHA-256, Konto, Arbeitsjahr, Codierung, Trennzeichen, Mapping, persistente Vorschau, Übernahmeergebnis und Zeitpunkte |
| `bank_rows` | Unveränderte Bankdaten: Buchungs-/Wertstellungsdatum, **vorzeichenbehafteter `amount_cents INTEGER`**, Währung EUR, Partner, Gegen-IBAN, Referenz, Rohfelder, Dublettenschlüssel, Import-/Zeilenbezug |
| `bank_transfers` | Einmalige Verknüpfung einer ausgehenden und einer eingehenden Kontoseite, positiver Betrag in Cent, Begründung, automatischer IBAN-Abgleich oder Nutzerbestätigung |
| `transactions` | Arbeitsaufzeichnung: positiver `amount_cents INTEGER` + Richtung, Kategorie, Bereich, Zahlungsart (`bank`/`cash`/`unknown`), Bargeldquelle, Konto, optional eindeutiger Bankzeilenbezug, Belegzuordnungen und Prüfhaken |
| `transaction_documents` | Mehrere Originalbelege je Zahlung; Fremdschlüssel verhindern nicht existente Zuordnungen |

SQLite-CHECK auf Bankbeträgen erzwingt den tatsächlichen Speichertyp INTEGER und einen Nichtnullbetrag. Trigger auf Zahlungseinträgen verhindern FLOAT-Beträge auch außerhalb der regulären Python-Eingabe. Rechnen beim Parsen erfolgt mit Decimal und anschließender Integer-Konvertierung, nicht binären Fließkommazahlen. Umrechnungen in Anzeigeformat passieren erst zur Darstellung.

Der Import ist eine atomare Transaktion: entweder alle akzeptierten Bankzeilen/Zahlungen/Verknüpfungen oder keine. Wiederholtes Übernehmen derselben Import-ID erzeugt keine zweite Buchung. Eindeutige Bank-IDs werden pro Konto dedupliziert; widersprüchliche Daten zu gleicher Bank-ID sperren den Import. Ohne ID: Fingerprint aus Daten plus Auftretensnummer, damit mehrere identische echte Zahlungen nicht pauschal zu einer kollabieren. Erneute/überlappende Exporte werden verglichen. Echte Zweitbuchungen lassen sich ausdrücklich bestätigen. Ähnliche Datensätze und mögliche manuelle Vorbuchungen sind Klärungsfälle.

Eigenübertrag-Regeln sind deterministisch. Nur eine bekannte eigene Gegen-IBAN macht eine einzelne Bankzeile automatisch neutral. Paarung zusätzlich nur bei gegenseitig passenden IBANs, gleichem EUR-Betrag mit Gegenzeichen, verschiedenen Konten, maximal fünf Tagen Abstand und eindeutiger Zuordnung. Unklare Kandidaten benötigen Bestätigung. Verknüpfungen funktionieren über Steuerjahre hinweg. Finanzamtszahlungen sind keine Eigenüberträge.

Barausgaben haben bewusst keinen Bankzeilenbezug. Für Videoeinkäufe werden Zweck und betrieblicher Anteil dokumentiert; Bewirtungen speichern Ort, Teilnehmer und Anlass. Eine Geldautomaten-/Bargeldabhebung wird als ungeklärte Bargeldbewegung geführt und nicht automatisch als Aufwand gebucht.

Die ursprüngliche Bankbuchung wird durch spätere Belegzuordnung nicht geändert. Betrag, Richtung, Buchungstag und Konto einer verknüpften Zahlung sind gegen Änderungen geschützt. Kategorien/Notizen/Bereich bleiben Arbeitsdaten; erkannte Überträge dürfen nicht als Ertrag/Aufwand umklassifiziert werden. Diese Version ist vorbereitende Erfassung; ein vollständiges fachliches Festschreibungs-/Stornokonzept folgt vor formaler Buchführung.

## Dokumente, Gedächtnis und Recht

- `documents`: Originaldateiname, interne Datei, SHA-256, Art (einschließlich `Kontoauszug`), Arbeitsjahr, Daten, Textauszug und Notizen. Originalbytes werden atomar geschrieben und nicht durch Textkorrekturen ersetzt.
- `drafts`: persistente Formulardaten einschließlich Dateiauswahl bei Dokumenten und direkt ausgewählten Rechnungen einer Buchung. Keine endgültige Buchung.
- `requests`: Wiederholungskennungen für neue manuelle Datensätze, zusammen mit dem eigentlichen Datensatz atomar gespeichert.
- `tasks`: Arbeitsjahr, Quelle/Fundstelle, Vorbereitung, Frist, Prüfstatus, Erledigungsnachweis und Kalendersequenz.
- `memory_facts`: sachliche Angabe mit Jahr, Quelle, offen/bestätigt/überholt; eine Quellenänderung öffnet bestätigte Fakten erneut.
- `chat_runs`: Frage, persistierter Kontextausschnitt, Dokumentverweise, Ergebnisse aller drei Modelle, Modellnamen/-Digests, Kontextgröße, Promptversion, Status und Fehler.
- `analyses`: getrennte Dokumentlesungen und Koordinator, Quellhash, Zwischenstand; ein Neustart markiert abgebrochene Auswertungen sichtbar als Fehler.
- `legal_versions`, `legal_units`, `legal_checks`: Originalfassungen, Quelladresse, Hash, Abrufdatum, Abschnittstexte, geprüfter Gültigkeitsbereich und Aktualisierungsfehler. Ein Abruf ist keine fachliche Freigabe.
- `audit`: Änderungen mit Vorher-/Nachherwerten; selbst lokal gespeichert, kein unangreifbares externes Journal.

## Haltbarkeit

Daten liegen außerhalb des Programmordners. SQLite nutzt Rollback-Journal und FULL-Synchronisierung mit serialisierten Schreibvorgängen. Damit verwendet die Version den zuvor betrachteten WAL-Modus nicht. Die App erlaubt nur eine laufende Instanz je Datenablage. Fehlt eine bekannte Datenbank, wird nicht still eine leere neue angelegt.

Sicherung über SQLite Backup API plus Originaldateien; Entwürfe, Bankoriginal-BLOBs, Chat und Rechtsquellen sind Bestandteil der Datenbank. Prüfung: Datenbankintegrität, Fremdschlüssel, SHA-256 aller Originalbelege und Bankoriginale. Wiederherstellung nur in einen neuen Ordner; Pfadtraversal und doppelte ZIP-Dateinamen werden zurückgewiesen. Die optionale Aktivierung wechselt den nächsten Startpfad; der alte Bestand bleibt erhalten.

Lokale Sicherungen behalten die jüngsten 48 Stände, dazu bis zu 30 Tages- und 12 Monatsstände. Zusätzliche Kopien auf dem gewählten externen Datenträger werden nicht automatisch gelöscht. Diese Backup-Rotation ist keine steuerrechtliche Lösch- oder Aufbewahrungsregel. Originalunterlagen werden nicht zeitgesteuert gelöscht.

## Jahresprofil und Quellenabruf – 29.09.2026

`tax_profiles`: Primärschlüssel `year INTEGER`, `vat_status`, `taxation`, `filing_status`, `source_note`, `updated_at`. Jahresprofile sind separate Datensätze und werden nicht automatisch ins Folgejahr kopiert. Nur der alte ausdrücklich 2025 betreffende Abgabestatus wird migriert. Allgemeine alte USt-Angaben bleiben zur manuellen Zuordnung erhalten. Profil plus persönliche Notizen werden atomar gespeichert und auditiert. Die SQLite-Sicherung enthält die neuen Tabellen automatisch.

`legal_checks.attempted_at` ergänzt den Zeitpunkt des letzten Versuchs. `checked_at` behält bei Fehlern den letzten Erfolg. Fehler und vorhandene Fassungen bleiben nach Neustart sichtbar. Das Download-API akzeptiert nur IDs aus dem amtlichen Quellenkatalog, keine frei übergebenen URLs. Vorübergehende Fehler werden maximal einmal wiederholt; Zertifikats- und Zugangssperren werden nicht umgangen.


## Erweiterungen 0.3.0

- `bank_accounts.opened_on/closed_on`: Nutzungszeitraum. Archivieren ändert keine Bankzeile. Neue Bank-/manuelle Zuordnungen außerhalb des Zeitraums werden abgewiesen; unveränderte historische Vorgänge bleiben bearbeitbar.
- `bank_imports.source_kind/statement_document_id`: Format und optionaler PDF-Dokumentbezug. Erneuter identischer Upload verwendet die gespeicherte Vorschau; ein ausdrücklich gewählter Formatwechsel baut die Vorschau neu auf.
- `intake_jobs`: PDF-/Klassifizierungsauftrag mit Status, Fortschritt, Konto/Jahr, Dokument-/Importbezug, Modellnamen, Seiten/OCR-Text, beiden Lesungen, Koordinator, offenen Punkten und Korrekturen. Jede Änderung erzeugt einen Audit-Eintrag, damit die Sicherungsüberwachung auch Zwischenstände erkennt.
- `transactions.receipt_state/receipt_note`: `pending` oder `none`; tatsächliche Dateizuordnung über `transaction_documents`. Datei vorhanden ist ein Zuordnungsstatus, keine steuerliche Anerkennung.
- `transactions.statement_document_id`: Kontoauszug bleibt getrennt von Rechnungsbelegen. Zusätzlich wird der ursprüngliche Import-/Zeilenbezug in der Arbeitsansicht ausgegeben.

PDF-Ablauf seit 0.3.2: Original -> Text/OCR -> erkannter Tabellenleser oder zwei unabhängige KI-Lesungen -> mechanischer Abgleich -> gespeicherte Monatsprüfung -> ausdrücklich bestätigte atomare Übernahme. Die gemeinsame CSV/PDF-Dublettenprüfung läuft dabei im Hintergrund; offene Zuordnungen erhalten einen zusätzlichen Dialog. Änderungen von Betrag/Datum sind vor Übernahme möglich und benötigen weiterhin eine Originalfundstelle. Nach Übernahme bleiben Bankoriginaldaten unverändert.

Schutz: widersprüchliche PDF-Lesungen bleiben Prüfpunkte; bekannte nicht passende Salden werden im aktuellen Monatsworkflow mit genauen Differenzen angezeigt. Eine bewusste Freigabe verlangt eigenen Prüfhaken und Begründung; der Hinweis bleibt erhalten. Ohne erkennbare Salden ist keine technische Vollständigkeitsbestätigung möglich. CSV/PDF-übergreifende Ähnlichkeit (Datum/Betrag gleich, Text abweichend) wird zum Zuordnungsfall, nicht still zusammengeführt. Keine Übernahme allein durch drei Modellstimmen.

Automatische Klassifizierung arbeitet in Achtergruppen. Antwortzeilen müssen eindeutig zu Eingabezeilen passen. Nutzereingaben markieren `user_reviewed` und haben Vorrang vor späteren Antworten. Unklare Bareinzahlungen, Abhebungen und Steuerarten bleiben offen. Die Prüffunktion für Quelldatum/-betrag beweist weder betriebliche Veranlassung noch Vorsteuerabzug.


## Erweiterungen 0.3.1

- `upload_trash`: wiederherstellbare Entfernung mit Jahr, Anzeigename, betroffenen Dokument-/Import-/Job-IDs, vorherigen Jobzuständen und Zeitpunkten. Keine physischen Dateilöschungen.
- `documents.trash_id`, `bank_imports.archived/trash_id`, `intake_jobs.archived/trash_id`: zusammenhängende Uploads verschwinden atomar aus Arbeitslisten. Finanzielle `transactions` und unveränderliche `bank_rows` bleiben erhalten.
- `intake_jobs.run_token`: jede Ausführung und Entfernung erhält einen neuen Token. Veraltete Worker dürfen auch nach Wiederherstellung nicht mehr schreiben. Ein bereits laufender Ollama-Aufruf kann noch enden; sein Ergebnis wird verworfen.
- `intake_jobs.error_code`: gezielte Rückmeldung bei benötigtem PDF-Öffnungskennwort. Kennwort selbst weder in Datenbank/Entwürfen/Audit noch in Modellprompts.
- Entfernen-Vorschau mit Token: relevante Änderungen der betroffenen IDs, Jobzustände oder Anzahl aktiver Zahlungen erfordern einen neuen Dialog. Wiederherstellung ist idempotent und markiert zuvor laufende Jobs als erneut startbar.
- `pdfio.py`: gemeinsame PDF-Öffnung für Dokumente und Auszüge. `decrypt('')` bei verschlüsseltem Original; `is_encrypted` allein ist kein Ablehnungsgrund. Lesen verändert das Original nicht. `pypdf[crypto]` liefert die AES-Abhängigkeit.
- Bestehende falsche PDF-Schutzmeldungen werden einmalig anhand unveränderter Originale korrigiert, wenn noch kein Dokumenttext vorliegt. Die Migration überschreibt keine Nutzereingaben.

## Erweiterungen 0.3.2

- Keine neue Finanzdatentabelle. `intake_jobs.result_json` enthält weiterhin die persistente Prüfliste und zusätzlich `page_status`, `all_pages_read`, erkannte Tabellenprüfungen und Hinweise zur optionalen KI-Einordnung. Nutzerentscheidungen liegen in den gespeicherten Review-Zeilen mit `scope`, `category`, `review_note` und `reviewed`.
- `statements.py` erkennt ausschließlich das unterstützte EUR-Volksbank-Layout mit VR-GiroBusiness, datierten Soll-/Haben-Zeilen und Auszugsnummer/Jahr. Gebühren-Unterpositionen, Überträge, Anfangs-/Endsalden und Hinweisseiten werden nicht als Zahlungen übernommen. Die Bankzeilen werden nach Buchungstag gruppiert; eine abweichende Wertstellung verschiebt sie nicht still in einen anderen Monat.
- Jede erkannte Tabellenzeile erhält eine Quellenkennung aus Seite, Zeile und Originaltext. Freigabe erfordert die vollständige Menge dieser Quellenkennungen. Fehlende oder doppelt zugeordnete echte Originalzeilen sperren weiterhin. Für Salden-/Umsatzabweichungen gilt ab 0.3.5 die dokumentierte Monatsfreigabe unten. Das gilt auch bei übereinstimmenden KI-Antworten.
- Eine von der KI umformulierte Fundstelle kann nur bei eindeutig passendem Datum, vorzeichenbehaftetem Betrag und passendem Kontext auf die tatsächliche Tabellenzeile zurückgeführt werden. Unbekannte Layouts brauchen weiter einen belegbaren Originaltext. Unbelegte Zeilen bleiben als fehlerhafte Entwürfe erhalten; ein Seitenfehler verhindert das Weiterlesen anderer Seiten nicht.
- Optional drei getrennte KI-Rollen für die Einordnung der erkannten Tabellenzeilen. Uneinigkeit bleibt offen. Betrag und Datum bleiben durch den Tabellenleser bestimmt; ein Ausfall der Einordnungsmodelle verwirft nicht die gelesenen Zahlungen.
- `POST /api/intake/pdf-approve`: vollständige Seitenprüfung, ausdrückliche Entscheidung je relevanter Zahlung und Gesamtbestätigung; danach gemeinsame Importvalidierung und atomare Speicherung. Ein erneuter Aufruf nach erfolgreicher Übernahme liefert das vorhandene Ergebnis. Bei offenen Dubletten wird nur die Vorschau gespeichert, noch keine neue Zahlung.
- Die Monatsansicht speichert Änderungen automatisch. Beim erneuten Lesen werden passende vorhandene Entscheidungen anhand von Seite, Datum, Cent-Betrag und Originalfundstelle übernommen; identische Vorkommen bleiben getrennt. Nicht mehr eindeutig passende Zeilen benötigen eine neue Prüfung.

## Oberfläche 0.3.2

`studio.css` führt die gemeinsamen Farb- und Flächenvariablen für Hell/Dunkel. Frühere parallele Darkmode-Farbblöcke wurden entfernt. `workspace.js` gestaltet den Einstieg, ohne eigene Zahlungstabellen oder Summenberechnungen einzuführen. Das Öffnen eines neuen Dialoginhalts setzt die Scrollposition zurück; gespeicherte Formularentwürfe öffnen bei der Wiederaufnahme auch übergeordnete eingeklappte Bereiche.

## Erweiterungen 0.3.3

- PDF-Review-Zeilen tragen `excluded: bool` und `exclusion_reason: already_recorded | not_payment`. Sie bleiben in `intake_jobs.result_json` erhalten; Auslassen ist keine physische Löschung.
- `already_recorded`: Originalzeile normalisieren und bei Quellen-/Saldenprüfung berücksichtigen; in der gemeinsamen Importvorschau `choice=skip` setzen. Bestehende Zahlung nicht ändern. `not_payment`: von Zahlungen/Summen ausschließen; vollständige Quellenmenge der erkannten echten Tabellenzeilen bleibt Pflicht.
- `bank_imports.preview_json.pdf_exclusions` dokumentiert ausgelassene Review-Zeilen mit Seite, Originalstelle und Grund. Die Prüfnote enthält die Entscheidung. Unabhängige andere Warnungen benötigen weiter eine dokumentierte Klärung. Keine neue SQLite-Tabelle und keine Migration von vorhandenen Zahlungen.
- `POST /api/intake/pdf-reopen` öffnet ausschließlich unbestätigte PDF-Vorschauen zur Bearbeitung. Gespeicherte Einordnungen/Zuordnungen werden übernommen; `pdf_checked=false` sperrt zwischenzeitlich die alte Vorschau. Bestätigte Importe bleiben unveränderlich.
- Bekannte Tabellen werden auch innerhalb gemischter PDFs seitenweise deterministisch gelesen. Originalzeilen und vorhandene Kontrollsummen bleiben prüfpflichtig. Markierte Gebührenaufschlüsselungen können als sichtbare, wiederherstellbare Ausschlüsse vorgeschlagen werden; Händler- oder Gebührenwörter allein reichen dafür nicht.
- Das Review-Formular verwendet eigene sichtbare Pflichtfeldprüfung statt nativer Browserblockaden hinter geschlossenen Detailbereichen. Der Server validiert weiterhin unabhängig. Die Reihenfolge im gespeicherten Entwurf bleibt stabil, wenn Zeilen zwischen Monatsliste und Ausschlussliste wechseln.

## Erweiterungen 0.3.4

- `POST /api/intake/pdf-check` prüft Zeilen ohne Buchung. `PDFReviewError.details` enthält konkrete Zeilenindizes, erfasste Werte, Erklärungen und bis zu drei belegte Originalkandidaten je Fehler. Maximal zwanzig fehlerhafte Zeilen pro Prüflauf werden gemeldet. Die zentrale HTTP-Fehlerantwort und der Browser erhalten diese strukturierten Details.
- Kandidaten stammen ausschließlich aus erkannten Originaltabellen. Eine passende Referenz, exakter Text sowie Datum/Betrag dienen der Zuordnung; unsichere Vorschläge bleiben als mögliche Ursache kenntlich. Bereits anderweitig zugeordnete Originalzeilen werden markiert. UI-Korrekturen ändern vor Bestätigung keine Bankbuchung.
- Automatische Reparatur nur einer nicht mehr existierenden Quellenkennung: vollständige normalisierte Originalstelle, Buchungstag und vorzeichenbehafteter Cent-Betrag müssen eindeutig identisch sein. Existiert die Kennung auf einer anderen Seite, ist eine ausdrückliche Korrektur erforderlich. Identische wiederholte Originalzeilen bleiben mehrdeutig.
- Veraltete Einzelzeilen-Lesefehler werden durch erfolgreiche aktuelle Quellenvalidierung ersetzt; Leserwidersprüche bleiben separat klärungsbedürftig. Bekannte Salden und die vollständige Quellenmenge werden unverändert geprüft.
- `UploadInTrash.details` liefert beim Kontoauszug-Upload einen Wiederherstellungshinweis mit Papierkorb-ID und erhaltenen Zahlungen. `restore_trash_id` löst nach erneutem Dateiabgleich die Wiederherstellung innerhalb derselben SQLite-Transaktion aus. Bei einem Folgefehler wird auch die Wiederherstellung zurückgerollt.
- Erneut gesendete Wiederherstellungsanfragen prüfen Datei-Hash/Jahr und bei CSV Konto gegen die bereits wiederhergestellten IDs. Neue/andere Dateien dürfen damit keine fremden Papierkorbeinträge aktivieren. `restored=true` verhindert automatisches erneutes Lesen oder Klassifizieren beim Öffnen des gespeicherten Stands.

## Erweiterungen 0.3.5: Monatsfreigaben und Zahlenabgleich

- `pdf_review.py` berechnet jedes Mal aus den aktuellen Beträgen (Cent-INTEGER) neu. Pro Originalauszug: Anfang, gelesener Endstand, errechneter Endstand, Einnahmen/Ausgaben und vorhandene Bank-Umsatzsummen mit einzelnen Differenzen. Originalstellen, PDF-Seiten, fehlende/doppelte Quellen, konkrete Zeilendiagnosen und nur mögliche Ursachen werden separat ausgegeben. Auszugsnummer ist keine angenommene Monatsnummer.
- Kontrollwerte gelten für die zugehörigen Auszugsseiten. Bei mehreren Buchungsmonaten im selben Auszug bleibt es ein gemeinsamer Vergleich. Fehlende Werte sind `null`; fehlende Kontrollwerte werden nicht zu Null oder einer erfolgreichen Vollständigkeitsprüfung umgedeutet.
- Tabelle `pdf_month_approvals`: Primärschlüssel `(job_id, month)`, Verweis auf Import, Zeitpunkt, eingefrorene Zeilen mit ursprünglichem Index, vollständiger Kontrollbericht für diesen Monat, Freigabenotiz und Teilergebnis. Bereits freigegebene Zeilen bleiben bei späteren Autosaves unverändert.
- Ein Original behält genau einen `bank_imports`-Datensatz pro Konto/Jahr/SHA. Zwischen Monatsfreigaben hat er Zustand `partial`; die Gesamtzahlen in `result_json` werden aus gespeicherten Monatsfreigaben abgeleitet. Der aktive Entwurf enthält nur die aktuell ausgewählten Importzeilen. Frühere Originalzeilen bleiben in `bank_rows` und den Monats-Snapshots erhalten.
- Freigabe und Monats-Checkpoint liegen in derselben SQLite-Transaktion. Ein Fehler rollt beide zurück. Wiederholte Monatsanfragen buchen nichts erneut. Ein wechselnder `pdf_selection_token` schützt vor Freigabe einer mittlerweile ersetzten Auswahl im alten Browserfenster.
- Vor der Übernahme: Quellen- und Vollständigkeitsprüfung für den gewählten Monat; Konto-/Datentypprüfung bleibt aktiv. Ein Fehler im unabhängigen Folgemonat blockiert nicht die ausgewählten geprüften Zeilen. Geteilte Auszugskontrollen bleiben dagegen sichtbar relevant für beide Monate.
- Nicht passende Salden/Umsatzsummen verlangen `overrides[month].accepted=true` und eine Notiz. Der unveränderte Zahlenvergleich wird gespeichert. Eine Notiz allein oder Modellmehrheit genügt nicht. Warnhinweis auch bei Verknüpfung mit manueller Zahlung, ohne deren alte Notiz zu entfernen.
- Nach einer Teilfreigabe ist ein neuer vollständiger Leselauf gesperrt, um die Quellenindizes bereits importierter Zeilen zu erhalten. Offene Zeilen können ergänzt/geändert werden. Entfernen und Wiederherstellen des Originals erhält die Checkpoints; keine Transaktion wird dabei gelöscht.
- API: `pdf-reconcile` liefert den aktuellen strukturierten Bericht, `pdf-approve` mit `months` übernimmt gezielt. Die alte Ganzdatei-Freigabe ohne `months` bleibt für unveränderte Alt-Aufrufe erhalten, einschließlich ihrer strengeren Saldenprüfung; die neue Oberfläche sendet immer Monate.
- `pdf-explain`: zwei unabhängige lokale Modellaufrufe, danach Koordinator. Zahlenbericht und max. 80 zugehörige Quellenausschnitte; Begrenzung wird mitgeliefert. Antworten werden im Audit gespeichert, dürfen aber weder Zeilen noch Freigaben ändern. Fehler führen zur manuellen Zahlenprüfung zurück.
- Das Dashboard fasst offene Prüfung und Teilimport zu einem sichtbaren Original zusammen. Bestätigte Monate sind ausgeblendet; gespeicherte Abgleiche bleiben unter Prüfverlauf zugänglich. Beides sind Import-/Dokumentationsstatus, keine steuerliche Anerkennung oder ELSTER-Übermittlung.

## Erweiterungen 0.3.6: Folgeseiten und Originalnachweise

- `page_identity` liest ausdrücklich bezeichnete Kontoauszugsnummer, Jahr, Kontonummer, eigene IBAN und Währung aus dem Seitenkopf unabhängig von `parse_page`. Datums-/Betragsähnlichkeit ist keine Seitenzuordnung.
- `attach_statement_pages` ergänzt eindeutig zugehörige, bislang unbekannte Seiten in den Kontrollgruppen. Widersprüchliche oder mehrdeutige Identität sowie abweichende wiederholte Kontrollwerte verhindern die Zuordnung. `page_links` dokumentiert Seite, wörtlichen Headernachweis und Erklärung; der Freigabe-Snapshot enthält diese Zuordnung.
- `partial_page_rows` liefert ausdrücklich datierte, mit PN und S/H gekennzeichnete Zahlungszeilen. Sie gelten als belegbare Einzelzeilen, nicht als vollständige Extraktion der übrigen Seite. `source_rows` vereinigt die vollständige bekannte Tabelle oder diese begrenzten Einzelbelege für Vergleich und Fehlerdiagnosen. Gebühren-Unterpositionen ohne solche Buchungszeilen werden nicht übernommen.
- Der Abgleich liest die gespeicherten Originaltexte bei jedem Aufruf neu. Vorhandene Entwurfswerte, Einordnungen und Notizen werden dabei nicht verändert. Finanzielle Originalkorrekturen bleiben explizite UI-Aktionen; die schon vorhandenen Freigaben behalten ihren damaligen Prüfbericht.
- Eine Folgeseite wird nicht als eigenes unprüfbares Fragment ausgegeben, wenn ihre Zugehörigkeit am Originalkopf belegt ist. Verbleibende unzugeordnete Seiten erhalten eine konkrete Erklärung ihrer fehlenden Zuordnung.


## Jahresprüfung ab 0.3.8

`chat_runs` enthält den unveränderlichen Datenstand einer Prüfung. `chat_steps` speichert Leserabschnitte und Koordinator separat. Nur `complete`-Schritte liefern Rückmeldungen für den Bericht. Bei einem wiederholt ungültigen Leserabschnitt wird der Elternschritt atomar auf `split` gesetzt und es werden zwei kleinere `pending`-Schritte angelegt. Verschachtelte Schrittschlüssel erhalten die Reihenfolge. Ein `split`-Elternschritt zählt weder als offene Arbeit noch als fertige Leserantwort; seine Diagnose bleibt erhalten. Die Aufteilung ändert keine Buchungen und keine ursprünglichen Geldwerte. Nach Neustart bleiben fertige Kindschritte erhalten.

`no_issue` darf ohne Zusatzkommentar vorliegen. Der gespeicherte Hinweis wird dann als Anwendungstext durch `note_defaulted` gekennzeichnet. Lange abgeschlossene Hinweisfelder bleiben erhalten. `review` benötigt einen konkreten Text. Der Status ist keine steuerliche Freigabe.

## EÜR-Arbeitsbereich ab 0.4.0

- `euer_allocations`: bestätigte Zuordnung pro Zahlung, separate Jahreszuordnung, Centbeträge, Anteile, Begründung und Fingerprint der aktuellen Zahlung/Belege/Jahresprofile.
- `euer_entries`: bestätigte Ergänzungen und manuelle Jahres-AfA mit Buchwertentwicklung; archivierte Einträge bleiben erhalten. Verknüpfte Anschaffungs- und Dokumentgrundlagen sowie Profilstand werden verglichen.
- `euer_reviews`: Jahrescheck auf einen konkreten Daten-Fingerprint bezogen.
- `euer_runs`, `euer_steps`: vollständiger Auftrag, unabhängige Leser, Eingabeabschnitte, validierte Antworten und Fortschritt. Beim Neustart werden offene Läufe als unterbrochen markiert; abgeschlossene Schritte bleiben unverändert.
- Die bestehenden Buchungstabellen und Originaldateien werden durch EÜR-Zuordnungen oder KI-Vorschläge nicht überschrieben. Neue Tabellen sind Bestandteil der SQLite-Sicherung.
