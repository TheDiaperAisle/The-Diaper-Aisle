# Tracker v2 (redesign, in review)

React 18 + Tailwind 3 + Vite. Source here; the static build goes to `../v2/`, which GitHub Pages serves at
`/The-Diaper-Aisle/v2/` once merged. It reads the same live `data/` files as `index.html`, which is unchanged.

- `DESIGN-SYSTEM.md`: tokens, type, components, rules. `DESIGN-PLAN.md`: what changed from v1 and why.
- Build: `npm ci && npm run build` (from this folder). Rebuild only when the design changes; the daily run never needs to.
- Shipping rules: `src/lib/ship.json` is a copy of the `SHIP` constant in `index.html`. Update both if shipping changes.
