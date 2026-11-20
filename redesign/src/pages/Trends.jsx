import { useEffect, useMemo, useState } from "react";
import Icon from "../components/Icon";
import { CATS, unit, money, pct, day } from "../lib/data";
import { loadHistory, useLocal, useWidth } from "../lib/store";

const STORES = ["Healthwick", "ABUniverse", "MyDips", "AgeComfort", "Rearz", "Amazon"];   // fixed colour slots 1-6
const scol = s => `var(--s${STORES.indexOf(s) + 1})`;
const DASH = ["", "7 4", "2 3", "10 3 2 3", "4 4", "1 0"];   // stroke per store, so lines differ by more than hue
const addDays = (d, n) => new Date(Date.parse(d + "T12:00:00Z") + n * 864e5).toISOString().slice(0, 10);
const median = a => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const pname = r => { const n = r.line || r.name; return n.toLowerCase().startsWith((r.brand || "").toLowerCase()) ? n : `${r.brand} ${n}`; };


// tooltip shared by every chart: values first, labels after
function Tip({ tip }) {
  if (!tip) return null;
  return (
    <div role="status" className="pointer-events-none absolute z-20 min-w-[160px] rounded-lg border border-line bg-card px-3 py-2 text-sm shadow-pop" style={{ left: tip.x, top: tip.y }}>
      <div className="mb-1 font-semibold">{tip.head}</div>
      {tip.items.map(([l, v, c]) => (
        <div key={l} className="flex items-center gap-2"><b className="num min-w-[52px]">{v}</b>{c && <i className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />}<span className="text-muted">{l}</span></div>
      ))}
    </div>
  );
}
const tipAt = (host, x, y, w) => ({ x: Math.min(Math.max(0, x + 14), Math.max(0, w - 200)), y: Math.max(0, y - 30) });

function Card({ title, sub, children, table, legend }) {
  return (
    <section className="card min-w-0 p-4 md:p-5">
      <h2 className="text-h3 font-bold">{title}</h2>
      {sub && <p className="mt-0.5 text-sm text-muted">{sub}</p>}
      {legend && <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">{legend}</div>}
      <div className="mt-3">{children}</div>
      {table && <details className="mt-3"><summary className="link inline-flex min-h-[44px] cursor-pointer items-center text-sm">Show as table</summary><div className="mt-2 max-h-80 overflow-auto">{table}</div></details>}
    </section>
  );
}
const Key = ({ c, children }) => <span className="inline-flex items-center gap-1.5"><i className="h-3 w-3 rounded-sm" style={{ background: c }} />{children}</span>;
const LineKey = ({ s, children }) => <span className="inline-flex items-center gap-1.5"><svg width="24" height="10" aria-hidden="true"><line x1="1" x2="23" y1="5" y2="5" stroke={scol(s)} strokeWidth="2.5" strokeDasharray={DASH[STORES.indexOf(s)] || undefined} /></svg>{children}</span>;
const T = ({ head, rows }) => (
  <table className="num w-full text-sm">
    <thead><tr className="border-b border-line-strong text-left">{head.map((h, i) => <th key={h} className={"px-2 py-1.5 font-semibold " + (i ? "text-right" : "")}>{h}</th>)}</tr></thead>
    <tbody>{rows.map((r, j) => <tr key={j} className="border-b border-line">{r.map((c, i) => <td key={i} className={"px-2 py-1.5 " + (i ? "text-right" : "")}>{c}</td>)}</tr>)}</tbody>
  </table>
);

// ---------- line: price index by store ----------
function IndexChart({ X }) {
  const [ref, W0] = useWidth(); const [tip, setTip] = useState(null); const [cur, setCur] = useState(null);
  const series = STORES.map(s => {
    const b = X.base.filter(x => x.r.store === s); if (!b.length) return null;
    const pts = X.dates.map(d => { let sum = 0, n = 0; b.forEach(x => { const p = X.priceAt(x.r, d); if (p) { sum += p / x.p0; n++; } }); return n ? sum / n * 100 : null; });
    return { s, n: b.length, pts };
  }).filter(Boolean);
  const ok = series.length && X.dates.length >= 2;
  const left = [...new Set(X.rows.map(r => r.store))].filter(s => !series.some(x => x.s === s)).sort();
  const W = Math.max(300, W0 || 900), H = W < 600 ? 250 : 320, L = 44, R = W < 600 ? 112 : 132, Tp = 12, B = 30;
  let body = null;
  if (ok) {
    const vals = series.flatMap(x => x.pts).filter(v => v != null);
    let lo = Math.min(100, ...vals), hi = Math.max(100, ...vals); const pad = Math.max(0.5, (hi - lo) * 0.12); lo -= pad; hi += pad;
    const xs = i => L + i / (X.dates.length - 1) * (W - L - R), ys = v => Tp + (hi - v) / (hi - lo) * (H - Tp - B);
    const step = (hi - lo) > 12 ? 5 : (hi - lo) > 5 ? 2 : (hi - lo) > 2 ? 1 : 0.5;
    const grid = []; for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) grid.push(v);
    const nt = Math.min(W < 600 ? 3 : 6, X.dates.length);
    const xt = [...Array(nt).keys()].map(k => Math.round(k * (X.dates.length - 1) / (nt - 1)));
    const ends = series.map(x => ({ s: x.s, v: x.pts[x.pts.length - 1], y: ys(x.pts[x.pts.length - 1]) })).sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 16) ends[i].y = ends[i - 1].y + 16;
    const over = ends.length ? ends[ends.length - 1].y - (H - B - 2) : 0;   // pushed past the bottom: move the stack up
    if (over > 0) ends.forEach(e => { e.y -= over; });
    for (let i = ends.length - 2; i >= 0; i--) if (ends[i + 1].y - ends[i].y < 16) ends[i].y = ends[i + 1].y - 16;
    const at = i => { setCur(i); setTip({ ...tipAt(null, xs(i), ys(100), W), head: X.dates[i], items: series.map(x => [x.s, x.pts[i] == null ? "—" : x.pts[i].toFixed(1), scol(x.s)]).sort((a, b) => parseFloat(b[1]) - parseFloat(a[1])) }); };
    const move = e => { const r = e.currentTarget.ownerSVGElement.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * W; at(Math.max(0, Math.min(X.dates.length - 1, Math.round((x - L) / (W - L - R) * (X.dates.length - 1))))); };
    const off = () => { setCur(null); setTip(null); };
    body = (
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={`Price index by store, ${X.start} to ${X.end}`} className="block max-w-full overflow-visible">
        {grid.map(v => <g key={v}><line x1={L} x2={W - R} y1={ys(v)} y2={ys(v)} stroke={Math.abs(v - 100) < 1e-9 ? "var(--axis)" : "var(--grid)"} /><text x={L - 8} y={ys(v) + 4} textAnchor="end" fontSize="13" className="fill-muted num">{+v.toFixed(1)}</text></g>)}
        {xt.map((i, k) => <text key={k} x={xs(i)} y={H - 8} fontSize="13" className="fill-muted num" textAnchor={k === 0 ? "start" : k === nt - 1 ? "end" : "middle"}>{X.dates[i].slice(5)}</text>)}
        {series.map(x => { let d = ""; x.pts.forEach((v, i) => { if (v != null) d += (d ? "L" : "M") + xs(i).toFixed(1) + " " + ys(v).toFixed(1); }); return <path key={x.s} d={d} fill="none" stroke={scol(x.s)} strokeDasharray={DASH[STORES.indexOf(x.s)] || undefined} strokeWidth="2.25" strokeLinejoin="round" strokeLinecap="round" />; })}
        {ends.map(e => <g key={e.s}><circle cx={xs(X.dates.length - 1)} cy={ys(e.v)} r="4" fill={scol(e.s)} stroke="rgb(var(--card))" strokeWidth="2" /><text x={W - R + 10} y={e.y + 4} fontSize="13" className="fill-ink font-medium">{e.s} <tspan className="num fill-muted">{e.v.toFixed(1)}</tspan></text></g>)}
        {cur != null && <line x1={xs(cur)} x2={xs(cur)} y1={Tp} y2={H - B} stroke="var(--axis)" />}
        <rect x={L} y={Tp} width={W - L - R} height={H - Tp - B} fill="transparent" tabIndex="0" aria-label="Chart: use left and right arrow keys for each day's values"
          onPointerMove={move} onPointerLeave={off} onBlur={off} onFocus={() => at(cur ?? X.dates.length - 1)}
          onKeyDown={e => { if (e.key === "ArrowLeft") { e.preventDefault(); at(Math.max(0, (cur ?? X.dates.length - 1) - 1)); } if (e.key === "ArrowRight") { e.preventDefault(); at(Math.min(X.dates.length - 1, (cur ?? 0) + 1)); } }} />
      </svg>
    );
  }
  return (
    <Card title="Price index by store" sub="Every listing's price at the start of the period = 100, averaged per store. Below 100 means that store got cheaper overall."
      legend={series.map(x => <LineKey key={x.s} s={x.s}>{x.s} <span className="num text-muted">({x.n})</span></LineKey>)}
      table={ok && <T head={["Date", ...series.map(x => x.s)]} rows={X.dates.map((d, i) => [d, ...series.map(x => x.pts[i] == null ? "—" : x.pts[i].toFixed(1))])} />}>
      <div ref={ref} className="relative">{ok ? body : <p className="py-10 text-center text-muted">Not enough history for this period yet.</p>}<Tip tip={tip} /></div>
      {left.length > 0 && <p className="mt-2 text-sm text-muted">Not shown: {left.join(", ")}. None of their listings were tracked from the start of this period, so there is nothing to index against yet.</p>}
    </Card>
  );
}

// ---------- horizontal bars ----------
function HBars({ items, diverging, fmt, tick, aria }) {
  const [ref, W0] = useWidth(); const [tip, setTip] = useState(null);
  if (!items.length) return <p ref={ref} className="py-10 text-center text-muted">Nothing to show for this period yet.</p>;
  const row = 32, W = Math.max(300, W0 || 520), L = W < 420 ? 112 : 140, R = 72, Tp = 4, H = Tp + items.length * row + 26;
  const vals = items.map(x => x.value);
  let lo = diverging ? Math.min(0, ...vals) : 0, hi = Math.max(0, ...vals);
  if (diverging) { const m = Math.max(Math.abs(lo), Math.abs(hi), 0.5); lo = -m; hi = m; } else hi = hi || 1;
  const xs = v => L + (v - lo) / (hi - lo) * (W - L - R), x0 = xs(0);
  // round tick values ($0, $2, $4), never odd ones like $2.38
  const nice = v => { const e = 10 ** Math.floor(Math.log10(v)), f = v / e; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * e; };
  const step = diverging ? 0 : nice(hi / 2.5);
  const ticks = diverging ? [lo, 0, hi] : [...Array(Math.floor(hi / step + 1e-9) + 1).keys()].map(i => i * step);
  return (
    <div ref={ref} className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={aria} className="block max-w-full">
        {ticks.map(v => <g key={v}><line x1={xs(v)} x2={xs(v)} y1={Tp} y2={H - 22} stroke={v === 0 ? "var(--axis)" : "var(--grid)"} /><text x={xs(v)} y={H - 6} textAnchor="middle" fontSize="13" className="fill-muted num">{tick(v)}</text></g>)}
        {items.map((x, i) => {
          const y = Tp + i * row + 5, h = row - 10, a = Math.min(xs(x.value), x0), w = Math.max(2, Math.abs(xs(x.value) - x0));
          const show = () => setTip({ ...tipAt(null, xs(x.value), y + h / 2, W), head: x.label, items: x.tip });
          return (
            <g key={x.label}>
              <text x={L - 10} y={y + h / 2 + 5} textAnchor="end" fontSize="14" className="fill-ink">{x.label.length > 16 ? x.label.slice(0, 15) + "…" : x.label}</text>
              <rect x={a} y={y} width={w} height={h} rx="4" fill={x.color} />
              <text x={x.value < 0 ? a - 6 : a + w + 6} y={y + h / 2 + 5} textAnchor={x.value < 0 ? "end" : "start"} fontSize="13" className="fill-ink num font-medium">{fmt(x.value)}</text>
              <rect x="0" y={y - 5} width={W} height={row} fill="transparent" tabIndex="0" aria-label={`${x.label}: ${fmt(x.value)}`} onPointerMove={show} onFocus={show} onPointerLeave={() => setTip(null)} onBlur={() => setTip(null)} />
            </g>
          );
        })}
      </svg>
      <Tip tip={tip} />
    </div>
  );
}

// ---------- columns: changes per day ----------
function DaysChart({ X, days }) {
  const [ref, W0] = useWidth(); const [tip, setTip] = useState(null);
  if (!days.length) return <p ref={ref} className="py-10 text-center text-muted">Not enough history for this period yet.</p>;
  const W = Math.max(300, W0 || 900), H = 250, L = 44, R = 10, Tp = 10, B = 30;
  const m = Math.max(1, ...days.map(x => Math.max(x.up, x.dn)));
  const y0 = Tp + (H - Tp - B) / 2, ys = v => (H - Tp - B) / 2 * v / m;
  const bw = (W - L - R) / days.length, gap = Math.min(4, bw * 0.2);
  const nt = Math.min(W < 600 ? 3 : 6, days.length);
  return (
    <div ref={ref} className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label="Price changes per day" className="block max-w-full">
        {[[y0, "0", "var(--axis)"], [y0 - ys(m), m, "var(--grid)"], [y0 + ys(m), m, "var(--grid)"]].map(([y, t, c], i) => <g key={i}><line x1={L} x2={W - R} y1={y} y2={y} stroke={c} /><text x={L - 8} y={y + 4} textAnchor="end" fontSize="13" className="fill-muted num">{t}</text></g>)}
        <text x={L + 8} y={Tp + 14} fontSize="13" className="fill-muted">Increases</text>
        <text x={L + 8} y={H - B - 6} fontSize="13" className="fill-muted">Decreases</text>
        {[...Array(nt).keys()].map(k => { const i = nt === 1 ? 0 : Math.round(k * (days.length - 1) / (nt - 1)); return <text key={k} x={k === 0 ? L : k === nt - 1 ? W - R : L + i * bw + bw / 2} y={H - 8} textAnchor={k === 0 ? "start" : k === nt - 1 ? "end" : "middle"} fontSize="13" className="fill-muted num">{days[i].d.slice(5)}</text>; })}
        {days.map((x, i) => { const bx = L + i * bw + gap / 2, w = Math.max(1, bw - gap), rx = Math.min(4, w / 2);
          const show = () => setTip({ ...tipAt(null, L + (i + 0.5) * bw, y0, W), head: x.d, items: [["Increases", String(x.up), "var(--inc)"], ["Decreases", String(x.dn), "var(--dec)"]] });
          return (
            <g key={x.d}>
              {x.up > 0 && <rect x={bx} y={y0 - ys(x.up) - 1} width={w} height={ys(x.up)} rx={rx} fill="var(--inc)" />}
              {x.dn > 0 && <rect x={bx} y={y0 + 1} width={w} height={ys(x.dn)} rx={rx} fill="var(--dec)" />}
              <rect x={L + i * bw} y={Tp} width={bw} height={H - Tp - B} fill="transparent" tabIndex="0" aria-label={`${x.d}: ${x.up} increases, ${x.dn} decreases`} onPointerMove={show} onFocus={show} onPointerLeave={() => setTip(null)} onBlur={() => setTip(null)} />
            </g>); })}
      </svg>
      <Tip tip={tip} />
    </div>
  );
}

const Dir = ({ v }) => v === 0 ? null : <span style={{ color: v > 0 ? "var(--inc)" : "var(--dec)" }} className="inline-flex"><Icon name={v > 0 ? "up" : "down"} size={15} /></span>;

function BrandBars({ brands }) {
  const [all, setAll] = useState(false);
  const moved = brands.filter(x => Math.abs(x.value) >= 0.05), still = brands.length - moved.length;
  return (
    <>
      {moved.length ? <HBars items={all ? brands : moved} diverging fmt={pct} tick={v => (v > 0 ? "+" : "") + +v.toFixed(1) + "%"} aria="Average price change by brand" />
        : <p className="py-6 text-center text-muted">No brand changed price on average in this period.</p>}
      {still > 0 && <button type="button" className="link mt-2 min-h-[44px] text-sm" onClick={() => setAll(a => !a)}>{all ? `Hide the ${still} unchanged brands` : `Show ${still} brands with no change`}</button>}
    </>
  );
}

function Movers({ title, sub, list, one }) {
  return (
    <section className="card min-w-0 p-4 md:p-5">
      <h2 className="text-h3 font-bold">{title}</h2>
      <p className="mt-0.5 text-sm text-muted">{sub}</p>
      {!list.length ? <p className="py-8 text-center text-muted">No price changes in this period.</p> : (
        <ol className="mt-3 divide-y divide-line">
          {list.map(x => (
            <li key={x.r.id} className="flex flex-wrap items-start gap-x-3 gap-y-1 py-3">
              <div className="min-w-0 basis-full sm:basis-0 sm:flex-1">
                <a translate="no" className="link font-semibold" href={x.r.url} target="_blank" rel="noopener">{pname(x.r)}<span className="sr-only"> (opens in a new tab)</span></a>
                <div className="text-sm text-muted">{x.r.store}, size {x.r.size}, {x.r.pkg.toLowerCase()} of {x.r.qty}{x.r.variant ? `, ${x.r.variant.toLowerCase()}` : ""}</div>
              </div>
              <div className="flex-1 sm:flex-none sm:text-right">
                <div className="num whitespace-nowrap text-sm">{money(x.p0)} → <b>{money(x.p1)}</b></div>
                <div className="num text-cap text-muted">{unit(x.p1 / x.r.qty)}/{one}</div>
              </div>
              <div className="w-[76px] text-right">
                <b className="num inline-flex items-center gap-0.5"><Dir v={x.c} /><span className="sr-only">{x.c > 0 ? "up" : "down"} </span>{pct(x.c).replace(/^[+−]/, "")}</b>
                {Math.abs(x.c) >= 50 && <div className="text-cap font-semibold text-warn" title="Moves this big are more often a corrected listing than a real price change">Large swing</div>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Seg({ label, value, options, onChange }) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-semibold text-muted">{label}</span>
      <div className="inline-flex flex-wrap rounded-full border border-line-strong bg-card p-1">
        {options.map(([v, l]) => (
          <button key={v} type="button" aria-pressed={value === v} onClick={() => onChange(v)}
            className={"min-h-[44px] rounded-full px-4 text-sm font-semibold transition-colors " + (value === v ? "bg-accent text-on-accent" : "text-ink hover:bg-sunken")}>{l}</button>
        ))}
      </div>
    </div>
  );
}

export default function Trends({ data }) {
  const [F, setF] = useLocal("dipaisle.trends", { cat: "diaper", days: 30 });
  useEffect(() => { if (data.status === "ready") loadHistory(); }, [data.status]);
  const one = CATS[F.cat].one;
  const X = useMemo(() => {
    if (!data.hist || !data.meta) return null;
    const H = data.hist;
    let first = data.meta.date; Object.values(H).forEach(h => { if (h.length && h[0][0] < first) first = h[0][0]; });
    const end = data.meta.date;
    const priceAt = (r, d) => { const h = H[r.id]; if (!h || !h.length) return (r.first || "") <= d ? r.price : null; let p = null; for (const x of h) { if (x[0] <= d) p = x[1]; else break; } return p; };
    const start = F.days ? (addDays(end, -F.days) < first ? first : addDays(end, -F.days)) : first;
    const rows = data.rows.filter(r => r.cat === F.cat && r.qty > 0 && r.pkg !== "Sample" && r.price > 0);
    const dates = []; for (let d = start; d <= end; d = addDays(d, 1)) dates.push(d);
    const base = rows.map(r => ({ r, p0: priceAt(r, start), p1: priceAt(r, end) })).filter(x => x.p0 && x.p1);
    return { start, end, rows, dates, base, priceAt, H };
  }, [data.hist, data.meta, data.rows, F.cat, F.days]);

  let content;
  if (data.status === "error" || data.histStatus === "error") content = <p className="card p-8 text-center text-muted">Price history could not be loaded. Reload to retry.</p>;
  else if (!X) content = <div className="grid gap-4" aria-hidden="true">{[0, 1, 2].map(i => <div key={i} className="card h-48 animate-pulse bg-sunken" />)}</div>;
  else {
    const live = X.rows.filter(r => r.avail);
    const now = median(live.map(r => r.price / r.qty));
    const m0 = median(X.base.map(x => x.p0 / x.r.qty)), m1 = median(X.base.map(x => x.p1 / x.r.qty));
    const avg = X.base.length ? X.base.reduce((a, x) => a + (x.p1 / x.p0 - 1), 0) / X.base.length * 100 : 0;
    const days = X.dates.slice(1).map(d => ({ d, up: 0, dn: 0 })); const idx = Object.fromEntries(days.map((x, i) => [x.d, i]));
    let up = 0, dn = 0;
    X.rows.forEach(r => { const h = X.H[r.id] || []; for (let i = 1; i < h.length; i++) { if (h[i][1] === h[i - 1][1]) continue; const k = idx[h[i][0]]; if (k != null) { h[i][1] > h[i - 1][1] ? days[k].up++ : days[k].dn++; } if (h[i][0] > X.start && h[i][0] <= X.end) { h[i][1] > h[i - 1][1] ? up++ : dn++; } } });
    const moved = X.base.filter(x => x.p1 !== x.p0).length;
    const by = {}; X.base.forEach(x => { (by[x.r.brand] ||= []).push(x.p1 / x.p0 - 1); });
    const brands = Object.entries(by).filter(([, v]) => v.length >= 5).map(([b, v]) => { const m = v.reduce((a, c) => a + c, 0) / v.length * 100, mv = v.filter(c => c !== 0).length;
      return { label: b, value: m, n: v.length, moved: mv, color: Math.abs(m) < 0.05 ? "var(--axis)" : m < 0 ? "var(--dec)" : "var(--inc)", tip: [["Average change", pct(m)], ["Listings", String(v.length)], ["Changed price", String(mv)]] }; }).sort((a, b) => a.value - b.value);
    const storesM = STORES.map(s => { const v = X.rows.filter(r => r.store === s && r.avail).map(r => r.price / r.qty); if (!v.length) return null; const m = median(v);
      return { label: s, value: m, n: v.length, color: scol(s), tip: [[`Median per ${one}`, unit(m)], ["In-stock listings", String(v.length)], ["Lowest", unit(Math.min(...v))], ["Highest", unit(Math.max(...v))]] }; }).filter(Boolean).sort((a, b) => a.value - b.value);
    const mv = X.base.filter(x => x.p1 !== x.p0).map(x => ({ ...x, c: (x.p1 / x.p0 - 1) * 100 }));
    const tiles = [
      [`Median shelf price per ${one} today`, unit(now), `Across ${live.length.toLocaleString()} in-stock listings`, ""],
      ["Average price change", <span className="inline-flex items-center gap-1"><Dir v={Math.abs(avg) < 0.05 ? 0 : avg} />{pct(avg)}</span>, `Across the ${X.base.length.toLocaleString()} listings tracked all period`, ""],
      ["Price changes recorded", (up + dn).toLocaleString(), <span className="inline-flex flex-wrap items-center gap-x-2"><span className="inline-flex items-center gap-0.5"><Dir v={1} />{up} increases</span><span className="inline-flex items-center gap-0.5"><Dir v={-1} />{dn} decreases</span></span>, ""],
      ["Listings at a new price", moved.toLocaleString(), `Of ${X.base.length.toLocaleString()}, compared with the start of the period. A listing can change several times.`, ""],
    ];
    content = (
      <div className="grid gap-4 md:gap-5">
        <section aria-label="Summary" className="grid grid-cols-2 border-y-2 border-ink lg:grid-cols-4">
          {tiles.map(([k, v, s, c], i) => (
            <div key={k} className={"py-4 pr-4 " + (i % 2 ? "border-l border-line pl-4 " : "") + (i === 2 ? "border-t border-line lg:border-l lg:border-t-0 lg:pl-4 " : "") + (i === 3 ? "border-t border-line lg:border-t-0 " : "")}>
              <div className="text-sm text-muted">{k}</div>
              <div className={"num mt-1 text-[26px] font-bold leading-8 md:text-[30px] md:leading-9 " + c}>{v}</div>
              <div className="num mt-1 text-cap text-muted">{s}</div>
            </div>
          ))}
        </section>
        <IndexChart X={X} />
        <div className="grid gap-4 md:gap-5 xl:grid-cols-2">
          <Card title="Average price change by brand" sub="Average change in listing price over the period, brands with at least 5 listings."
            legend={<><Key c="var(--dec)">Cheaper</Key><Key c="var(--inc)">Pricier</Key><Key c="var(--axis)">No change</Key></>}
            table={<T head={["Brand", "Average change", "Listings", "Changed price"]} rows={brands.map(x => [x.label, pct(x.value), x.n, x.moved])} />}>
            <BrandBars brands={brands} />
          </Card>
          <Card title={`Typical price per ${one} by store`} sub="Median shelf price per piece today, in-stock bags and cases."
            table={<T head={["Store", `Median per ${one}`, "In-stock listings"]} rows={storesM.map(x => [x.label, unit(x.value), x.n])} />}>
            <HBars items={storesM} fmt={unit} tick={v => "$" + v.toFixed(2)} aria={`Median price per ${one} by store`} />
          </Card>
        </div>
        <Card title="Price changes per day" sub="How many listings changed price each day: increases above the line, decreases below."
          legend={<><Key c="var(--inc)">Increases</Key><Key c="var(--dec)">Decreases</Key></>}
          table={<T head={["Date", "Increases", "Decreases"]} rows={days.filter(x => x.up || x.dn).map(x => [x.d, x.up, x.dn])} />}>
          <DaysChart X={X} days={days} />
        </Card>
        <div className="grid gap-4 md:gap-5 xl:grid-cols-2">
          <Movers title="Biggest price drops" sub="Largest decreases over the period." one={one} list={mv.filter(x => x.c < 0).sort((a, b) => a.c - b.c).slice(0, 10)} />
          <Movers title="Biggest price increases" sub="Largest increases over the period." one={one} list={mv.filter(x => x.c > 0).sort((a, b) => b.c - a.c).slice(0, 10)} />
        </div>
      </div>
    );
  }

  return (
    <main id="main" tabIndex={-1} className="mx-auto max-w-page outline-none px-4 pb-16 pt-5 md:px-6 md:pt-7 xl:px-8">
      <h1 className="font-display text-[26px] font-bold leading-8 tracking-tight md:text-h1">Price trends</h1>
      <p className="text-muted">{X ? <>{day(X.start)} to {day(X.end)}. <span className="num">{X.base.length.toLocaleString()}</span> listings tracked through the whole period.</> : "Loading price history…"}</p>
      <div className="my-4 flex flex-wrap items-center gap-x-6 gap-y-3">
        <Seg label="Show" value={F.cat} onChange={v => setF(f => ({ ...f, cat: v }))} options={Object.entries(CATS).map(([k, c]) => [k, c.label])} />
        <Seg label="Period" value={F.days} onChange={v => setF(f => ({ ...f, days: v }))} options={[[7, "7 days"], [30, "30 days"], [0, "All time"]]} />
      </div>
      <p className="mb-4 text-sm text-muted">Shelf prices before shipping and tax; sample packs left out.</p>
      {content}
      <p className="mt-8 max-w-[70ch] text-sm text-muted">Prices come from the daily tracker run; a listing's price is carried forward on days it did not change. A move of 50% or more is marked "Large swing": it is more often a corrected listing than a real price change. Index and brand averages use only listings tracked since the start of the period.</p>
    </main>
  );
}
