import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import type {
  ModeloProjectOperationProjection,
  PublicModeloFormField,
} from "../../src/shell/modeloContract";
import { label } from "../support/strings";

// The withholdings view of the 2025 Modelo 100: the boxes the withholding
// register supplies, as the application served them, the way to the register
// and the estimate from the quarterly declarations. Every figure and every
// sentence below is read from the scenario's modelo port, which answers the
// envelopes the application read; the window words only its own frame.

const LANGUAGES = ["en", "es", "ca", "hu"] as const;
type Language = (typeof LANGUAGES)[number];
const YEAR = 2025;

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
  await expect(
    panel.getByRole("heading", {
      name: label("desktop.modelo.credits.title", {}, language),
    }),
  ).toBeVisible();
  return panel;
}

/** The boxes the withholding register supplies, as the form served them. */
async function servedCredits(
  target: Page,
  language: Language,
): Promise<PublicModeloFormField[]> {
  return target.evaluate(async (asked) => {
    const port = window.__fixtureModelo!;
    const list = await port.declarations(asked);
    const unit = list.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!.existing!.work_unit_id;
    const read = await port.form(unit, asked);
    const found: PublicModeloFormField[] = [];
    const walk = (node: unknown): void => {
      if (Array.isArray(node)) node.forEach(walk);
      else if (node && typeof node === "object") {
        if ("held_zero" in node && "edit_address" in node) {
          const field = node as PublicModeloFormField;
          if (field.bindings.some((b) => b.policy.surface === "withholding"))
            found.push(field);
        }
        Object.values(node).forEach(walk);
      }
    };
    walk(read.form.form.pages);
    return found;
  }, language);
}

/** The estimate the application answered for the filer's profile. */
async function servedEstimate(
  target: Page,
  language: Language,
): Promise<ModeloProjectOperationProjection> {
  return target.evaluate(
    async ([asked, year]) => {
      const port = window.__fixtureModelo!;
      // The estimate is worded in the language the form was last read in.
      const list = await port.declarations(asked);
      const unit = list.creation_targets.find(
        (entry) => entry.modelo === "100" && entry.existing,
      )!.existing!.work_unit_id;
      await port.form(unit, asked);
      const outcome = await port.submit("modelo.project", {
        year: Number(year),
      });
      if (outcome.kind !== "settled") throw new Error("the estimate refused");
      return outcome.result;
    },
    [language, YEAR] as const,
  );
}

const refusalWords = (language: Language) =>
  (
    JSON.parse(
      readFileSync(
        new URL(
          `../../src/dev/fixtures/modelo/refusal-project-no-quarters-${language}.json`,
          import.meta.url,
        ),
        "utf8",
      ),
    ) as { refusal_words: string }
  ).refusal_words;

const ask = (panel: ReturnType<Page["locator"]>) =>
  panel.locator("[data-estimate-ask]");

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
  test(`the estimate leaves an unresolved credit and its totals without a figure (${language})`, async ({
    page: target,
  }) => {
    const panel = await openCredits(target, "renta-projected", language);
    const section = panel.locator("[data-estimate]");
    // It is an estimate before it is anything else.
    await expect(section).toContainText(
      label("desktop.modelo.credits.estimate.mark", {}, language),
    );
    await expect(section.locator("[data-estimate-result]")).toHaveCount(0);
    await ask(panel).click();
    const result = section.locator("[data-estimate-result]");
    await expect(result).toBeVisible();
    const served = await servedEstimate(target, language);
    expect(served.unresolved_bindings.length).toBeGreaterThan(0);
    expect(served.unresolved_casillas.length).toBeGreaterThan(0);
    // Every explanation is the application's own words.
    for (const row of served.unresolved_bindings) {
      const line = result.locator(
        `[data-unresolved-credit="${row.casilla_id}"]`,
      );
      await expect(line).toContainText(row.words);
      if (row.source_words) await expect(line).toContainText(row.source_words);
    }
    for (const row of served.unresolved_casillas) {
      await expect(
        result.locator(`[data-unresolved-box="${row.casilla_id}"]`),
      ).toBeVisible();
      await expect(result).toContainText(row.reason_words);
    }
    // A box left without a figure is given none in the estimate.
    for (const row of served.unresolved_casillas)
      expect(
        served.casilla_observations.some(
          (seen) => seen.casilla_id === row.casilla_id,
        ),
      ).toBe(false);
    await expect(result.locator("[data-estimate-box]")).toHaveCount(0);
    // Each figure carries the name the application served for it.
    for (const [group, figures] of [
      ["quarterly", served.m130_accumulated],
      ["annual", served.m100_projection],
    ] as const)
      for (const [name, words] of Object.entries(figures.words))
        await expect(
          result.locator(`[data-estimate-figure="${group}.${name}"]`),
        ).toContainText(words);
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
