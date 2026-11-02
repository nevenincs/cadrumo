// The limits a ledger entry form holds typed text to, as the backend serves them
// with `ledger.entry-options`. This is the one place the window holds them, and
// only while the Ledger page is open: there is no copy to fall back on, so with
// nothing served a draft stays as typed and is not taken.

import { useSyncExternalStore } from "react";
import type { LedgerEntryLimits } from "./ledgerSetup";

let held: LedgerEntryLimits | null = null;
const listeners = new Set<() => void>();

/** Holds what the backend served, or null where it has served nothing. */
export function holdLedgerLimits(limits: LedgerEntryLimits | null): void {
  if (held === limits) return;
  held = limits;
  for (const listener of listeners) listener();
}

/** The limits served, or null where none are. */
export const ledgerLimits = (): LedgerEntryLimits | null => held;

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The limits served, drawing again when they arrive or go. */
export const useLedgerLimits = (): LedgerEntryLimits | null =>
  useSyncExternalStore(subscribe, ledgerLimits);
