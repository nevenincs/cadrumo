import { expect, type Locator, type Page } from "@playwright/test";
import { label } from "./strings";
import {
  boxRow,
  envelope,
  type Language,
  openDeclaration,
  tab,
} from "./scenarioModelo";

/** The scenario host's call lines that are `line`, or `line` and what it
 * names after it, such as a file's kind. */
export const calls = async (target: Page, line: string) =>
  (await target.evaluate(() => window.__scenarioHostCalls ?? [])).filter(
    (call) => call === line || call.startsWith(`${line} `),
  );

/** Types `text` over a box, as the filer does, and waits until it is staged. */
export async function stage(target: Page, box: string, text: string) {
  await boxRow(target, box)
    .getByRole("gridcell")
    .nth(2)
    .getByRole("button")
    .click();
  const entry = target.getByRole("textbox", {
    name: label("workspace.modelo.editor.new_value_for_box", { box }),
  });
  await entry.fill(text);
  await entry.press("Enter");
  await expect(boxRow(target, box)).toContainText(
    label("workspace.modelo.attention.staged"),
  );
}

/** Opens the review of what is staged, and waits until the check answers. */
export async function review(target: Page, count = 1) {
  await target
    .getByRole("button", { name: label("workspace.modelo.next_button.apply") })
    .first()
    .click();
  await expect(
    target.getByRole("dialog", {
      name: label("workspace.modelo.review.title", { count }),
    }),
  ).toBeVisible();
  // Its title counts what is staged, which an apply clears.
  const dialog = target.getByRole("dialog");
  await expect(
    dialog.getByText(label("workspace.modelo.review.checking")),
  ).toHaveCount(0);
  return dialog;
}

export const applyButton = (dialog: Locator) =>
  dialog.getByRole("button", { name: label("workspace.modelo.review.apply") });

/** The value the producer's edits stage on box 06, as the filer types it. */
export const TYPED_06 = "1,234.56";

/** Opens the Export and record view of the 130 in `shape`. */
export async function filing(target: Page, shape: string) {
  await openDeclaration(target, "130", { shape });
  await tab(target, "workspace.modelo.filing.title").click();
}

/** The error detail the backend recorded for a scenario refusal, with the
 * sentence it served for it. */
export const refusal = (name: string, language: Language = "en") =>
  envelope<{ error_code: string; refusal_words: string | null }>(
    `refusal-${name}-${language}`,
  );

/** The host calls of a review's recovery: checks, renewals and reads. */
export const recovery = async (target: Page) =>
  (await target.evaluate(() => window.__scenarioHostCalls ?? [])).filter(
    (call) =>
      call === "modelo edit modelo.edit.preflight" ||
      call === "modelo submit modelo.edit.renew" ||
      call.startsWith("modelo form "),
  );
