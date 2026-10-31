#!/usr/bin/env python3
"""Dip Aisle: add Amazon.ca listings to the day's catalogue.

Amazon has no product feed, so this reads Amazon.ca search-result pages through the Firecrawl API
(Canadian location, raw HTML, 1 credit a page) for a rotating list of brand searches, and keeps
results from brands the tracker follows. It stays inside a monthly credit budget (Firecrawl free
plan = 1,000 credits/month; default budget 700, leaving room for other use): each run gets an even
share of what is left this month, and the searches checked longest ago go first. Listings not
re-checked today are carried forward from yesterday with their 'checked' date, and dropped after
CARRY_DAYS days without a check.

Usage (after scraper.py, before stock_check.py):  python3 amazon.py OUT_DIR PREV_DIR
Needs: ./scraper.py (same folder) for brand/name/product-key rules, a Firecrawl key in
$FIRECRAWL_API_KEY or ./firecrawl.key, and api.firecrawl.dev (+ m.media-amazon.com for
thumbnails) on the network allowlist. Rewrites OUT_DIR catalog/history/thumbs/meta files.
Prints a JSON summary; on any failure the Amazon rows from yesterday are kept and the error is
recorded in meta.stores.Amazon.
"""
import json, re, os, sys, glob, html, math, time, io, base64, datetime, calendar, urllib.request, urllib.parse

import scraper as S

MONTHLY_BUDGET = int(os.environ.get("AMAZON_CREDIT_BUDGET", "700"))
CARRY_DAYS = 14
BASE = "https://www.amazon.ca"

# Searches, one Amazon.ca results page each. Results from any tracked brand are kept, whichever search found them.
QUERIES = [
    # adult-baby (AB) brands
    "sunkiss adult diapers", "sunkiss incontinence underwear", "littleforbig diapers", "rearz diapers",
    "tykables diapers", "abuniverse diapers", "lngu diapers", "kiddo adult diapers", "crinklz diapers",
    "cuddlz diapers", "landofgenie diapers", "bambino diapers adult", "abdl diapers",
    # brands already tracked at the other stores
    "northshore megamax", "northshore gosupreme", "tena proskin briefs", "tena incontinence underwear",
    "depend underwear", "prevail briefs", "attends briefs", "abena abri-form", "tranquility briefs",
    "tranquility underwear", "forsite health briefs", "incontrol bedry", "molicare briefs",
    "fitright briefs", "betterdry diapers", "because underwear incontinence", "booster pads adult diaper",
]
# Amazon brand names -> tracker brand (on top of scraper.BRANDS)
EXTRA_BRANDS = {"sunkiss": "Sunkiss", "littleforbig": "Little for Big", "little for big": "Little for Big",
                "landofgenie": "Landofgenie", "land of genie": "Landofgenie", "bambino": "Bambino",
                "always discreet": None}
# make the scraper's brand rules know the Amazon-only brands, so names are stripped of them consistently
for _canon, _pat in (("Sunkiss", r"sunkiss\b"), ("Landofgenie", r"land ?of ?genie\b"), ("Bambino", r"bambino\b"),
                     ("Little for Big", r"little ?for ?big\b")):
    if _canon not in dict(S.BRANDS) or _canon == "Little for Big":
        S.BRANDS.append((_canon, _pat))
# Owner-supplied capacities (mL) that the store shows only in an image, by product key and size.
CAP_BY_SIZE = {
    # Sunkiss TrustPlus Adult Diapers with Tabs, from the product image (owner, 2026-10-31)
    "diaper|sunkiss|trustplus": {"S": 1300, "M": 1600, "L": 2000, "XL": 2300, "XXL": 2600},
}
AB_BRANDS = {"Sunkiss", "Little for Big", "Rearz", "Tykables", "ABUniverse", "LNGU", "Kiddo", "Crinklz", "Cuddlz",
             "Landofgenie", "Bambino"}
GENERIC = {"adult", "printed", "diaper", "diapers", "brief", "briefs", "incontinence", "underwear", "unisex",
           "disposable", "tabs", "with", "for", "men", "women", "and", "pieces", "count", "pack", "ct", "the",
           "protective", "absorbent", "absorbency", "plastic", "backed", "tab", "style", "pull", "ups", "on"}


def firecrawl_key():
    k = os.environ.get("FIRECRAWL_API_KEY")
    if not k and os.path.exists("firecrawl.key"):
        k = open("firecrawl.key").read().strip()
    return k or None


def fetch_search(query, key):
    """-> (raw html, credits used)"""
    body = json.dumps({"url": f"{BASE}/s?k={urllib.parse.quote_plus(query)}", "formats": ["rawHtml"],
                       "location": {"country": "CA", "languages": ["en-CA"]}, "proxy": "basic",
                       "onlyMainContent": False, "removeBase64Images": True, "maxAge": 0}).encode()
    req = urllib.request.Request("https://api.firecrawl.dev/v2/scrape", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.load(r)
    d = res.get("data") or {}
    return d.get("rawHtml") or "", int((d.get("metadata") or {}).get("creditsUsed") or 1)


def tracked_brand(raw_brand, known):
    b = (raw_brand or "").strip()
    low = b.lower()
    if low in EXTRA_BRANDS:
        return EXTRA_BRANDS[low]
    for canon, pat in S.BRANDS:
        if re.match(r"(?:" + pat + r")$", low, re.I) or re.match(pat, low, re.I):
            return canon
    v = re.sub(r"\W", "", low)
    if v in getattr(S, "VENDOR_ALIAS", {}):
        return S.VENDOR_ALIAS[v]
    return b if b in known else None


def parse_results(raw):
    """Amazon.ca search HTML -> [{asin, brand, title, price, img, sponsored}]"""
    out = []
    for b in re.split(r'(?=<div[^>]*data-asin="[A-Z0-9]{10}"[^>]*data-component-type="s-search-result")', raw)[1:]:
        b = b[:60000]
        asin = re.search(r'data-asin="([A-Z0-9]{10})"', b).group(1)
        h2 = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<h2[^>]*>(.*?)</h2>", b, re.S)]
        t = re.search(r'<h2[^>]*aria-label="([^"]+)"', b)
        title = html.unescape(t.group(1)) if t else (h2[-1] if h2 else "")
        brand = h2[0] if len(h2) > 1 else ""
        pr = re.search(r'<span class="a-price"[^>]*><span class="a-offscreen">\$([\d,]+\.\d{2})<', b)
        img = re.search(r'<img class="s-image" src="([^"]+)"', b)
        out.append({"asin": asin, "brand": brand, "title": title.strip(),
                    "price": float(pr.group(1).replace(",", "")) if pr else None,
                    "img": img.group(1) if img else None,
                    "sponsored": bool(re.search(r"puis-sponsored|>Sponsored<", b))})
    return out


def name_from_title(title):
    """'TrustPlus Adult Diapers with Tabs, Unisex, XLarge, 60 Count' -> 'TrustPlus Adult Diapers with Tabs'.
    Takes the first segment (split on , ; | ( and ' - ') that has a non-generic word."""
    title = re.sub(r"\bwith tabs\b|\s+for (?:adult|men|women|unisex)\b.*$", "", title, flags=re.I)
    segs = [s.strip() for s in re.split(r",|;|\||\(|\s[-–]\s", title) if s.strip()]
    for s in segs:
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z+'’]+", s) if w.lower() not in GENERIC and len(w) > 2
                 and not S.size_of(w)]
        if words:
            return re.sub(r"\s*\d+\s*(?:pieces|count|ct|pack)\b.*$", "", s, flags=re.I).strip()
    return segs[0] if segs else title


def to_row(it, brand, today):
    title = re.sub(r"\bMd\b", "Medium", re.sub(r"\bLg\b", "Large", re.sub(r"\bSm\b", "Small", it["title"])))
    name = name_from_title(title)
    p = {"title": f"{brand} {name}", "handle": it["asin"], "vendor": brand, "product_type": "", "tags": [],
         "options": [], "variants": []}
    cat = S.category("Amazon", p)
    if not cat:
        # many Amazon titles leave out the product type before the first comma; look at the whole title
        p2 = dict(p, title=f"{brand} {title}")
        cat = S.category("Amazon", p2)
        if not cat:
            return None
    line, title_var = S.split_title("Amazon", p, brand)
    # 'Premium Adult Diapers, Abena Slip Disposable ..., Level 4' -> 'Slip Premium - Level 4' (owner, 2026-10-31):
    # the product line ('Slip', 'Pants') follows the brand later in the title, and the level is part of the name
    # at the other stores ('Slip Premium - Level 4'), so both are added to match them.
    mb = re.search(r"[,;]\s*" + re.escape(brand) + r"\s+([A-Z][A-Za-z-]+)", title)
    if mb and mb.group(1).lower() not in line.lower() and mb.group(1).lower() not in GENERIC:
        line = f"{mb.group(1)} {line}"
    lv = re.search(r"\bLevel\s+(\d)\b", title, re.I)
    if lv and "level" not in line.lower():
        line = f"{line} - Level {lv.group(1)}"
    m = re.search(r"\b(white|pink|blue|black|purple|green|yellow|beige|grey|gray|red|tie[- ]?dye)\b", title, re.I)
    variant = title_var or (S.norm_variant(m.group(1).title()) if m else None)
    sz = None
    for seg in re.split(r"[,;()|]", title):
        sz = S.size_of(seg.replace("Small/Medium", "S/M").replace("Large/X-Large", "L/XL"))
        if sz and len(seg.strip()) <= 40:
            break
        sz = None
    size = sz or S.size_of(title) or "One size"
    q = re.search(r"(\d+)\s*(?:count|ct\b|pieces|pcs|pack\b|-pack|diapers|briefs)", title, re.I) or \
        re.search(r"\((\d+)\s*pack\)", title, re.I)
    qty = int(q.group(1)) if q and 0 < int(q.group(1)) <= 400 else None
    pkg = "Case" if (re.search(r"\bcase\b", title, re.I) or (qty and qty > 40)) else "Bag"
    lo_hi = (100, 5000) if cat == "booster" else (1000, 20000)
    cap = S.capacity_ml(title, *lo_hi)
    return {
        "id": f"Amazon|{it['asin']}|{size}|{pkg}|{qty}|{variant or '-'}", "store": "Amazon",
        "name": f"{brand} {title}", "brand": brand, "line": line, "pid": S.product_key(brand, line, cat),
        "variant": variant, "cat": cat, "dims": None, "style": S.style_of(p), "size": size, "pkg": pkg, "qty": qty,
        "price": it["price"], "cap": cap, "avail": True, "t": f"Amazon|{it['asin']}", "img": it["img"],
        "url": f"{BASE}/dp/{it['asin']}", "asin": it["asin"], "checked": today,
        "ab": brand in AB_BRANDS,
    }


def load_docs(folder, kind):
    files = sorted(glob.glob(os.path.join(folder, f"{kind}-*.json")) +
                   glob.glob(os.path.join(folder, kind, "*.json")))
    return files


def main(out, prev):
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4))).strftime("%Y-%m-%d")
    month = today[:7]
    rows = []
    for f in load_docs(out, "catalog"):
        rows += json.load(open(f))["rows"]
    rows = [r for r in rows if r["store"] != "Amazon"]
    known = {r["brand"] for r in rows}
    S.learn_casing({})  # keep casing rules available (no titles needed)

    prev_meta = {}
    pm = glob.glob(os.path.join(prev, "meta", "status.json")) + glob.glob(os.path.join(prev, "meta.json"))
    if pm:
        prev_meta = json.load(open(pm[0]))
    st = (prev_meta.get("amazon") or {})
    if st.get("month") != month:
        st = {"month": month, "used": 0, "last": st.get("last", {})}
    last = st.get("last", {})
    prev_amz = {}
    for f in load_docs(prev, "catalog"):
        for r in json.load(open(f)).get("rows", []):
            if r["store"] == "Amazon":
                prev_amz[r["id"]] = r

    # how many searches today: an even share of this month's remaining budget
    y, mth = int(today[:4]), int(today[5:7])
    days_left = calendar.monthrange(y, mth)[1] - int(today[8:10]) + 1
    remaining = max(0, MONTHLY_BUDGET - st.get("used", 0))
    daily = MONTHLY_BUDGET / calendar.monthrange(y, mth)[1]
    n_today = int(min(len(QUERIES), remaining // days_left, math.ceil(daily * 1.5)))
    order = sorted(QUERIES, key=lambda q: (last.get(q, ""), QUERIES.index(q)))
    todo = order[:n_today]

    key = firecrawl_key()
    status = {"ok": True, "searches": 0, "credits_month": st.get("used", 0)}
    found, errors = {}, []
    if not key:
        status = {"ok": False, "error": "no Firecrawl key (add project doc dip-aisle/firecrawl.key)"}
        todo = []
    for qy in todo:
        try:
            raw, used = fetch_search(qy, key)
        except Exception as e:  # noqa
            errors.append(f"{qy}: {e}")
            if "402" in str(e):  # out of credits until the monthly reset
                st["used"] = MONTHLY_BUDGET
                break
            continue
        st["used"] = st.get("used", 0) + used
        status["searches"] += 1
        items = parse_results(raw)
        if not items:
            errors.append(f"{qy}: no results (blocked or page changed)")
            continue
        last[qy] = today
        for it in items:
            if it["price"] is None:
                continue
            b = tracked_brand(it["brand"], known)
            if not b:
                continue
            r = to_row(it, b, today)
            if r:
                found[r["id"]] = r
        time.sleep(1)
    st["last"] = last
    status["credits_month"] = st["used"]
    if errors:
        status["errors"] = errors[:5]
        if not found and todo:
            status["ok"] = False
            status["error"] = errors[0][:200]

    # carry forward listings not seen today (until CARRY_DAYS old)
    cutoff = (datetime.date.fromisoformat(today) - datetime.timedelta(days=CARRY_DAYS)).isoformat()
    seen_asins = {r["asin"] for r in found.values()}
    carried = [r for rid, r in prev_amz.items() if rid not in found and r.get("asin") not in seen_asins
               and (r.get("checked") or "") >= cutoff]
    amz = list(found.values()) + carried

    # product facts from the other stores (name, capacity) when the product matches
    by_pid = {}
    for r in rows:
        by_pid.setdefault(r["pid"], r)
    for r in amz:
        o = by_pid.get(r["pid"])
        if o:
            r["line"] = o["line"]
            r["cap"] = r["cap"] or o.get("cap")
        sized = CAP_BY_SIZE.get(r["pid"], {}).get(r["size"])
        if sized:
            r["cap"] = sized
        r["ppd"] = round(r["price"] / r["qty"], 3) if r["qty"] else None
        r["ppl"] = round(r["ppd"] / (r["cap"] / 1000), 3) if (r.get("ppd") and r.get("cap")) else None
        r["ck"] = f"{r['pid']}|{r['size']}|"

    # history: only for listings checked today
    hfiles = load_docs(out, "history")
    hist = {}
    for f in hfiles:
        hist.update(json.load(open(f)).get("h", {}))
    for r in amz:
        h = hist.setdefault(r["id"], [])
        if r["id"] in found:
            point = [today, r["price"], 1]
            if not h or h[-1][1:] != point[1:]:
                if h and h[-1][0] == today:
                    h[-1] = point
                else:
                    h.append(point)
        r["first"] = h[0][0] if h else today
        r["prev"] = h[-2][1] if len(h) > 1 else None

    # thumbnails for new Amazon listings
    tfiles = load_docs(out, "thumbs")
    thumbs = {}
    for f in tfiles:
        thumbs.update(json.load(open(f)).get("t", {}))
    # scraper.py keeps only its own stores' thumbs, so carry Amazon thumbs over from prev/
    prev_thumbs = {}
    for f in load_docs(prev, "thumbs"):
        prev_thumbs.update(json.load(open(f)).get("t", {}))
    for r in amz:
        if r["t"] not in thumbs and r["t"] in prev_thumbs:
            thumbs[r["t"]] = prev_thumbs[r["t"]]
    try:
        from PIL import Image
    except ImportError:
        Image = None
    for r in amz:
        src = r.pop("img", None)
        if not src or not Image or (thumbs.get(r["t"]) or {}).get("src") == src:
            continue
        try:
            blob = urllib.request.urlopen(urllib.request.Request(src, headers=S.UA), timeout=30).read()
            im = Image.open(io.BytesIO(blob)).convert("RGB")
            im.thumbnail((88, 88))
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=55)
            thumbs[r["t"]] = {"src": src, "d": "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()}
        except Exception as e:  # noqa
            print("amazon thumb fail", r["t"], e, file=sys.stderr)

    # rewrite the out/ files
    def chunks(items, maxbytes=140_000):
        cur, size = [], 0
        for it in items:
            b = len(json.dumps(it))
            if cur and size + b > maxbytes:
                yield cur
                cur, size = [], 0
            cur.append(it)
            size += b
        if cur:
            yield cur
    all_rows = rows + amz
    all_rows.sort(key=lambda r: (r["store"], r["name"], S.SIZE_ORDER.index(r["size"]) if r["size"] in S.SIZE_ORDER else 99, r["pkg"]))
    for f in load_docs(out, "catalog") + hfiles + tfiles:
        os.remove(f)
    counts = {}
    for kind, items, wrap in (("catalog", all_rows, lambda c: {"rows": c, "date": today}),
                              ("history", list(hist.items()), lambda c: {"h": dict(c)}),
                              ("thumbs", list(thumbs.items()), lambda c: {"t": dict(c)})):
        n = 0
        for i, c in enumerate(chunks(items)):
            json.dump(wrap(c), open(os.path.join(out, f"{kind}-{i}.json"), "w"), separators=(",", ":"))
            n += 1
        counts[kind] = n
    meta_f = os.path.join(out, "meta.json")
    meta = json.load(open(meta_f))
    status.update({"rows": len(amz), "fresh": len(found), "carried": len(carried)})
    meta.setdefault("stores", {})["Amazon"] = status
    meta["amazon"] = st
    meta["rows"] = len(all_rows)
    meta["catalogDocs"], meta["historyDocs"], meta["thumbDocs"] = counts["catalog"], counts["history"], counts["thumbs"]
    json.dump(meta, open(meta_f, "w"), indent=1)
    print(json.dumps({"searches": status.get("searches", 0), "fresh": len(found), "carried": len(carried),
                      "credits_used_this_month": st["used"], "budget": MONTHLY_BUDGET, "errors": errors[:5]}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
