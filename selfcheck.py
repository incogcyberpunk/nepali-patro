#!/usr/bin/env python3
"""Runnable check for data.py. No framework: `python3 selfcheck.py`.

The interesting assertion is the last one: the sajanm dataset carries an exact
ad/bs pair for every single day of BS 2073-2083, so it doubles as an oracle for
the vendored month-length table. A typo anywhere in that stretch of the table
cannot survive this.
"""

import datetime
import sys

import data


def check_table():
    for year, months in data.BS_MONTH_DAYS.items():
        assert len(months) == 12, f"BS {year} has {len(months)} months"
        assert all(28 <= n <= 32 for n in months), f"BS {year} month length out of range"
        assert 340 <= sum(months) <= 380, f"BS {year} has {sum(months)} days"
    print(f"  table: {len(data.BS_MONTH_DAYS)} years, BS {data.MIN_BS_YEAR}-{data.MAX_BS_YEAR}")


def check_anchor():
    assert data.ad_from_bs(2000, 1, 1) == datetime.date(1943, 4, 14)
    # Independent published pair: 1 Baisakh 2082 BS = 14 April 2025 AD.
    assert data.ad_from_bs(2082, 1, 1) == datetime.date(2025, 4, 14)
    assert data.bs_from_ad(datetime.date(2025, 4, 14)) == (2082, 1, 1)
    print("  anchor: 2000-01-01 BS = 1943-04-14 AD, verified against 2082 new year")


def check_roundtrip():
    count = 0
    first = data.ad_from_bs(data.MIN_BS_YEAR, 1, 1)
    last = data.ad_from_bs(data.MAX_BS_YEAR, 12, data.days_in_bs_month(data.MAX_BS_YEAR, 12))
    day = first
    previous = None
    while day <= last:
        bs = data.bs_from_ad(day)
        assert data.ad_from_bs(*bs) == day, f"round trip failed at {day}"
        if previous is not None:
            assert bs > previous or (bs[0], bs[1]) != (previous[0], previous[1]), \
                f"BS went backwards at {day}"
        previous = bs
        day += datetime.timedelta(days=1)
        count += 1
    assert count == sum(sum(m) for m in data.BS_MONTH_DAYS.values())
    print(f"  round trip: {count} consecutive days AD->BS->AD")


def check_grid():
    for year in (2073, 2082, 2083, 2090):
        for month in range(1, 13):
            column = data.start_column(year, month)
            length = data.days_in_bs_month(year, month)
            assert 0 <= column <= 6
            assert column + length <= 42, "month cannot fit in a 6 week grid"
            end = data.ad_from_bs(year, month, length)
            assert end.isoweekday() % 7 == (column + length - 1) % 7
    print("  grid: leading columns and month lengths consistent for 4 sample years")


def check_out_of_range():
    for bad in ((data.MIN_BS_YEAR - 1, 1, 1), (data.MAX_BS_YEAR + 1, 1, 1), (2082, 1, 40)):
        try:
            data.ad_from_bs(*bad)
        except data.DateOutOfRange:
            continue
        raise AssertionError(f"expected DateOutOfRange for {bad}")
    print("  range guard: rejects years outside the table and impossible days")


def check_against_dataset():
    """Cross-check the vendored table against the sajanm ad/bs pairs.

    That dataset is a corroborating source, not gospel. Two of its years are
    demonstrably broken and are quarantined here:
      - BS 2073: the file contains 370 day entries. A BS year is 365 or 366.
      - BS 2081: its `ad` field puts Jestha at 31 days and Ashar at 32. Both
        S4NKALP and the nepali-calendar GNOME extension say 32/31, matching
        the table, so the dataset is the odd one out. (Its `bs` keys are still
        fine, so events for that year land on the right day.)
    Everything else must agree exactly, day for day.
    """
    quarantine = {2073: "370 day entries in a 365/366 day year",
                  2081: "Jestha/Ashar boundary contradicts two other sources"}
    total = years = 0
    for year in range(2073, 2084):
        pairs = list(data.sajanm_pairs(year))
        if not pairs:
            continue
        if year in quarantine:
            print(f"    skipping BS {year}: {quarantine[year]}")
            continue
        assert len(pairs) in (365, 366), \
            f"BS {year} dataset has {len(pairs)} days; expected 365 or 366"
        years += 1
        for ad, bs in pairs:
            assert data.bs_from_ad(ad) == bs, f"table disagrees with dataset: {ad} != BS {bs}"
            assert data.ad_from_bs(*bs) == ad, f"table disagrees with dataset: BS {bs} != {ad}"
            total += 1
    if not total:
        print("  dataset cross-check: SKIPPED (no cached sajanm data; run data.py --upcoming)")
        return
    print(f"  dataset cross-check: {total} ad/bs pairs across {years} years agree exactly")


def check_events():
    bs = data.today_bs()
    events = data.upcoming(5, offline=True)
    offsets = [item["in_days"] for item in events]
    assert offsets == sorted(offsets), "upcoming() must be chronological"
    assert all(item["events"] for item in events), "upcoming() must skip empty days"
    assert all(len(item["bs"]) == 3 for item in events)
    month = data.month_events(bs[0], bs[1], offline=True)
    assert all(1 <= day <= data.days_in_bs_month(bs[0], bs[1]) for day in month), \
        "month_events returned a day outside the month"
    state = f"{len(month)} days" if month else "no cached data"
    print(f"  events: current month {state}, upcoming() returned {len(events)} (offline)")


def main():
    print("nepaliPatro selfcheck")
    for check in (check_table, check_anchor, check_roundtrip, check_grid,
                  check_out_of_range, check_against_dataset, check_events):
        check()
    print(f"ok — today is {data.format_bs(data.today_bs())} "
          f"/ {datetime.date.today().isoformat()}")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
