import { useEffect } from "react";
import type { DocsTheme } from "../ipc/docsBridge";
import type { Prefs } from "./layout";
import { DARK_TERMINAL, LIGHT_TERMINAL } from "./terminalThemes";

/** The window's colour scheme, following the documentation's theme where
 * the preferences say so, the terminals' theme, and the document's scheme
 * and language as the styles and assistive technology read them. */
export function useWindowAppearance({
  docsTheme,
  prefersDark,
  prefs,
  locale,
}: {
  docsTheme: DocsTheme;
  prefersDark: boolean;
  prefs: Prefs;
  locale: string;
}) {
  const docsResolved =
    docsTheme === "auto" ? (prefersDark ? "dark" : "light") : docsTheme;
  const scheme =
    prefs.appearance === "follow" ? docsResolved : prefs.appearance;
  const terminalTheme =
    prefs.terminals === "dark" || scheme === "dark"
      ? DARK_TERMINAL
      : LIGHT_TERMINAL;

  useEffect(() => {
    document.documentElement.dataset.scheme = scheme;
    document.documentElement.lang = locale;
  }, [scheme, locale]);
  return { scheme, terminalTheme };
}
