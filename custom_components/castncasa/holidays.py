"""German state-wide public holidays used by CastnCasa."""

from __future__ import annotations

from datetime import date, timedelta

FEDERAL_STATES = {
    "BW": "Baden-Württemberg",
    "BY": "Bayern",
    "BE": "Berlin",
    "BB": "Brandenburg",
    "HB": "Bremen",
    "HH": "Hamburg",
    "HE": "Hessen",
    "MV": "Mecklenburg-Vorpommern",
    "NI": "Niedersachsen",
    "NW": "Nordrhein-Westfalen",
    "RP": "Rheinland-Pfalz",
    "SL": "Saarland",
    "SN": "Sachsen",
    "ST": "Sachsen-Anhalt",
    "SH": "Schleswig-Holstein",
    "TH": "Thüringen",
}


def easter_sunday(year: int) -> date:
    """Return Gregorian Easter Sunday using Meeus/Jones/Butcher."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def repentance_day(year: int) -> date:
    """Return Buß- und Bettag for Saxony."""
    anchor = date(year, 11, 23)
    back = (anchor.weekday() - 2) % 7
    if back == 0:
        back = 7
    return anchor - timedelta(days=back)


def public_holidays_for_year(year: int, state_code: str) -> dict[date, str]:
    """Return state-wide public holidays for one German federal state."""
    if state_code not in FEDERAL_STATES:
        return {}
    easter = easter_sunday(year)
    holidays = {
        date(year, 1, 1): "Neujahr",
        easter - timedelta(days=2): "Karfreitag",
        easter + timedelta(days=1): "Ostermontag",
        date(year, 5, 1): "Tag der Arbeit",
        easter + timedelta(days=39): "Christi Himmelfahrt",
        easter + timedelta(days=50): "Pfingstmontag",
        date(year, 10, 3): "Tag der Deutschen Einheit",
        date(year, 12, 25): "1. Weihnachtstag",
        date(year, 12, 26): "2. Weihnachtstag",
    }
    if state_code in {"BW", "BY", "ST"}:
        holidays[date(year, 1, 6)] = "Heilige Drei Könige"
    if state_code in {"BE", "MV"}:
        holidays[date(year, 3, 8)] = "Internationaler Frauentag"
    if state_code == "BB":
        holidays[easter] = "Ostersonntag"
        holidays[easter + timedelta(days=49)] = "Pfingstsonntag"
    if state_code in {"BW", "BY", "HE", "NW", "RP", "SL"}:
        holidays[easter + timedelta(days=60)] = "Fronleichnam"
    if state_code == "SL":
        holidays[date(year, 8, 15)] = "Mariä Himmelfahrt"
    if state_code == "TH":
        holidays[date(year, 9, 20)] = "Weltkindertag"
    if state_code in {"BB", "HB", "HH", "MV", "NI", "SH", "SN", "ST", "TH"}:
        holidays[date(year, 10, 31)] = "Reformationstag"
    if state_code in {"BW", "BY", "NW", "RP", "SL"}:
        holidays[date(year, 11, 1)] = "Allerheiligen"
    if state_code == "SN":
        holidays[repentance_day(year)] = "Buß- und Bettag"
    if state_code == "BE" and year == 2025:
        holidays[date(2025, 5, 8)] = "80. Jahrestag der Befreiung vom Nationalsozialismus"
    return holidays


def special_days_between(start: date, end: date, state_code: str) -> dict[str, list[dict[str, str]]]:
    """Return public holidays and weekend dates within an inclusive range."""
    holiday_map: dict[date, str] = {}
    for year in range(start.year, end.year + 1):
        holiday_map.update(public_holidays_for_year(year, state_code))
    holidays = [
        {"day": day.isoformat(), "name": name}
        for day, name in sorted(holiday_map.items())
        if start <= day <= end
    ]
    weekends: list[dict[str, str]] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() >= 5:
            weekends.append(
                {
                    "day": cursor.isoformat(),
                    "weekday": "sa" if cursor.weekday() == 5 else "so",
                }
            )
        cursor += timedelta(days=1)
    return {"holidays": holidays, "weekends": weekends}
