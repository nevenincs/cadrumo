import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import type { ModeloProjectOperationProjection } from "../../src/shell/modeloContract/modeloProject";
import type { PublicModeloFormField } from "../../src/shell/modeloContract/modeloWorkForm";
import { label } from "../support/strings";
import { MODELO_FIXTURES } from "../support/windowFixtures";

// The withholdings view of the 2025 Modelo 100: the boxes the withholding
// register supplies, as the application served them, the way to the register
// and the estimate from the quarterly declarations. Every figure and every
// sentence below is read from the scenario's modelo port, which answers the
// envelopes the application read; the window words only its own frame.

const LANGUAGES = ["en", "es", "ca", "hu"] as const;
type Language = (typeof LANGUAGES)[number];
const workspace = (target: Page) => target.locator(".declarations-workspace");

/** Opens the filer's Modelo 100 the way the list offers it, then its
 * withholdings view. */
async function openCredits(
  target: Page,
  shape: string,
  language: Language = "en",
) {
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
      name: label("desktop.modelo.view.credits", {}, language),
    })
    .click();
  const panel = workspace(target).getByRole("tabpanel");
  const heading = await target.evaluate(async (asked) => {
    const port = window.__fixtureModelo!;
    const list = await port.declarations(asked);
    const unit = list.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!.existing!.work_unit_id;
    return (await port.form(unit, asked)).form.form.withholding_credits_heading;
  }, language);
  expect(heading, "the form serves its credits heading").toEqual(
    expect.any(String),
  );
  await expect(panel.getByRole("heading", { name: heading! })).toBeVisible();
  return panel;
}

/** The boxes the withholding register supplies, and the boxes the form
 * served as worked out from any of them, each in the order the form draws
 * them; `dependents` is null when the form could not say which they are. */
async function servedCreditBoxes(
  target: Page,
  language: Language,
): Promise<{
  credits: PublicModeloFormField[];
  dependents: PublicModeloFormField[] | null;
}> {
  return target.evaluate(async (asked) => {
    const port = window.__fixtureModelo!;
    const list = await port.declarations(asked);
    const unit = list.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!.existing!.work_unit_id;
    const read = await port.form(unit, asked);
    const served = read.form.form.withholding_credits;
    const key = (address: PublicModeloFormField["address"]) =>
      address.kind === "casilla"
        ? `c:${address.casilla_id}`
        : `b:${address.binding_id}`;
    const credited = new Set(served.map((credit) => key(credit.address)));
    const reading = new Set(
      served.flatMap((credit) => (credit.dependents ?? []).map(key)),
    );
    const fields: PublicModeloFormField[] = [];
    const walk = (node: unknown): void => {
      if (Array.isArray(node)) node.forEach(walk);
      else if (node && typeof node === "object") {
        if ("held_zero" in node && "edit_address" in node)
          fields.push(node as PublicModeloFormField);
        Object.values(node).forEach(walk);
      }
    };
    walk(read.form.form.pages);
    return {
      credits: fields.filter((field) => credited.has(key(field.address))),
      dependents: served.every((credit) => credit.dependents !== null)
        ? fields.filter((field) => reading.has(key(field.address)))
        : null,
    };
  }, language);
}

/** The boxes the withholding register supplies, as the form served them. */
const servedCredits = async (target: Page, language: Language) =>
  (await servedCreditBoxes(target, language)).credits;

/** The estimate the application answered for the filer's profile. */
async function servedEstimate(
  target: Page,
  language: Language,
): Promise<ModeloProjectOperationProjection> {
  return target.evaluate(async (asked) => {
    const port = window.__fixtureModelo!;
    // The estimate is worded in the language the form was last read in.
    const list = await port.declarations(asked);
    const target = list.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!;
    await port.form(target.existing!.work_unit_id, asked);
    // The estimate is for the year of the return the scenario serves.
    const outcome = await port.submit("modelo.project", {
      year: target.filing_year,
    });
    if (outcome.kind !== "settled") throw new Error("the estimate refused");
    return outcome.result;
  }, language);
}

const refusalWords = (language: Language) =>
  (
    JSON.parse(
      readFileSync(
        new URL(
          `refusal-project-no-quarters-${language}.json`,
          MODELO_FIXTURES,
        ),
        "utf8",
      ),
    ) as { refusal_words: string }
  ).refusal_words;

const ask = (panel: ReturnType<Page["locator"]>) =>
  panel.locator("[data-estimate-ask]");

type ServedStep =
  | { kind: "create_work"; words: string }
  | { kind: "calculate_work"; work_unit_id: string; words: string }
  | { kind: "open_work"; work_unit_id: string; words: string };

/** The refusal the application recorded as `refusal`, in `language`. */
const servedRefusal = (refusal: string, language: Language) =>
  JSON.parse(
    readFileSync(
      new URL(`refusal-${refusal}-${language}.json`, MODELO_FIXTURES),
      "utf8",
    ),
  ) as {
    refusal_words: string;
    context: { key: string; value: string }[];
    next_step: ServedStep;
  };

/** The step the application named on the refusal recorded as `refusal`. */
const servedStep = (refusal: string, language: Language): ServedStep =>
  servedRefusal(refusal, language).next_step;

for (const language of LANGUAGES) {
  test(`credits with no payer record are unresolved and never zero (${language})`, async ({
    page: target,
  }) => {
    const panel = await openCredits(target, "renta", language);
    const credits = await servedCredits(target, language);
    expect(credits.length).toBeGreaterThanOrEqual(3);
    for (const field of credits) {
      const row = panel.locator(`[data-credit="${field.box}"]`);
      await expect(row).toBeVisible();
      await expect(row).toHaveAttribute("data-origin", field.origin);
      // The application's words for why it has no figure, not a figure.
      expect(field.value_text).toBeNull();
      await expect(row).toContainText(field.origin_words!);
      await expect(row.locator("[data-figure]")).toHaveCount(0);
    }
    // The totals that read them have no figure either.
    const dependents = panel.getByRole("region", {
      name: label("desktop.modelo.credits.dependents", {}, language),
    });
    await expect(dependents.locator("[data-credit]").first()).toContainText(
      credits[0]!.origin_words!,
    );
    await expect(dependents.locator("[data-figure]")).toHaveCount(0);
    // No box is typed into.
    await expect(panel.getByRole("textbox")).toHaveCount(0);
    await expect(panel.getByRole("spinbutton")).toHaveCount(0);
  });
}

test("the boxes worked out from the credits are the ones the application served", async ({
  page: target,
}) => {
  const panel = await openCredits(target, "renta");
  const { credits, dependents } = await servedCreditBoxes(target, "en");
  expect(credits.length).toBeGreaterThan(0);
  expect(dependents).not.toBeNull();
  expect(dependents!.length).toBeGreaterThan(0);
  const region = panel.getByRole("region", {
    name: label("desktop.modelo.credits.dependents"),
  });
  // Exactly the served boxes, in the order the form draws them, and none of
  // them is a credit itself.
  await expect(region.locator("[data-credit]")).toHaveCount(dependents!.length);
  for (const [at, field] of dependents!.entries()) {
    await expect(region.locator("[data-credit]").nth(at)).toHaveAttribute(
      "data-credit",
      field.box!,
    );
    expect(credits.map((credit) => credit.box)).not.toContain(field.box);
  }
});

test("a credit from the register shows the figure the application served", async ({
  page: target,
}) => {
  const panel = await openCredits(target, "renta-pay");
  const credits = await servedCredits(target, "en");
  const stated = credits.filter((field) => field.value_text !== null);
  expect(stated.length).toBeGreaterThan(0);
  for (const field of stated) {
    const row = panel.locator(`[data-credit="${field.box}"]`);
    await expect(row.locator("[data-figure]")).toHaveText(field.value_text!);
    await expect(row).toHaveAttribute("data-origin", field.origin);
    await expect(row).toContainText(field.origin_words!);
  }
  await expect(panel.getByRole("textbox")).toHaveCount(0);
});

test("the way to the register opens the withholding records", async ({
  page: target,
}) => {
  const panel = await openCredits(target, "renta");
  await panel
    .getByRole("button", {
      name: label("workspace.modelo.surface.open.withholding"),
    })
    .click();
  await expect(target.locator(".ledger-setup-registers")).toBeVisible();
  await expect(
    target.getByRole("tab", {
      name: label("desktop.ledger.registers.area.withholding"),
      exact: true,
    }),
  ).toHaveAttribute("aria-selected", "true");
});

test("a credit's box on the form is shown from the view", async ({
  page: target,
}) => {
  const panel = await openCredits(target, "renta");
  const credits = await servedCredits(target, "en");
  const first = credits[0]!;
  await panel
    .locator(`[data-credit="${first.box}"]`)
    .getByRole("button", {
      name: label("desktop.modelo.credits.show_box", { box: first.box! }),
    })
    .click();
  await expect(
    workspace(target).getByRole("tab", {
      name: new RegExp(`^${label("desktop.modelo.view.form")}`),
    }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    workspace(target).locator(`[data-key="c:${first.box}"]`),
  ).toHaveAttribute("aria-selected", "true");
});

for (const language of LANGUAGES) {
  test(`with no work income stated the estimate is refused in words naming the boxes it cannot work out (${language})`, async ({
    page: target,
  }) => {
    // No payer certificate is in the register, so the work income the annual
    // return reads has no figure and the application refuses the estimate.
    const panel = await openCredits(target, "renta-projected", language);
    const section = panel.locator("[data-estimate]");
    // It is an estimate before it is anything else.
    await expect(section).toContainText(
      label("desktop.modelo.credits.estimate.mark", {}, language),
    );
    await ask(panel).click();
    const served = servedRefusal("project-100-0A-projected", language);
    await expect(section.getByRole("status")).toHaveText(served.refusal_words);
    // The boxes are named in the sentence, as the application served them.
    const boxes = served.context.find((entry) => entry.key === "boxes")?.value;
    expect(boxes).toBeTruthy();
    expect(served.refusal_words).toContain(boxes!);
    // No step is served, so none is offered, and no estimate is drawn.
    expect(served.next_step).toBeNull();
    await expect(section.locator("[data-estimate-step]")).toHaveCount(0);
    await expect(section.locator("[data-estimate-result]")).toHaveCount(0);
    // The generic failure it replaces is never shown.
    await expect(section.getByRole("status")).not.toHaveText(
      label("desktop.modelo.credits.estimate.refused", {}, language),
    );
    await expect(panel.getByRole("textbox")).toHaveCount(0);
  });
}

test("the estimate gives the register's credit and leaves nothing unresolved", async ({
  page: target,
}) => {
  const panel = await openCredits(target, "renta-credited");
  await ask(panel).click();
  const result = panel.locator("[data-estimate-result]");
  await expect(result).toBeVisible();
  const served = await servedEstimate(target, "en");
  expect(served.unresolved_bindings).toHaveLength(0);
  expect(served.unresolved_casillas).toHaveLength(0);
  await expect(result.locator("[data-unresolved-credit]")).toHaveCount(0);
  await expect(result.locator("[data-unresolved-box]")).toHaveCount(0);
  await expect(result).toContainText(
    label("desktop.modelo.credits.estimate.nothing_left"),
  );
  // The result box carries the estimate's figure, and each credit the one it
  // states there.
  await expect(result.locator("[data-estimate-box]").first()).toBeVisible();
  const credits = await servedCredits(target, "en");
  for (const field of credits) {
    const seen = served.casilla_observations.find(
      (row) => row.casilla_id === field.box,
    );
    if (seen)
      await expect(
        panel.locator(`[data-credit="${field.box}"] [data-in-estimate]`),
      ).toBeVisible();
  }
});

for (const language of LANGUAGES) {
  test(`a profile with no quarterly declaration is refused in the application's words (${language})`, async ({
    page: target,
  }) => {
    const panel = await openCredits(target, "renta", language);
    await ask(panel).click();
    const section = panel.locator("[data-estimate]");
    await expect(section.getByRole("status")).toContainText(
      refusalWords(language),
    );
    // The sentence names no command: the way to put it right is served as an
    // action, not written into the words.
    expect(refusalWords(language)).not.toMatch(/aeat|`/i);
    await expect(section.locator("[data-estimate-result]")).toHaveCount(0);
  });
}

for (const language of LANGUAGES) {
  test(`a refusal for want of a quarter offers creating it in the application's words (${language})`, async ({
    page: target,
  }) => {
    const panel = await openCredits(target, "renta", language);
    await ask(panel).click();
    const section = panel.locator("[data-estimate]");
    const served = servedStep("project-no-quarters", language);
    expect(served.kind).toBe("create_work");
    const step = section.locator("[data-estimate-step=create_work]");
    await expect(step).toHaveText(served.words);
    // The words name no command and no action identifier.
    expect(served.words).not.toMatch(/operator\.|`|--/);
    await expect(section.locator("[data-estimate-result]")).toHaveCount(0);
  });
}

test("choosing the offered steps creates the quarter, calculates it, and offers the estimate again", async ({
  page: target,
}) => {
  const panel = await openCredits(target, "renta");
  const section = panel.locator("[data-estimate]");
  // Nothing exists yet: the creation is offered.
  await ask(panel).click();
  await expect(section.getByRole("status")).toContainText(refusalWords("en"));
  await section.locator("[data-estimate-step=create_work]").click();
  // The step ran; the refusal is gone and the estimate is asked for again.
  await expect(section.locator("[data-estimate-step]")).toHaveCount(0);
  await expect(section.getByRole("status")).toHaveCount(0);
  await expect(ask(panel)).toBeEnabled();
  // The quarter exists but is not calculated: its calculation is offered.
  await ask(panel).click();
  const calculation = servedStep("project-no-calculation", "en");
  expect(calculation.kind).toBe("calculate_work");
  const calculate = section.locator("[data-estimate-step=calculate_work]");
  await expect(calculate).toHaveText(calculation.words);
  await calculate.click();
  await expect(section.locator("[data-estimate-step]")).toHaveCount(0);
  await expect(ask(panel)).toBeEnabled();
  // The quarter is calculated without the answers it refuses without: the
  // application names the boxes it cannot work out and offers opening it.
  await ask(panel).click();
  const incomplete = servedRefusal("project-quarter-incomplete", "en");
  await expect(section.getByRole("status")).toContainText(
    incomplete.refusal_words,
  );
  expect(incomplete.next_step.kind).toBe("open_work");
  const open = section.locator("[data-estimate-step=open_work]");
  await expect(open).toHaveText(incomplete.next_step.words);
  await expect(section.locator("[data-estimate-result]")).toHaveCount(0);
  // Opening it leaves the Modelo 100 for the quarter the step names, whose
  // own form is read.
  await open.click();
  await expect(
    workspace(target).getByRole("heading", { level: 1 }),
  ).toBeVisible();
  await expect(workspace(target).locator("[data-estimate]")).toHaveCount(0);
});

for (const language of LANGUAGES) {
  test(`a quarter calculated without its earlier-filing answers is refused in words naming its open boxes, and opening it is offered (${language})`, async ({
    page: target,
  }) => {
    const panel = await openCredits(target, "renta", language);
    const section = panel.locator("[data-estimate]");
    await ask(panel).click();
    await section.locator("[data-estimate-step=create_work]").click();
    await expect(ask(panel)).toBeEnabled();
    await ask(panel).click();
    await section.locator("[data-estimate-step=calculate_work]").click();
    await expect(ask(panel)).toBeEnabled();
    await ask(panel).click();
    const served = servedRefusal("project-quarter-incomplete", language);
    // The sentence and the step are the application's, in this language.
    await expect(section.getByRole("status")).toHaveText(served.refusal_words);
    expect(served.next_step.kind).toBe("open_work");
    await expect(section.locator("[data-estimate-step=open_work]")).toHaveText(
      served.next_step.words,
    );
    // The open boxes are named in the sentence, never by an amount, and the
    // words name no command or action identifier.
    expect(
      served.context.find((entry) => entry.key === "inputs")?.value,
    ).toBeTruthy();
    expect(served.refusal_words).not.toMatch(/operator\.|`|--/);
    expect(served.next_step.words).not.toMatch(/operator\.|`|--/);
    // The generic failure it replaces is never shown.
    await expect(section.getByRole("status")).not.toHaveText(
      label("desktop.modelo.credits.estimate.refused", {}, language),
    );
    await expect(section.locator("[data-estimate-result]")).toHaveCount(0);
  });
}
