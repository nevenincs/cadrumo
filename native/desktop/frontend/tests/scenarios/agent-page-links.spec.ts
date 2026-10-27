import { expect, test, type Locator, type Page } from "@playwright/test";
import {
  agentColumn,
  agentTurns,
  ask,
  personTurns,
  settled,
} from "../support/agent";
import { showLedgerColumn } from "../support/ledgerPage";
import { label } from "../support/strings";
import { windowToast } from "../support/toast";

// `cadrumo://view/{id}` links in an agent's reply, opened by the window's
// navigator: in the window, in the TUI, with a notice when they open other
// than asked, refused with a toast when nothing opens them, and asked about
// when they would take down work staged on the page shown.

const calls = (page: Page) =>
  page.evaluate(() => window.__scenarioHostCalls ?? []);
const link = (page: Page, name: string) =>
  agentTurns(page).getByRole("link", { name, exact: true });

async function linksReply(page: Page, scenario: string) {
  await page.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);
  await ask(page, "Respóndeme con enlaces");
  await settled(page);
}

async function noLinkLeftTheWindow(page: Page) {
  const made = await calls(page);
  expect(made.some((call) => call.startsWith("openExternal cadrumo:"))).toBe(
    false,
  );
}

test("a setup link opens the AEAT access editor in the window, asks the TUI for nothing and offers a fresh check", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=aeat-setup&latency=0&bar=off");
  await ask(page, "Respóndeme con formato");
  await settled(page);
  const terminals = async () =>
    (await calls(page)).filter((call) => call.startsWith("openTerminal tui "))
      .length;
  const before = await terminals();
  await link(page, "Set up AEAT access").click();
  // The profile page, with its editor over it: opened as asked, so no notice.
  const editor = page.getByRole("dialog", {
    name: label("desktop.profile.action.aeat_access"),
    exact: true,
  });
  await expect(editor).toBeVisible();
  await expect(page.locator(".user-profile-page")).toBeVisible();
  await expect(windowToast(page)).toHaveText("");
  await page.keyboard.press("Escape");
  await expect(editor).toHaveCount(0);
  await agentColumn(page)
    .getByRole("button", { name: label("desktop.agent.aeat_setup_check") })
    .click();
  await expect(personTurns(page).last()).toContainText(
    label("desktop.agent.aeat_setup_resume_message"),
  );
  const made = await calls(page);
  expect(made.some((call) => call.startsWith("presentView "))).toBe(false);
  expect(await terminals()).toBe(before);
  await noLinkLeftTheWindow(page);
});

test("a window link opens its page and gives it the keyboard", async ({
  page,
}) => {
  await linksReply(page, "signed-in");
  await link(page, "el calendario").click();
  const calendar = page.locator(".calendar-page");
  await expect(calendar).toBeVisible();
  await expect(calendar).toBeFocused();
  // A view that opened as asked says nothing.
  await expect(windowToast(page)).toHaveText("");
  const made = await calls(page);
  expect(made.some((call) => call.startsWith("presentView "))).toBe(false);
  await noLinkLeftTheWindow(page);
});

test("a TUI view shows the TUI with the keyboard and asks the host for it", async ({
  page,
}) => {
  await linksReply(page, "signed-in");
  await link(page, "la sincronización con la AEAT").click();
  await expect
    .poll(() => calls(page))
    .toContain("presentView aeat-sync presented");
  const tui = page.locator('[data-terminal="tui"]');
  await expect(tui).toBeVisible();
  await expect(tui.locator(".xterm-helper-textarea")).toBeFocused();
  await noLinkLeftTheWindow(page);
});

test("a window view asked of the TUI opens in the window and says so", async ({
  page,
}) => {
  await linksReply(page, "signed-in");
  await link(page, "los registros, en el espacio de trabajo").click();
  await expect(page.locator(".logview")).toBeVisible();
  await expect(windowToast(page)).toHaveText(
    label("desktop.navigation.notice.in_window", {
      view: label("navigation.view.panel.logs.label"),
    }),
  );
  const made = await calls(page);
  expect(made.some((call) => call.startsWith("presentView "))).toBe(false);
});

test("an unknown view and a link in the retired profile form say why and open nothing", async ({
  page,
}) => {
  await linksReply(page, "signed-in");
  await link(page, "una vista que no existe").click();
  await expect(windowToast(page)).toHaveText(
    label("desktop.navigation.refused.unknown_view"),
  );
  await link(page, "un enlace antiguo").click();
  await expect(windowToast(page)).toHaveText(
    label("desktop.navigation.refused.link"),
  );
  const made = await calls(page);
  expect(made.some((call) => call.startsWith("presentView "))).toBe(false);
  await noLinkLeftTheWindow(page);
});

// The Ledger page's staged work, as its own scenarios stage it.
const ledger = (page: Page) => page.locator(".ledger-page");
const rowOf = (page: Page, text: string) =>
  ledger(page)
    .getByRole("grid")
    .locator("[data-kind=data]")
    .filter({
      has: page.locator("[data-column=description]", { hasText: text }),
    });
const cellOf = (row: Locator, column: string) =>
  row.locator(`[data-column=${column}]`);
const trayCount = async (page: Page) =>
  Number(
    await page
      .locator(".ledger-tray .ledger-tray-toggle span[aria-hidden=true]")
      .textContent(),
  );

async function stageOnLedger(page: Page) {
  await page.locator("[data-rail=ledger]").click();
  // The starting preset gives up Group where the page lacks room for it.
  await showLedgerColumn(page, "group_label");
  const cell = cellOf(rowOf(page, "PAPELERIA TRAZO"), "group_label");
  await expect(cell).toBeVisible();
  await cell.click();
  await page.keyboard.press("Enter");
  await page.locator(".ledger-cell-editor").fill("Oficina");
  await page.keyboard.press("Enter");
  expect(await trayCount(page)).toBe(1);
}

test("a link that would take down staged work asks first, keeps it on stay, and holds a second link", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await stageOnLedger(page);
  await ask(page, "Respóndeme con enlaces");
  await settled(page);
  await link(page, "el calendario").click();
  const leave = page.locator(".ledger-leave");
  await expect(leave).toBeVisible();
  // One navigation waits for an answer at a time: another is held with a
  // toast. The dialog covers the reply, so the second link is dispatched.
  await link(page, "los movimientos").dispatchEvent("click");
  await expect(windowToast(page)).toHaveText(
    label("desktop.navigation.pending"),
  );
  await leave
    .getByRole("button", { name: label("desktop.ledger.leave.cancel") })
    .first()
    .click();
  await expect(leave).toHaveCount(0);
  await expect(ledger(page)).toBeVisible();
  await expect(page.locator(".calendar-page")).toHaveCount(0);
  expect(await trayCount(page)).toBe(1);
});

test("a link that only shows a pane asks nothing and keeps the page", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await stageOnLedger(page);
  await ask(page, "Respóndeme con enlaces");
  await settled(page);
  await link(page, "el espacio de trabajo").click();
  await expect(page.locator('[data-terminal="tui"]')).toBeVisible();
  await expect(page.locator(".ledger-leave")).toHaveCount(0);
  await expect(ledger(page)).toBeVisible();
  expect(await trayCount(page)).toBe(1);
});
