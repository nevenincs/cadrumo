import type { Page } from "@playwright/test";
import type { Layout, Prefs } from "../../src/shell/layout";

/** Raw persisted input also permits obsolete keys to exercise loading old state. */
type Seed = {
  prefs?: Partial<Prefs> & Record<string, unknown>;
  layout?: Partial<Layout>;
};

/** The documentation beside the TUI, documentation first, with no agent
 * column: the window a test of that split is about. */
export const DOCS_BESIDE_TUI: Seed = {
  prefs: { order: "docs" },
  layout: { agentShown: false, docsShown: true },
};

/**
 * Stores a layout before the window first loads, as a person who arranged it
 * would have left it. Registered after a spec's own clearing of storage, it
 * runs after it; a reload inside the test keeps what the test has changed.
 */
export async function seedLayout(target: Page, seed: Seed = DOCS_BESIDE_TUI) {
  await target.addInitScript((stored) => {
    if (sessionStorage.getItem("layout-seeded")) return;
    localStorage.setItem("cadrumo-shell-layout", JSON.stringify(stored));
    sessionStorage.setItem("layout-seeded", "1");
  }, seed);
}
