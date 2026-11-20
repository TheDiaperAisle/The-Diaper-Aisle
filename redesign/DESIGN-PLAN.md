# Design plan (v2), within DESIGN-SYSTEM.md

## Brief
Make The Diaper Aisle look better and be easier to use, without losing anything the current tracker does, and keep
every number and small text easy to read. React + Tailwind, live data from `data/`, works at every width.

## What the current pages get wrong (audit of v1)
1. **Phones:** the price table has 17 columns and a 1240px minimum width, so on a 390px phone it is a sideways-scrolling
   spreadsheet. Most readers shop on phones.
2. **Laptops:** even at 1440px the table scrolls sideways. The number that matters (delivered $/piece) sits in
   column 12 of 17.
3. **Small text:** 11-12px uppercase labels, 11px shipping notes and 10px chart labels. Hard to read, especially for
   older readers.
4. **Filters** take a full-width band of 9 controls plus a row of store chips before any result is visible.
5. **No hierarchy in a row:** product, brand, store, size, pack and five prices all have the same weight.

## Direction: "shelf-tag utility"
- **Lead with the answer.** Each listing shows one big number: the delivered price per piece to the reader's province,
  with the shipping note under it. Shelf price and $/L sit beside it as secondary figures.
- **One row = one decision.** Product name (with brand, variant, stock badges) is one column. Store, size + waist
  and pack + quantity are compact columns. 9 columns, not 17. Nothing scrolls sideways at 1024px and up.
- **Cards on phones.** Below 1024px each listing is a card: thumbnail, name, badges, a price tag on the right, then a
  3-up spec strip (Size · Pack · Capacity). The whole card opens details. "View at store" is its own 44px link.
- **Filters in a rail / sheet.** Desktop: sticky left rail. Phone: "Filters (3)" button opens a bottom sheet. The search
  box and Sort stay visible above results on every size. Active filters show as removable chips.
- **Same features as v1:** three category tabs with counts, search, brand / size / package / colour / capacity / waist
  multi-selects with Blank options and counts, ship-to province, in-stock only, lowest per product + size, store chips,
  sort on every column, 100-at-a-time paging, saved filters per tab, product detail with sizes, cross-store comparison,
  price history, shipping notes, report-a-problem links, thumbnail zoom, store health and Trends with all six views.
- **Readable numbers.** IBM Plex Sans with tabular figures; 15px for table numbers, 17px semibold for the deciding
  price, 13px floor for captions; no all-caps under 13px.
- **Brand kept in the frame, not the data.** Ink header band with the sticker logo; shelf-tag edge on prices; the
  "Lowest" badge uses price green. Data area is white/neutral.

## Pages
1. **Tracker** (`#/diapers`, `#/pullups`, `#/boosters`): header → tabs → toolbar (search, sort, filters button on
   mobile, result count) → rail + results → feedback card → method notes.
2. **Product detail** (dialog over the tracker): header with photo, key facts grid, other sizes, every store for this
   size, price history chart, shipping note, actions.
3. **Trends** (`#/trends`): header → category + period segmented controls → 4 stat tiles → price index by store (line)
   → brand change (diverging bars) + store median (bars) → changes per day (columns) → biggest drops / increases.

## Check against the brief
| Brief item | How the plan meets it |
|---|---|
| Better visual design | Clear hierarchy, one hero number per row, calmer neutral data area, brand in frame |
| Within the design system | All colours / type / radii are tokens from DESIGN-SYSTEM.md |
| Numbers and small text readable | 13px floor, 15/17px numbers, tabular figures, AAA muted text |
| React + Tailwind | Vite + React 18 + Tailwind 3, static build in `/v2/` |
| Populated screens | Reads the live published `data/` (≈1,670 real listings, real history) |
| Fully responsive | Cards < 1024px, rail ≥ 1024px, checked at 390px and 1440px |
| Every page | Tracker (3 tabs), product dialog, image viewer, Trends |

## Pass 2: frontend-design review (after the ui-ux-pro-max design system)

### Review of pass 1 against the brief and the "templated" checklist
| Pass 1 had | Why it reads as a default | Revision |
|---|---|---|
| Uppercase tracked labels on every table header and caption | Template chrome; harder to read than sentence case | Sentence-case headers, 14px semibold; no all-caps anywhere except the logo wordmark |
| Meta strings joined with middle dots ("FitRight · Amazon", "Bag of 20 · $56.52") | Template chrome; packs facts into one hard-to-scan line | Facts get their own line or label; dots only inside the store comparison where space is tight |
| Price block = tinted rounded card with a blue left bar | "Accent bar on a rounded card" is a stock look | **The one bold element: a Canadian shelf label.** Ink-outlined box, ink header strip ("Delivered, per diaper"), the price large under it, shipping line at the foot. It is what shoppers already read in a store aisle, so it carries the brand idea (the aisle) and the number people decide on |
| Every block (rail, table, feedback, notes, every Trends chart) a white rounded card with a border | SaaS card kit; flattens hierarchy | Cards only where an object is separate: listing cards, the table, dialogs, charts. Filter rail sits on the page ground with dividers; feedback and method notes are plain sections under a rule |
| Four identical big-number tiles at the top of Trends | Default dashboard opener | One stat strip with dividers: the four figures read as one sentence about the period |
| 15px body | ui-ux-pro-max `readable-font-size` | 16px body and inputs |
| Store lines distinguished by hue only | ui-ux-pro-max chart rule | Solid / dashed / dotted strokes, legend shows the stroke |

### Wireframe: listing card (phone)
```
┌───────────────────────────────────────┐
│ [img] Ultra                            │
│       FitRight                         │
│       Amazon, 2 stores   ✓ Lowest      │
│ ┌─────────────────────┐  Pack $43.70   │
│ │ Delivered, per diaper│  $0.546 shelf  │  <- shelf label (ink box, ink strip)
│ │ $0.546              │  ↑ was $43.23  │
│ │ Free shipping       │                │
│ └─────────────────────┘                │
│  Size L     Case of 80     Capacity —  │
│  Fits 44–56" waist                     │
│ Compare 2 stores        View at Amazon │
└───────────────────────────────────────┘
```
Alignment: everything left-aligned; numbers right-aligned in table columns only.

### Check against the brief
Better visual design (one memorable, subject-specific element; less chrome), inside the design system (tokens unchanged, decisions logged in DESIGN-SYSTEM.md §0), numbers and small text readable (16px body, sentence-case labels, 13px floor kept), every page (tracker tabs, card, table, dialog, Trends).
