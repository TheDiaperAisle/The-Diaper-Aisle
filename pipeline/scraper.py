#!/usr/bin/env python3
"""Dip Aisle market tracker scraper.

Pulls the public Shopify product feed (/products.json) from each store,
keeps adult disposable diapers (tab briefs + pull-ups), and normalises each
product x size x package into one row.

Usage:  python3 scraper.py OUT_DIR [PREV_HISTORY_DIR]
Writes OUT_DIR/catalog-*.json (db docs, each <200 KB), OUT_DIR/history-*.json,
OUT_DIR/meta.json and OUT_DIR/rows.csv.
"""
import json, re, html, sys, os, time, csv, urllib.request, urllib.error, urllib.parse, datetime, io, base64

STORES = [
    ("Healthwick", "https://healthwick.ca"),
    ("ABUniverse", "https://ca.abuniverse.com"),
    ("MyDips", "https://mydips.ca"),
    ("AgeComfort", "https://agecomfort.com"),
    # Rearz Canada is a BigCommerce store (rearz.ca redirects to ca.rearz.ca, which serves CAD prices to any
    # location). It has no /products.json, so it is read from its sitemap, product pages and option-price lookups.
    ("Rearz", "https://ca.rearz.ca"),
]
VIA = {"Rearz": "bigcommerce"}
UA = {"User-Agent": "Mozilla/5.0 (DipAisleTracker; price research)"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError(f"store redirects this server's location to {newurl.split('/products')[0]} (geo-redirect)")


_opener = urllib.request.build_opener(_NoRedirect)


def _get(url, timeout=60):
    """GET a store URL (no redirects followed) and return the body as text."""
    req = urllib.request.Request(url, headers=UA)
    try:
        with _opener.open(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError, OSError) as e:
        host = url.split("/")[2]
        raise RuntimeError(f"cannot reach {host} ({getattr(e, 'reason', e)}); is it on the allowed-domains list?")


# ---------- BigCommerce (Rearz Canada) ----------
BC_KEEP = re.compile(r"diaper|brief|booster|underwear|bedry|tena|pull", re.I)
BC_SKIP = re.compile(r"cloth|wrap|cover|pocket|bib|pins|pail|change-?pad|bed-pad|swim|prefold|fitted|bamboo|mixed|"
                     r"stack|weekend|try-them|silence|latex|containment|seat|insert|liner|cream|powder|spray|wipe|"
                     r"sticker|frontals|deodori|laundry|pouch|clip|sleep-aid|training-pants", re.I)


def _bc_pkg(v):
    """'Bag (12)' -> 'Bag of 12', 'Sample (2)'/'Trial (3)' -> 'Sample pack of 2' (wording the row parser understands)."""
    m = re.match(r"\s*(sample|trial|bag|case|pack|box)\s*\((\d+)\)\s*$", v, re.I)
    if not m:
        return v
    k, n = m.group(1).lower(), m.group(2)
    return f"Sample pack of {n}" if k in ("sample", "trial") else f"{k.title()} of {n}"


def bc_product_urls(base):
    idx = _get(f"{base}/xmlsitemap.php")
    maps = [html.unescape(u) for u in re.findall(r"<loc>([^<]*type=products[^<]*)</loc>", idx)] or \
           [f"{base}/xmlsitemap.php?type=products&page=1"]
    urls = []
    for m in maps:
        urls += [u.strip() for u in re.findall(r"<loc>([^<]+)</loc>", _get(m))]
    keep = []
    for u in dict.fromkeys(urls):
        slug = u.rstrip("/").rsplit("/", 1)[-1]
        if BC_KEEP.search(slug) and not BC_SKIP.search(slug):
            keep.append(u)
    return keep


def bc_parse_page(raw, url):
    """Product page HTML -> (product id, title, crumbs, description, image, [(option id, name, [(value id, label)])], BCData)."""
    head = raw[:raw.find("</head>")] if "</head>" in raw else raw[:200000]
    prod_ld = {}
    crumbs = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', raw, re.S):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if d.get("@type") == "Product":
            prod_ld = d
        elif d.get("@type") == "BreadcrumbList":
            crumbs = [(e.get("item") or {}).get("name") or e.get("name") for e in d.get("itemListElement", [])]
    title = prod_ld.get("name") or (re.search(r'<meta property="og:title" content="([^"]+)"', head) or [None, ""])[1]
    title = html.unescape(title).strip()
    pid = re.search(r"/products/(\d+)/", head) or re.search(r'data-product-id="(\d+)"', raw)
    if not pid or not title:
        raise RuntimeError(f"unrecognised product page {url}")
    img = prod_ld.get("image")
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = img.get("url")
    if not img:
        mi = re.search(r'<meta property="og:image" content="([^"]+)"', head)
        img = mi.group(1) if mi else None
    if img:
        img = re.sub(r"/stencil/[^/]+/", "/stencil/160w/", html.unescape(img))
    options = []
    fields = list(re.finditer(r'<div class="form-field"[^>]*data-product-option-id="(\d+)"', raw))
    for i, fm in enumerate(fields):
        end = fields[i + 1].start() if i + 1 < len(fields) else fm.end() + 8000
        seg = raw[fm.end():min(end, fm.end() + 8000)]
        lab = re.search(r'<label class="form-label[^>]*>\s*([^<]+?)\s*<', seg)
        vals = re.findall(r'<input[^>]*value="(\d+)"[^>]*data-title="([^"]*)"', seg) or \
            re.findall(r'<option[^>]*value="(\d+)"[^>]*>\s*([^<]+?)\s*</option>', seg)
        vals = [(a, html.unescape(b).strip()) for a, b in vals if a]
        if vals:
            options.append((fm.group(1), lab.group(1).strip() if lab else "Option", vals))
    bc = {}
    i = raw.find("var BCData = ")
    if i >= 0:
        try:
            bc, _ = json.JSONDecoder().raw_decode(raw[i + len("var BCData = "):])
        except ValueError:
            bc = {}
    desc = html.unescape(prod_ld.get("description") or "")
    return pid.group(1), title, crumbs, desc, img, options, bc.get("product_attributes") or {}


def fetch_bigcommerce(base, delay=0.25):
    """Read every disposable product on a BigCommerce store into Shopify-shaped product dicts."""
    import itertools
    out = []
    for url in bc_product_urls(base):
        try:
            raw = _get(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        pid, title, crumbs, desc, img, options, pa = bc_parse_page(raw, url)
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        variants = []
        if not options:
            pr = ((pa.get("price") or {}).get("without_tax") or {}).get("value")
            if pr:
                variants.append({"id": pid, "price": str(pr), "available": bool(pa.get("instock") and pa.get("purchasable", True))})
        for combo in itertools.product(*[vals for _, _, vals in options]):
            q = "&".join(f"attribute[{oid}]={vid}" for (oid, _, _), (vid, _) in zip(options, combo))
            try:
                d = json.loads(_get(f"{base}/remote/v1/product-attributes/{pid}?{q}", timeout=30)).get("data") or {}
            except Exception as e:  # noqa
                print("rearz lookup fail", slug, q, e, file=sys.stderr)
                continue
            pr = ((d.get("price") or {}).get("without_tax") or {}).get("value")
            time.sleep(delay)
            if not pr:
                continue
            v = {"id": d.get("variantId") or "-".join(c[0] for c in combo), "price": str(pr),
                 "available": bool(d.get("instock") and d.get("purchasable", True))}
            for k, (oid, name, _), (vid, label) in zip((1, 2, 3), options, combo):
                v[f"option{k}"] = re.sub(r'\s*\([^)]*["”][^)]*\)\s*$', "", label) if SIZE_OPT.search(name) else _bc_pkg(label)
            variants.append(v)
        if options and not variants:
            raise RuntimeError(f"no option prices returned for {url}")
        out.append({
            "title": title, "handle": slug, "vendor": "Rearz", "tags": [],
            "product_type": crumbs[-2] if len(crumbs) >= 2 else "", "body_html": desc,
            "images": [{"src": img}] if img else [],
            "options": [{"name": n, "values": [_bc_pkg(l) for _, l in vals]} for _, n, vals in options[:3]],
            "variants": variants, "_url": url,
        })
        time.sleep(delay)
    if not out:
        raise RuntimeError("no products found in the store sitemap")
    return out


def fetch_store(base, via=None):
    if via == "bigcommerce":
        return fetch_bigcommerce(base)
    out, page = [], 1
    while page < 40:
        req = urllib.request.Request(f"{base}/products.json?limit=250&page={page}", headers=UA)
        with _opener.open(req, timeout=60) as r:
            d = json.load(r)["products"]
        if not d:
            break
        out += d
        page += 1
        time.sleep(1)
    return out


def text(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


# ---------- classification ----------
EXCLUDE = re.compile(r"\b(pad|pads|underpad|booster|liner|washable|reusable|bodysuit|onesie|jogging|"
                     r"training pants?|cover|covers|pail|refill|cream|bag of bags|diaper bags|bottle|pacifier|"
                     r"bib|socks?|bath|mat|strips|panty|carole martin|beanie|gift card|swim|t-?shirt|sticker|exercise|pulley|stuffer|insert|mattress)\b", re.I)
DIAPER_WORD = re.compile(r"diaper|brief|pull[- ]?(up|on)s?|protective underwear|absorbent underwear|"
                         r"disposable underwear|couche|tena slip|slip (?:brief|active|maxi|super|plus|junior)|breezers", re.I)


BOOSTER = re.compile(r"booster|doubler|power ?ups", re.I)


# promos and mixed bags that are not one product (e.g. MyDips 'Free samples Unlocked!' = lucky-dip sample bag)
PROMO = re.compile(r"free samples?|unlocked|lucky[- ]dip|mystery|grab bag", re.I)


def category(store, p):
    """'booster', 'pullup', 'diaper' (tab-style brief) or None."""
    t, pt = p["title"], (p.get("product_type") or "")
    if PROMO.search(t) or PROMO.search(p.get("handle") or ""):
        return None
    # cloth training pants sold under 'Brief' titles (MyDips 'Kiddo Brief Dino', 'Jungle circus') carry this tag
    if any(re.fullmatch(r"\s*training[- ]pants?\s*", str(g), re.I) for g in (p.get("tags") or [])):
        return None
    if BOOSTER.search(t) or pt in ("Booster Pads", "Boosters"):
        if re.search(r"choose for me|holder|pant\b|washable|reusable", t, re.I):
            return None
        return "booster"
    if not is_diaper(store, p):
        return None
    return "pullup" if style_of(p) == "Pull-up" else "diaper"


def is_diaper(store, p):
    t, pt = p["title"], (p.get("product_type") or "")
    if EXCLUDE.search(t):
        return False
    if store == "Healthwick":
        return pt in ("Adult Diapers", "ABDL", "Absorbent Underwear")
    if store == "ABUniverse":
        return pt == "Diapers"
    if store == "AgeComfort" and re.search(r"\bcloth\b", t, re.I):
        return False
    return bool(DIAPER_WORD.search(t) or re.search(r"diaper|couche", pt, re.I))


def style_of(p):
    s = p["title"] + " " + (p.get("product_type") or "")
    return "Pull-up" if re.search(r"pull|underwear|pants?\b", s, re.I) else "Brief"


# ---------- size ----------
SIZE_PATTERNS = [
    (r"\b(xx-?small|xxs)\b", "XXS"), (r"\b(x-?small|xs)\b", "XS"),
    (r"\b(s\s*/\s*m|small\s*/\s*medium)\b", "S/M"), (r"\b(m\s*/\s*l|medium\s*/\s*large)\b", "M/L"),
    (r"\b(l\s*/\s*xl)\b", "L/XL"),
    (r"\b(4xl|xxxx-?large)\b", "4XL"), (r"\b(3xl|xxx-?large)\b", "3XL"),
    (r"\b(2xl|xxl|xx-?large|2x-?large|x-?large\s*\+|xlarge\+|xl\+|bariatric)", "XXL"),
    (r"\b(xl|x-?large|extra\s*large)\b", "XL"),
    (r"\b(regular|r)\b", "Regular"), (r"\b(small|s)\b", "S"), (r"\b(medium|m)\b", "M"), (r"\b(large|l)\b", "L"),
]
SIZE_ORDER = ["XXS", "XS", "S", "S/M", "M", "M/L", "L", "L/XL", "Regular", "XL", "XXL", "3XL", "4XL", "One size"]


def size_of(s):
    for pat, lab in SIZE_PATTERNS:
        if re.search(pat, s, re.I):
            return lab
    return None


# ---------- package / quantity ----------
def pkg_of(s, title):
    s2 = (s + " " + title).lower()
    if "sample" in s2 or "trial" in s2:
        return "Sample"
    # 'Bag (10)' is one bag; only plural 'Bags (40)' / '3 Bags (36)' mean a multi-bag case
    if re.search(r"\bcase\b|\bbox\b|\bbags\s*\(\d+\)|4 bags|\d+\s*(?:bags|sacs)", s.lower()) and not re.search(r"\b1 bag", s.lower()):
        return "Case"
    return "Bag"


QTY_PATTERNS = [
    r"(?:bag|case|pack|box|package|pkg)\s*(?:of|-)?\s*(\d+)",
    r"(\d+)\s*(?:diapers|briefs|boosters|pads|units?|ct|count|pcs|pieces|per\s*(?:bag|pack|case))",
    r"\((\d+)\)",
    r"(\d+)\s*-?\s*pack",
]


def qty_from_variant(s):
    for pat in QTY_PATTERNS:
        m = re.search(pat, s, re.I)
        if m and 0 < int(m.group(1)) <= 400:
            return int(m.group(1))
    return None


SIZE_TOKEN = re.compile(r"(?<![\w/])(XXS|XS|S/M|M/L|L/XL|L/2XL|XXL|2XL|2X|3XL|XL|Small|Medium|Large|X-Large|Extra Large|Regular|R|S|M|L)(?![\w/])")
PER_PKG = re.compile(r"(\d+)\s*(?:units?|ct|briefs|diapers|boosters|pads|pcs|pieces)?\s*(?:/|per)\s*(?:pkg|package|bag|pack)\b", re.I)


def qty_table(desc):
    """Map size -> (per_package, per_case) from description text."""
    table = {}
    for m in PER_PKG.finditer(desc):
        per = int(m.group(1))
        back = desc[max(0, m.start() - 140):m.start()]
        toks = [t for t in SIZE_TOKEN.findall(back)]
        lab = None
        if toks:
            t = toks[-1]
            lab = size_of("XXL" if t == "2X" else t) or t
        fwd = desc[m.end():m.end() + 70]
        case = None
        mc = re.match(r"\s*[-–,]?\s*(\d+)\s*(?:pkgs?|bags?|packs?)\s*(?:/|per)\s*case", fwd, re.I)
        if mc:
            case = per * int(mc.group(1))
        mt = re.match(r"[^()]{0,40}\((\d+)(?:\s*total)?\)", fwd)
        if mt and (case is None or int(mt.group(1)) == case):
            case = int(mt.group(1))
        mc2 = re.match(r"\s*[-–,]?\s*(\d+)\s*/\s*case", fwd, re.I)
        if mc2:
            case = int(mc2.group(1))
        key = lab or "*"
        if key not in table:
            table[key] = (per, case)
    # spec tables like 'Medium (30" - 40") 12 in a bag 36 in a case' (AgeComfort)
    for m in re.finditer(r"(\d+)\s*(?:in a|per)\s*(?:bag|pack|package)\b[\s,;-]*(?:(\d+)\s*(?:in a|per)\s*case\b)?", desc, re.I):
        toks = SIZE_TOKEN.findall(desc[max(0, m.start() - 60):m.start()])
        key = (size_of("XXL" if toks[-1] == "2X" else toks[-1]) or toks[-1]) if toks else "*"
        if key not in table:
            table[key] = (int(m.group(1)), int(m.group(2)) if m.group(2) else None)
    if "*" not in table and table:
        vals = set(table.values())
        if len(vals) == 1:
            table["*"] = vals.pop()
    m = re.search(r"units? per (?:pack|bag|package)\s*:?\s*(\d+)", desc, re.I) or \
        re.search(r"(?:pack|bag|package) of (\d+)", desc, re.I)
    if "*" not in table and m:
        mcase = re.search(r"case is composed of (\d+) (?:packs|bags)", desc, re.I)
        table["*"] = (int(m.group(1)), int(m.group(1)) * int(mcase.group(1)) if mcase else None)
    # prose: 'Each package contains 21 briefs, with three packages per case'
    m = re.search(r"(?:each|per|one) (?:package|pack|bag) (?:contains|holds|has|of) (\d+)", desc, re.I)
    if "*" not in table and m:
        words = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "eight": 8}
        mc = re.search(r"(\d+|two|three|four|five|six|eight) (?:packages|packs|bags) (?:per|in a|to a) case", desc, re.I)
        n = (int(mc.group(1)) if mc.group(1).isdigit() else words[mc.group(1).lower()]) if mc else None
        table["*"] = (int(m.group(1)), int(m.group(1)) * n if n else None)
    m = re.search(r"sample (?:pack|bag)? ?contains (\d+)", desc, re.I)
    if m:
        table["sample"] = (int(m.group(1)), None)
    return table


# ---------- absorbency ----------
def capacity_ml(desc, lo=1000, hi=20000):
    vals = []
    # '11,500 ml', '11 500 ml', '1.200ml'
    for raw in re.findall(r"(\d{1,2}[,\. ]\d{3}|\d{3,5})\s*(?:ml|mL|ML|millilit)", desc):
        vals.append(int(re.sub(r"[,\. ]", "", raw)))
    # spec tables with the unit in the label: 'Absorption (ml) 11500', 'Capacity (mL): 4,400'
    for raw in re.findall(r"(?:absor\w*|capacity)\s*\(\s*ml\s*\)\s*:?\s*(\d{1,2}[,\. ]?\d{3}|\d{3,5})\b", desc, re.I):
        vals.append(int(re.sub(r"[,\. ]", "", raw)))
    vals = [v for v in vals if lo <= v <= hi]
    if vals:  # an explicit mL figure wins; litre mentions are often marketing ('13.5 litre experience' with a booster)
        return max(vals)
    # litres: '11 ½ liters', '4.4 litres', '4,4L', '12L' (a spaced 'L' only before 'capacity'/'absorb…', so sizes like '2 L' are ignored)
    for whole, frac, half in re.findall(r"(\d{1,2})(?:[.,](\d{1,3}))?\s*(½)?\s*(?:lit(?:re|er)s?\b)", desc, re.I) + \
            re.findall(r"(\d{1,2})[.,](\d{1,3})()\s*L\b", desc) + \
            re.findall(r"(\d{1,2})()()(?:L(?![\w/])|\s+L(?=\s+(?:capacity|absorb)))", desc):  # '12L capacity'
        vals.append(int(round((int(whole) + (float("0." + frac) if frac else 0) + (0.5 if half else 0)) * 1000)))
    vals = [v for v in vals if lo <= v <= hi]
    return max(vals) if vals else None


ABS_RANK = {"Light": 1, "Moderate": 2, "Heavy": 3, "Maximum": 4}


def absorbency_cat(p, desc):
    found = []
    for t in p.get("tags", []):
        m = re.match(r"Absorbency_(\w+)", t)
        if m and m.group(1).capitalize() in ABS_RANK:
            found.append(m.group(1).capitalize())
    if not found:
        m = re.search(r"absorbency\s*[:\-]?\s*(light|moderate|heavy|maximum|ultimate|super|extra)", desc, re.I) or \
            re.search(r"\b(maximum|ultimate|heavy|moderate|light)\s+absorb", desc + " " + p["title"], re.I)
        if m:
            w = m.group(1).capitalize()
            found.append({"Ultimate": "Maximum", "Super": "Heavy", "Extra": "Heavy"}.get(w, w))
    return max(found, key=ABS_RANK.get) if found else None


BRANDS = [  # canonical name, regex matched at the start of the title (after an optional "SAMPLE")
    ("ABUniverse", r"abu(?:niverse)?\b"), ("Abena", r"abena\b|abri[- ]?(?:form|flex|let|san)"),
    ("AMG", r"amg\b"), ("Attends", r"attends\b"), ("Because", r"because(?: market)?\b"),
    ("BetterDry", r"better ?dry\b"), ("Comfees", r"comfees\b"), ("Comfykinz", r"comfykinz\b"),
    ("Covidien", r"covidien\b"), ("Crinklz", r"crinklz\b"), ("Depend", r"depend\b"),
    ("FitRight", r"fit ?right\b"), ("Forsite Health", r"forsite(?: health)?\b"),
    ("InControl", r"in ?control\b"), ("Kiddo", r"kiddo\b"), ("Lille", r"lille\b"),
    ("Little for Big", r"lfb\b|little for big\b"), ("LNGU", r"lngu\b"), ("MoliCare", r"molicare\b"),
    ("Nateen", r"nateen\b"), ("NorthShore", r"northshore\b"), ("Prevail", r"prevail\b"),
    ("Rearz", r"rearz\b"), ("TENA", r"tena\b"), ("Threaded Armor", r"threaded armou?r\b"),
    ("Tranquility", r"tranquility\b"), ("Trest", r"trest\b"), ("Tykables", r"tykables\b"),
    ("Cuddlz", r"cuddlz\b"), ("Seni", r"seni\b"), ("Dry 24/7", r"dry ?24/?7"),
]
BRAND_STRIP = {"Abena": r"abena\b"}  # brand words to strip from the product name when narrower than detection
VENDOR_ALIAS = {re.sub(r"\W", "", c.lower()): c for c, _ in BRANDS}
VENDOR_ALIAS.update({"forsite": "Forsite Health", "forsitehealth": "Forsite Health", "fitright": "FitRight",
                     "incontrolbedry": "InControl", "becausemarket": "Because", "threadedarmour": "Threaded Armor",
                     "betterdry": "BetterDry", "lfb": "Little for Big"})
RETAILERS = {"", "none", "healthwickcanada", "healthwick", "mydips", "abuniversecanada", "agecomfort"}


def brand_of(store, p):
    t = re.sub(r"^\s*sample\s+", "", p["title"], flags=re.I)
    for canon, pat in BRANDS:
        if re.match(pat, t, re.I):
            return canon
    v = re.sub(r"\W", "", (p.get("vendor") or "").lower())
    if v in VENDOR_ALIAS:
        return VENDOR_ALIAS[v]
    if v in RETAILERS:
        if store == "ABUniverse":
            return "ABUniverse"
        return "Kiddo" if store == "MyDips" and "kiddo" in t.lower() else (p.get("vendor") or "").strip() or store
    vv = (p.get("vendor") or "").strip()
    return vv.title() if vv.isupper() else vv


COLOURS = r"(white|pink|blue|black|purple|green|yellow|beige|grey|gray|red|orange|tie[- ]dye|clear|natural)"
GENERIC_TAIL = r"(\s*[-–]?\s*(adult|incontinence|disposable|tab[- ]style|tabbed|premium)?\s*(diapers?|briefs?|couches?))+\s*$"
JUNK = [r"\b(?:by|per) (?:case|bag|pack)\b", r"\b[A-Z]{1,4}\d{3,}[A-Z0-9]*\b", r"\b(?:X{0,3}[SML]|XL|XXL|X{1,3}S)\d\b", r"\bEXTE\b",
        r"\b(?:x-?small|small|medium|large|x-?large|xx-?large|2xl|3xl|xl|xs)\b(?=[^a-z]*$)",
        r"\b(\d+(?:\.\d+)?\s*[\"”]?\s*x\s*\d+(?:\.\d+)?\s*[\"”]?)", r"\b\d{2,4}\s*ml\b",
        r"\s*-\s*(absorbency booster pads)$"]
CASE_MAP = {}  # lowercased word -> preferred casing, learned from mixed-case titles


def learn_casing(products_by_store):
    from collections import Counter
    seen = {}
    for prods in products_by_store.values():
        for p in prods:
            t = p["title"]
            if t.isupper():
                continue
            for w in re.findall(r"[A-Za-z][A-Za-z'’:\-]+", t):
                seen.setdefault(w.lower(), Counter())[w] += 1
    for k, c in seen.items():
        CASE_MAP[k] = c.most_common(1)[0][0]
    CASE_MAP.update({"am": "AM", "pm": "PM", "megamax": "MegaMax", "xl": "XL", "usa": "USA", "abu": "ABU"})


FORCE_CASE = {"megamax": "MegaMax", "airlock": "AirLock", "abdry": "ABDry"}


def smart_case(s):
    s = re.sub(r"[A-Za-z]+", lambda m: FORCE_CASE.get(m.group(0).lower(), m.group(0)), s)
    if not s.isupper() and not s.islower():
        return s
    def fix(m):
        w = m.group(0)
        return CASE_MAP.get(w.lower(), w.capitalize())
    return re.sub(r"[A-Za-z][A-Za-z'’\-]*", fix, s)


def split_title(store, p, brand):
    """-> (line name without brand, colour variant found in the title or None)"""
    t = re.sub(r"[™®©]", "", p["title"]).strip()
    t = re.sub(r"^\s*sample\s+", "", t, flags=re.I)
    t = re.sub(r"\s+sample\s*(pack)?\s*$", "", t, flags=re.I)
    t = re.sub(r"\bmedline\s+", "", t, flags=re.I)
    for canon, pat in BRANDS:
        if canon == brand:
            pat = BRAND_STRIP.get(canon, pat)
            t = re.sub(r"^(" + pat + r")\s*[-–:]?\s*", "", t, flags=re.I)
    if brand == "Forsite Health":
        t = re.sub(r"^health\s+", "", t, flags=re.I)
    t = re.sub(r"^(" + BRAND_STRIP.get(brand, dict(BRANDS).get(brand, "$^")) + r")\s+", "", t, flags=re.I)  # brand repeated mid-title
    colour = None
    ms = re.search(r"\s*[-–(]\s*((?:un)?scented)\)?\s*$", t, re.I)
    if ms:
        colour = ms.group(1).title()
        t = t[:ms.start()]
    m = re.search(r"\s+" + COLOURS + r"\s*$", t, re.I)
    if m and len(t[:m.start()].split()) >= 1:
        colour = norm_variant(m.group(1).title())
        t = t[:m.start()]
    for j in JUNK:
        t = re.sub(j, " ", t, flags=re.I)
    t = re.sub(GENERIC_TAIL, "", t, flags=re.I)
    t2 = re.sub(r"\b(adult\s+)?(diapers?|briefs?)\b", " ", t, flags=re.I)
    if re.search(r"[A-Za-z]{3}", t2):
        t = t2
    t = re.sub(r"^\s*[-–:]\s*|\s*[-–:]\s*$", "", re.sub(r"\s+", " ", t)).strip()
    t = smart_case(t) if t else ""
    if not re.sub(r"\b(adult|incontinence|disposable|protective|diapers?|briefs?|underwear|pull[- ]?(?:ups?|ons?)|pants?)\b|\W", "", t, flags=re.I):
        # nothing but generic words left (e.g. 'BetterDry Adult Diapers'): show the store's own title rather than 'Briefs'
        full = re.sub(r"\s+sample\s*(pack)?\s*$|^\s*sample\s+", "", re.sub(r"[™®©]", "", p["title"]), flags=re.I).strip()
        if colour:
            full = re.sub(r"\s*[-–(]?\s*" + re.escape(colour) + r"\)?\s*$", "", full, flags=re.I).strip()
        for j in JUNK:
            full = re.sub(j, " ", full, flags=re.I)
        t = smart_case(re.sub(r"\s+", " ", full).strip())
    return t, colour


STOP = {"boosterpads", "medline", "adult", "diaper", "diapers", "brief", "briefs", "incontinence", "the", "tab", "style", "tabbed",
        "disposable", "proskin", "pads", "pad", "booster", "boosters", "booster-pads", "protective", "a", "for",
        "with", "of", "new", "sizing", "version", "edition", "absorbent", "absorbency"}
NORM = {"maximum": "max", "maxi": "max", "pullups": "pull", "pull-ups": "pull", "pull-up": "pull", "pull": "pull",
        "ups": "", "underwear": "underwear", "overnights": "overnight", "nights": "night", "lil'": "lil", "li'l": "lil",
        "toplinera": "topliner", "top": "top", "liner": "liner", "abriflex": "abri-flex", "abri": "abri"}


def product_key(brand, line, cat):
    low = line.lower()
    if low.startswith(brand.lower() + " "):  # fallback names keep the brand ('BetterDry Adult Diapers'); key without it
        low = low[len(brand) + 1:]
    toks = re.findall(r"[a-z0-9']+", low.replace("’", "'").replace("abriflex", "abri flex"))
    if cat == "pullup":
        toks = [w for w in toks if w not in ("pull", "pulls", "ups", "up", "underwear", "pants", "pant", "on")]
    out = set()
    for w in toks:
        w = NORM.get(w, w)
        if w and w not in STOP:
            out.add(w)
    # 'top liner' == 'topliner'
    if {"top", "liner"} <= out:
        out -= {"top", "liner"}; out.add("topliner")
    key = f"{cat}|{brand.lower()}|{' '.join(sorted(out))}"
    return KEY_ALIAS.get(key, key)


# Hand-checked merges for listings that name the same product differently at different stores.
KEY_ALIAS = {
    "diaper|forsite health|hereos lil": "diaper|forsite health|heroes lil",
    "diaper|forsite health|jane mary max": "diaper|forsite health|jane mary",
    "diaper|forsite health|jane mary printed": "diaper|forsite health|jane mary",
    "diaper|forsite health|max sea under": "diaper|forsite health|sea under",
    "diaper|forsite health|am pm stripes": "diaper|forsite health|am max pm stripes",
    "diaper|rearz|alpaca": "diaper|rearz|alpaca overnight",
    "diaper|rearz|dinosaur": "diaper|rearz|dinosaur elite",
    "diaper|rearz|dinosaur mega": "diaper|rearz|dinosaur elite",   # Rearz 'Mega Dinosaur' = 'Dinosaur (Elite)', owner 2026-10-28
    "diaper|tena|bariatric": "diaper|tena|bariatric stretch super",
    "pullup|abena|abri flex": "pullup|abena|abri flex premium",
    "booster|rearz|overnight scented": "booster|rearz|overnight",
    "booster|tranquility|boosterpads plus super topliner": "booster|tranquility|plus super topliner",
    "booster|tranquility|contour plus super topliner": "booster|tranquility|plus super topliner",
    # Abena Abri-Form Comfort M4/L4/XL4 (owner 2026-10-31): AgeComfort still sells it as 'Abri Form Original
    # X Plus' (M 14 / L 12, the M4/L4 pack counts) and 'Abri-Form Premium XL4' (the old names)
    "diaper|abena|abri form original plus x": "diaper|abena|abri comfort form",
    "diaper|abena|abri form premium": "diaper|abena|abri comfort form",
    "diaper|abena|abri form": "diaper|abena|abri comfort form",   # Amazon 'Abri-Form Premium XL4'
    "diaper|abena|abri comfort foil form white": "diaper|abena|abri comfort form",   # Healthwick 'White Foil Comfort', same product (owner 2026-10-31)
}

# Display names for merged products whose store names differ (old vs current maker name). Keyed by pid.
LINE_NAME = {
    "diaper|abena|abri comfort form": "Abri-Form Comfort",
}


# ---------- Abena size + level codes ----------
# Abena names its products by size letter + absorbency level: 'Slip Premium M4', 'Pants L3', 'Flexi-Fit M-L3'
# (owner 2026-10-31). Stores write 'Slip Premium Briefs - Level 4' with the size as an option, or the old
# names ('X Plus' = level 4). The pid stays the same; only the display name ('line') gets the code.
ABENA_CODE = re.compile(r"\b(XXS|XS|S|M|L|XL|XXL|S-M|M-L|L-XL)([0-4])\b", re.I)
ABENA_CODE_SIZE = {"S-M": "S/M", "M-L": "M/L", "L-XL": "L/XL"}


def is_abena(r):
    return (r.get("brand") or "").lower() == "abena"


def abena_level(r):
    for text in (r.get("line") or "", r.get("name") or ""):
        m = re.search(r"\blevel\s*(\d)\b", text, re.I)
        if m:
            return m.group(1)
    m = ABENA_CODE.search(r.get("name") or "")
    if m:
        return m.group(2)
    if r.get("pid") == "diaper|abena|abri comfort form":
        return "4"   # every store listing of this merged product is level 4 ('X Plus' = old name; owner 2026-10-31)
    return None


def abena_fix_size(r):
    """'Abri-Flex ... XS1' / 'Abri-Form Premium XL4' with no size option: take the size from the code. Rebuilds the id."""
    if not is_abena(r) or r["size"] != "One size":
        return r
    m = ABENA_CODE.search(r.get("name") or "")
    if m:
        code = m.group(1).upper()
        r["size"] = ABENA_CODE_SIZE.get(code, code)
        parts = r["id"].split("|")
        parts[2] = r["size"]
        r["id"] = "|".join(parts)
    return r


def abena_names(rows):
    for r in rows:
        if not is_abena(r) or not r.get("line"):
            continue
        lvl = abena_level(r)
        base = r["line"]
        while base.lower().startswith("abena "):
            base = base[6:]
        base = re.sub(r"\s*-\s*level\s*\d\b", "", base, flags=re.I)
        base = ABENA_CODE.sub("", base)
        base = re.sub(r"\s{2,}", " ", base).strip(" -")
        code = r["size"].replace("/", "-") if r["size"] not in ("One size", "Regular") else None
        if lvl and code:
            r["line"] = f"{base} {code}{lvl}"
        elif lvl:
            r["line"] = f"{base} - Level {lvl}"
        else:
            r["line"] = base
    return rows


# Hand-checked capacities (mL) for products whose pages state it only in an image. Used only when no
# store's text gives a figure. Keyed by pid.
CAP_MANUAL = {
    "diaper|rearz|mega safari": 11000,   # Rearz product image, confirmed by the owner 2026-10-28
    "diaper|rearz|bella daytime lil": 6000,   # Lil Bella Daytime, Rearz product image, owner 2026-10-28
}


def thumb(src):
    if not src:
        return None
    return src + ("&" if "?" in src else "?") + "width=160"


SIZE_OPT = re.compile(r"size|taille|grandeur", re.I)
PKG_OPT = re.compile(r"option|type|case|quantit|pack|format|qty|count|amount", re.I)
VAR_OPT = re.compile(r"colou?r|couleur|scent|parfum|print|design|pattern|style|tape|strip|edition|theme", re.I)


def option_roles(p):
    roles = []
    for o in p.get("options", []):
        n, vals = o.get("name", ""), o.get("values", [])
        if re.search(r"size\s*(and|&)\s*quantit", n, re.I):
            roles.append("sizepkg")
        elif VAR_OPT.search(n):
            roles.append("variant")
        elif SIZE_OPT.search(n):
            roles.append("size")
        elif PKG_OPT.search(n) and n.lower() != "title":
            roles.append("pkg")
        else:  # decide from the values
            if vals and sum(1 for v in vals if size_of(v) and len(v) <= 14) >= len(vals) * 0.6:
                roles.append("size")
            elif any(re.search(r"pack|bag|case|sample|each|package|\d", v, re.I) for v in vals):
                roles.append("pkg")
            elif vals == ["Default Title"]:
                roles.append("none")
            else:
                roles.append("variant")
    return roles


def norm_variant(v):
    v = v.strip()
    if re.fullmatch(r"(no|not|non|un)[- ]?scent(ed)?|no scent strips?|unscented", v, re.I):
        return "Unscented"
    if re.fullmatch(r"scent(ed)?|with scent( strips?)?", v, re.I):
        return "Scented"
    v = re.sub(r"(?i)tie[- ]?dye", "Tie-Dye", v)
    return v.title() if v.isupper() or v.islower() else v


_PAGE_CACHE = {}
_RAW_CACHE = {}


def _page_raw(base, handle, why):
    """Product page HTML (cached; '' when it cannot be read, after logging '<why> fail <url> <error>')."""
    url = f"{base}/products/{urllib.parse.quote(handle)}"
    if url not in _RAW_CACHE:
        try:
            _RAW_CACHE[url] = _get(url, timeout=30)
            time.sleep(0.3)
        except Exception as e:  # noqa
            print(why, "fail", url, e, file=sys.stderr)
            _RAW_CACHE[url] = ""
    return _RAW_CACHE[url]


# Stores whose product pages add multi-pack 'case' choices in the browser (not in /products.json).
# ABUniverse (2026-10-30): a diaper_add_case.js widget offers '4 Packs - 40 Diapers' and '8 Packs - 80 Diapers'
# for the 'Pack - 10 Diapers' variant, priced pack price x 4 / x 8 less the page's discount table
# ('Per group of 4 packs' = 25% off), exactly as the page shows it.
CASE_WIDGET_STORES = {"ABUniverse"}


def case_widget(base, handle):
    """-> (type option name, pack value, [multipliers], [(start, end, price multiplier)]) or None."""
    raw = _page_raw(base, handle, "case options")
    m = re.search(r'<script[^>]*diaper_add_case\.js[^>]*>', raw, re.S)
    if not m:
        return None
    tag = m.group(0)
    def attr(n):
        a = re.search(n + r'="([^"]*)"', tag)
        return urllib.parse.unquote(html.unescape(a.group(1))) if a else ""
    mults = sorted({int(x) for x in re.findall(r'data-quantity-multiplier="(\d+)"', raw)})
    if not mults:
        return None
    discounts = []
    try:
        for d in json.loads(attr("data-discounts-table") or "[]"):
            q = [int(x) for x in re.findall(r"\d+", d.get("quantity", ""))]
            pc = re.match(r"(\d+(?:[.,]\d+)?)%", d.get("amount", ""))
            if q and pc:
                discounts.append((q[0], q[1] if len(q) > 1 else 10 ** 9, 1 - float(pc.group(1).replace(",", ".")) / 100))
    except ValueError:
        pass
    return attr("data-type-option-name") or "Type", attr("data-pack-variant"), mults, discounts


def add_case_variants(base, p):
    """Add the page-only case choices to a product as extra variants ('Case of 40 (4 packs)')."""
    w = case_widget(base, p["handle"])
    if not w:
        return
    tname, pack, mults, discounts = w
    idx = next((i for i, o in enumerate(p.get("options", [])) if o.get("name") == tname), None)
    if idx is None or not pack:
        return
    extra = []
    for v in p["variants"]:
        if v.get(f"option{idx + 1}") != pack:
            continue
        # the case label goes on the option that holds 'Pack - 10 Diapers' (on some pages, e.g. PreSchool, the
        # store's widget is attached to another option such as 'Scent Strips', but it still multiplies the pack)
        pidx = next((i for i in range(3) if re.match(r"\s*pack\b.*?\d", v.get(f"option{i + 1}") or "", re.I)), idx)
        per = qty_from_variant(v.get(f"option{pidx + 1}") or "")
        unit_prices = []
        for n in mults:
            app = [d for s0, e0, d in discounts if s0 <= n <= e0]
            mult = min(app) if app else 1
            price = round(float(v["price"]) * n * mult, 2)
            # a bigger case at the same $/diaper as a smaller one adds nothing (owner 2026-10-30): skip it
            unit = round(price / n, 2)
            if unit in unit_prices:
                continue
            unit_prices.append(unit)
            nv = dict(v, price=f"{price:.2f}")
            nv[f"option{pidx + 1}"] = f"Case of {per * n} ({n} packs)" if per else f"Case ({n} packs)"
            extra.append((pidx, nv))
    p["variants"] = p["variants"] + [nv for _, nv in extra]
    for pidx, v in extra:
        val = v[f"option{pidx + 1}"]
        if pidx < len(p["options"]) and val not in p["options"][pidx]["values"]:
            p["options"][pidx]["values"].append(val)


def page_capacity(base, handle, lo, hi):
    """Some stores (e.g. ABUniverse) keep capacity in a spec table on the product page rather than in the
    description: 'Absorbency *Capacity varies by size 6050ml'. Read the page and accept only an mL figure
    that sits right after 'capacity' or 'absorb…', so related-product blurbs elsewhere on the page are ignored."""
    url = f"{base}/products/{urllib.parse.quote(handle)}"
    if url not in _PAGE_CACHE:
        raw = _page_raw(base, handle, "page capacity")
        _PAGE_CACHE[url] = text(re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S)) if raw else ""
    vals = []
    for raw in re.findall(r"(?:capacity|absorb\w*)[^.!?]{0,40}?(\d{1,2}[,\. ]\d{3}|\d{3,5})\s*ml\b", _PAGE_CACHE[url], re.I):
        v = int(re.sub(r"[,\. ]", "", raw))
        if lo <= v <= hi:
            vals.append(v)
    return max(vals) if vals else None


def parse_store(store, base, products):
    rows = {}
    for p in products:
        cat = category(store, p)
        if not cat:
            continue
        if store in CASE_WIDGET_STORES:
            p = dict(p, options=[dict(o, values=list(o.get("values", []))) for o in p.get("options", [])])
            add_case_variants(base, p)
        desc = text(p.get("body_html"))
        lo_hi = (100, 5000) if cat == "booster" else (1000, 20000)
        cap = capacity_ml(desc, *lo_hi)
        if cap is None and VIA.get(store) is None:
            cap = page_capacity(base, p["handle"], *lo_hi)
        dm = re.search(r"(\d+(?:\.\d+)?)\s*[\"”]\s*x\s*(\d+(?:\.\d+)?)\s*[\"”]", desc)
        dims = f'{dm.group(1)}" x {dm.group(2)}"' if dm else None
        qt = qty_table(desc)
        img = thumb(p["images"][0]["src"]) if p.get("images") else None
        prod_size = size_of(p["title"])  # e.g. 'TENA ProSkin Plus Small Brief'
        brand = brand_of(store, p)
        line, title_var = split_title(store, p, brand)
        roles = option_roles(p)
        for v in p["variants"]:
            price = float(v["price"] or 0)
            if price <= 0:
                continue
            opts = [v.get(f"option{i}") for i in (1, 2, 3)]
            size_s, pkg_s, var_s = [], [], []
            for role, val in zip(roles, opts):
                if not val or val == "Default Title":
                    continue
                if role in ("size", "variant") and re.search(r"\b(bag|case|pack|box|sample|each)\b|\d+\s*-?\s*(pack|bags?|sacs?)", val, re.I):
                    role = "sizepkg" if size_of(val) and role == "size" else "pkg"
                if role == "size":
                    size_s.append(val)
                elif role == "pkg":
                    pkg_s.append(val)
                elif role == "sizepkg":
                    size_s.append(val); pkg_s.append(val)
                elif role == "variant":
                    var_s.append(norm_variant(val))
            vt = " / ".join(x for x in opts if x and x != "Default Title")
            if title_var:
                var_s.insert(0, title_var)
            variant = " · ".join(dict.fromkeys(var_s)) or None
            size = size_of(" ".join(size_s)) or size_of(" ".join(pkg_s)) or prod_size or "One size"
            pkg = pkg_of(" ".join(pkg_s) or vt, p["title"])
            qty = qty_from_variant(" ".join(pkg_s) or vt)
            nb = re.search(r"(\d+)\s*(?:bags?|sacs?)\b", vt, re.I)
            if nb and not re.search(r"\(\d+\)", vt):
                per0 = (qt.get(size) or qt.get("*") or (None,))[0]
                qty = per0 * int(nb.group(1)) if per0 else None
            if qty is None:
                per, tot = qt.get(size) or qt.get("*") or (None, None)
                if pkg == "Sample":
                    qty = (qt.get("sample") or (None,))[0] or qty_from_variant(p["title"]) or None
                elif pkg == "Case":
                    qty = tot
                else:
                    qty = per
                if qty is None and pkg != "Sample":
                    qty = qty_from_variant(p["title"])
                if qty is None and pkg == "Sample" and re.match(r"\s*sample\b", p["title"], re.I) \
                        and not re.search(r"pack|bag|kit", p["title"], re.I):
                    qty = 1  # single-unit samples (e.g. AgeComfort "SAMPLE ..." listings)
            key = f"{store}|{p['handle']}|{size}|{pkg}|{qty}|{variant or '-'}"
            avail = bool(v.get("available"))
            row = rows.get(key)
            if row and not ((avail and not row["avail"]) or (avail == row["avail"] and price < row["price"])):
                continue
            rows[key] = {
                "id": key, "store": store, "name": p["title"].strip(), "brand": brand, "line": line,
                "pid": product_key(brand, line, cat), "variant": variant,
                "cat": cat, "dims": dims if (cat == "booster" and size == "One size") else None,
                "style": style_of(p), "size": size, "pkg": pkg, "qty": qty, "price": price,
                "cap": cap, "avail": avail, "img": img, "t": f"{store}|{p['handle']}",
                "url": p.get("_url") or f"{base}/products/{p['handle']}?variant={v['id']}",
            }
    return list(rows.values())


def harmonise(rows):
    """Make product facts consistent across stores and drop same-store duplicate listings."""
    from collections import Counter, defaultdict
    by = defaultdict(list)
    for r in rows:
        by[r["pid"]].append(r)
    for pid, rs in by.items():
        # display name: prefer names from mixed-case store titles, then most common, then longest
        names = Counter(r["line"] for r in rs if not r["name"].isupper()) or Counter(r["line"] for r in rs)
        line = sorted(names.items(), key=lambda kv: (-kv[1], -len(kv[0])))[0][0]
        line = LINE_NAME.get(pid, line)
        caps = Counter(r["cap"] for r in rs if r["cap"])
        cap = sorted(caps.items(), key=lambda kv: (-kv[1], -kv[0]))[0][0] if caps else None
        manual = CAP_MANUAL.get(pid) if not cap else None  # only when no store states it in text
        dims = Counter(r["dims"] for r in rs if r["dims"])
        for r in rs:
            r["line"] = line
            r["cap_src"] = "store" if r["cap"] == cap and r["cap"] else ("other store" if cap else ("manual" if manual else None))
            r["cap"] = cap or manual
            if r["size"] == "One size" and r["cat"] == "booster" and not r["dims"] and len(dims) == 1:
                r["dims"] = next(iter(dims))
    # same store, same product facts, same price -> keep one listing
    seen, out = {}, []
    for r in rows:
        k = (r["store"], r["pid"], r["size"], r["pkg"], r["qty"], r["variant"], r["dims"], r["price"])
        if k in seen:
            if r["avail"] and not seen[k]["avail"]:
                out[out.index(seen[k])] = r
                seen[k] = r
            continue
        seen[k] = r
        out.append(r)
    abena_names(out)
    for r in out:
        r["ppd"] = round(r["price"] / r["qty"], 3) if r["qty"] else None
        r["ppl"] = round(r["ppd"] / (r["cap"] / 1000), 3) if (r["ppd"] and r["cap"]) else None
        r["ck"] = f"{r['pid']}|{r['size']}|{r['dims'] or ''}"   # compare key: same product + size across stores
    return out


def main():
    out = sys.argv[1]
    prev = sys.argv[2] if len(sys.argv) > 2 else None
    os.makedirs(out, exist_ok=True)
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4))).strftime("%Y-%m-%d")
    all_rows, status = [], {}
    fetched = {}
    for store, base in STORES:
        try:
            fetched[store] = fetch_store(base, VIA.get(store))
        except Exception as e:  # noqa
            status[store] = {"ok": False, "error": str(e)[:200]}
    learn_casing(fetched)
    for store, base in STORES:
        if store not in fetched:
            continue
        try:
            rows = parse_store(store, base, fetched[store])
            all_rows += rows
            status[store] = {"ok": True, "products": len(fetched[store]), "rows": len(rows)}
        except Exception as e:  # noqa
            status[store] = {"ok": False, "error": f"parse error: {e}"[:200]}
        print(store, status[store], file=sys.stderr)

    # carry forward rows for stores that failed today, so the table never empties
    prev_rows = {}
    if prev and os.path.isdir(prev):
        for f in sorted(os.listdir(prev)):
            if f.startswith("catalog-") or f.startswith("catalog/"):
                pass
        for root, _, files in os.walk(prev):
            for f in files:
                if f.endswith(".json") and "catalog" in os.path.join(root, f):
                    d = json.load(open(os.path.join(root, f)))
                    for r in d.get("rows", []):
                        prev_rows[r["id"]] = r
    all_rows = [abena_fix_size(r) for r in all_rows]
    all_rows = harmonise([r for r in all_rows if not r.get("stale")]) + [r for r in all_rows if r.get("stale")]
    for store, st in status.items():
        if not st["ok"]:
            carried = [dict(r, stale=True) for r in prev_rows.values() if r["store"] == store]
            all_rows += carried
            st["carried"] = len(carried)

    # ----- history: {id: [[date, price, avail], ...]} only on change -----
    hist = {}
    if prev and os.path.isdir(prev):
        for root, _, files in os.walk(prev):
            for f in files:
                if f.endswith(".json") and "history" in root + f:
                    hist.update(json.load(open(os.path.join(root, f))).get("h", {}))
    live_ids = {r["id"] for r in all_rows}
    cutoff = (datetime.date.fromisoformat(today) - datetime.timedelta(days=60)).isoformat()
    hist = {k: v for k, v in hist.items() if k in live_ids or (v and v[-1][0] >= cutoff)}
    for r in all_rows:
        if r.get("stale"):
            continue
        h = hist.setdefault(r["id"], [])
        point = [today, r["price"], 1 if r["avail"] else 0]
        if not h or h[-1][1:] != point[1:]:
            if h and h[-1][0] == today:
                h[-1] = point
            else:
                h.append(point)
        r["first"] = h[0][0]
        prices = [x[1] for x in h]
        r["prev"] = h[-2][1] if len(h) > 1 else None

    # ----- thumbnails: 72px WebP data URIs, carried forward when unchanged -----
    thumbs = {}
    if prev and os.path.isdir(prev):
        for root, _, files in os.walk(prev):
            for f in files:
                if f.endswith(".json") and "thumbs" in root + f:
                    thumbs.update(json.load(open(os.path.join(root, f))).get("t", {}))
    want = {}
    for r in all_rows:
        if r.get("img"):
            want.setdefault(r["t"], r["img"])
    try:
        from PIL import Image
    except ImportError as e:
        Image = None
        print("thumb fail: Pillow is not installed, no new thumbnails made:", e, file=sys.stderr)
    keep = {}
    for k, src in want.items():
        old = thumbs.get(k)
        if old and old.get("src") == src:
            keep[k] = old
            continue
        if Image is None:
            continue
        try:
            base = dict(STORES)[k.split("|")[0]]
            local = re.sub(r"^https://cdn\.shopify\.com/s/files/[\d/]+/", base + "/cdn/shop/", src).replace("width=160", "width=200")
            blob = None
            for u in ((local, src) if VIA.get(k.split("|")[0]) is None else (src,)):
                try:
                    blob = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read()
                    break
                except Exception:  # noqa
                    continue
            if blob is None:
                raise RuntimeError("image not reachable")
            im = Image.open(io.BytesIO(blob)).convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[3])
            bg.thumbnail((88, 88))
            buf = io.BytesIO()
            bg.save(buf, "WEBP", quality=55)
            keep[k] = {"src": src, "d": "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()}
        except Exception as e:  # noqa
            print("thumb fail", k, e, file=sys.stderr)
    for r in all_rows:
        r.pop("img", None)

    # ----- write chunked docs -----
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

    for f in os.listdir(out):
        if f.endswith(".json"):
            os.remove(os.path.join(out, f))
    all_rows.sort(key=lambda r: (r["store"], r["name"], SIZE_ORDER.index(r["size"]) if r["size"] in SIZE_ORDER else 99, r["pkg"]))
    n_cat = 0
    for i, c in enumerate(chunks(all_rows)):
        json.dump({"rows": c, "date": today}, open(f"{out}/catalog-{i}.json", "w"), separators=(",", ":"))
        n_cat += 1
    hitems = list(hist.items())
    n_hist = 0
    for i, c in enumerate(chunks(hitems)):
        json.dump({"h": dict(c)}, open(f"{out}/history-{i}.json", "w"), separators=(",", ":"))
        n_hist += 1
    n_th = 0
    for i, c in enumerate(chunks(list(keep.items()))):
        json.dump({"t": dict(c)}, open(f"{out}/thumbs-{i}.json", "w"), separators=(",", ":"))
        n_th += 1
    meta = {"lastRun": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "date": today, "stores": status, "rows": len(all_rows),
            "catalogDocs": n_cat, "historyDocs": n_hist, "thumbDocs": n_th}
    json.dump(meta, open(f"{out}/meta.json", "w"), indent=1)
    with open(f"{out}/rows.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()) if all_rows else ["id"], extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
