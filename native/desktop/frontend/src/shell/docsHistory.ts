/**
 * The documentation frame's page history as the window learns it from the
 * page's own reports: each `ready` and `location` names the address it is on.
 * The page runs on another origin, so the window cannot read its history; it
 * keeps its own record instead. A report that follows a Back or Forward the
 * window asked for moves within the record, and any other one is a new page
 * that drops what lay ahead, as a browser's history does.
 */
export type DocsHistory = {
  readonly entries: readonly string[];
  /** The entry shown now; -1 before the first page reported itself. */
  readonly index: number;
  /** The move the window asked of the page and is waiting to hear of. */
  readonly pending: "back" | "forward" | null;
};

export const NO_DOCS_HISTORY: DocsHistory = {
  entries: [],
  index: -1,
  pending: null,
};

/** The page reported that it is on `url`. */
export function docsVisited(history: DocsHistory, url: string): DocsHistory {
  const { entries, index, pending } = history;
  if (pending === "back" && index > 0) {
    const next = [...entries];
    next[index - 1] = url;
    return { entries: next, index: index - 1, pending: null };
  }
  if (pending === "forward" && index < entries.length - 1) {
    const next = [...entries];
    next[index + 1] = url;
    return { entries: next, index: index + 1, pending: null };
  }
  // The same address again is that page reloading, not a new entry.
  if (index >= 0 && entries[index] === url)
    return pending === null ? history : { ...history, pending: null };
  return {
    entries: [...entries.slice(0, index + 1), url],
    index: index + 1,
    pending: null,
  };
}

/** The window asks the page to move; nothing changes where it cannot. */
export function docsTravel(
  history: DocsHistory,
  direction: "back" | "forward",
): DocsHistory {
  if (!docsCan(history)[direction]) return history;
  return { ...history, pending: direction };
}

/** The move asked for was never reported, so it is no longer awaited. */
export function docsTravelLapsed(history: DocsHistory): DocsHistory {
  return history.pending === null ? history : { ...history, pending: null };
}

/** Whether Back and Forward can move the page now. */
export function docsCan(history: DocsHistory): {
  back: boolean;
  forward: boolean;
} {
  return {
    back: history.index > 0,
    forward: history.index >= 0 && history.index < history.entries.length - 1,
  };
}
