# DFW Pauper website

A one-page static site. All the content you'll update lives in five small files in `data/`, so nobody has to touch the HTML for routine changes.

| File | What it holds | How often to update |
|---|---|---|
| `data/events.json` | Stores, weekly events, special events. Also read by the social auto-poster. | Whenever a store adds or changes a night |
| `data/meta.json` | Top 10 worldwide Pauper decks and their share | Monthly (copy from MTGGoldfish) |
| `data/banned.json` | Pauper banned list | After each Banned & Restricted announcement (next: Nov 30, 2026) |
| `data/site.json` | Site name, live URL, the community Discord new players are sent to (name, invite), social links, contact email | When branding, links or stats change |
| `data/faq.json` | FAQ questions and answers | Whenever a common question comes up |

Each file has a `_how_to_edit` note at the top. Times are 24-hour Central time (`19:00` = 7 PM). Entries marked `"sample": true` are placeholders: they show a "Sample listing" badge on the site and are skipped by the auto-poster. Delete them once real events exist.

## Editing on GitHub (no tools needed)
1. Open the file on github.com and click the pencil icon.
2. Make the change. Keep the quotes and commas in place.
3. Click **Commit changes**. The live site updates in about a minute.

If a page shows "Couldn't load…", the JSON has a typo (usually a missing comma). Paste the file into https://jsonlint.com to find it.

## Hosting on GitHub Pages (free)
1. Create a public repo (for example `dfw-pauper`) and upload everything in this folder.
2. Repo **Settings → Pages → Build and deployment**: Source "Deploy from a branch", branch `main`, folder `/ (root)`.
3. The site appears at `https://<your-username>.github.io/dfw-pauper/`.
4. Custom domain later: buy one (about $10–15/yr), enter it under Settings → Pages → Custom domain, and add the DNS records GitHub shows.

## Previewing locally
The page loads its data with `fetch`, so opening `index.html` straight from disk won't work. Run `python3 -m http.server` in this folder and open http://localhost:8000.
