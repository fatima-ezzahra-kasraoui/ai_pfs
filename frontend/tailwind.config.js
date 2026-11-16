/** @type {import('tailwindcss').Config} */
// Les couleurs pointent vers les variables CSS de src/styles.css : le thème clair/sombre
// (préférence système ou data-theme) s'applique donc sans classes `dark:`.
// `preflight` est désactivé pour ne pas altérer les pages existantes (styles.css).
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  corePlugins: { preflight: false },
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        fg: "var(--text)",
        muted: "var(--muted)",
        line: "var(--border)",
        primary: { DEFAULT: "var(--primary)", fg: "var(--primary-text)" },
        ok: "var(--ok)",
        warn: "var(--warn)",
        danger: "var(--danger)",
        info: "var(--info)",
      },
      fontFamily: { sans: ['"Inter Variable"', "Inter", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
