import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The window's back and forward: Alt+Left and Alt+Right, and a pointer's
// back and forward buttons, step through where the viewer has been in this
// window: from page to page, into a declaration and out to its list, and
// between a declaration's views. A step that would drop staged edits asks
// first, as the header's back link does; a dialog's own buttons are its own.

const workspace = (target: Page) => target.locator(".declarations-workspace");
const heading = (target: Page) =>
  workspace(target).getByRole("heading", { level: 1 });
const list = (target: Page) =>
  target.locator(".declarations-page").getByRole("grid");
const views = (target: Page) =>
  workspace(target).getByRole("tablist", {
    name: label("desktop.modelo.views.label"),
  });

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() =>
    localStorage.removeItem("cadrumo-shell-layout"),
  );
});

/** The ledger, then the declarations, then one declaration. */
async function walkIn(target: Page) {
  await target.goto(`/scenarios.html?scenario=ledger&latency=0&bar=off`);
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-page")).toBeVisible();
  await target.locator("[data-rail=declarations]").click();
  await list(target)
    .locator("[data-kind=data]")
    .filter({ hasText: "Modelo 130" })
    .first()
    .dblclick();
  await expect(heading(target)).toBeVisible();
}

test("Alt+Left steps back out of a declaration and across pages, Alt+Right steps forward", async ({
  page: target,
}) => {
  await walkIn(target);
  await target.keyboard.press("Alt+ArrowLeft");
  await expect(workspace(target)).toHaveCount(0);
  await expect(list(target)).toBeVisible();
  await target.keyboard.press("Alt+ArrowLeft");
  await expect(target.locator(".ledger-page")).toBeVisible();
  await expect(target.locator(".declarations-page")).toHaveCount(0);
  // Off a grid cell the Ledger passes Alt+Right to the window as well.
  await expect
    .poll(() =>
      target.evaluate(
        () =>
          document.activeElement?.closest(".ledger-page") !== null &&
          document.activeElement !== null,
      ),
    )
    .toBe(true);
  await target.keyboard.press("Alt+ArrowRight");
  await expect(list(target)).toBeVisible();
  await target.locator(".declarations-page").focus();
  await target.keyboard.press("Alt+ArrowRight");
  await expect(heading(target)).toBeVisible();
});

test("back and forward step between a declaration's views", async ({
  page: target,
}) => {
  await walkIn(target);
  const tabs = views(target).getByRole("tab");
  await expect(tabs.first()).toHaveAttribute("aria-selected", "true");
  await tabs.nth(1).click();
  await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
  await target.keyboard.press("Alt+ArrowLeft");
  await expect(tabs.first()).toHaveAttribute("aria-selected", "true");
  await expect(heading(target)).toBeVisible();
  await target.keyboard.press("Alt+ArrowRight");
  await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
});

test("a pointer's back and forward buttons step as the chords do", async ({
  page: target,
}) => {
  await walkIn(target);
  await heading(target).dispatchEvent("mouseup", { button: 3 });
  await expect(workspace(target)).toHaveCount(0);
  await expect(list(target)).toBeVisible();
  await list(target).dispatchEvent("mouseup", { button: 4 });
  await expect(heading(target)).toBeVisible();
  // The other buttons are not a step.
  await heading(target).dispatchEvent("mouseup", { button: 1 });
  await expect(heading(target)).toBeVisible();
});

test("a back step over staged edits asks first, as the header's back link does", async ({
  page: target,
}) => {
  await walkIn(target);
  const row = target
    .getByRole("tabpanel")
    .filter({ has: target.getByRole("row") })
    .first()
    .getByRole("row")
    .filter({ has: target.getByRole("gridcell", { name: "06", exact: true }) });
  await row.getByRole("gridcell").nth(2).getByRole("button").click();
  const entry = target.getByRole("textbox", {
    name: label("workspace.modelo.editor.new_value_for_box", { box: "06" }),
  });
  await entry.fill("1,234.56");
  await entry.press("Enter");
  await expect(row).toContainText(label("workspace.modelo.attention.staged"));
  await target.keyboard.press("Alt+ArrowLeft");
  const leaving = target.getByRole("dialog", {
    name: label("desktop.ledger.leave.title"),
  });
  await expect(leaving).toBeVisible();
  // A pointer's back button pressed on the question is the question's own.
  await leaving.dispatchEvent("mouseup", { button: 3 });
  await expect(leaving).toBeVisible();
  await leaving
    .getByRole("button", {
      name: label("desktop.ledger.leave.cancel"),
      exact: true,
    })
    .last()
    .click();
  await expect(heading(target)).toBeVisible();
  await expect(row).toContainText(label("workspace.modelo.attention.staged"));
  await target.keyboard.press("Alt+ArrowLeft");
  await leaving
    .getByRole("button", {
      name: label("workspace.modelo.leave.discard"),
      exact: true,
    })
    .click();
  await expect(workspace(target)).toHaveCount(0);
  await expect(list(target)).toBeVisible();
});
