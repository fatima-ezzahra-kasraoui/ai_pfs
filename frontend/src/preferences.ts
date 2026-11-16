/**
 * Préférences d'interface non sensibles (thème). Seul module autorisé à toucher au stockage du navigateur,
 * et uniquement pour des préférences : jamais de jeton, de mot de passe ni de donnée de sécurité.
 */
export type Theme = "system" | "light" | "dark";
const KEY = "agentshield.theme";

export function loadTheme(): Theme {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function saveTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(KEY, theme);
  } catch {
    /* stockage indisponible : la préférence n'est simplement pas mémorisée */
  }
}

export function applyTheme(theme: Theme): void {
  if (theme === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", theme);
}
