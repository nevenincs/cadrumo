import { expect, test } from "@playwright/test";
import { chordAria, IS_MAC, type ChordKeys } from "../src/shared/chords";

// The ARIA notation names the platform's primary modifier in full, so the
// expected text follows the platform the test runs on.
const PRIMARY = IS_MAC ? "Meta" : "Control";

test("a primary-modifier letter chord names the platform modifier and an upper-case key", () => {
  const undo: ChordKeys = { code: "KeyZ", key: "z", mod: true };
  expect(chordAria(undo)).toBe(`${PRIMARY}+Z`);
});

test("a named key keeps its name", () => {
  const review: ChordKeys = { code: "Enter", key: "Enter", mod: true };
  expect(chordAria(review)).toBe(`${PRIMARY}+Enter`);
});

test("alt and shift are listed ahead of the primary modifier", () => {
  const chord: ChordKeys = { code: "KeyI", key: "I", alt: true, shift: true };
  expect(chordAria(chord)).toBe("Alt+Shift+I");
  const all: ChordKeys = { code: "KeyK", key: "K", mod: true, alt: true };
  expect(chordAria(all)).toBe(IS_MAC ? "Alt+Meta+K" : "Control+Alt+K");
});

test("the literal Control key stays Control on every platform", () => {
  const chord: ChordKeys = { code: "KeyB", key: "B", ctrl: true };
  expect(chordAria(chord)).toBe("Control+B");
});
