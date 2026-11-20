# The Diaper Aisle: design system (v2)

Product: a public, daily-updated price tracker for adult disposable diapers, pull-ups and boosters sold in Canada (CAD).
Users: adults buying incontinence or ABDL products for themselves or someone they care for. Many shop on phones,
many compare dozens of near-identical listings, and some have low vision. Their one question: **"Where is this
product, in my size, cheapest delivered to me?"**

Style: **"Shelf-tag utility"**. A calm, trustworthy data tool (think a grocery flyer cleaned up by a bank), with the
brand's sticker-shelf personality kept in the header, the price tags and the badges, never in the data itself.
No gradients on data, no decoration that competes with numbers, no stock photos.

The tokens live in `src/index.css` (CSS variables, light + dark) and `tailwind.config.js` (names). Components use
token names only, never raw hex.

## 1. Colour

Brand palette (from the logo): aisle ink `#33254c`, shelf purple `#7f749d`, aisle blue `#5ea6db`, aisle teal
`#1f5f80`, sky `#b6d9f3`, frost `#f2f5f8`, price green `#7fc678`, size red `#eb665d`.

Semantic tokens (light / dark). Every text token passes WCAG AA (4.5:1) on every surface it is used on, in both themes; ink and muted pass AAA (7:1). Ratios below are against `bg`.

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg` | `#f3f5f9` | `#17112a` | page |
| `card` | `#ffffff` | `#221a3a` | panels, table, cards |
| `sunken` | `#eef1f6` | `#1c1532` | inputs' wells, table header, key/value tiles |
| `ink` | `#1d1530` (16:1) | `#f5f3fa` (15:1) | text and numbers |
| `muted` | `#4f4867` (7.8:1 on bg) | `#c9c2dc` (9:1) | secondary text: still AAA, small text never goes lighter |
| `line` | `#dcdfe8` | `#3a2f57` | dividers |
| `line-strong` | `#a69fbd` | `#6c608d` | input borders (3:1 against card) |
| `accent` | `#1f5f80` (6.4:1) | `#86c5ef` | links, selected state, primary buttons |
| `on-accent` | `#ffffff` | `#17112a` | text on accent |
| `accent-soft` | `#e3f0f9` | `#22385a` | selected chips, the highlighted price column |
| `good` | `#1f6e35` (5.8:1) | `#8fd694` | price down, free shipping, in stock |
| `good-soft` | `#e2f4e3` | `#1e3a2a` | "Lowest" tag fill |
| `bad` | `#a8302c` (6.2:1) | `#f6a59a` | price up, out of stock, problems |
| `bad-soft` | `#fbe7e5` | `#43202a` | out-of-stock badge fill |
| `warn` | `#7a5200` (6.3:1) | `#f1c46b` | "+ shipping at checkout", stale price |
| `brand-ink` | `#33254c` | `#33254c` | header band (always dark) |
| `brand-blue` | `#5ea6db` | `#5ea6db` | header accents, price-tag edge |

Chart colours (Trends): one fixed slot per store, validated for colour-blind separation on both surfaces (kept
from v1): Healthwick `#2a78d6`, ABUniverse `#eb6834`, MyDips `#1baf7a`, AgeComfort `#eda100`, Rearz `#e87ba4`,
Amazon `#008300`. Direction: cheaper = blue `#2a78d6`, pricier = red `#e34948` (blue/red, not green/red,
so colour-blind users can tell them apart). Colour is never the only signal: arrows (▲ ▼), signs (+ −) and words go with it.

## 2. Type

- **Display:** Rubik 700, uppercase only for the wordmark and section eyebrows (brand voice from v1).
- **Text and numbers:** IBM Plex Sans 400/500/600/700. Chosen for legibility: open apertures, a slashed-free but
  clearly distinct 0/O and 1/l/I, and true tabular figures. All numbers use `tabular-nums` so prices line up.
- **Scale (px / line-height):** 13/18 caption · 14/20 small · 15/22 body · 17/24 price · 20/28 h3 · 24/30 h2 ·
  32/38 h1 (mobile 26/32).
- **Floor:** nothing below **13px**, and 13px is used only for helper captions in `muted` (8.5:1). Table numbers are
  15px; the delivered unit price, the number people decide on, is 17px semibold. Uppercase labels get +0.04em tracking
  and are at least 13px.

## 3. Space, shape, depth

- 4px base grid: 4, 8, 12, 16, 20, 24, 32, 48.
- Page gutter: 16px on phones, 24px from 768px, 32px from 1280px. Max content width 1440px.
- Radius: 8px inputs and chips' inner tiles, 12px cards and the table, 9999px pills and buttons.
- Borders over shadows. One shadow level (`shadow-pop`) for things that float: menus, dialogs, image zoom.
- Touch targets: at least 44 × 44px on touch screens (chips, buttons, rows' tap areas, close buttons).

## 4. Components

- **Header band:** brand-ink background, logo, wordmark, store health pills, updated time. Primary nav (Diapers,
  Pull-ups, Boosters with counts; Trends) sits under it as a segmented tab bar that scrolls sideways on phones.
- **Price tag** (`PriceTag`): the delivered unit price, big, with its shipping note under it (green "Free shipping",
  muted "+$12.00 ship", warn "+ shipping at checkout"). On cards it has a brand-blue left edge, echoing a shelf tag.
- **Badges:** `Lowest` (good-soft, check icon), `Out of stock` / `Backorder` (bad-soft), `Stale price` (warn outline),
  pack (`Bag`, `Case`, `Sample`), variant (outline). All 13px, 600, with text, never colour alone.
- **Filters:** 1280px+: a sticky left rail (288px). Below 1280px: a "Filters" button with the active count opens
  a bottom sheet; results stay visible behind it. Multi-selects are checkbox lists with counts; store choice is chips.
- **Results:** at 1024px+ a sortable table (8 columns, header sticks to the page). Below 1024px, one card per listing with the
  price tag on the right and specs as a labelled list. A "Sort by" select works at every size.
- **Dialog:** product detail. Centred modal at 768px+, full-height sheet on phones. Comparison table becomes stacked
  rows on phones.
- **Charts:** inline SVG, 13px axis labels, direct labels at line ends, "Show as table" under each chart, a keyboard-
  reachable tooltip.
- **Focus:** a 2px `accent` ring with 2px offset on every interactive element. Never removed.

## 5. Motion

150ms ease-out for hover and colour, 200ms for sheets and dialogs. Everything is off under `prefers-reduced-motion`.

## 6. Voice

Plain, short, Canadian spelling (colour). Says what a number means ("Delivered = price + shipping for just this
pack ÷ pieces"). No hype, no "everything worked" lines.

## 7. Anti-patterns (don't)

- Text below 13px, or muted text lighter than the `muted` token.
- Hiding the delivered price behind a hover.
- A 16-column table that needs sideways scrolling on a laptop.
- Green vs red as the only price-direction signal.
- Emoji as icons (use the inline SVG icon set in `src/components/Icon.jsx`).
