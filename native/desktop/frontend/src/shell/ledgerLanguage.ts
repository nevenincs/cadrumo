// The language the Ledger page shows, held for the reads whose answers carry
// sentences: they are asked in it, so what the backend says arrives in the
// words the window is drawn in. Held only while the page is open; with none
// held a read leaves the language out and the backend answers in its own.

import type { OutputLanguage } from "./ledger";

let held: OutputLanguage | null = null;

/** Holds the language the page shows, or null where the page is closed. */
export function holdLedgerLanguage(language: OutputLanguage | null): void {
  held = language;
}

/** The language the page shows, or null where none is held. */
export const ledgerLanguage = (): OutputLanguage | null => held;
