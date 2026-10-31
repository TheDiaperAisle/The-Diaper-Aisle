#!/usr/bin/env python3
"""Dip Aisle stock check: fix 'in stock' flags that a store's product feed gets wrong.

Healthwick instead writes backorders into the product description; those variants are marked too.

AgeComfort sells many items as backorders ("continue selling when out of stock"), so its
/products.json says available=true even when the product page shows
"Out of Stock - This item will ship once back in stock". The page renders one stock badge
for the selected variant (icon-in_stock / icon-out_stock), then one per variant in the same
order as the page's schema.org offers. This script reads those badges and updates the rows
the scraper wrote.

Usage (after scraper.py):  python3 stock_check.py OUT_DIR
Rewrites OUT_DIR/catalog-*.json and OUT_DIR/history-*.json in place and prints a summary.
Needs www.agecomfort.com on the network allowlist; if a page cannot be read, that product keeps
the feed's value.
"""
import json, re, sys, os, glob, time, urllib.request, urllib.parse

PAGE_BASE = {"AgeComfort": "https://www.agecomfort.com"}
# Stores that flag backorders in the product description instead ("Please Note: PVS-512 (S/M) AND PVS-513 (L)
# are currently backordered", "this product is on manufacturer backorder") while the feed still says available.
DESC_BASE = {"Healthwick": "https://healthwick.ca"}
UA = {"User-Agent": "Mozilla/5.0 (DipAisleTracker; price research)"}


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def variant_stock(raw):
    """Page HTML -> {variant id: True (in stock) / False (out of stock)}, or {} if the layout is not recognised."""
    marks = re.findall(r"icon-(in|out)_stock", raw)
    ids = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', raw, re.S):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            offers = d.get("offers") or []
            offers = offers if isinstance(offers, list) else [offers]
            for o in offers:
                v = re.search(r"variant=(\d+)", o.get("url") or "")
                ids.append(v.group(1) if v else None)
            break
    if not ids:
        return {}
    if len(marks) == len(ids) + 1:      # selected-variant badge, then one per variant
        return {i: m == "in" for i, m in zip(ids, marks[1:]) if i}
    if len(ids) == 1 and marks:          # single-variant product
        return {ids[0]: marks[0] == "in"} if ids[0] else {}
    return {}


def desc_backorders(base, handles):
    """-> {variant id: False} for variants a product description says are backordered."""
    out, page = {}, 1
    while page < 10:
        d = json.loads(fetch(f"{base}/products.json?limit=250&page={page}"))["products"]
        if not d:
            break
        for p in d:
            if p["handle"] not in handles:
                continue
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p.get("body_html") or ""))
            for sent in re.findall(r"[^.]*\bback-?order\w*[^.]*", txt, re.I):
                codes = [c.upper() for c in re.findall(r"\b([A-Z]{1,5}-?\d{2,}[A-Z]?)\b", sent)]
                for v in p["variants"]:
                    sku = (v.get("sku") or "").upper()
                    if (codes and any(sku.startswith(c) for c in codes)) or \
                            (not codes and re.search(r"this (?:product|item) is (?:on|currently on|currently) (?:\w+ )?back-?order", sent, re.I)):
                        out[str(v["id"])] = False
        page += 1
    return out


def main(out):
    cat_files = sorted(glob.glob(os.path.join(out, "catalog-*.json")))
    docs = {f: json.load(open(f)) for f in cat_files}
    handles = {}
    for f, d in docs.items():
        for r in d["rows"]:
            if r["store"] in PAGE_BASE and not r.get("stale"):
                m = re.search(r"/products/([^?#/]+)", r["url"])
                if m:
                    handles.setdefault((r["store"], m.group(1)), []).append(r)
    stock, failed = {}, []
    for (store, handle), rows in handles.items():
        try:
            raw = fetch(f"{PAGE_BASE[store]}/products/{urllib.parse.quote(handle)}")
        except Exception as e:  # noqa
            failed.append(f"{handle}: {e}")
            continue
        s = variant_stock(raw)
        if not s:
            failed.append(f"{handle}: stock badges not recognised")
        stock.update(s)
        time.sleep(0.3)
    for store, base in DESC_BASE.items():
        hs = {re.search(r"/products/([^?#/]+)", r["url"]).group(1)
              for d in docs.values() for r in d["rows"] if r["store"] == store and "/products/" in r["url"]}
        try:
            stock.update(desc_backorders(base, hs))
        except Exception as e:  # noqa
            failed.append(f"{store} descriptions: {e}")
    changed = {}
    for f, d in docs.items():
        for r in d["rows"]:
            m = re.search(r"variant=(\d+)", r.get("url") or "")
            if r["store"] not in PAGE_BASE or not m or m.group(1) not in stock:
                continue
            on_page = stock[m.group(1)]
            if r["avail"] and not on_page:       # feed says buyable, page says out of stock (backorder)
                r["avail"] = False
                r["bo"] = True
                changed[r["id"]] = 0
            elif on_page and r.get("bo"):
                r.pop("bo", None)
        json.dump(d, open(f, "w"), separators=(",", ":"))
    # keep today's history point in step with the corrected stock flag
    for f in sorted(glob.glob(os.path.join(out, "history-*.json"))):
        h = json.load(open(f))
        for rid, av in changed.items():
            pts = h.get("h", {}).get(rid)
            if pts:
                pts[-1][2] = av
                if len(pts) > 1 and pts[-2][1:] == pts[-1][1:]:
                    pts.pop()
        json.dump(h, open(f, "w"), separators=(",", ":"))
    print(json.dumps({"pages": len(handles), "pages_failed": len(failed), "marked_out_of_stock": len(changed),
                      "examples_failed": failed[:5]}))


if __name__ == "__main__":
    main(sys.argv[1])
