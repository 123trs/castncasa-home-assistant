# CastnCasa for Home Assistant

CastnCasa brings household shift and absence forecasts from the CastnCasa Android app into Home Assistant and combines them with real resident presence.

## What the integration provides

A fresh installation creates household forecast entities, public-holiday and weekend calendars, and the CastnCasa Heat 1.0 forecast entities. Each paired resident adds ten resident-specific entities, including planned absence, actual presence, last seen, next departure, expected return and plan deviation.

Actual presence has priority over the schedule forecast. CastnCasa can use Home Assistant `person.<name>` / `device_tracker.<name>` entities and also accepts an encrypted heartbeat from the paired CastnCasa app. This presence path is independent from calendar synchronization.

CastnCasa Heat recommends `komfort`, `reduziert`, or `wiederaufheizen`, but it does not switch heating equipment by itself. If a resident is confirmed home, CastnCasa Heat stays on the comfort recommendation even when the schedule forecast says the household should be empty.

## Installation with HACS

1. In HACS, add `123trs/castncasa-home-assistant` as a **custom repository** of type **Integration**.
2. Install **CastnCasa**.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and add **CastnCasa**.
5. Open the CastnCasa integration and choose **Configure → Pair resident**.
6. Open CastnCasa on the Android phone and scan the one-time QR code.
7. In the CastnCasa app settings, select the German federal state used for public holidays. It is synchronized to Home Assistant with the resident schedule.

The pairing code is single-use and expires after five minutes.

### German buyer setup

A step-by-step German setup guide for customers is available here:

[CastnCasa – Käufer-Setup für Home Assistant](docs/KAUFER_SETUP_DE.md)

## Synchronization and presence

CastnCasa supports two operating modes:

- If Home Assistant is externally reachable, the app can synchronize schedule changes and presence immediately through the remote HA address.
- If Home Assistant is only reachable at home, the app can keep changes locally and synchronize them automatically after returning to the home network. Presence is handled separately from schedule synchronization; a local-home heartbeat that disappears is treated as an away signal after the presence timeout.

Native Home Assistant presence remains an additional independent signal and confirmed presence always wins over an absence forecast.

## Updates

Future integration updates can be installed through HACS. Existing entity unique IDs are treated as a compatibility contract for the 1.x series.

## Privacy and network model

Pairing, schedule synchronization and app presence heartbeats happen directly between the CastnCasa app and the user's Home Assistant instance. API requests use the paired device credentials and encrypted request bodies. CastnCasa does not require a CastnCasa cloud service for household schedule or presence data.

## Support

Product and setup website: https://wattzahls.de/castncasa/

Issues: https://github.com/123trs/castncasa-home-assistant/issues
