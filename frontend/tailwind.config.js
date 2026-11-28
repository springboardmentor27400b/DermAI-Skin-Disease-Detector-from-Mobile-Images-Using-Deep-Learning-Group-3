/** @type {import('tailwindcss').Config} */
const v = (n) => `rgb(var(--${n}) / <alpha-value>)`;
export default {
  future: { hoverOnlyWhenSupported: true },
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: v("ink"), mute: v("mute"), canvas: v("canvas"), line: v("line"),
        accent: { DEFAULT: v("accent"), dark: v("accent-dark"), soft: v("accent-soft") },
        clay: v("clay"),
        hero: { DEFAULT: v("hero-bg"), fg: v("hero-fg"), mute: v("hero-mute") },
        amber: { DEFAULT: "#A8650C", soft: "#F6E7CF" },
        danger: { DEFAULT: "#B3261E", soft: "#F6DAD7" },
        ok: { DEFAULT: "#2F7D4F", soft: "#D9ECE0" },
      },
      fontFamily: {
        sans: ['"Instrument Sans"', "system-ui", "Segoe UI", "sans-serif"],
        display: ["Fraunces", "Georgia", "Times New Roman", "serif"],
      },
      borderRadius: { DEFAULT: "var(--radius)", lg: "calc(var(--radius) * 1.5)" },
    },
  },
  plugins: [],
};

