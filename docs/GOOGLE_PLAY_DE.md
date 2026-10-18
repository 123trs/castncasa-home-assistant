# CastnCasa – Google-Play-Texte (DE)

Stand: CastnCasa 1.0.2

## App-Name

CastnCasa

## Kurzbeschreibung

Schichtkalender mit Home-Assistant-Anbindung für Anwesenheit und Heizungsprognosen.

## Vollständige Beschreibung

CastnCasa macht wechselnde Arbeitszeiten für dein Smart Home nutzbar.

Lege Früh-, Spät- und Nachtschichten, freie Tage, Urlaub oder eigene Profile einmal an und verteile sie anschließend schnell im Monatskalender. CastnCasa kann deine Planung direkt mit deiner eigenen Home-Assistant-Instanz verbinden.

Damit kann Home Assistant nicht nur sehen, wann jemand laut Dienstplan arbeitet, sondern auch geplante Abwesenheiten, nächste Abfahrten und erwartete Heimkehrzeiten für Automationen verwenden.

CastnCasa unterstützt mehrere Bewohner. Jeder Bewohner wird separat gekoppelt und erhält eigene Kalender- und Prognosedaten. Reale Anwesenheit hat dabei immer Vorrang vor der Dienstplan-Prognose.

### Zwei Synchronisationswege

- Ist Home Assistant von außen erreichbar, synchronisiert CastnCasa Änderungen sofort über die externe Home-Assistant-Adresse.
- Ist Home Assistant nur lokal erreichbar, speichert CastnCasa Änderungen auf dem Smartphone und synchronisiert automatisch, sobald das Gerät wieder im Heimnetz ist.

Die Präsenzerkennung ist vom Kalender-Sync getrennt und kann zusätzlich Home-Assistant-Personen bzw. Device-Tracker berücksichtigen.

### CastnCasa Heat

CastnCasa Heat stellt Home Assistant eine leicht nutzbare Heizungsprognose bereit:

- komfort
- reduziert
- wiederaufheizen

Damit können eigene Home-Assistant-Automationen Energie sparen, wenn voraussichtlich länger niemand zu Hause ist, und vor der erwarteten Heimkehr rechtzeitig wieder Komfort herstellen.

CastnCasa steuert die Heizung nicht selbst. Die eigentliche Automation bleibt vollständig beim Anwender.

### Datenschutz

Kalender-, Anwesenheits- und Kopplungsdaten werden direkt zwischen der CastnCasa-App und der Home-Assistant-Instanz des Anwenders übertragen. Für diese Daten ist kein CastnCasa-Cloud-Dienst erforderlich.

Weitere Informationen und die Home-Assistant-Integration:
https://wattzahls.de/castncasa/

## Versionshinweise 1.0.2

- Zwei Sync-Wege: sofort remote oder automatisch im Heimnetz
- Präsenzerkennung unabhängig vom Kalender-Sync
- Reale Anwesenheit hat Vorrang vor der Dienstplan-Prognose
- Verbesserte Home-Assistant-Sensoren für Anwesenheit, last_seen, Abwesenheit, Abfahrt, Heimkehr und Planabweichung
- CastnCasa Heat nutzt die reale Anwesenheit als Sicherheitsvorrang

## Hinweise für geschlossene Tester

Bitte insbesondere testen:

- neue Kopplung per QR-Code
- mehrere Bewohner
- Änderungen bei extern erreichbarem Home Assistant
- Änderungen bei nur lokal erreichbarem Home Assistant
- automatische Nachsynchronisierung im Heimnetz
- Präsenzerkennung unabhängig vom Kalender-Sync
- Nachtschichten über Mitternacht
- Bearbeiten und Löschen von Schichtprofilen
- Wochenenden und gesetzliche Feiertage
- Home-Assistant-Sensoren und CastnCasa-Heat-Prognose
