# CastnCasa for Home Assistant

CastnCasa brings household shift and absence forecasts from the CastnCasa Android app into Home Assistant.

## What the integration provides

A fresh installation creates household forecast entities, public-holiday and weekend calendars, and the CastnCasa Heat 1.0 forecast entities. Each paired resident adds seven resident-specific entities.

CastnCasa Heat is **forecast-only**: it recommends `komfort`, `reduziert`, or `wiederaufheizen`, but it does not switch heating equipment. Real Home Assistant presence should always take priority over schedule forecasts.

## Installation with HACS

1. In HACS, add `123trs/castncasa-home-assistant` as a **custom repository** of type **Integration**.
2. Install **CastnCasa**.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and add **CastnCasa**.
5. Open the CastnCasa integration and choose **Configure → Pair resident**.
6. Open CastnCasa on the Android phone and scan the one-time QR code.
7. In the CastnCasa app settings, select the German federal state used for public holidays. It is synchronized to Home Assistant with the resident schedule.

The pairing code is single-use and expires after five minutes.

## Updates

Future integration updates can be installed through HACS. Existing entity unique IDs are treated as a compatibility contract for the 1.x series.

## Privacy and network model

Pairing and schedule synchronization happen directly between the CastnCasa app and the user's Home Assistant instance. Device tokens are stored by Home Assistant for authenticated local API access.

## Support

Website: https://wattzahls.de/

Issues: https://github.com/123trs/castncasa-home-assistant/issues