import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

const NO_HTML = { selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']", message: "Interdit : le contenu issu d'un agent n'est jamais interprété comme du HTML." };
const NO_STORAGE = [
  { selector: "Identifier[name='localStorage']", message: "Pas de stockage local de jeton ; seules les préférences d'interface passent par src/preferences.ts." },
  { selector: "Identifier[name='sessionStorage']", message: "Pas de stockage navigateur pour des données de sécurité." },
];

export default tseslint.config(
  { ignores: ["dist", "coverage"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: { ...reactHooks.configs.recommended.rules, "no-restricted-syntax": ["error", NO_HTML, ...NO_STORAGE] },
  },
  {
    files: ["src/preferences.ts", "src/**/*.test.{ts,tsx}", "src/test/**"],
    rules: { "no-restricted-syntax": ["error", NO_HTML] },
  },
);
