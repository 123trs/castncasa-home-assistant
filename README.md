# CastnCasa for Home Assistant

CastnCasa brings household shift and absence forecasts from the CastnCasa Android app into Home Assistant and combines them with real resident presence.

## What the integration provides

A fresh installation creates household forecast/presence entities, public-holiday and weekend calendars, and the CastnCasa Heat 1.0 recommendation entities. Each paired resident adds eleven resident-specific entities, including planned absence, actual presence, last seen, next departure, expected return and plan deviation.

CastnCasa keeps **planned** and **effective** absence separate. Actual Home Assistant presence has priority, followed by a fresh CastnCasa app presence heartbeat; the duty-plan forecast is the fallback. CastnCasa Heat recommends `komfort`, `reduziert`, or `wiederaufheizen`, but it does not switch heating equipment by itself. Confirmed presence always forces the recommendation back to comfort.

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

CastnCasa supports two operating modes automatically:

- If Home Assistant is externally reachable, the app synchronizes schedule changes immediately through the configured remote Home Assistant URL.
- If Home Assistant is only reachable at home, no external Home Assistant access is required. Changes stay queued securely on the phone and synchronize automatically as soon as the phone is back on the home network and the local Home Assistant URL is reachable.

Presence is handled separately from calendar synchronization. A reachable local Home Assistant endpoint acts as the home-network presence signal; remote/network signals can complement it. Native Home Assistant presence remains an additional independent signal, and confirmed actual presence always wins over an absence forecast.

## Updates

Future integration updates can be installed through HACS. Existing entity unique IDs are treated as a compatibility contract for the 1.x series.

## Privacy and network model

Pairing, schedule synchronization and app presence heartbeats happen directly between the CastnCasa app and the user's Home Assistant instance. The Home Assistant status endpoint can advertise a remote URL and a local/home-network URL so the app can select the best available path automatically. API requests use the paired device credentials and encrypted request bodies. CastnCasa does not require a CastnCasa cloud service for household schedule or presence data.

## Support

Product and setup website: https://wattzahls.de/castncasa/

Issues: https://github.com/123trs/castncasa-home-assistant/issues
