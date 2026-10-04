# Cay Steuerstudio: GitHub und Claude Code

Stand: 04.10.2026. Das ZIP enthält den Programmstand 0.4.0 und die vollständige Übergabe. Ein GitHub-Repository wurde noch nicht angelegt.

## 1. Vorhandenes Dashboard sichern

In deiner bisherigen Anwendung eine Sicherung herunterladen und den Datenpfad notieren. Die Nutzerdaten bleiben außerhalb des GitHub-Projekts. Falls du 0.4.0 vor dem Umbau ausprobieren möchtest, befolge `START_HIER.md`.

Die neuen Wünsche – frei verwaltbare Kategorien, nachträglich korrigierbares Zahlungsdatum, weniger Steuerfelder, abgeschlossene Eingabe bei „kein Beleg“ und umfassend vereinfachte Oberfläche – sind im Claude-Auftrag enthalten. Sie sind in 0.4.0 noch nicht umgesetzt.

## 2. Privates Repository mit GitHub Desktop anlegen

1. [GitHub Desktop](https://desktop.github.com/) installieren und mit deinem GitHub-Konto anmelden.
2. **File → New repository** wählen. Als Namen `cay-steuerstudio` und als lokalen Elternordner zum Beispiel `D:\Projekte` verwenden. GitHub Desktop legt darin `D:\Projekte\cay-steuerstudio` an. Keine zusätzliche README, Gitignore-Vorlage oder Lizenz erzeugen; diese Auswahl ist für diesen Import nicht nötig.
3. Das erhaltene ZIP entpacken. Den **Inhalt** des Ordners `cay-steuer-dashboard` in den gerade angelegten Repository-Ordner kopieren. `app.py`, `CLAUDE.md`, `CLAUDE_AUFTRAG.md` und `.gitignore` müssen direkt dort liegen, nicht noch einen Ordner tiefer. `dist` und `tests` gehören ebenfalls dazu.
4. In GitHub Desktop unter **Changes** die Dateiliste ansehen. Nur den neuen Programmordner übernehmen. Keine alten Datenordner, Datenbank, Kontoauszüge, ELSTER-Zertifikate, Zugangsdaten oder persönlichen Screenshots hineinkopieren. Die mitgelieferte `.gitignore` schließt typische lokale Daten aus.
5. Als Zusammenfassung `Cay Steuerstudio 0.4.0 – Übergabestand` eintragen und den Commit erstellen.
6. **Publish repository** anklicken, **Keep this code private** aktiviert lassen und veröffentlichen.

Jetzt liegt der Quellcode lokal und als privates Repository auf GitHub. GitHub ist die Versionsverwaltung; die tatsächlichen Steuerbelege bleiben in deiner vorhandenen lokalen Datenablage.

## 3. Claude Code im Projekt öffnen

Am besten arbeitest du lokal auf dem Windows-Rechner, auf dem später auch das Dashboard und Ollama laufen sollen.

Wenn du Claude Code bereits als Terminalprogramm nutzt, PowerShell öffnen und – bei obigem Beispielpfad – eingeben:

```powershell
Set-Location "D:\Projekte\cay-steuerstudio"
claude
```

Claude Code arbeitet damit direkt im lokalen Repository. Für diesen lokalen Arbeitsweg ist keine weitere „GitHub-Verbindung“ im Prompt nötig. GitHub Desktop kann die späteren Commits anschließend zu GitHub übertragen.

Falls du die Claude-Desktop-App mit dem **Code**-Bereich nutzt, dort eine lokale Sitzung öffnen und den Repository-Ordner auswählen. Bezeichnungen und Verfügbarkeit können je nach installierter App abweichen; die aktuelle offizielle Anleitung ist unten verlinkt.

Wenn Claude Code noch nicht installiert ist oder `claude` nicht gefunden wird, folge der [offiziellen Einrichtung für Windows](https://code.claude.com/docs/en/setup). Nicht versehentlich ein zweites Projekt in einem anderen Ordner öffnen.

## 4. Den Auftrag starten

Die vollständige Vorlage steht in **CLAUDE_AUFTRAG.md**. Du kannst ihren gesamten Inhalt in Claude Code einfügen. Alternativ reicht im korrekt geöffneten Repository dieser Startauftrag:

> Übernimm Cay Steuerstudio in diesem Repository. Lies zuerst CLAUDE.md, dann CLAUDE_AUFTRAG.md, docs/UEBERGABE_0.4.0.md und TESTBERICHT.md. Führe anschließend den vollständigen Auftrag in CLAUDE_AUFTRAG.md aus. Prüfe die laufende Anwendung mit separaten Testdaten und überarbeite danach Bedienung, Gestaltung und Code. Besonders wichtig sind frei verwaltbare Kategorien, nachvollziehbar korrigierbare Zahlungsdaten nach PDF-Import, einfache Tatsachenfragen statt überfordernder Steuerformulare und ein abgeschlossener Erfassungsstatus bei „kein Beleg“. Ich möchte eine ruhige, hochwertige und einfach bedienbare Oberfläche wie bei einer guten Apple-Anwendung. Erhalte meinen Datenbestand und die funktionierenden Import-/Sicherungsmechanismen. Arbeite in überprüfbaren Etappen in einem eigenen Branch; bleibe nicht bei Planung oder Mockups stehen. Mein angegebenes Arbeitsbudget beträgt ungefähr 100 € Claude-Code-Guthaben. Nutze es sparsam und dokumentiere Fortschritt, Tests und den nächsten Schritt für einen möglichen Neustart.

Das Guthaben habe ich nicht in deinem Konto geprüft. Ein Prompt kann keine harte Abrechnungsgrenze setzen. Prüfe vor dem Start im Claude-Konto die tatsächlich verwendete Abrechnung und verfügbare Guthabenanzeige. Die offizielle Kostenhilfe erklärt die aktuell angebotenen Kontrollmöglichkeiten; keinen bestimmten stundenlangen Arbeitsumfang als garantiert ansehen.

## 5. Später Änderungen sichern

Claude soll nachvollziehbare Commits in seinem Arbeitsbranch erstellen. In GitHub Desktop siehst du Branch und Änderungen. Mit **Push origin** werden vorhandene lokale Commits ins Remote übertragen. Vor einem Wechsel zurück zum alten Stand die Datenbank-Kompatibilität beachten: Git stellt den Code zurück, nicht automatisch deine Datenbank.

Die Übergabe enthält:

- `CLAUDE.md`: dauerhafter Projekteinstieg.
- `CLAUDE_AUFTRAG.md`: vollständiger Umbauauftrag.
- `docs/UEBERGABE_0.4.0.md`: Architektur und bekannte Fehler mit Einstiegsstellen im Code.
- `TESTBERICHT.md`: überprüfter Stand und Grenzen.
- `START_HIER.md`: Installation und Nutzung von 0.4.0.

Offizielle Anleitungen, beim Erstellen der Übergabe geprüft:

- [GitHub Desktop: Erstes Repository anlegen und veröffentlichen](https://docs.github.com/en/desktop/overview/creating-your-first-repository-using-github-desktop)
- [Claude Code: Einrichtung und lokaler Projektstart](https://code.claude.com/docs/en/setup)
- [Claude Code: Desktop-Einstieg](https://code.claude.com/docs/en/desktop-quickstart)
- [Claude Code: Kosten kontrollieren](https://code.claude.com/docs/en/costs)
