# The Diaper Aisle

Public price tracker for adult disposable diapers, pull-ups and boosters sold in Canada.

- `index.html` + `app/` are the site (GitHub Pages serves them from the `main` branch root), built from `redesign/` (React + Tailwind). Don't edit them by hand: change `redesign/src` and run `npm run build` there.
- `shipping.json` holds each store's shipping rules (used by the page and the email report).
- `data/` holds the daily data: `meta.json`, `catalog-N.json`, `history-N.json`, `thumbs-N.json`. It is rewritten every day by the scheduled refresh; don't edit it by hand.
- `tools/publish.py <source_dir>` turns the scraper's output folder into `data/`.

Found a wrong price or pack size? Email thediaperaisle@gmail.com.
