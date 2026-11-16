#!/usr/bin/env python3
"""Dip Aisle: the owner's personal deal matcher ("My deals", owner edition of the daily email only).

Usage:  python3 pipeline/my_deals.py ./out ./prev PROFILE.json > my_deals.json

PROFILE.json is the owner's private shopping profile (sizes, owned products, fit notes). It is never committed:
keep it outside the repo. This script only reads the tracker's catalog and history.

A listing is a deal when it is a diaper or booster the owner can wear (size/fit rules below), in stock, and its
price per piece is at or below the owner's benchmark for its absorbency tier, or below the benchmark of a LOWER
tier (more capacity for less: "upgrade"). Benchmarks = the cheapest in-stock price today of the products the owner
already uses in that tier (falls back to yesterday's price when all of them are sold out).
"""
import glob, json, os, sys

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


def run(out_dir, prev_dir, profile_path):
    prof = json.load(open(profile_path))
    rows, prev = load_rows(out_dir), load_rows(prev_dir)
    hist = load_hist(out_dir) or load_hist(prev_dir)
    prev_by_id = {r["id"]: r for r in prev}
    tiers = prof["tiers"] + prof["booster_tiers"]
    nd = len(prof["tiers"])

    def live(r):
        return r.get("avail") and not r.get("bo") and r.get("pkg") != "Sample" and r.get("ppd")

    # ---- benchmarks per tier: cheapest in-stock price of what the owner already uses ----
    bench = {}
    for o in prof["owned"]:
        cands = [r for r in rows if matches(r, o) and live(r)] or \
                [r for r in prev if matches(r, o) and r.get("ppd") and r.get("pkg") != "Sample"]
        if not cands:
            continue
        best = min(cands, key=lambda r: r["ppd"])
        cur = bench.get(o["tier"])
        if cur is None or best["ppd"] < cur["ppd"]:
            bench[o["tier"]] = {"ppd": round(best["ppd"], 2), "name": o["name"], "store": best["store"], "url": best.get("url")}

    def is_deal(r, ti, rows_tiers):
        """(beats, upgrade_from) where beats = the tier benchmark beaten (own tier or a lower one)."""
        best = None
        for j in rows_tiers:
            b = bench.get(tiers[j]["id"])
            if b and r["ppd"] <= b["ppd"] + 1e-9:
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
        h = [p[1] / r["qty"] for p in hist.get(r["id"], []) if r.get("qty")]
        prior_low = min(h[:-1]) if len(h) > 1 else None
        p0 = prev_by_id.get(r["id"])
        was_deal = bool(p0 and p0.get("avail") and p0.get("ppd") and p0["ppd"] <= r["ppd"] + 1e-9)
        deal = {
            "tier": tiers[ti]["id"], "beats": tiers[beat]["id"], "upgrade": beat < ti,
            "item": f'{r.get("name")}', "brand": r.get("brand"), "size": r.get("size"), "pkg": r.get("pkg"),
            "qty": r.get("qty"), "price": r.get("price"), "ppd": round(r["ppd"], 2), "cap": cap,
            "per_l": round(r["ppd"] / cap * 1000, 2) if cap else None, "store": r.get("store"), "url": r.get("url"),
            "fit": fit, "fit_label": FIT_LABEL.get(fit) if fit else None,
            "new": not was_deal, "lowest_seen": prior_low is not None and r["ppd"] < prior_low - 1e-9,
            "ck": r.get("ck") or r["id"],
        }
        # one row per product x size: keep the cheapest pack, preferring a better fit
        k = deal["ck"]
        cur = deals.get(k)
        if cur is None or (deal["ppd"], FIT_ORDER.get(fit or "", 9)) < (cur["ppd"], FIT_ORDER.get(cur["fit"] or "", 9)):
            deals[k] = deal

    out = []
    for t in tiers:
        ds = [d for d in deals.values() if d["tier"] == t["id"]]
        # best value first: price per litre for diapers, price per piece for boosters
        ds.sort(key=lambda d: (FIT_ORDER.get(d["fit"] or "", 0) >= 4, d["per_l"] if d["per_l"] else d["ppd"]))
        if not ds:
            continue
        lim = prof.get("max_per_tier", 6)
        out.append({"tier": t["id"], "name": t["name"], "range": [t["min"], t["max"]], "benchmark": bench.get(t["id"]),
                    "deals": ds[:lim], "more": max(0, len(ds) - lim)})
    new_count = sum(1 for g in out for d in g["deals"] if d["new"])
    res = {"benchmarks": bench, "groups": out, "new_count": new_count,
           "count": sum(len(g["deals"]) for g in out), "text": to_text(out, bench, tiers)}
    return res


def rng(t):
    a, b = t["range"]
    return f"{a:,}+ mL" if b >= 99999 else (f"under {b + 1:,} mL" if a == 0 else f"{a:,}–{b:,} mL")


def to_text(groups, bench, tiers):
    if not groups:
        return ""
    names = {t["id"]: t["name"] for t in tiers}
    lines = ["MY DEALS (at or below what you pay now)"]
    for g in groups:
        b = g["benchmark"]
        lines.append("")
        lines.append(f'{g["name"]} · {rng(g)}' + (f' · your price ${b["ppd"]:.2f} ({b["name"]})' if b else ""))
        for d in g["deals"]:
            tags = [x for x in (d["fit_label"], f'beats your {names[d["beats"]].lower()} price' if d["upgrade"] else "",
                                "new" if d["new"] else "", "lowest seen" if d["lowest_seen"] else "") if x]
            cap = f'{d["cap"]:,} mL · ' if d["cap"] else ""
            lines.append(f'- {d["item"]} {d["size"] or ""} {d["pkg"]} {d["qty"]} @ {d["store"]}: ${d["price"]:.2f} '
                         f'= ${d["ppd"]:.2f} each · {cap}{", ".join(tags)}\n  {d["url"]}')
        if g["more"]:
            lines.append(f'  + {g["more"]} more')
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1], sys.argv[2], sys.argv[3]), indent=1, ensure_ascii=False))
