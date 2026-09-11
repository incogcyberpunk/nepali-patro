#!/usr/bin/env python3
"""Bikram Sambat <-> Gregorian conversion and Nepali calendar events.

Standard library only, on purpose: this used to depend on the `nepali-datetime`
pip package, which vanished when Python was upgraded to 3.14.

Month-length table below is the published Bikram Sambat calendar data taken from
amitgaru/nepali-datetime (Apache-2.0), file nepali_datetime/data/calendar_bs.csv.
BS month lengths are decided per year by the Panchanga committee and cannot be
derived from a formula, so every implementation ships this table.
"""

from __future__ import annotations

import argparse
import bisect
import datetime
import json
import os
import subprocess
import tempfile
import urllib.request

# --- calendar table -------------------------------------------------------

# Days in each of the 12 BS months, keyed by BS year (Baisakh .. Chait).
BS_MONTH_DAYS = {
    1975: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    1976: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    1977: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    1978: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    1979: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    1980: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    1981: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),
    1982: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    1983: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    1984: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    1985: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),
    1986: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    1987: (31, 32, 31, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    1988: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    1989: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),
    1990: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    1991: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),
    1992: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    1993: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    1994: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    1995: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),
    1996: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    1997: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    1998: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    1999: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2000: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2001: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2002: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2003: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2004: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2005: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2006: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2007: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2008: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 29, 31),
    2009: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2010: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2011: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2012: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),
    2013: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2014: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2015: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2016: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),
    2017: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2018: (31, 32, 31, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2019: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2020: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),
    2021: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2022: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),
    2023: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2024: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),
    2025: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2026: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2027: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2028: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2029: (31, 31, 32, 31, 32, 30, 30, 29, 30, 29, 30, 30),
    2030: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2031: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2032: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2033: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2034: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2035: (30, 32, 31, 32, 31, 31, 29, 30, 30, 29, 29, 31),
    2036: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2037: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2038: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2039: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),
    2040: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2041: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2042: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2043: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),
    2044: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2045: (31, 32, 31, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2046: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2047: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),
    2048: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2049: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),
    2050: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2051: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),
    2052: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2053: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),
    2054: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2055: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2056: (31, 31, 32, 31, 32, 30, 30, 29, 30, 29, 30, 30),
    2057: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2058: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2059: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2060: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2061: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2062: (31, 31, 31, 32, 31, 31, 29, 30, 29, 30, 29, 31),
    2063: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2064: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2065: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2066: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 29, 31),
    2067: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2068: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2069: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2070: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),
    2071: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2072: (31, 32, 31, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2073: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2074: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),
    2075: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2076: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),
    2077: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2078: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),
    2079: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2080: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),
    2081: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2082: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2083: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2084: (31, 31, 32, 31, 31, 30, 30, 30, 29, 30, 30, 30),
    2085: (31, 32, 31, 32, 30, 31, 30, 30, 29, 30, 30, 30),
    2086: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2087: (31, 31, 32, 31, 31, 31, 30, 29, 30, 30, 30, 30),
    2088: (30, 31, 32, 32, 30, 31, 30, 30, 29, 30, 30, 30),
    2089: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2090: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2091: (31, 31, 32, 31, 31, 31, 30, 30, 29, 30, 30, 30),
    2092: (30, 31, 32, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2093: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2094: (31, 31, 32, 31, 31, 30, 30, 30, 29, 30, 30, 30),
    2095: (31, 31, 32, 31, 31, 31, 30, 29, 30, 30, 30, 30),
    2096: (30, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2097: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2098: (31, 31, 32, 31, 31, 31, 29, 30, 29, 30, 29, 31),
    2099: (31, 31, 32, 31, 31, 31, 30, 29, 29, 30, 30, 30),
    2100: (31, 32, 31, 32, 30, 31, 30, 29, 30, 29, 30, 30),
}

MIN_BS_YEAR = min(BS_MONTH_DAYS)
MAX_BS_YEAR = max(BS_MONTH_DAYS)

# Anchor: 1 Baisakh 2000 BS fell on 14 April 1943 AD.
_ANCHOR_BS = (2000, 1, 1)
_ANCHOR_AD = datetime.date(1943, 4, 14)

# Running day count at the start of each BS year, indexed alongside _YEARS.
_YEARS = sorted(BS_MONTH_DAYS)
_YEAR_START = []
_total = 0
for _y in _YEARS:
    _YEAR_START.append(_total)
    _total += sum(BS_MONTH_DAYS[_y])

MONTHS_NE = (
    "बैशाख", "जेठ", "असार", "साउन", "भदौ", "असोज",
    "कात्तिक", "मंसिर", "पुष", "माघ", "फागुन", "चैत",
)
MONTHS_EN = (
    "Baisakh", "Jestha", "Ashar", "Shrawan", "Bhadra", "Asoj",
    "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chait",
)
WEEKDAYS_NE = ("आइत", "सोम", "मंगल", "बुध", "बिही", "शुक्र", "शनि")
WEEKDAYS_EN = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

_NE_DIGITS = "०१२३४५६७८९"
_TO_NE = str.maketrans("0123456789", _NE_DIGITS)
_TO_EN = str.maketrans(_NE_DIGITS, "0123456789")


class DateOutOfRange(ValueError):
    """Raised for BS/AD dates the vendored table cannot describe."""


def to_ne_digits(value) -> str:
    return str(value).translate(_TO_NE)


def to_en_digits(value: str) -> str:
    return str(value).translate(_TO_EN)


def days_in_bs_month(year: int, month: int) -> int:
    try:
        return BS_MONTH_DAYS[year][month - 1]
    except KeyError:
        raise DateOutOfRange(f"BS year {year} outside {MIN_BS_YEAR}-{MAX_BS_YEAR}") from None
    except IndexError:
        raise DateOutOfRange(f"BS month {month} out of 1-12") from None


def _day_index(year: int, month: int, day: int) -> int:
    """Days elapsed since 1 Baisakh MIN_BS_YEAR."""
    last = days_in_bs_month(year, month)
    if not 1 <= day <= last:
        raise DateOutOfRange(f"BS {year}-{month:02d} has {last} days, got day {day}")
    index = _YEAR_START[year - MIN_BS_YEAR]
    index += sum(BS_MONTH_DAYS[year][: month - 1])
    return index + day - 1


_ANCHOR_INDEX = _day_index(*_ANCHOR_BS)


def ad_from_bs(year: int, month: int, day: int) -> datetime.date:
    return _ANCHOR_AD + datetime.timedelta(days=_day_index(year, month, day) - _ANCHOR_INDEX)


def bs_from_ad(ad: datetime.date) -> tuple[int, int, int]:
    index = _ANCHOR_INDEX + (ad - _ANCHOR_AD).days
    if index < 0 or index >= _total:
        raise DateOutOfRange(f"{ad.isoformat()} outside BS {MIN_BS_YEAR}-{MAX_BS_YEAR}")
    pos = bisect.bisect_right(_YEAR_START, index) - 1
    year = _YEARS[pos]
    rest = index - _YEAR_START[pos]
    for month, length in enumerate(BS_MONTH_DAYS[year], start=1):
        if rest < length:
            return year, month, rest + 1
        rest -= length
    raise AssertionError("unreachable: year overflow")  # pragma: no cover


def today_bs() -> tuple[int, int, int]:
    return bs_from_ad(datetime.date.today())


def start_column(year: int, month: int) -> int:
    """Grid column of the 1st of a BS month, Sunday = 0."""
    return ad_from_bs(year, month, 1).isoweekday() % 7


def format_bs(bs: tuple[int, int, int], nepali: bool = True) -> str:
    year, month, day = bs
    if nepali:
        return f"{to_ne_digits(day)} {MONTHS_NE[month - 1]} {to_ne_digits(year)}"
    return f"{day} {MONTHS_EN[month - 1]} {year}"


# --- events ---------------------------------------------------------------

CACHE_DIR = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "nepaliPatro"
)
_S4NKALP = "https://raw.githubusercontent.com/S4NKALP/nepali-calendar-api/main/data/{year}/{month}.json"
_SAJANM = "https://raw.githubusercontent.com/sajanm/nepali-lunar-calendar-events/master/{year}.json"
TIMEOUT = 4
_memo: dict[str, object] = {}


def _cached_json(name: str, url: str, offline: bool = False):
    """Cache-first JSON load. Returns None instead of raising, ever."""
    if name in _memo:
        return _memo[name]
    path = os.path.join(CACHE_DIR, name)
    for loader in (_read_cache, None if offline else _download):
        if loader is None:
            continue
        data = loader(path, url)
        if data is not None:
            _memo[name] = data
            return data
    _memo[name] = None
    return None


def _read_cache(path: str, _url: str):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _download(path: str, url: str):
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            payload = response.read()
        data = json.loads(payload.decode("utf-8"))
    except Exception:
        return None
    try:  # cache write is best effort; atomic so a crash cannot leave a stub
        os.makedirs(CACHE_DIR, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=CACHE_DIR)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(tmp, path)
    except OSError:
        pass
    return data


def _split_events(text: str) -> list[str]:
    parts = []
    for chunk in text.replace("|", ",").split(","):
        chunk = chunk.strip(" -\u200b")
        if chunk and chunk != "--":
            parts.append(chunk)
    return parts


def _from_s4nkalp(year: int, month: int, offline: bool):
    raw = _cached_json(
        f"s4nkalp-{year}-{month:02d}.json",
        _S4NKALP.format(year=year, month=month),
        offline,
    )
    if not isinstance(raw, dict):
        return None
    out = {}
    for entry in raw.get("days", []):
        label = to_en_digits(entry.get("n", "")).strip()
        if not label.isdigit():
            continue  # leading blanks that pad the first week
        out[int(label)] = {
            "events": _split_events(entry.get("f", "")),
            "tithi": entry.get("t", "").strip(),
            "holiday": bool(entry.get("h")),
        }
    return out or None


def _parse_ad(text: str) -> datetime.date | None:
    # The dataset changed shape mid-life: BS 2073-2079 use MM/DD/YYYY, 2080+ YYYY/MM/DD.
    for pattern in ("%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(text, pattern).date()
        except (TypeError, ValueError):
            continue
    return None


def _sajanm_events(entry: dict) -> str:
    # ...and renamed "event" to "events" at the same time.
    return entry.get("events") or entry.get("event") or ""


def _from_sajanm(year: int, month: int, offline: bool):
    raw = _cached_json(f"sajanm-{year}.json", _SAJANM.format(year=year), offline)
    if not isinstance(raw, list) or not 1 <= month <= len(raw):
        return None
    out = {}
    for entry in raw[month - 1]:
        try:
            day = int(entry["bs"].split("-")[2])
        except (KeyError, IndexError, ValueError, AttributeError):
            continue
        out[day] = {
            "events": _split_events(_sajanm_events(entry)),
            "tithi": entry.get("tithi", "").strip(),
            "holiday": bool(entry.get("holiday")),
        }
    return out or None


def month_events(year: int, month: int, offline: bool = False) -> dict[int, dict]:
    """{bs day: {events, tithi, holiday}} for a BS month, {} when unavailable."""
    for provider in (_from_s4nkalp, _from_sajanm):
        data = provider(year, month, offline)
        if data:
            return data
    return {}


def sajanm_pairs(year: int, offline: bool = True):
    """Yield (ad date, bs tuple) pairs from the sajanm dataset, for validation."""
    raw = _cached_json(f"sajanm-{year}.json", _SAJANM.format(year=year), offline)
    if not isinstance(raw, list):
        return
    for month in raw:
        for entry in month:
            try:
                bs = tuple(int(part) for part in entry["bs"].split("-"))
            except (KeyError, ValueError, AttributeError):
                continue
            ad = _parse_ad(entry.get("ad", ""))
            if ad is not None and len(bs) == 3:
                yield ad, bs


def upcoming(count: int = 8, offline: bool = False, start: datetime.date | None = None):
    """Next `count` days that carry at least one event, today included."""
    day = start or datetime.date.today()
    found = []
    cache: dict[tuple[int, int], dict] = {}
    for offset in range(400):
        try:
            bs = bs_from_ad(day + datetime.timedelta(days=offset))
        except DateOutOfRange:
            break
        key = (bs[0], bs[1])
        if key not in cache:
            cache[key] = month_events(*key, offline=offline)
            if not cache[key] and len(cache) > 1:
                break  # ran past the end of published data
        entry = cache[key].get(bs[2])
        if entry and entry["events"]:
            found.append({"bs": bs, "in_days": offset, **entry})
            if len(found) >= count:
                break
    return found


# --- cli ------------------------------------------------------------------

def _today_line() -> str:
    ad = datetime.date.today()
    bs = bs_from_ad(ad)
    return f"{format_bs(bs)}  ·  {ad.strftime('%a %d %b %Y')}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Nepali date and event lookup")
    parser.add_argument("--today", action="store_true", help="print today in BS and AD")
    parser.add_argument("--upcoming", type=int, nargs="?", const=8, metavar="N",
                        help="print the next N events (default 8)")
    parser.add_argument("--notify", action="store_true", help="send today's date as a notification")
    parser.add_argument("--offline", action="store_true", help="never touch the network")
    args = parser.parse_args()

    if args.notify:
        body = _today_line()
        events = upcoming(1, offline=args.offline)
        if events and events[0]["in_days"] == 0:
            body += "\n" + ", ".join(events[0]["events"])
        subprocess.run(["notify-send", "आजको मिति", body], check=False)
        return

    if args.upcoming is not None:
        for item in upcoming(args.upcoming, offline=args.offline):
            when = "आज" if item["in_days"] == 0 else f"{item['in_days']}d"
            mark = "*" if item["holiday"] else " "
            print(f"{mark} {format_bs(item['bs']):>22}  {when:>4}  {', '.join(item['events'])}")
        return

    print(_today_line())


if __name__ == "__main__":
    main()
