"""Turn the shared events file into this week's post text and schedule graphic."""
from __future__ import annotations

import base64
import html
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
X_LIMIT = 270  # margin: X counts emoji as 2
BLUESKY_LIMIT = 300


@dataclass
class Event:
    when: datetime
    store: dict
    title: str
    entry_fee: str = ""
    prizes: str = ""
    signup_url: str = ""
    format_notes: str = ""
    special: bool = False

    @property
    def store_label(self) -> str:
        city = self.store.get("city", "")
        return f"{self.store.get('name', '?')} ({city})" if city else self.store.get("name", "?")


@dataclass
class Week:
    start: date
    end: date
    events: list[Event] = field(default_factory=list)
    site_name: str = "DFW Pauper"
    site_url: str = ""


def _fmt_time(t: time) -> str:
    h = t.hour % 12 or 12
    suffix = "AM" if t.hour < 12 else "PM"
    return f"{h} {suffix}" if t.minute == 0 else f"{h}:{t.minute:02d} {suffix}"


def _fmt_range(start: date, end: date) -> str:
    if start.month == end.month:
        return f"{start:%b} {start.day}–{end.day}"
    return f"{start:%b} {start.day}–{end:%b} {end.day}"


def load_week(events_path: Path, site_path: Path | None, today: date | None = None,
              include_samples: bool = False) -> Week:
    data = json.loads(events_path.read_text())
    tz = ZoneInfo(data.get("timezone", "America/Chicago"))
    today = today or datetime.now(tz).date()
    start = today - timedelta(days=today.weekday())  # Monday
    end = start + timedelta(days=6)
    stores = {s["id"]: s for s in data.get("stores", [])}

    week = Week(start=start, end=end)
    if site_path and site_path.exists():
        site = json.loads(site_path.read_text())
        week.site_name = site.get("name") or week.site_name
        week.site_url = site.get("url", "")

    def keep(e: dict) -> bool:
        return include_samples or not e.get("sample")

    for e in data.get("weekly", []):
        if not keep(e) or not e.get("active", True) or e.get("day") not in DAYS:
            continue
        d = start + timedelta(days=DAYS.index(e["day"]))
        if d.isoformat() in e.get("skip_dates", []):  # cancelled or moved this week
            continue
        t = time.fromisoformat(e.get("start_time", "19:00"))
        week.events.append(Event(
            when=datetime.combine(d, t, tz), store=stores.get(e.get("store"), {}),
            title="Weekly Pauper", entry_fee=e.get("entry_fee", ""), prizes=e.get("prizes", ""),
            signup_url=e.get("signup_url", ""), format_notes=e.get("format_notes", "")))

    for e in data.get("special", []):
        if not keep(e):
            continue
        d = date.fromisoformat(e["date"])
        if not (start <= d <= end):
            continue
        t = time.fromisoformat(e.get("start_time", "12:00"))
        week.events.append(Event(
            when=datetime.combine(d, t, tz), store=stores.get(e.get("store"), {}),
            title=e.get("title", "Pauper event"), entry_fee=e.get("entry_fee", ""),
            prizes=e.get("prizes", ""), signup_url=e.get("signup_url", ""),
            format_notes=e.get("format_notes", ""), special=True))

    week.events.sort(key=lambda ev: ev.when)
    return week


def _line(ev: Event, with_fee: bool = True) -> str:
    star = "⭐ " if ev.special else ""
    name = f"{ev.title} @ {ev.store_label}" if ev.special else ev.store_label
    fee = f" · {ev.entry_fee}" if with_fee and ev.entry_fee else ""
    return f"{star}{ev.when:%a} {_fmt_time(ev.when.time())} · {name}{fee}"


def _fit(header: str, lines: list[str], footer: str, limit: int) -> str:
    """Join lines under a character limit, replacing overflow with '+N more'."""
    for n in range(len(lines), -1, -1):
        body = lines[:n]
        if n < len(lines):
            body = body + [f"+{len(lines) - n} more"]
        text = "\n".join([header, "", *body, "", footer]).strip()
        if len(text) <= limit:
            return text
    return header[:limit]


def build_texts(week: Week) -> dict[str, str]:
    """Return post text per platform."""
    header = f"🗓️ Pauper in DFW this week ({_fmt_range(week.start, week.end)})"
    lines = [_line(e) for e in week.events]
    short = [_line(e, with_fee=False) for e in week.events]
    tags = "#MTGPauper #Pauper #DFW"
    link = f"Details: {week.site_url}" if week.site_url else ""

    long_footer = "\n".join(x for x in [link, "Commons only. All skill levels welcome!", tags] if x)
    discord_lines = []
    for e in week.events:
        extra = " · ".join(x for x in [e.prizes, e.format_notes] if x)
        signup = f" · <{e.signup_url}>" if e.signup_url else ""
        discord_lines.append(f"**{_line(e)}**" + (f"\n  {extra}" if extra else "") + signup)

    return {
        "discord": "\n".join([f"## {header}", "", *discord_lines, "", link]).strip(),
        "facebook": "\n".join([header, "", *lines, "", long_footer]).strip(),
        "instagram": "\n".join([header, "", *lines, "", "Link in bio for details.",
                                tags + " #MagicTheGathering #Dallas #FortWorth"]).strip(),
        # X charges ~13x more for posts with a link, so the X post has none.
        "x": _fit(header, short, tags, X_LIMIT),
        "bluesky": _fit(header, short, link or tags, BLUESKY_LIMIT),
    }


def _logo_data_uri(logo_path: Path | None) -> str:
    if logo_path and logo_path.exists():
        return "data:image/png;base64," + base64.b64encode(logo_path.read_bytes()).decode()
    return ""


# Brand palette (matches the website): Ink Black, White, Tangerine, Deep Ocean, Emerald.
INK, WHITE, TANGERINE, OCEAN, EMERALD = "#171A21", "#FCFCFC", "#FF934F", "#0B7A75", "#69B578"
FONTS = ("https://fonts.googleapis.com/css2?family=Montserrat:wght@800;900"
         "&family=Inter:wght@400;500;600&display=swap")


def render_html(week: Week, logo_path: Path | None = None) -> str:
    rows = []
    limit = 12
    for e in week.events[:limit]:
        cls = "row special" if e.special else "row"
        tag = '<i>Special event</i>' if e.special else ""
        title = html.escape(e.title if e.special else e.store.get("name", ""))
        sub = html.escape(e.store_label if e.special else e.store.get("city", ""))
        fee = html.escape(e.entry_fee)
        rows.append(
            f'<div class="{cls}"><div class="day">{e.when:%a}<span>{e.when:%b} {e.when.day}</span></div>'
            f'<div class="what">{tag}<b>{title}</b><small>{sub}</small></div>'
            f'<div class="time">{_fmt_time(e.when.time())}<small>{fee}</small></div></div>')
    if len(week.events) > limit:
        rows.append(f'<div class="more">+{len(week.events) - limit} more on the website</div>')
    if not rows:
        rows.append('<div class="row"><div class="what"><b>No events listed this week</b></div></div>')
    logo = _logo_data_uri(logo_path)
    logo_html = f'<img class="logo" src="{logo}" alt="">' if logo else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{FONTS}"><style>
*{{box-sizing:border-box;margin:0}}
body{{width:1080px;height:1080px;background:{INK};color:{WHITE};font-family:Inter,'DejaVu Sans',Arial,sans-serif;
padding:68px 72px;display:flex;flex-direction:column}}
.display{{font-family:Montserrat,'DejaVu Sans',sans-serif;text-transform:uppercase}}
header{{display:flex;align-items:center;justify-content:space-between;gap:32px}}
h1{{font-size:84px;font-weight:900;line-height:.95}}
h2{{font-size:30px;font-weight:800;color:{TANGERINE};margin-top:16px;letter-spacing:1px}}
.logo{{width:190px;height:190px;border-radius:50%;background:{WHITE};flex:none}}
.bar{{height:8px;margin:36px 0 32px;background:linear-gradient(90deg,{TANGERINE} 0 40%,{OCEAN} 40% 75%,{EMERALD} 75%)}}
.list{{display:flex;flex-direction:column;gap:16px;flex:1}}
.row{{display:flex;align-items:center;gap:28px;background:#222631;border-left:10px solid {OCEAN};border-radius:6px;padding:18px 28px}}
.row.special{{background:#2a2420;border-left-color:{TANGERINE}}}
.day{{width:120px;font-family:Montserrat,sans-serif;text-transform:uppercase;font-size:40px;font-weight:900;
color:{TANGERINE};display:flex;flex-direction:column;line-height:1}}
.day span{{font-family:Inter,sans-serif;font-size:20px;font-weight:500;color:#b9bdc7;text-transform:none;margin-top:4px}}
.what{{flex:1;display:flex;flex-direction:column;font-size:32px;font-weight:600}}
.what i{{font-style:normal;font-size:18px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:{EMERALD}}}
small{{font-size:22px;font-weight:400;color:#b9bdc7}}
.time{{text-align:right;font-family:Montserrat,sans-serif;font-size:36px;font-weight:900;display:flex;flex-direction:column}}
.time small{{font-family:Inter,sans-serif}}
.more{{font-size:24px;color:#b9bdc7;padding-left:8px}}
.compact{{gap:8px}} .compact .row{{padding:7px 24px;gap:20px}}
.compact .day{{flex-direction:row;align-items:baseline;gap:10px;width:170px;font-size:28px}} .compact .day span{{font-size:17px}}
.compact .what{{flex-direction:row;align-items:baseline;gap:12px;font-size:24px}} .compact .what i{{font-size:14px}}
.compact small{{font-size:18px}} .compact .time{{flex-direction:row;align-items:baseline;gap:12px;font-size:26px}}
footer{{font-size:24px;color:#b9bdc7;display:flex;justify-content:space-between;padding-top:24px}}
footer b{{color:{EMERALD};font-weight:600}}
</style></head><body>
<header><div><h1 class="display">Pauper<br>this week</h1>
<h2 class="display">{_fmt_range(week.start, week.end)} · Dallas-Fort Worth</h2></div>{logo_html}</header>
<div class="bar"></div>
<div class="list{' compact' if len(rows) > 7 else ''}">{''.join(rows)}</div>
<footer><span><b>Commons only.</b> All skill levels welcome.</span><span>{html.escape(week.site_url)}</span></footer>
</body></html>"""


def render_image(week: Week, out_png: Path, chromium_path: str | None = None,
                 logo_path: Path | None = None) -> Path:
    from playwright.sync_api import sync_playwright

    out_png.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path) if chromium_path else p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1080})
        try:
            page.set_content(render_html(week, logo_path), wait_until="networkidle", timeout=20000)
        except Exception:  # fonts unreachable: render with fallback fonts
            page.set_content(render_html(week, logo_path), wait_until="load")
        page.screenshot(path=str(out_png))
        browser.close()
    return out_png
