import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { filing } from "../support/scenarioModeloWrites";
import { openDeclaration, tab } from "../support/scenarioModelo";

// The to-do rail of a declaration the application serves as closed to edits
// (recorded as filed) says so in the closure's words, the same words the
// workspace banner uses. The refusal words the form carried before the filing
// and the generic no-admission words are never what the rail says then.

const CLOSED = () => label("workspace.modelo.filed.read_only");
const GENERIC = () => label("workspace.modelo.editability.no_admission");
const RULES = () => label("workspace.modelo.editor.rules_incomplete");

/** The panel the To do tab controls. */
async function rail(target: Page) {
  const tabs = target.getByRole("tab", {
    name: label("workspace.modelo.todo.title"),
  });
  const id = await tabs.first().getAttribute("aria-controls");
  return target.locator(`[role="tabpanel"][id="${id}"]`);
}

async function recordFiling(target: Page) {
  await target
    .getByRole("button", {
      name: label("workspace.modelo.filing.record_as_filed"),
    })
    .click();
  await target
    .getByRole("dialog")
    .getByRole("button", {
      name: label("application.modelo.lifecycle.file_confirm_accept"),
    })
    .click();
}

test("after recording the filing the to-do rail says the declaration is closed, not the earlier refusal words", async ({
  page: target,
}) => {
  await filing(target, "exported");
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.filing.record_as_filed"),
    }),
  ).toBeEnabled();
  // What the rail said before the filing: its words, which the closure's must
  // replace.
  await tab(target, "desktop.modelo.view.form").click();
  const panel = await rail(target);
  const before = ((await panel.textContent()) ?? "").trim();
  await tab(target, "workspace.modelo.filing.title").click();
  await recordFiling(target);
  await expect(
    target.getByText(label("workspace.modelo.filing.recorded_here")).first(),
  ).toBeVisible({ timeout: 5000 });
  await tab(target, "desktop.modelo.view.form").click();
  const closed = await rail(target);
  await expect(closed).toContainText(CLOSED());
  await expect(closed).not.toContainText(GENERIC());
  await expect(closed).not.toContainText(RULES());
  // Anything the rail said before that the closure does not repeat is gone.
  if (before && !before.includes(CLOSED()))
    await expect(closed).not.toContainText(before);
});

test("a declaration opened already filed has the closure's words in the to-do rail", async ({
  page: target,
}) => {
  await openDeclaration(target, "130", { shape: "filed" });
  const panel = await rail(target);
  await expect(panel).toContainText(CLOSED());
  await expect(panel).not.toContainText(GENERIC());
  await expect(panel).not.toContainText(RULES());
});
