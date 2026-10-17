# CastnCasa – Käufer-Setup für Home Assistant

Diese Anleitung führt von der Installation bis zur ersten synchronisierten Person in Home Assistant.

## Voraussetzungen

- CastnCasa für Android
- Home Assistant mit HACS
- Smartphone und Home Assistant müssen sich gegenseitig über die von Home Assistant verwendete URL erreichen können

## 1. CastnCasa-Integration über HACS installieren

1. In Home Assistant **HACS** öffnen.
2. **Integrationen** öffnen.
3. Über das Menü **Benutzerdefinierte Repositories** öffnen.
4. Als Repository eintragen: `https://github.com/123trs/castncasa-home-assistant`
5. Kategorie: **Integration**.
6. **CastnCasa** installieren.
7. Home Assistant neu starten.

Updates der Integration werden anschließend wie andere HACS-Updates angeboten.

## 2. CastnCasa in Home Assistant einrichten

1. **Einstellungen → Geräte & Dienste** öffnen.
2. **Integration hinzufügen** wählen.
3. Nach **CastnCasa** suchen.
4. CastnCasa hinzufügen.

Die Grundintegration wird nur einmal pro Home-Assistant-Instanz eingerichtet.

## 3. Bewohner koppeln

Für jedes Smartphone bzw. jeden Bewohner wird eine eigene Kopplung angelegt.

1. In Home Assistant **Einstellungen → Geräte & Dienste → CastnCasa** öffnen.
2. **Konfigurieren** wählen.
3. **Neuen Bewohner koppeln** öffnen.
4. Home Assistant zeigt einen einmaligen QR-Code an.
5. In der Android-App **CastnCasa → Einstellungen → Home Assistant → Mit Home Assistant verbinden** öffnen.
6. **QR-Code scannen** wählen und den QR-Code aus Home Assistant scannen.
7. Nach erfolgreicher Kopplung synchronisiert CastnCasa den Bewohner, seine Schichten und die Abwesenheitsprognose.

Der QR-Code ist nur einmal verwendbar und 5 Minuten gültig.

## 4. Bewohner und Bundesland festlegen

In der CastnCasa-App unter **Einstellungen**:

- den Bewohnernamen eintragen;
- das Bundesland für gesetzliche Feiertage auswählen;
- bei Bedarf die Bewohnerfarbe festlegen;
- Schichtprofile anlegen oder bearbeiten.

Änderungen am Kalender werden anschließend automatisch mit Home Assistant synchronisiert.

## 5. Was Home Assistant erhält

Ohne gekoppelte Bewohner stellt CastnCasa 16 Basis-Entitäten bereit. Jeder gekoppelte Bewohner ergänzt 7 weitere Entitäten.

Dazu gehören unter anderem:

- aktuell geplante Abwesenheit des Haushalts;
- nächster Beginn und Ende einer geplanten Leerphase;
- erwartete nächste Heimkehr;
- Wochenend- und Feiertagskalender;
- Bewohner-Kalender und Monatskalender;
- CastnCasa-Heat-Prognose mit Empfehlung `komfort`, `reduziert` oder `wiederaufheizen`.

## 6. CastnCasa Heat 1.0

Unter **CastnCasa → Konfigurieren → Heat-Einstellungen** lassen sich drei Werte einstellen:

- **Mindest-Leerphase**: Ab welcher geplanten Abwesenheitsdauer eine Absenkung sinnvoll ist.
- **Wiederaufheiz-Vorlauf**: Wie viele Minuten vor der erwarteten Heimkehr wieder aufgeheizt werden soll.
- **Komfortpuffer**: Zusätzlicher zeitlicher Sicherheitsabstand vor der erwarteten Heimkehr.

CastnCasa Heat steuert die Heizung nicht selbst. Es stellt Prognosen und Empfehlungen als Home-Assistant-Entitäten bereit. Die eigentliche Heizungsautomation bleibt beim Anwender.

**Wichtig:** Reale Anwesenheit in Home Assistant hat immer Vorrang vor einer Dienstplan-Prognose.

## 7. Zweiten oder weiteren Bewohner koppeln

Den Kopplungsvorgang einfach erneut über **CastnCasa → Konfigurieren → Neuen Bewohner koppeln** starten. Jeder Bewohner erhält seine eigenen Entitäten und Kalender.

## 8. Verbindung prüfen oder Bewohner abmelden

In der Android-App unter **Einstellungen → Home Assistant** kann die Verbindung geprüft werden. Ein Bewohner kann dort auch sauber von Home Assistant abgemeldet werden.

## Fehlerbehebung

### QR-Code ist abgelaufen

In Home Assistant erneut **Neuen Bewohner koppeln** öffnen. Dadurch wird ein neuer einmaliger QR-Code erzeugt.

### Smartphone erreicht Home Assistant nicht

Prüfen, ob die im Home Assistant verwendete interne oder externe URL vom Smartphone erreichbar ist. Bei externer Nutzung muss die Home-Assistant-URL auch außerhalb des Heimnetzes funktionieren.

### Kalender ist noch leer

In CastnCasa zuerst einen Bewohnernamen setzen und mindestens einen Kalendereintrag bzw. eine Schicht anlegen. Danach die Verbindung unter **Einstellungen → Home Assistant** prüfen.

### Integration aktualisieren

HACS öffnen und verfügbare CastnCasa-Updates installieren. Danach Home Assistant neu starten, wenn HACS dies verlangt.

## Datenschutz

Die Kopplung und Synchronisierung erfolgen direkt zwischen der CastnCasa-App und der Home-Assistant-Instanz des Anwenders. Der für die Verbindung erzeugte Gerätetoken wird auf Android geschützt gespeichert.

Support und Produktseite: https://wattzahls.de/castncasa/

Fehler melden: https://github.com/123trs/castncasa-home-assistant/issues
