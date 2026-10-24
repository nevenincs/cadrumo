import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// A dialog opened by key gives the focus back to the action that opened it.

const head = (target: Page) => target.locator(".pane-docs .pane-head");

for (const [action, title] of [
  ["desktop.ledger.action.import", "desktop.ledger.import.title"],
  ["desktop.ledger.action.export", "desktop.ledger.export.title"],
] as const)
  test(`the ${action.split(".").pop()} dialog gives the focus back to its action on Escape`, async ({
    page: target,
  }) => {
    await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
    await target.locator("[data-rail=ledger]").click();
    await expect(
      target.locator(".ledger-page").getByRole("grid"),
    ).toBeVisible();
    const opener = head(target).getByRole("button", {
      name: label(action),
      exact: true,
    });
    await opener.focus();
    await target.keyboard.press("Enter");
    const dialog = target.getByRole("dialog", { name: label(title) });
    await expect(dialog).toBeVisible();
    await target.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(opener).toBeFocused();
  });
