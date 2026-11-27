"""Weekly DFW Pauper event poster.

  python -m poster.main                      # preview: write files, send preview to mod Discord channel
  python -m poster.main --mode publish       # post to every configured platform
  python -m poster.main --mode publish --platforms discord,bluesky
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from . import publishers
from .build import build_texts, load_week, render_image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=os.environ.get("EVENTS_FILE", "data/events.json"))
    ap.add_argument("--site", default=os.environ.get("SITE_FILE", "data/site.json"))
    ap.add_argument("--logo", default=os.environ.get("LOGO_FILE", "assets/logo.png"))
    ap.add_argument("--mode", choices=["preview", "publish"], default="preview")
    ap.add_argument("--platforms", default=",".join(publishers.ORDER))
    ap.add_argument("--date", help="Any day in the week to post about (YYYY-MM-DD). Default: today.")
    ap.add_argument("--out", default="output")
    ap.add_argument("--include-samples", action="store_true", help="Preview only: show sample events")
    ap.add_argument("--allow-empty", action="store_true", help="Publish even if no events this week")
    args = ap.parse_args()

    if args.mode == "publish" and args.include_samples:
        sys.exit("Refusing to publish sample events.")

    week = load_week(Path(args.events), Path(args.site),
                     date.fromisoformat(args.date) if args.date else None, args.include_samples)
    texts = build_texts(week)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    image = render_image(week, out / "schedule.png", os.environ.get("CHROMIUM_PATH"), Path(args.logo))
    for name, text in texts.items():
        (out / f"{name}.txt").write_text(text + "\n")
    print(f"Week {week.start}..{week.end}: {len(week.events)} event(s). Files in {out}/")

    if args.mode == "preview":
        for name, text in texts.items():
            print(f"\n----- {name} ({len(text)} chars) -----\n{text}")
        preview_hook = os.environ.get("DISCORD_PREVIEW_WEBHOOK_URL")
        if preview_hook:
            body = "**Preview of this week's posts.** Nothing has been posted publicly.\n" \
                   "To publish: GitHub > Actions > Weekly event posts > Run workflow > mode: publish.\n\n" \
                   f"**X / Bluesky version:**\n```\n{texts['x']}\n```"
            publishers.discord(body, image, webhook_url=preview_hook)
            print("Sent preview to the mod Discord channel.")
        return 0

    if not week.events and not args.allow_empty:
        print("No events this week; nothing posted.")
        return 0

    failed = []
    wanted = [p.strip() for p in args.platforms.split(",") if p.strip()]
    for name in publishers.ORDER:
        if name not in wanted:
            continue
        if not publishers.configured(name):
            print(f"[skip] {name}: not set up (missing {', '.join(publishers.REQUIRED[name])})")
            continue
        try:
            result = publishers.PUBLISHERS[name](texts[name], image)
            print(f"[ok]   {name}: {result}")
        except Exception as e:  # keep going so one broken platform doesn't block the rest
            print(f"[FAIL] {name}: {e}")
            failed.append(name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
