import { expect, type Page, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import type { ProfileImputationElectionReadProjection } from "../../src/shell/profileContract";
import { label } from "../support/strings";
import { openDeclaration, tab } from "../support/scenarioModelo";
import { windowFixture } from "../support/windowFixtures";

// The host answers a profile's reads one at a time, so a read the window asks
// again for a declaration that has not changed holds every read behind it,
// the form's own on a page return included. The History view's record and
// history are asked once per revision of the declaration: showing the view
// again, or coming back to the page, reuses them while the form read says the
// same revision; a changed revision asks once. The profile's imputation
// election is asked once per showing of the declaration page: showing the
// Sources view again reuses it, and a page return asks once, since the
// profile can change on its own page meanwhile.

declare global {
  interface Window {
    __pageReturnReads?: Record<string, number>;
    __pageReturnRevision?: string | null;
  }
}

const HISTORY = "workspace.modelo.history.title";
const FORM = "desktop.modelo.view.form";
const SOURCES = "workspace.modelo.key.sources";

/** Counts what the window submits by definition, and answers the history the
 * scenario does not serve with an empty one. Each record and history read
 * takes a while, as one behind others in the host's lane does, so a view
 * shown again while they run is seen too. */
const countSubmits = (target: Page) =>
  target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const submit = port.submit.bind(port);
    const form = port.form.bind(port);
    window.__pageReturnReads = {};
    window.__pageReturnRevision = null;
    const pause = () =>
      new Promise((resolve) => window.setTimeout(resolve, 400));
    port.submit = (async (definition: string, ...rest: unknown[]) => {
      const reads = window.__pageReturnReads!;
      reads[definition] = (reads[definition] ?? 0) + 1;
      if (definition === "modelo.work.history") {
        await pause();
        return {
          kind: "settled",
          operation_id: `history-${reads[definition]}`,
          revision: 1,
          result: { entries: [] },
        };
      }
      if (definition === "modelo.work.metadata") await pause();
      return (submit as (...args: unknown[]) => unknown)(definition, ...rest);
    }) as typeof port.submit;
    // A form read that says another calculation revision, when asked to.
    port.form = async (...args) => {
      const read = await form(...args);
      const revision = window.__pageReturnRevision;
      return revision ? { ...read, calculation_revision_id: revision } : read;
    };
  });
const submitted = (target: Page, definition: string) =>
  target.evaluate(
    (asked) => window.__pageReturnReads?.[asked] ?? 0,
    definition,
  );

/** Leaves the declaration for the Ledger and comes back, then waits for the
 * fresh form read to land and for anything it asks after it. */
async function pageReturn(target: Page) {
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator("section.ledger-page")).toBeVisible();
  await target.locator("[data-rail=declarations]").click();
  await expect(target.locator(".declarations-workspace")).toBeVisible();
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
}

async function show(target: Page, key: string) {
  const shown = tab(target, key);
  if ((await shown.getAttribute("aria-selected")) !== "true")
    await shown.click();
  await expect(shown).toHaveAttribute("aria-selected", "true");
}

test("the History view reads the record and history once per revision of the declaration", async ({
  page: target,
}) => {
  await openDeclaration(target, "130", { shape: "receipt" });
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  await countSubmits(target);
  const counts = async () => ({
    metadata: await submitted(target, "modelo.work.metadata"),
    history: await submitted(target, "modelo.work.history"),
  });

  await show(target, HISTORY);
  // Shown again while the first answers are on their way, and after.
  for (let round = 0; round < 3; round += 1) {
    await show(target, FORM);
    await show(target, HISTORY);
  }
  await target.waitForTimeout(1500);
  expect(await counts()).toEqual({ metadata: 1, history: 1 });

  // Back on the page with the declaration unchanged: nothing is asked again.
  await pageReturn(target);
  await show(target, HISTORY);
  await target.waitForTimeout(1500);
  expect(await counts()).toEqual({ metadata: 1, history: 1 });

  // Back on the page with another calculation revision: asked once.
  await target.evaluate(() => {
    window.__pageReturnRevision = "page-return-revision";
  });
  await pageReturn(target);
  await show(target, HISTORY);
  await target.waitForTimeout(1500);
  expect(await counts()).toEqual({ metadata: 2, history: 2 });
});

type Served = {
  reads: Record<
    string,
    Record<string, ProfileImputationElectionReadProjection>
  >;
};
const served = JSON.parse(
  readFileSync(
    windowFixture("desktop-imputation-election", "imputationElection"),
    "utf8",
  ),
) as Served;
const YEAR = served.reads.devengo!.en!.tax_year;

test("the imputation election is read once per showing of the declaration page", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=renta&election=devengo&lang=en",
  );
  await target.locator("[data-rail=declarations]").click();
  const read = await target.evaluate(async () =>
    window.__fixtureModelo!.declarations("en"),
  );
  const existing = read.creation_targets.find(
    (entry) => entry.modelo === "100" && entry.existing,
  )!;
  await target
    .getByRole("button", { name: label("workspace.declarations.list.key.new") })
    .first()
    .click();
  const dialog = target.getByRole("dialog");
  await dialog.getByText(existing.modelo_title, { exact: true }).click();
  await dialog.getByRole("radio", { name: existing.period_words! }).click();
  await dialog
    .getByRole("button", {
      name: label("workspace.declarations.list.new.open_it"),
    })
    .click();
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0, {
    timeout: 30_000,
  });
  const element = target
    .locator(".declarations-workspace")
    .getByRole("region", {
      name: label("workspace.modelo.election.title", { year: YEAR }),
    });
  const reads = () => target.evaluate(() => window.__scenarioElection!.reads());
  const before = await reads();

  await show(target, SOURCES);
  await expect(element).toBeVisible();
  for (let round = 0; round < 3; round += 1) {
    await show(target, FORM);
    await show(target, SOURCES);
    await expect(element).toBeVisible();
  }
  await target.waitForTimeout(500);
  expect((await reads()) - before).toBe(1);

  await pageReturn(target);
  await show(target, SOURCES);
  await expect(element).toBeVisible();
  await target.waitForTimeout(500);
  expect((await reads()) - before).toBe(2);
});
