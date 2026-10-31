# Dip Aisle: publish to the public site (GitHub Pages)

Added 2026-10-31 (owner). The public site is the GitHub repo **TheDiaperAisle/The-Diaper-Aisle** (branch `main`, served by GitHub Pages). `index.html` there is the tracker page; it reads static files from `data/`. The artifact database stays the source of truth: the scraper still reads `./prev` from it and writes `./out`. This step only copies `./out` to the repo.

## When
Run after RUNBOOK step 4 (database writes) and before step 6 (report), every day the scraper produced `./out`.

## Steps
1. Load the `add_repo` tool via ToolSearch (query "add_repo") and call it with owner `TheDiaperAisle`, repo `The-Diaper-Aisle`, access `push`. Clone exactly as its result says, into `./site` (`git clone --depth 1 https://github.com/TheDiaperAisle/The-Diaper-Aisle ./site`, long timeout).
2. `python3 site/tools/publish.py ./out ./site` — rewrites `site/data/` from the scraper output and prints `{"catalog", "history", "thumbs", "rows", "date"}`.
3. Commit and push only the data:
   ```
   cd site
   git add -A data
   git -c user.name="The Diaper Aisle" -c user.email="thediaperaisle@gmail.com" commit -m "Data for <YYYY-MM-DD>"
   git fetch --depth 1 origin main && git rebase origin/main
   git push origin main
   ```
   If nothing changed, git says so; that is fine.
4. Check: `git ls-remote origin main` shows the new commit.

## Failures
Any failure (add_repo refused, clone/push failed, publish.py error) goes in `issues` as a PROBLEM: "Public site not updated: <reason>". It appears in the owner's push/email only, never the public edition. It does not stop the rest of the run.

Do not edit `index.html` or anything outside `data/` during the daily run.
