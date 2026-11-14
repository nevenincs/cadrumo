import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// Moving between the declarations list and one declaration, and between the
// declaration's views, keeps the keyboard where the person can go on: back
// from a declaration lands on the row it was opened from, and a next action
// that opens another view puts the keyboard in that view rather than on the
// document.

const workspace = (target: Page) => target.locator(".declarations-workspace");
const rows = (target: Page) =>
  target
    .locator(".declarations-page")
    .getByRole("grid")
    .locator("[data-kind=data]");

async function openDeclaration(target: Page, shape = "") {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off${shape ? `&modelo=${shape}` : ""}`,
  );
  await target.locator("[data-rail=declarations]").click();
  await rows(target).filter({ hasText: "Modelo 130" }).first().dblclick();
  await expect(
    workspace(target).getByRole("heading", { level: 1 }),
  ).toBeVisible();
}

/** The text of the list row the keyboard is in, or null outside a row. */
const focusedRow = (target: Page) =>
  target.evaluate(
    () =>
      document.activeElement?.closest("[data-kind=data]")?.textContent ?? null,
  );

test("back from a declaration puts the keyboard on the row it was opened from", async ({
  page: target,
}) => {
  await openDeclaration(target);
  await workspace(target)
    .locator("header")
    .first()
    .getByRole("button", {
      name: label("workspace.declarations.destination.overview"),
    })
    .click();
  await expect(rows(target).first()).toBeVisible();
  await expect.poll(() => focusedRow(target)).toContain("Modelo 130");
});

test("a next action that opens the check puts the keyboard in it", async ({
  page: target,
}) => {
  // Checked again after its box 06 was typed over the ledger's figure: what
  // blocks filing is that divergence, and resolving it is the next action.
  await openDeclaration(target, "stale");
  await workspace(target)
    .getByRole("button", {
      name: label("workspace.modelo.next_button.resolve"),
    })
    .click();
  await expect(
    workspace(target).getByRole("tab", {
      name: new RegExp(`^${label("workspace.modelo.step.review")}`),
    }),
  ).toHaveAttribute("aria-selected", "true");
  await expect
    .poll(() =>
      target.evaluate(
        () =>
          (document.activeElement?.closest("[role=tabpanel]") ?? null) !== null,
      ),
    )
    .toBe(true);
});
