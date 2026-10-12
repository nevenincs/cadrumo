import { expect, type Page } from "@playwright/test";
import type { PanelTab } from "../../src/shell/layout";
import { label } from "./strings";

export const panelToggle = (page: Page, locale = "en") =>
  page
    .getByRole("navigation", { name: label("desktop.rail.label", {}, locale) })
    .getByRole("button", { name: label("desktop.panel.label", {}, locale) });

export async function openPanelTab(
  page: Page,
  tab: PanelTab,
  { touch = false, locale = "en" } = {},
) {
  const activation = touch ? "tap" : "click";
  const panel = page.locator("section.panel");
  if (await panel.isHidden()) await panelToggle(page, locale)[activation]();
  await expect(panel).toBeVisible();
  const trigger = page.getByRole("tab", {
    name: label(`desktop.rail.${tab}`, {}, locale),
  });
  await trigger[activation]();
}
