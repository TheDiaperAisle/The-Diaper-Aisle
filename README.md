# The Diaper Aisle

Public price tracker for adult disposable diapers, pull-ups and boosters sold in Canada.

- `index.html` is the whole site (GitHub Pages serves it from the `main` branch root).
- `data/` holds the daily data: `meta.json`, `catalog-N.json`, `history-N.json`, `thumbs-N.json`. It is rewritten every day by the scheduled refresh; don't edit it by hand.
- `tools/publish.py <source_dir>` turns the scraper's output folder into `data/`.

Found a wrong price or pack size? Email thediaperaisle@gmail.com.
