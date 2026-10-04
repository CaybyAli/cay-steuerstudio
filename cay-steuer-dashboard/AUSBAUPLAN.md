> Historischer Ausbauplan. Für die Weiterarbeit ab 04.10.2026 gelten `CLAUDE_AUFTRAG.md` und `docs/UEBERGABE_0.4.0.md`. Einige frühere Punkte sind in 0.4.0 bereits umgesetzt.

# Fahrplan – umgesetzt und nächster Ausbau

Stand 01.10.2026 · ausschließlich YouTube/Twitch und Privat.

## Mit 0.3.2 zusätzlich umgesetzt

Durchgängig erneuerte Oberfläche mit fünf Hauptwegen, ruhiger Startseite, einheitlichen hellen/dunklen Flächen, sichtbarem Papierkorb und aufklappbaren Zusatzangaben. Aufgaben stehen direkt in der Navigation.

Eigenes Fenster zur PDF-Prüfung nach Monaten, einfache Auswahl Privat/Betrieblich, optionale Details und Notizen, automatisch gespeicherter Zwischenstand und eine Freigabe bis ins Dashboard. Erkannte Volksbank-Tabellen werden ohne KI-Betragsraten gelesen und mit Kontostand/Umsatzsummen abgeglichen. Andere Layouts behalten die unabhängigen KI-Lesungen. Mögliche Doppelungen werden vor der Übernahme gesondert geklärt; eine fehlerhafte Zeile verwirft nicht mehr alle anderen gelesenen Seiten.

## Mit 0.3.1 zusätzlich umgesetzt

PDF-Schutzfehler korrigiert, echte Öffnungskennwörter nur vorübergehend im Speicher, Upload-Papierkorb mit Wiederherstellung und Schutz bestätigter Zahlungen, zusammengefasster Zahlungsbereich, ältere Dokument-Auszüge direkt einlesbar und ein verständlicher Jahresleitfaden. Die unten genannten fachlichen Ausbauschritte bleiben offen.

## Mit 0.3.0 umgesetzt

| Schritt | Was er macht | Kontrolle |
|---|---|---|
| 1. Original speichern | CSV und PDF mit Konto, Jahr und Prüfsumme sichern | Nach Neustart aus Importverlauf erreichbar |
| 2. Zahlungen erkennen | CSV deterministisch lesen; PDF-Text bzw. lokale OCR mit zwei unabhängigen KI-Lesungen | Quellzeile/Seite, Datum, Betrag, Vorzeichen und Vollständigkeit prüfen |
| 3. Vorsortieren | Arbeiter und Prüfer schlagen Bereich/Kategorie vor; Koordinator erläutert offene Punkte | Widersprüche bleiben ungeklärt; eigene Änderungen haben Vorrang |
| 4. Übernehmen | Geprüfte Auswahl atomar buchen, Doppelungen vergleichen, manuelle Vorbuchungen verknüpfen | Keine Übernahme ohne Bestätigung; kein FLOAT-Geld in SQLite |
| 5. Monat bearbeiten | Beleg, Kein Beleg und Notiz direkt zuordnen | Private Vorgänge ohne pauschale Betriebsbeleg-Warnung; betriebliche Lücken sichtbar |
| 6. Konten archivieren | Ende der Nutzungszeit festhalten und spätere Auswahl ausblenden | Frühere Daten und Nachträge bleiben erhalten |
| 7. Sicherung | Originale, Bearbeitungsstände und bestätigte Daten in geprüfte Sicherungen aufnehmen | Wiederherstellung in getrennten Ordner testen |

## Dein nächster Arbeitsschritt

Den vorhandenen PDF-Auszug 2024 unter **Zahlungen → Kontoauszüge → Öffnen → Erneut lesen lassen** öffnen. In der Monatsprüfung mit dem Original vergleichen, jede Zahlung einordnen und freigeben. Danach einen Monat Volksbank 2025 mit Original-CSV abgleichen; erst anschließend den übrigen Bestand importieren. Monatlich alle Konto-, Plattform- und ggf. PayPal-Unterlagen auf Vollständigkeit prüfen; Bareinkäufe gesondert ergänzen. Die Software kann nicht wissen, welche noch nicht erfassten Konten, Sachleistungen oder Abrechnungen fehlen.

## Vor einer fertigen Steuererklärung noch nötig

1. **Ausgangslage und Fristen belegen.** Abgabestand 2025, USt-Status je Jahr, Gestattung Ist-Versteuerung, Voranmeldungen, Dauerfristverlängerung, ELSTER-Zugang, Anlagen/AfA und offene Bescheide übernehmen. Aufgaben mit tatsächlich belegten Fristen führen. Die Softwareentwicklung ist kein Grund, eine bestehende Frist abzuwarten.
2. **Vollständiges Sachverhaltsmodell.** Plattformbrutto, Gebühren, Währung, Gegenpartei/Land, Privatanteile, Anlagegüter, Sachvergütungen/PR-Samples, Verträge und Korrektur-/Stornovorgänge strukturiert erfassen. E-Rechnungen im Original erhalten und strukturiert prüfen. Nicht jede steuerliche Einnahme ist eine Bankzahlung.
3. **Rechtsbasis pro Jahr.** Verbindliche bzw. geeignete amtliche Quellen mit historischer Gültigkeit, Übergängen und Fundstellen hinterlegen. Aktuelle Downloads allein reichen nicht. Bundesrecht, Landesverwaltung, örtliche Zuständigkeit und Gemeindesachverhalte auseinanderhalten.
4. **Deterministisches Rechenwerk.** EÜR, Umsatzsteuer und private Einkommensteuer getrennt und mit fachlich festgelegten Soll-Ergebnissen testen. Jahreswechsel, AfA, gemischte Nutzung, Sonderfälle und Bescheidänderungen berücksichtigen. BAföG-Bewilligungszeiträume gesondert betrachten.
5. **Fristen und Dokumentlesen ausbauen.** OCR außerhalb des Bankeingangs, lange Verträge/Briefe, nachgewiesene Bekanntgabe, Fristverlängerung und echte Benachrichtigungen. Heute existieren Aufgaben und Kalenderexport, aber keine allgemeine Zustellung bei ausgeschaltetem PC.
6. **Abgabe integrieren.** Geprüfte Formularzuordnung, unterstützte ELSTER-/ERiC-Integration, vollständige Vorschau, bewusste Nutzerfreigabe und Übermittlungsprotokoll. Danach Bescheidabgleich und dokumentierte Korrekturen.

## Maßstab

Weniger manuelle Eingabe, erkennbare Lücken, überprüfbare Vorschläge und wiederherstellbare Daten. Keine automatische Erklärung allein auf Grundlage von Modellzustimmung. Vollständige Fehlerfreiheit und pauschale Überlegenheit gegenüber einem Steuerberater lassen sich nicht garantieren.
