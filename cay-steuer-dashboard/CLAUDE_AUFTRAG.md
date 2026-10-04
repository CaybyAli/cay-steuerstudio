# Vollständiger Auftrag für Claude Code: Cay Steuerstudio überarbeiten

Du übernimmst mein vorhandenes Projekt **Cay Steuerstudio**. Ich heiße in diesem Projekt **Cay / CaybyAli**. Ich möchte, dass du den vorhandenen Stand gründlich verstehst und danach tatsächlich verbesserst: Oberfläche, Bedienabläufe, Codequalität und Zuverlässigkeit. Bleibe nicht bei einem Konzept, einer Fehlerliste oder einem hübschen Mockup stehen. Arbeite am funktionsfähigen Produkt.

## Mein Ziel

Ich brauche ein lokales, kostenlos betreibbares Steuer-Dashboard für mein Creator-Unternehmen (YouTube/Twitch) und die dazugehörige private Ablage. Das Autohaus ist kein Bestandteil dieses Projekts. Das Dashboard soll Belege, Bank-/Barzahlungen, Einordnung, offene Aufgaben, Fristen und eine nachvollziehbare Vorbereitung der EÜR zusammenführen. Spätere Erklärungsfunktionen müssen fachlich belastbar ergänzt werden; täusche heute keine fertige Steuererklärung vor.

Das Finanzamt macht Druck. Die vielen Abbrüche, Fehlermeldungen und Umwege haben mich Zeit gekostet. Ich bin kein Steuerexperte und möchte verständlich arbeiten können. Ich weiß nicht bei jeder Zahlung, welche Umsatzsteuerbehandlung oder welche Formularzeile richtig ist.

Mein Rechner: Windows, RTX 4090, Ryzen 9 7950X3D, 64 GB RAM. Die drei Assistenzrollen sind Arbeiter (Qwen), unabhängiger Prüfer (Gemma) und Koordinator (GPT-OSS), lokal über Ollama. Die tatsächlichen Modellnamen stehen in den Einstellungen; nicht blind neue Modelle herunterladen. Ich habe nach eigener Angabe ungefähr **100 € Claude-Code-Nutzungsguthaben**. Nutze das bewusst für überprüfbare Fortschritte. Das ist kein Auftrag, Guthaben auszuschöpfen oder weitere kostenpflichtige Dienste zu buchen.

## Zuerst verstehen, dann umsetzen

Lies `CLAUDE.md`, `docs/UEBERGABE_0.4.0.md`, `TESTBERICHT.md` und anschließend gezielt die relevanten Dateien. Prüfe den aktuellen Code selbst: Die Dokumentation ist eine Einstiegshilfe, kein Ersatz für Untersuchung. Starte die Anwendung mit separaten synthetischen Daten und bediene die wichtigen Abläufe im Browser. Halte kurz fest, was du beobachtest und priorisierst. Beginne danach mit der Umsetzung und überprüfe die Änderungen. Für normale reversible Code- und Designentscheidungen musst du mich nicht ständig fragen.

Arbeite in einem eigenen Git-Branch, zum Beispiel `claude/studio-redesign`. Erstelle kleine, verständliche Commits nach überprüften Arbeitsschritten. Bewahre einen startfähigen Stand und dokumentiere den Weg zurück. Produktive Daten nicht als Testdaten benutzen und die Anwendung nicht aus Versehen mit einer leeren Standardablage ersetzen.

## Die dringendsten Nutzerprobleme

### 1. Die Oberfläche ist zu viel

Die aktuelle Website hat zu viele Bereiche, Hinweise, Formulare, Fachbegriffe und konkurrierende Abläufe. Ich möchte die Qualität und Klarheit einer guten Apple-Anwendung: ruhig, hochwertig, aufgeräumt, gut lesbar, einfach bedienbar. Jeder soll verstehen, was als Nächstes zu tun ist.

Entwickle eine zusammenhängende Informationsstruktur. Als Ausgangspunkt kommen „Übersicht“, „Zahlungen“, „Unterlagen“ und „Steuerjahr“ infrage; KI und Einstellungen sollen zum jeweiligen Arbeitsschritt passen. Entscheide anhand der tatsächlichen Abläufe, statt diese Namen nur mechanisch umzusetzen. Auf der Startseite reichen wenige klare Aktionen und ein konkreter nächster Schritt. Details bei Bedarf aufklappen, sinnvolle Voreinstellungen, verständliche leere Zustände, sichtbare Speicher- und Verarbeitungszustände. Keine endlosen Warnwände oder technischen Modelltexte im Hauptablauf. Helle und dunkle Ansicht müssen beide sauber sein. Tastaturbedienung, Kontrast, Fokus und kleinere Fenster prüfen. Dezente Bewegung ist optional; Lesbarkeit und Geschwindigkeit haben Vorrang.

### 2. Kategorien sind fest vorgegeben und nicht änderbar

Ich möchte eigene Kategorien erstellen, umbenennen und bei Bedarf archivieren können. Bestehende Buchungen und gespeicherte KI-Vorschläge müssen dabei konsistent bleiben. Trenne meine alltagstauglichen Kategorien von technischen EÜR-Positionen: Eine umbenannte Kategorie darf keine Steuerberechnung unbemerkt verändern. Eine optionale steuerliche Zuordnung kann im Hintergrund geführt und später geprüft werden.

Untersuche dafür nicht nur das Dropdown, sondern alle Stellen in Backend, Import, KI-Validierung, Filtern und Export. Ersetze starre Listen durch ein ordentliches persistentes Modell. Keine verwaisten Einträge, keine verlorenen Buchungen beim Umbenennen/Archivieren, keine Duplikate durch Groß-/Kleinschreibung.

### 3. „Bezahlt am“ ist nach PDF-Import gesperrt

Ich muss ein falsch erkanntes Zahlungsdatum korrigieren können, auch nach der Übernahme ins Dashboard. Aktuell sind importierte Bankzahlungen in Oberfläche und Backend geschützt. Baue einen verständlichen, nachvollziehbaren Korrekturweg mit Originalbezug und Änderungsprotokoll.

Unterscheide Original-Bankdaten, Buchungstag, Wertstellung, tatsächlich bestätigtes Zahlungsdatum und gegebenenfalls steuerliche Jahreszuordnung. Die Originaldatei und ursprüngliche Importinformation müssen erhalten bleiben. Eine Korrektur darf beim nächsten Import keine zweite Zahlung erzeugen oder den Bankabgleich unbemerkt verfälschen. Prüfe nach der Änderung Monats-/Jahresansichten, Kontogültigkeit, Dublettenerkennung, Exporte sowie veraltete KI-/EÜR-Bestätigungen. Hebe nicht nur `readonly` auf und entferne nicht einfach den Schutz im Backend.

### 4. Steuerangaben überfordern mich

Viele Felder sind für mich unnötig, weil ich die Antwort gar nicht kenne. Der normale Erfassungsablauf darf nicht voraussetzen, dass ich Ist-/Soll-Versteuerung, Reverse Charge, Vorsteuer oder EÜR-Zeilen selbst beherrsche.

Erfasse einfache Tatsachen. Nutze belastbare Dokumentangaben und verständliche Vorschläge. Zeige steuerliche Details erst, wenn sie für die konkrete Entscheidung erforderlich sind. „Weiß ich nicht / später klären“ muss eine echte speicherbare Antwort sein. Unbekannt darf nicht als Null, Kleinunternehmerstatus, 100 % betrieblich oder endgültig geprüft gespeichert werden. Eine relevante fachliche Lücke vor Berechnung/Export konkret erklären, ohne die tägliche Belegerfassung zu blockieren. Keine automatische Steuerentscheidung aus einem Händlernamen oder einer Finanzamts-Erstattung.

### 5. „Betrieblich → kein Beleg“ bleibt ein endloser Fehler

Wenn ich ausdrücklich „Kein Beleg vorhanden“ angebe, möchte ich, dass meine Entscheidung gespeichert und berücksichtigt wird. Die Zahlung soll nicht immer wieder wie ein unbearbeiteter technischer Fehler erscheinen.

Trenne daher mindestens: Eingabe noch offen, Beleg folgt, Rechnung verknüpft, ohne Beleg dokumentiert, Beleg für diesen Vorgang nicht erforderlich und ein konkreter fachlicher Prüfpunkt. Definiere sauber, wie Banknachweis, Rechnung und gegebenenfalls dokumentierter Eigenbeleg zusammenhängen. Ein Kontoauszug ist nicht automatisch eine Rechnung.

Eine bewusst dokumentierte fehlende Rechnung beendet die organisatorische Eingabe. Das bedeutet nicht automatisch Vorsteuerabzug oder Absetzbarkeit. Wenn ein steuerliches Problem bleibt, benenne genau, welches Ergebnis davon abhängt. Keine pauschale Endlosschleife „Beleg fehlt → prüfen → kein Beleg → Beleg fehlt“. Prüfe Zähler, Filter und Status überall: Übersicht, Monatsliste, Details, Jahrescheck und KI.

## Technische und fachliche Qualität

Die aktuelle Architektur ist Python/SQLite plus Vanilla-JS. Die Oberfläche enthält viele globale Überschreibungen von `render`, `action` und `submit`. Untersuche diese Kopplung und ersetze sie durch klare Zuständigkeiten. Ein Frameworkwechsel ist möglich, wenn du den konkreten Nutzen und Migrationsweg begründest; ein Windows-Nutzer muss das Ergebnis weiterhin einfach starten können. Verlange nicht für jede Benutzung eine Entwicklungsumgebung oder laufende Cloud-Dienste.

Erhalte Importherkunft, atomare Speicherung, Originaldateien, Dublettenschutz, Wiederaufnahme, Sicherungen und Jahresisolation. Centgenaue Rechnungen kommen aus geprüftem Programmcode, nicht aus KI-Prosa. Die zweite KI muss unabhängig lesen. Fehlerhafte, abgeschnittene oder unvollständige Modellantworten dürfen nicht als abgeschlossen gelten. Fertige Schritte müssen einen Neustart überleben. Die Oberfläche muss unterscheiden können: wartet, läuft, beantwortet, unterbrochen, Benutzerangabe erforderlich und tatsächlich fehlgeschlagen.

Die EÜR 0.4.0 ist ein begrenzter Arbeitsentwurf. Vorjahres-AfA, Verlustvorträge und geänderte Bescheide niemals ungeprüft in ein neues Jahr übernehmen. Neue Steuerregeln anhand aktueller amtlicher Quellen für das richtige Jahr prüfen. Keine Aussage „fertige EÜR“, „abgabefertig“ oder „alles korrekt“, wenn Daten, Formularfelder oder steuerliche Voraussetzungen fehlen. Entwickle trotzdem einen nützlichen Arbeitsablauf; verstecke das Produkt nicht hinter allgemeinen Warntexten.

## Bisherige Fehler, die nicht zurückkommen dürfen

- „EÜR“ im freien Chat leitete den Auftrag unbeabsichtigt in eine reine Buchungs-Jahresprüfung um. Der eigentliche Nutzerauftrag ging nicht vollständig an diese Leser.
- Lange Aufträge stießen auf eine 3.000-Zeichen-Grenze. Das war eine Ablehnung, keine heimliche Backend-Kürzung. Aktuell gilt 12.000 mit zusätzlicher Kontextprüfung.
- Aussagen wie „106 von 106 beantwortet“ wurden als vollständige Beleg-/Jahresprüfung missverstanden, obwohl nur Buchungsdaten gelesen wurden.
- Gemma-Antworten scheiterten an leeren oder zu langen Hinweisen. Fertige Arbeiterantworten durften dabei nicht verloren gehen.
- PDF-Folgeseiten wurden getrennt, Gebührenaufschlüsselungen als zusätzliche Zahlungen erkannt, Buchungstag und Gebührenzeitraum verwechselt.
- Originalzeilen konnten nicht eindeutig belegt werden; Monats-/Umsatzsummen passten nicht. Ein Hinweis muss zum richtigen Monat und zur richtigen Quelle führen.
- Entfernte PDF-/CSV-Uploads blockierten den erneuten Upload. Papierkorb/Wiederherstellung und Dublettenschutz müssen zusammenpassen.
- „Nicht verknüpft“ wurde zu leicht mit „nicht vorhanden“ verwechselt. Private Zahlungen brauchen keinen Betriebsrechnungsbeleg.
- Frontend-Erweiterungen brachten Konflikte zwischen Formularen und globalen Handlern. In 0.4.0 wurde unter anderem ein verstecktes Formularfeld `name="id"` entfernt, das `form.id` überschrieb und das Speichern einer Anlage verhinderte.

## Abnahme durch echte Abläufe

Prüfe mindestens diese Benutzerwege im Browser, zusätzlich zu geeigneten gezielten Backend-Tests:

1. CSV und mehrseitige PDF importieren, Einordnung bearbeiten, Monate freigeben, ohne doppelte Zahlungen.
2. Eine neue Kategorie anlegen, umbenennen, archivieren und danach alte Buchungen/Filter/Export wieder öffnen.
3. Zahlungsdatum einer übernommenen PDF-Zahlung berichtigen, Anwendung neu starten, richtige Monats-/Jahreszuordnung und unverändertes Original nachweisen.
4. Betrieblich ohne Beleg dokumentieren, speichern, neu öffnen: kein erneuter organisatorischer Pflichtfehler; ein fachlicher Restpunkt bleibt konkret und korrekt.
5. Unbekannte Steuerangaben zulassen, gewöhnliche Zahlung trotzdem speichern. Erst beim abhängigen Ergebnis gezielt klären.
6. Mit und ohne verknüpfte Rechnung arbeiten. Keine private Einzahlung als Umsatz; keine Anschaffung doppelt als volle Ausgabe und AfA.
7. Ein KI-Lauf wird im Prüfer-Schritt unterbrochen. Neustart/Fortsetzen wiederholt keine fertigen Arbeiterschritte und behält den Originalauftrag.
8. Formulareingaben/Entwürfe, Sicherung/Wiederherstellung und Migration eines bestehenden Bestands bleiben vollständig erhalten.
9. Helle/dunkle Ansicht, Tastatur und kleines Fenster: kein abgeschnittener Speichern-Knopf, kein still blockiertes Pflichtfeld, keine unbegründete Warnflut.
10. Bei echten Modelltests festhalten, welche installierten Modelle mit welcher Kontextgröße tatsächlich liefen. Simulation und realen Windows-/Ollama-Test klar unterscheiden.

Bestehende Tests sind Regressionserwartungen, keine Begründung, schlechte Produktentscheidungen zu erhalten. Wenn du ein Verhalten absichtlich verbesserst, aktualisiere passende Tests mit einer nachvollziehbaren Begründung. Lösche keine Tests bloß, um ein grünes Ergebnis zu bekommen.

## Budget, Arbeitsweise und Übergabe

Arbeite in überprüfbaren Etappen: Bestandsaufnahme, konkrete Fehler-/Datenkorrekturen, vereinfachte Oberfläche, gezielte technische Konsolidierung, Abschlussprüfung. Nutze Browserbilder und kurze Statusmeldungen, damit Fortschritt sichtbar ist. Spare Kontext durch eine laufend gepflegte Projektstatusdatei; lies nicht bei jeder Runde alles neu. Keine unbegrenzten Wiederholungs-, Recherche- oder Agentenschleifen. Budgetangaben nur behaupten, wenn tatsächliche Nutzungsdaten vorliegen; ein Prompt setzt keine harte Abrechnungsgrenze.

Wenn das Guthaben oder Kontextfenster knapp wird, hinterlasse einen sauberen Commit und `docs/WEITERARBEITEN.md` mit aktuellem Branch/Commit, erledigten Schritten, offenen Problemen, Testergebnissen und exakt dem nächsten sinnvollen Schritt. Bewahre einen nutzbaren Zwischenstand.

Am Ende erwarte ich ein startfähiges, deutlich einfacheres Dashboard, eine kurze Aktualisierungsanleitung, überprüfbare Tests und eine ehrliche Liste verbleibender Einschränkungen. Beginne jetzt mit dem Repository, prüfe die tatsächlichen Abläufe und setze die Verbesserungen anschließend um.
