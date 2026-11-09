import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import type { ModeloDeclarationsListProjectionV1 } from "../../src/shell/modeloContract/modeloDeclarations";
import type { ModeloWorkbenchFormProjectionV1 } from "../../src/shell/modeloContract/modeloWorkForm";
import { label } from "../support/strings";
import { MODELO_FIXTURES } from "../support/windowFixtures";

declare global {
  interface Window {
    __sourceRequests?: unknown[];
  }
}

// An annual summary whose quarters are not there yet. The form the backend
// read for the scenario's Modelo 390 names each Modelo 303 period it sums that
// is missing, unverified or not yet filed, in the read model's words and with
// the step that puts it right; the to-do rail lists them under its own heading
// and each one is a door. The spec reads the recorded form rather than stating
// a period, a sentence or a request of its own.

const FORM = "modelo-390-0A";

/** The form the scenario answers for the Modelo 390, as the application read it. */
const recorded = (language = "en") =>
  JSON.parse(
    readFileSync(new URL(`${FORM}-${language}.json`, MODELO_FIXTURES), "utf8"),
  ) as ModeloWorkbenchFormProjectionV1;

const open = (target: Page) =>
  target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");

const sources = (target: Page) => target.locator("[data-todo-sources]");

/** The declarations row that opens the recorded form, as the list read it. */
const summaryRow = () => {
  const listed = JSON.parse(
    readFileSync(new URL("declarations-en.json", MODELO_FIXTURES), "utf8"),
  ) as ModeloDeclarationsListProjectionV1;
  const row = listed.rows.find(
    (candidate) => candidate.work_unit_id === recorded().work_unit_id,
  );
  if (!row) throw new Error(`the declarations list names no row for ${FORM}`);
  return row;
};

async function openAnnualSummary(target: Page) {
  await open(target);
  await target.locator("[data-rail=declarations]").click();
  const rows = target
    .locator(".declarations-page")
    .getByRole("grid")
    .locator("[data-kind=data]");
  // The list is one large read; under a loaded host it takes a while.
  await expect(rows.first()).toBeVisible({ timeout: 15_000 });
  // The modelo has a row for every year it is due, and only this one opens
  // the recorded work, so the row is picked by its period as well as its title.
  const row = summaryRow();
  await rows
    .filter({ hasText: row.modelo_title })
    .filter({ hasText: row.period_words ?? row.modelo_title })
    .first()
    .dblclick();
  await expect(target.locator(".declarations-workspace")).toBeVisible();
}

test("the to-do rail lists each declaration the summary still needs, in the read model's words", async ({
  page: target,
}) => {
  const needed = recorded().source_requirements;
  // ANTI-VACUITY: the scenario's summary sums quarters it does not hold yet.
  expect(needed.length).toBeGreaterThan(0);

  await openAnnualSummary(target);
  await expect(sources(target)).toContainText(
    label("workspace.modelo.todo.sources"),
  );
  const doors = sources(target).getByRole("button");
  await expect(doors).toHaveCount(needed.length);
  for (const [index, requirement] of needed.entries()) {
    const door = doors.nth(index);
    await expect(door).toHaveText(requirement.words);
    await expect(door).toHaveAttribute("title", requirement.next_step.words);
    await expect(door).toHaveAttribute(
      "data-todo-source",
      requirement.next_step.kind,
    );
  }
});

test("a missing quarter's door creates exactly the declaration the read model named", async ({
  page: target,
}) => {
  const missing = recorded().source_requirements.find(
    (requirement) => requirement.next_step.kind === "create_work",
  );
  expect(missing).toBeDefined();
  if (missing?.next_step.kind !== "create_work") return;
  const step = missing.next_step;

  await openAnnualSummary(target);
  await target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const submit = port.submit;
    const requests: unknown[] = (window.__sourceRequests = []);
    port.submit = async (...args) => {
      if (args[0] === "modelo.work.create") requests.push(args[1]);
      return submit(...args);
    };
  });
  await sources(target)
    .getByRole("button", { name: missing.words, exact: true })
    .click();

  await expect
    .poll(() => target.evaluate(() => window.__sourceRequests ?? []))
    .toEqual([
      expect.objectContaining({
        modelo: step.modelo,
        period: { filing_year: step.filing_year, code: step.period_code },
      }),
    ]);
});
