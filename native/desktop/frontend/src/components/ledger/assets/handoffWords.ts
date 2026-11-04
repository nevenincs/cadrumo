// What a filing handoff leaves out, as the backend says it: each interval
// Modelo 100 leaves out, and each reason a Modelo 130 amount leaves elements
// out, arrive as finished sentences naming the elements by the register's own
// names. The window draws them and decides nothing: a sentence the backend
// could not say whole is not drawn, and an element the list holds no name for
// is counted, never named by its id.

import type { ActivityAssetFilingResult } from "../../../shell/ledgerSetup";

export type Handoff = NonNullable<ActivityAssetFilingResult["filing_handoff"]>;

/** What the handoff leaves out, in the order the backend states it: its
 * Modelo 100 intervals, then the Modelo 130 reasons. */
export function leftOutNotes(handoff: Handoff): string[] {
  return [
    ...handoff.m100_gaps.flatMap((gap) => gap.words ?? []),
    ...handoff.left_out.map((entry) => entry.words),
  ];
}
