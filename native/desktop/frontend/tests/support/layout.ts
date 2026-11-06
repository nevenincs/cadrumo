import type { Page } from "@playwright/test";
import type { Layout, Prefs } from "../../src/shell/layout";

/** Raw persisted input also permits obsolete keys to exercise loading old state. */
type Seed = {
  prefs?: Partial<Prefs> & Record<string, unknown>;
  layout?: Partial<Layout>;
};

/** The documentation shown, placed before the TUI, with no agent column. It
 * saves nothing about the TUI, which a fresh layout keeps closed, so a test
 * of the two side by side opens the TUI itself (`showTui`). */
export const DOCS_FIRST: Seed = {
  prefs: { order: "docs" },
  layout: { agentShown: false, docsShown: true, page: "docs" },
};

/**
 * Stores a layout before the window first loads, as a person who arranged it
 * would have left it. Registered after a spec's own clearing of storage, it
 * runs after it; a reload inside the test keeps what the test has changed.
 */
export async function seedLayout(target: Page, seed: Seed = DOCS_FIRST) {
  await target.addInitScript((stored) => {
    if (sessionStorage.getItem("layout-seeded")) return;
    localStorage.setItem("cadrumo-shell-layout", JSON.stringify(stored));
    sessionStorage.setItem("layout-seeded", "1");
  }, seed);
}
