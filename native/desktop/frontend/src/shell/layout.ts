import type { TerminalKind } from "./host";

export type PanelTab = Exclude<TerminalKind, "tui"> | "logs";
export type Maximized = "agent" | "docs" | "tui" | "panel" | null;

export type TerminalFontSize = "small" | "medium" | "large" | "x-large";

/** Canonical order of the terminal font-size steps. Their sizes live in
 * src/styles/tokens.css; Settings labels each step with its token's own size. */
export const TERMINAL_FONT_SIZES: readonly TerminalFontSize[] = [
  "small",
  "medium",
  "large",
  "x-large",
];

export type Prefs = {
  appearance: "follow" | "light" | "dark";
  terminals: "match" | "dark";
  orientation: "row" | "column";
  order: "docs" | "tui";
  fontSize: TerminalFontSize;
};

export type ProfileView = {
  section: string;
  filter: "all" | "missing" | "required" | "saved";
  expanded: string[];
  collapsed: string[];
};

export type Layout = {
  page: "docs" | "calendar" | "profile";
  maximized: Maximized;
  /** Null follows the host default until the person chooses a level. */
  logLevel: number | null;
  calendarView: "months" | "list";
  profileView: ProfileView;
  /** The agent column, always beside the rail. */
  agentShown: boolean;
  /** The agent column's share of the window width. */
  agentRatio: number;
  tuiShown: boolean;
  docsShown: boolean;
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
  terminals: "match",
  orientation: "row",
  order: "tui",
  fontSize: "medium",
};

export const DEFAULT_LAYOUT: Layout = {
  page: "profile",
  maximized: null,
  logLevel: null,
  calendarView: "months",
  profileView: {
    section: "",
    filter: "all",
    expanded: ["identity", "contact"],
    collapsed: [],
  },
  agentShown: true,
  agentRatio: 0.24,
  tuiShown: false,
  // The documentation is opened on request: an empty first pane is not a
  // reason to show it.
  docsShown: false,
  splitRatio: 0.56,
  panelOpen: false,
  panelRatio: 0.3,
  tab: "console",
  zoom: 1,
};

const STORE = "cadrumo-shell-layout";

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

function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function identifiers(value: unknown, fallback: string[]): string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string")
    ? [...new Set(value)]
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
  const p = object(stored.prefs);
  // Retire the old independent language authority as soon as it is read,
  // including launches that leave before the debounced layout save.
  if (Object.hasOwn(p, "language")) {
    const migrated = { ...p };
    delete migrated.language;
    try {
      localStorage.setItem(
        STORE,
        JSON.stringify({ ...stored, prefs: migrated }),
      );
    } catch {
      // Storage can be read-only; the obsolete value is still ignored below.
    }
  }

  const l = object(stored.layout);
  const profile = object(l.profileView);
  return {
    prefs: {
      appearance: pick(
        p.appearance,
        ["follow", "light", "dark"] as const,
        DEFAULT_PREFS.appearance,
      ),
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
      // A shell from before the documentation could be put away stored the
      // documentation first as its default, not as anybody's choice: the
      // order it saved gives way to today's default.
      order:
        typeof l.docsShown === "boolean"
          ? pick(p.order, ["docs", "tui"] as const, DEFAULT_PREFS.order)
          : DEFAULT_PREFS.order,
      // An older shell stored a numeric point size (12/13/14/16); that no
      // longer matches a named step, so it falls back to the default here.
      fontSize: pick(p.fontSize, TERMINAL_FONT_SIZES, DEFAULT_PREFS.fontSize),
    },
    layout: {
      page: pick(
        l.page,
        ["docs", "calendar", "profile"] as const,
        l.page === undefined &&
          (typeof l.tuiShown === "boolean" || typeof l.docsShown === "boolean")
          ? "docs"
          : DEFAULT_LAYOUT.page,
      ),
      maximized: pick(
        l.maximized,
        ["agent", "docs", "tui", "panel", null] as const,
        null,
      ),
      logLevel: pick(l.logLevel, [0, 1, 2, 3, 4, null], null),
      calendarView: pick(
        l.calendarView,
        ["months", "list"] as const,
        DEFAULT_LAYOUT.calendarView,
      ),
      profileView: {
        section: typeof profile.section === "string" ? profile.section : "",
        filter: pick(
          profile.filter,
          ["all", "missing", "required", "saved"] as const,
          "all",
        ),
        expanded: identifiers(
          profile.expanded,
          DEFAULT_LAYOUT.profileView.expanded,
        ),
        collapsed: identifiers(profile.collapsed, []),
      },
      agentShown:
        typeof l.agentShown === "boolean"
          ? l.agentShown
          : DEFAULT_LAYOUT.agentShown,
      agentRatio: share(l.agentRatio, DEFAULT_LAYOUT.agentRatio, 0.1, 0.9),
      tuiShown:
        typeof l.tuiShown === "boolean" ? l.tuiShown : DEFAULT_LAYOUT.tuiShown,
      docsShown:
        typeof l.docsShown === "boolean"
          ? l.docsShown
          : DEFAULT_LAYOUT.docsShown,
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
    localStorage.setItem(
      STORE,
      JSON.stringify({
        prefs,
        layout,
      }),
    );
  } catch {
    // The defaults apply next launch.
  }
}
