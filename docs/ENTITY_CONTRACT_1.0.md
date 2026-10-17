# CastnCasa Home Assistant 1.0 entity contract

CastnCasa 1.x freezes the Home Assistant entity identity contract.

Base: 16 entities without residents.
Per resident: 7 additional entities.

Stable base unique-ID suffixes:
active_residents
planned_away_now
next_house_empty_from
next_house_empty_until
next_expected_return
planned_house_empty
holidays_calendar
weekends_calendar
heat_empty_duration
heat_time_until_home
heat_recommended_mode
heat_reheat_from
heat_forecast_status
heat_forecast_confidence
heat_lowering_recommended
heat_reheating

Stable resident suffix patterns:
resident_<id>_today
resident_<id>_tomorrow
resident_<id>_next_planned_absence
resident_<id>_expected_home
resident_<id>_planned_away
resident_<id>_calendar
resident_<id>_month_calendar

Compatibility rules:
- integration domain stays castncasa
- existing unique IDs do not change in 1.x without migration
- customer-visible default names are regression-tested
- CastnCasa Heat remains forecast-only; real HA presence has priority
