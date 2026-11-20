// Data and business rules ported from the v1 tracker (index.html / trends.html). Same files, same maths.
// Shipping rules per store and province: shipping.json at the site root (also read by pipeline/changes.py for the
// emails). Loaded at run time, so a shipping change needs no rebuild. Filled in by lib/store.js before prices are shown.
export const SHIP = { checked: "", stores: {} };
export const SHIP_URL = import.meta.env.VITE_SHIP || "shipping.json";

export const DATA_BASE = import.meta.env.VITE_DATA || "data/";
export const FEEDBACK = "thediaperaisle@gmail.com";

export const SIZE_ORDER = ["Youth/Junior","XXS","XS","S","S/M","M","M/L","L","L/XL","Regular","XL","XXL","3XL","4XL","5XL","One size"];
export const PKG_RANK = { Sample: 0, Bag: 1, Case: 2 };
export const CATS = {
  diaper: { hash: "diapers", one: "diaper", label: "Diapers", sub: "Tab-style briefs" },
  pullup: { hash: "pullups", one: "pull-up", label: "Pull-ups", sub: "Pull-on protective underwear" },
  booster: { hash: "boosters", one: "booster", label: "Boosters", sub: "Booster pads and doublers" },
};
export const PROVINCES = [["ON","Ontario"],["QC","Quebec"],["BC","British Columbia"],["AB","Alberta"],["MB","Manitoba"],["SK","Saskatchewan"],["NS","Nova Scotia"],["NB","New Brunswick"],["PE","Prince Edward Island"],["NL","Newfoundland and Labrador"]];

const CAP_BINS = { diaper: [1000,2000,3000,4000,5000,6000,8000,10000], pullup: [500,1000,1500,2000,3000], booster: [250,500,1000,2000] };
export function capOptions(cat) {
  const o = []; let lo = 1;
  CAP_BINS[cat].forEach(h => { o.push([`${lo}-${h}`, lo === 1 ? `Up to ${h.toLocaleString()} mL` : `${lo.toLocaleString()}–${h.toLocaleString()} mL`]); lo = h + 1; });
  o.push([`${lo}-`, `${lo.toLocaleString()} mL or more`]);
  return o;
}
export const WAIST_BANDS = [[0,29,'Up to 29"'],[30,35,'30–35"'],[36,41,'36–41"'],[42,47,'42–47"'],[48,53,'48–53"'],[54,59,'54–59"'],[60,999,'60" and up']];

export const BL = "__blank";
// multi-select filters: key in saved state, label, "all" text, blank label, matcher
export const FILTERS = [
  { id: "sz", label: "Size", all: "All sizes", blank: "Blank (no size)", chipsOutside: true, match: (r, v) => v === BL ? (r.cat === "booster" ? r.dl == null : r.size === "One size") : r.size === v },
  { id: "w", label: "Waist / hip", all: "Any waist", blank: "Blank (no waist size)", noBooster: true, match: (r, v) => { if (v === BL) return !r.waist; if (!r.waist) return false; const [lo, hi] = v.split("-").map(Number); return r.waist[0] <= hi && r.waist[1] >= lo; } },
  { id: "p", label: "Package", all: "All packages", blank: "Blank (no pack count)", match: (r, v) => v === BL ? !r.qty : r.pkg === v },
  { id: "a", label: "Capacity", all: "Any capacity", blank: "Blank (no capacity)", match: (r, v) => { if (v === BL) return !r.cap; const [lo, hi] = v.split("-").map(Number); return r.cap >= lo && (!hi || r.cap <= hi); } },
  { id: "b", label: "Brand", all: "All brands", blank: "Blank (no brand)", match: (r, v) => v === BL ? !r.brand : r.brand === v },
  { id: "vr", label: "Colour / scent", all: "All variants", blank: "Blank (no colour or scent)", match: (r, v) => v === BL ? !r.variant : r.variant === v },
];
export function filterOptions(id, cat, rows) {
  if (id === "b") return [...new Set(rows.map(r => r.brand).filter(Boolean))].sort((a, b) => a.localeCompare(b)).map(v => [v, v]);
  if (id === "sz") return [...new Set(rows.map(r => r.size))].sort((a, b) => SIZE_ORDER.indexOf(a) - SIZE_ORDER.indexOf(b)).map(v => [v, v]);
  if (id === "p") return ["Sample","Bag","Case"].filter(v => rows.some(r => r.pkg === v)).map(v => [v, v]);
  if (id === "vr") return [...new Set(rows.map(r => r.variant).filter(Boolean))].sort().map(v => [v, v]);
  if (id === "a") return capOptions(cat);
  if (id === "w") return WAIST_BANDS.map(([lo, hi, l]) => [lo + "-" + hi, l]);
  return [];
}

export const BLANK = () => ({ q: "", b: [], sz: [], p: [], a: [], vr: [], w: [], s: false, best: false, stores: [], sort: { k: "dpd", dir: "asc" } });

// formatting
const CAD2 = new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD", currencyDisplay: "narrowSymbol", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const CAD3 = new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD", currencyDisplay: "narrowSymbol", minimumFractionDigits: 3, maximumFractionDigits: 3 });
export const money = v => v == null ? "—" : CAD2.format(v);
export const unit = v => v == null ? "—" : (v < 1 ? CAD3 : CAD2).format(v);   // under $1 shows 3 decimals: $0.546
const DAY = new Intl.DateTimeFormat("en-CA", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
export const day = d => d ? DAY.format(new Date(d + "T12:00:00Z")) : "—";   // "Oct 31, 2026"
export const inch = v => (Math.round(v * 100) / 100) + '"';
export const pct = v => (v >= 0.05 ? "+" : v <= -0.05 ? "−" : "") + Math.abs(v).toFixed(1) + "%";
const titleCase = s => /[a-z]/.test(s) ? s : s.toLowerCase().replace(/\b\w/g, c => c.toUpperCase()).replace(/\bAm Pm\b/, "AM PM");

// shipping: [[order subtotal from, fee], ...]; fee null = quoted at checkout
export function shipFee(store, subtotal, prov) {
  const rules = SHIP.stores[store]?.rules?.[prov]; if (!rules) return undefined;
  let fee; rules.forEach(([from, f]) => { if (subtotal >= from) fee = f; });
  return fee;
}

// fetch: meta.json always fresh; every other file tagged with the run it belongs to
let V = "?v=" + Date.now();
export async function getJSON(p) {
  const r = await fetch(DATA_BASE + p + V, p === "meta.json" ? { cache: "no-store" } : {});
  if (!r.ok) throw new Error(p + " " + r.status);
  const d = await r.json();
  if (p === "meta.json" && d.lastRun) V = "?v=" + encodeURIComponent(d.lastRun);
  return d;
}
export const loadSet = (name, n) => Promise.all([...Array(n || 0).keys()].map(i => getJSON(name + "-" + i + ".json")));

export function bigSrc(src) {
  return src.replace(/([?&]width=)\d+/, "$1600")
    .replace(/\/stencil\/\d+w\/(.*?)[?&]width=\d+/, "/stencil/608x608/$1")
    .replace(/\._AC_[A-Z]{2}\d+_\./, "._AC_SL600_.");
}

// rows: derived fields + cross-store groups (product + size)
export function prepareRows(docs) {
  const all = [];
  docs.forEach(d => (d.rows || []).forEach(r => all.push({ ...r })));
  all.forEach(r => {
    r.cat = r.cat || (r.style === "Pull-up" ? "pullup" : "diaper");
    r.dname = r.line || titleCase(r.name); r.ck = r.ck || r.id;
    // full name for display: "FitRight Ultra", not "Ultra" with the brand on another line
    r.fname = !r.brand || r.dname.toLowerCase().startsWith(r.brand.toLowerCase()) ? r.dname : `${r.brand} ${r.dname}`;
    const dm = r.dims && r.dims.match(/([\d.]+)\D+([\d.]+)/);
    if (dm) { const a = +dm[1], b = +dm[2]; r.dl = Math.max(a, b); r.dw = Math.min(a, b); }
    r.wlo = r.waist ? r.waist[0] : null;
    r.hay = (r.dname + " " + r.name + " " + r.brand + " " + r.store + " " + (r.variant || "")).toLowerCase();
  });
  const groups = new Map();
  all.forEach(r => { if (!groups.has(r.ck)) groups.set(r.ck, []); groups.get(r.ck).push(r); });
  groups.forEach(g => { const n = new Set(g.map(r => r.store)).size; g.forEach(r => { r.nst = n; }); });
  return { rows: all, groups };
}

// delivered price for the chosen province, then "Lowest" per product + size (in stock, known shipping, no samples)
export function applyShip(rows, groups, prov) {
  rows.forEach(r => {
    r.ship = undefined; r.dpd = null; r.shipq = false; r.dpl = null; r.lowest = false;
    if (!r.qty) return;
    const f = shipFee(r.store, r.price, prov);
    r.ship = f; r.shipq = f === null;
    if (f !== undefined) r.dpd = Math.round((r.price + (f || 0)) / r.qty * 1000) / 1000;
    if (r.dpd != null && r.cap) r.dpl = Math.round(r.dpd / (r.cap / 1000) * 1000) / 1000;
  });
  groups.forEach(g => {
    const live = g.filter(r => r.avail && r.dpd != null && !r.shipq && r.pkg !== "Sample");
    const low = live.length ? Math.min(...live.map(r => r.dpd)) : null;
    g.forEach(r => { r.lowest = r.nst > 1 && low != null && r.avail && !r.shipq && r.pkg !== "Sample" && r.dpd === low; });
  });
}

export function filterRows(rows, F, cat) {
  const q = F.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const picks = FILTERS.filter(f => !(f.noBooster && cat === "booster")).map(f => [f.match, F[f.id] || []]).filter(([, v]) => v.length);
  const stores = new Set(F.stores);
  let list = rows.filter(r => r.cat === cat && (!stores.size || stores.has(r.store)) &&
    picks.every(([m, vals]) => vals.some(v => m(r, v))) && (!F.s || r.avail) && q.every(w => r.hay.includes(w)));
  if (F.best) {
    const top = new Map();
    list.forEach(r => { if (r.dpd == null) return; const t = top.get(r.ck); const better = !t || (r.avail && !t.avail) || (r.avail === t.avail && r.dpd < t.dpd); if (better) top.set(r.ck, r); });
    list = [...top.values()];
  }
  return list;
}

// sort options, grouped; labels use the tab's noun ("per diaper")
export const sortGroups = one => [
  ["Price", [["dpd", `Delivered per ${one}`], ["ppd", `Shelf price per ${one}`], ["dpl", "Delivered per litre of capacity"], ["price", "Pack price"]]],
  ["Product", [["cap", "Capacity"], ["size", "Size"], ["wlo", "Waist"], ["dl", "Length"], ["dw", "Width"], ["qty", "Pieces per pack"], ["pkg", "Pack type"]]],
  ["Name", [["name", "Product name"], ["brand", "Brand"], ["store", "Store"], ["nst", "Number of stores"]]],
];
export const SORTS = []; // kept for imports; use sortGroups
export const ASC_FIRST = ["name","brand","store","size","wlo","pkg","ppd","dpd","ppl","dpl","price","qty"];
export function compare(sort) {
  const { k, dir } = sort, m = dir === "asc" ? 1 : -1;
  return (a, b) => {
    // "+ shipping at checkout" rows leave shipping out, so they never rank among real delivered prices
    if ((k === "dpd" || k === "dpl") && a.shipq !== b.shipq) return a.shipq ? 1 : -1;
    let x = a[k], y = b[k];
    if (k === "size") { x = SIZE_ORDER.indexOf(x); y = SIZE_ORDER.indexOf(y); }
    if (k === "pkg") { x = PKG_RANK[x]; y = PKG_RANK[y]; }
    if (k === "name") { x = a.dname; y = b.dname; }
    const nx = x == null || x === "", ny = y == null || y === "";
    if (nx || ny) return nx === ny ? 0 : nx ? 1 : -1;   // blanks always last
    return (typeof x === "string" ? x.localeCompare(y) : x - y) * m;
  };
}
