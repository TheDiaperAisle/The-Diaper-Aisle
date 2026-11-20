import { useEffect, useMemo, useRef, useState, useDeferredValue } from "react";
import Icon from "../components/Icon";
import FilterPanel from "../components/FilterPanel";
import ProductDialog from "../components/ProductDialog";
import { ResultsTable, ResultCards, nextSort } from "../components/Results";
import { ImageProvider } from "../components/bits";
import { CATS, BLANK, BL, FILTERS, SORTS, FEEDBACK, PROVINCES, filterOptions, filterRows, applyShip, compare } from "../lib/data";
import { useLocal, useMedia } from "../lib/store";

const PAGE = 100;
function seed() {   // carry over filters saved by the current tracker (same site) the first time
  const s = { prov: "ON", tabs: { diaper: BLANK(), pullup: BLANK(), booster: BLANK() } };
  try {
    const f = JSON.parse(localStorage.getItem("dipaisle.f2") || "null");
    if (f) { if (f.prov) s.prov = f.prov; Object.keys(s.tabs).forEach(c => { if (f.tabs?.[c]) s.tabs[c] = { ...BLANK(), ...f.tabs[c] }; }); }
  } catch { /* none */ }
  return s;
}

export default function Tracker({ cat, data }) {
  const [st, setSt] = useLocal("dipaisle.v2", seed());
  const F = { ...BLANK(), ...st.tabs[cat] };
  const set = patch => setSt(s => ({ ...s, tabs: { ...s.tabs, [cat]: { ...BLANK(), ...s.tabs[cat], ...patch } } }));
  const setProv = prov => setSt(s => ({ ...s, prov }));
  const [limit, setLimit] = useState(PAGE);
  const [openId, setOpenId] = useState(null);
  const [sheet, setSheet] = useState(false);
  const wide = useMedia("(min-width: 1024px)");    // table instead of cards
  const rail = useMedia("(min-width: 1280px)");    // filters in a side rail instead of a sheet
  const one = CATS[cat].one;
  const q = useDeferredValue(F.q);

  useEffect(() => { setLimit(PAGE); }, [cat, q, JSON.stringify(F), st.prov]);   // eslint-disable-line
  // delivered prices depend on the province
  const shipped = useMemo(() => { applyShip(data.rows, data.groups, st.prov); return data.rows.length; }, [data.rows, data.groups, st.prov]);
  const catRows = useMemo(() => data.rows.filter(r => r.cat === cat), [data.rows, cat, shipped]);
  const sort = cat !== "booster" && ["dl", "dw"].includes(F.sort.k) ? { k: "dpd", dir: "asc" } : F.sort;
  const list = useMemo(() => filterRows(data.rows, { ...F, q }, cat).sort(compare(sort)),
    [data.rows, cat, shipped, q, JSON.stringify({ ...F, q: "" }), sort.k, sort.dir]);   // eslint-disable-line
  const stores = useMemo(() => [...new Set([...catRows.map(r => r.store), ...Object.keys(data.meta?.stores || {})])].sort(), [catRows, data.meta]);
  const r = openId ? data.rows.find(x => x.id === openId) : null;

  // active filters as removable chips
  const chips = [];
  if (F.q) chips.push([`“${F.q}”`, () => set({ q: "" })]);
  FILTERS.filter(f => !(f.noBooster && cat === "booster")).forEach(f => (F[f.id] || []).forEach(v => {
    const label = v === BL ? f.blank : (filterOptions(f.id, cat, catRows).find(o => o[0] === v)?.[1] || v);
    chips.push([label, () => set({ [f.id]: F[f.id].filter(x => x !== v) })]);
  }));
  F.stores.forEach(s => chips.push([s, () => set({ stores: F.stores.filter(x => x !== s) })]));
  if (F.s) chips.push(["In stock only", () => set({ s: false })]);
  if (F.best) chips.push(["Lowest price only", () => set({ best: false })]);
  const nActive = chips.length - (F.q ? 1 : 0);
  const clearAll = () => set({ ...BLANK(), sort: F.sort });

  const sorts = SORTS.filter(([k]) => cat === "booster" ? !["size", "wlo"].includes(k) : !["dl", "dw"].includes(k));
  const sortLabel = SORTS.find(s => s[0] === sort.k)?.[1].toLowerCase();
  const panel = <FilterPanel cat={cat} rows={catRows} F={F} set={set} prov={st.prov} setProv={setProv} stores={stores} />;
  const provName = PROVINCES.find(p => p[0] === st.prov)?.[1];

  return (
    <ImageProvider thumbs={data.thumbs} big={data.big}>
      <main id="main" className="mx-auto max-w-page px-4 pb-16 pt-5 md:px-6 md:pt-7 xl:px-8">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-x-6 gap-y-1">
          <div>
            <h1 className="font-display text-[26px] leading-8 md:text-h1 font-bold tracking-tight">{CATS[cat].label}</h1>
            <p className="text-muted">{CATS[cat].sub}. Prices in CAD before tax, delivered to <strong className="font-semibold text-ink">{provName}</strong>.</p>
          </div>
        </div>

        {/* toolbar */}
        <div className="sticky top-0 z-20 -mx-4 mb-3 border-b border-line bg-bg/95 px-4 py-3 backdrop-blur md:-mx-6 md:px-6 lg:static lg:mx-0 lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-0">
          <div className="flex flex-wrap items-center gap-2">
            <label className="relative min-w-0 basis-full sm:basis-auto sm:flex-[1_1_260px]">
              <span className="sr-only">Search products</span>
              <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input type="search" value={F.q} onChange={e => set({ q: e.target.value })} placeholder="Search product, brand or store" className="input !pl-10" autoComplete="off" />
            </label>
            <button type="button" onClick={() => setSheet(true)} className="btn-ghost xl:hidden">
              <Icon name="filter" /> Filters{nActive > 0 && <span className="num rounded-full bg-accent px-2 text-cap text-on-accent">{nActive}</span>}
            </button>
            <label className="flex min-w-0 flex-1 items-center gap-2 lg:flex-none">
              <span className="sr-only whitespace-nowrap text-sm font-semibold text-muted sm:not-sr-only">Sort</span>
              <select className="input lg:w-64" value={sort.k} onChange={e => set({ sort: nextSort({ k: "" }, e.target.value) })}>
                {sorts.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
              <button type="button" className="btn-ghost !min-w-[44px] !px-0" onClick={() => set({ sort: { k: sort.k, dir: sort.dir === "asc" ? "desc" : "asc" } })}
                aria-label={sort.dir === "asc" ? "Sorted low to high. Switch to high to low" : "Sorted high to low. Switch to low to high"} title={sort.dir === "asc" ? "Low to high" : "High to low"}>
                <Icon name={sort.dir === "asc" ? "up" : "down"} />
              </button>
            </label>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[288px_minmax(0,1fr)]">
          {rail && (
            <aside aria-label="Filters" className="sticky top-4 self-start">
              <div className="max-h-[calc(100dvh-32px)] overflow-y-auto pb-2 pr-2">
                <div className="mb-3 flex items-center justify-between"><h2 className="text-h3 font-bold">Filters</h2>
                  {nActive > 0 && <button type="button" className="link text-sm" onClick={clearAll}>Clear all</button>}</div>
                {panel}
              </div>
            </aside>
          )}

          <section aria-labelledby="res-h" className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <h2 id="res-h" className="mr-1 text-base text-muted" aria-live="polite">
                {data.status !== "ready" ? (data.status === "error" ? "Prices could not be loaded." : "Loading listings…")
                  : <><strong className="num font-semibold text-ink">{list.length.toLocaleString()}</strong> of <span className="num">{catRows.length.toLocaleString()}</span> {one} listings, sorted by {sortLabel}, {sort.dir === "asc" ? "low to high" : "high to low"}</>}
              </h2>
              {chips.map(([l, rm], i) => (
                <button key={i} type="button" onClick={rm} className="chip border-accent/40 bg-accent-soft text-ink hover:border-accent" aria-label={`Remove filter ${l}`}>
                  {l} <Icon name="x" size={14} />
                </button>
              ))}
              {chips.length > 1 && <button type="button" className="link min-h-[36px] text-sm" onClick={() => { clearAll(); }}>Clear all</button>}
            </div>

            {data.status === "loading" && <Skeleton />}
            {data.status === "ready" && !list.length && (
              <div className="card grid justify-items-center gap-3 px-6 py-14 text-center">
                <p className="text-h3 font-semibold">No listings match</p>
                <p className="max-w-md text-muted">Try removing a filter or changing the search. Filters are kept separately for each tab.</p>
                <button type="button" className="btn-primary" onClick={clearAll}>Clear filters</button>
              </div>
            )}
            {list.length > 0 && (wide
              ? <ResultsTable list={list.slice(0, limit)} cat={cat} one={one} sort={sort} onSort={k => set({ sort: nextSort(sort, k) })} onOpen={setOpenId} />
              : <ResultCards list={list.slice(0, limit)} one={one} onOpen={setOpenId} />)}
            {list.length > limit && (
              <div className="mt-4 grid justify-items-center gap-2">
                <button type="button" className="btn-primary" onClick={() => setLimit(l => l + PAGE)}>Show {Math.min(PAGE, list.length - limit)} more</button>
                <span className="num text-cap text-muted">Showing {limit.toLocaleString()} of {list.length.toLocaleString()}</span>
              </div>
            )}
          </section>
        </div>

        <Feedback />
        <Method one={one} />
        <p className="mt-6 text-sm text-muted">This is the new design, in review. <a className="link" href={import.meta.env.VITE_OLD_URL || "../index.html"}>Open the current tracker</a>.</p>
      </main>

      {!rail && (
        <FilterSheet open={sheet} onClose={() => setSheet(false)} count={list.length} one={one} nActive={nActive} clearAll={clearAll}>{panel}</FilterSheet>
      )}
      <ProductDialog r={r} data={data} prov={st.prov} onOpen={setOpenId} onClose={() => setOpenId(null)} />
    </ImageProvider>
  );
}

function FilterSheet({ open, onClose, count, one, nActive, clearAll, children }) {
  const ref = useRef(null);
  useEffect(() => { const d = ref.current; if (open && !d.open) d.showModal(); if (!open && d.open) d.close(); }, [open]);
  return (
    <dialog ref={ref} onClose={onClose} onClick={e => e.target === ref.current && onClose()} aria-labelledby="fs-h"
      className="m-0 mt-auto h-[92dvh] max-h-[92dvh] w-full max-w-full overflow-hidden rounded-t-2xl bg-card p-0 text-ink shadow-pop md:mx-auto md:max-w-[560px]">
      <div className="anim-in flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-line px-4 py-2">
          <h2 id="fs-h" className="text-h3 font-bold">Filters</h2>
          <div className="flex items-center gap-1">
            {nActive > 0 && <button type="button" className="link min-h-[44px] px-2 text-sm" onClick={clearAll}>Clear all</button>}
            <button type="button" className="btn-ghost !px-3" onClick={onClose} aria-label="Close filters"><Icon name="x" /></button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-4 pt-3">{children}</div>
        <div className="border-t border-line p-3 pb-[max(12px,env(safe-area-inset-bottom))]">
          <button type="button" className="btn-primary w-full" onClick={onClose}>Show <span className="num">{count.toLocaleString()}</span> {one} listings</button>
        </div>
      </div>
    </dialog>
  );
}

function Skeleton() {
  return (
    <div className="grid gap-3" aria-hidden="true">
      {[0, 1, 2, 3, 4].map(i => <div key={i} className="card h-24 animate-pulse bg-sunken" />)}
    </div>
  );
}

function Feedback() {
  const [copied, setCopied] = useState("");
  const copy = async () => {
    try { await navigator.clipboard.writeText(FEEDBACK); setCopied("Copied"); } catch { setCopied("Select the address and copy it"); }
    setTimeout(() => setCopied(""), 2500);
  };
  return (
    <section aria-labelledby="fb-h" className="mt-12 flex flex-wrap items-center justify-between gap-5 border-t-2 border-ink pt-6">
      <div className="max-w-[62ch]">
        <h2 id="fb-h" className="text-h3 font-bold">Help make the tracker better</h2>
        <p className="mt-1 text-muted">Spotted a price, pack size or stock status that looks off, or have an idea for a feature? Prices are checked daily, but mistakes slip through. Tell us which listing is wrong or what you'd like added.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="select-all font-semibold break-all">{FEEDBACK}</span>
        <a className="btn-primary" href={`https://mail.google.com/mail/?view=cm&fs=1&to=${FEEDBACK}&su=Tracker%20feedback`} target="_blank" rel="noopener"><Icon name="mail" size={16} /> Email us in Gmail</a>
        <button type="button" className="btn-ghost" onClick={copy}><Icon name="copy" size={16} /> <span aria-live="polite">{copied || "Copy address"}</span></button>
      </div>
    </section>
  );
}

function Method({ one }) {
  return (
    <details className="mt-6 border-t border-line pt-5">
      <summary className="flex cursor-pointer items-center gap-2 font-semibold"><Icon name="info" className="text-muted" /> How prices are worked out</summary>
      <div className="mt-3 grid max-w-[80ch] gap-3 text-muted">
        <p><strong className="text-ink">Shelf/{one}</strong> = package price ÷ pieces in the package.</p>
        <p><strong className="text-ink">Delivered/{one}</strong> = (package price + the store's cheapest standard shipping for an order of just that package to your province) ÷ pieces, before tax. Bags and samples often fall under free-shipping minimums, so their delivered price can be well above the shelf price; a bigger order spreads the shipping. "+ shipping at checkout" means the store quotes shipping at checkout, so the number shown leaves it out.</p>
        <p><strong className="text-ink">Capacity</strong> is the maker's stated absorbency in millilitres, from product pages (not lab-tested), shared across every store that sells the same product. Blank means no store publishes one. <strong className="text-ink">$/L</strong> = delivered price per piece ÷ capacity in litres: lower means more absorbency per dollar.</p>
        <p><strong className="text-ink">Lowest</strong> marks the cheapest in-stock delivered price for the same product and size across stores (samples left out).</p>
        <p>Walmart prices are checked by hand about every two weeks; every other store is checked daily.</p>
      </div>
    </details>
  );
}
