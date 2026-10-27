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
  /** Which details are listed. */
  show: "all" | "unset" | "required" | "filled";
  group: "section" | "status" | "none";
  sort: "form" | "missing" | "alpha";
  /** The groups the person closed; every other one is open. */
  collapsed: string[];
};

// What a shell from before the show filter stored as its filter.
const LEGACY_FILTER = {
  missing: "unset",
  required: "required",
  saved: "filled",
} as const;
const legacyShow = (filter: unknown): ProfileView["show"] =>
  typeof filter === "string" && Object.hasOwn(LEGACY_FILTER, filter)
    ? LEGACY_FILTER[filter as keyof typeof LEGACY_FILTER]
    : "all";

/** The Ledger page's sections: three tabs, and three under its setup menu. */
export const LEDGER_SECTIONS = [
  "movements",
  "invoices",
  "documents",
  "rules",
  "registers",
  "health",
] as const;
export type LedgerSection = (typeof LEDGER_SECTIONS)[number];

/** How the Ledger page is laid out. Presentation only: names of columns,
 * groupings and views the page defines, and sizes. Never a period, a value,
 * a search or anything staged. */
export type LedgerView = {
  section: LedgerSection;
  /** The movements grid's columns, by the ids the page gives them. */
  columns: {
    hidden: string[];
    order: string[];
    /** Widths in CSS pixels, by column id. */
    widths: Record<string, number>;
  };
  density: "compact" | "comfortable";
  /** The grouping key the page offers, or null for none. */
  groupBy: string | null;
  /** The saved view chosen, by the page's id for it. */
  savedView: string | null;
  inspectorOpen: boolean;
  /** The inspector's width in CSS pixels; null keeps the token's. */
  inspectorWidth: number | null;
  /** The format the last export was written in. */
  exportFormat: "csv" | "jsonl" | "xlsx";
};

export type Layout = {
  page: "docs" | "calendar" | "profile" | "ledger" | "declarations" | "browser";
  maximized: Maximized;
  /** Null follows the host default until the person chooses a level. */
  logLevel: number | null;
  calendarView: "months" | "list";
  profileView: ProfileView;
  ledgerView: LedgerView;
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
    show: "all",
    group: "section",
    sort: "form",
    collapsed: [],
  },
  ledgerView: {
    section: "movements",
    columns: { hidden: [], order: [], widths: {} },
    density: "compact",
    groupBy: null,
    savedView: null,
    inspectorOpen: false,
    inspectorWidth: null,
    exportFormat: "csv",
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

// The shape of a name the Ledger page gives a column, grouping or view. Any
// other stored text is dropped: what is kept here is never free text.
const VIEW_ID = /^[a-z][a-z0-9_.:-]{0,63}$/;
const VIEW_IDS_MAX = 64;
const viewId = (value: unknown): string | null =>
  typeof value === "string" && VIEW_ID.test(value) ? value : null;
const viewIds = (value: unknown): string[] =>
  Array.isArray(value) && value.length <= VIEW_IDS_MAX
    ? [...new Set(value.map(viewId).filter((id) => id !== null))]
    : [];
const width = (value: unknown): number | null =>
  typeof value === "number" &&
  Number.isFinite(value) &&
  value >= 16 &&
  value <= 4096
    ? Math.round(value)
    : null;

function ledgerViewOf(value: unknown): LedgerView {
  const stored = object(value);
  const columns = object(stored.columns);
  const widths: Record<string, number> = {};
  for (const [id, size] of Object.entries(object(columns.widths)).slice(
    0,
    VIEW_IDS_MAX,
  )) {
    const kept = width(size);
    if (viewId(id) !== null && kept !== null) widths[id] = kept;
  }
  return {
    section: pick(stored.section, LEDGER_SECTIONS, "movements"),
    columns: {
      hidden: viewIds(columns.hidden),
      order: viewIds(columns.order),
      widths,
    },
    density: pick(
      stored.density,
      ["compact", "comfortable"] as const,
      "compact",
    ),
    groupBy: viewId(stored.groupBy),
    savedView: viewId(stored.savedView),
    inspectorOpen:
      typeof stored.inspectorOpen === "boolean" ? stored.inspectorOpen : false,
    inspectorWidth: width(stored.inspectorWidth),
    exportFormat: pick(
      stored.exportFormat,
      ["csv", "jsonl", "xlsx"] as const,
      "csv",
    ),
  };
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
      // The Browser page is saved with the rest but never restored: opening it
      // starts a browser on the profile's session, which a launch must not do
      // by itself.
      page: pick(
        l.page,
        ["docs", "calendar", "profile", "ledger", "declarations"] as const,
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
        show: pick(
          profile.show,
          ["all", "unset", "required", "filled"] as const,
          legacyShow(profile.filter),
        ),
        group: pick(
          profile.group,
          ["section", "status", "none"] as const,
          "section",
        ),
        sort: pick(profile.sort, ["form", "missing", "alpha"] as const, "form"),
        collapsed: identifiers(profile.collapsed, []),
      },
      ledgerView: ledgerViewOf(l.ledgerView),
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
