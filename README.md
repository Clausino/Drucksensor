# Drucksensor

Erster Programmstand zum Einlesen und Prüfen von Drucksensormessungen.
Die Oberfläche verwendet wie „Bareiss Kinetik +“ die Menüreihenfolge
Daten, Modelle, Simulation, Ausgabe, Einstellungen und Hilfe sowie dessen
dunkelblaue Kopfzeile. Mit `ttkbootstrap` stehen die `superhero`-/`flatly`-
Themes zur Verfügung; fehlt das optionale Paket, startet das Programm mit
ähnlich gefärbten nativen Tkinter-Styles. Auswertung, Simulation und Export
sind noch nicht implementiert.

## Start

```bash
python3 -m pip install -r requirements.txt  # optional für die ttkbootstrap-Themes
python3 drucksensor.py
```

Unter Linux kann alternativ `start_drucksensor.sh` verwendet werden. Tkinter
muss für den nativen Fallback verfügbar sein. Das Programm sucht CSV-Dateien
mit Spalten für `Date`, `Time`, `bar` und `°C`;
Excel-CSV-Exporte mit `sep=,` und vorgeschalteten Sensor-Metadaten werden
ebenfalls erkannt. Über **Daten → Messdaten importieren ...** können mehrere
Dateien ausgewählt, geprüft und vor dem Import in einer Vorschau kontrolliert
werden. Bereits importierte Dateien werden nicht doppelt geladen.
