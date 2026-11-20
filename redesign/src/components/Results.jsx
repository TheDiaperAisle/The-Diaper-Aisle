import Icon from "./Icon";
import { Badge, StockBadges, CompareNote, ShipNote, Delta, Dash, Thumb, ShelfLabel } from "./bits";
import { unit, money, inch, ASC_FIRST } from "../lib/data";

const Name = ({ r }) => (
  <>
    <span translate="no" className="font-semibold text-ink">{r.fname}</span>
    {r.variant && <span className="ml-1.5 align-[1px]"><Badge tone="outline">{r.variant}</Badge></span>}
    {r.cat === "booster" && r.size !== "One size" && <span className="ml-1.5 align-[1px]"><Badge tone="outline">Size {r.size}</Badge></span>}
  </>
);
const sizeText = r => r.cat === "booster"
  ? (r.dl != null ? `${inch(r.dl)} × ${inch(r.dw)}` : null)
  : r.size;
const waistText = r => r.waist ? `${r.waist[0]}–${r.waist[1]}" waist` : null;
const StoreLink = ({ r, className = "" }) => (
  <a href={r.url} target="_blank" rel="noopener" onClick={e => e.stopPropagation()} className={"link inline-flex items-center gap-1 whitespace-nowrap " + className}>
    Buy at {r.store}<Icon name="ext" size={15} /><span className="sr-only"> (opens in a new tab)</span>
  </a>
);

// ---------- desktop table ----------
function Th({ k, sort, onSort, children, num, title, className = "" }) {
  const on = sort.k === k;
  return (
    <th scope="col" aria-sort={on ? (sort.dir === "asc" ? "ascending" : "descending") : undefined} className={"sticky top-0 z-10 bg-sunken p-0 font-normal " + className}>
      <button type="button" onClick={() => onSort(k)} title={title}
        className={"flex w-full items-center gap-1 whitespace-nowrap px-2.5 py-3 text-left text-sm font-semibold hover:text-ink " + (num ? "justify-end text-right " : "") + (on ? "text-ink" : "text-muted")}>
        {children}
        {on && <Icon name={sort.dir === "asc" ? "up" : "down"} size={14} />}
      </button>
    </th>
  );
}

export function ResultsTable({ list, cat, one, sort, onSort, onOpen }) {
  const booster = cat === "booster";
  const p = { sort, onSort };
  return (
    <div className="card overflow-x-clip">   {/* clip, not auto: keeps the header sticky to the page */}
      <table className="w-full border-collapse text-base">
        <caption className="sr-only">Listings. Select a row for details, other stores and price history.</caption>
        <thead className="border-b border-line-strong">
          <tr>
            <Th k="name" {...p} className="pl-4">Product</Th>
            <Th k="store" {...p}>Store</Th>
            {booster ? <Th k="dl" {...p} title="Length × width, in inches">L × W</Th> : <Th k="size" {...p}>Size</Th>}
            <Th k="qty" {...p} num>Pack</Th>
            <Th k="price" {...p} num title="Package price; shelf price per piece under it">Price</Th>
            <Th k="dpd" {...p} num className="!bg-accent-soft" title="Price plus shipping for just this pack to your province, divided by pieces"><span className="text-right leading-tight">Delivered<span className="block font-normal">per {one}</span></span></Th>
            <Th k="cap" {...p} num title="Maker's stated capacity; $/L uses the delivered price">Capacity</Th>
            <th scope="col" className="sticky top-0 z-10 bg-sunken pr-4"><span className="sr-only">Store link</span></th>
          </tr>
        </thead>
        <tbody>
          {list.map(r => (
            <tr key={r.id} onClick={() => onOpen(r.id)} className="cursor-pointer border-b border-line last:border-0 hover:bg-sunken/70 [&>td]:align-top">
              <td className="py-3 pl-4 pr-2.5">
                <div className="flex min-w-[220px] gap-3">
                  <Thumb r={r} size={52} />
                  <div className="min-w-0">
                    <button type="button" onClick={e => { e.stopPropagation(); onOpen(r.id); }} className="rounded text-left leading-snug underline-offset-2 hover:underline"><Name r={r} /></button>
                    {(!r.avail || r.stale) && <div className="mt-1 flex flex-wrap gap-1"><StockBadges r={r} /></div>}
                  </div>
                </div>
              </td>
              <td className="px-2.5 py-3">
                <div className="whitespace-nowrap">{r.store}</div>
                {r.nst > 1 && <button type="button" onClick={e => { e.stopPropagation(); onOpen(r.id); }} className="link whitespace-nowrap text-sm">Compare {r.nst} stores</button>}
              </td>
              <td className="px-2.5 py-3">
                {sizeText(r) ? <span className="num whitespace-nowrap font-medium">{sizeText(r)}</span> : <Dash />}
                {!booster && waistText(r) && <div className="num whitespace-nowrap text-sm text-muted">{waistText(r)}</div>}
              </td>
              <td className="whitespace-nowrap px-2.5 py-3 text-right">
                <div className="num font-medium">{r.qty ?? <Dash title="No pack count" />}</div>
                <div className="text-sm text-muted">{r.pkg}</div>
              </td>
              <td className="whitespace-nowrap px-2.5 py-3 text-right">
                <div className="num">{money(r.price)}</div>
                <div className="num text-sm text-muted">{unit(r.ppd)}/{one}</div>
                <Delta r={r} compact />
              </td>
              <td className="bg-accent-soft/60 px-2.5 py-3 text-right">
                <div className="num whitespace-nowrap text-price font-bold">{r.dpd != null ? unit(r.dpd) : <Dash title="No shipping data" />}</div>
                <ShipNote r={r} className="block whitespace-nowrap" />
                <div className="mt-1"><CompareNote r={r} /></div>
              </td>
              <td className="whitespace-nowrap px-2.5 py-3 text-right">
                <div className="num">{r.cap ? r.cap.toLocaleString() + " mL" : <Dash title="No store publishes a capacity" />}</div>
                {r.dpl != null && <div className="num text-sm text-muted">{money(r.dpl)}/L</div>}
              </td>
              <td className="py-2 pl-1 pr-3 text-right">
                <a href={r.url} target="_blank" rel="noopener" onClick={e => e.stopPropagation()}
                  className="inline-flex min-h-[44px] items-center gap-1 whitespace-nowrap rounded-full px-2 text-sm font-semibold text-accent hover:bg-accent-soft">
                  Store page<Icon name="ext" size={15} /><span className="sr-only"> for {r.fname} at {r.store} (opens in a new tab)</span>
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------- phone / tablet cards ----------
function Spec({ k, children }) {
  return (
    <div className="min-w-0 px-2 py-2 first:pl-0">
      <dt className="text-cap text-muted">{k}</dt>
      <dd className="num truncate font-semibold">{children}</dd>
    </div>
  );
}

export function ResultCards({ list, one, onOpen }) {
  return (
    <ul className="grid gap-3 md:grid-cols-2">
      {list.map(r => (
        <li key={r.id} className="card flex flex-col overflow-hidden [contain-intrinsic-size:auto_300px] [content-visibility:auto]">
          <div className="flex gap-3 p-3 pb-2">
            <Thumb r={r} size={64} />
            <div className="min-w-0 flex-1">
              <button type="button" onClick={() => onOpen(r.id)} className="block min-h-[44px] w-full rounded text-left leading-snug">
                <Name r={r} />
              </button>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm"><span className="font-medium">{r.store}</span><CompareNote r={r} /><StockBadges r={r} /></div>
            </div>
          </div>
          <div className="mx-3 flex items-start justify-between gap-3">
            <ShelfLabel r={r} one={one} />
            <div className="pt-1 text-right">
              <div className="text-cap text-muted">Pack price</div>
              <div className="num font-semibold">{money(r.price)}</div>
              <div className="num text-cap text-muted">{unit(r.ppd)}/{one} shelf</div>
              <Delta r={r} />
            </div>
          </div>
          <dl className="mx-3 mt-3 grid grid-cols-3 divide-x divide-line border-y border-line">
            <Spec k={r.cat === "booster" ? "L × W" : "Size"}>{sizeText(r) || "—"}</Spec>
            <Spec k="Pack">{r.qty ? `${r.pkg} of ${r.qty}` : r.pkg}</Spec>
            <Spec k="Capacity">{r.cap ? `${r.cap.toLocaleString()} mL` : "—"}</Spec>
          </dl>
          {((r.cat !== "booster" && r.waist) || r.dpl != null) && <p className="num mx-3 mt-1.5 flex flex-wrap gap-x-4 text-sm text-muted">{r.cat !== "booster" && r.waist && <span>Fits {r.waist[0]}–{r.waist[1]}" waist</span>}{r.dpl != null && <span>{money(r.dpl)} per litre delivered</span>}</p>}
          <div className="mt-auto flex items-center justify-between gap-2 px-3 pb-1 pt-1">
            <button type="button" onClick={() => onOpen(r.id)} className="inline-flex min-h-[44px] items-center text-sm font-semibold text-accent">
              {r.nst > 1 ? `Compare ${r.nst} stores` : "Details and price history"}
            </button>
            <StoreLink r={r} className="min-h-[44px] text-sm" />
          </div>
        </li>
      ))}
    </ul>
  );
}

export const nextSort = (sort, k) => sort.k === k ? { k, dir: sort.dir === "asc" ? "desc" : "asc" } : { k, dir: ASC_FIRST.includes(k) ? "asc" : "desc" };
