# ui-ux-pro-max output (raw, 2026-11-20)

Query: "price comparison data dashboard" --design-system --density 8 --variance 3 --motion 2 (retry of a broader query that returned an e-commerce landing page).
What was adopted and what was overridden is in ../DESIGN-SYSTEM.md, section 0.

## Design System: The Diaper Aisle

### Design Dials
- **Variance:** 3/10 — Centered / Minimal
- **Motion:** 2/10 — Subtle
- **Density:** 8/10 — Dense / Dashboard

### Pattern
- **Name:** Enterprise Gateway
- **Conversion Focus:** Path selection (I am a...). Mega menu navigation. Trust signals prominent. Provide pause/stop for video and rotating logos; stop on focus and reduced motion. Logo carousel controls must be keyboard operable; pause moving media offscreen/hidden and render a static final state under reduced motion.
- **CTA Placement:** Contact Sales (Primary) + Login (Secondary)
- **Color Strategy:** Corporate: Navy/Grey. High integrity. Conservative accents.
- **Sections:** Hero (Video/Mission) > Solutions by Industry > Solutions by Role > Client Logos > Contact Sales

### Style
- **Name:** Minimalism & Swiss Style
- **Mode Support:** Light supported | Dark supported
- **Keywords:** Clean, simple, spacious, functional, white space, high contrast, geometric, sans-serif, grid-based, essential
- **Best For:** Enterprise apps, dashboards, documentation sites, SaaS platforms, professional tools
- **Performance:** cost:low|drivers:none | **Accessibility:** risk:low|requires:contrast-text-4.5,keyboard,visible-focus,reduced-motion

### Colors
| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#1E40AF` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#3B82F6` | `--color-secondary` |
| On Secondary | `#000000` | `--color-on-secondary` |
| Accent/CTA | `#D97706` | `--color-accent` |
| On Accent/CTA | `#000000` | `--color-on-accent` |
| Background | `#F8FAFC` | `--color-background` |
| Foreground | `#1E3A8A` | `--color-foreground` |
| Card | `#FFFFFF` | `--color-card` |
| Card Foreground | `#1E3A8A` | `--color-card-foreground` |
| Muted | `#E9EEF6` | `--color-muted` |
| Muted Foreground | `#475569` | `--color-muted-foreground` |
| Border | `#DBEAFE` | `--color-border` |
| Destructive | `#DC2626` | `--color-destructive` |
| On Destructive | `#FFFFFF` | `--color-on-destructive` |
| Ring | `#1E40AF` | `--color-ring` |

*Notes: Blue data + amber highlights [Accent adjusted from #F59E0B]*

### Typography
- **Heading:** Fira Code
- **Body:** Fira Sans
- **Mood:** dashboard, data, analytics, code, technical, precise
- **Best For:** Dashboards, analytics, data visualization, admin panels
- **Google Fonts:** https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap
- **CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');
```

### Key Effects
Subtle hover (200-250ms), smooth transitions, sharp shadows if any, clear type hierarchy, fast loading

### Motion
**Scroll Reveal** (Subtle) — Trigger: scroll (viewport enter) | Duration: 300-400ms | Easing: `power1.out`
```js
gsap.from(el, { opacity: 0, y: 12, duration: 0.35, ease: 'power1.out', scrollTrigger: { trigger: el, start: 'top 90%', toggleActions: 'play none none reverse' } });
```
*Framework notes: Requires the ScrollTrigger plugin registered once via gsap.registerPlugin(ScrollTrigger); Use matchMedia('(prefers-reduced-motion: reduce)') to skip non-essential motion and render the final state immediately*
- ✅ Keep the y offset small (8-16px) so it reads as a fade, not a slide
- ❌ Don't reveal below-the-fold content needed for SEO/crawlers as invisible-by-default without a no-JS fallback

### Avoid (Anti-patterns)
- Ornate design
- No filtering

### Pre-Delivery Checklist
- [ ] No emojis as icons (use SVG: Heroicons/Lucide)
- [ ] cursor-pointer on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard nav
- [ ] prefers-reduced-motion respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px


## Supplementary searches
```
## UI Pro Max Search Results
**Domain:** typography | **Query:** readable numbers data tabular
**Source:** typography.csv | **Found:** 1 results

### Result 1
- **Font Pairing Name:** Dashboard Data
- **Category:** Mono + Sans
- **Heading Font:** Fira Code
- **Body Font:** Fira Sans
- **Mood/Style Keywords:** dashboard, data, analytics, code, technical, precise
- **Best For:** Dashboards, analytics, data visualization, admin panels
- **Google Fonts URL:** https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap
- **CSS Import:** @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');
- **Tailwind Config:** fontFamily: { mono: ['Fira Code', 'monospace'], sans: ['Fira Sans', 'sans-serif'] }
- **Notes:** Fira family cohesion. Code for data, Sans for labels.

## UI Pro Max Search Results
**Domain:** chart | **Query:** price trend comparison
**Source:** charts.csv | **Found:** 1 results

### Result 1
- **Data Type:** Trend Over Time
- **Keywords:** trend, time-series, line, growth, timeline, progress, accessible chart, keyboard accessible chart
- **Best Chart Type:** Line Chart
- **Secondary Options:** Area Chart, Smooth Area
- **When to Use:** Data has a time axis; user needs to observe rise/fall trends or rate of change over a continuous period
- **When NOT to Use:** Fewer than 4 data points (use stat card); more than 6 series (visual noise); no time dimension exists
- **Data Volume Threshold:** <1000 pts: SVG; ≥1000 pts: Canvas + downsampling; >10000: aggregate to intervals
- **Color Guidance:** Primary: #0080FF. Multiple series: distinct colors + distinct line styles. Fill: 20% opacity
- **Accessibility Grade:** deprecated: use Accessibility Risk
- **Accessibility Risk:** risk:low
- **Accessibility Notes:** Use solid, dashed, and dotted line styles plus direct series labels; never distinguish series by hue alone.
- **A11y Fallback:** Visible data table plus concise trend summary. Keyboard: focus reveals hover values; +/- buttons zoom; Reset restores the full range.
- **Library Recommendation:** Chart.js, Recharts, ApexCharts
- **Interactive Level:** Hover + Zoom

## UI Pro Max Search Results
**Domain:** ux | **Query:** data table mobile responsive
**Source:** ux-guidelines.csv | **Found:** 2 results

### Result 1
- **Category:** Responsive
- **Issue:** Table Handling
- **Platform:** Web
- **Description:** Tables can overflow on mobile
- **Do:** Use horizontal scroll or card layout
- **Don't:** Wide tables breaking layout
- **Code Example Good:** overflow-x-auto wrapper
- **Code Example Bad:** Table overflows viewport
- **Severity:** Medium

### Result 2
- **Category:** Responsive
- **Issue:** Mobile First
- **Platform:** Web
- **Description:** Design for mobile then enhance for larger
- **Do:** Start with mobile styles then add breakpoints
- **Don't:** Desktop-first causing mobile issues
- **Code Example Good:** Default mobile + md: lg: xl:
- **Code Example Bad:** Desktop default + max-width queries
- **Severity:** Medium

```
