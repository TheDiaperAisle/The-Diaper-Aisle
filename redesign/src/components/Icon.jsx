// Inline stroke icons (24px grid, 1.75 stroke). Decorative by default; pass a label to make one meaningful.
const P = {
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  filter: <path d="M4 5h16M7 12h10M10 19h4" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  check: <path d="m5 12.5 4.5 4.5L19 7" />,
  ext: <><path d="M14 4h6v6" /><path d="M20 4 11 13" /><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></>,
  chev: <path d="m6 9 6 6 6-6" />,
  up: <path d="M12 19V5m-6 6 6-6 6 6" />,
  down: <path d="M12 5v14m6-6-6 6-6-6" />,
  truck: <><path d="M3 6h11v10H3zM14 10h4l3 3v3h-7" /><circle cx="7" cy="17.5" r="1.8" /><circle cx="17" cy="17.5" r="1.8" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m4 7 8 6 8-6" /></>,
  copy: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" /></>,
  chart: <path d="M4 19h16M6 15l4-5 3 3 5-7" />,
  sort: <path d="M7 4v16m-3-3 3 3 3-3M17 20V4m-3 3 3-3 3 3" />,
  back: <path d="M15 6l-6 6 6 6" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
  tag: <><path d="M3 12V4h8l9 9-8 8z" /><circle cx="7.5" cy="8.5" r="1.3" /></>,
};
export default function Icon({ name, size = 18, label, className = "" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"
      strokeLinejoin="round" className={"shrink-0 " + className} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      {P[name]}
    </svg>
  );
}
