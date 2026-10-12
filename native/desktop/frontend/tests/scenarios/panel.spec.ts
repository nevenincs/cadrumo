import { expect, test } from "@playwright/test";
import { openPanelTab, panelToggle } from "../support/panel";
import { label } from "../support/strings";

test("one panel toggle retains the log error and message counts while collapsed", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  const rail = page.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  const toggle = panelToggle(page);
  await expect(toggle).toHaveCount(1);
  for (const tab of ["console", "python", "logs"])
    await expect(
      rail.getByRole("button", { name: label(`desktop.rail.${tab}`) }),
    ).toHaveCount(0);
  await expect(page.locator("section.panel")).toBeHidden();
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await expect(toggle.locator("[data-slot=badge]")).toHaveText("2");
  await expect(toggle).toHaveAccessibleName(
    `${label("desktop.panel.label")}, ${label("desktop.logs.errors", { count: 2 })}`,
  );
  const messages = rail.getByRole("button", {
    name: label("desktop.rail.messages"),
  });
  await expect(messages.locator("[data-slot=badge]")).toHaveText("3");
  await openPanelTab(page, "logs");
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  await expect(toggle.locator("[data-slot=badge]")).toHaveText("2");
  await toggle.click();
  await expect(page.locator("section.panel")).toBeHidden();
  await expect(toggle.locator("[data-slot=badge]")).toHaveText("2");
  await toggle.click();
  await expect(
    page.getByRole("tab", { name: label("desktop.rail.logs") }),
  ).toHaveAttribute("aria-selected", "true");
});
