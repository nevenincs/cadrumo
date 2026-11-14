import { useCallback, useEffect, useRef, useState } from "react";

// Whether a pane around a page is shown, and how large the person drew it,
// kept in the shell's browser storage for whoever uses this window. It is
// presentation only: a pane's name and its sizes in CSS pixels, never a
// value, a declaration or anything the backend serves, and it is never sent
// anywhere. Storage may be missing, cleared, read-only or written by an older
// shell; every pane then opens at its defaults.

const STORE = "cadrumo-pane-preferences";
const VERSION = 1;
const PANES_MAX = 32;
const PANE_ID = /^[a-z][a-z0-9_.:-]{0,63}$/;
const SIZE_LEAST = 16;
const SIZE_MOST = 4096;

/** Where a pane is drawn: beside the page, or under it. Each placement keeps
 * its own size, since a width says nothing about a height. */
export type PanePlacement = "side" | "bottom";

export type PanePreference = {
  /** Null follows the page's default until the person shows or hides it. */
  open: boolean | null;
  /** Sizes in CSS pixels by placement; null keeps the page's default. */
  side: number | null;
  bottom: number | null;
};

export const DEFAULT_PANE_PREFERENCE: PanePreference = {
  open: null,
  side: null,
  bottom: null,
};

const size = (value: unknown): number | null =>
  typeof value === "number" &&
  Number.isFinite(value) &&
  value >= SIZE_LEAST &&
  value <= SIZE_MOST
    ? Math.round(value)
    : null;

/** One stored pane, with anything unexpected dropped. */
export function panePreferenceOf(value: unknown): PanePreference {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    return DEFAULT_PANE_PREFERENCE;
  const held = value as Record<string, unknown>;
  return {
    open: typeof held.open === "boolean" ? held.open : null,
    side: size(held.side),
    bottom: size(held.bottom),
  };
}

function readPanes(): Record<string, unknown> {
  let raw: unknown;
  try {
    raw = JSON.parse(localStorage.getItem(STORE) ?? "null");
  } catch {
    return {};
  }
  if (raw === null || typeof raw !== "object") return {};
  const held = raw as Record<string, unknown>;
  if (held.version !== VERSION) return {};
  const panes = held.panes;
  return panes !== null && typeof panes === "object" && !Array.isArray(panes)
    ? (panes as Record<string, unknown>)
    : {};
}

/** What is kept for the pane `id`, or its defaults. */
export function readPanePreference(id: string): PanePreference {
  if (!PANE_ID.test(id)) return DEFAULT_PANE_PREFERENCE;
  return panePreferenceOf(readPanes()[id]);
}

/** Keeps `preference` for the pane `id`; other panes keep theirs. */
export function writePanePreference(
  id: string,
  preference: PanePreference,
): void {
  if (!PANE_ID.test(id)) return;
  const panes: Record<string, PanePreference> = {};
  for (const [kept, value] of Object.entries(readPanes())) {
    if (PANE_ID.test(kept) && kept !== id)
      panes[kept] = panePreferenceOf(value);
  }
  panes[id] = panePreferenceOf(preference);
  const names = Object.keys(panes);
  for (const dropped of names.slice(0, Math.max(0, names.length - PANES_MAX)))
    delete panes[dropped];
  try {
    localStorage.setItem(STORE, JSON.stringify({ version: VERSION, panes }));
  } catch {
    // Not kept: the pane opens at its defaults next time.
  }
}

export type PanePreferenceControl = {
  preference: PanePreference;
  setOpen(open: boolean): void;
  /** A size in CSS pixels for a placement, or null for the default. */
  setSize(placement: PanePlacement, size: number | null): void;
};

/** The preference kept for the pane `id`, and the ways to change it. */
export function usePanePreference(id: string): PanePreferenceControl {
  const [preference, setPreference] = useState(() => readPanePreference(id));
  const changed = useRef(false);
  useEffect(() => {
    // Only a change the person made is written back.
    if (changed.current) writePanePreference(id, preference);
  }, [id, preference]);
  const setOpen = useCallback((open: boolean) => {
    changed.current = true;
    setPreference((held) => ({ ...held, open }));
  }, []);
  const setSize = useCallback(
    (placement: PanePlacement, next: number | null) => {
      changed.current = true;
      setPreference((held) => ({ ...held, [placement]: size(next) }));
    },
    [],
  );
  return { preference, setOpen, setSize };
}
