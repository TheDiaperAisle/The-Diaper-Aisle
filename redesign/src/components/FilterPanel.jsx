import { useId, useState } from "react";
import Icon from "./Icon";
import { FILTERS, BL, PROVINCES, filterOptions } from "../lib/data";

function Toggle({ checked, onChange, children, hint }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-lg py-2">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} className="mt-0.5 h-5 w-5 shrink-0 accent-[rgb(var(--accent))]" />
      <span><span className="block font-medium">{children}</span>{hint && <span className="block text-cap text-muted">{hint}</span>}</span>
    </label>
  );
}

function Group({ f, cat, rows, value, onChange, defaultOpen }) {
  const id = useId();
  const opts = [[BL, f.blank], ...filterOptions(f.id, cat, rows)]
    .map(([v, l]) => [v, l, rows.filter(r => f.match(r, v)).length])
    .filter(([v, , n]) => n || v === BL || value.includes(v));
  const set = new Set(value);
  const toggle = v => onChange(set.has(v) ? value.filter(x => x !== v) : [...value, v]);
  const [all, setAll] = useState(false);
  const SHOW = 8;   // long lists show 8, then "Show all": no scroll box inside the scrolling sheet
  const shown = all || opts.length <= SHOW + 2 ? opts : opts.filter(([v], i) => i < SHOW || set.has(v));
  return (
    <details className="group border-t border-line" open={defaultOpen || value.length > 0}>
      <summary className="flex min-h-[48px] cursor-pointer list-none items-center gap-2 py-2 font-semibold [&::-webkit-details-marker]:hidden">
        <span className="flex-1">{f.label}</span>
        {value.length > 0 && <span className="num rounded-full bg-accent px-2 text-cap font-semibold text-on-accent">{value.length}</span>}
        <Icon name="chev" className="text-muted transition-transform group-open:rotate-180" />
      </summary>
      <div className="pb-3">
        {value.length > 0 && <button type="button" className="link mb-1 text-sm" onClick={() => onChange([])}>Clear {f.label.toLowerCase()}</button>}
        <ul role="group" aria-label={f.label}>
          {shown.map(([v, l, n]) => (
            <li key={v}>
              <label htmlFor={id + v} className={"flex min-h-[40px] cursor-pointer pointer-coarse:min-h-[44px] items-center gap-3 rounded-lg px-2 hover:bg-sunken " + (v === BL ? "italic text-muted" : "")}>
                <input id={id + v} type="checkbox" checked={set.has(v)} onChange={() => toggle(v)} className="h-[18px] w-[18px] shrink-0 accent-[rgb(var(--accent))]" />
                <span className="flex-1 text-sm">{l}</span>
                <span className="num text-cap text-muted">{n.toLocaleString()}</span>
              </label>
            </li>
          ))}
        </ul>
        {shown.length < opts.length && <button type="button" className="link mt-1 min-h-[44px] text-sm" onClick={() => setAll(true)}>Show all {opts.length} {f.label.toLowerCase()} options</button>}
      </div>
    </details>
  );
}

export default function FilterPanel({ cat, rows, F, set, prov, setProv, stores }) {
  const counts = {}; rows.forEach(r => { counts[r.store] = (counts[r.store] || 0) + 1; });
  const picked = new Set(F.stores);
  return (
    <div className="grid gap-1">
      <label className="grid gap-1.5 pb-3">
        <span className="font-semibold flex items-center gap-2"><Icon name="truck" className="text-muted" /> Ship to</span>
        <select className="input" value={prov} onChange={e => setProv(e.target.value)}>
          {PROVINCES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <span className="text-cap text-muted">Delivered prices include each store's shipping to this province.</span>
      </label>
      <div className="border-t border-line py-2">
        <Toggle checked={F.s} onChange={v => set({ s: v })}>In stock only</Toggle>
        <Toggle checked={F.best} onChange={v => set({ best: v })} hint="One row per product and size: the cheapest delivered">Lowest price only</Toggle>
      </div>
      <fieldset className="border-t border-line py-3">
        <legend className="sr-only">Stores</legend>
        <div className="mb-2 flex min-h-[28px] items-center justify-between font-semibold"><span aria-hidden="true">Stores</span>
          {picked.size > 0 && <button type="button" className="link text-sm" onClick={() => set({ stores: [] })}>Show all stores</button>}</div>
        <div className="flex flex-wrap gap-2">
          {stores.filter(n => counts[n] || picked.has(n)).map(n => {
            const on = picked.has(n);
            return (
              <button key={n} type="button" aria-pressed={on}
                onClick={() => set({ stores: on ? F.stores.filter(x => x !== n) : [...F.stores, n] })}
                className={"chip " + (on ? "border-accent bg-accent text-on-accent" : "border-line-strong bg-card text-ink hover:border-accent")}>
                {n} <span className={"num text-cap " + (on ? "opacity-90" : "text-muted")}>{counts[n] || 0}</span>
              </button>
            );
          })}
        </div>
      </fieldset>
      {FILTERS.filter(f => !(f.noBooster && cat === "booster") && !(f.chipsOutside && cat !== "booster")).map((f, i) => (
        <Group key={f.id + cat} f={f} cat={cat} rows={rows} value={F[f.id] || []} defaultOpen={i === 0} onChange={v => set({ [f.id]: v })} />
      ))}
    </div>
  );
}
