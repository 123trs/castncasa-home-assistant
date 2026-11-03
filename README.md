# CastnCasa for Home Assistant

<p align="center"><img src="custom_components/castncasa/brand/logo.png" alt="CastnCasa" width="512"></p>

**CastnCasa gives Home Assistant a view of what happens next.** Home Assistant already knows who is home now; CastnCasa adds when the household is expected to become empty, when someone should return, and how that forecast compares with actual presence.

The Android shift calendar is a convenient way to enter changing schedules, but the real Home Assistant value is **predictive presence**: automations can plan ahead instead of reacting only after everybody has left.

**One-time purchase. No subscription. No CastnCasa cloud required for household schedule or presence data.**

A real example: a heating schedule may switch from reduced to comfort at 04:00 even though everybody is scheduled to leave at 05:30. CastnCasa can expose that upcoming empty period before it starts. An automation can keep an already active reduction in place when the comfort phase would be too short, then resume normal heating before the expected return. Actual presence always has priority over the schedule forecast.

Typical use cases include:

- reduce heating during longer planned absences and start reheating before the expected return,
- avoid briefly reheating an already reduced house when another useful empty period is about to begin,
- use upcoming departures and returns in Home Assistant automations,
- start vacuuming or other non-critical routines when the home is effectively empty,
- combine several residents into one household absence forecast,
- keep shift and presence data local between the Android app and Home Assistant.

Product website: https://wattzahls.de/castncasa/

## What the integration provides

A fresh installation creates household forecast/presence entities, public-holiday and weekend calendars, and the CastnCasa Heat 1.0 recommendation entities. Each paired resident adds eleven resident-specific entities, including planned absence, actual presence, last seen, next departure, expected return and plan deviation.

CastnCasa keeps **planned** and **effective** absence separate. Actual Home Assistant presence has priority, followed by a fresh CastnCasa app presence heartbeat; the duty-plan forecast is the fallback. CastnCasa Heat recommends `komfort`, `reduziert`, or `wiederaufheizen`, but it does not switch heating equipment by itself. It also publishes **Absenkung halten** when a sufficiently long shared empty period will start before the configured **Mindest-Komfortphase** has elapsed. This signal is intended to keep an already active reduction in place; it does not recommend lowering the heating early solely because departure is approaching. Confirmed actual presence still has priority over an absence forecast.

The Heat settings are:

- **Minimum empty period**: how long a shared household absence must last before reduction is useful.
- **Reheat lead time**: when normal reheating should start before the expected return.
- **Comfort buffer**: additional safety time before the expected return.
- **Minimum comfort period**: minimum useful occupied period before an already reduced heating system should be brought back to comfort.

## Ready-to-use blueprints

Two reusable automation blueprints are included so the forecast can be used without manually wiring every state transition:

- **[CastnCasa: Aktionen nach Heat-Modus](blueprints/automation/123trs/castncasa_heat_mode_actions.yaml)** — runs user-selected actions when Heat changes between `komfort`, `reduziert` and `wiederaufheizen`.
- **[CastnCasa: Aktionen bei effektiv leer / bewohnt](blueprints/automation/123trs/castncasa_effective_empty_actions.yaml)** — runs user-selected actions when the household becomes effectively empty or occupied again.

Both blueprints deliberately contain **no hard-coded heating or device commands**. CastnCasa supplies the forecast; the user decides what Home Assistant should do.

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

## CastnCasa calendar card

From version 1.0.14 the integration ships and loads the tested CastnCasa calendar card automatically. Add this card to a Home Assistant dashboard:

```yaml
type: custom:castncasa-time-calendar
title: Abwesenheit · Alle Bewohner
initial_view: dayGridMonth
include_holidays: true
```

The month view discovers the currently paired resident calendars automatically. On desktop/tablet, shift absence is positioned and sized from the **actual start and end times**, not from the shift name. The legend only lists shifts that occur in the currently selected month. On phones, resident shifts are shown as compact, color-coded short-name chips stacked vertically; public holidays use the compact `FT` chip. Calendar changes are checked every 60 seconds and only trigger a refresh when CastnCasa data actually changed, while the currently selected month is preserved.

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
