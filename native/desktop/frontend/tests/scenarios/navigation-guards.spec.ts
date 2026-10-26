import { expect, test, type Locator, type Page } from "@playwright/test";
import { agentTurns, ask, settled } from "../support/agent";
import { label } from "../support/strings";
import { windowToast } from "../support/toast";

// The pages' own guards and focus targets under the window's navigator: a
// profile draft and an unanswered Censo review asked about, a Censo answer
// in flight refused, an open dialog standing every navigation down while a
// pane opens freely, and a link's row revealed in the Ledger's grids, or
// announced when the person's view hides it or it is not there.

const calendar = (page: Page) => page.locator(".calendar-page");
const profilePage = (page: Page) => page.locator(".user-profile-page");
const prompt = (page: Page) => page.locator(".navigation-prompt");

/** The link the agent writes when asked for `link`, held by its place
 * among the replies' links. A dialog covers the reply, so a link under one
 * is dispatched rather than clicked. */
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

async function openProfile(page: Page, scenario = "user-profile") {
  await page.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);
  await page
    .locator(".rail")
    .getByRole("button", { name: label("desktop.profile.title"), exact: true })
    .click();
  await expect(profilePage(page)).toContainText("Soler Vidal");
}

async function draftGivenName(page: Page, value: string) {
  await profilePage(page)
    .getByRole("button", {
      name: label("desktop.profile.edit_field", { field: "Given name" }),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", { name: "Given name", exact: true });
  const field = dialog.getByLabel("Given name", { exact: true });
  await field.fill(value);
  return { dialog, field };
}

test("a profile draft is asked about: stay keeps it, discard goes", async ({
  page,
}) => {
  await openProfile(page);
  const link = await linkTo(page, "cadrumo://view/calendar");
  const { dialog, field } = await draftGivenName(page, "Borrador");
  await link.dispatchEvent("click");
  await expect(prompt(page)).toBeVisible();
  await prompt(page).locator(".navigation-prompt-stay").click();
  await expect(prompt(page)).toHaveCount(0);
  await expect(field).toHaveValue("Borrador");
  await expect(calendar(page)).toHaveCount(0);
  await link.dispatchEvent("click");
  await prompt(page).locator(".navigation-prompt-go").click();
  await expect(calendar(page)).toBeVisible();
  await expect(dialog).toHaveCount(0);
  await expect(profilePage(page)).toHaveCount(0);
});

test("an unchanged profile editor asks nothing, and showing a pane over a draft asks nothing", async ({
  page,
}) => {
  await openProfile(page);
  const pane = await linkTo(page, "cadrumo://view/terminal");
  const away = await linkTo(page, "cadrumo://view/calendar");
  const { field } = await draftGivenName(page, "Borrador");
  await pane.dispatchEvent("click");
  await expect(page.locator('[data-terminal="tui"]')).toBeVisible();
  await expect(prompt(page)).toHaveCount(0);
  await expect(field).toHaveValue("Borrador");
  // Typed back to what is stored, the draft holds nothing to lose.
  await field.fill("Ana");
  await away.dispatchEvent("click");
  await expect(prompt(page)).toHaveCount(0);
  await expect(calendar(page)).toBeVisible();
});

test("an open dialog stands every navigation down and keeps its input", async ({
  page,
}) => {
  await openProfile(page);
  const link = await linkTo(page, "cadrumo://view/calendar");
  const pane = await linkTo(page, "cadrumo://view/terminal");
  await profilePage(page)
    .getByRole("button", {
      name: label("desktop.profile.action.menu"),
      exact: true,
    })
    .click();
  await page
    .getByRole("menuitem", {
      name: label("desktop.profile.password.title"),
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", {
    name: label("desktop.profile.password.title"),
    exact: true,
  });
  const current = dialog.getByLabel(label("desktop.profile.password.current"), {
    exact: true,
  });
  await current.fill("not yet sent");
  for (const each of [link, pane]) {
    await each.dispatchEvent("click");
    await expect(windowToast(page)).toHaveText(
      label("desktop.navigation.modal"),
    );
  }
  await expect(dialog).toBeVisible();
  await expect(current).toHaveValue("not yet sent");
  await expect(calendar(page)).toHaveCount(0);
  await expect(page.locator('[data-terminal="tui"]')).toBeHidden();
});

test("an unanswered Censo review is asked about, and an answer in flight is refused", async ({
  page,
}) => {
  await openProfile(page, "censo-ready");
  const link = await linkTo(page, "cadrumo://view/calendar");
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
  await link.click();
  await expect(prompt(page)).toBeVisible();
  await prompt(page).locator(".navigation-prompt-stay").click();
  await expect(apply).toBeVisible();
  await page.evaluate(() => window.__scenarioCenso!.hold());
  await apply.click();
  await expect
    .poll(() => page.evaluate(() => window.__scenarioCenso!.answers()))
    .toBe(1);
  await link.click();
  await expect(windowToast(page)).toHaveText(label("desktop.navigation.busy"));
  await expect(prompt(page)).toHaveCount(0);
  await expect(profilePage(page)).toBeVisible();
  await page.evaluate(() => window.__scenarioCenso!.release());
  await expect(band).toContainText(label("desktop.profile.censo.done"));
  await link.click();
  await expect(calendar(page)).toBeVisible();
});

test("a palette navigation is not held by the palette's own dialog", async ({
  page,
}) => {
  await openProfile(page);
  await page.keyboard.press("Control+KeyK");
  const palette = page.locator(".palette");
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("navigation.view.calendar.label"));
  await palette.getByRole("listbox").getByRole("option").first().click();
  await expect(calendar(page)).toBeVisible();
  await expect(windowToast(page)).not.toHaveText(
    label("desktop.navigation.modal"),
  );
});

// ---- A link's row in the Ledger -------------------------------------------

const ledgerGrid = (page: Page) =>
  page.locator(".ledger-movements [role=grid]");
const movementRow = (page: Page, text: string) =>
  ledgerGrid(page)
    .locator("[data-kind=data]")
    .filter({
      has: page.locator("[data-column=description]", { hasText: text }),
    })
    .first();
const notice = (page: Page) => page.locator(".ledger-reveal-notice");

async function openLedger(page: Page) {
  await page.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await page.locator("[data-rail=ledger]").click();
  await expect(movementRow(page, "PAPELERIA TRAZO")).toBeVisible();
}

test("a movement link selects its row and gives it the keyboard", async ({
  page,
}) => {
  await openLedger(page);
  const row = movementRow(page, "PAPELERIA TRAZO");
  const id = await row.getAttribute("data-key");
  expect(id).toMatch(/^[0-9a-f]{64}$/);
  // Leave the Ledger, so the link opens it again and reveals the row.
  await page
    .locator(".rail")
    .getByRole("button", { name: label("desktop.profile.title"), exact: true })
    .click();
  await (
    await linkTo(page, `cadrumo://view/ledger/movements?select=${id}`)
  ).click();
  const shown = ledgerGrid(page).locator(`[data-key="${id}"]`);
  await expect(shown).toHaveAttribute("aria-selected", "true");
  await expect(shown.locator(":focus")).toHaveCount(1);
  await expect(notice(page)).toHaveCount(0);
});

test("a movement the search hides is announced, and Show it clears only the search", async ({
  page,
}) => {
  await openLedger(page);
  const id = await movementRow(page, "PAPELERIA TRAZO").getAttribute(
    "data-key",
  );
  const search = page.locator(".ledger-page").getByRole("searchbox", {
    name: label("desktop.ledger.search.label"),
  });
  await search.fill("TAXI");
  await expect(movementRow(page, "PAPELERIA TRAZO")).toHaveCount(0);
  await (
    await linkTo(page, `cadrumo://view/ledger/movements?select=${id}`)
  ).click();
  await expect(notice(page)).toContainText(
    label("desktop.ledger.reveal.movement_hidden"),
  );
  // Nothing of the person's view changed on its own.
  await expect(search).toHaveValue("TAXI");
  await notice(page).locator(".ledger-reveal-show").click();
  await expect(search).toHaveValue("");
  const shown = ledgerGrid(page).locator(`[data-key="${id}"]`);
  await expect(shown).toHaveAttribute("aria-selected", "true");
  await expect(shown.locator(":focus")).toHaveCount(1);
  await expect(notice(page)).toHaveCount(0);
});

test("a movement that is not here keeps the page and says only that", async ({
  page,
}) => {
  await openLedger(page);
  await (
    await linkTo(
      page,
      `cadrumo://view/ledger/movements?select=${"0".repeat(64)}`,
    )
  ).click();
  await expect(notice(page)).toHaveText(
    new RegExp(label("desktop.ledger.reveal.movement_missing")),
  );
  await expect(notice(page).locator(".ledger-reveal-show")).toHaveCount(0);
  await expect(ledgerGrid(page)).toBeVisible();
});

test("an invoice link focuses its row in the catalogue", async ({ page }) => {
  await openLedger(page);
  const tab = (key: string) =>
    page.getByRole("tab", { name: label(`desktop.ledger.section.${key}`) });
  await tab("invoices").click();
  // Every period, so the catalogue shows rows whatever today is.
  await page.locator(".pane-docs .pane-head .ledger-period").click();
  await page.locator(".ledger-period-all").click();
  const grid = page.locator(".ledger-invoices [role=grid]");
  const first = grid.locator("[data-kind=data]").first();
  await expect(first).toBeVisible();
  const id = await first.getAttribute("data-key");
  await tab("movements").click();
  await expect(grid).toHaveCount(0);
  await (
    await linkTo(page, `cadrumo://view/ledger/invoices?select=${id}`)
  ).click();
  await expect(grid.locator(`[data-key="${id}"] :focus`)).toHaveCount(1);
});

test("a movement link into an empty ledger says it is not here, and opens no grid", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=ledger&ledger=empty&latency=0&bar=off",
  );
  await (
    await linkTo(
      page,
      `cadrumo://view/ledger/movements?select=${"a".repeat(64)}`,
    )
  ).click();
  await expect(page.locator(".ledger-empty")).toBeVisible();
  await expect(notice(page)).toContainText(
    label("desktop.ledger.reveal.movement_missing"),
  );
  await expect(notice(page).locator(".ledger-reveal-show")).toHaveCount(0);
  await expect(ledgerGrid(page)).toHaveCount(0);
});
