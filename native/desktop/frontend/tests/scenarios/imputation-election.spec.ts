import { expect, test, type Page } from "@playwright/test";
import { windowFixture } from "../support/windowFixtures";
import { readFileSync } from "node:fs";
import type { ImputationElection } from "../../src/shell/profileHousehold";
import { label } from "../support/strings";

// The imputation election element in the Renta's Sources view, shown because
// the form says the declaration asks for it. The profile states are what the
// application read through `user-profile.imputation-election.read`; every
// question, choice and refusal sentence below is that served text, not wording
// of the window.

type Served = {
  reads: Record<string, Record<string, ImputationElection>>;
  refusals: Record<string, Record<string, { refusal_words: string }>>;
};
const served = JSON.parse(
  readFileSync(
    windowFixture("desktop-imputation-election", "imputationElection"),
    "utf8",
  ),
) as Served;

const LANGUAGES = ["en", "es", "ca", "hu"] as const;
type Language = (typeof LANGUAGES)[number];
/** The ejercicio the application read the elections for. */
const YEAR = served.reads.devengo!.en!.tax_year;

const workspace = (target: Page) => target.locator(".declarations-workspace");

/** Opens the filer's Modelo 100 the way the list offers it, then its Sources
 * view, where the profile's elements are drawn. */
async function openSources(
  target: Page,
  election: string,
  language: Language = "en",
) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=renta&election=${election}&lang=${language}`,
  );
  await target.locator("[data-rail=declarations]").click();
  const read = await target.evaluate(
    async (asked) => window.__fixtureModelo!.declarations(asked),
    language,
  );
  const existing = read.creation_targets.find(
    (entry) => entry.modelo === "100" && entry.existing,
  )!;
  await target
    .getByRole("button", {
      name: label("workspace.declarations.list.key.new", {}, language),
    })
    .first()
    .click();
  const dialog = target.getByRole("dialog");
  await dialog.getByText(existing.modelo_title, { exact: true }).click();
  await dialog.getByRole("radio", { name: existing.period_words! }).click();
  await dialog
    .getByRole("button", {
      name: label("workspace.declarations.list.new.open_it", {}, language),
    })
    .click();
  await expect(
    workspace(target).getByRole("heading", { level: 1 }),
  ).toBeVisible({ timeout: 30_000 });
  await workspace(target)
    .getByRole("tab", {
      name: label("workspace.modelo.key.sources", {}, language),
    })
    .click();
  const element = workspace(target).getByRole("region", {
    name: label("workspace.modelo.election.title", { year: YEAR }, language),
  });
  await expect(element).toBeVisible();
  return element;
}

const stateOf = (element: ReturnType<Page["locator"]>) =>
  element.locator("[data-election-state]");
const radios = (element: ReturnType<Page["locator"]>) =>
  element.getByRole("radio");

test("an unstated year reads undeclared and none of the choices is selected", async ({
  page: target,
}) => {
  const element = await openSources(target, "undeclared");
  const read = served.reads.undeclared!.en!;
  await expect(stateOf(element)).toHaveAttribute(
    "data-election-state",
    "undeclared",
  );
  await expect(stateOf(element)).toHaveText(
    label("workspace.modelo.election.state.undeclared", { year: YEAR }),
  );
  // The questions and choices are the ones the setup wizard asks.
  await expect(element).toContainText(read.criterion_question.prompt);
  for (const choice of read.criterion_question.choices)
    await expect(element).toContainText(choice.label);
  await expect(radios(element)).toHaveCount(
    read.criterion_question.choices.length,
  );
  for (const radio of await radios(element).all())
    await expect(radio).not.toBeChecked();
  // The accounting question is not asked, and nothing can be saved yet.
  await expect(element).not.toContainText(read.accounting_question.prompt);
  await expect(
    element.getByRole("button", {
      name: label("workspace.modelo.election.save", { year: YEAR }),
    }),
  ).toBeDisabled();
  // The earlier years the profile states are listed with the served labels.
  await expect(element).toContainText(
    label("workspace.modelo.election.other_years"),
  );
  await expect(element).toContainText(
    `${read.criterion_statements[0]!.ejercicio}: ${read.criterion_question.choices[0]!.label}`,
  );
});

test("a declared year selects the stated choice and asks only the question the application says", async ({
  page: target,
}) => {
  const read = served.reads.devengo!.en!;
  const element = await openSources(target, "devengo");
  await expect(stateOf(element)).toHaveAttribute(
    "data-election-state",
    "declared",
  );
  await expect(radios(element).nth(0)).toBeChecked();
  await expect(radios(element).nth(1)).not.toBeChecked();
  await expect(element).not.toContainText(read.accounting_question.prompt);
});

test("a cash-basis year asks the accounting question with its stated answer", async ({
  page: target,
}) => {
  const read = served.reads.cobros_y_pagos!.en!;
  const element = await openSources(target, "cobros_y_pagos");
  await expect(radios(element).nth(1)).toBeChecked();
  await expect(element).toContainText(read.accounting_question.prompt);
  // The accounting choices are the second group: "no" is the stated one.
  const accounting = element.getByRole("radiogroup").nth(1);
  const stated = read.accounting_question.choices.findIndex(
    (choice) => choice.value === read.codigo_comercio_accounting.value,
  );
  await expect(accounting.getByRole("radio").nth(stated)).toBeChecked();
});

test("choosing the criterion the application names asks the accounting question, and choosing another takes it away", async ({
  page: target,
}) => {
  const read = served.reads.undeclared!.en!;
  const element = await openSources(target, "undeclared");
  const asked = read.criterion_question.choices.findIndex((choice) =>
    read.accounting_asked_for_criteria.includes(choice.value),
  );
  const other = asked === 0 ? 1 : 0;
  await radios(element).nth(asked).click();
  await expect(element).toContainText(read.accounting_question.prompt);
  await radios(element).nth(other).click();
  await expect(element).not.toContainText(read.accounting_question.prompt);
});

test("a contradictory year is said so and selects nothing", async ({
  page: target,
}) => {
  const element = await openSources(target, "contradictory");
  await expect(stateOf(element)).toHaveAttribute(
    "data-election-state",
    "contradictory",
  );
  await expect(element).toContainText(
    label("workspace.modelo.election.contradictory", { year: YEAR }),
  );
  for (const radio of await radios(element).all())
    await expect(radio).not.toBeChecked();
  await expect(
    element.getByRole("button", {
      name: label("workspace.modelo.election.clear", { year: YEAR }),
    }),
  ).toBeVisible();
});

test("a save names the revision it read, and the election is read again", async ({
  page: target,
}) => {
  const read = served.reads.undeclared!.en!;
  const element = await openSources(target, "undeclared");
  const before = await target.evaluate(() =>
    window.__scenarioElection!.reads(),
  );
  await radios(element).nth(0).click();
  await element
    .getByRole("button", {
      name: label("workspace.modelo.election.save", { year: YEAR }),
    })
    .click();
  await expect(stateOf(element)).toHaveAttribute(
    "data-election-state",
    "declared",
  );
  await expect(element).toContainText(
    label("workspace.modelo.election.saved", { year: YEAR }),
  );
  const writes = await target.evaluate(() =>
    window.__scenarioElection!.writes(),
  );
  expect(writes).toHaveLength(1);
  expect(writes[0]).toMatchObject({
    expected_revision: read.record_revision,
    expected_content_digest: read.content_digest,
    edit: {
      kind: "imputation_election",
      tax_year: YEAR,
      criterion: read.criterion_question.choices[0]!.value,
      codigo_comercio_accounting: null,
    },
  });
  // The read after the write is the one that shows the stated year.
  expect(await target.evaluate(() => window.__scenarioElection!.reads())).toBe(
    before + 1,
  );
  await expect(radios(element).nth(0)).toBeChecked();
});

test("clearing a stated year sends an empty token and the year reads undeclared again", async ({
  page: target,
}) => {
  const element = await openSources(target, "devengo");
  await element
    .getByRole("button", {
      name: label("workspace.modelo.election.clear", { year: YEAR }),
    })
    .click();
  await expect(stateOf(element)).toHaveAttribute(
    "data-election-state",
    "undeclared",
  );
  const writes = await target.evaluate(() =>
    window.__scenarioElection!.writes(),
  );
  // Each question the year states is cleared with an empty token; one that
  // states nothing is left as it is.
  const stated = served.reads.devengo!.en!;
  expect(writes[0]).toMatchObject({
    edit: {
      criterion: "",
      codigo_comercio_accounting:
        stated.codigo_comercio_accounting.state === "undeclared" ? null : "",
    },
  });
  for (const radio of await radios(element).all())
    await expect(radio).not.toBeChecked();
});

test("a refused write shows the application's sentence and keeps the choice", async ({
  page: target,
}) => {
  const element = await openSources(target, "undeclared");
  await target.evaluate(() =>
    window.__scenarioElection!.refuseNext("unknown_choice"),
  );
  await radios(element).nth(0).click();
  await element
    .getByRole("button", {
      name: label("workspace.modelo.election.save", { year: YEAR }),
    })
    .click();
  await expect(element.getByRole("alert")).toContainText(
    served.refusals.unknown_choice!.en!.refusal_words,
  );
  // Nothing was stated: the year is still undeclared and the choice is kept
  // to be corrected.
  await expect(stateOf(element)).toHaveAttribute(
    "data-election-state",
    "undeclared",
  );
  await expect(radios(element).nth(0)).toBeChecked();
});

test("a change that was not seen to settle is unknown and is read again, not repeated", async ({
  page: target,
}) => {
  const element = await openSources(target, "undeclared");
  await target.evaluate(() => window.__scenarioElection!.loseNextAnswer());
  await radios(element).nth(0).click();
  await element
    .getByRole("button", {
      name: label("workspace.modelo.election.save", { year: YEAR }),
    })
    .click();
  await expect(element.getByRole("alert")).toContainText(
    label("desktop.profile.unknown"),
  );
  // The read after it shows what the profile came to state.
  await expect(stateOf(element)).toHaveAttribute(
    "data-election-state",
    "declared",
  );
  expect(
    await target.evaluate(() => window.__scenarioElection!.writes()),
  ).toHaveLength(1);
});

for (const language of LANGUAGES) {
  test(`the questions and states are served in ${language}`, async ({
    page: target,
  }) => {
    const read = served.reads.cobros_y_pagos![language]!;
    const element = await openSources(target, "cobros_y_pagos", language);
    await expect(element).toContainText(read.criterion_question.prompt);
    await expect(element).toContainText(read.accounting_question.prompt);
    await expect(stateOf(element)).toHaveText(
      label(
        "workspace.modelo.election.state.declared",
        { year: YEAR },
        language,
      ),
    );
  });
}
