# nepaliPatro — reference documentation

Complete reference for the Bikram Sambat + Gregorian calendar popup in
`~/sysScripts/nepaliPatro`. For a quick tour, see [README.md](../README.md);
this document is the full description of how every part works and why.

- [1. What it is](#1-what-it-is)
- [2. Requirements](#2-requirements)
- [3. Files](#3-files)
- [4. Running it](#4-running-it)
- [5. The interface](#5-the-interface)
- [6. Date conversion](#6-date-conversion)
- [7. Events](#7-events)
- [8. Files written on disk](#8-files-written-on-disk)
- [9. Styling](#9-styling)
- [10. Window and compositor behaviour](#10-window-and-compositor-behaviour)
- [11. Performance](#11-performance)
- [12. Verification](#12-verification)
- [13. Desktop integration](#13-desktop-integration)
- [14. Limits and expiry dates](#14-limits-and-expiry-dates)
- [15. Troubleshooting](#15-troubleshooting)
- [16. Extending it](#16-extending-it)
- [17. Design decisions](#17-design-decisions)
- [18. Attribution and licences](#18-attribution-and-licences)

---

## 1. What it is

A popup calendar for Wayland compositors that support the `wlr-layer-shell`
protocol. It shows the Bikram Sambat (Nepali) calendar and the Gregorian
calendar, either as the main grid with the other as small secondary numerals in
each cell, plus a pane listing the next Nepali festivals and holidays.

It is meant to hang off a status bar clock: one click opens it, another closes
it. It also works as a plain CLI date tool with no GUI involved.

Scope boundaries, so expectations are right:

- It is a **viewer**. There is no event creation, no reminders, no sync.
- Festival and holiday data comes from **public datasets**, not from a
  computation. Nepali festival dates follow the lunar calendar and public
  holidays are decided by government notice, so no offline formula can produce
  them. Date *conversion*, by contrast, is entirely offline and exact.
- It targets **this machine's setup** (Hyprland + waybar + Catppuccin Mocha),
  but nothing in it is Hyprland-specific beyond the integration snippets.

## 2. Requirements

| Requirement | Why | Notes |
|---|---|---|
| Python 3.8+ | the app itself | only ever run on CPython 3.14.7; older versions are untested, 3.8 is simply the oldest the syntax allows. **No pip packages at all** |
| `gtk4` | the UI toolkit | |
| `python-gobject` | Python bindings for GTK | |
| `gtk4-layer-shell` | anchors the window as a compositor layer | must be loadable as `libgtk4-layer-shell.so` |
| A `wlr-layer-shell` compositor | positions the popup over everything | Hyprland, sway, river, niri… |
| A Devanagari font | Nepali text | `noto-fonts` provides Noto Sans Devanagari |
| `glib2` | `gdbus`, used by the launcher fast path | already a GTK dependency |
| `libnotify` | `--notify` only | provides `notify-send` |

On Arch:

```bash
sudo pacman -S --needed gtk4 python-gobject gtk4-layer-shell noto-fonts libnotify
# gtk4-layer-shell is in extra; nothing here comes from the AUR
```

There is deliberately **no `requirements.txt`**. `data.py` uses only
`datetime`, `bisect`, `json`, `os`, plus `urllib.request`, `tempfile`,
`argparse` and `subprocess` imported lazily at their call sites; `app.py` adds
`calendar`, `threading` and the GTK bindings. This was a reaction to the
previous version breaking when Python 3.14 landed and the `nepali-datetime`
wheel was not yet available for it.

## 3. Files

```
nepaliPatro/
├── patro                  launcher: dispatches to the GUI, the CLI or the checks
├── app.py                 the GTK4 popup (UI only, no date maths)
├── data.py                BS↔AD conversion, event fetching, cache, CLI
├── selfcheck.py           runnable correctness checks, no test framework
├── style.css              all colour and layout styling
├── nepaliPatro.desktop    desktop entry, with a "notify today's date" action
├── README.md              overview
└── docs/
    ├── REFERENCE.md       this file
    ├── screenshot-bs.png
    └── screenshot-ad.png
```

Responsibilities are kept apart on purpose: `data.py` knows nothing about GTK
and can be imported by anything, `app.py` contains no calendar arithmetic
beyond cursor bookkeeping, and `selfcheck.py` imports both.

## 4. Running it

Everything goes through the `patro` launcher.

| Command | Effect |
|---|---|
| `patro` | toggle the popup: opens it, or closes an open one |
| `patro --today` | print today in BS and AD, e.g. `२६ भाद्र २०८३  ·  Fri 11 Sep 2026` |
| `patro --upcoming [N]` | print the next `N` days that carry events (default 8) |
| `patro --notify` | send today's date, and today's events if any, via `notify-send` |
| `patro --offline` | as `--today`, but never touch the network |
| `patro --check` | run `selfcheck.py`; exits non-zero on failure |

`--offline` also composes: `patro --upcoming 5 --offline`.

Sample output:

```
$ patro --upcoming 4
           २६ भाद्र २०८३    आज  कुशे औँसी, बाबुको मुख हेर्ने दिन
*          २७ भाद्र २०८३    1d  गुँलाधर्म समाप्ति
           २८ भाद्र २०८३    2d  दरखाने दिन
           २९ भाद्र २०८३    3d  हरितालिका व्रत, तीज(महिला कर्मचारीहरूको लागि मात्र बिदा)
```

A leading `*` marks a holiday.

**How the toggle works.** The GUI is a `Gtk.Application` with the ID
`np.nepaliPatro`, so the session bus enforces a single instance: a second
launch is delivered to the first as an `activate` signal, and the handler
closes the popup instead of opening a second one. The launcher shortcuts this:
before starting Python at all, it tries to deliver `activate` itself over the
bus with `gdbus`, which is why closing costs ~8 ms instead of a full start.

## 5. The interface

### Anatomy

```
┌─────────────────────────────────────────┐
│  ‹        भाद्र २०८३              ›     │  title: month + year in the active calendar
│         17 Aug – 16 Sep 2026            │  subtitle: the span in the other calendar
│  आज / today              ( ने | EN )    │  today chip · calendar slider
│  आइत सोम मंगल बुध बिही शुक्र शनि        │  weekday header, weekends in red
│   १   २   ३   ४   ५   ६   ७            │  primary numerals
│   1   2   3   4   5   6   7             │  secondary numerals (other calendar)
│  …                                      │
│  २६ भाद्र २०८३ · 11 Sep 2026 · औशी     │  detail line: selected or today, + tithi
│  आउँदा पर्वहरू · upcoming               │
│  २६ भाद्र   आज   कुशे औँसी…             │  8 scrollable rows
│  …                                      │
│  २६ भाद्र २०८३  ·  Fri 11 Sep 2026      │  footer: always today, never the cursor
└─────────────────────────────────────────┘
```

In Nepali mode the grid is the BS month with Gregorian day numbers underneath;
in English mode it is the Gregorian month with BS day numbers underneath. The
weekday header switches script with the mode. Sunday is the first column, and
both Saturday and Sunday are treated as non-working days.

### Colour meaning

Three independent channels, all Catppuccin Mocha:

**Day numbers say what kind of day it is.**

| Colour | Meaning |
|---|---|
| red `#f38ba8` | non-working day: the Saturday and Sunday columns, and any day the dataset marks as a holiday |
| peach `#fab387` | the day has an event, but is still a working day |
| text `#cdd6f4` | ordinary day |

**Fills and rings say where you are.**

| Treatment | Meaning |
|---|---|
| filled pill | today — mauve `#cba6f7` in Nepali mode, blue `#89b4fa` in English mode |
| lavender inset ring | the day you selected, i.e. the one the detail line describes |
| grey fill | hover only |

**Lavender is structural, not semantic**: the border, the `‹ ›` arrows, the
section heading, the date column of the events list. Grey (`subtext`) marks
secondary information: the small secondary numerals, the subtitle, the detail
line, the footer.

In the events list a holiday row turns red and today's row date turns green
`#a6e3a1`. The slider knob is filled in the accent of the calendar you are
looking at, matching that mode's today marker, so the mode is never ambiguous.

### Keyboard

| Key | Action |
|---|---|
| `Escape`, `q` | close |
| `Left`, `h` | previous month |
| `Right`, `l` | next month |
| `n` | next day (moves the selection, following it into the next month) |
| `p` | previous day |
| `t`, `Home` | back to today, clearing the selection |
| `m` | switch calendar, same as the slider |

Month and day movement respect the active calendar: `h`/`l` step BS months in
Nepali mode and Gregorian months in English mode. Movement stops silently at
the edges of the vendored month table rather than raising.

The popup takes `EXCLUSIVE` keyboard focus from the compositor, so these keys
work the moment it opens, without clicking it first.

### Mouse

- Click a day to select it; click it again to deselect. The detail line follows
  the selection, or shows today when nothing is selected.
- Click a row in the upcoming pane to jump the grid to that date and select it.
- `‹` `›` move a month, `आज / today` returns to today, the `ने`/`EN` slider
  switches calendar.
- Hovering a day with events shows them as a tooltip.
- A click anywhere outside the popup dismisses it.

## 6. Date conversion

### Why a table

Bikram Sambat month lengths are 29–32 days and are **not derivable from a
formula**: they are fixed per year by the Panchanga committee and published.
Every correct implementation therefore ships the same table. `data.py` vendors
BS 1975–2100, taken from `amitgaru/nepali-datetime` (Apache-2.0), file
`nepali_datetime/data/calendar_bs.csv`.

```python
BS_MONTH_DAYS = {
    1975: (31, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    ...
    2100: (31, 32, 31, 32, 30, 31, 30, 29, 30, 29, 30, 30),
}
```

That range corresponds to **13 April 1918 – 12 April 2044** Gregorian.

### The algorithm

Both directions go through a single day index — the number of days since
1 Baisakh 1975 BS:

1. `_YEAR_START[i]` holds the running day total at the start of each BS year,
   built once at import from `BS_MONTH_DAYS`.
2. `_day_index(y, m, d)` = that year's start + the lengths of the preceding
   months + `d - 1`.
3. The anchor `1 Baisakh 2000 BS = 14 April 1943 AD` converts an index to a
   Gregorian date: `_ANCHOR_AD + timedelta(days=index - _ANCHOR_INDEX)`.
4. The reverse takes the index, finds the year with `bisect.bisect_right` over
   `_YEAR_START`, then walks at most 12 months to find the day.

Cost is trivial and the whole table unmarshals in 0.1 ms, so nothing here is
worth optimising.

### API

```python
import data

data.ad_from_bs(2083, 5, 26)      # -> datetime.date(2026, 9, 11)
data.bs_from_ad(date(2026, 9, 11))# -> (2083, 5, 26)
data.today_bs()                   # -> (2083, 5, 26)
data.days_in_bs_month(2083, 5)    # -> 31
data.start_column(2083, 5)        # -> grid column of the 1st, Sunday = 0
data.format_bs((2083, 5, 26))     # -> '२६ भाद्र २०८३'
data.format_bs((2083, 5, 26), nepali=False)  # -> '26 Bhadra 2083'
data.to_ne_digits(2083)           # -> '२०८३'
data.to_en_digits('२०८३')         # -> '2083'

data.MIN_BS_YEAR, data.MAX_BS_YEAR   # 1975, 2100
data.MONTHS_NE, data.MONTHS_EN, data.WEEKDAYS_NE, data.WEEKDAYS_EN
```

Anything outside the table raises `data.DateOutOfRange` (a `ValueError`
subclass). It never extrapolates — a wrong date is worse than a refusal.

Month names use the Sanskritised set the source dataset uses
(`बैशाख जेष्ठ असार श्रावण भाद्र असोज कार्तिक मंसिर पुष माघ फाल्गुन चैत्र`)
rather than the colloquial `जेठ / साउन / भदौ` forms, so names match the
datasets the events come from.

## 7. Events

### Sources

| Order | Source | Granularity | Licence |
|---|---|---|---|
| primary | [`S4NKALP/nepali-calendar-api`](https://github.com/S4NKALP/nepali-calendar-api) `data/{bsYear}/{bsMonth}.json` | one file per BS month | MIT |
| fallback | [`sajanm/nepali-lunar-calendar-events`](https://github.com/sajanm/nepali-lunar-calendar-events) `{bsYear}.json` | one file per BS year | none stated |

Two sources, because each covers for a different weakness: S4NKALP is small
per request and permissively licensed, sajanm carries an explicit `ad`/`bs`
pair for every day of BS 2073–2083 and therefore doubles as an oracle that
validates the vendored month table (see [§12](#12-verification)).

Both feeds have quirks the parser absorbs: sajanm changed its date format
mid-life (`MM/DD/YYYY` for BS 2073–2079, `YYYY/MM/DD` from 2080) and renamed
its `event` field to `events`, so `_parse_ad` tries both patterns and
`_sajanm_events` accepts either key.

### Shape

```python
data.month_events(2083, 5)          # {day: {...}} for a BS month, {} if unavailable
# {26: {'events': ['कुशे औँसी', 'बाबुको मुख हेर्ने दिन'],
#       'tithi': 'औशी',
#       'holiday': False}, ...}

data.upcoming(8)                    # next 8 days that carry events, today included
# [{'bs': (2083, 5, 26), 'in_days': 0, 'events': [...], 'tithi': '…', 'holiday': False}, ...]
```

`upcoming()` scans forward up to 400 days, pulling months as needed, and stops
early if it walks past the end of published data. Both functions accept
`offline=True`, which restricts them to the cache.

Event strings arrive as one blob per day separated by commas or pipes;
`_split_events` splits them, drops `--` placeholders and strips stray
zero-width spaces.

### Caching and network policy

- Cache directory: `$XDG_CACHE_HOME/nepaliPatro`, i.e. `~/.cache/nepaliPatro`.
- Filenames: `s4nkalp-{bsYear}-{bsMonth}.json`, `sajanm-{bsYear}.json` — raw
  upstream payloads, unmodified.
- Writes are atomic (`mkstemp` + `os.replace`), so an interrupted download can
  never leave a truncated file that later parses as "no events".
- Network timeout is 4 s, and **every failure is silent**: `_cached_json`
  returns `None` rather than raising, and the UI simply shows no events. A
  calendar that refuses to draw because GitHub is unreachable would be useless.
- Fetched payloads are memoised per process, so a session touches each file
  once.
- The cache never expires. Published festival data for a past month does not
  change, and deleting the directory is the way to force a refresh.

### How the UI uses this

The popup **never blocks on the network**. `Window.month_data()` returns cached
data immediately, or `{}` plus a background `threading.Thread`; when that
thread finishes it calls back through `GLib.idle_add` and the grid re-renders.
So the first ever launch of a new month paints without events and fills them in
a moment later, and every launch after that is instant and offline.

## 8. Files written on disk

| Path | Contents | Written when |
|---|---|---|
| `~/.config/nepaliPatro/state` | `BS` or `AD` — the calendar you last used | on switching mode |
| `~/.cache/nepaliPatro/*.json` | upstream event payloads | on a successful fetch |

Both honour `XDG_CONFIG_HOME` / `XDG_CACHE_HOME`. Both are optional: if the
state file is missing or unreadable the app starts in BS mode, and if the cache
cannot be written the app still works, it just refetches.

Nothing else is touched. No dotfiles are modified, no services installed.

## 9. Styling

All appearance lives in `style.css`, loaded at startup and applied at
`GTK_STYLE_PROVIDER_PRIORITY_APPLICATION`. Colours are declared once as
`@define-color` at the top, so retheming means editing 14 lines.

### Class reference

| Selector | Applies to |
|---|---|
| `window.patro` | the popup window; transparent so the frame's rounded corners show |
| `.frame` | the visible card: background, 2 px lavender border, 14 px radius |
| `.frame.mode-bs` / `.frame.mode-ad` | mode accent switch, drives today's fill colour |
| `.title` / `.subtitle` | month + year, and the span in the other calendar |
| `.nav` | the `‹ ›` buttons |
| `.chip` | the `आज / today` button |
| `.seg` | the slider track |
| `button.segwrap` | invisible button wrapper inside the track |
| `.segknob` + `.bs` / `.ad` + `.on` | the knob; `.on` fills it in that mode's accent |
| `.weekday`, `.weekday.off` | weekday header, weekend header |
| `button.day` | a day cell's click target, frameless |
| `.cell` | the painted box inside it |
| `.cell.off` / `.event` / `.holiday` / `.today` / `.selected` | day state |
| `.cell .num` / `.cell .alt` | primary and secondary numerals |
| `.detail` | the line under the grid |
| `.section` | the `आउँदा पर्वहरू · upcoming` heading |
| `scrolledwindow.events` | the events pane background |
| `.ev-date` / `.ev-when` / `.ev-name` | columns of an event row |
| `.events row.holiday` / `.events row.now` | holiday row, today's row |
| `.footer` | today's date, above a 1 px top border |
| `window.dismisser` | the invisible click catcher |
| `tooltip, tooltip label` | tooltips, which are separate surfaces and need their own font rule |

### Two GTK traps encoded in that file

1. **Day state is painted on an inner `Gtk.Box`, not on the button.** A themed
   GTK button paints its own `background-image`, which covers any
   `background-color` you set — so `today` never filled. Every day cell is
   therefore a frameless `Gtk.Button` (`set_has_frame(False)`) wrapping a plain
   `Gtk.Box` that carries the state classes.
2. **GTK adds a `.background` class to every window, and the theme paints it.**
   That is where the mysterious opaque rectangle came from — the
   Catppuccin-based GTK theme sets `window_bg_color: #24273a`. CSS overrides
   lose to the theme's own window rules, so both windows call
   `self.remove_css_class("background")`. This is what actually makes the
   popup's rounded corners and the catcher layer transparent.

## 10. Window and compositor behaviour

### The two layers

| Namespace | Geometry | Layer | Keyboard | Purpose |
|---|---|---|---|---|
| `nepaliPatro` | 430 × ~683, anchored top, 6 px margin | `TOP` | `EXCLUSIVE` | the calendar |
| `nepaliPatro-dismiss` | fullscreen, fully transparent | `TOP` | `NONE` | catches an outside click |

You can see both with `hyprctl layers | grep nepaliPatro`.

### Why keyboard mode is `EXCLUSIVE`

With `focus_follows_mouse` enabled, the pointer travelling from the bar down to
the popup crosses other windows. An `ON_DEMAND` layer surface hands keyboard
focus to whatever it passes over, and the popup used to vanish mid-journey.
`EXCLUSIVE` holds focus for as long as the popup lives, which also makes the
keys work immediately.

### Why dismissal is explicit

A layer-shell surface has no xdg-toplevel, so:

- `notify::is-active` is **never true** for it — using it as a focus signal was
  the original cause of the vanish-on-approach bug.
- Pointer `leave` events proved unreliable in practice.

So dismissal is only ever: `Escape`/`q`, clicking the launcher again, or
clicking the transparent catcher layer. Moving the pointer away deliberately
does nothing, which is what you want from a calendar you are reading.

The trade-off, stated plainly: the catcher swallows the **first** click you
make elsewhere. Deleting the `Dismisser` class and the two lines that present
it removes that behaviour and leaves `Escape`/`q` and the clock toggle.

### Startup order

`Dismisser` is presented **before** the popup, so the compositor stacks the
popup above it and clicks on the calendar are not intercepted.

## 11. Performance

Cold start is ~350 ms to first frame, and closing an open popup is ~8 ms.
Every number below was measured on this machine (i5-1235U, Iris Xe, Hyprland)
with a frame-clock harness and `python3 -X importtime`, medians over
interleaved runs, not estimated.

### Where the time goes

| Phase | Cost |
|---|---|
| Python interpreter | 11 ms |
| `import gi` — of which ~55 ms is `asyncio` | 71 ms |
| GTK/Gdk typelibs | 61 ms |
| `import data` | 28 ms |
| GTK init, CSS parse, display connect | ~55–80 ms |
| building ~130 widgets | 18 ms |
| first frame | remainder |

### What was changed, and what it bought

- **Lazy imports in `data.py`** — `urllib.request` (40 ms), `argparse` (22 ms),
  `subprocess` (12 ms) and `tempfile` (12 ms) were 85 of its 92 ms and are not
  on the paint path. Moved to their call sites: `import data` fell to 28 ms.
- **`GSK_RENDERER=cairo`** in the launcher. GTK's software renderer is the
  fastest of the three here — 347 ms to first frame against 441 for `gl` and
  521 for `vulkan` — because a 430×683 surface that lives seconds is all
  first-frame latency, and creating a GL context and compiling shaders costs
  more than hardware drawing saves. It also halves memory: 90 MB RSS instead of
  175 MB. Screenshots under all three renderers are indistinguishable.
- **`gdbus` fast path** in the launcher. Closing used to spawn a whole second
  Python + GTK, ~400 ms, purely to deliver a toggle message to the process
  already running. Now the launcher delivers it directly: 8 ms on a hit, and a
  10 ms miss on the open path is the entire cost.

### Measured and then rejected

- Compacting the vendored month table: it unmarshals in **0.1 ms**. Nothing to win.
- Dropping the dismisser layer: ~30 ms under `gl`, nothing under cairo.
- `NON_UNIQUE` to skip bus registration: saves 35 ms (40 ms → 4.5 ms) but
  destroys the toggle, which is the whole interaction model.
- Narrowing the `.frame *` font rule to rely on inheritance: rendered
  identically but ten interleaved A/B runs showed no gain, so it was reverted.
  CSS *as a whole* is worth ~100 ms (removing it entirely: 348 ms → 206 ms),
  but which rules cause that is not yet established.

### The floor, and what would break it

A minimal **C** GTK4 layer-shell app with a comparable widget tree reaches its
first frame in 83 ms; the identical program in Python takes 175 ms. So the
interpreter and bindings cost ~92 ms, and our own UI content costs ~175 ms more
on top. Two consequences:

- Rewriting in C or Rust would land near 250 ms — a full rewrite for ~27%.
- ~55 ms is `asyncio`, which PyGObject imports eagerly in `gi/_ossighelper.py`
  for SIGINT handling and which this app never uses. That is an upstream fix
  (a lazy import), not something to hack around locally.

The only large win left is **not starting a process per click**: keeping one
instance resident and hiding/showing the surface would make every open ~8 ms.
Verified feasible — a layer surface unmaps and remaps cleanly, and `gdbus
Activate` reaches a live instance in 8–26 ms. The costs are 90 MB resident and
having to refresh "today" on every show, since a long-lived process would
otherwise keep marking the day it started on. Not implemented.

## 12. Verification

```bash
patro --check
```

No test framework, no fixtures — one script of asserts that runs in about a
second. It checks:

| Check | What it proves |
|---|---|
| `check_table` | 126 years, 12 months each, lengths 28–32, year totals 340–380 |
| `check_anchor` | `2000-01-01 BS = 1943-04-14 AD`, plus the independently published `2082-01-01 BS = 2025-04-14 AD`, both directions |
| `check_roundtrip` | all **46,022** days in the table survive AD→BS→AD, and BS never goes backwards |
| `check_grid` | leading column and month length agree with the weekday of the last day, for four sample years |
| `check_out_of_range` | years outside the table and impossible days raise `DateOutOfRange` |
| `check_against_dataset` | **3,287** `ad`/`bs` pairs from the sajanm dataset agree with the vendored table exactly, day for day |
| `check_events` | `upcoming()` is chronological, skips empty days, and `month_events` never returns a day outside its month |
| `check_day_step` | `n`/`p` cross month boundaries both ways and stop at the table edge — driven through the real `Window.step_day` with a stub, so no display is needed |

Two dataset years are **quarantined** in `check_against_dataset`, with reasons
in the source:

- **BS 2073** — the file contains 370 day entries; a BS year is 365 or 366.
- **BS 2081** — its `ad` fields put Jestha at 31 days and Ashar at 32, while
  both S4NKALP and the nepali-calendar GNOME extension say 32/31, matching the
  vendored table. The dataset is the outlier; its `bs` keys are still correct,
  so events for that year land on the right day.

The dataset cross-check is skipped with a message if nothing is cached yet.

## 13. Desktop integration

> **Current state warning.** These edits live in the `feat/nepali-patro-clock`
> branch of `~/dotfiles`, which is **not merged**. With that repo on `main`, all
> three entry points point at `~/sysScripts/fetchNepaliDate.sh`, which was
> deleted — so the waybar click, the login notification and the `nepdate` alias
> are all dead until the branch is merged and redeployed.

### waybar

In `~/.config/waybar/modules.json`, on the clock module:

```json
"clock": {
    "format": "{:%H:%M}",
    "tooltip": false,
    "on-click": "~/sysScripts/nepaliPatro/patro",
    "on-click-right": "~/sysScripts/nepaliPatro/patro --notify"
}
```

`"tooltip": false` matters: waybar's own hover tooltip would otherwise appear
over the popup.

### Hyprland

```lua
-- ~/.config/hypr/conf/autostart.lua
hl.exec_cmd("~/sysScripts/nepaliPatro/patro --notify")
```

A keybind, if you want one — this config keeps them in
`~/.config/hypr/conf/keybindings/appKeybinds.lua`:

```lua
hl.bind("SUPER + C", hl.dsp.exec_cmd("~/sysScripts/nepaliPatro/patro"))
```

### Shell

```bash
alias nepdate='~/sysScripts/nepaliPatro/patro --today'
alias patro='~/sysScripts/nepaliPatro/patro'
```

### Desktop entry

`nepaliPatro.desktop` provides an app-launcher entry plus a "Notify today's
date" action. Install it by symlink so edits track the repo:

```bash
ln -sf ~/sysScripts/nepaliPatro/nepaliPatro.desktop \
       ~/.local/share/applications/nepaliPatro.desktop
```

Note that `Exec`/`TryExec` are absolute paths — desktop files do not expand
`~`. Moving the repo means editing them.

## 14. Limits and expiry dates

Three independent horizons, worth knowing before relying on this:

1. **Date conversion stops after 12 April 2044** (end of BS 2100). Past that
   every call raises `DateOutOfRange`; it fails loudly rather than guessing.
   Fix: append rows to `BS_MONTH_DAYS` when the committee publishes them, then
   run `patro --check`.
2. **Events stop after BS 2083** — around 14 April 2027. Both upstreams end
   there today: `data/2084/01.json` and `2084.json` both 404. They publish
   yearly, so 2084 will likely appear, but that is their decision. Degradation
   is clean and tested: `upcoming()` returns `[]`, `month_events()` returns
   `{}`, nothing raises, weekends stay red because that is computed locally,
   and cached years keep working offline forever.
3. **Public holidays are decided by government notice each year**, so no
   offline table can be authoritative about future festivals — the events part
   is inherently online, unlike conversion.

Smaller known warts:

- With no data at all the events pane shows `पर्वहरू खोज्दै…` ("searching for
  festivals"), which is honest during a fetch but misleading once a year
  genuinely does not exist upstream.
- Weekend red and holiday red are the same red, so a Saturday and Dashain look
  alike at a glance. Deliberate — both are days off — but they are not
  distinguishable.
- The catcher layer swallows the first click you make outside the popup.
- Every open costs ~350 ms because it is a fresh process. See
  [§11](#11-performance).

## 15. Troubleshooting

**Nothing appears when I click the clock.**
Check for a stale instance: `pgrep -af "[a]pp.py"`. Because the app is
single-instance, a leftover process makes your click a *close* rather than an
open; the next click will open it. `pkill -f "[a]pp.py"` clears it. Also
confirm the file exists — if `~/sysScripts` is on a branch without
`nepaliPatro/`, the launcher path is simply gone.

**"compositor does not support the layer-shell protocol"**
The compositor lacks `wlr-layer-shell`. GNOME does not implement it.

**Devanagari renders as boxes or with broken conjuncts.**
Install a Devanagari font (`noto-fonts`) and check `fc-list | grep -i devanagari`.
Tooltips are separate surfaces and do not inherit the frame's font rule, which
is why `style.css` has an explicit `tooltip, tooltip label` rule.

**An opaque rectangle sits behind the popup, or the screen dims.**
Something re-added GTK's `.background` class, or a rule in `style.css` lost to
the theme's own window rules. Both windows must call
`remove_css_class("background")`; see [§9](#9-styling).

**Vulkan warnings on launch.**
Gone once `vulkan-intel` is installed — before that, the only Vulkan driver
present was NVIDIA's (shipped by `nvidia-utils`, which Hyprland pulls in) on an
Intel-only machine, so the probe could only fail. Harmless either way, and the
launcher pins cairo regardless.

**Events are missing or stale.**
`rm -rf ~/.cache/nepaliPatro` and reopen; the app refetches. If a BS year is
past the upstream horizon there is nothing to fetch — see
[§14](#14-limits-and-expiry-dates).

**The popup closes the instant I click something else.**
That is the catcher layer working as designed. See
[§10](#10-window-and-compositor-behaviour) for how to remove it.

## 16. Extending it

**Add BS years.** Append rows to `BS_MONTH_DAYS` in `data.py` — nothing else is
hardcoded, `MIN_BS_YEAR`/`MAX_BS_YEAR` and the running totals derive from it.
Then `patro --check`, which will re-round-trip every day in the table.

**Add an event source.** Write a `_from_yoursource(year, month, offline)`
returning `{day: {"events": [...], "tithi": str, "holiday": bool}}` or `None`,
and add it to the provider tuple in `month_events()`. Use `_cached_json` so it
inherits caching, atomic writes, the 4 s timeout and silent failure.

**Retheme.** Edit the `@define-color` block at the top of `style.css`. For a
light theme, `base`, `mantle`, `surface`, `text` and `subtext` are the ones that
matter; `crust` is used as the text colour on top of filled accents.

**Add a key.** One `elif` in `Window.on_key`, and update both the module
docstring and this file's key table.

**Change what counts as a weekend.** `WEEKEND = (0, 6)` in `app.py`, columns
with Sunday = 0.

**Change the events pane size.** `UPCOMING = 8` in `app.py`; the scroller's
`min_content_height`/`max_content_height` bound the pane itself.

## 17. Design decisions

Recorded because the alternatives all look reasonable until you try them.

**GTK4 + PyGObject + gtk4-layer-shell.** Chosen for one hard requirement:
correct Devanagari shaping (Pango/HarfBuzz) inside a compositor-anchored
surface. Rejected: Tk (X11-only here, no HarfBuzz, broken conjuncts), any TUI
including ratatui and opentui (the terminal owns shaping; Indic rendering in
Ghostty is an open issue), PyQt6 (no layer-shell binding), eww/AGS/QuickShell
(new frameworks to learn for a single popup), a web stack (a browser engine for
a calendar).

**A vendored month table, stdlib only.** Rejected `pip install nepali-datetime`
— that is exactly what broke when Python 3.14 arrived — and rejected deriving
month lengths from the events JSON, which only covers 2073–2083.

**Two event sources.** sajanm alone was rejected: no stated licence and 87 KB
per year. S4NKALP is primary and permissive; sajanm stays as fallback *and* as
the oracle that validates the vendored table.

**Explicit dismissal.** `notify::is-active` and pointer-leave were both tried
and both failed for layer surfaces; see
[§10](#10-window-and-compositor-behaviour).

**A segmented `ने`/`EN` slider.** A single toggle button naming the destination
was rejected as misleading — it was unclear whether the label meant the current
state or the target.

**Sanskritised month names.** Matches the dataset's own `metadata.np` field, so
names agree with the events that come from it.

## 18. Attribution and licences

| Component | Source | Licence |
|---|---|---|
| BS month-length table | [`amitgaru/nepali-datetime`](https://github.com/amitgaru/nepali-datetime) → `nepali_datetime/data/calendar_bs.csv` | Apache-2.0 |
| Primary event data | [`S4NKALP/nepali-calendar-api`](https://github.com/S4NKALP/nepali-calendar-api) | MIT |
| Fallback event data | [`sajanm/nepali-lunar-calendar-events`](https://github.com/sajanm/nepali-lunar-calendar-events) | none stated — used as fallback and validation only |
| Colour palette | [Catppuccin](https://github.com/catppuccin/catppuccin) Mocha | MIT |

Event data is fetched at runtime and cached locally; none of it is
redistributed in this repository. The vendored month table is published
calendar data, credited in the `data.py` module docstring.
