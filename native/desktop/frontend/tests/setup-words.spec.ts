import { expect, test } from "@playwright/test";
import { refusalWords } from "../src/components/setup/setupWords";

// What the setup window says of a refused command, read through a translator
// that returns the key it is asked for. No page is opened.

const KEYS = (key: string) => key;

test("each code the setup host refuses a command with has a sentence of its own", () => {
  const codes = [
    "not_signed_in",
    "busy",
    "plan_changed",
    "not_pending",
    "not_cancellable",
    "unavailable",
    "model_selection_unusable",
    "browser_not_removed",
  ];

  const keys = codes.map((code) => refusalWords(KEYS, code));

  expect(new Set(keys).size).toBe(codes.length);
  expect(keys).not.toContain("desktop.setup.refused_other");
});

test("a refused local model selection says what to do about the selection, not that setup was unreachable", () => {
  expect(refusalWords(KEYS, "model_selection_unusable")).toBe(
    "desktop.setup.refused_model_selection_unusable",
  );
});

test("a code the window does not know gets the general sentence", () => {
  expect(refusalWords(KEYS, "a_code_from_a_newer_host")).toBe(
    "desktop.setup.refused_other",
  );
});
