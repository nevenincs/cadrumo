import { expect, test, type Page } from "@playwright/test";
import type {
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../../src/shell/modeloContract/modeloWorkForm";
import { label } from "../support/strings";

// Two journeys through the Modelo 100 workspace, each from the declarations
// list to the result and to the withholding register: a salaried filer whose
// payer certificate is in the register, and a self-employed filer whose
// activity income the ledger books and whose register holds no certificate.
// Every figure, state and sentence asserted is read from what the scenario's
// modelo port answers, which is what the application read for the filer; the
// window words only its own frame. A withholding box (the ones the form says
// the register supplies) is never typed into on any of the views.

const LANGUAGES = ["en", "es", "ca", "hu"] as const;
type Language = (typeof LANGUAGES)[number];

const workspace = (target: Page) => target.locator(".declarations-workspace");

/** Opens the filer's Modelo 100 the way the list offers it. */
async function openRenta(target: Page, shape: string, language: Language) {
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
  // The Modelo 100's form is one large read; it takes a while to arrive.
  await expect(
    workspace(target).getByRole("heading", { level: 1 }),
  ).toBeVisible({ timeout: 30_000 });
}

/** The form the application served for the filer's declaration. */
async function servedForm(
  target: Page,
  language: Language,
): Promise<ModeloWorkbenchFormProjectionV1> {
  return target.evaluate(async (asked) => {
    const port = window.__fixtureModelo!;
    const list = await port.declarations(asked);
    const unit = list.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!.existing!.work_unit_id;
    return port.form(unit, asked);
  }, language);
}

/** Every box of a served form. */
function boxes(form: ModeloWorkbenchFormProjectionV1): PublicModeloFormField[] {
  const found: PublicModeloFormField[] = [];
  const walk = (node: unknown): void => {
    if (Array.isArray(node)) node.forEach(walk);
    else if (node && typeof node === "object") {
      if ("held_zero" in node && "edit_address" in node)
        found.push(node as PublicModeloFormField);
      Object.values(node).forEach(walk);
    }
  };
  walk(form.form.form.pages);
  return found;
}

/** The boxes the form says the withholding register supplies. */
const registerBoxes = (form: ModeloWorkbenchFormProjectionV1) =>
  boxes(form).filter((field) =>
    field.bindings.some((binding) => binding.policy.surface === "withholding"),
  );

async function openOutline(target: Page, language: Language) {
  await target
    .getByRole("tab", {
      name: label("desktop.modelo.side.outline", {}, language),
    })
    .click();
  const tree = workspace(target).getByRole("tree", {
    name: label("desktop.modelo.outline.label", {}, language),
  });
  await expect(tree).toBeVisible();
  return tree;
}

/** Jumps from the outline to the section that holds `box`. */
async function showBox(
  target: Page,
  form: ModeloWorkbenchFormProjectionV1,
  box: string,
  language: Language,
) {
  const tree = await openOutline(target, language);
  const holder = form.form.form.pages
    .flatMap((page) => page.sections)
    .find((section) =>
      JSON.stringify(section.blocks).includes(`"box":"${box}"`),
    )!;
  await tree.locator(`[data-outline-section="${holder.id}"]`).click();
  const row = workspace(target).locator(`[data-key="c:${box}"]`);
  await expect(row).toBeVisible();
  return row;
}

/** Opens the withholdings view and returns its panel. */
async function openCredits(target: Page, language: Language) {
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

/** Follows the way to the withholding register from a view. */
async function openRegister(
  target: Page,
  scope: ReturnType<Page["locator"]>,
  language: Language,
) {
  await scope
    .getByRole("button", {
      name: label("workspace.modelo.surface.open.withholding", {}, language),
    })
    .click();
  await expect(target.locator(".ledger-setup-registers")).toBeVisible();
  await expect(
    target.getByRole("tab", {
      name: label("desktop.ledger.registers.area.withholding", {}, language),
      exact: true,
    }),
  ).toHaveAttribute("aria-selected", "true");
}

for (const language of LANGUAGES) {
  test(`a salaried filer reaches the result and the register, and types no withholding box (${language})`, async ({
    page: target,
  }) => {
    await openRenta(target, "renta-pay", language);
    const form = await servedForm(target, language);

    // The result: the box the form names, with the figure it served.
    const result = form.form.form.result!;
    expect(result.value).not.toBeNull();
    const resultField = boxes(form).find(
      (field) => field.box === result.casilla_id,
    )!;
    expect(resultField.value_text).not.toBeNull();
    const resultRow = await showBox(target, form, result.casilla_id, language);
    await expect(resultRow).toContainText(resultField.value_text!);

    // The register's boxes are read-only on the form and lead to the register.
    const credits = registerBoxes(form);
    expect(credits.length).toBeGreaterThanOrEqual(3);
    for (const field of credits) {
      const row = await showBox(target, form, field.box!, language);
      await expect(row.getByRole("textbox")).toHaveCount(0);
      await expect(row.getByRole("spinbutton")).toHaveCount(0);
      await expect(
        row.getByRole("button", {
          name: label(
            "workspace.modelo.surface.correct.withholding",
            {},
            language,
          ),
        }),
      ).toBeVisible();
    }

    // The withholdings view states the figure the register supplied.
    const panel = await openCredits(target, language);
    const stated = credits.filter((field) => field.value_text !== null);
    expect(stated.length).toBeGreaterThan(0);
    for (const field of credits) {
      const row = panel.locator(`[data-credit="${field.box}"]`);
      await expect(row).toBeVisible();
      if (field.value_text !== null)
        await expect(row.locator("[data-figure]")).toHaveText(field.value_text);
      else await expect(row.locator("[data-figure]")).toHaveCount(0);
    }
    await expect(panel.getByRole("textbox")).toHaveCount(0);
    await expect(panel.getByRole("spinbutton")).toHaveCount(0);
    await openRegister(target, panel, language);
  });

  test(`a self-employed filer's result stays unresolved, no credit is typed, and the register is the way out (${language})`, async ({
    page: target,
  }) => {
    await openRenta(target, "renta-activity", language);
    const form = await servedForm(target, language);

    // The return could not be worked out: the result has no figure, and the
    // form says why instead of drawing a zero.
    const result = form.form.form.result!;
    expect(result.value).toBeNull();
    const resultField = boxes(form).find(
      (field) => field.box === result.casilla_id,
    )!;
    expect(resultField.value_text).toBeNull();
    const resultRow = await showBox(target, form, result.casilla_id, language);
    await expect(resultRow.locator("[data-figure]")).toHaveCount(0);
    await expect(resultRow).toContainText(resultField.origin_words!);

    // What needs the filer is counted in the outline the form served.
    const tree = await openOutline(target, language);
    const needing = form.form.form.outline.filter(
      (group) => group.applies !== false && group.counts.needs_you > 0,
    );
    expect(needing.length).toBeGreaterThan(0);
    for (const group of needing)
      await expect(
        tree.locator(
          `[data-outline-group="${group.id}"] [data-mark=needs_you]`,
        ),
      ).toHaveText(String(group.counts.needs_you));

    // A credit the register has no figure for is unresolved here, in the
    // application's words and never as a zero; one the register states, even
    // as none, is drawn as the figure it stated with its origin. No box of
    // the view takes a typed value.
    const credits = registerBoxes(form);
    expect(credits.length).toBeGreaterThanOrEqual(3);
    const panel = await openCredits(target, language);
    for (const field of credits) {
      const row = panel.locator(`[data-credit="${field.box}"]`);
      if (field.value_text === null) {
        await expect(row).toContainText(field.origin_words!);
        await expect(row.locator("[data-figure]")).toHaveCount(0);
      } else {
        await expect(row.locator("[data-figure]")).toHaveText(field.value_text);
        await expect(row).toContainText(field.origin_words!);
      }
    }
    await expect(panel.getByRole("textbox")).toHaveCount(0);
    await expect(panel.getByRole("spinbutton")).toHaveCount(0);

    // The estimate from the quarters asks for the first quarter instead of
    // answering with a figure, when the edition projects one at all.
    if (form.form.form.projectable) {
      await panel.locator("[data-estimate-ask]").click();
      await expect(panel.locator("[data-estimate-result]")).toHaveCount(0);
      await expect(
        panel.locator("[data-estimate]").getByRole("status"),
      ).toBeVisible();
    } else await expect(panel.locator("[data-estimate-ask]")).toHaveCount(0);

    // The settlement waits for a result that is not yet known.
    await workspace(target)
      .getByRole("tab", {
        name: label("workspace.modelo.filing.title", {}, language),
      })
      .click();
    const settlement = workspace(target).locator("[data-settlement]");
    await expect(settlement).toBeVisible();
    await expect(settlement.locator("select")).toHaveCount(0);

    await workspace(target)
      .getByRole("tab", {
        name: label("desktop.modelo.view.credits", {}, language),
      })
      .click();
    await openRegister(
      target,
      workspace(target).getByRole("tabpanel"),
      language,
    );
  });
}
