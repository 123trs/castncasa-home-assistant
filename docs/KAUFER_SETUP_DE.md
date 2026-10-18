# CastnCasa – Käufer-Setup für Home Assistant

Diese Anleitung führt von der Installation bis zur ersten synchronisierten Person in Home Assistant.

## Voraussetzungen

- CastnCasa für Android
- Home Assistant mit HACS
- Smartphone und Home Assistant müssen sich für Kopplung und Synchronisierung entweder über die externe Home-Assistant-Adresse oder im Heimnetz erreichen können

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

## 5. Synchronisierung und Anwesenheit

CastnCasa 1.0.2 unterstützt zwei Synchronisationswege:

- **Home Assistant extern erreichbar:** Änderungen werden sofort über die externe Home-Assistant-Adresse synchronisiert.
- **Home Assistant nur lokal erreichbar:** Änderungen bleiben auf dem Smartphone zwischengespeichert und werden automatisch synchronisiert, sobald das Smartphone wieder im Heimnetz ist.

Die Präsenzerkennung arbeitet unabhängig vom Kalender-Sync. Zusätzlich kann Home Assistant eigene `person`- bzw. `device_tracker`-Signale verwenden. Bestätigte reale Anwesenheit hat immer Vorrang vor der Dienstplan-Prognose.

## 6. Was Home Assistant erhält

Ohne gekoppelte Bewohner stellt CastnCasa 16 Basis-Entitäten bereit. Jeder gekoppelte Bewohner ergänzt 10 weitere Entitäten.

Dazu gehören unter anderem:

- aktuell geplante Abwesenheit des Haushalts;
- tatsächliche Anwesenheit je Bewohner;
- `last_seen` je Bewohner;
- geplante Abwesenheit je Bewohner;
- nächste Abfahrt;
- erwartete Heimkehr;
- Abweichung vom Plan;
- nächster Beginn und Ende einer geplanten Leerphase;
- Wochenend- und Feiertagskalender;
- Bewohner-Kalender und Monatskalender;
- CastnCasa-Heat-Prognose mit Empfehlung `komfort`, `reduziert` oder `wiederaufheizen`.

## 7. CastnCasa Heat 1.0

Unter **CastnCasa → Konfigurieren → Heat-Einstellungen** lassen sich drei Werte einstellen:

- **Mindest-Leerphase**: Ab welcher geplanten Abwesenheitsdauer eine Absenkung sinnvoll ist.
- **Wiederaufheiz-Vorlauf**: Wie viele Minuten vor der erwarteten Heimkehr wieder aufgeheizt werden soll.
- **Komfortpuffer**: Zusätzlicher zeitlicher Sicherheitsabstand vor der erwarteten Heimkehr.

CastnCasa Heat steuert die Heizung nicht selbst. Es stellt Prognosen und Empfehlungen als Home-Assistant-Entitäten bereit. Die eigentliche Heizungsautomation bleibt beim Anwender.

**Wichtig:** Reale Anwesenheit in Home Assistant hat immer Vorrang vor einer Dienstplan-Prognose.

## 8. Zweiten oder weiteren Bewohner koppeln

Den Kopplungsvorgang einfach erneut über **CastnCasa → Konfigurieren → Neuen Bewohner koppeln** starten. Jeder Bewohner erhält seine eigenen Entitäten und Kalender.

## 9. Verbindung prüfen oder Bewohner abmelden

In der Android-App unter **Einstellungen → Home Assistant** kann die Verbindung geprüft werden. Ein Bewohner kann dort auch sauber von Home Assistant abgemeldet werden.

## Fehlerbehebung

### QR-Code ist abgelaufen

In Home Assistant erneut **Neuen Bewohner koppeln** öffnen. Dadurch wird ein neuer einmaliger QR-Code erzeugt.

### Smartphone erreicht Home Assistant unterwegs nicht

Das ist bei einer rein lokalen Home-Assistant-Installation zulässig. CastnCasa speichert Änderungen lokal zwischen und synchronisiert sie automatisch, sobald das Smartphone wieder im Heimnetz ist.

Wenn Home Assistant extern erreichbar sein soll, prüfen, ob die externe Home-Assistant-Adresse auch außerhalb des Heimnetzes funktioniert.

### Änderungen wurden noch nicht synchronisiert

Bei einer nur lokal erreichbaren Home-Assistant-Instanz zuerst prüfen, ob das Smartphone wieder mit dem Heimnetz verbunden ist. Die Synchronisierung wird dann automatisch nachgeholt.

### Kalender ist noch leer

In CastnCasa zuerst einen Bewohnernamen setzen und mindestens einen Kalendereintrag bzw. eine Schicht anlegen. Danach die Verbindung unter **Einstellungen → Home Assistant** prüfen.

### Integration aktualisieren

HACS öffnen und verfügbare CastnCasa-Updates installieren. Danach Home Assistant neu starten, wenn HACS dies verlangt.

## Datenschutz

Die Kopplung, Synchronisierung und App-Präsenzsignale erfolgen direkt zwischen der CastnCasa-App und der Home-Assistant-Instanz des Anwenders. Der für die Verbindung erzeugte Gerätetoken wird auf Android geschützt gespeichert. Für Kalender- und Anwesenheitsdaten ist kein CastnCasa-Cloud-Dienst erforderlich.

Support und Produktseite: https://wattzahls.de/castncasa/

Fehler melden: https://github.com/123trs/castncasa-home-assistant/issues
