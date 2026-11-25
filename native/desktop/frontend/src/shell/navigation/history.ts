// The window's back and forward: where the viewer has been in this window,
// as a stack of positions. A position is only a place the window shows: a
// page, its Ledger section, the declaration open and that declaration's view,
// each by the id the window already shows it under. It holds no value of any
// record, lives in memory for one sign-in only, and is never stored.

import type { Layout, LedgerSection } from "../layout";

/** One place the viewer has been; `View` names a declaration's views. */
export type ViewerPosition<View extends string = string> = {
  readonly page: Layout["page"];
  /** The Ledger section shown, on the Ledger page only. */
  readonly section: LedgerSection | null;
  /** The declaration open, on the declarations page only; null is the
   * list. */
  readonly workUnitId: string | null;
  /** The open declaration's view by its tab id, or null for the view it
   * opens on. */
  readonly view: View | null;
};

/** The positions in the order they were shown, and the one shown now. */
export type ViewerHistory<View extends string = string> = {
  readonly entries: readonly ViewerPosition<View>[];
  readonly index: number;
};

/** A history with nothing shown yet. */
export function emptyHistory<View extends string>(): ViewerHistory<View> {
  return { entries: [], index: -1 };
}

/** How many positions are kept; the oldest go first. */
export const HISTORY_LIMIT = 100;

/** The position the window shows, from its layout and its open declaration:
 * what another page holds is not part of where the viewer is. */
export function viewerPosition<View extends string>(
  page: Layout["page"],
  ledgerSection: LedgerSection,
  declaration: { workUnitId: string | null; view: View | null },
): ViewerPosition<View> {
  const declarations = page === "declarations";
  const workUnitId = declarations ? declaration.workUnitId : null;
  return {
    page,
    section: page === "ledger" ? ledgerSection : null,
    workUnitId,
    view: workUnitId === null ? null : declaration.view,
  };
}

export function samePosition(a: ViewerPosition, b: ViewerPosition): boolean {
  return (
    a.page === b.page &&
    a.section === b.section &&
    a.workUnitId === b.workUnitId &&
    a.view === b.view
  );
}

/** The history with `position` shown: unchanged when it is the one shown
 * already; otherwise it replaces whatever lay ahead and becomes the newest. */
export function recordPosition<View extends string>(
  history: ViewerHistory<View>,
  position: ViewerPosition<View>,
  limit = HISTORY_LIMIT,
): ViewerHistory<View> {
  const shown = history.entries[history.index];
  if (shown && samePosition(shown, position)) return history;
  const entries = [...history.entries.slice(0, history.index + 1), position];
  const kept = entries.slice(Math.max(0, entries.length - limit));
  return { entries: kept, index: kept.length - 1 };
}

/** The index one step back (-1) or forward (1), or null at either end. */
export function stepIndex(
  history: ViewerHistory,
  delta: -1 | 1,
): number | null {
  const index = history.index + delta;
  return index >= 0 && index < history.entries.length ? index : null;
}
