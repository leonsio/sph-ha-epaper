# E1003 SD-Screensaver – Installation und erster Test

## Dateien installieren

Repository aktualisieren und `sph-reterminal-e1003.yaml` zusammen mit
`components/sd_screensaver` verwenden. Fonts, Icons und secrets.yaml bleiben erforderlich.
Es wird kein Screensaver-Testbild mehr in die Firmware eingebettet.

ESPHome **2026.9.0 oder neuer**, ESP-IDF, 16 MB Flash und PSRAM sind erforderlich.

```sh
esphome config sph-reterminal-e1003.yaml
esphome compile sph-reterminal-e1003.yaml
```

Anschließend wie gewohnt per ESPHome installieren. Diese Firmware wurde hier
nicht mit der ESP32-Toolchain kompiliert und nicht auf einem E1003 getestet.
Die Konfiguration und der lokale Bildleser wurden geprüft; der erste Build
und die SD-/Display-Prüfung erfolgen auf deinem Gerät.

## Einstellungen

Unter Home Assistant → Einstellungen → Geräte & Dienste → ESPHome →
Maxim ePaper E1003 stehen folgende Einstellungen bereit:

| Feld | Werte | Standard |
|---|---|---|
| Screensaver | Ein/Aus | Aus |
| Screensaver Darstellung | Bild / Digitale Uhr / Analoge Uhr | Bild |
| Screensaver Start nach | 1, 2, 5, 10 … 60 Minuten | 5 Minuten |
| Screensaver Bildwechsel | 5–60 Minuten | 15 Minuten |

Alle Einstellungen bleiben über Neustart und Deep Sleep erhalten. Startzeit,
Aktivierung, Touch-/Tastenbedienung und USB-/Deep-Sleep-Regeln gelten für alle
Darstellungen. Nur der Bildwechsel gilt ausschließlich für Bilder. Ein Wechsel
der Darstellung beendet den laufenden Screensaver zunächst. Touch oder Taste zeigt
die vorige Seite; die erste Berührung löst dort keinen Befehl aus.

Beide Uhren zeigen große schwarze Ziffern bzw. ein großes Zifferblatt auf Weiß,
Wochentag, Datum und die vorhandenen aktuellen HA-Wetterdaten.
Die analoge Uhr hat Stunden- und Minutenzeiger, keinen Sekundenzeiger.
Die Anzeige aktualisiert sich beim Wechsel der Uhrzeitminute (wach bis ca. 5 s
Poll-Verzögerung plus Displaytransfer). Bei fehlender Zeit wird die Synchronisierung
angezeigt; fehlende Wetterwerte werden nicht erfunden. Uhren benötigen keine SD-Karte.

Bilder werden ausschließlich von SD geladen. Ohne lesbare Karte lässt sich der
Bildmodus nicht einschalten. Eine Kartenentnahme beendet den Bildmodus beim
nächsten wachen Poll; im Deep Sleep erst beim Aufwachen. Die Einschaltpräferenz
bleibt erhalten. Bei Bildladefehlern wird der Screensaver ausgeschaltet. Karten
werden niemals automatisch formatiert. Der Bildwechsel bleibt auch im Uhrmodus
als Einstellung sichtbar, beeinflusst die Uhr aber nicht.

## Bilder von SD-Karte

Auf der Karte einen Ordner `screensaver` anlegen:

```text
/screensaver/test_bild.bmp
/screensaver/urlaub.bmp
/screensaver/familie.gray4
```

Dann `Screensaver Darstellung` auf **Bild** stellen. Dateien werden zufällig
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
Passende Bilder werden pixelgenau übernommen. Andere BMP-Größen werden
proportional eingepasst, mit weißen Rändern und Nearest-Neighbor-Skalierung.
Das erhält vorhandene Pixelwerte, kann aber bei Größenänderungen Dithering-Muster
verändern. Im Vorbereitungsskript ist mit `--fit cover` alternativ Zuschnitt möglich.
Es gibt keine zusätzliche Dithering- oder Glättungsstufe.

Bildwechsel und minütliche Uhr-Updates verwenden GC16. Eine mehrstufige Reinigung
**INIT weiß → GC16 schwarz → GC16 weiß → GC16 Inhalt** erfolgt standardmäßig nur
beim Booten (einschließlich Deep-Sleep-Wakeup). In Home Assistant sind zusätzlich
`E1003 Cleanup bei Seitenwechsel` und `E1003 Cleanup Intervall` (Aus/15/30/60 Minuten)
wählbar. Beide sind standardmäßig aus und gelten auch für den Screensaver.

Die Uhr wird vollständig neu gezeichnet, einschließlich Datum und Wetter.
`epaper_refresh` wartet nach jeder Übertragung auf `LUTAFSR == 0` und schaltet den
Controller anschließend in Standby. So bleibt die Panelansteuerung zwischen Updates
nicht aktiv. Vor dem nächsten Transfer weckt der native Treiber den Controller.
SD-Dateiverwaltung und Bilddecodierung bleiben in `sd_screensaver`.

VCOM (`1400`, Register `2`) und Temperaturvorgabe (`25 °C`) bleiben unverändert.
Die Verbesserung gegen das Verblassen muss am realen Gerät überprüft werden;
Details, Quellen und Grenzen der Diagnose stehen in der README.

## Deep Sleep / USB

Wenn Screensaver EIN und die gewählte Darstellung verfügbar ist, wartet der bisherige 90-Sekunden-Idle-Sleep
auf den Screensaver; damit werden auch Startzeiten von 5–60 Minuten erreicht.
Die Keep-Awake-Ausnahmen einzelner Seiten gelten dann für die normale UI weiterhin,
verhindern aber nicht den späteren Screensaver-Sleep.

- `Deep Sleep` AUS: Gerät bleibt wach; die Bildwechsel laufen über den Timer.
- USB-Signal EIN: Screensaver bleibt wach.
- USB-Signal zuverlässig AUS und `Deep Sleep` EIN: nach dem Bildrefresh und
  dem vorhandenen Idle-Timeout schläft das Gerät bis zum nächsten Bildwechsel.
  Bei Uhren wird stattdessen bis zur nächsten Uhrzeitminute geschlafen.
  SD wird vorher ausgehängt und ausgeschaltet. Timer-Wakeup lädt direkt das nächste
  Foto bzw. zeichnet die aktuelle Uhr; Touch/Geste oder Taste beendet den Screensaver.
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


Der Hardwaretest der überarbeiteten Display-Reinigung steht aus. Timerboot, Zeitsynchronisierung und GC16 verursachen im Deep Sleep zusätzliche Verzögerung bis zur sichtbaren Minute.
