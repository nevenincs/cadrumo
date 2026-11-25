import { expect, test } from "@playwright/test";
import {
  clipboardChord,
  pasteRange,
} from "../src/components/ui/dataGridClipboard";

const keys = ["a", "b", "c", "d"];

test("a single active cell in a multi-row selection pastes down the selected rows in grid order", () => {
  expect(
    pasteRange(
      { rows: ["c"], columns: ["category"] },
      new Set(["d", "b", "c"]),
      keys,
    ),
  ).toEqual({ rows: ["b", "c", "d"], columns: ["category"] });
});

test("a drawn range, a lone selection, or an active row outside the selection keeps the range", () => {
  const cell = { rows: ["a"], columns: ["category"] };
  const drawn = { rows: ["a", "b"], columns: ["category"] };
  expect(pasteRange(drawn, new Set(["a", "b", "c"]), keys)).toBe(drawn);
  expect(pasteRange(cell, new Set(["a"]), keys)).toBe(cell);
  expect(pasteRange(cell, new Set(["b", "c"]), keys)).toBe(cell);
  expect(pasteRange(cell, undefined, keys)).toBe(cell);
});

test("only the primary modifier with C, X or V is a clipboard chord", () => {
  expect(clipboardChord({ code: "KeyC" }, true)).toBe("copy");
  expect(clipboardChord({ code: "KeyX" }, true)).toBe("cut");
  expect(clipboardChord({ code: "KeyV" }, true)).toBe("paste");
  expect(clipboardChord({ code: "KeyV" }, false)).toBeNull();
  expect(clipboardChord({ code: "KeyD" }, true)).toBeNull();
});
