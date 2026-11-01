# The Diaper Aisle: daily price tracker

This repo is the whole tracker: the public page (`index.html`, served by GitHub Pages at
https://thediaperaisle.github.io/The-Diaper-Aisle/), its data (`data/`) and the scripts that refresh the data (`pipeline/`).
`data/` is the source of truth: each daily run reads yesterday's data from it and commits today's data back to it.

Owner: Nick (nicholas.dumoulin2@gmail.com). The tracker covers adult disposable diaper prices in Canada (CAD).

## Layout
- `index.html`: the tracker page. It reads `data/`. Change it only when the owner asks, never during the daily run.
- `tools/publish.py`: copies a scraper output folder into `data/` and updates `data/meta.json` doc counts.
- `pipeline/scraper.py`: the stores (Healthwick, ABUniverse, MyDips, AgeComfort via Shopify `/products.json`; Rearz via BigCommerce pages + price API). Writes `out/`.
- `pipeline/amazon.py`: adds Amazon.ca listings through the Firecrawl API. Needs `FIRECRAWL_API_KEY` in the environment (never commit the key, never print it). Imports `scraper.py` from its own folder.
- `pipeline/stock_check.py`: fixes AgeComfort and Healthwick backorders that the feeds report as in stock. Edits `out/` in place.
- `pipeline/changes.py`: compares `prev/` with `out/` and prints the day's changes, problems, `banner` and `report` as JSON.
- `pipeline/email_html.py`: builds the designed HTML email (owner and public editions) from `changes.json`.
- `assets/tda-logo-email.png`: the email logo (inline attachment, `cid:att0`).
- `docs/`: SHIPPING.md (shipping rules behind the page's `SHIP` constant) and the old Cowork runbook (history and owner decisions; background only).

Scratch folders `out/`, `prev/`, `email/` and files `scrape.log`, `changes.json`, `logo.b64` are git-ignored. Never commit them.

## Data layout (`data/`)
- `catalog-0..N.json`: `{rows:[...], date}`. One row per product x colour/scent variant x size x package. `pid` groups the same product across stores, and `ck` = pid + size is the cross-store compare key. `cat` is `diaper`, `pullup` or `booster`. `bo: true` = backorder (feed says buyable, product page says out of stock).
- `history-0..N.json`: `{h:{rowId:[[date, price, inStock], ...]}}`. A point is added only when price or stock changes.
- `thumbs-0..N.json`: `{t:{"Store|handle":{src, d:dataURI}}}`, 88px WebP.
- `meta.json`: last run, per-store status, doc counts, Amazon credit use (`amazon`).

Row ids include the quantity (`Store|handle|size|pkg|qty|variant`). When a scraper fix changes a row's qty or pkg, carry that row's history over to the new id so the price trend is not lost.

## Daily run
Run everything from the repo root. Needs Python 3 with Pillow: `python3 -m pip install pillow` (add `--break-system-packages` if pip refuses), then check `python3 -c "from PIL import Image"` works. Plain `pip` can belong to a different Python. Without Pillow no thumbnails are made.

1. `git pull --ff-only origin main`
2. `rm -rf prev out email && mkdir prev && cp data/*.json prev/`
3. `python3 pipeline/scraper.py ./out ./prev 2> scrape.log` (about 4-5 minutes)
4. `python3 pipeline/amazon.py ./out ./prev 2>> scrape.log`
   Budget: at most 700 Firecrawl credits a month (free plan = 1,000), about 22 searches a day, oldest-checked first. Credit use lives in `meta.json` → `amazon`. HTTP 429 on some searches is normal (rate limit); a total failure keeps yesterday's Amazon rows and shows as a problem.
5. `python3 pipeline/stock_check.py ./out`
   If `pages_failed` is more than half of `pages`, add the problem "AgeComfort stock check could not read product pages: <first error>".
6. Publish: `python3 tools/publish.py ./out .`, then
   `git add -A data && git -c user.name="The Diaper Aisle" -c user.email="thediaperaisle@gmail.com" commit -m "Data for <YYYY-MM-DD>" && git push origin main`.
   Commit only `data/`. If the push fails, it's a problem: "Public site not updated: <reason>. Today's price points are lost from the history unless this is fixed before tomorrow's run."
7. Report: `python3 pipeline/changes.py ./prev ./out ./scrape.log > changes.json`. If step 6 failed or any step could not run, add it to `issues` in changes.json and to the PROBLEMS section of `report` (and to `banner`'s "N problems to check" count).
8. Notify the owner, but only when something changed or there is a problem. On a quiet day (no changes and no problems) send no push and no email.
   Otherwise send a push notification if a push tool is available, with `banner` as the first sentence and then `report`, then send the emails (next section).
9. Final reply: the report, plus one line on which emails went out.

## Owner rules for the report (2026-10-30)
- When asking the owner to check or clarify a product, include a link to its product page at each store involved (owner 2026-10-31).
- Mention only what changed and what is broken. No "everything worked" lines, no row counts, no "data published" line.
- Quiet day banner: "Dip Aisle: no price or stock changes today."
- PROBLEMS cover: store failures, per-store row/product counts down more than 10%, jumps in rows with no pack quantity, price moves over 50% (likely parse errors), scraper crashes, failed Rearz price lookups or thumbnail downloads, products that lost a capacity they had yesterday because their page could not be read, a failed stock check, and a failed publish.
- Missing capacities are NOT a problem by themselves (most TENA, Prevail and Attends products never state one). Failed capacity-page reads are expected (MyDips and AgeComfort geo-redirect cloud servers) and matter only when they cost a product its capacity.

## Emails
Build: `python3 pipeline/email_html.py --build changes.json <YYYY-MM-DD> ./email` and `base64 -w0 assets/tda-logo-email.png > logo.b64`.
`email/plan.json` says, per edition, whether to send and gives the subject.

- `owner` edition: full report including PROBLEMS. To nicholas.dumoulin2@gmail.com only. Goes out when anything changed or there is any problem.
- `public` edition: same report without problems. To the other recipients, all in To, one email. Goes out only when a price, stock or listing changed.
  Other recipients: drewlehman5@gmail.com
- Quiet day (no changes and no problems): no email to anyone and no push notification (owner decision, 2026-10-31).

Send each edition with the Gmail connector's send tool, one message per edition:
- `subject` from plan.json; `htmlBody` = `email/<edition>.html` exactly as written; `body` = `email/<edition>.txt` exactly as written.
- `attachments`: exactly one, `{"content": <logo.b64>, "filename": "tda-logo.png", "mimeType": "image/png", "inline": true}`. The HTML shows it as `cid:att0`.
- The email is only the report and the tracker link. Never mention tools, connectors, sessions or how the run works.
- Never send the owner edition to anyone else, and never put problems in the public edition.
- Fallbacks: if the HTML build fails or Gmail rejects the HTML, send that edition as plain text (`email/<edition>.txt`). If Gmail is not available or sending fails, say so in the owner's push or final reply only, never in an email.
- Gmail connector quirks (tested): the `background:` CSS shorthand and external image URLs are stripped; `background-color` and `cid:att0` work. Don't hand-edit the HTML.

## Stores and parsing notes
- Missing data (owner 2026-11-01): when the feed or title lacks a fact (count, size, capacity, dimensions), the product page is the default next source, after other stores' figures for the same product. Add page reads for new gaps the same way.
- Booster dimensions: `dims_of` reads '4.25" x 13.5"', '4.25 x 15 inches', 'Dimensions: L 16.5", W 6"' and cm figures (shown in inches); `dims_by_size` reads per-size lists ('S: Fits size 4.25" x 13.5" ... M: ...'). Missing from the feed → product page (only labelled 'Dimensions:'/'Size:' figures there). The page shows L (longer side) and W (shorter side) columns on the Booster tab.
- AgeComfort: product pages live on `www.agecomfort.com`; the feed marks backorders as available, so stock comes from `stock_check.py`.
- Rearz (`ca.rearz.ca`) is BigCommerce: sitemap → product pages → `/remote/v1/product-attributes/{id}` per size x pack for exact CAD price and stock. Don't take prices from the page HTML.
- ABUniverse case rows (4 packs / 40, 25% off) come from the page's `diaper_add_case.js` widget. A bigger case at the same $/diaper is skipped.
- Package: "Bag (10)" is one bag; only plural "Bags (n)" / "3 Bags (36)" / "Case" are cases.
- Abena (owner 2026-10-31): names use size + level codes (`Slip Premium M4`, `Flexi-Fit M-L3`) via `abena_names`; the level is part of the pid so levels are never compared; AgeComfort "Abri Form Original X Plus", "Abri-Form Premium" and Healthwick "White Foil Comfort" are Abri-Form Comfort (level 4). Read the product descriptions when checking Abena: some stores give levels only as codes, and capacities differ by size (M4 3600 mL, L4 4000 mL).
- Capacities per size: `caps_by_size` reads "M: ... 3600mL" lists and size tables from descriptions; a figure stated for a size beats a whole-product figure. NorthShore's per-size figures are a different measure from its ISO figure and are ignored.
- Amazon piece counts: `amazon_qty` reads the title ("Case/96", "96/case", "Pack/12", "Bag of 20", "3 Packs of 12", "(64 Total - 2 Pack)", "15-Count"). When the title has no count or is unclear ("24 Count (Pack of 4)", a lone "Pack of 2"), the product page's "Number of Items" decides (owner 2026-11-01, B007WUVGQS = 96). The same page read gives the size of listings whose title has none (they show "One size" until then) and the capacity from the listing's own bullets, description and details. Capacity order: title, another store's figure for the same product, `CAP_BY_SIZE`, then the product page (owner 2026-11-01); a page is read for capacity only when none of the others has it. Each page is read once and cached per ASIN in `meta.json` → `amazon.qty`. While pages are waiting (`stores.Amazon.pages_waiting`), up to 40 a day are read and searches drop to 8 a day; with no backlog, all credits go to searches.
- Amazon adult-baby listings (Little for Big, Landofgenie, ...) are named by the print after the piece count: "... Cloth Back Diaper 2 Pieces - Little Beauty (Medium)" → "Little Beauty". 2-3 pieces = Sample (owner 2026-11-01).
- Image-only capacities are in `CAP_MANUAL` (scraper) and `CAP_BY_SIZE` (amazon), owner-confirmed.
- Hand-checked product merges are in `KEY_ALIAS`. Open question: Rearz "Tena Slip Maxi (European)" vs TENA "Slip Maxi" is not merged until checked.
- Network: the run needs healthwick.ca, ca.abuniverse.com, mydips.ca, agecomfort.com, www.agecomfort.com, ca.rearz.ca, cdn11.bigcommerce.com, cdn.shopify.com, api.firecrawl.dev, m.media-amazon.com and github.com.
