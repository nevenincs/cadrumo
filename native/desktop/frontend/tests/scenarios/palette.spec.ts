import { expect, test, type Locator, type Page } from "@playwright/test";
import {
  pageViewId,
  WINDOW_VIEWS,
} from "../../src/shell/navigation/windowViews";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";

// The palette's views come from the navigation register: each is found by
// its label, its keywords and its id, opens through the navigator, and keeps
// the id and chord it had before. A pasted `cadrumo:` link is one entry that
// opens it or says why it cannot, and the current view's link can be copied.

const open = async (target: Page) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(
    target
      .getByRole("navigation", { name: label("desktop.rail.label") })
      .getByRole("button", { name: label("desktop.rail.agent"), exact: true }),
  ).not.toHaveAttribute("aria-disabled", "true");
};

const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

const palette = (target: Page) => target.locator(".palette");
const input = (target: Page) =>
  palette(target).getByRole("combobox", {
    name: label("desktop.palette.label"),
  });
const options = (target: Page) =>
  palette(target).getByRole("listbox").getByRole("option");

/** Opens the palette from anywhere and types `query`. */
async function search(target: Page, query: string) {
  await target.keyboard.press("ControlOrMeta+Shift+KeyK");
  await expect(input(target)).toBeFocused();
  await input(target).fill(query);
}

const optionTitled = (target: Page, text: string): Locator =>
  options(target).filter({
    has: target.locator(".palette-title", {
      hasText: new RegExp(`^${text}$`),
    }),
  });

const ledgerTab = (target: Page, section: string) =>
  target
    .locator(".pane-docs .pane-head")
    .getByRole("tab", { name: label(`desktop.ledger.section.${section}`) });

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("the view shown is the element its page or Ledger section opens", () => {
  for (const [id, entry] of Object.entries(WINDOW_VIEWS)) {
    if (entry.view.kind !== "page") continue;
    const section = entry.view.section;
    // A page that keeps its saved section is shown as that section.
    if (entry.view.page === "ledger" && section === null) continue;
    expect(pageViewId(entry.view.page, section ?? "movements"), id).toBe(id);
  }
  expect(pageViewId("ledger", "rules")).toBe("ledger/rules");
  expect(pageViewId("calendar", "rules")).toBe("calendar");
});

test("a view is found by its label, its keywords and its register id", async ({
  page: target,
}) => {
  await open(target);
  const invoices = label("navigation.view.ledger.invoices.label");
  for (const query of [invoices, "facturas", "ledger/invoices", "invoices"]) {
    await search(target, query);
    const option = optionTitled(target, invoices);
    await expect(option, query).toHaveCount(1);
    // A section says which page it belongs to.
    await expect(option.locator(".palette-context")).toHaveText(
      label("navigation.view.ledger.label"),
    );
    await target.keyboard.press("Escape");
    await expect(palette(target)).toHaveCount(0);
  }
  // A section is quiet: unasked, the palette does not list it.
  await target.keyboard.press("ControlOrMeta+Shift+KeyK");
  await expect(options(target).first()).toBeVisible();
  await expect(optionTitled(target, invoices)).toHaveCount(0);
  await expect(
    optionTitled(target, label("navigation.view.ledger.label")),
  ).toHaveCount(1);
});

test("choosing a Ledger section opens that section with the keyboard in it", async ({
  page: target,
}) => {
  await open(target);
  await search(target, "ledger/invoices");
  await expect(options(target).first()).toContainText(
    label("navigation.view.ledger.invoices.label"),
  );
  await target.keyboard.press("Enter");
  await expect(palette(target)).toHaveCount(0);
  await expect(target.locator(".ledger-page")).toBeVisible();
  await expect(ledgerTab(target, "invoices")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    target.locator(".ledger-page:focus, .ledger-page :focus"),
  ).toHaveCount(1);
});

test("a view only the TUI has opens in the workspace, and says so", async ({
  page: target,
}) => {
  await open(target);
  const withholding = label("navigation.view.withholding.label");
  await search(target, withholding);
  const option = optionTitled(target, withholding);
  await expect(option).toHaveCount(1);
  await expect(option).toContainText(label("navigation.view.terminal.label"));
  await target.keyboard.press("Enter");
  await expect
    .poll(() => calls(target))
    .toContain("presentView withholding presented");
  const tui = target.locator('[data-terminal="tui"]');
  await expect(tui).toBeVisible();
  await expect(tui.locator(".xterm-helper-textarea")).toBeFocused();
});

test("the views keep their action ids, and their chords still toggle", async ({
  page: target,
}) => {
  await seedLayout(target, {
    layout: {
      agentShown: true,
      docsShown: true,
      tuiShown: true,
      panelOpen: false,
      page: "docs",
    },
  });
  await open(target);
  await target.keyboard.press("ControlOrMeta+Shift+KeyK");
  for (const id of [
    "agent.toggle",
    "tui.toggle",
    "docs.toggle",
    "panel.toggle",
    "panel.console",
    "panel.python",
    "panel.logs",
    "view.calendar",
    "view.ledger",
    "view.declarations",
    "view.profile",
    "view.copyLink",
  ])
    await expect(
      palette(target).locator(`[data-value="action:${id}"]`),
      id,
    ).toHaveCount(1);
  await target.keyboard.press("Escape");
  await expect(palette(target)).toHaveCount(0);
  for (const [chord, pane] of [
    ["ControlOrMeta+Shift+KeyA", ".pane-agent"],
    ["ControlOrMeta+Shift+KeyT", ".pane-tui"],
    ["ControlOrMeta+Shift+KeyH", ".pane-docs"],
  ] as const) {
    await expect(target.locator(pane), chord).toBeVisible();
    await target.keyboard.press(chord);
    await expect(target.locator(pane), chord).toBeHidden();
    await target.keyboard.press(chord);
    await expect(target.locator(pane), chord).toBeVisible();
  }
  const panel = target.locator(".panel");
  await target.keyboard.press("Control+Backquote");
  await expect(panel).toBeVisible();
  await target.keyboard.press("Control+Backquote");
  await expect(panel).toBeHidden();
  await target.keyboard.press("ControlOrMeta+Shift+Digit3");
  await expect(target.locator(".logview")).toBeVisible();
  await target.keyboard.press("ControlOrMeta+Shift+Digit3");
  await expect(panel).toBeHidden();
});

test("a pasted view link is one entry that opens it", async ({
  page: target,
}) => {
  await open(target);
  await search(target, "cadrumo://view/ledger/invoices");
  await expect(options(target)).toHaveCount(1);
  await expect(options(target)).toHaveText(
    label("desktop.palette.open_link", {
      view: label("navigation.view.ledger.invoices.label"),
    }),
  );
  await target.keyboard.press("Enter");
  await expect(palette(target)).toHaveCount(0);
  await expect(ledgerTab(target, "invoices")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  const made = await calls(target);
  expect(made.some((call) => call.startsWith("openExternal "))).toBe(false);
});

test("a pasted link that opens nothing says why, and choosing it does nothing", async ({
  page: target,
}) => {
  await open(target);
  for (const [link, reason] of [
    ["cadrumo://view/Ledger", "desktop.navigation.refused.uppercase"],
    ["cadrumo://view/ledger#rows", "desktop.navigation.refused.fragment"],
    ["cadrumo://view/no-such-view", "desktop.navigation.refused.unknown_view"],
  ] as const) {
    await search(target, link);
    await expect(options(target), link).toHaveCount(1);
    await expect(options(target), link).toHaveText(label(reason));
    await expect(options(target), link).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    await target.keyboard.press("Enter");
    await expect(palette(target)).toBeVisible();
    await target.keyboard.press("Escape");
    await expect(palette(target)).toHaveCount(0);
  }
});

test("copying the link of the view shown copies the section's link", async ({
  page: target,
}) => {
  await open(target);
  await search(target, "ledger/invoices");
  await target.keyboard.press("Enter");
  await expect(ledgerTab(target, "invoices")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await search(target, label("desktop.palette.copy_link"));
  await expect(options(target).first()).toContainText(
    label("desktop.palette.copy_link"),
  );
  await target.keyboard.press("Enter");
  // The host is told only how much was copied: the section's link, not the
  // Ledger's nor another section's, has exactly this length.
  const link = "cadrumo://view/ledger/invoices";
  await expect
    .poll(() => calls(target))
    .toContain(`writeClipboard ${link.length} characters`);
  await expect(
    target.locator("[data-slot=toast]:not(.ledger-toast)"),
  ).toHaveText(label("desktop.toast.copied"));
});

test("two views of one name are told apart by the page they are on", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(() =>
    window.__scenarioLanguage!.publish({
      language: "es",
      persisted: true,
      profile: "Demo profile",
      revision: 10,
    }),
  );
  await expect(target.locator("html")).toHaveAttribute("lang", "es");
  const name = label("navigation.view.ledger.registers.label", {}, "es");
  expect(name).toBe(label("navigation.view.panel.logs.label", {}, "es"));
  await target.keyboard.press("ControlOrMeta+Shift+KeyK");
  await palette(target)
    .getByRole("combobox", {
      name: label("desktop.palette.label", {}, "es"),
    })
    .fill(name);
  const named = optionTitled(target, name);
  await expect(named).toHaveCount(2);
  await expect(named.locator(".palette-context")).toHaveText([
    label("navigation.view.ledger.label", {}, "es"),
    label("navigation.view.panel.label", {}, "es"),
  ]);
});

test("a pasted link to a movement opens the Ledger on that row", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  const grid = target.locator(".ledger-movements [role=grid]");
  const row = grid
    .locator("[data-kind=data]")
    .filter({
      has: target.locator("[data-column=description]", {
        hasText: "PAPELERIA TRAZO",
      }),
    })
    .first();
  await expect(row).toBeVisible();
  const id = await row.getAttribute("data-key");
  expect(id).toMatch(/^[0-9a-f]{64}$/);
  // Away from the Ledger, so the link opens it again and reveals the row.
  await target
    .locator(".rail")
    .getByRole("button", { name: label("desktop.profile.title"), exact: true })
    .click();
  await search(target, `cadrumo://view/ledger/movements?select=${id}`);
  await expect(options(target)).toHaveCount(1);
  await target.keyboard.press("Enter");
  await expect(palette(target)).toHaveCount(0);
  const shown = grid.locator(`[data-key="${id}"]`);
  await expect(shown).toHaveAttribute("aria-selected", "true");
  await expect(shown.locator(":focus")).toHaveCount(1);
});
