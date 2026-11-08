#!/usr/bin/env python3
"""Dip Aisle: render the daily report (changes.py JSON) as an HTML email in The Diaper Aisle design system.

Usage:  python3 changes.py ./prev ./out ./scrape.log > changes.json
        python3 email_html.py --build changes.json YYYY-MM-DD OUTDIR   (daily run: writes both editions + plan.json)
        python3 email_html.py changes.json YYYY-MM-DD > email.html     (one HTML, full edition)
        python3 email_html.py --logo SOURCE.png      (builds tda-logo-email.png, ~13 KB)
  SOURCE = project file "The Dip Aisle Logos/03 - Print Resolutio Exports/DTA_Logo_Stroke_300DPI.png"
  (project_read it; it comes back as a local file path).
Send the HTML as the email's htmlBody, changes.py's `report` as the plain-text body, and the logo
(tda-logo-email.png) as the first attachment with inline=true; the HTML points at it as cid:att0.
Email-safe: tables + inline styles only, no scripts, no external CSS, one inline image.
Gmail connector rules (tested 2026-10-30): use background-color, never the `background:` shorthand (stripped);
external image URLs are stripped; the inline logo must be src="cid:att0".
"""
import html, json, re, sys

# design tokens (The Diaper Aisle, tokens.json v1)
INK, BLUE, TEAL, NAVY = "#33254c", "#5ea6db", "#1f5f80", "#14425c"
CYAN, SKY, MIST, FROST, WHITE = "#64c2e8", "#b6d9f3", "#cee3f0", "#f2f5f8", "#ffffff"
PURPLE, GREY = "#7f749d", "#98979c"
GREEN, GREEN_DEEP, RED, RED_DEEP = "#7fc678", "#298540", "#eb665d", "#c83c38"
FONT = "Rubik, 'Helvetica Neue', Helvetica, Arial, sans-serif"
TRACKER = "https://thediaperaisle.github.io/The-Diaper-Aisle/"
# The Diaper Aisle sticker logo (white die-cut border, for dark grounds), 240px wide, shown at 180px.
# Made from project file "The Dip Aisle Logos/03 - Print Resolutio Exports/DTA_Logo_Stroke_300DPI.png"
# (cropped, resized, 64-colour PNG, ~13 KB). Attach it as the email's FIRST attachment with inline=true.
LOGO_FILE = "tda-logo-email.png"
LOGO_H = 164

e = html.escape


def split_item(item):
    """'Brand Line (variant size pkg) @ Store' -> (product, detail, store)."""
    store = ""
    if " @ " in item:
        item, store = item.rsplit(" @ ", 1)
    m = re.match(r"(.*?)\s*\((.*)\)\s*$", item)
    return (m.group(1), m.group(2), store) if m else (item, "", store)


def money(x):
    return f"${x:,.2f}"


def pill(text, bg, fg, border=None):
    b = f"border:2px solid {border};" if border else ""
    return (f'<span style="display:inline-block;{b}background-color:{bg};color:{fg};font-family:{FONT};font-size:12px;'
            f'line-height:16px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;padding:4px 10px;'
            f'border-radius:9999px;white-space:nowrap;">{text}</span>')


MAX_ROWS = 20  # per section; the plain-text part of the email always carries the full list


def more_row(n):
    return (f'''
    <tr><td style="padding:10px 0;font-family:{FONT};font-size:13px;line-height:18px;color:{TEAL};">
      + {n} more &middot; <a href="{TRACKER}" style="color:{TEAL};">see the tracker</a></td></tr>''' if n > 0 else "")


def section(title, count, rows_html, accent):
    return f'''
<tr><td style="padding:24px 32px 0 32px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td style="font-family:{FONT};font-size:13px;line-height:16px;font-weight:700;letter-spacing:0.06em;
        text-transform:uppercase;color:{INK};padding:0 0 8px 0;border-bottom:3px solid {accent};">
      {e(title)}&nbsp;<span style="color:{TEAL};">({count})</span></td></tr>
    {rows_html}
  </table>
</td></tr>'''


def item_row(product, detail, store, right_html, sub="", url=None):
    name = (f'<a href="{e(url)}" style="color:{INK};text-decoration:underline;">{e(product)}</a>'
            if url and url.startswith("http") else e(product))
    sub_html = f'<div style="font-size:13px;line-height:18px;color:{TEAL};">{sub}</div>' if sub else ""
    return f'''
    <tr><td style="padding:12px 0;border-bottom:1px solid {MIST};">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="font-family:{FONT};vertical-align:top;">
          <div style="font-size:15px;line-height:20px;font-weight:600;color:{INK};">{name}</div>
          <div style="font-size:13px;line-height:18px;color:{TEAL};">{e(detail)}{" &middot; " if detail and store else ""}<b>{e(store)}</b></div>
          {sub_html}
        </td>
        <td style="font-family:{FONT};vertical-align:top;text-align:right;white-space:nowrap;padding-left:12px;">{right_html}</td>
      </tr></table>
    </td></tr>'''


def delivered_html(c):
    """delivered price per piece under a price change (Ontario, the tracker's default), owner 2026-11-03"""
    if c.get("d_new") is None:
        return ""
    u = lambda x: f"${x:.{3 if x < 1 else 2}f}"
    txt = (f'{u(c["d_new"])}/{c["one"]} + shipping' if c.get("ship_quoted")
           else f'{u(c["d_new"])}/{c["one"]} delivered')
    return f'<div style="font-size:12px;line-height:16px;color:{TEAL};padding-top:4px;white-space:nowrap;">{txt}</div>'


def render(d, date, logo_src="cid:att0"):
    """logo_src: 'cid:att0' = the email's first attachment (LOGO_FILE, inline=true). Gmail rewrites it to the
    attachment's Content-ID; other src forms (cid:0, https://...) are stripped by the Gmail connector."""
    changes, back, oos = d.get("price_changes", []), d.get("back_in_stock", []), d.get("out_of_stock", [])
    new, gone, issues = d.get("new_listings", []), d.get("removed_listings", []), d.get("issues", [])
    banner = re.sub(r"^Dip Aisle:\s*", "", d.get("banner", "")).rstrip(".")
    # headline: the banner without the per-store breakdowns (the sections below carry those)
    headline = re.sub(r"\s*\([^()]*\)", "", banner).replace("; ", ", ")
    headline = re.sub(r", ([^,]*)$", r" and \1", headline) if headline.count(",") else headline
    quiet = not (changes or back or oos or new or gone or issues)

    # ---- summary badges ----
    up = sum(1 for c in changes if c["new"] > c["old"])
    badges = []
    if issues:
        badges.append(pill(f"! {len(issues)} to check", RED_DEEP, WHITE))
    if changes:
        badges.append(pill(f"$ {len(changes)} price change{'s' if len(changes) != 1 else ''}" + (f" &middot; {up} up" if up else ""), SKY, INK, INK))
    if oos:
        badges.append(pill(f"{len(oos)} out of stock", WHITE, RED_DEEP, RED_DEEP))
    if back:
        badges.append(pill(f"{len(back)} back in stock", WHITE, GREEN_DEEP, GREEN_DEEP))
    if new:
        badges.append(pill(f"+ {len(new)} new", FROST, TEAL, TEAL))
    if gone:
        badges.append(pill(f"{len(gone)} removed", FROST, PURPLE, PURPLE))
    badge_row = " ".join(f'<span style="display:inline-block;margin:0 4px 8px 0;">{b}</span>' for b in badges)

    body = []
    if quiet:
        body.append(f'''
<tr><td style="padding:32px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td style="background-color:{FROST};border-radius:16px;padding:24px;text-align:center;font-family:{FONT};">
      <div style="font-size:20px;line-height:26px;font-weight:600;color:{INK};">No price or stock changes today.</div>
      <div style="font-size:14px;line-height:20px;color:{TEAL};padding-top:4px;">Every shelf looks the same as yesterday.</div>
    </td></tr></table>
</td></tr>''')

    if issues:
        rows = "".join(f'''
    <tr><td style="padding:10px 0;border-bottom:1px solid {MIST};font-family:{FONT};font-size:14px;line-height:20px;color:{INK};">
      <span style="color:{RED_DEEP};font-weight:700;">!</span>&nbsp; {e(i)}</td></tr>''' for i in issues[:MAX_ROWS]) + more_row(len(issues) - MAX_ROWS)
        body.append(section("Problems", len(issues), rows, RED_DEEP))

    if changes:
        rows = ""
        for c in changes[:MAX_ROWS]:
            p, det, st = split_item(c["item"])
            is_up = c["new"] > c["old"]
            pct = f'{"&#9650;" if is_up else "&#9660;"} {c["pct"]:+.1f}%' if c.get("pct") is not None else ""
            colour = RED_DEEP if is_up else GREEN_DEEP
            right = (f'<div style="font-size:15px;line-height:20px;font-weight:700;color:{INK};">{money(c["new"])}</div>'
                     f'<div style="font-size:13px;line-height:18px;color:{TEAL};"><s>{money(c["old"])}</s></div>'
                     f'<div style="font-size:12px;line-height:16px;font-weight:700;color:{colour};padding-top:2px;">'
                     f'{pct} {"up" if is_up else "down"}</div>' + delivered_html(c))
            rows += item_row(p, det, st, right, url=c.get("url"))
        rows += more_row(len(changes) - MAX_ROWS)
        body.append(section("Price changes", len(changes), rows, BLUE))

    for title, items, accent, tag in (("Back in stock", back, GREEN_DEEP, pill("In stock", WHITE, GREEN_DEEP, GREEN_DEEP)),
                                      ("Newly out of stock", oos, RED_DEEP, pill("Sold out", WHITE, RED_DEEP, RED_DEEP))):
        if items:
            rows = "".join(item_row(*split_item(x["item"]),
                                    f'<div style="font-size:15px;line-height:20px;font-weight:700;color:{INK};padding-bottom:4px;">{money(x["price"])}</div>{tag}', url=x.get("url"))
                           for x in items[:MAX_ROWS]) + more_row(len(items) - MAX_ROWS)
            body.append(section(title, len(items), rows, accent))

    if new:
        rows = "".join(item_row(*split_item(x["item"]),
                                f'<div style="font-size:15px;line-height:20px;font-weight:700;color:{INK};">{money(x["price"])}</div>'
                                + delivered_html(x)
                                + ("" if x.get("avail", True) else f'<div style="padding-top:4px;">{pill("Sold out", WHITE, RED_DEEP, RED_DEEP)}</div>'),
                                url=x.get("url"))
                       for x in new[:MAX_ROWS]) + more_row(len(new) - MAX_ROWS)
        body.append(section("New listings", len(new), rows, TEAL))

    if gone:
        rows = "".join(item_row(*split_item(x["item"]),
                                f'<div style="font-size:13px;line-height:18px;color:{TEAL};">was {money(x["price"])}</div>', url=x.get("url"))
                       for x in gone[:MAX_ROWS]) + more_row(len(gone) - MAX_ROWS)
        body.append(section("Removed listings", len(gone), rows, PURPLE))

    out = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><title>Daily update {e(date)}</title>
</head>
<body style="margin:0;padding:0;background-color:{FROST};">
<div style="display:none;max-height:0;overflow:hidden;">{e(headline[:1].upper() + headline[1:])}.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{FROST};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
  style="max-width:600px;background-color:{WHITE};border:3px solid {INK};border-radius:16px;overflow:hidden;">

  <!-- header: dark ink ground with the sticker logo, like the brand's social posts -->
  <tr><td align="center" style="background-color:{INK};padding:32px 32px 24px 32px;font-family:{FONT};text-align:center;">
    <img src="{logo_src}" width="180" height="{LOGO_H}" alt="The Diaper Aisle"
      style="display:block;margin:0 auto;width:180px;height:auto;max-width:100%;border:0;outline:none;text-decoration:none;color:{WHITE};font-family:{FONT};font-size:20px;font-weight:700;">
    <div style="font-size:13px;line-height:16px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:{CYAN};padding-top:32px;">
      {e(date)}</div>
    <div style="font-size:28px;line-height:32px;font-weight:700;color:{WHITE};padding-top:4px;text-transform:uppercase;">
      Daily price update</div>
  </td></tr>
  <!-- blue shelf edge -->
  <tr><td style="background-color:{BLUE};height:10px;line-height:10px;font-size:0;border-top:3px solid {INK};border-bottom:3px solid {INK};">&nbsp;</td></tr>

  {"" if quiet else f"""<!-- banner -->
  <tr><td style="padding:28px 32px 0 32px;font-family:{FONT};">
    <div>{badge_row}</div>
  </td></tr>"""}

  {"".join(body)}

  <!-- tracker button -->
  <tr><td align="center" style="padding:32px 32px 28px 32px;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="background-color:{TEAL};border:3px solid {INK};border-radius:9999px;">
        <a href="{TRACKER}" style="display:inline-block;padding:12px 28px;font-family:{FONT};font-size:14px;line-height:16px;
          font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:{WHITE};text-decoration:none;">Open the tracker</a>
      </td></tr></table>
  </td></tr>

  <!-- footer -->
  <tr><td style="background-color:{FROST};border-top:2px solid {MIST};padding:16px 32px;font-family:{FONT};font-size:12px;line-height:18px;color:{TEAL};text-align:center;">
    Prices in CAD from Healthwick, ABUniverse, MyDips, AgeComfort, Rearz, Amazon and Well.ca, checked every morning, and Walmart, checked every two weeks. Delivered prices include shipping to Ontario.<br>
    <a href="{TRACKER}" style="color:{TEAL};">{TRACKER}</a>
  </td></tr>
</table>
</td></tr></table>
</body></html>'''
    # drop comments and blank lines: the daily run pastes this into the Gmail tool, so keep it small
    return re.sub(r"\n\s*\n", "\n", re.sub(r"[ \t]*<!--.*?-->", "", out))

CHANGE_KEYS = ("price_changes", "back_in_stock", "out_of_stock", "new_listings", "removed_listings")
TRACKER_LINE = "Tracker: " + TRACKER


def has_changes(d):
    return any(d.get(k) for k in CHANGE_KEYS)


def public_view(d):
    """The edition for everyone except the owner: same changes, no problems (owner 2026-10-30)."""
    p = dict(d, issues=[])
    banner = re.sub(r";?\s*\d+ problems? to check", "", d.get("banner", "")).replace(": .", ":").rstrip(" .;") + "."
    if banner.strip() in ("Dip Aisle:.", "Dip Aisle."):
        banner = "Dip Aisle: no price or stock changes today."
    p["banner"] = banner
    lines = (d.get("report") or "").split("\n")
    out, skip = [], False
    for i, ln in enumerate(lines):
        if i == 0:
            out.append(banner)
            continue
        if re.match(r"PROBLEMS \(\d+\)$", ln):
            skip = True
            if out and out[-1] == "":
                out.pop()
            continue
        if skip and ln == "":
            skip = False
        if not skip:
            out.append(ln)
    p["report"] = "\n".join(out)
    return p


def subject(view, date):
    """Scoreboard subject (owner 2026-11-03): 'Diaper Aisle · Nov 3: 42 ↓ 29 ↑ · 3 sold out · 2 back · 16 new'.
    Only non-zero parts; the owner edition adds '⚠ N to check' when there are problems."""
    import datetime as _dt
    ch = view.get("price_changes", [])
    down = sum(1 for c in ch if c["new"] < c["old"])
    up = sum(1 for c in ch if c["new"] > c["old"])
    parts = []
    if down or up:
        parts.append(" ".join(x for x in ((f"{down} ↓" if down else ""), (f"{up} ↑" if up else "")) if x))
    for key, word in (("out_of_stock", "sold out"), ("back_in_stock", "back"), ("new_listings", "new"), ("removed_listings", "removed")):
        if view.get(key):
            parts.append(f"{len(view[key])} {word}")
    if view.get("issues"):
        parts.append(f"⚠ {len(view['issues'])} to check")
    try:
        d = _dt.date.fromisoformat(date)
        day = f"{d.strftime('%b')} {d.day}"
    except ValueError:
        day = date
    return f"Diaper Aisle · {day}: " + (" · ".join(parts) if parts else "no changes")


# Price changes smaller than this (in %) are left out of the email as noise; the tracker keeps them
# (owner 2026-11-05: 1%, raised to 5% on 2026-11-08)
EMAIL_MIN_PCT = 5.0


def drop_small_changes(d):
    """The email's copy of the day: price changes under EMAIL_MIN_PCT removed from the list, the report text and the
    banner's count."""
    ch = d.get("price_changes", [])
    keep = [c for c in ch if c.get("pct") is None or abs(c["pct"]) >= EMAIL_MIN_PCT]
    if len(keep) == len(ch):
        return d
    d = dict(d, price_changes=keep)
    up = sum(1 for c in keep if c["new"] > c["old"])
    part = f"{len(keep)} price change{'s' if len(keep) != 1 else ''} ({up} up / {len(keep) - up} down)" if keep else ""
    banner = re.sub(r"\d+ price changes? \([^()]*(?:\([^()]*\)[^()]*)*\)", part, d.get("banner", ""))
    banner = re.sub(r":\s*;\s*", ": ", re.sub(r";\s*;", ";", banner)).replace(": .", ":").strip()
    if re.fullmatch(r"Dip Aisle:\s*\.?", banner):
        banner = "Dip Aisle: no price or stock changes today."
    d["banner"] = banner
    lines, out, i = (d.get("report") or "").split("\n"), [], 0
    small = re.compile(r"\(([+-]?\d+(?:\.\d+)?)%\)")
    while i < len(lines):
        ln = lines[i]
        if i == 0:
            out.append(banner)
        elif re.match(r"PRICE CHANGES \(\d+\)$", ln):
            body = []
            i += 1
            while i < len(lines) and lines[i].startswith("- "):
                m = small.search(lines[i])
                if not m or abs(float(m.group(1))) >= EMAIL_MIN_PCT:
                    body.append(lines[i])
                i += 1
            if body:
                out += [f"PRICE CHANGES ({len(body)})"] + body
            elif out and out[-1] == "":
                out.pop()   # no section left: drop its blank separator too
            continue
        else:
            out.append(ln)
        i += 1
    d["report"] = "\n".join(out)
    return d


def build(changes_json, date, outdir):
    """Write both editions and plan.json. An edition is only sent when it has something to say:
    full (owner) = any change or any problem; public (everyone else) = any price/stock/listing change.
    No email at all on a quiet day (owner 2026-10-30)."""
    import os
    os.makedirs(outdir, exist_ok=True)
    d = drop_small_changes(json.load(open(changes_json)))
    plan = {}
    for name, view, send in (("owner", d, has_changes(d) or bool(d.get("issues"))),
                             ("public", public_view(d), has_changes(d))):
        plan[name] = {"send": send}
        if not send:
            continue
        base = os.path.join(outdir, name)
        open(base + ".html", "w").write(render(view, date))
        open(base + ".txt", "w").write((view.get("report") or "") + "\n\n" + TRACKER_LINE + "\n")
        plan[name].update(subject=subject(view, date), html=base + ".html", text=base + ".txt")
    json.dump(plan, open(os.path.join(outdir, "plan.json"), "w"), indent=1, ensure_ascii=False)
    return plan


def build_logo(src, dst=LOGO_FILE):
    from PIL import Image
    im = Image.open(src).convert("RGBA")
    im = im.crop(im.getbbox())
    im = im.resize((240, round(im.height * 240 / im.width)), Image.LANCZOS)
    im.quantize(colors=64, method=Image.FASTOCTREE, dither=Image.FLOYDSTEINBERG).save(dst, optimize=True)
    return dst


if __name__ == "__main__":
    if sys.argv[1] == "--logo":
        print(build_logo(sys.argv[2]))
    elif sys.argv[1] == "--build":
        print(json.dumps(build(sys.argv[2], sys.argv[3], sys.argv[4]), indent=1, ensure_ascii=False))
    else:
        d = json.load(open(sys.argv[1]))
        print(render(d, sys.argv[2] if len(sys.argv) > 2 else "", *sys.argv[3:4]))
