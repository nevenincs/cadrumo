/**
 * The documentation frame's page history as the window learns it from the
 * page's own reports: each `ready` and `location` names the address it is on
 * and, from a page that says so, the place of its entry in the frame's
 * history and whether it came back to that entry or made a new one. The page
 * runs on another origin, so the window cannot read its history; it keeps its
 * own record instead, which follows the page's report whoever moved it: the
 * window's Back and Forward, or the page's own (a link, the mouse's back
 * button, a script). Without a place, a report that follows a Back or Forward
 * the window asked for moves within the record, and any other one is a new
 * page that drops what lay ahead, as a browser's history does.
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

/** Where a page's history entry stands, as the page reports it. */
export type DocsPlace = {
  /** The entry's place in the frame's history, from 0. */
  readonly entry: number;
  /** True when the page came back to an entry it already had. */
  readonly traversed: boolean;
};

/** A place read from a page's report, or null where it reported none. */
export function readDocsPlace(
  entry: unknown,
  traversed: unknown,
): DocsPlace | null {
  return typeof entry === "number" &&
    Number.isSafeInteger(entry) &&
    entry >= 0 &&
    typeof traversed === "boolean"
    ? { entry, traversed }
    : null;
}

/** The page reported that it is on `url`, at `place` where it said. */
export function docsVisited(
  history: DocsHistory,
  url: string,
  place: DocsPlace | null = null,
): DocsHistory {
  const { entries, index, pending } = history;
  if (place) {
    // Entries before the window first heard of the page (a frame that kept
    // its history across a reload of the window) are known only to exist.
    const next = Array.from(
      {
        length: Math.max(place.entry + 1, place.traversed ? entries.length : 0),
      },
      (_, at) => entries[at] ?? "",
    );
    next[place.entry] = url;
    return { entries: next, index: place.entry, pending: null };
  }
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
