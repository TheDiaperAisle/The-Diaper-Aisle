import Icon from "./Icon";
import { CATS } from "../lib/data";
import logo from "../../../assets/tda-logo.webp";

const NAV = [["diapers", "diaper"], ["pullups", "pullup"], ["boosters", "booster"]];

// the URL hash is the route, so skip links move focus instead of changing the hash
export const skip = e => { e.preventDefault(); const el = document.getElementById("results") || document.getElementById("main"); el?.focus(); el?.scrollIntoView({ block: "start" }); };

export default function Header({ route, data }) {
  const m = data.meta;
  const when = m ? new Date(m.lastRun).toLocaleString("en-CA", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : null;
  const counts = {};
  data.rows.forEach(r => { counts[r.cat] = (counts[r.cat] || 0) + 1; });
  const stores = Object.entries(m?.stores || {});
  const bad = stores.filter(([, s]) => !s.ok);
  return (
    <header className="aisle-band relative overflow-hidden bg-brand-ink text-white">
      <a href="#results" onClick={skip} className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-white focus:px-4 focus:py-2 focus:text-[#1d1530]">Skip to results</a>
      <div className="relative mx-auto flex max-w-page flex-wrap items-center gap-x-6 gap-y-3 px-4 pb-4 pt-4 md:px-6 md:pb-5 md:pt-6 xl:px-8">
        {/* the logo is the heading: it already spells the name, so no text wordmark beside it */}
        <a href="#diapers" className="sign -my-1 shrink-0 rounded-2xl sm:-my-2">
          <img src={logo} alt="The Diaper Aisle" width="200" height="193" className="sign-logo h-auto w-[120px] sm:w-[164px] lg:w-[200px]" />
        </a>
        <div className="flex min-w-0 flex-1 basis-[180px] flex-col items-start gap-3">
          {/* a paper price tag: pointed end, punched hole, a loop of string through it */}
          <p className="tag-wrap">
            <span className="price-tag text-sm font-bold leading-snug sm:text-base">Canadian adult diaper prices, checked daily</span>
          </p>
          <p className="hidden max-w-[46ch] text-base text-brand-sky sm:block">
            Diapers, pull-ups and boosters from {stores.length || "every"} stores, compared per piece with shipping to your province.
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2 text-sm" aria-live="polite">
          {data.status === "loading" && <span className="rounded-full bg-white/10 px-3 py-1.5">Loading today's prices…</span>}
          {data.status === "error" && <span className="rounded-full bg-[#a8302c] px-3 py-1.5 font-semibold">Prices could not be loaded. Reload to retry.</span>}
          {when && (
            <details className="group relative">
              <summary className="flex min-h-[36px] pointer-coarse:min-h-[44px] cursor-pointer list-none items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 hover:bg-white/15 [&::-webkit-details-marker]:hidden">
                <span className={"h-2.5 w-2.5 rounded-full " + (bad.length ? "bg-[#eb665d]" : "bg-[#7fc678]")} aria-hidden="true" />
                <span className="whitespace-nowrap">Updated {when}</span>
                <span className={"text-brand-sky " + (bad.length ? "" : "hidden sm:inline")}>{bad.length ? `${bad.length} of ${stores.length} stores not refreshed` : `${stores.length} stores checked`}</span>
                <Icon name="chev" size={16} className="text-brand-sky transition-transform group-open:rotate-180" />
              </summary>
              <ul className="absolute right-0 z-30 mt-2 w-64 max-w-[calc(100vw-32px)] rounded-xl border border-line bg-card p-2 text-ink shadow-pop">
                {stores.map(([n, s]) => (
                  <li key={n} className="flex items-center gap-2 rounded-lg px-2 py-1.5">
                    <span className={"h-2.5 w-2.5 rounded-full " + (s.ok ? "bg-[#4caf5c]" : "bg-[#d9534f]")} aria-hidden="true" />
                    <span className="flex-1 font-medium">{n}</span>
                    <span className={"text-cap " + (s.ok ? "text-muted" : "font-semibold text-bad")}>{s.ok ? "Checked today" : "Check failed"}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </div>
      <nav aria-label="Sections" className="mx-auto max-w-page px-4 md:px-6 xl:px-8">
        <ul className="flex gap-1 overflow-x-auto -mb-px [scrollbar-width:none]">
          {NAV.map(([h, c]) => (
            <li key={h}>
              <a href={"#" + h} aria-current={route === h ? "page" : undefined}
                className={"flex items-center gap-2 whitespace-nowrap rounded-t-xl px-3 sm:px-4 min-h-[48px] text-base font-semibold transition-colors " +
                  (route === h ? "bg-bg text-ink" : "text-white/90 hover:bg-white/10")}>
                {CATS[c].label}
                {counts[c] != null && <span className={"num hidden text-sm font-medium sm:inline " + (route === h ? "text-muted" : "text-brand-sky")}>{counts[c].toLocaleString()}</span>}
              </a>
            </li>
          ))}
          <li className="ml-auto">
            <a href="#trends" aria-current={route === "trends" ? "page" : undefined}
              className={"flex items-center gap-2 whitespace-nowrap rounded-t-xl px-3 sm:px-4 min-h-[48px] text-base font-semibold transition-colors " +
                (route === "trends" ? "bg-bg text-ink" : "text-white/90 hover:bg-white/10")}>
              <Icon name="chart" className="hidden sm:block" /> Trends
            </a>
          </li>
        </ul>
      </nav>
    </header>
  );
}
