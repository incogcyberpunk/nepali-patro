<div align="center">

# नेपाली पात्रो · nepaliPatro

**A Bikram Sambat + Gregorian calendar popup for Wayland, with the next Nepali festivals built in.**

Click your bar clock, get both calendars and what's coming. Click again, it's gone.

![GTK4](https://img.shields.io/badge/GTK-4-4A86CF?logo=gtk&logoColor=white)
![Wayland](https://img.shields.io/badge/Wayland-layer--shell-FFB300?logo=wayland&logoColor=black)
![Python](https://img.shields.io/badge/Python-stdlib%20only-3776AB?logo=python&logoColor=white)
![pip deps](https://img.shields.io/badge/pip%20dependencies-0-success)
![Cold start](https://img.shields.io/badge/cold%20start-~350%20ms-brightgreen)
![Toggle](https://img.shields.io/badge/toggle-8%20ms-brightgreen)
![Checks](https://img.shields.io/badge/self--check-46%2C022%20days%20round--tripped-blueviolet)

<img src="docs/screenshot-bs.png" width="45%" alt="Nepali calendar mode: Bhadra 2083 grid with Gregorian day numbers underneath and an upcoming festivals pane"> <img src="docs/screenshot-ad.png" width="45%" alt="English calendar mode: September 2026 grid with Bikram Sambat day numbers underneath">

*Nepali mode (mauve accent) and English mode (blue accent) — one slider apart.*

</div>

---

## Why this exists

Nepal runs on Bikram Sambat, your laptop runs on Gregorian, and every festival
date lives in the gap between them. This puts both grids in one popup, tells you
what `भोलि` holds, and never asks you to open a browser to find out when Dashain
starts.

## What it does

🗓️ **Both calendars, either way round.** Nepali mode gives you the BS month with
Gregorian numbers underneath; English mode flips it. The weekday header switches
script too.

🎉 **Upcoming festivals, right there.** Eight scrollable rows of what's next,
with `आज` / `भोलि` / `+N` day counts. Click a row and the grid jumps to it.

🎨 **Colour that means something.** Red is a day off — weekend or holiday. Peach
means something's happening but you're still working. The filled pill is today,
mauve or blue depending on which calendar you're reading.

🌙 **Tithi and event names** in the detail line and in every day's tooltip.

⌨️ **Keyboard driven.** `h`/`l` for months, `n`/`p` for days, `t` for today, `m`
to flip calendars, `q` to go away.

📴 **Works offline.** Events cache to disk on first fetch; date conversion is
100% local and needs no network, ever. Nothing blocks on the wire — the grid
paints instantly and events fill in behind it.

🪶 **Zero pip packages.** Standard library plus system GTK. Nothing to break the
next time Python bumps a minor version — which is exactly why the old version
died.

## Install

```bash
sudo pacman -S --needed gtk4 python-gobject gtk4-layer-shell noto-fonts libnotify

git clone https://github.com/incogcyberpunk/System-Scripts.git ~/sysScripts
~/sysScripts/nepaliPatro/patro --check   # prove it works
~/sysScripts/nepaliPatro/patro           # open it
```

Needs a compositor that speaks `wlr-layer-shell` — Hyprland, sway, river, niri.
Not GNOME.

### Wire it to your bar

```json
"clock": {
    "format": "{:%H:%M}",
    "tooltip": false,
    "on-click": "~/sysScripts/nepaliPatro/patro",
    "on-click-right": "~/sysScripts/nepaliPatro/patro --notify"
}
```

Then a desktop entry, if you want it in your launcher:

```bash
ln -sf ~/sysScripts/nepaliPatro/nepaliPatro.desktop ~/.local/share/applications/
```

## Use it

| Key | | Key | |
|---|---|---|---|
| `q` `Esc` | close | `n` | next day |
| `h` `←` | previous month | `p` | previous day |
| `l` `→` | next month | `t` `Home` | back to today |
| `m` | switch calendar | | |

Click a day to pin the detail line to it. Click an event row to jump there.
Click anywhere outside to dismiss.

## Also a CLI

```console
$ patro --today
२६ भाद्र २०८३  ·  Fri 11 Sep 2026

$ patro --upcoming 4
           २६ भाद्र २०८३    आज  कुशे औँसी, बाबुको मुख हेर्ने दिन
*          २७ भाद्र २०८३    1d  गुँलाधर्म समाप्ति
           २८ भाद्र २०८३    2d  दरखाने दिन
           २९ भाद्र २०८३    3d  हरितालिका व्रत, तीज(महिला कर्मचारीहरूको लागि मात्र बिदा)

$ patro --notify     # today's date as a desktop notification
```

`*` marks a holiday. Add `--offline` to any of them to stay off the network.

## Fast, and measured

| | |
|---|---|
| open (cold process) | **~350 ms** to first frame |
| close, or toggle an open popup | **8 ms** — the launcher delivers it over D-Bus instead of starting Python |
| resident memory while open | 90 MB |

Three things got it there, each one measured rather than guessed: lazy imports
in `data.py` (`import data` went 92 ms → 28 ms), GTK's **cairo** renderer, which
beats both `gl` (441 ms) and `vulkan` (521 ms) because a small short-lived popup
is all first-frame latency, and a `gdbus` fast path so closing doesn't spawn a
second interpreter to say one word.

The full profile — including why a C rewrite would only buy ~90 ms, and where
the remaining 55 ms of `asyncio` comes from — is in
[docs/REFERENCE.md §11](docs/REFERENCE.md#11-performance).

## Verified, not vibed

```console
$ patro --check
nepaliPatro selfcheck
  table: 126 years, BS 1975-2100
  anchor: 2000-01-01 BS = 1943-04-14 AD, verified against 2082 new year
  round trip: 46022 consecutive days AD->BS->AD
  grid: leading columns and month lengths consistent for 4 sample years
  range guard: rejects years outside the table and impossible days
    skipping BS 2073: 370 day entries in a 365/366 day year
    skipping BS 2081: Jestha/Ashar boundary contradicts two other sources
  dataset cross-check: 3287 ad/bs pairs across 9 years agree exactly
  events: current month 31 days, upcoming() returned 5 (offline)
  day step: n/p cross month boundaries both ways and stop at the table edge
ok — today is २६ भाद्र २०८३ / 2026-09-11
```

Every day in the vendored table round-trips, and 3,287 independently published
`ad`/`bs` pairs agree with it exactly. Two dataset years are quarantined with
reasons — one of them contradicts itself, one contradicts two other sources.

## Honest limits

- **Date conversion works until 12 April 2044** (end of BS 2100), then raises
  rather than guessing. Month lengths aren't computable — they're published per
  year, so the table has an end.
- **Festival data currently ends at BS 2083** (~April 2027). Both upstreams stop
  there; they publish yearly. When it runs out, the calendar keeps working and
  the events pane just goes quiet.
- Weekend red and holiday red are the same red.
- The invisible click-catcher swallows the first click you make elsewhere.

## Under the hood

`patro` dispatches · `app.py` draws · `data.py` converts and fetches ·
`selfcheck.py` proves it · `style.css` themes it.

Two layer surfaces (the calendar, plus a transparent fullscreen click catcher),
one D-Bus name for the toggle, events cached in `~/.cache/nepaliPatro`, chosen
calendar remembered in `~/.config/nepaliPatro/state`.

📖 **[Full reference documentation →](docs/REFERENCE.md)** — architecture, the
conversion algorithm, event schema, every CSS class, GTK traps, performance
data, troubleshooting, and the design decisions with their rejected
alternatives.

## Credits

Month-length table from [`amitgaru/nepali-datetime`](https://github.com/amitgaru/nepali-datetime)
(Apache-2.0). Festival data from
[`S4NKALP/nepali-calendar-api`](https://github.com/S4NKALP/nepali-calendar-api)
(MIT) with [`sajanm/nepali-lunar-calendar-events`](https://github.com/sajanm/nepali-lunar-calendar-events)
as fallback and validation oracle. Colours are
[Catppuccin](https://github.com/catppuccin/catppuccin) Mocha. Event data is
fetched and cached at runtime, never redistributed here.
