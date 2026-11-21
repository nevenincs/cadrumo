import { expect, test, type Page } from "@playwright/test";
import { moreViewsButton, openRailView } from "../support/railViews";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";
import { agentTurns, ask, settled } from "../support/agent";
import { windowToast } from "../support/toast";
import { open, startFromDocs } from "../support/scenarioShell";
import {
  CITATION_QUERY,
  NO_MATCH_QUERY,
} from "../../src/dev/fixtures/reference";

// Reference is a page of the first pane that searches the sources bundled
// with the product when the person asks, and draws what the read served and
// nothing else. Each standing the search can be in is kept apart.

test.beforeEach(async ({ page: target }) => {
  await startFromDocs(target);
});

const railButton = moreViewsButton;
const referencePage = (target: Page) => target.locator(".reference-page");
const field = (target: Page) =>
  referencePage(target).getByRole("searchbox", {
    name: label("desktop.reference.query_label"),
  });
const searchButton = (target: Page) =>
  referencePage(target).locator(".reference-search");
const searches = (target: Page) =>
  target.evaluate(
    () =>
      (window.__scenarioHostCalls ?? []).filter((call) =>
        call.startsWith("reference "),
      ).length,
  );

async function ask_(target: Page, query: string) {
  await field(target).fill(query);
  await searchButton(target).click();
}

test("nothing is searched until the person asks, and the page says its answers are orientation", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.reference.title");
  await expect(railButton(target)).toHaveAttribute("aria-pressed", "true");
  await expect(target.locator("#tab-docs")).toHaveText(
    label("desktop.reference.title"),
  );
  const page = referencePage(target);
  await expect(page).toBeVisible();
  await expect(page).toBeFocused();
  // The standing is never searched: not an empty answer, not a search.
  await expect(page.locator("[data-reference-idle]")).toHaveText(
    label("desktop.reference.idle"),
  );
  await expect(page.locator("[data-reference-orientation]")).toHaveText(
    label("desktop.reference.orientation"),
  );
  await expect(page.locator("[data-reference-empty]")).toHaveCount(0);
  await expect(searchButton(target)).toBeDisabled();
  await target.evaluate(
    () => new Promise((resolve) => window.setTimeout(resolve, 400)),
  );
  expect(await searches(target)).toBe(0);
});

test("a search draws the served passages, sources and terminology", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.reference.title");
  // Pressing Enter in the field asks as the button does.
  await field(target).fill("  synthetic query  ");
  await field(target).press("Enter");
  const page = referencePage(target);
  const passages = page.locator('[data-reference="passages"]');
  await expect(passages.locator("[data-reference-hit]")).toHaveCount(2);
  await expect(passages).toContainText("Synthetic source one");
  await expect(passages).toContainText(
    "Synthetic passage one, about the query.",
  );
  await expect(passages).toContainText(
    label("desktop.reference.source", { source: "synthetic/source-0" }),
  );
  const terms = page.locator('[data-reference="terminology"]');
  await expect(terms).toContainText("Synthetic concept");
  await expect(terms).toContainText("Synthetic: what the concept names.");
  await expect(terms).toContainText(
    label("desktop.reference.matched_on", { term: "synthetic term" }),
  );
  await expect(page.locator("[data-reference-idle]")).toHaveCount(0);
  // The query went as typed, without the white space around it, once.
  await expect(searches(target)).resolves.toBe(1);
  await expect(
    target.evaluate(() => window.__scenarioHostCalls ?? []),
  ).resolves.toContain("reference en 8 synthetic query");
});

test("an exact citation draws its served verbatim evidence", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.reference.title");
  await ask_(target, CITATION_QUERY);
  const citation = referencePage(target).locator('[data-reference="citation"]');
  await expect(citation).toContainText(CITATION_QUERY);
  await expect(citation).toContainText(
    "Synthetic verbatim text of the cited provision.",
  );
  await expect(citation).toContainText(
    label("desktop.reference.article", { article: "1" }),
  );
  await expect(citation).toContainText(
    "cadrumo://corpus/synthetic/source-citation",
  );
  await expect(
    referencePage(target).locator('[data-reference="passages"]'),
  ).toHaveCount(0);
});

test("a search that matches nothing says so, and is not the standing of a search that failed", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.reference.title");
  await ask_(target, NO_MATCH_QUERY);
  const page = referencePage(target);
  await expect(page.locator("[data-reference-empty]")).toHaveText(
    label("desktop.reference.empty", { query: NO_MATCH_QUERY }),
  );
  await expect(page.locator("[data-reference-failed]")).toHaveCount(0);
  await expect(page.locator("[data-reference-idle]")).toHaveCount(0);
});

test("a search in flight is told apart from the others and cannot be asked twice", async ({
  page: target,
}) => {
  await seedLayout(target);
  await target.addInitScript(() => {
    window.__scenarioReferenceHeld = true;
  });
  await open(target, "signed-in");
  await openRailView(target, "desktop.reference.title");
  await ask_(target, "synthetic");
  const page = referencePage(target);
  await expect(page.locator("[data-reference-searching]")).toHaveText(
    label("desktop.reference.searching"),
  );
  await expect(page).toHaveAttribute("aria-busy", "true");
  await expect(searchButton(target)).toBeDisabled();
  await expect(page.locator("[data-reference-idle]")).toHaveCount(0);
  await expect(page.locator("[data-reference-empty]")).toHaveCount(0);
  await target.evaluate(() => {
    window.__scenarioReferenceHeld = false;
  });
  await expect(page.locator("[data-reference-hit]").first()).toBeVisible();
  await expect(page.locator("[data-reference-searching]")).toHaveCount(0);
  expect(await searches(target)).toBe(1);
});

test("a search that fails says so with its code, is never drawn as no result and is made again only on request", async ({
  page: target,
}) => {
  await seedLayout(target);
  await target.addInitScript(() => {
    window.__scenarioReferenceRefused = true;
  });
  await open(target, "signed-in");
  await openRailView(target, "desktop.reference.title");
  await ask_(target, "synthetic");
  const failed = referencePage(target).locator("[data-reference-failed]");
  await expect(failed).toHaveAttribute("data-reference-failed", "timed_out");
  await expect(failed).toContainText(
    label("desktop.reference.failed", { code: "timed_out" }),
  );
  await expect(
    referencePage(target).locator("[data-reference-empty]"),
  ).toHaveCount(0);
  expect(await searches(target)).toBe(1);
  // Left alone, it is not searched again.
  await target.evaluate(
    () => new Promise((resolve) => window.setTimeout(resolve, 600)),
  );
  expect(await searches(target)).toBe(1);
  // Asked again once the host answers, it shows the answer.
  await target.evaluate(() => {
    window.__scenarioReferenceRefused = false;
  });
  await failed
    .getByRole("button", { name: label("desktop.reference.search_again") })
    .click();
  await expect(
    referencePage(target).locator("[data-reference-hit]").first(),
  ).toBeVisible();
  expect(await searches(target)).toBe(2);
});

test("the typed text stays when the page is shown again, with its answer", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.reference.title");
  await ask_(target, "synthetic");
  await expect(
    referencePage(target).locator("[data-reference-hit]").first(),
  ).toBeVisible();
  await target.locator('[data-rail="home"]').click();
  await expect(referencePage(target)).toHaveCount(0);
  await openRailView(target, "desktop.reference.title");
  await expect(field(target)).toHaveValue("synthetic");
  await expect(
    referencePage(target).locator("[data-reference-hit]").first(),
  ).toBeVisible();
  expect(await searches(target)).toBe(1);
});

test("the palette opens Reference by its label", async ({ page: target }) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await target.keyboard.press("ControlOrMeta+Shift+KeyK");
  const input = target
    .locator(".palette")
    .getByRole("combobox", { name: label("desktop.palette.label") });
  await expect(input).toBeFocused();
  await input.fill(label("navigation.view.reference.label"));
  await target
    .locator(".palette")
    .getByRole("option")
    .filter({
      has: target.locator(".palette-title", {
        hasText: new RegExp(`^${label("navigation.view.reference.label")}$`),
      }),
    })
    .click();
  await expect(referencePage(target)).toBeVisible();
  await expect(referencePage(target)).toBeFocused();
  expect(await searches(target)).toBe(0);
});

test("an agent link to Reference opens it with the keyboard on it and no notice", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await ask(target, "Respóndeme con enlaces");
  await settled(target);
  await agentTurns(target)
    .getByRole("link", { name: "la referencia", exact: true })
    .click();
  const page = referencePage(target);
  await expect(page).toBeVisible();
  await expect(page).toBeFocused();
  await expect(windowToast(target)).toHaveText("");
  expect(await searches(target)).toBe(0);
});

test("signing out drops what was found and asks for a sign-in, searching nothing more", async ({
  page: target,
}) => {
  await seedLayout(target);
  await open(target, "signed-in");
  await openRailView(target, "desktop.reference.title");
  await ask_(target, "synthetic");
  await expect(
    referencePage(target).locator("[data-reference-hit]").first(),
  ).toBeVisible();
  await target.keyboard.press("ControlOrMeta+k");
  await target
    .locator(".palette")
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.account.sign_out"));
  await target.keyboard.press("Enter");
  const page = referencePage(target);
  await expect(page).toContainText(label("desktop.reference.signed_out"));
  await expect(page.locator("[data-reference-hit]")).toHaveCount(0);
  await expect(page.locator("[data-reference-orientation]")).toHaveCount(0);
  await expect(field(target)).toHaveCount(0);
  expect(await searches(target)).toBe(1);
});
