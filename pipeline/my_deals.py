#!/usr/bin/env python3
"""Dip Aisle: the owner's personal deal matcher ("My deals", owner edition of the daily email only).

Usage:  python3 pipeline/my_deals.py ./out ./prev PROFILE.json > my_deals.json

PROFILE.json is the owner's private shopping profile (sizes, owned products, fit notes). It is never committed:
keep it outside the repo. This script only reads the tracker's catalog and history.

All prices are DELIVERED prices per piece to Ontario (package price + that store's shipping for an order of just that
package, as the tracker's Delivered column), so a cheap bag with a flat shipping fee is not mistaken for a deal.
Where shipping is only quoted at checkout, the shelf price is used and the deal says "+ shipping".

A listing is a deal when it is a diaper or booster the owner can wear (size/fit rules below), in stock, and its
price per piece is at or below the owner's benchmark for its absorbency tier, or below the benchmark of a LOWER
tier (more capacity for less: "upgrade"). Benchmarks = the cheapest in-stock price today of the products the owner
already uses in that tier (falls back to yesterday's price when all of them are sold out).

Daily vs weekly (owner 2026-11-19: the same matches every day were too much): on most days only deals that CHANGED
are listed (new today, delivered price down DROP_PCT% or more since yesterday, or a new lowest price), with a count
of the unchanged ones; on WEEKLY_DAY (Monday) the full list. `--full` forces the full list.
"""
import datetime, glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from changes import delivered  # same shipping rules as the tracker page (Ontario)

DROP_PCT = 5          # a deal whose delivered price fell this much since yesterday counts as changed
WEEKLY_DAY = 0        # Monday: the full list of current deals
FIT_ORDER = {"good": 0, "likely": 1, "snug": 2, "unknown": 3, "small": 4, "large": 5}
FIT_LABEL = {"good": "Fits you", "likely": "Likely fits", "snug": "Snug fit", "unknown": "Fit unknown",
             "small": "May run small", "large": "May run large"}


def load_rows(d):
    rows = []
    for f in sorted(glob.glob(os.path.join(d, "catalog-*.json"))):
        rows += json.load(open(f)).get("rows", [])
    return rows


def load_hist(d):
    h = {}
    for f in sorted(glob.glob(os.path.join(d, "history-*.json"))):
        h.update(json.load(open(f)).get("h", {}))
    return h


def text(r):
    return " ".join(str(r.get(k) or "") for k in ("brand", "name", "line", "variant")).lower()


def matches(r, o):
    if o.get("brand") and o["brand"] not in (r.get("brand") or "").lower() + " " + (r.get("name") or "").lower():
        return False
    t = text(r)
    if not all(m in t for m in o["match"]):
        return False
    return o.get("size") is None or r.get("size") == o["size"]


def size_fit(r, prof):
    """fit key for this listing's size, or None when the size can't be worn at all."""
    lo, hi = prof["waist"]
    t = text(r)
    for o in prof["owned"]:
        if o.get("fit") and matches(r, o):
            return o["fit"]
    for rule in prof.get("fit_rules", []):
        if (r.get("brand") or "").lower() == rule["brand"].lower() and r.get("size") == rule["size"] \
                and not any(u in t for u in rule.get("unless", [])):
            return rule["fit"]
    w, s = r.get("waist"), r.get("size")
    if w:
        a, b = w
        if a > hi + 2 or b < lo:          # starts well above or ends below the owner's waist
            return None
        if a > hi:
            return "large"
        if b >= 42:
            return "likely"
        return "small"
    # no stated range: go by the size name
    if s in ("M", "M/L", "S/M"):
        return "unknown"
    return None


def tier_of(cap, tiers):
    for i, t in enumerate(tiers):
        if cap is not None and t["min"] <= cap <= t["max"]:
            return i
    return None


def dppd(r):
    """delivered price per piece (Ontario), falling back to the shelf price when shipping is quoted at checkout."""
    if not r.get("ppd"):
        return None
    d, quoted = delivered(r, r["price"])
    return (d if d is not None and not quoted else r["ppd"]), (d is None or quoted)


def run(out_dir, prev_dir, profile_path, full=None):
    prof = json.load(open(profile_path))
    rows, prev = load_rows(out_dir), load_rows(prev_dir)
    hist = load_hist(out_dir) or load_hist(prev_dir)
    prev_by_id = {r["id"]: r for r in prev}
    tiers = prof["tiers"] + prof["booster_tiers"]
    nd = len(prof["tiers"])

    def live(r):
        return r.get("avail") and not r.get("bo") and r.get("pkg") != "Sample" and r.get("ppd")

    for r in rows + prev:
        if r.get("ppd"):
            r["_d"], r["_q"] = dppd(r)

    # ---- benchmarks per tier: cheapest in-stock price of what the owner already uses ----
    bench = {}
    for o in prof["owned"]:
        cands = [r for r in rows if matches(r, o) and live(r)] or \
                [r for r in prev if matches(r, o) and r.get("ppd") and r.get("pkg") != "Sample"]
        if not cands:
            continue
        best = min(cands, key=lambda r: r["_d"])
        cur = bench.get(o["tier"])
        if cur is None or best["_d"] < cur["ppd"]:
            bench[o["tier"]] = {"ppd": round(best["_d"], 2), "name": o["name"], "store": best["store"], "url": best.get("url")}

    def is_deal(r, ti, rows_tiers):
        """(beats, upgrade_from) where beats = the tier benchmark beaten (own tier or a lower one)."""
        best = None
        for j in rows_tiers:
            b = bench.get(tiers[j]["id"])
            if b and r["_d"] <= b["ppd"] + 1e-9:
                if best is None or j < best:   # prefer reporting the lowest tier it beats
                    best = j
        return best

    deals = {}
    for r in rows:
        if not live(r) or r.get("cat") not in ("diaper", "booster"):
            continue
        cap = r.get("cap")
        if r["cat"] == "diaper":
            fit = size_fit(r, prof)
            if fit is None or cap is None:
                continue
            ti = tier_of(cap, prof["tiers"])
            if ti is None:
                continue
            beat = is_deal(r, ti, range(0, ti + 1))
        else:
            fit = None
            if cap is None:
                continue
            bi = tier_of(cap, prof["booster_tiers"])
            if bi is None:
                continue
            ti = nd + bi
            beat = is_deal(r, ti, range(nd, ti + 1))
        if beat is None:
            continue
        h = [p[1] for p in hist.get(r["id"], [])]
        prior_low = min(h[:-1]) if len(h) > 1 else None
        p0 = prev_by_id.get(r["id"])
        was_deal = bool(p0 and p0.get("avail") and p0.get("_d") and p0["_d"] <= r["_d"] + 1e-9)
        deal = {
            "tier": tiers[ti]["id"], "beats": tiers[beat]["id"], "upgrade": beat < ti,
            "item": f'{r.get("name")}', "brand": r.get("brand"), "size": r.get("size"), "pkg": r.get("pkg"),
            "qty": r.get("qty"), "price": r.get("price"), "ppd": round(r["_d"], 2), "shelf_ppd": round(r["ppd"], 2),
            "plus_shipping": r["_q"], "cap": cap,
            "per_l": round(r["_d"] / cap * 1000, 2) if cap else None, "store": r.get("store"), "url": r.get("url"),
            "fit": fit, "fit_label": FIT_LABEL.get(fit) if fit else None,
            "new": not was_deal, "lowest_seen": prior_low is not None and r["price"] < prior_low - 1e-9,
            # changed today: the price moved since yesterday (a low price that holds is not news again)
            "moved": bool(p0 and p0.get("price") != r["price"]),
            "drop_pct": round((1 - r["_d"] / p0["_d"]) * 100, 1) if (p0 and p0.get("_d") and r["_d"] < p0["_d"]) else None,
            "ck": r.get("ck") or r["id"],
        }
        # one row per product x size: keep the cheapest pack, preferring a better fit
        k = deal["ck"]
        cur = deals.get(k)
        if cur is None or (deal["ppd"], FIT_ORDER.get(fit or "", 9)) < (cur["ppd"], FIT_ORDER.get(cur["fit"] or "", 9)):
            deals[k] = deal

    for d in deals.values():
        d["lowest_seen"] = d["lowest_seen"] and (d["moved"] or d["new"])
        d["changed"] = d["new"] or d["lowest_seen"] or (d["drop_pct"] or 0) >= DROP_PCT
    if full is None:
        try:
            day = json.load(open(os.path.join(out_dir, "meta.json"))).get("date")
            full = datetime.date.fromisoformat(day).weekday() == WEEKLY_DAY
        except Exception:  # noqa
            full = datetime.date.today().weekday() == WEEKLY_DAY
    total = len(deals)
    changed = sum(1 for d in deals.values() if d["changed"])

    out = []
    for t in tiers:
        ds = [d for d in deals.values() if d["tier"] == t["id"] and (full or d["changed"])]
        # best value first: price per litre for diapers, price per piece for boosters
        ds.sort(key=lambda d: (FIT_ORDER.get(d["fit"] or "", 0) >= 4, d["per_l"] if d["per_l"] else d["ppd"]))
        if not ds:
            continue
        lim = prof.get("max_per_tier", 6)
        out.append({"tier": t["id"], "name": t["name"], "range": [t["min"], t["max"]], "benchmark": bench.get(t["id"]),
                    "deals": ds[:lim], "more": max(0, len(ds) - lim)})
    new_count = sum(1 for d in deals.values() if d["new"])
    shown = sum(len(g["deals"]) + g["more"] for g in out)
    res = {"benchmarks": bench, "groups": out, "new_count": new_count, "changed": changed, "total": total,
           "full": full, "unchanged": total - shown, "count": sum(len(g["deals"]) for g in out),
           "notify": bool(changed or (full and total)),
           "text": to_text(out, bench, tiers, full, total - shown)}
    return res


def rng(t):
    a, b = t["range"]
    return f"{a:,}+ mL" if b >= 99999 else (f"under {b + 1:,} mL" if a == 0 else f"{a:,}–{b:,} mL")


def to_text(groups, bench, tiers, full=True, unchanged=0):
    if not groups:
        return ""
    names = {t["id"]: t["name"] for t in tiers}
    lines = ["MY DEALS (delivered to Ontario, at or below what you pay now)" if full else
             "MY DEALS: CHANGED TODAY (delivered to Ontario, at or below what you pay now)"]
    if not full and unchanged:
        lines.append(f"{unchanged} other deal{'s' if unchanged != 1 else ''} unchanged. Full list on Mondays.")
    for g in groups:
        b = g["benchmark"]
        lines.append("")
        lines.append(f'{g["name"]} · {rng(g)}' + (f' · your price ${b["ppd"]:.2f} ({b["name"]})' if b else ""))
        for d in g["deals"]:
            tags = [x for x in (d["fit_label"], f'beats your {names[d["beats"]].lower()} price' if d["upgrade"] else "",
                                "new" if d["new"] else "", f'down {d["drop_pct"]:.0f}%' if (d.get("drop_pct") or 0) >= DROP_PCT else "",
                                "lowest seen" if d["lowest_seen"] else "") if x]
            cap = f'{d["cap"]:,} mL · ' if d["cap"] else ""
            lines.append(f'- {d["item"]} {d["size"] or ""} {d["pkg"]} {d["qty"]} @ {d["store"]}: ${d["price"]:.2f} '
                         f'= ${d["ppd"]:.2f} each {"+ shipping" if d["plus_shipping"] else "delivered"} · {cap}{", ".join(tags)}\n  {d["url"]}')
        if g["more"]:
            lines.append(f'  + {g["more"]} more')
    return "\n".join(lines)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--full"]
    print(json.dumps(run(args[0], args[1], args[2], full=True if "--full" in sys.argv else None), indent=1, ensure_ascii=False))
