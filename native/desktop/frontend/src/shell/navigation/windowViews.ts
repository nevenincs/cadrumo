// How the window implements the register's `gui` elements: each id names a
// change of the layout store, which stays the one owner of what is shown.
// The register says only that the window implements an element; this table
// says how, and a coverage test holds it to the register's gui ids. A gui
// element with no entry here is declared but not drawn.

import type { LedgerSection, PanelTab } from "../layout";

/** The window's pages that a register element opens. */
export type WindowPage =
  "profile" | "calendar" | "ledger" | "declarations" | "docs" | "browser";

/** A dialog a page opens over itself as a view is shown. */
export type WindowDialog = "aeat-access";

/** A host port a view needs; without it the window does not implement it. */
export type WindowPort =
  "userProfile" | "views" | "ledger" | "modelo" | "sedeView";

export type WindowView =
  /** A page of the first pane: opening it unmounts the page shown before. */
  | {
      readonly kind: "page";
      readonly page: WindowPage;
      /** The Ledger section it shows; null keeps the section saved. */
      readonly section: LedgerSection | null;
      /** The dialog the page opens as it is shown; absent for the page
       * itself. */
      readonly dialog?: WindowDialog;
    }
  /** The agent column, beside the rail. */
  | { readonly kind: "agent" }
  /** The terminal workspace pane. */
  | { readonly kind: "terminal" }
  /** The bottom panel, on a tab; null keeps the tab saved. */
  | { readonly kind: "panel"; readonly tab: PanelTab | null };

export type WindowViewEntry = {
  readonly view: WindowView;
  /** Only the signed-in profile's views are shown. */
  readonly signedIn: boolean;
  readonly port: WindowPort | null;
  /** The link parameters the window honours for this element. */
  readonly honours: readonly string[];
};

const page = (
  name: WindowPage,
  section: LedgerSection | null,
  port: WindowPort | null,
): WindowViewEntry => ({
  view: { kind: "page", page: name, section },
  signedIn: name !== "docs",
  port,
  honours: [],
});

const panel = (tab: PanelTab | null): WindowViewEntry => ({
  view: { kind: "panel", tab },
  signedIn: false,
  port: null,
  honours: [],
});

/** Register id to how the window opens it. The movements and invoices
 * grids reveal the row a `select` names. */
export const WINDOW_VIEWS: Readonly<Record<string, WindowViewEntry>> = {
  profile: page("profile", null, "userProfile"),
  "profile/aeat-access": {
    ...page("profile", null, "userProfile"),
    view: {
      kind: "page",
      page: "profile",
      section: null,
      dialog: "aeat-access",
    },
  },
  calendar: page("calendar", null, "views"),
  docs: page("docs", null, null),
  ledger: page("ledger", null, "ledger"),
  "ledger/movements": {
    ...page("ledger", "movements", "ledger"),
    honours: ["select"],
  },
  "ledger/invoices": {
    ...page("ledger", "invoices", "ledger"),
    honours: ["select"],
  },
  "ledger/documents": page("ledger", "documents", "ledger"),
  "ledger/rules": page("ledger", "rules", "ledger"),
  "ledger/registers": page("ledger", "registers", "ledger"),
  "ledger/health": page("ledger", "health", "ledger"),
  declarations: page("declarations", null, "modelo"),
  browser: page("browser", null, "sedeView"),
  agent: { view: { kind: "agent" }, signedIn: true, port: null, honours: [] },
  terminal: {
    view: { kind: "terminal" },
    signedIn: false,
    port: null,
    honours: [],
  },
  panel: panel(null),
  "panel/console": panel("console"),
  "panel/python": panel("python"),
  "panel/logs": panel("logs"),
};

/** The window's own view of `id`, or undefined where the window has none. */
export function windowView(id: string): WindowViewEntry | undefined {
  return Object.hasOwn(WINDOW_VIEWS, id) ? WINDOW_VIEWS[id] : undefined;
}

/** The element of the page shown, the inverse of this table for pages: a
 * Ledger section's own id, otherwise the page's; a dialog over a page is
 * not the page. Undefined for a page no element opens. */
export function pageViewId(
  page: string,
  ledgerSection: LedgerSection,
): string | undefined {
  const section = page === "ledger" ? ledgerSection : null;
  return Object.keys(WINDOW_VIEWS).find((id) => {
    const view = WINDOW_VIEWS[id]?.view;
    return (
      view?.kind === "page" &&
      view.page === page &&
      view.section === section &&
      view.dialog === undefined
    );
  });
}

/** What the window has mounted that a navigation can take down: the page
 * shown, and for the Ledger its section, by the ids owners register with. */
export function mountedNow(
  page: string,
  ledgerSection: LedgerSection,
): ReadonlySet<string> {
  return new Set(
    page === "ledger" ? [page, `ledger/${ledgerSection}`] : [page],
  );
}

/** What opening `view` would take down of what is mounted now: leaving a
 * page takes it down; a section keeps its page; a pane, the panel or a TUI
 * page takes down nothing. */
export function unmountedBy(
  mounted: ReadonlySet<string>,
  view: WindowView,
  ledgerSection: LedgerSection,
): ReadonlySet<string> {
  if (view.kind !== "page") return new Set();
  const next = mountedNow(view.page, view.section ?? ledgerSection);
  return new Set([...mounted].filter((id) => !next.has(id)));
}
