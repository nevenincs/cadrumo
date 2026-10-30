// The Ledger page's own key chords, declared once for the control that shows
// a chord and the listener that runs it, so the shown key is the one that
// works. Each listener matches through chordMatches.

import type { ChordKeys } from "@/shared/chords";

/** Undo the last staged change: the movements section runs it, the changes
 * tray shows it. */
export const UNDO_CHORD: ChordKeys = { code: "KeyZ", key: "Z", mod: true };

/** Redo the last undone change, by either chord. */
export const REDO_CHORDS: readonly ChordKeys[] = [
  { code: "KeyZ", key: "Z", mod: true, shift: true },
  { code: "KeyY", key: "Y", mod: true },
];

/** Open the review of what is staged: the movements section runs it, the
 * changes tray shows it. Physical, so Shift is part of the chord. */
export const REVIEW_CHORD: ChordKeys = {
  code: "Enter",
  key: "Enter",
  mod: true,
};

/** The review chord on either Enter key: the numeric keypad's Enter is the
 * same key to the person pressing it. */
export const REVIEW_CHORDS: readonly ChordKeys[] = [
  REVIEW_CHORD,
  { ...REVIEW_CHORD, code: "NumpadEnter" },
];

/** Show, focus or hide the inspector: the Ledger page runs it, the
 * inspector's close button shows it. */
export const INSPECTOR_CHORD: ChordKeys = { code: "KeyI", key: "I", alt: true };
