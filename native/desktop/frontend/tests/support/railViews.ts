import type { Page } from "@playwright/test";
import { label } from "./strings";

/** The rail button whose menu opens the views a person opens less often. */
export const moreViewsButton = (target: Page) =>
  target.locator('[data-rail="views"]');

/** Opens one of those views from the rail: its button, then its menu item. */
export async function openRailView(
  target: Page,
  titleKey: string,
  language?: string,
) {
  await moreViewsButton(target).click();
  await target
    .getByRole("menuitem", { name: label(titleKey, {}, language) })
    .click();
}
