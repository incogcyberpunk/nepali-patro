#!/usr/bin/env python3
"""nepaliPatro - Bikram Sambat + Gregorian calendar popup for Wayland.

A gtk4-layer-shell surface anchored under waybar. Launch it again while it is
open and it closes, so a single waybar click can toggle it.

Dismiss: Escape, a click anywhere outside it, or clicking the launcher again.
Moving the pointer away deliberately does not close it.
Keys: Escape close · Left/Right or h/l month · t today · m switch calendar
"""

from ctypes import CDLL

# gtk4-layer-shell must be loaded before libwayland-client, and GI pulls in
# libwayland as soon as Gdk is imported. See gtk4-layer-shell/linking.md.
CDLL("libgtk4-layer-shell.so")

import calendar  # noqa: E402
import datetime  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402
from gi.repository import Gtk4LayerShell as LayerShell  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data  # noqa: E402

APP_ID = "np.nepaliPatro"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "nepaliPatro", "state",
)
MARGIN_TOP = 6           # clears waybar
UPCOMING = 8             # rows in the events pane
WEEKEND = (0, 6)         # Sunday and Saturday are both holidays in Nepal


def load_mode() -> str:
    try:
        with open(STATE_FILE, encoding="utf-8") as handle:
            mode = handle.read().strip()
        return mode if mode in ("BS", "AD") else "BS"
    except OSError:
        return "BS"


def save_mode(mode: str) -> None:
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as handle:
            handle.write(mode)
    except OSError:
        pass


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="nepaliPatro")
        self.add_css_class("patro")
        self.set_default_size(430, -1)

        LayerShell.init_for_window(self)
        LayerShell.set_namespace(self, "nepaliPatro")
        LayerShell.set_layer(self, LayerShell.Layer.TOP)
        LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
        LayerShell.set_margin(self, LayerShell.Edge.TOP, MARGIN_TOP)
        # EXCLUSIVE, not ON_DEMAND: with focus_follows_mouse the pointer crosses
        # other windows on its way down from the bar, and an ON_DEMAND surface
        # loses keyboard focus to whatever it passes over, which used to dismiss
        # the popup mid-travel. Holding focus also makes Escape and the arrow
        # keys work without clicking the popup first.
        LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.EXCLUSIVE)

        self.today_ad = datetime.date.today()
        self.today_bs = data.bs_from_ad(self.today_ad)
        self.mode = load_mode()
        self.cursor_bs = [self.today_bs[0], self.today_bs[1]]
        self.cursor_ad = [self.today_ad.year, self.today_ad.month]
        self.selected = None
        self._months = {}       # (bs year, bs month) -> events dict
        self._pending = set()   # keys currently being fetched

        # Dismiss guards. A layer-shell surface has no xdg-toplevel, so GTK's
        # is-active is never true for it and is useless as a focus signal, and
        # pointer crossing events proved unreliable. Dismissal is therefore
        # explicit: Escape, clicking the clock again, or clicking outside the
        # popup, which the transparent Dismisser layer below us catches.
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)

        self.build_ui()
        self.render()

    # --- layout ---------------------------------------------------------

    def build_ui(self):
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        frame.add_css_class("frame")
        self.frame = frame
        self.set_child(frame)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        prev_btn = Gtk.Button(label="\u2039")
        prev_btn.set_has_frame(False)
        prev_btn.add_css_class("nav")
        prev_btn.connect("clicked", lambda _b: self.shift(-1))
        header.append(prev_btn)

        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        self.title = Gtk.Label(halign=Gtk.Align.CENTER)
        self.title.add_css_class("title")
        self.subtitle = Gtk.Label(halign=Gtk.Align.CENTER)
        self.subtitle.add_css_class("subtitle")
        titles.append(self.title)
        titles.append(self.subtitle)
        header.append(titles)

        next_btn = Gtk.Button(label="\u203a")
        next_btn.set_has_frame(False)
        next_btn.add_css_class("nav")
        next_btn.connect("clicked", lambda _b: self.shift(1))
        header.append(next_btn)
        frame.append(header)

        tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        today_btn = Gtk.Button(label="आज / today")
        today_btn.set_has_frame(False)
        today_btn.add_css_class("chip")
        today_btn.connect("clicked", lambda _b: self.go_today())
        tools.append(today_btn)
        tools.append(Gtk.Box(hexpand=True))

        # Segmented slider on the right: the filled knob sits on the calendar
        # you are looking at, so the current mode is never ambiguous. The paint
        # goes on an inner box because a themed button overrides background.
        segment = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        segment.add_css_class("seg")
        segment.set_valign(Gtk.Align.CENTER)
        self.mode_chips = {}
        for mode, label in (("BS", "ने"), ("AD", "EN")):
            knob = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            knob.add_css_class("segknob")
            knob.add_css_class(mode.lower())
            text = Gtk.Label(label=label)
            text.add_css_class("seglabel")
            knob.append(text)

            button = Gtk.Button(child=knob)
            button.set_has_frame(False)
            button.add_css_class("segwrap")
            button.connect("clicked", self.on_mode_chip, mode)
            segment.append(button)
            self.mode_chips[mode] = knob
        tools.append(segment)
        frame.append(tools)

        self.grid = Gtk.Grid(column_homogeneous=True, row_spacing=1,
                             column_spacing=1, margin_top=6)
        frame.append(self.grid)

        self.detail = Gtk.Label(halign=Gtk.Align.START, wrap=True, xalign=0)
        self.detail.add_css_class("detail")
        frame.append(self.detail)

        section = Gtk.Label(label="आउँदा पर्वहरू · upcoming", halign=Gtk.Align.START)
        section.add_css_class("section")
        frame.append(section)

        self.events_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.events_list.connect("row-activated", self.on_event_row)
        scroller = Gtk.ScrolledWindow(min_content_height=150, max_content_height=240,
                                      propagate_natural_height=True, vexpand=False)
        scroller.add_css_class("events")
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self.events_list)
        frame.append(scroller)

        self.footer = Gtk.Label(halign=Gtk.Align.CENTER)
        self.footer.add_css_class("footer")
        frame.append(self.footer)

    # --- data -----------------------------------------------------------

    def month_data(self, year, month):
        """Events for a BS month; paints from cache now, fetches in background."""
        key = (year, month)
        if key in self._months:
            return self._months[key]
        cached = data.month_events(year, month, offline=True)
        if cached:
            self._months[key] = cached
            return cached
        self.fetch_later(key)
        return {}

    def fetch_later(self, key):
        if key in self._pending:
            return
        self._pending.add(key)

        def worker():
            fetched = data.month_events(key[0], key[1])
            GLib.idle_add(self.fetch_done, key, fetched)

        threading.Thread(target=worker, daemon=True).start()

    def fetch_done(self, key, fetched):
        self._pending.discard(key)
        self._months[key] = fetched
        self.render()
        return GLib.SOURCE_REMOVE

    # --- rendering ------------------------------------------------------

    def render(self):
        # One accent colour per calendar: the slider knob and today's marker
        # share it, so the popup says which calendar it is showing.
        self.frame.remove_css_class("mode-bs" if self.mode == "AD" else "mode-ad")
        self.frame.add_css_class("mode-bs" if self.mode == "BS" else "mode-ad")
        for mode, knob in self.mode_chips.items():
            parent = knob.get_parent()
            if mode == self.mode:
                knob.add_css_class("on")
                parent.set_tooltip_text("नेपाली पात्रो — showing this calendar"
                                        if mode == "BS" else
                                        "English calendar — showing this calendar")
            else:
                knob.remove_css_class("on")
                parent.set_tooltip_text("switch to नेपाली पात्रो (m)" if mode == "BS"
                                        else "switch to English calendar (m)")
        while (child := self.grid.get_first_child()) is not None:
            self.grid.remove(child)

        weekdays = data.WEEKDAYS_NE if self.mode == "BS" else data.WEEKDAYS_EN
        for column, name in enumerate(weekdays):
            label = Gtk.Label(label=name)
            label.add_css_class("weekday")
            if column in WEEKEND:
                label.add_css_class("off")
            self.grid.attach(label, column, 0, 1, 1)

        if self.mode == "BS":
            self.render_bs()
        else:
            self.render_ad()

        self.render_detail()
        self.render_upcoming()
        self.footer.set_label(
            f"{data.format_bs(self.today_bs)}   ·   {self.today_ad.strftime('%a %d %b %Y')}"
        )

    def render_bs(self):
        year, month = self.cursor_bs
        self.title.set_label(f"{data.MONTHS_NE[month - 1]} {data.to_ne_digits(year)}")
        first = data.ad_from_bs(year, month, 1)
        last = data.ad_from_bs(year, month, data.days_in_bs_month(year, month))
        self.subtitle.set_label(
            f"{data.MONTHS_EN[month - 1]} {year} · "
            f"{first.strftime('%d %b')} – {last.strftime('%d %b %Y')}"
        )

        events = self.month_data(year, month)
        column = data.start_column(year, month)
        row = 1
        for day in range(1, data.days_in_bs_month(year, month) + 1):
            ad = data.ad_from_bs(year, month, day)
            entry = events.get(day, {})
            self.grid.attach(
                self.make_cell(
                    main=data.to_ne_digits(day),
                    alt=str(ad.day),
                    bs=(year, month, day),
                    column=column,
                    entry=entry,
                    is_today=(year, month, day) == self.today_bs,
                ),
                column, row, 1, 1,
            )
            column += 1
            if column == 7:
                column, row = 0, row + 1

    def render_ad(self):
        year, month = self.cursor_ad
        self.title.set_label(f"{calendar.month_name[month]} {year}")
        bs_first = data.bs_from_ad(datetime.date(year, month, 1))
        bs_last = data.bs_from_ad(
            datetime.date(year, month, calendar.monthrange(year, month)[1])
        )
        if bs_first[1] == bs_last[1]:
            span = f"{data.MONTHS_NE[bs_first[1] - 1]} {data.to_ne_digits(bs_first[0])}"
        else:
            span = (f"{data.MONTHS_NE[bs_first[1] - 1]} – "
                    f"{data.MONTHS_NE[bs_last[1] - 1]} {data.to_ne_digits(bs_last[0])}")
        self.subtitle.set_label(span)

        weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)
        for row, week in enumerate(weeks, start=1):
            for column, day in enumerate(week):
                if day == 0:
                    continue
                bs = data.bs_from_ad(datetime.date(year, month, day))
                entry = self.month_data(bs[0], bs[1]).get(bs[2], {})
                self.grid.attach(
                    self.make_cell(
                        main=str(day),
                        alt=data.to_ne_digits(bs[2]),
                        bs=bs,
                        column=column,
                        entry=entry,
                        is_today=datetime.date(year, month, day) == self.today_ad,
                    ),
                    column, row, 1, 1,
                )

    def make_cell(self, main, alt, bs, column, entry, is_today):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add_css_class("cell")
        num = Gtk.Label(label=main)
        num.add_css_class("num")
        small = Gtk.Label(label=alt)
        small.add_css_class("alt")
        box.append(num)
        box.append(small)

        if column in WEEKEND:
            box.add_css_class("off")
        if entry.get("holiday"):
            box.add_css_class("holiday")
        if entry.get("events"):
            box.add_css_class("event")
        if is_today:
            box.add_css_class("today")
        if self.selected == bs:
            box.add_css_class("selected")

        button = Gtk.Button(child=box)
        button.set_has_frame(False)
        button.add_css_class("day")
        button.set_tooltip_text(", ".join(entry.get("events", [])) or None)
        button.connect("clicked", self.on_day, bs)
        return button

    def render_detail(self):
        bs = self.selected or self.today_bs
        entry = self.month_data(bs[0], bs[1]).get(bs[2], {})
        bits = [data.format_bs(bs), data.ad_from_bs(*bs).strftime("%d %b %Y")]
        if entry.get("tithi"):
            bits.append(entry["tithi"])
        line = "  ·  ".join(bits)
        if entry.get("events"):
            line += "\n" + ", ".join(entry["events"])
        elif not entry:
            line += "\n…"
        self.detail.set_label(line)

    def render_upcoming(self):
        self.events_list.remove_all()

        items = data.upcoming(UPCOMING, offline=True)
        if not items:
            self.fetch_later((self.today_bs[0], self.today_bs[1]))
            placeholder = Gtk.Label(label="पर्वहरू खोज्दै…", halign=Gtk.Align.CENTER)
            placeholder.add_css_class("ev-name")
            row = Gtk.ListBoxRow(activatable=False, child=placeholder)
            self.events_list.append(row)
            return

        for item in items:
            row = Gtk.ListBoxRow(activatable=True)
            row.bs = item["bs"]
            if item["holiday"]:
                row.add_css_class("holiday")
            if item["in_days"] == 0:
                row.add_css_class("now")

            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            date_label = Gtk.Label(
                label=f"{data.to_ne_digits(item['bs'][2])} "
                      f"{data.MONTHS_NE[item['bs'][1] - 1]}",
                width_chars=9, xalign=0,
            )
            date_label.add_css_class("ev-date")
            when = ("आज" if item["in_days"] == 0
                    else "भोलि" if item["in_days"] == 1
                    else f"+{item['in_days']}")
            when_label = Gtk.Label(label=when, width_chars=4, xalign=0)
            when_label.add_css_class("ev-when")
            name = Gtk.Label(label=", ".join(item["events"]), xalign=0, hexpand=True,
                             wrap=True, max_width_chars=30)
            name.add_css_class("ev-name")
            line.append(date_label)
            line.append(when_label)
            line.append(name)
            row.set_child(line)
            self.events_list.append(row)

    # --- interaction ----------------------------------------------------

    def shift(self, delta):
        if self.mode == "BS":
            year, month = self.cursor_bs
            month += delta
            if month > 12:
                year, month = year + 1, 1
            elif month < 1:
                year, month = year - 1, 12
            if not data.MIN_BS_YEAR <= year <= data.MAX_BS_YEAR:
                return
            self.cursor_bs = [year, month]
        else:
            year, month = self.cursor_ad
            month += delta
            if month > 12:
                year, month = year + 1, 1
            elif month < 1:
                year, month = year - 1, 12
            try:  # keep the AD cursor inside the BS table's reach
                data.bs_from_ad(datetime.date(year, month, 1))
            except data.DateOutOfRange:
                return
            self.cursor_ad = [year, month]
        self.render()

    def go_today(self):
        self.cursor_bs = [self.today_bs[0], self.today_bs[1]]
        self.cursor_ad = [self.today_ad.year, self.today_ad.month]
        self.selected = None
        self.render()

    def toggle_mode(self):
        self.set_mode("AD" if self.mode == "BS" else "BS")

    def on_mode_chip(self, _button, mode):
        self.set_mode(mode)

    def set_mode(self, mode):
        if mode == self.mode:
            return
        self.mode = mode
        save_mode(self.mode)
        self.render()

    def on_day(self, _button, bs):
        self.selected = None if self.selected == bs else bs
        self.render()

    def on_event_row(self, _list, row):
        bs = getattr(row, "bs", None)
        if not bs:
            return
        self.selected = bs
        self.cursor_bs = [bs[0], bs[1]]
        ad = data.ad_from_bs(*bs)
        self.cursor_ad = [ad.year, ad.month]
        self.render()

    def on_key(self, _controller, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.close()
        elif keyval in (Gdk.KEY_Left, Gdk.KEY_h):
            self.shift(-1)
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_l):
            self.shift(1)
        elif keyval in (Gdk.KEY_t, Gdk.KEY_Home):
            self.go_today()
        elif keyval == Gdk.KEY_m:
            self.toggle_mode()
        else:
            return False
        return True


class Dismisser(Gtk.ApplicationWindow):
    """Invisible fullscreen layer under the popup: a click on it dismisses.

    This is how dropdowns behave everywhere, and unlike focus or hover it is a
    signal the compositor delivers reliably.
    """

    def __init__(self, app):
        super().__init__(application=app)
        self.add_css_class("dismisser")
        self.on_dismiss = lambda: None

        LayerShell.init_for_window(self)
        LayerShell.set_namespace(self, "nepaliPatro-dismiss")
        LayerShell.set_layer(self, LayerShell.Layer.TOP)
        for edge in (LayerShell.Edge.TOP, LayerShell.Edge.BOTTOM,
                     LayerShell.Edge.LEFT, LayerShell.Edge.RIGHT):
            LayerShell.set_anchor(self, edge, True)
        LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.NONE)

        click = Gtk.GestureClick()
        click.set_button(0)  # any button
        click.connect("pressed", lambda *_a: self.on_dismiss())
        self.add_controller(click)


class Patro(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.popup = None
        self.catcher = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        css = os.path.join(HERE, "style.css")
        if os.path.exists(css):
            provider = Gtk.CssProvider()
            provider.load_from_path(css)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def do_activate(self):
        if getattr(self, "popup", None) is not None:  # launched again: toggle off
            self.dismiss()
            return
        # Map the catcher first so the popup ends up above it.
        self.catcher = Dismisser(self)
        self.catcher.on_dismiss = self.dismiss
        self.catcher.present()
        self.popup = Window(self)
        self.popup.connect("close-request", self.on_popup_closed)
        self.popup.present()

    def dismiss(self):
        if self.popup is not None:
            self.popup.close()

    def on_popup_closed(self, *_args):
        self.popup = None
        if self.catcher is not None:
            self.catcher.close()
            self.catcher = None
        return False


def main() -> int:
    if not LayerShell.is_supported():
        print("compositor does not support the layer-shell protocol", file=sys.stderr)
        return 1
    return Patro().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
