# Tracker source

React 18 + Tailwind 3 + Vite. Source here; `npm run build` writes the site's `../index.html` and `../app/` (nothing else).
The page reads `../data/` (daily data) and `../shipping.json` (shipping rules) at run time.

- `DESIGN-SYSTEM.md`: tokens, type, components, rules. `DESIGN-PLAN.md`: what changed from v1 and why.
- Build: `npm ci && npm run build` (from this folder). Rebuild only when the design changes; the daily run never needs to.
- Shipping rules live in `../shipping.json`; edit them there, no rebuild needed.
