import { expect, test, type Page } from "@playwright/test";
import type { PublicModeloFormElectionQuestion } from "../../src/shell/modeloContract/modeloWorkForm";
import { label } from "../support/strings";

// How the 2025 Modelo 100's result is settled, in the export view: the
// questions the export offer served, with the amounts of a split and the
// words of why a question cannot be answered. Every sentence and amount below
// is read from the scenario's modelo port, which answers what the application
// served; the window words only its own frame.

const LANGUAGES = ["en", "es", "ca", "hu"] as const;
type Language = (typeof LANGUAGES)[number];

const workspace = (target: Page) => target.locator(".declarations-workspace");

/** Opens the filer's Modelo 100 the way the list offers it, then its export
 * view. */
async function openFiling(target: Page, shape: string, language: Language) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=${shape}&lang=${language}`,
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
      name: label("workspace.modelo.filing.title", {}, language),
    })
    .click();
  const settlement = workspace(target).locator("[data-settlement]");
  await expect(settlement).toBeVisible();
  return settlement;
}

/** The questions the export offer served for the filer's declaration. */
async function servedQuestions(
  target: Page,
  language: Language,
): Promise<PublicModeloFormElectionQuestion[]> {
  return target.evaluate(async (asked) => {
    const port = window.__fixtureModelo!;
    const list = await port.declarations(asked);
    const unit = list.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!.existing!.work_unit_id;
    const offer = (await port.form(unit, asked)).export_offer;
    if (!offer) throw new Error("the form served no export offer");
    return offer.elections;
  }, language);
}

for (const language of LANGUAGES) {
  test(`a split within the period states both instalments as advisory (${language})`, async ({
    page,
  }) => {
    const settlement = await openFiling(page, "renta-instalment", language);
    const served = (await servedQuestions(page, language)).find(
      (question) => question.election === "instalment",
    )!;
    expect(served.state).toBe("available");
    expect(served.figures.length).toBe(2);

    const question = settlement.locator("[data-election=instalment]");
    await expect(question).toHaveAttribute("data-state", "available");
    const figures = question.locator("[data-figure]");
    await expect(figures).toHaveCount(2);
    for (const [position, figure] of served.figures.entries()) {
      const drawn = figures.nth(position);
      // The amount is the one the application stated, as written.
      await expect(drawn).toHaveAttribute("data-amount", figure.amount);
      await expect(drawn).toContainText(figure.words);
      await expect(drawn).toHaveAttribute("data-advisory", "true");
      await expect(drawn).toContainText(figure.advisory_words!);
      await expect(drawn.locator("[data-slot=badge]")).toHaveText(
        label("desktop.modelo.settlement.advisory", {}, language),
      );
    }
    // An answer is chosen, never typed, and the figures stay beside it.
    const select = question.locator("select");
    const split = served.choices.find((choice) => choice.value !== "single")!;
    await select.selectOption(split.value);
    await expect(select).toHaveValue(split.value);
    await expect(figures).toHaveCount(2);
  });

  test(`a split after the filing period is unavailable and says why (${language})`, async ({
    page,
  }) => {
    const settlement = await openFiling(page, "renta-pay", language);
    const served = (await servedQuestions(page, language)).find(
      (question) => question.election === "instalment",
    )!;
    expect(served.state).toBe("unavailable");
    expect(served.reason).toBe("past_filing_window");

    const question = settlement.locator("[data-election=instalment]");
    await expect(question).toHaveAttribute("data-reason", served.reason!);
    await expect(question).toContainText(served.state_words!);
    await expect(question.locator("select")).toHaveCount(0);
    await expect(question.locator("[data-figure]")).toHaveCount(0);
    // Paying the result at once is still an answer the filer chooses.
    await expect(
      settlement.locator("[data-election=payment] select"),
    ).toHaveCount(1);
  });

  test(`a result that could not be calculated is unknown, not settled (${language})`, async ({
    page,
  }) => {
    const settlement = await openFiling(page, "renta", language);
    const served = (await servedQuestions(page, language)).filter(
      (question) => question.state !== "not_applicable",
    );
    expect(served.length).toBeGreaterThan(0);
    for (const question of served) {
      expect(question.reason).toBe("result_unknown");
      const drawn = settlement.locator(`[data-election=${question.election}]`);
      await expect(drawn).toHaveAttribute("data-reason", "result_unknown");
      await expect(drawn).toContainText(question.state_words!);
      await expect(drawn.locator("select")).toHaveCount(0);
      await expect(drawn.locator("[data-figure]")).toHaveCount(0);
    }
  });
}
