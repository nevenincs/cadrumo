import { expect, test } from "@playwright/test";
import {
  INSPECTOR_CHORD,
  REDO_CHORDS,
  REVIEW_CHORD,
  REVIEW_CHORDS,
  UNDO_CHORD,
} from "../src/components/ledger/ledgerChords";
import { exactly, type Modifiers } from "../src/components/ui/dataGridModel";
import {
  chordMatches,
  chordText,
  IS_MAC,
  type ChordKeys,
} from "../src/shared/chords";

// The Ledger's shortcuts as the movements section and the page run them, and
// as the changes tray and the inspector show them. No page is opened.

type Press = {
  code: string;
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
};

const press = (
  code: string,
  key: string,
  held: Partial<Omit<Press, "code" | "key">> = {},
): Press => ({
  code,
  key,
  ctrlKey: false,
  metaKey: false,
  shiftKey: false,
  altKey: false,
  ...held,
});

/** The platform's primary modifier, and the other one of the pair. */
const PRIMARY = IS_MAC ? { metaKey: true } : { ctrlKey: true };
const OTHER = IS_MAC ? { ctrlKey: true } : { metaKey: true };

const any = (chords: readonly ChordKeys[], at: Press) =>
  chords.some((chord) => chordMatches(chord, at));

// Every modifier combination over the keys these chords touch, with what each
// key types on a US layout and on a layout that moves letters (AZERTY gives
// "w" on KeyZ, QWERTZ gives "y" on KeyZ and "z" on KeyY).
const KEYS: [string, string][] = [
  ["KeyZ", "z"],
  ["KeyZ", "Z"],
  ["KeyZ", "w"],
  ["KeyZ", "y"],
  ["KeyY", "y"],
  ["KeyY", "z"],
  ["KeyI", "i"],
  ["KeyI", "ˆ"],
  ["KeyI", "Dead"],
  ["Enter", "Enter"],
  ["NumpadEnter", "Enter"],
  ["KeyX", "x"],
];
const PRESSES: Press[] = KEYS.flatMap(([code, key]) =>
  Array.from({ length: 16 }, (_, bits) =>
    press(code, key, {
      ctrlKey: !!(bits & 1),
      metaKey: !!(bits & 2),
      shiftKey: !!(bits & 4),
      altKey: !!(bits & 8),
    }),
  ),
);

const was = (at: Press, wanted: Modifiers) => exactly(at, wanted);

test("undo runs on the primary modifier with the Z key, on any layout", () => {
  expect(chordMatches(UNDO_CHORD, press("KeyZ", "z", PRIMARY))).toBe(true);
  // AZERTY types "w" on the key; the chord is the physical key.
  expect(chordMatches(UNDO_CHORD, press("KeyZ", "w", PRIMARY))).toBe(true);
  // QWERTZ types "z" on KeyY: that is not undo.
  expect(chordMatches(UNDO_CHORD, press("KeyY", "z", PRIMARY))).toBe(false);
  expect(chordMatches(UNDO_CHORD, press("KeyZ", "z", OTHER))).toBe(false);
  expect(
    chordMatches(
      UNDO_CHORD,
      press("KeyZ", "Z", { ...PRIMARY, shiftKey: true }),
    ),
  ).toBe(false);
  expect(chordText(UNDO_CHORD)).toBe(IS_MAC ? "⌘Z" : "Ctrl+Z");
});

test("redo runs on primary Shift+Z and on primary Y, and never with undo", () => {
  const shiftZ = press("KeyZ", "Z", { ...PRIMARY, shiftKey: true });
  expect(any(REDO_CHORDS, shiftZ)).toBe(true);
  expect(any(REDO_CHORDS, press("KeyY", "y", PRIMARY))).toBe(true);
  expect(
    any(REDO_CHORDS, press("KeyY", "Y", { ...PRIMARY, shiftKey: true })),
  ).toBe(false);
  for (const at of PRESSES)
    expect(chordMatches(UNDO_CHORD, at) && any(REDO_CHORDS, at)).toBe(false);
});

test("review runs on primary+Enter and not on primary+Shift+Enter", () => {
  expect(any(REVIEW_CHORDS, press("Enter", "Enter", PRIMARY))).toBe(true);
  expect(
    any(REVIEW_CHORDS, press("Enter", "Enter", { ...PRIMARY, shiftKey: true })),
  ).toBe(false);
  expect(any(REVIEW_CHORDS, press("Enter", "Enter"))).toBe(false);
  expect(any(REVIEW_CHORDS, press("Enter", "Enter", OTHER))).toBe(false);
  expect(
    any(REVIEW_CHORDS, press("Enter", "Enter", { ...PRIMARY, altKey: true })),
  ).toBe(false);
});

test("review runs on the keypad's Enter too, and is shown as the one Enter", () => {
  expect(any(REVIEW_CHORDS, press("NumpadEnter", "Enter", PRIMARY))).toBe(true);
  expect(
    any(
      REVIEW_CHORDS,
      press("NumpadEnter", "Enter", { ...PRIMARY, shiftKey: true }),
    ),
  ).toBe(false);
  expect(REVIEW_CHORDS[0]).toBe(REVIEW_CHORD);
  for (const chord of REVIEW_CHORDS)
    expect(chordText(chord)).toBe(chordText(REVIEW_CHORD));
  expect(chordText(REVIEW_CHORD)).toBe(IS_MAC ? "⌘Enter" : "Ctrl+Enter");
});

test("the inspector chord is Alt with the I key, whatever the layout types", () => {
  expect(
    chordMatches(INSPECTOR_CHORD, press("KeyI", "i", { altKey: true })),
  ).toBe(true);
  // macOS's Option+I is a dead key: the physical key still runs.
  expect(
    chordMatches(INSPECTOR_CHORD, press("KeyI", "Dead", { altKey: true })),
  ).toBe(true);
  expect(
    chordMatches(
      INSPECTOR_CHORD,
      press("KeyI", "I", { altKey: true, shiftKey: true }),
    ),
  ).toBe(false);
  expect(
    chordMatches(
      INSPECTOR_CHORD,
      press("KeyI", "i", { ...PRIMARY, altKey: true }),
    ),
  ).toBe(false);
  expect(chordText(INSPECTOR_CHORD)).toBe(IS_MAC ? "⌥I" : "Alt+I");
});

// The listeners matched these keys by hand before they read the declared
// chords; every press they took or left alone is taken or left alone now.
test("the declared chords take exactly the presses the listeners took by hand", () => {
  for (const at of PRESSES) {
    const label = JSON.stringify(at);
    expect(chordMatches(UNDO_CHORD, at), label).toBe(
      at.code === "KeyZ" && was(at, { primary: true }),
    );
    expect(any(REDO_CHORDS, at), label).toBe(
      (at.code === "KeyZ" && was(at, { primary: true, shift: true })) ||
        (at.code === "KeyY" && was(at, { primary: true })),
    );
    expect(any(REVIEW_CHORDS, at), label).toBe(
      at.key === "Enter" && was(at, { primary: true }),
    );
    expect(chordMatches(INSPECTOR_CHORD, at), label).toBe(
      at.code === "KeyI" && was(at, { alt: true }),
    );
  }
});
