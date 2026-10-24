import { expect, test, type Locator, type Page } from "@playwright/test";
import { agentTurns, ask, settled } from "../support/agent";
import { label } from "../support/strings";

// The window's close raised by the system (its own close, Alt+F4), played on
// the scenario host's window port, which holds a close as the native host
// does: the page is asked once, a second close while it has not answered
// closes, and `keep_open` lets the next close ask again. A close is never
// refused: a dialog does not hold it, staged work and work in flight are
// asked about, and a close over a question already waiting is left
// unanswered so the next close closes.

const port = "&window=port";
const systemClose = (page: Page) =>
  page.evaluate(() => window.__scenarioWindow!.systemClose());
const actions = (page: Page) =>
  page.evaluate(() => window.__scenarioWindow!.actions());
const closed = (page: Page) =>
  page.evaluate(() => window.__scenarioWindow!.closed());
/** The window's answers to closes, without its other actions. */
const answers = async (page: Page) =>
  (await actions(page)).filter(
    (action) => action === "close_now" || action === "keep_open",
  );
const prompt = (page: Page) => page.locator(".navigation-prompt");
const toast = (page: Page) =>
  page.locator("[data-slot=toast]:not(.ledger-toast)");

test("a close over the sign-in dialog closes the window", async ({ page }) => {
  await page.goto(
    `/scenarios.html?scenario=signed-out&latency=0&bar=off${port}`,
  );
  const password = page.getByLabel(label("desktop.signin.password"), {
    exact: true,
  });
  await expect(password).toBeVisible();
  await password.fill("not yet sent");
  await systemClose(page);
  await expect.poll(() => closed(page)).toBe(true);
  expect(await answers(page)).toEqual(["close_now"]);
  await expect(toast(page)).not.toHaveText(label("desktop.navigation.modal"));
});

// ---- A question already waiting -------------------------------------------

async function linkTo(page: Page, link: string): Promise<Locator> {
  const links = agentTurns(page).getByRole("link", {
    name: "el enlace",
    exact: true,
  });
  const before = await links.count();
  await ask(page, `Enlaza ${link}`);
  await settled(page);
  const found = links.nth(before);
  await expect(found).toHaveAttribute("href", link);
  return found;
}

/** The profile page with a drafted given name and the window's own leave
 * question waiting over it. */
async function leavePromptWaiting(page: Page) {
  await page.goto(
    `/scenarios.html?scenario=user-profile&latency=0&bar=off${port}`,
  );
  const profile = page.locator(".user-profile-page");
  await page
    .locator(".rail")
    .getByRole("button", { name: label("desktop.profile.title"), exact: true })
    .click();
  await expect(profile).toContainText("Soler Vidal");
  const link = await linkTo(page, "cadrumo://view/calendar");
  await profile
    .getByRole("button", {
      name: label("desktop.profile.edit_field", { field: "Given name" }),
      exact: true,
    })
    .click();
  await page
    .getByRole("dialog", { name: "Given name", exact: true })
    .getByLabel("Given name", { exact: true })
    .fill("Borrador");
  await link.dispatchEvent("click");
  await expect(prompt(page)).toBeVisible();
}

test("a close over a waiting leave question is left unanswered, and a second close closes", async ({
  page,
}) => {
  await leavePromptWaiting(page);
  await systemClose(page);
  await expect(toast(page)).toHaveText(label("desktop.navigation.pending"));
  expect(await answers(page)).toEqual([]);
  expect(await closed(page)).toBe(false);
  await expect(prompt(page)).toBeVisible();
  await systemClose(page);
  expect(await closed(page)).toBe(true);
});

test("once the waiting question is answered, the next close is asked again", async ({
  page,
}) => {
  await leavePromptWaiting(page);
  await systemClose(page);
  await prompt(page).locator(".navigation-prompt-stay").click();
  await expect(prompt(page)).toHaveCount(0);
  await expect.poll(() => answers(page)).toEqual(["keep_open"]);
  // The draft is still there, so the close asks about it.
  await systemClose(page);
  await expect(prompt(page)).toBeVisible();
  expect(await closed(page)).toBe(false);
  await prompt(page).locator(".navigation-prompt-go").click();
  await expect.poll(() => closed(page)).toBe(true);
  expect(await answers(page)).toEqual(["keep_open", "close_now"]);
});

// ---- Staged ledger work ----------------------------------------------------

const leave = (page: Page) => page.locator(".ledger-leave");

async function stagedLedger(page: Page) {
  await page.goto(`/scenarios.html?scenario=ledger&latency=0&bar=off${port}`);
  await page.locator("[data-rail=ledger]").click();
  const grid = page.locator(".ledger-page").getByRole("grid");
  const row = grid.locator("[data-kind=data]").filter({
    has: page.locator("[data-column=description]", {
      hasText: "PAPELERIA TRAZO",
    }),
  });
  await expect(row.first()).toBeVisible();
  await row.first().locator("[data-column=group_label]").click();
  await page.keyboard.press("Enter");
  const editor = page.locator(".ledger-cell-editor");
  await expect(editor).toBeVisible();
  await editor.fill("Oficina");
  await page.keyboard.press("Enter");
  await expect(page.locator(".ledger-tray")).toBeVisible();
}

test("a close over staged ledger work asks once, and keeping on editing keeps the window", async ({
  page,
}) => {
  await stagedLedger(page);
  await systemClose(page);
  await expect(leave(page)).toHaveCount(1);
  await leave(page)
    .getByRole("button", { name: label("desktop.ledger.leave.cancel") })
    .first()
    .click();
  await expect(leave(page)).toHaveCount(0);
  await expect.poll(() => answers(page)).toEqual(["keep_open"]);
  expect(await closed(page)).toBe(false);
  await expect(page.locator(".ledger-tray")).toBeVisible();
  // Asked again on the next close; discarding closes.
  await systemClose(page);
  await expect(leave(page)).toBeVisible();
  await leave(page).locator(".ledger-leave-discard").click();
  await expect.poll(() => closed(page)).toBe(true);
  expect(await answers(page)).toEqual(["keep_open", "close_now"]);
});

test("a close over the ledger's own leave question is left unanswered, and a second close closes", async ({
  page,
}) => {
  await stagedLedger(page);
  // Signing out asks about the staged work in the ledger's own words.
  await page.keyboard.press("Control+Shift+KeyD");
  await expect(leave(page)).toBeVisible();
  await systemClose(page);
  expect(await answers(page)).toEqual([]);
  expect(await closed(page)).toBe(false);
  await expect(leave(page)).toBeVisible();
  await systemClose(page);
  expect(await closed(page)).toBe(true);
});

// ---- Work in flight --------------------------------------------------------

test("a close while a Censo answer is in flight asks rather than refuses", async ({
  page,
}) => {
  await page.goto(
    `/scenarios.html?scenario=censo-ready&latency=0&bar=off${port}`,
  );
  await page
    .locator(".rail")
    .getByRole("button", { name: label("desktop.profile.title"), exact: true })
    .click();
  const band = page.getByRole("region", {
    name: label("desktop.profile.censo.band"),
    exact: true,
  });
  await band
    .getByRole("button", {
      name: label("desktop.profile.censo.pull"),
      exact: true,
    })
    .click();
  const apply = band.getByRole("button", {
    name: label("desktop.profile.censo.apply"),
    exact: true,
  });
  await expect(apply).toBeVisible();
  await page.evaluate(() => window.__scenarioCenso!.hold());
  await apply.click();
  await expect
    .poll(() => page.evaluate(() => window.__scenarioCenso!.answers()))
    .toBe(1);
  await systemClose(page);
  await expect(prompt(page)).toContainText(
    label("desktop.navigation.close_busy.title"),
  );
  await expect(toast(page)).not.toHaveText(label("desktop.navigation.busy"));
  await prompt(page).locator(".navigation-prompt-stay").click();
  await expect.poll(() => answers(page)).toEqual(["keep_open"]);
  expect(await closed(page)).toBe(false);
  await systemClose(page);
  await prompt(page).locator(".navigation-prompt-go").click();
  await expect.poll(() => closed(page)).toBe(true);
  expect(await answers(page)).toEqual(["keep_open", "close_now"]);
  await page.evaluate(() => window.__scenarioCenso!.release());
});
