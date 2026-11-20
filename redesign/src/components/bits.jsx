import { createContext, useContext, useRef, useState, useEffect } from "react";
import Icon from "./Icon";
import { SHIP, unit, money } from "../lib/data";

export function Badge({ tone = "neutral", children, title }) {
  const t = {
    neutral: "bg-sunken text-ink border-line",
    outline: "bg-transparent text-ink border-line-strong",
    good: "bg-good-soft text-good border-good/40",
    bad: "bg-bad-soft text-bad border-bad/40",
    warn: "bg-transparent text-warn border-warn/60",
  }[tone];
  return <span title={title} className={"inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-px text-cap font-semibold " + t}>{children}</span>;
}

export function StockBadges({ r }) {
  return (
    <>
      {!r.avail && (r.bo
        ? <Badge tone="bad" title="The store still takes orders and ships once it is back in stock">Backorder</Badge>
        : <Badge tone="bad">Out of stock</Badge>)}
      {r.stale && <Badge tone="warn" title="This price could not be re-checked today">Stale price</Badge>}
    </>
  );
}

// The signature element: a Canadian shelf label. Ink outline, ink header strip, the delivered unit price large.
export function ShelfLabel({ r, one, size = "md", label }) {
  const big = size === "lg";
  return (
    <div className="inline-flex min-w-[148px] flex-col overflow-hidden rounded-md border-2 border-ink bg-card">
      <div className={"bg-ink px-2.5 py-0.5 font-semibold text-card " + (big ? "text-sm" : "text-cap")}>{label || `Delivered, per ${one}`}</div>
      <div className={"px-2.5 pt-1 " + (big ? "pb-2" : "pb-1.5")}>
        <div className={"num font-bold leading-none tracking-tight " + (big ? "text-[34px]" : "text-[26px]")}>{r.dpd != null ? unit(r.dpd) : "—"}</div>
        <div className="mt-1"><ShipNote r={r} className={big ? "text-sm" : ""} />{r.dpd == null && <span className="text-cap text-muted">No shipping data</span>}</div>
      </div>
    </div>
  );
}

// "Lowest of 3": cheapest in-stock delivered price for this product and size among the stores that sell it
export const LowestBadge = ({ n }) => (
  <Badge tone="good"><Icon name="check" size={14} /> Lowest of {n}</Badge>
);
// a listing with no other store to compare against says so, so a missing badge is never ambiguous
export const CompareNote = ({ r }) => r.lowest ? <LowestBadge n={r.nst} />
  : r.nst === 1 ? <span className="text-cap text-muted">Only store</span> : null;

// the note under a delivered price
export function ShipNote({ r, className = "" }) {
  if (!r.qty || r.dpd == null) return null;
  if (r.shipq) return <span className={"text-cap text-warn font-medium " + className} title={SHIP.stores[r.store]?.summary || "Shipping is set at checkout"}>+ shipping at checkout</span>;
  if (r.ship === 0) return <span className={"text-cap text-good font-semibold " + className}>Free shipping</span>;
  return <span className={"text-cap text-muted " + className}>incl. {money(r.ship)} ship</span>;
}

export function Delta({ r, compact }) {
  if (r.prev == null || r.prev === r.price) return null;
  const up = r.price > r.prev;
  return (
    <span className={"inline-flex items-center gap-0.5 whitespace-nowrap text-cap font-medium " + (up ? "text-bad" : "text-good")} title={`Was ${money(r.prev)} at the last check`}>
      <Icon name={up ? "up" : "down"} size={13} /><span className="sr-only">{up ? "Price up" : "Price down"}, </span>{compact ? "was " : (up ? "up from " : "down from ")}{money(r.prev)}
    </span>
  );
}

export const Dash = ({ title }) => <span className="text-muted" title={title}>—</span>;
export const perOne = (v, one) => v == null ? "—" : `${unit(v)}/${one}`;

// ---- product images: hover preview (mouse) + click / Enter to enlarge ----
const ImgCtx = createContext(null);
export function ImageProvider({ thumbs, big, children }) {
  const [open, setOpen] = useState(null);          // {t, name}
  const [hover, setHover] = useState(null);        // {t, rect}
  const dlg = useRef(null);
  const canHover = typeof matchMedia !== "undefined" && matchMedia("(hover:hover) and (pointer:fine)").matches;
  useEffect(() => { const d = dlg.current; if (!d) return; if (open && !d.open) d.showModal(); if (!open && d.open) d.close(); }, [open]);
  useEffect(() => { const f = () => setHover(null); addEventListener("scroll", f, { passive: true }); return () => removeEventListener("scroll", f); }, []);
  const api = { thumbs, big, canHover, open: (t, name) => { setHover(null); setOpen({ t, name }); }, hover: (t, rect) => canHover && setHover(t ? { t, rect } : null) };
  let pos = null;
  if (hover) {
    const w = 300, gap = 12, r = hover.rect;
    let left = r.right + gap; if (left + w > innerWidth - 8) left = Math.max(8, r.left - w - gap);
    pos = { left, top: Math.max(8, Math.min(innerHeight - w - 8, r.top + r.height / 2 - w / 2)) };
  }
  return (
    <ImgCtx.Provider value={api}>
      {children}
      {hover && (
        <div aria-hidden="true" className="pointer-events-none fixed z-50 h-[300px] w-[300px] rounded-xl border border-line bg-white p-2 shadow-pop" style={pos}>
          <BigImg t={hover.t} className="h-full w-full object-contain" />
        </div>
      )}
      <dialog ref={dlg} onClose={() => setOpen(null)} onClick={e => e.target === dlg.current && setOpen(null)} aria-label="Product image"
        className="w-[min(600px,calc(100vw-32px))] rounded-2xl border border-line bg-card p-0 text-ink shadow-pop backdrop:bg-black/60">
        {open && (
          <div className="grid gap-3 p-4">
            <div className="flex items-start justify-between gap-4">
              <p className="font-semibold text-h3 pt-1.5">{open.name}</p>
              <button type="button" className="btn-ghost !px-3" onClick={() => setOpen(null)} aria-label="Close image"><Icon name="x" /></button>
            </div>
            <BigImg t={open.t} alt={open.name} className="w-full max-h-[min(560px,calc(100vh-180px))] object-contain rounded-xl bg-white" />
          </div>
        )}
      </dialog>
    </ImgCtx.Provider>
  );
}
function BigImg({ t, alt = "", className }) {
  const { thumbs, big } = useContext(ImgCtx);
  const [src, setSrc] = useState(big[t] || thumbs[t]);
  useEffect(() => setSrc(big[t] || thumbs[t]), [t, big, thumbs]);
  return <img src={src} alt={alt} className={className} onError={() => src !== thumbs[t] && setSrc(thumbs[t])} />;
}

export function Thumb({ r, size = 56 }) {
  const ctx = useContext(ImgCtx);
  const src = ctx?.thumbs[r.t];
  const name = r.fname;
  const box = { width: size, height: size };
  if (!src) return <div style={box} className="shrink-0 rounded-lg border border-line bg-sunken" aria-hidden="true" />;
  return (
    <button type="button" style={box} title="Enlarge photo" aria-label={`Enlarge photo of ${name}`}
      className="shrink-0 cursor-zoom-in overflow-hidden rounded-lg border border-line bg-white"
      onClick={e => { e.stopPropagation(); ctx.open(r.t, name); }}
      onMouseEnter={e => ctx.hover(r.t, e.currentTarget.getBoundingClientRect())} onMouseLeave={() => ctx.hover(null)}>
      <img src={src} alt="" loading="lazy" width={size} height={size} className="h-full w-full object-contain" />
    </button>
  );
}
