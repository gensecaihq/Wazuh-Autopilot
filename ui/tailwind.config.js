/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"] },
      colors: {
        bg: v("bg"),
        deep: v("deep"),
        card: v("card"),
        card2: v("card2"),
        line: v("line"),
        fg: v("fg"),
        muted: v("muted"),
        subtle: v("subtle"),
        accent: v("accent"),
        danger: v("danger"),
        success: v("success"),
        info: v("info"),
        warn: v("warn"),
      },
      borderRadius: { xl: "0.875rem" },
      keyframes: {
        pulseRing: { "0%": { boxShadow: "0 0 0 0 rgb(var(--accent) / .55)" }, "100%": { boxShadow: "0 0 0 10px rgb(var(--accent) / 0)" } },
        shimmer: { "0%": { backgroundPosition: "-400px 0" }, "100%": { backgroundPosition: "400px 0" } },
      },
      animation: { pulseRing: "pulseRing 1.6s ease-out infinite", shimmer: "shimmer 1.4s linear infinite" },
    },
  },
  plugins: [],
};
