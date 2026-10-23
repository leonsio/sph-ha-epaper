# SPH TRMNL 7.5 DIY

ESPHome-Konfiguration für ein 7,5"-E-Paper-Dashboard mit Daten aus dem
**Schulportal Hessen** über Home Assistant.

Die Konfiguration stellt unter anderem dar:

- Startseite mit Uhrzeit, Wetter, Tagesstundenplan, Hausaufgaben und nächsten Arbeiten
- Wochenstundenplan mit A/B-Wochenlogik
- Wetterseite mit aktueller Wetterlage, 24-Stunden- und Mehrtagesvorhersage
- Batteriestatus und WLAN-Signal
- Seitenauswahl über drei Hardware-Taster

Hauptdatei:

```text
sph-trmnl-7.5-diy.yaml
```

## Voraussetzungen

### Home Assistant

Es wird eine laufende Home-Assistant-Installation mit aktivierter ESPHome-Integration benötigt.

Die ESPHome-Konfiguration liest ihre Daten über die native Home-Assistant-API ein.

### ESPHome

Die Konfiguration ist für einen **ESP32-S3** mit Arduino-Framework ausgelegt und wurde mit einer aktuellen ESPHome-Version entwickelt.

Benötigt werden insbesondere die ESPHome-Komponenten:

- `waveshare_epaper`
- `homeassistant`
- `json`
- `font`
- `sntp`
- `adc`
- `wifi_signal`

Für das Laden der über `gfonts://` eingebundenen Schriften muss der ESPHome-Compiler Internetzugriff besitzen.

## Zwingende Voraussetzung: sph-ha

Für Stundenplan, Hausaufgaben und Leistungskontrollen wird die Home-Assistant-Custom-Integration **sph-ha** benötigt:

https://github.com/leonsio/sph-ha

`sph-ha` bindet das **Schulportal Hessen** in Home Assistant ein und stellt unter anderem die Module **Stundenplan**, **Mein Unterricht** und **Lerngruppen** bereit.

Die Installation erfolgt laut sph-ha-Dokumentation über HACS als benutzerdefiniertes Repository in der Kategorie **Integration**. Anschließend wird unter:

```text
Einstellungen → Geräte & Dienste → Integration hinzufügen
```

die Integration **Schulportal Hessen** eingerichtet.

Für jedes Kind wird in `sph-ha` ein eigener Eintrag angelegt. Unter anderem werden benötigt:

- Schulnummer
- SPH-Benutzername
- SPH-Passwort
- Name des Kindes
- Kürzel des Kindes

Dieses Projekt verwendet die JSON-Sensoren aus `sph-ha`.

Beispiel für:

```yaml
substitutions:
  child_name: maxim
  child_short: mk
```

werden folgende Home-Assistant-Entities erwartet:

```text
sensor.stundenplan_maxim_mk_json
sensor.mein_unterricht_maxim_mk_json
sensor.lerngruppen_maxim_mk_json
```

Die ESPHome-Konfiguration greift jeweils auf das Attribut:

```text
json
```

zu.

Beim Stundenplan wird ausschließlich `eigener_plan` dargestellt. Die vorhandene `wochenkennung` wird weiterhin für die A/B-Wochenlogik verwendet.

## Kind konfigurieren

Name und Kürzel werden nur einmal am Anfang der YAML-Datei definiert:

```yaml
substitutions:
  child_name: maxim
  child_short: mk
```

Für ein anderes Kind müssen nur diese beiden Werte geändert werden.

Die Werte müssen den Bestandteilen der von Home Assistant erzeugten Entity-IDs entsprechen, normalerweise also kleingeschrieben und ohne Leerzeichen.

Beispiel:

```yaml
substitutions:
  child_name: anna
  child_short: ak
```

führt unter anderem zu:

```text
sensor.stundenplan_anna_ak_json
sensor.mein_unterricht_anna_ak_json
sensor.lerngruppen_anna_ak_json
```

## Weitere benötigte Home-Assistant-Entities

Zusätzlich zu `sph-ha` erwartet die aktuelle YAML-Datei folgende Entities.

### Feiertagskalender

```text
calendar.deutschland_he
```

Verwendetes Attribut:

```text
message
```

Wenn der Feiertagskalender in der eigenen Home-Assistant-Installation anders heißt, muss die `entity_id` in der YAML angepasst werden.

### Sonnenaufgang und Sonnenuntergang

```text
sensor.sun_next_rising
sensor.sun_next_setting
```

Die Sensoren müssen ISO-8601-Zeitstempel liefern.

Falls diese Entities in der eigenen Home-Assistant-Konfiguration nicht vorhanden sind, müssen entsprechende Sensoren angelegt oder die Entity-IDs in der YAML geändert werden.

### Wetter-Hilfssensor

Die aktuelle Konfiguration erwartet:

```text
sensor.maxim_epaper_wetter
```

mit folgenden Attributen:

```text
condition
daily_json
hourly_json
outdoor_temperature
outdoor_humidity
pressure
wind_speed
apparent_temperature
indoor_temperature
indoor_humidity
```

Dieser Sensor gehört **nicht** zu `sph-ha` und muss in Home Assistant separat vorhanden sein.

Vor einer allgemeinen Verwendung des Projekts sollte entweder ein entsprechender Template-/Hilfssensor angelegt oder die Wetterquelle in `sph-trmnl-7.5-diy.yaml` an die eigene Home-Assistant-Konfiguration angepasst werden.

## Hardware

Die aktuelle YAML ist auf folgende Hardwarebelegung ausgelegt:

- ESP32-S3
- 7,5"-Waveshare-E-Paper, 800 × 480 Pixel
- ESPHome-Modell: `7.50inV2p`
- Landscape, Rotation `0`

### Display / SPI

| Funktion | GPIO |
|---|---:|
| SPI CLK | GPIO7 |
| SPI MOSI | GPIO9 |
| E-Paper CS | GPIO44 |
| E-Paper DC | GPIO10 |
| E-Paper RESET | GPIO38 |
| E-Paper BUSY | GPIO4 |

`BUSY` wird mit `inverted: true` verwendet.

### Taster

Die Taster arbeiten mit `INPUT_PULLUP` und schalten beim Drücken gegen GND.

| Funktion | GPIO |
|---|---:|
| Startseite | GPIO2 |
| Wochenplan | GPIO3 |
| Wetterseite | GPIO5 |

### Batterie

| Funktion | GPIO |
|---|---:|
| Batteriespannung ADC | GPIO1 |
| Battery Enable | GPIO6 |

Die Spannung wird in der YAML über eine hinterlegte Kalibrierung in Prozent umgerechnet. Diese Kennlinie kann je nach verwendetem Akku und Board angepasst werden müssen.

## Schriftarten

Die YAML verwendet sowohl automatisch über Google Fonts geladene Schriften als auch lokale TTF-Dateien.

### Automatisch über ESPHome geladen

Folgende Varianten von **Inter** werden über `gfonts://` eingebunden:

```text
Inter 600
Inter 700
```

Dafür müssen keine lokalen Dateien im Repository gespeichert werden. Beim Kompilieren benötigt ESPHome jedoch Internetzugriff.

### Lokal benötigte Schriftdateien

Folgende Dateien werden direkt aus dem Verzeichnis `fonts/` geladen:

```text
NotoSans-Bold.ttf
NotoSansMono-ExtraBold.ttf
MaterialDesignIconsDesktop.ttf
```

Wenn sich die YAML-Datei unter:

```text
/config/esphome/sph-trmnl-7.5-diy.yaml
```

befindet, müssen die Dateien hier liegen:

```text
/config/esphome/fonts/NotoSans-Bold.ttf
/config/esphome/fonts/NotoSansMono-ExtraBold.ttf
/config/esphome/fonts/MaterialDesignIconsDesktop.ttf
```

Empfohlene Verzeichnisstruktur:

```text
/config/esphome/
├── sph-trmnl-7.5-diy.yaml
├── secrets.yaml
└── fonts/
    ├── NotoSans-Bold.ttf
    ├── NotoSansMono-ExtraBold.ttf
    └── MaterialDesignIconsDesktop.ttf
```

Bezugsquellen:

- Noto Sans / Noto Sans Mono: https://fonts.google.com/noto
- Material Design Icons: https://pictogrammers.com/library/mdi/

Die Schriftdateien sind nicht Bestandteil dieses Projekts. Vor einer Weitergabe oder Aufnahme von Font-Dateien in das Repository müssen die jeweiligen Lizenzbedingungen beachtet werden.

## WLAN und secrets.yaml

Die YAML verwendet:

```yaml
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
```

Daher muss mindestens folgende Datei vorhanden sein:

```yaml
# /config/esphome/secrets.yaml

wifi_ssid: "MEIN-WLAN"
wifi_password: "MEIN-WLAN-PASSWORT"
```

## Sicherheit bei einem öffentlichen Repository

Die veröffentlichte YAML enthält keine WLAN-Passwörter oder API-Schlüssel direkt im Quelltext. Folgende Werte werden über `secrets.yaml` eingebunden:

```yaml
wifi_ssid: "..."
wifi_password: "..."
api_encryption_key: "..."
fallback_ap_password: "..."
```

Als Vorlage liegt `secrets.yaml.example` im Repository. Diese Datei kann lokal nach `secrets.yaml` kopiert und mit den eigenen Werten befüllt werden.

`secrets.yaml` mit echten Zugangsdaten darf nicht in ein öffentliches Git-Repository eingecheckt werden.

## Installation

1. **sph-ha installieren und einrichten.**
   Prüfen, dass die drei benötigten JSON-Sensoren für das gewünschte Kind vorhanden sind.

2. **ESPHome installieren.**
   ESPHome kann beispielsweise als Home-Assistant-Add-on verwendet werden.

3. **YAML kopieren.**
   `sph-trmnl-7.5-diy.yaml` nach `/config/esphome/` kopieren.

4. **Schriftarten installieren.**
   Die drei lokalen TTF-Dateien nach `/config/esphome/fonts/` kopieren.

5. **secrets.yaml konfigurieren.**
   WLAN-Zugangsdaten eintragen und für ein öffentliches Repository auch API-Key und Fallback-Passwort auslagern.

6. **Kind konfigurieren.**
   Am Anfang der YAML `child_name` und `child_short` einstellen.

7. **Home-Assistant-Entities prüfen.**
   Insbesondere:
   - sph-ha JSON-Sensoren
   - Wetter-Hilfssensor
   - Sonnenaufgang/-untergang
   - Feiertagskalender

8. **Hardware-Pins prüfen.**
   Bei abweichender Hardware die GPIO-Belegung vor dem Flashen anpassen.

9. **Konfiguration validieren und kompilieren.**
   In ESPHome zunächst die YAML validieren und anschließend installieren.

10. **Erstinstallation flashen.**
    Bei einem neuen ESP32-S3 empfiehlt sich die erste Installation über USB. Danach können Updates per OTA erfolgen.

## Aktualisierungsverhalten

Die Anzeige wird bewusst nicht bei jeder Änderung eines Home-Assistant-Sensors vollständig neu aufgebaut.

Aktuell gilt:

- Uhr auf der Startseite: jede Minute
- kompletter Inhalt der Startseite: alle 30 Minuten
- Wetterseite: alle 30 Minuten, wenn sichtbar
- Wochenplan: stündlich, wenn sichtbar
- Seitenwechsel: sofortige Aktualisierung
- vollständiger E-Paper-Refresh: `full_update_every: 120`

Die Home-Assistant-Werte werden zwischen den Display-Updates weiterhin über die API aktualisiert und beim nächsten Seitenaufbau verwendet.

## Stundenplanlogik

Die Stundenplananzeige nutzt:

```text
sensor.stundenplan_<name>_<kürzel>_json
```

und daraus:

```text
eigener_plan
wochenkennung
```

Beibehalten werden unter anderem:

- A/B-Wochen
- Wechsel der Wochenkennung beim Sprung in die Folgewoche
- Wochenende → nächste Schulwoche
- Freitag nach Ende der letzten Unterrichtsstunde → nächste Schulwoche
- Auswahl des nächsten Schultags auf der Startseite
- A/B-Badges einzelner Unterrichtsstunden
- parallele Unterrichtseinträge

## Hinweise

Dieses Projekt ist ein eigenständiges ESPHome-Projekt und keine offizielle Erweiterung des Schulportal Hessen.

Die Schulportal-Daten werden über das separate Projekt `sph-ha` bereitgestellt:

https://github.com/leonsio/sph-ha


## reTerminal E1003: modulare Konfiguration und Display-Reinigung

`sph-reterminal-e1003.yaml` enthält nur noch die benutzerspezifischen Substitutionen
und die Pakete unter `packages/e1003/`. Bestehende Entity-IDs bleiben erhalten.
Beim Aktualisieren müssen die neuen Paketdateien und beide lokalen Komponenten
mit übernommen werden; nur die Hauptdatei auszutauschen reicht nicht.

| Dateien | Aufgabe |
| --- | --- |
| `core.yaml`, `assets.yaml` | Boot, Plattform, Verbindungen, Schriftarten und Bilder |
| `homeassistant.yaml`, `state.yaml` | Sensoren und interner Zustand |
| `settings.yaml`, `input.yaml`, `schedule.yaml` | Einstellungen, Bedienung und Zeitsteuerung |
| `runtime.yaml`, `screensaver.yaml` | Allgemeine Abläufe bzw. Screensaver-Abläufe |
| `display.yaml`, `render.yaml`, `render/*.yaml` | Display und Renderer für Uhr, Home, Start, Maxim, Elisa, Schule und Wetter |
| `components/epaper_refresh/` | Allgemeine Panel-Synchronisierung und Reinigungszyklus |
| `components/sd_screensaver/` | SD-Karte, Bilddecodierung, Screensaver-Zustand und Wiederaufnahme |

Die Renderfragmente werden über native ESPHome-`!include`-Variablen zu einer
Lambda zusammengesetzt. Ihre Reihenfolge in `render.yaml` ist wichtig, da die
Seiten gemeinsame Zeichenhelfer verwenden. IDs und Substitutionen werden weiterhin
von ESPHome aufgelöst. Lokale `fonts/`, `icons/` und `secrets.yaml` bleiben neben
der Hauptkonfiguration; sie werden nicht in das Paketverzeichnis verschoben.

Die mehrstufige Reinigung **INIT weiß → GC16 schwarz → GC16 weiß → Inhalt**
ist unabhängig vom Neuzeichnen der Oberfläche konfigurierbar:

| Einstellung in Home Assistant | Standard | Verhalten |
| --- | --- | --- |
| E1003 Cleanup beim Booten | Ein | Mehrstufige Reinigung bei Neustart/Power-On; nicht beim normalen Deep-Sleep-Wakeup |
| E1003 Full Refresh bei Seitenwechsel | Aus | Vollständiger GC16-Neuaufbau beim Wechsel, ohne Reinigungszyklus oder zusätzliche Wartezeit |
| E1003 Full Refresh Intervall | Aus | Optional vollständiger GC16-Neuaufbau alle 15, 30 oder 60 Minuten; auch im Screensaver |

Ein erzwungener Neuaufbau, ein Seitenwechsel, ein Minutenupdate oder ein
Intervall lösen keine mehrstufige Reinigung aus. Die bisherigen internen IDs
der Optionen bleiben erhalten; ihre Anzeigenamen wurden angepasst. Nach einer Reinigung werden die UI-Caches
ungültig gemacht, damit der komplette Inhalt wieder erscheint.
Die Seitenwechsel-Option wartet nur auf den tatsächlichen Hardwareabschluss.
Der bisherige zusätzliche 10-ms-Delay im Refresh-Ablauf entfällt.

Die Screensaver-Uhren verwenden nach ihrem ersten vollständigen Aufbau lokale
GC16-Teilupdates: Analog werden alte Zeigersilhouetten gelöscht und beide Zeiger
neu gezeichnet; Zifferblatt und Zahlen werden erhalten. Die Zeigerlänge wird an
den tatsächlichen Textgrenzen der Ziffern begrenzt, damit das Löschen keine Zahlen
berührt. Digital werden nur geänderte Ziffernzellen gelöscht und neu gezeichnet.
Datum und Wetter werden nur bei geänderten Anzeigeinhalten aktualisiert.
Jede geänderte Digitalziffer, die Analogzeiger, Datum, Wetter sowie linkes und
rechtes Hinweisfeld werden in getrennten Übertragungen aktualisiert. Damit
verbindet der Treiber eine geänderte Minutenstelle nicht mehr mit einem entfernten
Wetter-/Hinweisfeld zu einem großen Rechteck. Ein unverändertes Feld löst keine
Übertragung aus. Pro Übertragung bleibt die hardwarebedingte 32-Pixel-Ausrichtung
der X-Grenzen bestehen. Analog bildet die Ausdehnung der alten/neuen Zeiger das
notwendige Refresh-Rechteck; das ist keine Aktualisierung des ganzen Zifferblatts.
Nach jeder Übertragung geht der gesamte Controller in Standby.
Ein Deep-Sleep-Wakeup verliert den RAM-Bildpuffer und erfordert einen vollständigen
Aufbau der Uhr, aber keinen INIT-Schwarz-Weiß-Reinigungszyklus.

Bei beiden Uhransichten stehen oben links alle morgigen Müllabfuhren und oben
rechts alle laufenden Waschmaschinen, Trockner und Geschirrspüler aus dem
Start-Dashboard-Paket. Leere Felder haben weder Überschrift noch Platzhalter.
Ein tatsächliches Abfuhrdatum hat Vorrang vor dem relativen `days`-Wert;
undatierte `days: 1`-Einträge gelten nur am selben Tag wie das Datenpaket.
Pausierte, fertige, ausgeschaltete und nicht verfügbare Geräte werden ausgeblendet.
`packages/epaper_start_package.yaml` ergänzt dafür den unveränderten Rohzustand
`raw_state`. Das aktualisierte HA-Paket ebenfalls übernehmen und Template-Entitäten
neu laden. Ältere Pakete werden anhand der bekannten übersetzten Zustände akzeptiert.

Die Hinweise werden nur bei gültiger Uhrzeit und einem gültigen HA-Paket mit
höchstens 180 Sekunden altem `timestamp` angezeigt. Bei Programmende, Datenausfall
oder Tageswechsel wird das jeweilige Hinweisfeld wieder gelöscht. Der Screensaver
prüft alle fünf Sekunden auf geänderte Hinweise; die HA-Vorlage liefert mindestens
minütlich neue Daten. Mehrere Geräte/Abfuhren bleiben gleichzeitig sichtbar.
Die periodischen Refreshskripte für Elisa, Start und Maxim werden nur gestartet,
wenn die jeweilige Seite tatsächlich sichtbar, der Screensaver weder aktiv noch
zur Wiederaufnahme vorgemerkt und das Display frei ist. Auch neue RMV-Pakete
starten bei versteckter Elisa-Seite kein `elisa_refresh` mehr. Die Daten bleiben
im Sensorcache und werden beim nächsten Öffnen der Seite vollständig gezeichnet.
Der Kopfbereich ist für Hinweise reserviert; Uhr und Zifferblatt liegen darunter.

Der IT8951 bleibt nur bis zum Ende der physischen Wellenform aktiv: Die Komponente
wartet auf `LUTAFSR == 0`, sendet anschließend `TCON_STANDBY` und gibt erst nach
Abarbeitung des Befehls das Display frei. Der native Treiber weckt ihn vor dem
nächsten Transfer mit `SYS_RUN`. `sleep_when_done: false` ist deshalb bewusst
beibehalten: Standby erfolgt durch `epaper_refresh` nach der Synchronisierung.
Die Panelansteuerung bleibt zwischen Updates nicht mehr dauerhaft im RUN-Zustand.
Zwischen den Stufen eines Cleanups wird nicht in Standby gewechselt.

Für Graustufen bleibt GC16 aktiv; `full_update_every: 30` entspricht dem
Seeed-Beispiel. Das ist ein einzelner GC16-Flächenrefresh, kein INIT-Cleanup.
Bei ausdrücklich lokalen UI-Updates wird der interne Zähler vor dem Transfer
zurückgesetzt, damit die 30er-Grenze nicht mitten beim Scrollen oder bei einer
Minutenaktualisierung überraschend die ganze Fläche erfasst. Der stündliche
vollständige Neuaufbau bleibt erhalten.

Maxims Uhr und Countdown werden aus demselben Minuten-Zeitstempel in zwei
aufeinanderfolgenden Übertragungen aktualisiert. Der native Treiber besitzt nur
ein Dirty-Rechteck pro Übertragung: Ein gemeinsamer Transfer würde auch den
großen Zwischenraum zwischen Uhr rechts und Countdown links aktualisieren.
Während beider Transfers bleibt die Bedienung gesperrt. Bei unveränderten
Ziffern wird das jeweilige Feld nicht neu gezeichnet.

Beim Raumscrollen in der Haussteuerung werden Wetter-Navigation, WLAN-, Akku-
und Schlafsymbole nicht zusammen mit dem Inhalt gezeichnet. Änderungen an diesen
Statusanzeigen werden beim nächsten Update außerhalb eines Home-Teilupdates
übernommen. Dadurch ziehen sie das Dirty-Rechteck nicht bis in den Kopfbereich.

Nachbilder beim Wechsel von schwarzen Texten auf graue Flächen sind weiterhin
eine mögliche Grenze der direkten GC16-Umschaltung. Die Seitenwechsel-Option
erzwingt jetzt ausschließlich einen GC16-Neuaufbau; die frühere mehrstufige
Reinigung ist auf Neustarts beschränkt. Der Standard bleibt auf Wunsch aus.
VCOM (`1400`, Register `2`) und Temperaturvorgabe (`25 °C`) bleiben unverändert.
Der tatsächliche VCOM-Wert eines individuellen Panels lässt sich nicht aus Fotos
bestimmen. Das Verblassen unveränderter Bereiche passt zur bislang dauerhaft
aktiven Panelansteuerung; die Ursache und die Wirkung des Standby-Fixes müssen
am realen Gerät bestätigt werden. Ein speziell für E1003 dokumentierter Serienfehler
mit genau diesem Symptombild wurde bei der Recherche nicht gefunden.

Quellen zur Ansteuerung:

- [Seeed ESPHome Display-Cookbook](https://wiki.seeedstudio.com/reterminal_e10xx_esphome/): GC16, Graustufen, Full-Refresh nach 30 Updates.
- [Seeed IT8951-Referenztreiber](https://github.com/Seeed-Projects/Seeed_GxEPD2/blob/master/src/it8951/GxEPD2_it103_1872x1404.cpp): `powerOff()` nutzt `STANDBY`.
- [IT8951-Referenzheader](https://github.com/ZinggJM/GxEPD2/blob/master/src/it8951/GxEPD2_it78_1872x1404.h): Abschalten der Panelspannungen gegen zeitliches Verblassen.
- [ESPHome IT8951](https://esphome.io/components/display/it8951/): GC16 für Graustufen; reduzierte Graustufen-Wellenformen können falsch darstellen.

Prüfung der Refresh-Zustandsmaschine ohne Hardware:

```sh
python -m unittest discover -s tests -v
```

Für Konfigurationsprüfung und Firmware-Build werden die eigenen lokalen Schriften,
Symbole und Zugangsdaten benötigt:

```sh
esphome config sph-reterminal-e1003.yaml
esphome compile sph-reterminal-e1003.yaml
```

Der Host-Regressionstest prüft die physische Refresh-Barriere, Writer-Restore,
Standby erst nach Wellenformende und erneutes Aktualisieren nach Standby.
Die Cleanup-Policy wird zusätzlich mit der echten YAML-Lambda auf dem Host geprüft.
Weitere Tests kompilieren den echten Maxim-Teilrenderer mit Zeichenrekordern
und prüfen die Trennung der Uhr-/Countdown-Rechtecke sowie die Home-Status-Guards.
Der vollständige Screensaver-Uhr-Renderer wird ebenfalls auf dem Host kompiliert:
Analog-Minutenupdates ohne Zifferblatt-Neuaufbau, einzelne Digitalziffern,
unveränderte/geänderte Fußzeilen, Mitternacht und erzwungener Neuaufbau.
Zusätzliche Tests prüfen die Dirty-Grenzen einzelner Ziffern und Hinweise,
mehrere gleichzeitige Geräte/Mülltonnen, Zustandsfilter, Ablauf der Datenfrist
und Tages-/Monats-/Jahreswechsel.
Diese Änderung wurde ohne ESPHome-Firmware-Build und ohne angeschlossenes Panel
validiert. Der Test ersetzt keinen Paneltest.

### Auffälligkeiten im Log vom 23.10.2026

Der nachgereichte Crash-Backtrace zeigt `vApplicationStackOverflowHook` und
bestätigt damit einen Task-Stacküberlauf. Der konkrete Task wird im Ausschnitt
nicht genannt. Der große Renderer läuft im ESPHome-Loop; dessen Standardstack
war bislang 8192 Byte. `esp32.framework.advanced.loop_task_stack_size` wird jetzt
auf 32768 Byte erhöht. Das reserviert zusätzlich 24 KiB internes RAM und ist eine
gezielte Maßnahme für den wahrscheinlichen betroffenen Task, kein Nachweis, dass
sämtliche Absturzursachen behoben sind.

Bei jedem API-Verbindungsaufbau zeigt `boot_diag` den Build-Zeitpunkt, den
ESP-IDF-Resetgrund und die konfigurierte Stackgröße. Nach UI-Refreshes zeigt
`memory_diag` den aktuellen Task, seine minimale bisherige Stackreserve und
freies internes RAM. Diese Werte müssen am Gerät unter wiederholten Seitenwechseln
beobachtet werden; Host-Tests können den Xtensa-Stackbedarf nicht bestimmen.
OTA-Rollback bleibt aktiv. Ein früher Absturz kann deshalb weiterhin die vorige
Firmware starten; deren Build-Zeitpunkt und bekannte alte Fehlermeldungen sind
ein Hinweis auf diesen Wechsel.

- `Screensaver Bilder >> 0` kam durch bedingungsloses Publizieren alle fünf
  Sekunden. Die Anzahl und der Dateiname werden jetzt nur initial oder bei
  Änderung veröffentlicht. Null bedeutet keine gefundenen Bilddateien und ist
  für den Uhrmodus kein Fehler.
- Der fehlende Codepoint `U+F0AAC` gehört zum Geschirrspüler. Er wurde im tatsächlich
  verwendeten Font `mdi_start_appliance` ergänzt.
- Die Wakeup-Diagnose konnte während ihres künstlichen 250-ms-Delays erneut
  gestartet werden. Der Delay wurde entfernt; die bestehende Einmal-Markierung
  wird jetzt ohne dazwischenliegende Wartezeit gesetzt.
- Zeichenoperationen blockierten teilweise 60–455 ms; diese Warnungen sind keine
  Display-Timeouts. Lokale Uhrupdates reduzieren die Zeichenarbeit, die vollständigen
  Schul-/Wetterseiten können weiterhin die 50-ms-Warnschwelle überschreiten.
- Auf einen WLAN-Roamingwechsel folgt ein API-Verbindungsabbruch mit anschließend
  erfolgreichem Wiederverbinden. Im Ausschnitt stehen keine IT8951-Timeouts oder
  Treiberfehler; die Standby-Abschlüsse sind sichtbar.
- Der Hinweis `flash_chip: winbond` ist eine Optimierungsempfehlung. Der konkrete
  Flash-Chip wurde nicht anhand des Logs umkonfiguriert.
