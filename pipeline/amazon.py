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
# Listings whose title leaves out the piece count, the size or the capacity (and no other store or CAP_BY_SIZE has
# the capacity) get their product page read once, 1 credit each. Results are kept per ASIN in meta.amazon.qty.
# While pages are waiting, up to PAGE_LOOKUPS a day are read and searches drop to no fewer than MIN_SEARCHES
# (owner 2026-11-01: clean the data up quickly); with no backlog every credit goes to searches again.
PAGE_LOOKUPS = 40
MIN_SEARCHES = 8
# Other pack sizes of tracked products that searches never show (Amazon lists one or two versions of a product per
# search; Sunkiss Masterpiece 40-count cases were missing, owner 2026-11-02). A product page names all its versions;
# a version with a size + pack count the tracker lacks for that product is watched: its own page is read for the price,
# at most WATCH_PAGES a day, each about once a week (carried forward in between). Colour-only versions are skipped.
WATCH_PAGES = 4
WATCH_DAYS = 7
PAGE_RETRY_DAYS = 45   # pages that gave no count are tried again after this long
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
CAP_BY_SIZE = {   # "*" = every size
    # Sunkiss Masterpiece, every size and colour: 6000 mL from the product photo (owner 2026-11-02, B0C9VSXGZ3)
    "diaper|sunkiss|masterpiece": {"*": 6000},
    # Sunkiss TrustPlus Adult Diapers with Tabs, from the product image (owner, 2026-10-31)
    "diaper|sunkiss|trustplus": {"S": 1300, "M": 1600, "L": 2000, "XL": 2300, "XXL": 2600},
    # Abena Slip Flexi-Fit Premium M-L4: 'Absorbs up to 115 fl oz' in the Amazon description (B0CP6JDR16, owner 2026-10-31)
    "diaper|abena|4 fit flexi level premium slip": {"M/L": 3400},
}
# Owner-checked listings (2026-11-01): piece counts the listing does not state, and listings that are not disposable diapers
QTY_BY_ASIN = {"B0098798ZY": 12,    # Tranquility Premium DayTime Pull-On Underwear XXL ('XXL 12')
               "B0C8TPWV3T": 14}    # MoliCare Slip Maxi 9 Drops, M
# Owner-checked product names for listings whose title names only a size ('Attends XXL Briefs (XXL)'); the page
# description says 'ATTENDS BRIEFS DERMADRY BARTRC - 4X12 XXL' (owner 2026-11-02)
# Owner-checked capacities (mL) for single listings (owner 2026-11-02); Tranquility SlimLine differs by size
CAP_BY_ASIN = {"B00K69K0HS": 657,   # Tranquility Premium ATN, S: 22.2 oz
               "B07KKLYQ6K": 602,   # Tranquility SlimLine, M
               "B00RXYV88E": 302,   # Tranquility SlimLine, Youth/Junior
               "B002ZQ9RP6": 374}   # Tranquility SlimLine, S
LINE_BY_ASIN = {"B00Y3AWZCE": "DermaDry Advance",              # product image (owner 2026-11-02)
                "B0DBJ9ZD3L": "Overnight Bariatric Briefs"}    # product image (owner 2026-11-02)
NOT_TRACKED = {"B0GRTJZR84", "B0GRT3VWJZ"}   # Landofgenie Women's Cartoon Print Underwear Potty Pants (reusable underwear)
AB_BRANDS = {"Sunkiss", "Little for Big", "Rearz", "Tykables", "ABUniverse", "LNGU", "Kiddo", "Crinklz", "Cuddlz",
             "Landofgenie", "Bambino"}
GENERIC = {"adult", "printed", "diaper", "diapers", "brief", "briefs", "incontinence", "underwear", "unisex",
           "disposable", "tabs", "with", "for", "men", "women", "and", "pieces", "count", "pack", "ct", "the",
           "protective", "absorbent", "absorbency", "plastic", "backed", "tab", "style", "pull", "ups", "on", "hips",
           "waist", "inch", "inches", "small", "medium", "large"}


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
        title = re.sub(r"^\s*sponsored\s+ad\s*[–—:-]\s*", "", title, flags=re.I)
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
    # pack sizes are not part of the name: 'Case/100', 'Pk/25', '- CASE/32', '(4 bags of 25)'
    title = re.sub(r"\s*-?\s*\b(?:case|pack|pk|bag|box)\s*/\s*\d+\b|\(\s*\d+\s*(?:bags|packs)\s+of\s+\d+\s*\)", " ", title, flags=re.I)
    segs = [s.strip() for s in re.split(r",|;|\||\(|\s[-–]\s", title) if s.strip()]
    for s in segs:
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z+'’]+", s) if w.lower() not in GENERIC and len(w) > 2
                 and not S.size_of(w)]
        if words:
            return re.sub(r"\s*\d+\s*(?:pieces|count|ct|pack)\b.*$", "", s, flags=re.I).strip()
    return segs[0] if segs else title


def amazon_size(title):
    # '(Medium To Extra Large)' / '(Small To Extra Large Sizes)' is the range the product comes in, not this listing's size
    sw = r"(?:x*-?small|medium|x*-?large|extra[\s-]*(?:small|large))"
    t = re.sub(r"\([^()]*\b" + sw + r"\s+to\s+" + sw + r"\b[^()]*\)", "", title, flags=re.I)
    for seg in re.split(r"[,;()|]", t):
        seg2 = re.sub(r"large\s*/\s*(?:x-?|extra\s*)large", "L/XL", re.sub(r"\bbariatric\b", " ", seg, flags=re.I), flags=re.I)
        seg2 = re.sub(r"\bextra[\s-]*small\b", "XS", seg2.replace("Small/Medium", "S/M"), flags=re.I)
        sz = S.size_of(seg2)
        if sz and len(seg.strip()) <= 40:
            return sz
    return S.size_of(t) or "One size"


def amazon_qty(title):
    """Pieces in the listing, from its title -> (qty or None, sure).
    sure=False means the title is unclear ('24 Count (Pack of 4)' is 24 or 96 depending on the seller, a lone
    'Pack of 2' may be 2 bags) and the product page's 'Number of Items' should decide."""
    t = re.sub(r"\b(?:level|size|stage|step)\s*\d+\b", " ", title, flags=re.I)
    n = r"(?<![A-Za-z\d.])(\d{1,3})"
    def ok(v):
        return v if 0 < v <= 400 else None
    # '(64 Total - 2 Pack)', '4 packs of 20 (80 total)'
    m = re.search(n + r"\s*total\b", t, re.I)
    if m:
        return ok(int(m.group(1))), True
    # 'Case of 56', 'Case/96 (8/12s)', '96/case', '90/case', 'Pack/12', 'Pk/25', 'Bag of 20', '20 per bag', '48/Case'
    m = re.search(r"\b(?:(?:case|bag|box)\s*(?:/|of)|(?:pack|pk)\s*/)\s*(\d{1,3})\b", t, re.I)
    m = m or re.search(n + r"\s*(?:/|per)\s*(?:case|bag|box|pack|pk)\b", t, re.I)
    if m:
        return ok(int(m.group(1))), True
    # '4X12' = 4 bags of 12 (Attends: 'ATTENDS BRIEFS DERMADRY BARTRC - 4X12 XXL')
    m = re.search(n + r"\s*[x×]\s*(\d{1,3})\b(?!\s*(?:[\"”']|in\b|inch|cm|mm|ml|oz))", t, re.I)
    if m and int(m.group(1)) <= 12:
        return ok(int(m.group(1)) * int(m.group(2))), True
    # '3 Packs of 12', '4 bags of 25', '(2 bags of 36)'
    m = re.search(n + r"\s*(?:packs|bags|boxes)\s+of\s+(\d{1,3})\b", t, re.I)
    if m:
        return ok(int(m.group(1)) * int(m.group(2))), True
    # '14pcs x 4bags'
    m = re.search(n + r"\s*(?:pcs|pieces|ct|count)\s*x\s*(\d{1,2})\s*(?:bags|packs)\b", t, re.I)
    if m:
        return ok(int(m.group(1)) * int(m.group(2))), True
    # '96 Count', '15-Count', '24ct', '10 Pieces', '12 pcs', '(12 Pack)', 'Sample 2 Pack', '10Pack'
    m = re.search(n + r"\s*-?\s*(?:count|coun\b|ct\b|pieces|pcs|pc\b|pack\b|-pack|diapers|briefs)", t, re.I)
    multi = re.search(r"\(\s*pack of (\d+)\s*\)|\bpack of (\d+)\b", t, re.I)
    if m:
        q = ok(int(m.group(1)))
        k = multi and int(multi.group(1) or multi.group(2))
        return q, not (k and k > 1)
    # a lone 'Pack of 20' is most likely the piece count, but 'Pack of 2' or 'DDEW30 Pack of 14' can be bags:
    # use it until the product page says otherwise
    if multi:
        return ok(int(multi.group(1) or multi.group(2))), False
    return None, False


def amazon_pkg(title, qty):
    # 2-3 diapers is a sample pack, whatever the listing calls it (owner 2026-11-01, Little for Big 2 Pieces)
    if (qty and qty <= 3) or re.search(r"\bsample\b|\btrial\b", title, re.I):
        return "Sample"
    return "Case" if (re.search(r"\bcase\b", title, re.I) or (qty and qty >= 40)) else "Bag"


def page_qty(raw):
    n = _page_qty_fields(raw)
    if n:
        return n
    # the listing's own description: '... - 4X12 XXL' (4 bags of 12)
    q, sure = amazon_qty(page_text(raw))
    return q if sure and q and q >= 6 else None


def _page_qty_fields(raw):
    """Amazon product page -> 'Number of Items' (or 'Sold as a case of N'), or None.
    Sellers often leave 'Number of Items' at 1, and a case can list its bags ('4' for 4 bags of 14), so
    counts under 6 are not taken (sample packs of 2 already say so in their titles)."""
    for pat in (r"Number of Items\s*</(?:span|th)>\s*</?t[dh][^>]*>\s*(?:<td[^>]*>\s*)?(?:<span[^>]*>)?\s*(\d{1,3})\s*<",
                r"(?:sold as|comes as|contains)\s+(?:a\s+)?(?:case|pack|bag|box) of (\d{1,3})\b",
                r"Unit Count\s*</(?:span|th)>\s*</?t[dh][^>]*>\s*(?:<td[^>]*>\s*)?(?:<span[^>]*>)?\s*(\d{1,3})(?:\.0)?\s*Count"):
        for m in re.finditer(pat, raw, re.I):
            v = int(m.group(1))
            if 6 <= v <= 400:
                return v
    return None


PAGE_SECTIONS = ("feature-bullets", "productDescription", "pqv-feature-bullets", "pqv-description",
                 "productOverview_feature_div", "prodDetails", "detailBullets")


def page_text(raw):
    """Text of the listing's own sections (bullets, description, details). Skips comparison tables, 'customers also
    bought' and ads, which name other products and their capacities."""
    parts = []
    for sid in PAGE_SECTIONS:
        for m in re.finditer(r'id="' + sid + r'"', raw):
            chunk = raw[m.end():m.end() + 40000]
            stop = re.search(r'id="(?:aplus|CardInstance|ad-|sims-|rhf|similarities)|_feature_div"', chunk[50:])
            chunk = chunk[:50 + stop.start()] if stop else chunk
            chunk = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", chunk, flags=re.S)
            parts.append(html.unescape(re.sub(r"<[^>]+>", " ", chunk)))
    return re.sub(r"\s+", " ", " ".join(parts))


def page_cap(raw, size, cat):
    """Capacity (mL) the product page states for this listing, or None. A figure for its size beats a whole-product one."""
    lo, hi = (100, 5000) if cat == "booster" else (S.CAP_MIN, 20000)
    t = page_text(raw)
    if not t:
        return None
    by = S.caps_by_size(t, lo, hi) or {}
    if by.get(size):
        return by[size]
    cap = S.capacity_ml(t, lo, hi)
    if cap:
        return cap
    # 'over 181 oz capacity', '115 oz of absorbency'
    vals = [int(round(float(x) * 29.5735 / 10.0)) * 10 for x in
            re.findall(r"(\d{2,3}(?:\.\d)?)\s*(?:fl\.?\s*)?(?:oz|ounces)\.?\s+(?:of\s+)?(?:capacity|absorb)", t, re.I)]
    vals = [v for v in vals if lo <= v <= hi]
    return max(vals) if vals else None


def page_siblings(raw):
    """Amazon product page -> {asin: 'Blue S/M(Pack of 40)'} for every version of the product"""
    m = re.search(r'"dimensionValuesDisplayData"\s*:\s*(\{[^{}]*\})', raw)
    try:
        return {a: " ".join(v) for a, v in json.loads(m.group(1)).items()} if m else {}
    except ValueError:
        return {}


def page_offer(raw):
    """Amazon product page -> (title, price, in stock) for the listing itself, or None"""
    t = re.search(r'id="productTitle"[^>]*>\s*([^<]+?)\s*<', raw)
    p = re.search(r'id="corePrice[^"]*".{0,3000}?class="a-offscreen">\$([\d,]+\.\d{2})<', raw, re.S)
    if not (t and p):
        return None
    a = re.search(r'id="availability"[^>]*>(.{0,400})', raw, re.S)
    av = re.sub(r"<[^>]+>", " ", a.group(1)) if a else ""
    return html.unescape(t.group(1)), float(p.group(1).replace(",", "")), not re.search(r"unavailable|out of stock", av, re.I)


def fetch_page(asin, key):
    """-> (raw html of the Amazon.ca product page, credits used)"""
    body = json.dumps({"url": f"{BASE}/dp/{asin}", "formats": ["rawHtml"],
                       "location": {"country": "CA", "languages": ["en-CA"]}, "proxy": "basic",
                       "onlyMainContent": False, "removeBase64Images": True, "maxAge": 0}).encode()
    req = urllib.request.Request("https://api.firecrawl.dev/v2/scrape", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.load(r)
    d = res.get("data") or {}
    return d.get("rawHtml") or "", int((d.get("metadata") or {}).get("creditsUsed") or 1)


def print_name(title):
    """'Little for Big Adjustable ... Cloth Back Diaper 2 Pieces - Little Beauty (Medium 28"-38")' -> ('Little Beauty', None).
    Adult-baby listings put the product's print name after the piece count; the words before it are the same
    for every print. -> (name, colour) or (None, None)."""
    m = re.search(r"\d+\s*(?:pieces|pcs|pc|count|coun|ct|pack)\b\)?(?:\s*\(\d+\s*packs?\))?"
                  r"(?:\s*pack\s+\d+\s+prints?\s+random\s+assorted|\s*sample\s+pack)?\s*[-–]\s*(.+)$", title, re.I)
    if not m:
        return None, None
    t = re.split(r"[,(;|]", m.group(1))[0]
    t = re.sub(r"\b\d[\d,.]*\s*(?:ml|l)\b", " ", t, flags=re.I)
    t = re.sub(r"\b(?:adult\s+)?(?:printed\s+)?(?:diapers?|briefs?)\b", " ", t, flags=re.I)
    t = re.sub(r"\s+(?:x{0,2}[sml]|xl|xxl|[sml]/[sml])\s*$", "", re.sub(r"\s+", " ", t).strip(), flags=re.I)
    colour = None
    mc = re.search(r"\s+(white|pink|blue|black|purple|green|yellow|grey|gray|red)\s*$", t, re.I)
    if mc and len(t[:mc.start()].split()) >= 1:
        colour, t = S.norm_variant(mc.group(1).title()), t[:mc.start()]
    t = t.strip(" -–")
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’]+", t) if w.lower() not in GENERIC and len(w) > 2]
    if not words:
        return None, None
    # 'Little for Big Ultra Absorbent 7000 mL ... - Goth Brat': the other stores call it 'Goth BRAT Ultra Absorbent'
    if re.search(r"\bultra\s+absorbent\b", title[:m.start()], re.I) and "ultra" not in t.lower():
        t += " Ultra Absorbent"
    return t, colour


def page_size(raw):
    """Amazon product page -> the listing's size from its details table ('Size | Medium'), or None."""
    for pat in (r"prodDetSectionEntry\">\s*Size\s*</th>\s*<td[^>]*>\s*([^<]{1,40}?)\s*</td>",
                r">\s*Size\s*</span>\s*</td>\s*<td[^>]*>\s*<span[^>]*>\s*([^<]{1,40}?)\s*</span>"):
        m = re.search(pat, raw)
        if m:
            sz = amazon_size(html.unescape(m.group(1)))
            if sz != "One size":
                return sz
    return None


def to_row(it, brand, today):
    if it["asin"] in NOT_TRACKED:
        return None
    it = dict(it, title=re.sub(r"^\s*sponsored\s+ad\s*[–—:-]\s*", "", it["title"], flags=re.I))
    title = re.sub(r"\bMd\b", "Medium", re.sub(r"\bLg\b", "Large", re.sub(r"\bSm\b", "Small", it["title"])))
    name = name_from_title(title)
    p = {"title": f"{brand} {name}", "handle": it["asin"], "vendor": brand, "product_type": "", "tags": [],
         "options": [], "variants": []}
    pn0 = print_name(title)[0] if brand in AB_BRANDS else None
    if pn0 and pn0.lower() in title.lower():
        # the print name after the piece count ('- Potty Pants') says nothing about the product type
        p = dict(p, title=f"{brand} {name_from_title(title[:title.lower().rfind(pn0.lower())].rstrip(' -–'))}")
    cat = S.category("Amazon", p)
    if not cat:
        # many Amazon titles leave out the product type before the first comma; look at the whole title
        p2 = dict(p, title=f"{brand} {title}")
        cat = S.category("Amazon", p2)
        if not cat:
            return None
    line, title_var = S.split_title("Amazon", p, brand)
    # sizes and 'Unisex'/'Bulk' are not part of a product name ('ULTRA BRIEFS LARGE UNISEX BULK' -> 'Ultra')
    sz = r"(?:\d?x{0,3}-?|extra[\s-]*)(?:small|medium|large)|x{1,3}l|[2-5]xl|xs|regular"
    l2 = re.sub(r"\b(?:XX|X)?[SML]\s*/\s*(?:XX|X)?[SML]\b|\s(?:XX|X)?[SML]\s*/?\s*$", " ", line)   # 'L/XL', 'S/M', a trailing 'L/'
    l2 = re.sub(r"\b(?:size\s*)?(?:" + sz + r")(?:\s*[/-]\s*(?:" + sz + r"))*\b|\bsize\s*\d\b|\b(?:unisex|bulk)\b", " ", l2, flags=re.I)
    l2 = re.sub(r"\s*/\s*(?=/|$)|^\s*/\s*|\s+-\s+(?=-|$)", " ", re.sub(r"\s+", " ", l2)).strip(" -,/")
    l2 = re.sub(r"\s+", " ", re.sub(r"\s+/\s+", " / ", l2))
    l2 = re.sub(r"^\s*size:?\s*$", "", l2, flags=re.I)
    if re.search(r"[A-Za-z]{3}", l2):
        line = l2
    elif re.fullmatch(r"\s*size:?\b.*", line, re.I):   # the title had only a size where the name goes
        line = {"pullup": "Underwear", "booster": "Booster Pads"}.get(cat, "Briefs")
    line = LINE_BY_ASIN.get(it["asin"], line)
    pn, pn_colour = print_name(title) if brand in AB_BRANDS else (None, None)
    if pn:
        p2 = dict(p, title=f"{brand} {pn}")
        line, title_var = S.split_title("Amazon", p2, brand)[0], title_var or pn_colour
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
    size = amazon_size(title)
    qty, _ = amazon_qty(title)
    pkg = amazon_pkg(title, qty)
    lo_hi = (100, 5000) if cat == "booster" else (S.CAP_MIN, 20000)
    cap = S.capacity_ml(title, *lo_hi)
    # booster pad dimensions, same form as the other stores: 'Mini 10.5" x 2.75"' -> '10.5" x 2.75"'
    dims = S.dims_of(title) if cat == "booster" and size == "One size" else None
    return S.abena_fix_size({
        "id": f"Amazon|{it['asin']}|{size}|{pkg}|{qty}|{variant or '-'}", "store": "Amazon",
        "name": f"{brand} {title}", "brand": brand, "line": line, "pid": S.product_key(brand, line, cat),
        "variant": variant, "cat": cat, "dims": dims, "style": S.style_of(p), "size": size, "pkg": pkg, "qty": qty,
        "price": it["price"], "cap": cap, "avail": True, "t": f"Amazon|{it['asin']}", "img": it["img"],
        "url": f"{BASE}/dp/{it['asin']}", "asin": it["asin"], "checked": today,
        "ab": brand in AB_BRANDS,
    })


def load_docs(folder, kind):
    files = sorted(glob.glob(os.path.join(folder, f"{kind}-*.json")) +
                   glob.glob(os.path.join(folder, kind, "*.json")))
    return files


def asin_image(asin):
    return f"https://m.media-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_.jpg"


def make_thumb(src, Image, label=None):
    """Download an image -> {src, d: 88px WebP data URI}, or None (Amazon answers unknown ASINs with a 1x1 GIF)."""
    try:
        blob = urllib.request.urlopen(urllib.request.Request(src, headers=S.UA), timeout=30).read()
        im = Image.open(io.BytesIO(blob)).convert("RGB")
        if min(im.size) < 20:
            raise ValueError("placeholder image")
        im.thumbnail((88, 88))
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=55)
        return {"src": src, "d": "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()}
    except Exception as e:  # noqa
        if label:  # "thumb fail" lines are counted as a problem by changes.py
            print("thumb fail", label, e, file=sys.stderr)
        return None


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
        st = {"month": month, "used": 0, "last": st.get("last", {}), "qty": st.get("qty", {})}
    qcache = st.setdefault("qty", {})
    last = st.get("last", {})
    prev_amz = {}
    for f in load_docs(prev, "catalog"):
        for r in json.load(open(f)).get("rows", []):
            if r["store"] == "Amazon":
                prev_amz[r["id"]] = r

    # product facts from the other stores (name, capacity) when the product matches
    by_pid, by_ck, pid_cap = {}, {}, {}
    for r in rows:
        by_pid.setdefault(r["pid"], r)
        if r.get("cap"):
            pid_cap[r["pid"]] = max(pid_cap.get(r["pid"], 0), r["cap"])   # sizes no store states: the highest figure
        if r.get("cap"):
            by_ck.setdefault((r["pid"], r["size"]), r)   # capacities can differ by size (Abena M4 3600 / L4 4000 mL)

    def known_cap(r):
        """Capacity from the title, another store or CAP_BY_SIZE: these come before reading the product page."""
        if r.get("cap") or r["asin"] in CAP_BY_ASIN or S.CAP_MANUAL.get(r["pid"]) or CAP_BY_SIZE.get(r["pid"], {}).get(r["size"]) or CAP_BY_SIZE.get(r["pid"], {}).get("*") \
                or S.brand_site_caps(r["brand"]).get(r["pid"]):
            return True
        return bool(by_pid.get(r["pid"]) and ((by_ck.get((r["pid"], r["size"])) or {}).get("cap") or pid_cap.get(r["pid"])))

    def other_dims(r):
        """booster dimensions the other stores agree on for this product, or None"""
        d = {x["dims"] for x in rows if x["pid"] == r["pid"] and x.get("dims") and x["size"] == r["size"]}
        return d.pop() if len(d) == 1 else None

    retry = (datetime.date.fromisoformat(today) - datetime.timedelta(days=PAGE_RETRY_DAYS)).isoformat()

    def stale(a, k):
        c = qcache.get(a)
        return c is None or k not in c or (not c[k] and c.get("d", "") < retry)

    def wants_page(r):
        """-> sort key if the listing's product page should be read (lower first), else None"""
        q, sure = amazon_qty(r["name"])
        nosize = r["size"] == "One size" and r["cat"] != "booster"
        a = r["asin"]
        need_n, need_size = not sure and stale(a, "n"), nosize and stale(a, "size")
        need_cap = not known_cap(r) and stale(a, "cap")
        need_dims = r["cat"] == "booster" and not r.get("dims") and not other_dims(r) and stale(a, "dims")
        if not (need_n or need_size or need_cap or need_dims):
            return None
        return (not need_size, q is not None, not need_n, a)

    def reparse(r):
        """listing from yesterday, read again from its stored title (so parsing fixes reach it without a new search)"""
        if r.get("name", "").startswith(r["brand"] + " "):
            it = {"asin": r["asin"], "title": r["name"][len(r["brand"]) + 1:], "price": r["price"], "img": None}
            nr = to_row(it, r["brand"], r.get("checked"))
            if nr is None:
                return None   # now excluded (e.g. reusable cloth diapers, owner 2026-11-01)
            nr.pop("img", None)
            return nr
        return r

    # how many searches today: an even share of this month's remaining budget
    y, mth = int(today[:4]), int(today[5:7])
    days_left = calendar.monthrange(y, mth)[1] - int(today[8:10]) + 1
    remaining = max(0, MONTHLY_BUDGET - st.get("used", 0))
    daily = MONTHLY_BUDGET / calendar.monthrange(y, mth)[1]
    n_today = int(min(len(QUERIES), remaining // days_left, math.ceil(daily * 1.5)))
    order = sorted(QUERIES, key=lambda q: (last.get(q, ""), QUERIES.index(q)))
    backlog = len({r["asin"] for r in map(reparse, prev_amz.values()) if r and wants_page(r)})
    n_search = max(min(MIN_SEARCHES, n_today), n_today - backlog) if backlog else n_today
    reserve = max(0, min(PAGE_LOOKUPS, backlog, remaining - n_search))   # credits kept for product pages
    todo = order[:n_search]

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

    # other pack sizes of tracked products (see WATCH_PAGES): find them from the versions product pages list
    watch = st.setdefault("watch", {})
    known_rows = list(found.values()) + [r for r in prev_amz.values() if r["asin"] not in {x["asin"] for x in found.values()}]
    tracked = {r["asin"] for r in known_rows}

    def combo(lab):
        """'Overnight Medium(48 Count)' -> ('overnight', 'M', 48); colours are dropped, so colours of one size + pack match"""
        style = re.sub(r"\b(?:white|pink|blue|black|purple|green|yellow|beige|grey|gray|red|orange|tie[- ]?dye)\b|\(.*?\)|\b\d+\b|"
                       r"\b(?:count|pack|of|pieces|ct|x{0,3}-?(?:small|medium|large)|xl|xxl|xs|[sml](?:/[sml]|/xl)?|l/xl|s/m)\b", " ", lab.lower())
        return (" ".join(style.split()), amazon_size(lab), amazon_qty(lab)[0])
    for r in known_rows:
        sib = (qcache.get(r["asin"]) or {}).get("sib") or {}
        have = {combo(l) for a2, l in sib.items() if a2 in tracked or a2 in watch}
        for a2, lab in sib.items():
            if a2 in tracked or a2 in watch or a2 in NOT_TRACKED:
                continue
            c = combo(lab)
            if c in have:
                continue   # another colour of a style + size + pack the tracker already has
            have.add(c)
            watch[a2] = {"brand": r["brand"], "last": ""}
    due = sorted((w["last"], a) for a, w in watch.items() if a not in {x["asin"] for x in found.values()}
                 and w["last"] <= (datetime.date.fromisoformat(today) - datetime.timedelta(days=WATCH_DAYS)).isoformat())
    status["watched"] = 0
    for _, a in due[:WATCH_PAGES if key else 0]:
        if st.get("used", 0) >= MONTHLY_BUDGET:
            break
        try:
            raw, used = fetch_page(a, key)
        except Exception as e:  # noqa
            errors.append(f"page {a}: {e}")
            continue
        st["used"] = st.get("used", 0) + used
        watch[a]["last"] = today
        off = page_offer(raw)
        if not off:
            continue
        title, price, avail = off
        brand = watch[a]["brand"]
        title = re.sub(r"^" + re.escape(brand) + r"\s+", "", title, flags=re.I)
        nr = to_row({"asin": a, "title": title, "price": price, "img": None}, brand, today)
        if nr:
            nr["avail"] = avail
            nr.pop("img", None)
            found[nr["id"]] = nr
            qcache[a] = {"n": page_qty(raw), "size": page_size(raw), "cap": page_cap(raw, page_size(raw) or nr["size"], nr["cat"]),
                         "dims": S.dims_of(page_text(raw)) if nr["cat"] == "booster" else None, "sib": page_siblings(raw), "d": today}
            status["watched"] += 1
        time.sleep(1)
    status["credits_month"] = st["used"]

    # carry forward listings not seen today (until CARRY_DAYS old)
    cutoff = (datetime.date.fromisoformat(today) - datetime.timedelta(days=CARRY_DAYS)).isoformat()
    seen_asins = {r["asin"] for r in found.values()}
    carried = [r for rid, r in prev_amz.items() if rid not in found and r.get("asin") not in seen_asins
               and (r.get("checked") or "") >= cutoff]
    carried = [r for r in map(reparse, carried) if r]
    amz = list(found.values()) + carried
    fresh = {id(r) for r in found.values()}

    # product pages (cached per ASIN) fill in what the title leaves out: piece count, size, capacity
    guess = {r["asin"]: amazon_qty(r["name"]) for r in amz}
    by_asin = {r["asin"]: r for r in amz}
    pending = sorted((k, a) for a, k in ((r["asin"], wants_page(r)) for r in amz) if k)
    pending = list(dict.fromkeys(a for k, a in pending))
    lookups = 0
    for a in pending[:reserve if key else 0]:
        try:
            for wait in (20, 40, 0):   # Firecrawl rate limit (HTTP 429): wait and try again
                try:
                    raw, used = fetch_page(a, key)
                    break
                except Exception as e:  # noqa
                    if "429" not in str(e) or not wait:
                        raise
                    time.sleep(wait)
        except Exception as e:  # noqa
            errors.append(f"page {a}: {e}")
            if "402" in str(e):
                break
            continue
        st["used"] = st.get("used", 0) + used
        lookups += 1
        if 'id="productTitle"' in raw:   # a real product page, not a block or captcha page
            r = by_asin[a]
            size = page_size(raw) or r["size"]
            qcache[a] = {"n": page_qty(raw), "size": page_size(raw), "cap": page_cap(raw, size, r["cat"]),
                         "dims": S.dims_of(page_text(raw)) if r["cat"] == "booster" else None, "sib": page_siblings(raw), "d": today}
        time.sleep(1)
    status["pages"] = lookups
    status["pages_waiting"] = max(0, len(pending) - lookups)
    status["credits_month"] = st["used"]
    if errors:
        status["errors"] = errors[:5]
    for r in amz:
        # a clear title count wins: the page's 'Number of Items' sometimes counts bags ('8' for Case/96 of 8 x 12)
        q, sure = guess[r["asin"]]
        n = QTY_BY_ASIN.get(r["asin"]) or (q if sure else ((qcache.get(r["asin"]) or {}).get("n") or q))
        r["qty"], r["pkg"] = n, amazon_pkg(r["name"], n)
        if r["size"] == "One size" and (qcache.get(r["asin"]) or {}).get("size"):
            r["size"] = qcache[r["asin"]]["size"]
        r["id"] = f"Amazon|{r['asin']}|{r['size']}|{r['pkg']}|{n}|{r['id'].split('|', 5)[5]}"

    # product facts from the other stores (name, capacity) when the product matches; the product page comes last
    def dkey(d):
        return tuple(sorted(float(x) for x in re.findall(r"\d+(?:\.\d+)?", d or ""))) or None
    for r in amz:
        # a booster whose title gives its dimensions is the same brand's pad with those dimensions
        # ('TopLiner Booster Pads, Mini 10.5" x 2.75"' is TopLiner Mini, not the 14" x 4" TopLiner)
        if r["cat"] == "booster" and r.get("dims"):
            same = {x["pid"] for x in rows if x["cat"] == "booster" and x["brand"] == r["brand"] and dkey(x.get("dims")) == dkey(r["dims"])}
            if len(same) == 1:
                r["pid"] = same.pop()
        o = by_pid.get(r["pid"])
        if o:
            r["line"] = o["line"]
            r["cap"] = r["cap"] or (by_ck.get((r["pid"], r["size"])) or {}).get("cap") or pid_cap.get(r["pid"])
            # booster dimensions: the other stores' figure when they all agree
            if r["cat"] == "booster" and not r.get("dims"):
                r["dims"] = other_dims(r)
        r["line"] = S.LINE_NAME.get(r["pid"], r["line"])
        S.abena_names([r])
        sized = CAP_BY_ASIN.get(r["asin"]) or CAP_BY_SIZE.get(r["pid"], {}).get(r["size"]) or CAP_BY_SIZE.get(r["pid"], {}).get("*")
        if sized:
            r["cap"] = sized
        r["cap"] = r["cap"] or S.CAP_MANUAL.get(r["pid"]) or S.brand_site_caps(r["brand"]).get(r["pid"]) or (qcache.get(r["asin"]) or {}).get("cap")
        if r["cat"] == "booster" and not r.get("dims"):
            r["dims"] = (qcache.get(r["asin"]) or {}).get("dims")   # product page, last
        r["ppd"] = round(r["price"] / r["qty"], 3) if r["qty"] else None
        r["ppl"] = round(r["ppd"] / (r["cap"] / 1000), 3) if (r.get("ppd") and r.get("cap")) else None
        r["ck"] = f"{r['pid']}|{r['size']}|{r.get('dims') or ''}"   # same compare key as scraper.py (boosters by dimensions)

    # history: only for listings checked today
    hfiles = load_docs(out, "history")
    hist = {}
    for f in hfiles:
        hist.update(json.load(open(f)).get("h", {}))
    # a listing whose piece count was corrected gets a new id: move its price history over
    ids = {r["id"] for r in amz}
    for r in amz:
        if r["id"] in hist:
            continue
        p = r["id"].split("|")
        old = [k for k in hist if k.startswith(f"Amazon|{r['asin']}|") and k not in ids
               and k.split("|")[2] in (p[2], "One size") and k.split("|")[5:] == p[5:]]
        if len(old) == 1:
            hist[r["id"]] = hist.pop(old[0])
    for r in amz:
        h = hist.setdefault(r["id"], [])
        if id(r) in fresh:
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
    except ImportError as e:
        Image = None
        print("thumb fail: Pillow is not installed, no Amazon thumbnails made:", e, file=sys.stderr)
    for r in amz:
        src = r.pop("img", None)
        if not Image or not src or (thumbs.get(r["t"]) or {}).get("src") == src:
            continue
        thumb = make_thumb(src, Image, r["t"])
        if thumb:
            thumbs[r["t"]] = thumb
    # listings carried over from earlier days have no search image: try Amazon's ASIN image
    # (many ASINs have none and get a 1x1 placeholder, so these misses are not reported)
    for r in amz:
        if Image and r["t"] not in thumbs:
            thumb = make_thumb(asin_image(r["t"].split("|", 1)[1]), Image)
            if thumb:
                thumbs[r["t"]] = thumb

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
