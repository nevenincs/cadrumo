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

/** `request` asking for its sentences in the language the page shows; as it
 * stands where none is held. */
export function inLanguage<Request extends object>(
  request: Request,
): Request & { output_language?: OutputLanguage } {
  return held === null ? request : { ...request, output_language: held };
}
