import type { Page } from "@playwright/test";

/** The window's own toast, not one a page draws: the Ledger page draws its
 * own and so does each of its sections. */
export const windowToast = (page: Page) =>
  page.locator("[data-slot=toast]:not(.ledger-toast):not(.ledger-page-toast)");
