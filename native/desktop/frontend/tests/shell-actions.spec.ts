import { expect, test } from "@playwright/test";
import { chordModifiers } from "../src/shared/chords";
import {
  findAction,
  findButtonAction,
  type Action,
  type Chord,
  type FocusArea,
} from "../src/shell/actions";

// findAction reads only the key, the modifiers and `isComposing`; the specs
// run in Node, which has no KeyboardEvent, so a press is those fields alone.
type Press = Pick<
  KeyboardEvent,
  "code" | "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey" | "isComposing"
>;
const press = (init: Partial<Press>): KeyboardEvent =>
  ({
    code: "",
    key: "",
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    altKey: false,
    isComposing: false,
    ...init,
  }) as KeyboardEvent;
// The chords below use `mod`, the platform's primary modifier, so a press
// carries the modifier that chord resolves to on the platform running this.
const primary = (init: Partial<Press>): KeyboardEvent =>
  press({ ...chordModifiers({ code: "", key: "", mod: true }), ...init });

const action = (id: string, chords: Chord[], buttons?: number[]): Action => ({
  id,
  label: id,
  group: "general",
  icon: "search",
  chords,
  buttons,
  run: () => undefined,
});

const palette = action("palette.open", [
  { mod: true, code: "KeyK", key: "K", scope: "browser" },
  { mod: true, shift: true, code: "KeyK", key: "K", scope: "global" },
]);
const back = action(
  "window.back",
  [{ alt: true, code: "ArrowLeft", key: "←", scope: "app" }],
  [3],
);
const terminalCopy = action("terminal.copy", [
  { mod: true, shift: true, code: "KeyC", key: "C", scope: "terminal" },
]);
const actions = [palette, back, terminalCopy];

const found = (event: KeyboardEvent, area: FocusArea) =>
  findAction(actions, event, area)?.id ?? null;

test("a browser chord fires in the chrome, the docs frame and the browser, never in a terminal", () => {
  const ctrlK = () => primary({ code: "KeyK", key: "k" });
  expect(found(ctrlK(), "chrome")).toBe("palette.open");
  expect(found(ctrlK(), "docs")).toBe("palette.open");
  expect(found(ctrlK(), "browser")).toBe("palette.open");
  expect(found(ctrlK(), "terminal")).toBeNull();
});

test("the global palette chord fires in every area", () => {
  for (const area of ["chrome", "docs", "browser", "terminal"] as const)
    expect(
      found(primary({ code: "KeyK", key: "K", shiftKey: true }), area),
    ).toBe("palette.open");
});

test("an app chord is not found over the browser, as before", () => {
  const altLeft = () =>
    press({ code: "ArrowLeft", key: "ArrowLeft", altKey: true });
  expect(found(altLeft(), "chrome")).toBe("window.back");
  expect(found(altLeft(), "browser")).toBeNull();
  expect(found(altLeft(), "terminal")).toBeNull();
});

test("the pointer's back button runs over the chrome and not over the browser", () => {
  expect(findButtonAction(actions, 3, "chrome")?.id).toBe("window.back");
  expect(findButtonAction(actions, 3, "browser")).toBeNull();
  expect(findButtonAction(actions, 3, "terminal")).toBeNull();
});

test("copy, cut, paste and plain keys are not shell actions over the browser", () => {
  for (const key of ["c", "x", "v"])
    expect(
      found(primary({ code: `Key${key.toUpperCase()}`, key }), "browser"),
    ).toBeNull();
  expect(found(press({ code: "KeyA", key: "a" }), "browser")).toBeNull();
  expect(
    found(primary({ code: "KeyC", key: "C", shiftKey: true }), "browser"),
  ).toBeNull();
});
