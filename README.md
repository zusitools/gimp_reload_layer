Fügt zwei neue Funktionen zum Ebenenmenü von GIMP hinzu:
* Reload active layer: Lädt den Inhalt der aktuellen Ebene anhand des Ebenennamens neu. Der Ebenenname muss ein Dateiname sein (absolut oder relativ zum Bildpfad). Optional kann dem Ebenennamen ein zusätzlicher Befehl #flipH oder #flipV nachgestellt sein, dann wird das eingefügte Bild horizontal bzw. vertikal gespiegelt.
* Replace with clipboard contents: Lädt den Inhalt der aktuellen Ebene aus dem Inhalt der Zwischenablage neu.

Zur Installation wird die Datei `reload-layer.py` in einen der Plugin-Ordner kopiert. Der Pfad zum Plugin-Ordner steht in den GIMP-Einstellungen unter Ordner → Plugins.

Beschränkungen
======

"Reload active layer" wurde nicht mit Dateien getestet, die mehr als eine Ebene besitzen.