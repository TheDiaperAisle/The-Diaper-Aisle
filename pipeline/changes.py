#!/usr/bin/env python3
"""Dip Aisle: daily change + data-issue report, comparing yesterday's data (PREV_DIR) with today's (OUT_DIR).

Usage:  python3 changes.py PREV_DIR OUT_DIR [SCRAPE_LOG]
  SCRAPE_LOG = the scraper's stderr (python3 scraper.py ./out ./prev 2> scrape.log)
Prints JSON with:
  price_changes, back_in_stock, out_of_stock, new_listings, removed_listings  (lists)
  issues   (list of data-quality problems found during the scrape)
  banner   (one short line for a phone notification)
  report   (the full plain-text report)
Stale (carried-forward) rows are ignored for change detection, since they were not re-read today.
"""
import json, os, re, sys
from collections import Counter

NO_CAP_BRANDS = {"TENA", "Prevail", "Attends"}  # capacity usually not advertised; never flag it as missing


def load_rows(d):
    rows = {}
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith(".json") and "catalog" in os.path.join(root, f):
                for r in json.load(open(os.path.join(root, f))).get("rows", []):
                    rows[r["id"]] = r
    return rows


def load_meta(d):
    for p in (os.path.join(d, "meta", "status.json"), os.path.join(d, "meta.json")):
        if os.path.exists(p):
            return json.load(open(p))
    return {}


def label(r):
    name = " ".join(b for b in (r.get("brand") or "", r.get("line") or r.get("name") or "") if b).strip()
    pkg = (r.get("pkg") or "") + (f" of {r['qty']}" if r.get("qty") else "")
    extra = " ".join(x for x in (r.get("variant"), r.get("size"), pkg) if x)
    return f"{name} ({extra}) @ {r['store']}"


# Delivered price per piece, as the tracker shows it (owner 2026-11-03: price changes include it). Shipping rules come
# from the page itself (index.html, const SHIP) so the email and the tracker always agree; province = the page default.
SHIP_PROV = "ON"
ONE = {"diaper": "diaper", "pullup": "pull-up", "booster": "booster"}


def _ship_rules():
    try:
        page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "index.html"), encoding="utf-8").read()
        return json.loads(re.search(r"const SHIP = (\{.*?\});\n", page).group(1))["stores"]
    except Exception:  # noqa
        return {}


SHIP = _ship_rules()


def delivered(r, price):
    """-> (delivered price per piece, shipping quoted at checkout?) or (None, False) when it can't be worked out"""
    rules = ((SHIP.get(r.get("store")) or {}).get("rules") or {}).get(SHIP_PROV)
    if not rules or not r.get("qty"):
        return None, False
    fee = None
    for frm, f in rules:
        if price >= frm:
            fee = f
    return round((price + (fee or 0)) / r["qty"], 3), fee is None


def unit(x):
    return f"${x:.{3 if x < 1 else 2}f}"


def delivered_note(c):
    if c.get("d_new") is None:
        return ""
    if c.get("ship_quoted"):
        return f" · {unit(c['d_new'])}/{c['one']} + shipping"
    return f" · delivered {unit(c['d_old'])} → {unit(c['d_new'])}/{c['one']} ({SHIP_PROV})" if c.get("d_old") is not None and c["d_old"] != c["d_new"] \
        else f" · delivered {unit(c['d_new'])}/{c['one']} ({SHIP_PROV})"


def money(x):
    return f"${x:.2f}"


def main():
    prev_dir, out_dir = sys.argv[1], sys.argv[2]
    log = open(sys.argv[3], errors="replace").read() if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
    prev, out = load_rows(prev_dir), load_rows(out_dir)
    pmeta, ometa = load_meta(prev_dir), load_meta(out_dir)
    stale_stores = {r["store"] for r in out.values() if r.get("stale")}

    # a row whose pack quantity was corrected gets a new id (Store|handle|size|pkg|qty|variant): when exactly one
    # unmatched row of yesterday has the same store, handle, size and variant, it is the same listing
    def loose(k):
        x = k.split("|")
        return tuple(x[:3] + x[5:])
    spare = {}
    for k in prev:
        if k not in out:
            spare.setdefault(loose(k), []).append(k)
    renamed = {}
    for k in out:
        if k not in prev and len(spare.get(loose(k), [])) == 1:
            renamed[k] = spare[loose(k)][0]
    # a size found later or corrected ('One size' -> M, '2X' read as XXL): same listing, package and variant
    used = set(renamed.values())
    def by_pkg(k):
        x = k.split("|")
        return tuple(x[:2] + x[3:4] + x[5:])
    spare2, need2 = {}, {}
    for k in prev:
        if k not in out and k not in used:
            spare2.setdefault(by_pkg(k), []).append(k)
    for k in out:
        if k not in prev and k not in renamed:
            need2.setdefault(by_pkg(k), []).append(k)
    for key, new in need2.items():
        if len(new) == 1 and len(spare2.get(key, [])) == 1:
            renamed[new[0]] = spare2[key][0]
    if len(set(renamed.values())) != len(renamed):
        renamed = {k: v for k, v in renamed.items() if list(renamed.values()).count(v) == 1}

    changes, back, oos, new, gone = [], [], [], [], []
    for k, r in out.items():
        p = prev.get(k) or prev.get(renamed.get(k))
        if r.get("stale"):
            continue
        if not p:
            new.append({"id": k, "item": label(r), "price": r["price"], "avail": r.get("avail")})
            continue
        if p.get("stale"):
            continue
        if r["price"] != p["price"]:
            d_old, _ = delivered(r, p["price"])
            d_new, quoted = delivered(r, r["price"])
            changes.append({"id": k, "item": label(r), "old": p["price"], "new": r["price"],
                            "pct": round((r["price"] - p["price"]) / p["price"] * 100, 1) if p["price"] else None,
                            "d_old": d_old, "d_new": d_new, "ship_quoted": quoted, "one": ONE.get(r.get("cat"), "piece")})
        if r.get("avail") and not p.get("avail"):
            back.append({"id": k, "item": label(r), "price": r["price"]})
        elif p.get("avail") and not r.get("avail"):
            oos.append({"id": k, "item": label(r), "price": r["price"]})
    for k, p in prev.items():
        if k not in out and k not in renamed.values() and p["store"] not in stale_stores:
            gone.append({"id": k, "item": label(p), "price": p["price"]})
    changes.sort(key=lambda c: c["pct"] or 0)

    # ----- data issues -----
    issues = []
    stores = (ometa.get("stores") or {})
    for s, st in stores.items():
        if not st.get("ok"):
            issues.append(f"{s} FAILED: {st.get('error')} (yesterday's {st.get('carried', 0)} rows carried forward as stale)")
    if not ometa:
        issues.append("no meta.json in today's output: the scraper may not have finished")
    for s, st in stores.items():
        old = ((pmeta.get("stores") or {}).get(s) or {}).get("rows")
        if st.get("ok") and old and st.get("rows") is not None and st["rows"] < old * 0.9:
            issues.append(f"{s} row count dropped {old} → {st['rows']} ({round((st['rows'] - old) / old * 100)}%)")
        oldp = ((pmeta.get("stores") or {}).get(s) or {}).get("products")
        if st.get("ok") and oldp and st.get("products") is not None and st["products"] < oldp * 0.9:
            issues.append(f"{s} product count dropped {oldp} → {st['products']}")
    live = [r for r in out.values() if not r.get("stale")]
    noqty = Counter(r["store"] for r in live if not r.get("qty"))
    prev_noqty = Counter(r["store"] for r in prev.values() if not r.get("qty") and not r.get("stale"))
    for s, n in noqty.items():
        if n > prev_noqty.get(s, 0) + 5:
            issues.append(f"{s}: {n} rows have no pack quantity (was {prev_noqty.get(s, 0)})")
    for r in live:
        p = prev.get(r["id"]) or prev.get(renamed.get(r["id"]))
        if p and not p.get("stale") and p["price"] and abs(r["price"] - p["price"]) / p["price"] > 0.5:
            issues.append(f"price moved >50%, check for a parsing error: {label(r)} {money(p['price'])} → {money(r['price'])}")
    if log is not None:
        for kind, pat in (("Rearz option-price lookups failed", r"^rearz lookup fail"),
                          ("thumbnails failed to download", r"^thumb fail"),
                          ("ABUniverse case-option pages could not be read", r"^case options fail"),
                          ):
            n = len(re.findall(pat, log, re.M))
            if n:
                issues.append(f"{n} {kind}")
        # Failed product-page capacity reads only matter when a product LOST a capacity it had yesterday.
        # Many products never advertise one (owner 2026-10-30: most TENA, Prevail, Attends), so a failed
        # read for a product that had no capacity before, or that still has one from another store, is not an issue.
        failed = {u.rstrip("/").rsplit("/", 1)[-1].split("?")[0] for u in re.findall(r"^page capacity fail (\S+)", log, re.M)}
        lost = sorted({label(r).split(" (")[0] + " @ " + r["store"] for k, r in out.items()
                       if not r.get("stale") and not r.get("cap") and (r.get("brand") or "") not in NO_CAP_BRANDS
                       and k in prev and prev[k].get("cap") and r["t"].split("|", 1)[-1] in failed})
        if lost:
            issues.append(f"{len(lost)} product(s) lost their capacity because the product page could not be read: " + "; ".join(lost[:10]))
        tb = re.search(r"Traceback \(most recent call last\):.*", log, re.S)
        if tb:
            issues.append("scraper crashed: " + tb.group(0).strip().splitlines()[-1][:200])

    # ----- text -----
    # Banner: only what changed and what is broken (owner 2026-10-30). Nothing about things that worked.
    def by_store(items):
        c = Counter(x["id"].split("|", 1)[0] for x in items)
        if len(c) == 1:
            return f"all {next(iter(c))}"
        return ", ".join(f"{s} {n}" for s, n in c.most_common())
    head = []
    if changes:
        up = sum(1 for c in changes if c["new"] > c["old"])
        dirs = " / ".join(x for x in (f"{up} up" if up else "", f"{len(changes) - up} down" if len(changes) - up else "") if x)
        head.append(f"{len(changes)} price change{'s' if len(changes) != 1 else ''} ({dirs}; {by_store(changes)})")
    if oos:
        head.append(f"{len(oos)} out of stock ({by_store(oos)})")
    if back:
        head.append(f"{len(back)} back in stock ({by_store(back)})")
    if new:
        head.append(f"{len(new)} new ({by_store(new)})")
    if gone:
        head.append(f"{len(gone)} removed ({by_store(gone)})")
    if issues:
        head.append(f"{len(issues)} problem{'s' if len(issues) != 1 else ''} to check")
    banner = "Dip Aisle: " + ("; ".join(head) if head else "no price or stock changes today") + "."

    lines = [banner]
    sections = [
        ("PROBLEMS", [f"- {i}" for i in issues]),
        ("PRICE CHANGES", [f"- {c['item']}: {money(c['old'])} → {money(c['new'])} ({c['pct']:+.1f}%)" + delivered_note(c) for c in changes]),
        ("BACK IN STOCK", [f"- {x['item']}: {money(x['price'])}" for x in back]),
        ("NEWLY OUT OF STOCK", [f"- {x['item']}: {money(x['price'])}" for x in oos]),
        ("NEW LISTINGS", [f"- {x['item']}: {money(x['price'])}" + ("" if x["avail"] else " (out of stock)") for x in new]),
        ("REMOVED LISTINGS", [f"- {x['item']}: was {money(x['price'])}" for x in gone]),
    ]
    for title, items in sections:
        if items:
            lines += ["", f"{title} ({len(items)})"] + items
    print(json.dumps({"price_changes": changes, "back_in_stock": back, "out_of_stock": oos, "new_listings": new,
                      "removed_listings": gone, "issues": issues, "banner": banner, "report": "\n".join(lines)},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
