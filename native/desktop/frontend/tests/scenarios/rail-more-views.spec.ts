import { expect, test } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { moreViewsButton } from "../support/railViews";
import { open, startFromDocs } from "../support/scenarioShell";
import { label } from "../support/strings";

// The views a person opens less often share one rail button, whose menu
// names each. The button says when its menu is open; putting the menu away
// gives focus back to it, and choosing a view leaves focus on that view.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

const VIEWS = [
  "desktop.withholding.title",
  "desktop.reference.title",
  "desktop.operations.title",
];

test("the rail's more views button names each view and says when its menu is open", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  const button = moreViewsButton(target);
  await expect(button).toHaveAccessibleName(label("desktop.rail.more_views"));
  await expect(button).toHaveAttribute("aria-haspopup", "menu");
  await expect(button).toHaveAttribute("aria-expanded", "false");
  await button.click();
  await expect(button).toHaveAttribute("aria-expanded", "true");
  await expect(target.getByRole("menuitem")).toHaveText(
    VIEWS.map((key) => label(key)),
  );
  await target.keyboard.press("Escape");
  await expect(target.getByRole("menu")).toBeHidden();
  await expect(button).toHaveAttribute("aria-expanded", "false");
  await expect(button).toBeFocused();
});

test("a view chosen from the menu opens with focus on it", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await moreViewsButton(target).click();
  await target
    .getByRole("menuitem", { name: label("desktop.reference.title") })
    .click();
  await expect(target.locator(".reference-page")).toBeFocused();
  await expect(moreViewsButton(target)).toHaveAttribute("aria-pressed", "true");
  await expect(moreViewsButton(target)).toHaveAttribute(
    "aria-expanded",
    "false",
  );
});
