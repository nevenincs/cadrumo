import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import type { BorradorComparison } from "../../src/shell/borrador";
import type { LedgerErrorDetail } from "../../src/shell/ledger";
import type { ModeloTaxationComparisonProjection } from "../../src/shell/modeloContract/modeloWork";
import { label } from "../support/strings";
import { MODELO_FIXTURES } from "../support/windowFixtures";

// The comparisons of the 2025 Modelo 100: joint against individual filing, and
// the AEAT draft against the saved calculation. Every amount, status, reason
// and sentence below is read from what the scenario's host answers, which is
// what the application read for synthetic households; the window words only
// its own frame, and the expected amounts are compared by their digits so the
// window's formatting is not trusted to check itself.

const LANGUAGES = ["en", "es", "ca", "hu"] as const;
type Language = (typeof LANGUAGES)[number];

const workspace = (target: Page) => target.locator(".declarations-workspace");

const digits = (text: string | null) => (text ?? "").replace(/\D/g, "");

/** Opens the filer's Modelo 100 the way the list offers it, then its
 * comparison view. */
async function openCompare(
  target: Page,
  shape: string,
  language: Language,
  borrador?: string,
) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=${shape}&lang=${language}${
      borrador ? `&borrador=${borrador}` : ""
    }`,
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
      name: label("desktop.modelo.view.compare", {}, language),
    })
    .click();
  return workspace(target).getByRole("tabpanel");
}

/** What the application served when the comparison was asked for the filer's
 * declaration: its answer, or its refusal's detail. */
async function servedComparison(
  target: Page,
  language: Language,
): Promise<
  | { kind: "settled"; result: ModeloTaxationComparisonProjection }
  | { kind: "refused"; detail: LedgerErrorDetail }
> {
  return target.evaluate(async (asked) => {
    const port = window.__fixtureModelo!;
    const list = await port.declarations(asked);
    const unit = list.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!.existing!.work_unit_id;
    // The comparison is worded in the language the form was last read in.
    await port.form(unit, asked);
    const outcome = await port.submit("modelo.work.compare_taxation", {
      work_unit_id: unit,
    });
    if (outcome.kind === "settled")
      return { kind: "settled" as const, result: outcome.result };
    if (outcome.kind === "refused" && outcome.detail)
      return { kind: "refused" as const, detail: outcome.detail };
    throw new Error("the comparison neither answered nor refused");
  }, language);
}

const context = (detail: LedgerErrorDetail, key: string) =>
  String(detail.context.find((fact) => fact.key === key)?.value ?? "");

/** Asks for the comparison and returns its element. */
async function ask(panel: Locator) {
  const element = panel.locator("[data-taxation-comparison]");
  await expect(element).toBeVisible();
  await element.locator("[data-comparison-ask]").click();
  return element;
}

for (const language of LANGUAGES) {
  test(`joint filing comes out lower: both modes, their amounts and the reason as served (${language})`, async ({
    page,
  }) => {
    const panel = await openCompare(page, "renta-married", language);
    const element = await ask(panel);
    const served = await servedComparison(page, language);
    if (served.kind !== "settled") throw new Error("the comparison refused");
    const projection = served.result;

    const result = element.locator("[data-comparison-result]");
    await expect(result).toBeVisible();
    await expect(result).toHaveAttribute(
      "data-recommendation",
      projection.recommendation,
    );
    const joint = result.locator("[data-comparison-mode=joint]");
    const individual = result.locator("[data-comparison-mode=individual]");
    // The exact amounts of each mode, in its own column.
    const tax = async (mode: Locator) =>
      digits(await mode.locator("[data-comparison-tax]").textContent());
    const amount = async (mode: Locator) =>
      digits(
        await mode.locator("[data-comparison-result-amount]").textContent(),
      );
    expect(await tax(joint)).toBe(digits(projection.conjunta_cuota_resultante));
    expect(await amount(joint)).toBe(digits(projection.conjunta_resultado));
    expect(await tax(individual)).toBe(
      digits(projection.individual_cuota_resultante),
    );
    expect(await amount(individual)).toBe(
      digits(projection.individual_resultado),
    );
    // Only the recommended mode is marked, and the sentence is the served one.
    await expect(joint).toHaveAttribute("data-recommended", "true");
    await expect(individual).toHaveAttribute("data-recommended", "false");
    await expect(joint.locator("[data-slot=badge]")).toHaveText(
      label("desktop.modelo.compare.taxation.recommended", {}, language),
    );
    await expect(result.locator("[data-comparison-reason]")).toHaveText(
      projection.recommendation_reason_words,
    );
    await expect(result.locator("[data-comparison-caveat]")).toHaveText(
      projection.individual_branch_caveat,
    );
    // It is a read: it can be asked for again.
    await expect(element.locator("[data-comparison-ask]")).toBeEnabled();
  });

  test(`boxes without a value are named and open in the form, never read as zero (${language})`, async ({
    page,
  }) => {
    const panel = await openCompare(page, "renta-uncredited", language);
    const element = await ask(panel);
    const served = await servedComparison(page, language);
    if (served.kind !== "refused") throw new Error("the comparison answered");

    const refusal = element.locator("[data-comparison-refusal]");
    await expect(refusal).toHaveAttribute(
      "data-comparison-refusal",
      context(served.detail, "refusal"),
    );
    await expect(refusal.locator("[data-tone]")).toHaveText(
      served.detail.refusal_words!,
    );
    await expect(element.locator("[data-comparison-result]")).toHaveCount(0);
    const boxes = context(served.detail, "casilla_ids")
      .split(",")
      .map((box) => box.trim())
      .filter((box) => box !== "");
    expect(boxes.length).toBeGreaterThan(0);
    for (const box of boxes)
      await expect(
        refusal.locator(`[data-comparison-box="${box}"]`),
      ).toBeVisible();
    // A named box leads to its place in the form.
    await refusal.locator(`[data-comparison-box="${boxes[0]}"] button`).click();
    await expect(
      workspace(page).getByRole("tab", {
        name: new RegExp(`^${label("desktop.modelo.view.form", {}, language)}`),
        selected: true,
      }),
    ).toBeVisible();
  });

  test(`a refusal the household answers leads to the profile (${language})`, async ({
    page,
  }) => {
    const panel = await openCompare(page, "renta-spouseless", language);
    const element = await ask(panel);
    const served = await servedComparison(page, language);
    if (served.kind !== "refused") throw new Error("the comparison answered");
    const refusal = element.locator("[data-comparison-refusal]");
    await expect(refusal).toHaveAttribute(
      "data-comparison-refusal",
      "spouse_unstated",
    );
    await expect(refusal.locator("[data-tone]")).toHaveText(
      served.detail.refusal_words!,
    );
    await refusal.locator("[data-comparison-profile]").click();
    await expect(page.locator(".user-profile-page")).toBeVisible();
  });

  for (const [shape, token, profile] of [
    ["renta", "family_situation_unstated", true],
    ["renta-alone", "no_family_unit", true],
    ["renta-uncalculated", "not_calculated", false],
  ] as const) {
    test(`${token}: the application's sentence, and the profile only where it answers (${language})`, async ({
      page,
    }) => {
      const panel = await openCompare(page, shape, language);
      const element = await ask(panel);
      const served = await servedComparison(page, language);
      if (served.kind !== "refused") throw new Error("the comparison answered");
      const refusal = element.locator("[data-comparison-refusal]");
      await expect(refusal).toHaveAttribute("data-comparison-refusal", token);
      await expect(refusal.locator("[data-tone]")).toHaveText(
        served.detail.refusal_words!,
      );
      await expect(element.locator("[data-comparison-result]")).toHaveCount(0);
      await expect(refusal.locator("[data-comparison-profile]")).toHaveCount(
        profile ? 1 : 0,
      );
      await expect(refusal.locator("[data-comparison-box]")).toHaveCount(0);
    });
  }

  test(`a window with no drafts offers only the comparison of the filing modes (${language})`, async ({
    page,
  }) => {
    const panel = await openCompare(page, "renta-married", language);
    await expect(panel.locator("[data-taxation-comparison]")).toBeVisible();
    await expect(panel.locator("[data-borrador-comparison]")).toHaveCount(0);
  });
}

/** The comparison of the AEAT draft the application read at `state`. */
const servedDraft = (state: string, language: Language): BorradorComparison =>
  JSON.parse(
    readFileSync(
      new URL(`borrador-100-0A-${state}-${language}.json`, MODELO_FIXTURES),
      "utf8",
    ),
  );

for (const language of LANGUAGES) {
  test(`the AEAT draft against the calculation, box by box, the draft apart as an observation (${language})`, async ({
    page,
  }) => {
    const panel = await openCompare(
      page,
      "renta-married",
      language,
      "compared",
    );
    const element = panel.locator("[data-borrador-comparison]");
    await expect(element).toBeVisible();
    await element.locator("[data-comparison-ask]").click();
    const served = servedDraft("compared", language);

    const result = element.locator("[data-borrador-result]");
    await expect(result).toHaveAttribute("data-status", served.status.token);
    await expect(result.locator("[data-borrador-status]")).toHaveText(
      served.status.words,
    );
    // Both sides are named, the draft as an observation and the calculation
    // as local, each in the application's words.
    const draft = result.locator("[data-borrador-side=draft]");
    await expect(draft).toContainText(served.capture!.evidence.words);
    await expect(draft).toContainText(
      label("desktop.modelo.compare.borrador.observation", {}, language),
    );
    const calculation = result.locator("[data-borrador-side=calculation]");
    await expect(calculation).toContainText(served.calculation!.evidence.words);
    await expect(calculation).not.toContainText(
      label("desktop.modelo.compare.borrador.observation", {}, language),
    );
    // Each box is drawn once, under its classification, with its reason.
    await expect(result.locator("[data-borrador-box]")).toHaveCount(
      served.rows.length,
    );
    for (const row of served.rows) {
      const drawn = result.locator(`[data-borrador-box="${row.casilla_id}"]`);
      await expect(drawn).toHaveAttribute(
        "data-classification",
        row.classification.token,
      );
      await expect(drawn).toContainText(row.reason.words);
      const draftValue = drawn.locator("[data-borrador-value]");
      if (row.borrador_value === null)
        await expect(draftValue).toHaveText(
          label("desktop.modelo.compare.borrador.no_value", {}, language),
        );
      else if (typeof row.borrador_value === "object")
        expect(digits(await draftValue.textContent())).toBe(
          digits(row.borrador_value.decimal),
        );
      if (row.difference)
        await expect(
          drawn.locator("[data-borrador-difference]"),
        ).toHaveAttribute("data-borrador-difference", row.difference.decimal);
    }
    for (const [token, count] of Object.entries(served.counts))
      await expect(
        result.locator(`[data-borrador-group=${token}]`),
      ).toHaveCount(count === 0 ? 0 : 1);
  });

  for (const state of ["no-capture", "capture-refused", "no-calculation"]) {
    test(`${state}: the status in the application's words, no boxes, nothing read as agreement (${language})`, async ({
      page,
    }) => {
      const panel = await openCompare(page, "renta-married", language, state);
      const element = panel.locator("[data-borrador-comparison]");
      await element.locator("[data-comparison-ask]").click();
      const served = servedDraft(state, language);
      const result = element.locator("[data-borrador-result]");
      await expect(result).toHaveAttribute("data-status", served.status.token);
      await expect(result.locator("[data-borrador-status]")).toHaveText(
        served.status.words,
      );
      await expect(result.locator("[data-borrador-box]")).toHaveCount(0);
      await expect(result.locator("[data-refused-captures]")).toHaveCount(
        served.refused_captures > 0 ? 1 : 0,
      );
    });
  }

  test(`stale: the reasons are listed and the boxes are still classified (${language})`, async ({
    page,
  }) => {
    const panel = await openCompare(page, "renta-married", language, "stale");
    const element = panel.locator("[data-borrador-comparison]");
    await element.locator("[data-comparison-ask]").click();
    const served = servedDraft("stale", language);
    const result = element.locator("[data-borrador-result]");
    await expect(result).toHaveAttribute("data-status", "stale");
    for (const reason of served.stale_reasons)
      await expect(
        result.locator(`[data-stale-reason=${reason.token}]`),
      ).toHaveText(reason.words);
    await expect(result.locator("[data-borrador-box]")).toHaveCount(
      served.rows.length,
    );
  });

  test(`a read that fails says so and draws no comparison (${language})`, async ({
    page,
  }) => {
    const panel = await openCompare(
      page,
      "renta-married",
      language,
      "unavailable",
    );
    const element = panel.locator("[data-borrador-comparison]");
    await element.locator("[data-comparison-ask]").click();
    await expect(element).toHaveAttribute("data-phase", "failed");
    await expect(element.locator("[data-borrador-result]")).toHaveCount(0);
  });
}
