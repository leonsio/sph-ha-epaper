# E1003 SD-Screensaver – Installation und erster Test

## Dateien installieren

Das ZIP im ESPHome-Verzeichnis entpacken. Die YAML ersetzt `sph-reterminal-e1003.yaml`.
Den Ordner `components/sd_screensaver` vollständig mitkopieren; er muss relativ zur YAML
unter `components` liegen. Die drei vorhandenen `.h`-Includes sind mitgeliefert.
Deine bestehenden Ordner `fonts`, `icons` und `secrets.yaml` bleiben erforderlich.
Die eigentlichen Testbilder sind nicht im ZIP: deine vorhandene `test_bild.bmp`
muss direkt neben der YAML liegen.

ESPHome **2026.9.0 oder neuer**, ESP-IDF, 16 MB Flash und PSRAM sind erforderlich.

```sh
esphome config sph-reterminal-e1003.yaml
esphome compile sph-reterminal-e1003.yaml
```

Anschließend wie gewohnt per ESPHome installieren. Diese Firmware wurde hier
nicht mit der ESP32-Toolchain kompiliert und nicht auf einem E1003 getestet.
Die Konfiguration und der lokale Bildleser wurden geprüft; der erste Build
und die SD-/Display-Prüfung erfolgen auf deinem Gerät.

## Erster Test mit deinem vorbereiteten Bild

1. Für **Testbild (Firmware)** ist keine SD-Karte erforderlich.
2. Unter Home Assistant → Einstellungen → Geräte & Dienste → ESPHome →
   Maxim ePaper E1003 die Geräteeinstellungen öffnen.
3. Die SD-Diagnosesensoren dürfen beim Firmware-Test AUS anzeigen.
4. `Screensaver Bildquelle` auf **Testbild (Firmware)** lassen.
5. `Screensaver Start nach` zum Test auf **1 Minute** stellen und `Screensaver`
   einschalten. Den Bildwechsel z. B. auf **5 Minuten** stellen.
6. Nicht mehr bedienen. Spätestens nach etwa 65 Sekunden erscheint das Bild.
7. Ein Touch/Tastendruck beendet den Screensaver und zeigt die vorherige Seite.
   Die erste Berührung wird nicht als Bedienbefehl auf der darunterliegenden UI gewertet.

Standardmäßig wird `test_bild.bmp` beim Kompilieren eingebettet. Alternativ oben
in `substitutions` ändern:

```yaml
screensaver_test_file: test_bild.png
```

Danach neu kompilieren/installieren. Es wird jeweils **ein** Testbild eingebettet,
um den Firmware-Platzbedarf zu begrenzen. Der Testmodus liest dieses Bild aus
der Firmware, weil dein ESPHome-Verzeichnis kein Dateisystem im Gerät ist.
Der Firmware-Test funktioniert ohne SD-Karte; nur die Quelle SD-Karte benötigt eine lesbare Karte.

## Einstellmöglichkeiten

| Feld | Werte | Standard |
|---|---|---|
| Screensaver | Ein/Aus; Firmware-Test ohne SD, SD-Quelle nur mit lesbarer Karte | Aus |
| Screensaver Bildwechsel | 5–60 Minuten, in 5-Minuten-Schritten | 15 Minuten |
| Screensaver Start nach | 1, 2, 5, 10, 15 … 60 Minuten ohne Bedienung | 5 Minuten |
| Screensaver Bildquelle | Testbild (Firmware), SD-Karte | Testbild (Firmware) |

Die Auswahl bleibt über Neustart/Deep Sleep erhalten. Einschalten startet die
Inaktivitätszeit neu. Touch und Tasten setzen sie zurück; HA-Datenupdates zählen
nicht als Bedienung. Startzeitänderungen beziehen sich auf die letzte Bedienung;
Bildwechseländerungen auf den letzten Bildwechsel. Ein Quellenwechsel verlässt
zunächst den Screensaver. Bei einem Bildladefehler wird die Funktion ausgeschaltet
und die normale Oberfläche wiederhergestellt; Details stehen im Log.

Bei Bildquelle SD-Karte wird ohne lesbare Karte der Schalter AUS angezeigt und Einschalten abgelehnt.
Die Dropdowns bleiben sichtbar: ESPHome/HA unterstützen kein dynamisches Ausgrauen
dieser Gerätefelder. Ihre Werte allein aktivieren den Screensaver nicht.
Beim Entfernen der Karte endet der Screensaver nach spätestens ca. 5 Sekunden,
sofern das Gerät wach und der Displaytransfer abgeschlossen ist. Im Deep Sleep
wird eine Kartenentnahme erst beim nächsten Aufwachen erkannt. Die gespeicherte
Einschaltpräferenz bleibt bei Kartenentnahme erhalten; erneutes Einsetzen kann
den Screensaver wieder aktivieren. Der AUS-Schalter löscht diese Präferenz.
Eine nicht lesbare Karte wird niemals automatisch formatiert.

## Bilder von SD-Karte

Auf der Karte einen Ordner `screensaver` anlegen:

```text
/screensaver/test_bild.bmp
/screensaver/urlaub.bmp
/screensaver/familie.gray4
```

Dann `Screensaver Bildquelle` auf **SD-Karte** stellen. Dateien werden zufällig
ausgewählt; bei mehreren Bildern wird das letzte Bild nicht unmittelbar wiederholt.
Es gibt keinen vollständigen Shuffle-Zyklus. Unterordner werden nicht durchsucht;
maximal 1024 Dateien werden berücksichtigt.

Unterstützt werden unkomprimierte BMPs mit 1/4/8-Bit-Palette und 24/32-Bit-RGB,
auch top-down BMPs. Komprimierte BMPs (RLE/Bitfields) werden übersprungen.
PNG/JPEG werden zunächst **nicht direkt zur Laufzeit von SD** dekodiert. Du kannst
sie mit dem mitgelieferten Skript in BMP oder Gray4 umwandeln:

```sh
python3 -m pip install Pillow
python3 prepare_screensaver.py test_bild.png screensaver/test_bild.bmp
python3 prepare_screensaver.py test_bild.png screensaver/test_bild.gray4
```

Den Ergebnisordner auf die SD-Karte kopieren. Gray4 ist ein eigenes Format:
`G4E1` + Breite/Höhe als zwei uint16 little-endian + zeilenweise 4-Bit-Pixel,
linker Pixel im hohen Nibble; 0 schwarz, 15 weiß. Bei ungerader Breite wird das
letzte niedrige Nibble mit Weiß gefüllt. Gray4 muss die logische Panelgröße haben.

## Bildqualität und Full-Refresh

Die aktuelle Displaykonfiguration verwendet **1872 × 1404 Pixel im Querformat**.
Für vorbereitete OpenDithering-Bilder möglichst genau dieses Format verwenden.
Passende Bilder werden pixelgenau übernommen. Andere BMP-/Testbildgrößen werden
proportional eingepasst, mit weißen Rändern und Nearest-Neighbor-Skalierung.
Das erhält vorhandene Pixelwerte, kann aber bei Größenänderungen Dithering-Muster
verändern. Im Vorbereitungsskript ist mit `--fit cover` alternativ Zuschnitt möglich.
Es gibt keine zusätzliche Dithering- oder Glättungsstufe.

**Kein Weiß → Schwarz → Weiß und kein separates Cleanup-Bild.** Jeder Fotowechsel
überträgt das gesamte Bild mit **GC16**, um die Graustufen zuverlässig darzustellen.
Spätestens nach einer Stunde wird das aktuelle Vollbild wieder mit GC16 übertragen.
Weil ein Bildwechsel höchstens 60 Minuten auseinanderliegt und bereits ein
Vollbild-Refresh ist, startet dieser Wechsel den Stunden-Zähler neu. Ein zusätzlicher
zweiter Refresh direkt danach ist unnötig. GC16 kann während seiner normalen
Hardware-Wellenform sichtbar blinken; das ist kein zusätzlich eingeblendetes Bild.
Die normale Oberfläche behält ihre bestehenden DU-Teilupdates.

## Deep Sleep / USB

Wenn Screensaver EIN und SD lesbar sind, wartet der bisherige 90-Sekunden-Idle-Sleep
auf den Screensaver; damit werden auch Startzeiten von 5–60 Minuten erreicht.
Die Keep-Awake-Ausnahmen einzelner Seiten gelten dann für die normale UI weiterhin,
verhindern aber nicht den späteren Screensaver-Sleep.

- `Deep Sleep` AUS: Gerät bleibt wach; die Bildwechsel laufen über den Timer.
- USB-Signal EIN: Screensaver bleibt wach.
- USB-Signal zuverlässig AUS und `Deep Sleep` EIN: nach dem Bildrefresh und
  dem vorhandenen Idle-Timeout schläft das Gerät bis zum nächsten Bildwechsel.
  SD wird vorher ausgehängt und ausgeschaltet. Timer-Wakeup lädt direkt das nächste
  Foto; Touch/Geste oder Taste beendet den Screensaver.
- USB-Signal unbekannt: Gerät bleibt im Screensaver wach. Aus der Batteriespannung
  lässt sich USB-Versorgung nicht zuverlässig ableiten.

Verwendet wird dein bestehendes HA-Signal `binary_sensor.e1003_usb_power`.
Im Deep Sleep sind Einstellungen erst nach dem Aufwecken erreichbar. Ein Timerboot
und das Laden/GC16 benötigen Zeit; das Foto erscheint daher etwas nach dem
konfigurierten Intervall. Der Bildschirm hält das bisherige Bild bis dahin.

## Technische Prüfung

YAML-Struktur, eindeutige IDs und Dropdownbereiche wurden geprüft.
Der C++-Bildleser wurde auf dem Host mit API-Stubs kompiliert und mit generierten
BMPs (Palette, RGB/RGBA, top-down), Gray4, abgeschnittenen Dateien und unzulässiger
Komprimierung geprüft. Außerdem: Spiegelung, Intervall-/Stundenlogik, SD-Sperre,
Zufall ohne direkte Wiederholung und RTC-Timer-Wiederaufnahme.
Das ersetzt keinen ESPHome-/ESP-IDF-Build und keinen Hardwaretest.

Pinbelegung laut Seeed: SD-Detect GPIO15 aktiv LOW, SD-Enable GPIO39 beim E1003,
SD-CS GPIO14 und gemeinsamer SPI GPIO7/9/8. ESPHome besitzt den Bus explizit als
`spi2`; der SD-Baustein hängt seine SD-Verbindung an diesen Bus und initialisiert
keinen konkurrierenden SPI-Bus.

Referenzen:
- https://wiki.seeedstudio.com/reterminal_e10xx_with_esphome_rtc_sd_microphone/
- https://github.com/esphome/esphome/tree/2026.9.0/esphome/components/it8951
- https://github.com/espressif/esp-idf/blob/v5.5.1/components/fatfs/vfs/esp_vfs_fat.h

## Firmware-Test ohne SD-Karte

Die Bildquelle „Testbild (Firmware)“ funktioniert auch ohne eingesetzte oder lesbare SD-Karte. Die Kartenprüfung gilt nur für „SD-Karte“. Die SD-Diagnosesensoren zeigen weiterhin den tatsächlichen Kartenstatus.
