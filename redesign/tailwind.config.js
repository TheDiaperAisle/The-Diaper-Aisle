/** Token names only; values live in src/index.css (light + dark). See DESIGN-SYSTEM.md. */
const c = n => `rgb(var(--${n}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: Object.fromEntries(["bg","card","sunken","ink","muted","line","line-strong","accent","on-accent","accent-soft",
        "good","good-soft","bad","bad-soft","warn","brand-ink","brand-blue","brand-sky"].map(n => [n, c(n)])),
      fontFamily: { sans: ['"IBM Plex Sans"', "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"], display: ["Rubik", "system-ui", "sans-serif"] },
      fontSize: {
        cap: ["13px", "18px"], sm: ["14px", "20px"], base: ["16px", "24px"], price: ["17px", "24px"],
        h3: ["20px", "28px"], h2: ["24px", "30px"], h1: ["32px", "38px"],
      },
      boxShadow: { pop: "0 12px 32px -8px rgb(23 17 42 / .28), 0 2px 6px rgb(23 17 42 / .12)" },
      maxWidth: { page: "1440px" },
    },
  },
  plugins: [
    // touch screens: lift small controls to the 44px target
    ({ addVariant }) => { addVariant("pointer-coarse", "@media (pointer: coarse)"); },
  ],
};
