import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { getJSON, loadSet, prepareRows, bigSrc, SHIP, SHIP_URL } from "./data";

// One shared load of the published data; components subscribe to it.
const state = { status: "loading", meta: null, rows: [], groups: new Map(), thumbs: {}, big: {}, hist: null, histStatus: "idle", error: null };
const subs = new Set();
let version = 0;
const emit = () => { version++; subs.forEach(f => f()); };
const subscribe = f => { subs.add(f); return () => subs.delete(f); };

let started = false;
async function start() {
  if (started) return; started = true;
  try {
    state.meta = await getJSON("meta.json");
    const v = "?v=" + encodeURIComponent(state.meta.lastRun || Date.now());
    const [cats, ship] = await Promise.all([
      loadSet("catalog", state.meta.catalogDocs),
      fetch(SHIP_URL + v).then(r => r.ok ? r.json() : null).catch(() => null),   // without it, delivered prices show "—"
    ]);
    if (ship) Object.assign(SHIP, ship);
    Object.assign(state, prepareRows(cats), { status: "ready" }); emit();
    const th = await loadSet("thumbs", state.meta.thumbDocs);
    const o = {}, big = {};
    th.forEach(d => Object.entries(d.t || {}).forEach(([k, v]) => { o[k] = v.d; if (v.src) big[k] = bigSrc(v.src); }));
    state.thumbs = o; state.big = big; emit();
  } catch (e) { state.status = "error"; state.error = String(e); emit(); }
}
export async function loadHistory() {
  if (state.hist || state.histStatus === "loading") return;
  state.histStatus = "loading"; emit();
  try {
    const docs = await loadSet("history", state.meta?.historyDocs);
    const h = {}; docs.forEach(d => Object.assign(h, d.h || {}));
    Object.values(h).forEach(x => x.sort((a, b) => a[0] < b[0] ? -1 : 1));
    state.hist = h; state.histStatus = "ready";
  } catch (e) { state.histStatus = "error"; }
  emit();
}

export function useData() {
  useEffect(() => { start(); }, []);
  useSyncExternalStore(subscribe, () => version);
  return state;
}

// hash routes: #/diapers #/pullups #/boosters #/trends (v1 links like #diapers still work)
const parse = () => { const h = location.hash.replace(/^#\/?/, ""); return ["diapers","pullups","boosters","trends"].includes(h) ? h : "diapers"; };
export function useRoute() {
  const [r, setR] = useState(parse);
  useEffect(() => { const f = () => setR(parse()); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  return r;
}

export function useMedia(q) {
  const [m, setM] = useState(() => matchMedia(q).matches);
  useEffect(() => { const mq = matchMedia(q), f = () => setM(mq.matches); mq.addEventListener("change", f); f(); return () => mq.removeEventListener("change", f); }, [q]);
  return m;
}

// measured width, so charts draw at real size and their text never shrinks below 13px
export function useWidth() {
  const ref = useRef(null); const [w, setW] = useState(0);
  useEffect(() => { const el = ref.current; if (!el) return; const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width))); ro.observe(el); return () => ro.disconnect(); }, []);
  return [ref, w];
}

export function useLocal(key, init) {
  const [v, setV] = useState(() => { try { const s = localStorage.getItem(key); return s ? { ...init, ...JSON.parse(s) } : init; } catch { return init; } });
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* private mode */ } }, [key, v]);
  return [v, setV];
}
