import { useEffect, useRef } from "react";
import Icon from "./Icon";
import { Badge, LowestBadge, ShipNote, Thumb, ShelfLabel } from "./bits";
import { CATS, SHIP, SIZE_ORDER, FEEDBACK, PROVINCES, unit, money, inch } from "../lib/data";
import { loadHistory, useWidth } from "../lib/store";

function History({ h }) {
  const [ref, w] = useWidth();
  if (!h) return null;
  if (h.length < 2) return <p ref={ref} className="text-sm text-muted">{h.length ? `One price point so far: ${money(h[0][1])} on ${h[0][0]}. The chart fills in as the price changes.` : "No history yet."}</p>;
  const pts = h.map(([d, p]) => [Date.parse(d), p]); pts.push([Date.now(), pts[pts.length - 1][1]]);
  const W = Math.max(280, w || 600), H = W < 480 ? 170 : 200, L = 60, R = 12, T = 12, B = 30, xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), lo = Math.min(...ys) * 0.97, hi = Math.max(...ys) * 1.03;
  const X = t => L + (t - x0) / (x1 - x0 || 1) * (W - L - R), Y = v => T + (hi - v) / (hi - lo || 1) * (H - T - B);
  let d = ""; pts.forEach((p, i) => { d += i ? `H${X(p[0]).toFixed(1)}V${Y(p[1]).toFixed(1)}` : `M${X(p[0]).toFixed(1)} ${Y(p[1]).toFixed(1)}`; });
  const ticks = [lo, (lo + hi) / 2, hi];
  const last = pts[pts.length - 1];
  return (
    <div ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="block max-w-full" role="img" aria-label={`Price history: ${h.map(([d, p]) => `${money(p)} from ${d}`).join(", ")}`}>
        {ticks.map(v => <g key={v}><line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke="var(--grid)" /><text x={L - 8} y={Y(v) + 4} textAnchor="end" className="fill-muted num" fontSize="13">${v.toFixed(2)}</text></g>)}
        <path d={d} fill="none" stroke="rgb(var(--accent))" strokeWidth="2.5" strokeLinejoin="round" />
        <circle cx={X(last[0])} cy={Y(last[1])} r="4.5" fill="rgb(var(--accent))" stroke="rgb(var(--card))" strokeWidth="2" />
        <text x={L} y={H - 8} className="fill-muted num" fontSize="13">{new Date(x0).toISOString().slice(0, 10)}</text>
        <text x={W - R} y={H - 8} textAnchor="end" className="fill-muted" fontSize="13">today</text>
      </svg>
      <details className="mt-1 text-sm">
        <summary className="link cursor-pointer">Show price changes as a list</summary>
        <ul className="num mt-2 grid gap-1">{h.map(([d, p, s]) => <li key={d}>{d}: {money(p)}{s === false ? " · out of stock" : ""}</li>)}</ul>
      </details>
    </div>
  );
}

const Fact = ({ k, children }) => (
  <div className="rounded-lg bg-sunken px-3 py-2.5">
    <dt className="text-cap text-muted">{k}</dt>
    <dd className="num font-semibold">{children}</dd>
  </div>
);

export default function ProductDialog({ r, data, prov, onOpen, onClose }) {
  const ref = useRef(null);
  useEffect(() => { const d = ref.current; if (r && !d.open) d.showModal(); if (!r && d.open) d.close(); if (r) d.scrollTop = 0; }, [r]);
  useEffect(() => { if (r) loadHistory(); }, [r]);
  const body = r && (() => {
    const one = (CATS[r.cat] || CATS.diaper).one;
    const provName = PROVINCES.find(p => p[0] === prov)?.[1] || prov;
    const peers = (data.groups.get(r.ck) || [r]).slice().sort((a, b) => (b.avail - a.avail) || ((a.dpd ?? 1e9) - (b.dpd ?? 1e9)));
    const nStores = new Set(peers.map(p => p.store)).size;
    const sib = data.rows.filter(x => x.pid === r.pid && x.cat === r.cat);
    const sizes = [...new Set(sib.map(x => x.size))].sort((a, b) => SIZE_ORDER.indexOf(a) - SIZE_ORDER.indexOf(b));
    const pick = sz => sib.filter(x => x.size === sz).sort((a, b) => (b.avail - a.avail) || ((a.ppd ?? 1e9) - (b.ppd ?? 1e9)))[0];
    const ship = SHIP.stores[r.store];
    const mail = `https://mail.google.com/mail/?view=cm&fs=1&to=${FEEDBACK}&su=${encodeURIComponent(`Tracker correction: ${r.brand} ${r.dname} (${r.size}, ${r.pkg}) at ${r.store}`)}`;
    return (
      <>
        <div className="sticky top-0 z-10 flex items-start gap-3 border-b border-line bg-card px-4 py-3 md:px-6">
          <Thumb r={r} size={64} />
          <div className="min-w-0 flex-1">
            <p className="text-sm text-muted">{r.brand}</p>
            <h2 id="pd-title" className="text-h3 md:text-h2 font-bold leading-tight">{r.dname}</h2>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {r.variant && <Badge tone="outline">{r.variant}</Badge>}
              <Badge>{r.store}</Badge>
              {r.avail ? <Badge tone="good">In stock</Badge> : <Badge tone="bad">{r.bo ? "Backorder" : "Out of stock"}</Badge>}
              {r.lowest && <LowestBadge />}
            </div>
          </div>
          <button type="button" onClick={onClose} className="btn-ghost !px-3" aria-label="Close details"><Icon name="x" /></button>
        </div>

        <div className="grid gap-6 px-4 py-4 md:px-6 md:py-5">
          <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
            <ShelfLabel r={r} one={one} size="lg" label={`Delivered to ${provName}, per ${one}`} />
            <dl className="grid grid-cols-[auto_auto] gap-x-4 gap-y-1 pt-1 text-base">
              <dt className="text-muted">Pack price</dt><dd className="num text-right font-semibold">{money(r.price)}</dd>
              <dt className="text-muted">Package</dt><dd className="text-right">{r.pkg}{r.qty ? ` of ${r.qty}` : ""}</dd>
              <dt className="text-muted">Shelf, per {one}</dt><dd className="num text-right">{unit(r.ppd)}</dd>
            </dl>
          </div>

          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {r.cat === "booster"
              ? <Fact k="Size (L × W)">{r.dl != null ? `${inch(r.dl)} × ${inch(r.dw)}${r.size !== "One size" ? " · " + r.size : ""}` : (r.size !== "One size" ? r.size : "—")}</Fact>
              : <><Fact k="Size">{r.size}</Fact><Fact k="Waist / hip">{r.waist ? `${r.waist[0]}–${r.waist[1]}" (${Math.round(r.waist[0] * 2.54)}–${Math.round(r.waist[1] * 2.54)} cm)` : "—"}</Fact></>}
            <Fact k="Capacity">{r.cap ? r.cap.toLocaleString() + " mL" : "—"}</Fact>
            <Fact k="Delivered $/L">{r.dpl == null ? "—" : money(r.dpl) + (r.shipq ? " + ship" : "")}</Fact>
            <Fact k="Tracked since">{r.first || "—"}</Fact>
            {r.checked && <Fact k="Price checked">{r.checked}</Fact>}
          </dl>

          {sizes.length > 1 && (
            <section aria-labelledby="pd-sizes">
              <h3 id="pd-sizes" className="font-semibold">Other sizes</h3><p className="mb-2 text-sm text-muted">Cheapest shelf price per {one} in each size</p>
              <div className="flex flex-wrap gap-2">
                {sizes.map(sz => { const p = pick(sz), on = sz === r.size; return (
                  <button key={sz} type="button" aria-current={on || undefined} onClick={() => onOpen(p.id)}
                    className={"chip " + (on ? "border-accent bg-accent text-on-accent" : "border-line-strong bg-card hover:border-accent")}>
                    <span className="font-semibold">{sz}</span> <span className={"num " + (on ? "opacity-90" : "text-muted")}>{unit(p.ppd)}</span>
                  </button>); })}
              </div>
            </section>
          )}

          <section aria-labelledby="pd-cmp">
            <h3 id="pd-cmp" className="font-semibold">{r.size} at {nStores} {nStores === 1 ? "store" : "stores"} </h3>
            <p className="mb-2 text-sm text-muted">Every pack and variant, cheapest delivered first</p>
            <ul className="divide-y divide-line rounded-xl border border-line">
              {peers.map(p => { const me = p.id === r.id; return (
                <li key={p.id} className={"flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2.5 " + (me ? "bg-accent-soft/60" : "")}>
                  <button type="button" disabled={me} onClick={() => onOpen(p.id)} className="min-w-[150px] flex-1 text-left disabled:cursor-default">
                    <span className="font-semibold">{p.store}</span>{me && <span className="ml-2 text-cap text-muted">(this listing)</span>}
                    <span className="block text-sm text-muted">{p.pkg}{p.qty ? ` of ${p.qty}` : ""}{p.variant ? ` · ${p.variant}` : ""} · {money(p.price)}</span>
                  </button>
                  <div className="text-right">
                    <div className="num font-bold">{p.dpd != null ? unit(p.dpd) : "—"}<span className="font-normal text-cap text-muted">/{one}</span></div>
                    <ShipNote r={p} />
                  </div>
                  <div className="flex w-full items-center justify-between gap-2 sm:w-auto sm:flex-col sm:items-end">
                    <span className="flex gap-1">{p.lowest && <LowestBadge />}{!p.avail && <Badge tone="bad">Out</Badge>}</span>
                    <a className="link inline-flex items-center gap-1 text-sm" href={p.url} target="_blank" rel="noopener">View<Icon name="ext" size={14} /><span className="sr-only"> {p.store} (opens in a new tab)</span></a>
                  </div>
                </li>); })}
            </ul>
          </section>

          <section aria-labelledby="pd-hist">
            <h3 id="pd-hist" className="font-semibold">Price history</h3>
            <p className="mb-2 text-sm text-muted">Pack price of this listing</p>
            {data.histStatus === "error" ? <p className="text-sm text-muted">Price history isn't available right now.</p>
              : !data.hist ? <p className="text-sm text-muted">Loading history…</p>
              : <History h={data.hist[r.id] || []} />}
          </section>

          {ship && <p className="text-sm text-muted"><strong className="text-ink">{r.store} shipping:</strong> {ship.summary} <em>Source: {ship.source}{ship.verified ? " (checked at checkout)" : ""}, {SHIP.checked}.</em></p>}

          <div className="flex flex-wrap gap-2 border-t border-line pt-4">
            <a className="btn-primary" href={r.url} target="_blank" rel="noopener">View at {r.store} <Icon name="ext" size={16} /></a>
            <a className="btn-ghost" href={mail} target="_blank" rel="noopener"><Icon name="mail" size={16} /> Report a problem</a>
          </div>
          <p className="-mt-3 text-cap text-muted">Or email <strong className="select-all text-ink">{FEEDBACK}</strong> and tell us which listing is wrong.</p>
        </div>
      </>
    );
  })();
  return (
    <dialog ref={ref} onClose={onClose} onClick={e => e.target === ref.current && onClose()} aria-labelledby="pd-title"
      className="m-0 mt-auto h-[100dvh] max-h-[100dvh] w-full max-w-full overflow-y-auto bg-card p-0 text-ink shadow-pop md:m-auto md:h-auto md:max-h-[calc(100dvh-48px)] md:w-[min(760px,calc(100vw-48px))] md:rounded-2xl md:border md:border-line">
      <div className="anim-in">{body}</div>
    </dialog>
  );
}
