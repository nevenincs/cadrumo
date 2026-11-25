// The limits a ledger entry form holds typed text to, as the backend serves them
// with `ledger.entry-options`. This is the one place the window holds them, and
// only while the Ledger page is open: there is no copy to fall back on, so with
// nothing served a draft stays as typed and is not taken.
//
// The years a typed year takes are served with the same answer. The periods
// reader asks for that answer wherever a period is read, so the years it
// served are held here too, for a year typed outside the Ledger page.

import { useSyncExternalStore } from "react";
import type { LedgerEntryYearWindow } from "./ledgerEntryContract";
import type {
  LedgerEntryLimitsProjection,
  TextLimitName,
} from "./ledgerEntryContract";

let held: LedgerEntryLimitsProjection | null = null;
// The years the periods reader was served, held while it is registered.
let servedYears: LedgerEntryYearWindow | null = null;
const listeners = new Set<() => void>();

/** Holds what the backend served, or null where it has served nothing. */
export function holdLedgerLimits(
  limits: LedgerEntryLimitsProjection | null,
): void {
  if (held === limits) return;
  held = limits;
  for (const listener of listeners) listener();
}

/** Holds the years the periods reader was served, or null to drop them. */
export function holdEntryYears(years: LedgerEntryYearWindow | null): void {
  if (servedYears === years) return;
  servedYears = years;
  for (const listener of listeners) listener();
}

/** The years a typed ledger year takes, as served, or null where none are:
 * no year is checked against a window of the window's own. */
export const entryYears = (): LedgerEntryYearWindow | null =>
  held?.entry_years ?? servedYears;

/** The years served, drawing again when they arrive or go. */
export const useHeldEntryYears = (): LedgerEntryYearWindow | null =>
  useSyncExternalStore(subscribe, entryYears);

/** The limits served, or null where none are. */
export const ledgerLimits = (): LedgerEntryLimitsProjection | null => held;

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The limits served, drawing again when they arrive or go. */
export const useLedgerLimits = (): LedgerEntryLimitsProjection | null =>
  useSyncExternalStore(subscribe, ledgerLimits);

/** A served text limit, or null where it is not served: the Ledger page is
 * closed, or the backend has not answered. Nothing stands in for it. */
export const textLimit = (name: TextLimitName): number | null =>
  held?.text_limits.find((found) => found.name === name)?.max ?? null;

/** A served text limit, drawing again when it arrives or goes. */
export const useTextLimit = (name: TextLimitName): number | null => {
  useLedgerLimits();
  return textLimit(name);
};
