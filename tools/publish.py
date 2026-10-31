#!/usr/bin/env python3
"""Copy the tracker's daily data into this repo's data/ folder.

Usage: python3 tools/publish.py <source_dir> [repo_dir]

<source_dir> is either the scraper's ./out folder (catalog-0.json, history-0.json,
thumbs-0.json, meta.json) or a folder downloaded from the artifact database. Every
*.json file under it is sorted by its contents, so the file names don't matter:
  {"rows": [...]}            -> catalog
  {"h": {...}}               -> history
  {"t": {...}}               -> thumbs
  {"stores": ..., "lastRun"} -> meta
A file wrapped as {"id": ..., "data": {...}} is unwrapped first.

The old data/ files are replaced, and meta.json gets the new doc counts.
Prints a one-line JSON summary.
"""
import json, sys, pathlib, shutil

src = pathlib.Path(sys.argv[1])
repo = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else pathlib.Path(__file__).resolve().parent.parent)
out = repo / "data"

def docs(path):
    try:
        d = json.loads(path.read_text())
    except Exception:
        return []
    items = d if isinstance(d, list) else [d]
    res = []
    for x in items:
        if isinstance(x, dict) and isinstance(x.get("data"), dict) and "id" in x:
            res.append((str(x["id"]), x["data"]))
        elif isinstance(x, dict):
            res.append((path.stem, x))
    return res

def order(key):
    digits = "".join(c for c in key if c.isdigit())
    return (int(digits) if digits else 0, key)

sets = {"catalog": [], "history": [], "thumbs": []}
meta = None
for p in sorted(src.rglob("*.json")):
    for key, d in docs(p):
        if "stores" in d or "lastRun" in d: meta = d
        elif isinstance(d.get("rows"), list): sets["catalog"].append((key, d))
        elif isinstance(d.get("h"), dict): sets["history"].append((key, d))
        elif isinstance(d.get("t"), dict): sets["thumbs"].append((key, d))

if meta is None or not sets["catalog"]:
    sys.exit(f"publish: no catalog/meta found under {src}")

if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
for name, lst in sets.items():
    seen = {}
    for key, d in lst:
        seen[key] = d                      # same doc found twice -> keep one
    for i, key in enumerate(sorted(seen, key=order)):
        (out / f"{name}-{i}.json").write_text(json.dumps(seen[key], separators=(",", ":")))
    meta[{"catalog": "catalogDocs", "history": "historyDocs", "thumbs": "thumbDocs"}[name]] = len(seen)
(out / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))
print(json.dumps({"catalog": meta["catalogDocs"], "history": meta["historyDocs"],
                  "thumbs": meta["thumbDocs"], "rows": sum(len(d["rows"]) for _, d in sets["catalog"]),
                  "date": meta.get("date")}))
