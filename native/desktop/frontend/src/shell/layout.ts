import type { TerminalKind } from "./host";

export type PanelTab = Exclude<TerminalKind, "tui"> | "logs";
export type Maximized = "docs" | "tui" | "panel" | null;

export type TerminalFontSize = "small" | "medium" | "large" | "x-large";

/** Canonical order of the terminal font-size steps. Their sizes live in
 * src/tokens.css; Settings labels each step with its token's own size. */
export const TERMINAL_FONT_SIZES: readonly TerminalFontSize[] = [
  "small",
  "medium",
  "large",
  "x-large",
];

/** The language preference that follows Cadrumo's own output language. */
export const FOLLOW_LANGUAGE = "follow";

export type Prefs = {
  appearance: "follow" | "light" | "dark";
  /** A language code, or `FOLLOW_LANGUAGE`. A code the documentation is not
   * bundled in is ignored where the preference is used. */
  language: string;
  terminals: "match" | "dark";
  orientation: "row" | "column";
  order: "docs" | "tui";
  fontSize: TerminalFontSize;
};

export type Layout = {
  tuiShown: boolean;
  /** The documentation pane's share of the split. */
  splitRatio: number;
  panelOpen: boolean;
  /** The bottom panel's share of the window height. */
  panelRatio: number;
  tab: PanelTab;
  zoom: number;
};

export const DEFAULT_PREFS: Prefs = {
  appearance: "follow",
  language: FOLLOW_LANGUAGE,
  terminals: "match",
  orientation: "row",
  order: "docs",
  fontSize: "medium",
};

export const DEFAULT_LAYOUT: Layout = {
  tuiShown: true,
  splitRatio: 0.56,
  panelOpen: false,
  panelRatio: 0.3,
  tab: "console",
  zoom: 1,
};

const STORE = "cadrumo-shell-layout";
const LANGUAGE_CODE = /^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$/;
const TABS: readonly PanelTab[] = ["console", "python", "logs"];

function pick<T>(value: unknown, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

function share(
  value: unknown,
  fallback: number,
  low: number,
  high: number,
): number {
  return typeof value === "number" &&
    Number.isFinite(value) &&
    value >= low &&
    value <= high
    ? value
    : fallback;
}

// Every stored field is validated: browser storage is a convenience that may
// be missing, cleared or written by an older shell.
export function loadState(): { prefs: Prefs; layout: Layout } {
  let raw: unknown;
  try {
    raw = JSON.parse(localStorage.getItem(STORE) ?? "null");
  } catch {
    raw = null;
  }
  const stored = (raw && typeof raw === "object" ? raw : {}) as {
    prefs?: Record<string, unknown>;
    layout?: Record<string, unknown>;
  };
  const p = stored.prefs ?? {};
  const l = stored.layout ?? {};
  return {
    prefs: {
      appearance: pick(
        p.appearance,
        ["follow", "light", "dark"] as const,
        DEFAULT_PREFS.appearance,
      ),
      language:
        typeof p.language === "string" && LANGUAGE_CODE.test(p.language)
          ? p.language
          : DEFAULT_PREFS.language,
      terminals: pick(
        p.terminals,
        ["match", "dark"] as const,
        DEFAULT_PREFS.terminals,
      ),
      orientation: pick(
        p.orientation,
        ["row", "column"] as const,
        DEFAULT_PREFS.orientation,
      ),
      order: pick(p.order, ["docs", "tui"] as const, DEFAULT_PREFS.order),
      // An older shell stored a numeric point size (12/13/14/16); that no
      // longer matches a named step, so it falls back to the default here.
      fontSize: pick(p.fontSize, TERMINAL_FONT_SIZES, DEFAULT_PREFS.fontSize),
    },
    layout: {
      tuiShown:
        typeof l.tuiShown === "boolean" ? l.tuiShown : DEFAULT_LAYOUT.tuiShown,
      splitRatio: share(l.splitRatio, DEFAULT_LAYOUT.splitRatio, 0.1, 0.9),
      panelOpen:
        typeof l.panelOpen === "boolean"
          ? l.panelOpen
          : DEFAULT_LAYOUT.panelOpen,
      panelRatio: share(l.panelRatio, DEFAULT_LAYOUT.panelRatio, 0.1, 0.9),
      tab: pick(l.tab, TABS, DEFAULT_LAYOUT.tab),
      zoom: share(l.zoom, DEFAULT_LAYOUT.zoom, 0.5, 2),
    },
  };
}

export function saveState(prefs: Prefs, layout: Layout): void {
  try {
    localStorage.setItem(STORE, JSON.stringify({ prefs, layout }));
  } catch {
    // The defaults apply next launch.
  }
}
