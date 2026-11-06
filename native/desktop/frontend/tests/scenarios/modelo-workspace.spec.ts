import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import type { ModeloWorkbenchFormProjectionV1 } from "../../src/shell/modeloContract/modeloWorkForm";
import { label } from "../support/strings";
import { MODELO_FIXTURES } from "../support/windowFixtures";

// One declaration's workspace over the scenario's modelo family, which
// answers the forms the application read for a synthetic taxpayer: the
// header, the next action, the Check lines and the source groups are the
// read model's. The window routes the next action to a view, opens a box
// from a finding or a source, says why a declaration cannot be changed, and
// says an operation whose settlement was not seen is unknown.
// The rules-incomplete banner is shown by the stories: the list does not
// open the scenario's 390, which its read model says could not be read.

const workspace = (target: Page) => target.locator(".declarations-workspace");
const tab = (target: Page, key: string) =>
  workspace(target).getByRole("tab", { name: new RegExp(`^${label(key)}`) });

async function openDeclaration(target: Page, modelo: string, shape = "") {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off${shape ? `&modelo=${shape}` : ""}`,
  );
  await target.locator("[data-rail=declarations]").click();
  const rows = target
    .locator(".declarations-page")
    .getByRole("grid")
    .locator("[data-kind=data]");
  await rows
    .filter({ hasText: `Modelo ${modelo}` })
    .first()
    .dblclick();
  await expect(
    workspace(target).getByRole("heading", { level: 1 }),
  ).toBeVisible();
}

test("the header states the read model's result, deadline and next action", async ({
  page: target,
}) => {
  const served = JSON.parse(
    readFileSync(new URL("modelo-130-1T-en.json", MODELO_FIXTURES), "utf8"),
  ) as ModeloWorkbenchFormProjectionV1;
  await openDeclaration(target, "130");
  const header = workspace(target).locator("header").first();
  await expect(header).toContainText("Result: could not be calculated");
  await expect(header).toContainText(served.header.deadline!.text);
  // The quarter's earlier-filing answers are still to be given, so filling them in comes first.
  await expect(
    header.getByRole("button", {
      name: label("workspace.modelo.next_button.fill"),
    }),
  ).toBeVisible();
  // What blocks filing is counted on the Check tab, in words for the reader.
  await expect(
    tab(target, "workspace.modelo.step.review").getByRole("img", {
      name: /blocking: \d+/,
    }),
  ).toBeVisible();
});

test("resolving opens the check's lines, and a line opens its box", async ({
  page: target,
}) => {
  // Checked again after its box 06 was typed over the ledger's figure: what blocks filing is that divergence.
  await openDeclaration(target, "130", "stale");
  await workspace(target)
    .getByRole("button", {
      name: label("workspace.modelo.next_button.resolve"),
    })
    .click();
  await expect(tab(target, "workspace.modelo.step.review")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  const blocks = workspace(target).getByRole("region", {
    name: label("workspace.modelo.level.blocks"),
  });
  await expect(blocks).toContainText("Two sources hold different values");
  await blocks
    .getByRole("button")
    .filter({ has: target.getByText("06", { exact: true }) })
    .click();
  await expect(tab(target, "desktop.modelo.view.form")).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("a source group's box opens it in the form", async ({ page: target }) => {
  await openDeclaration(target, "130");
  await tab(target, "workspace.modelo.key.sources").click();
  await expect(
    workspace(target).getByRole("heading", {
      name: label("workspace.modelo.sources.title"),
    }),
  ).toBeVisible();
  await workspace(target)
    .getByRole("button", {
      name: label("workspace.modelo.sources.go_to_box", { box: "03" }),
    })
    .click();
  await expect(tab(target, "desktop.modelo.view.form")).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("a declaration recorded as filed is read only and offers a correction", async ({
  page: target,
}) => {
  await openDeclaration(target, "130", "filed");
  await expect(workspace(target).getByRole("status").first()).toContainText(
    label("workspace.modelo.filed.read_only"),
  );
  await workspace(target)
    .getByRole("button", { name: label("workspace.modelo.correction.title") })
    .first()
    .click();
  // The correction opens over the History view.
  const correction = target.getByRole("dialog");
  await expect(correction).toContainText(
    label("workspace.modelo.correction.lead"),
  );
  await correction
    .getByRole("button", { name: label("workspace.modelo.editor.cancel") })
    .click();
  await expect(tab(target, "workspace.modelo.history.title")).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("a calculation whose settlement was not seen is unknown and holds", async ({
  page: target,
}) => {
  await openDeclaration(target, "303", "unknown");
  const calculate = workspace(target).getByRole("button", {
    name: label("workspace.modelo.next_button.calculate"),
  });
  await calculate.click();
  // Values nobody is recorded as having typed here are at risk: it asks.
  const proceed = target.getByRole("button", {
    name: label("workspace.modelo.calculate.at_risk_proceed"),
  });
  if (await proceed.isVisible()) await proceed.click();
  // The form asks the 303's calculation evidence first; it is answered so
  // the calculation is sent.
  const evidence = target.getByRole("dialog", {
    name: label("workspace.modelo.calculate.evidence.title"),
  });
  await expect(evidence).toBeVisible();
  await evidence
    .getByRole("radio", {
      name: label("workspace.modelo.calculate.evidence.no"),
    })
    .click();
  await evidence
    .getByRole("button", {
      name: label("workspace.modelo.calculate.evidence.calculate"),
    })
    .click();
  const alert = workspace(target)
    .getByRole("alert")
    .filter({
      hasText: label("workspace.modelo.write_hold.unknown"),
    });
  await expect(alert).toBeVisible();
  await expect(
    alert.getByRole("button", {
      name: label("workspace.modelo.write_hold.check_status"),
    }),
  ).toBeVisible();
});

test("what the calculation noted about a box is said beside it, at its level", async ({
  page: target,
}) => {
  const read = JSON.parse(
    readFileSync(
      new URL("modelo-130-1T-income-en.json", MODELO_FIXTURES),
      "utf8",
    ),
  ) as ModeloWorkbenchFormProjectionV1;
  const noted = read.issue_lines.find(
    (line) =>
      line.from_calculation &&
      line.address?.kind === "casilla" &&
      !line.in_records,
  )!;
  const casilla =
    noted.address?.kind === "casilla" ? noted.address.casilla_id : "";
  await openDeclaration(target, "130", "income");
  await tab(target, "desktop.modelo.view.form").click();
  const notes = workspace(target)
    .locator(`[data-key="c:${casilla}"]`)
    .getByRole("list", { name: label("desktop.modelo.box_notes.label") });
  await expect(notes).toContainText(noted.message);
  await expect(notes).toContainText(
    label(`workspace.modelo.level.${noted.level}`),
  );
  // The check lists the same note at its level.
  await tab(target, "workspace.modelo.step.review").click();
  await expect(
    workspace(target)
      .getByRole("region", {
        name: label(`workspace.modelo.level.${noted.level}`),
      })
      .getByText(noted.message, { exact: true }),
  ).toBeVisible();
});

// The navigator beside a long form: the outline the read model served, its
// counts, and the jump to a section. The served envelope is read through the
// scenario's own modelo port, as the window reads it.

/** The Modelo 100 of the scenario's synthetic filer, as served in English. */
async function servedRenta(target: Page) {
  return target.evaluate(async () => {
    const port = window.__fixtureModelo!;
    const list = await port.declarations("en");
    const unit = list.creation_targets.find(
      (entry) => entry.modelo === "100" && entry.existing,
    )!.existing!.work_unit_id;
    return port.form(unit, "en");
  });
}

/** Opens the filer's 2025 Modelo 100 the way the list offers it: its row
 * opens no local work, so the new-declaration dialog opens the one that
 * exists. */
async function openRenta(target: Page) {
  await target.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=renta",
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
  // The Modelo 100's form is one large read; it takes a while to arrive.
  await expect(
    workspace(target).getByRole("heading", { level: 1 }),
  ).toBeVisible({ timeout: 30_000 });
}

async function openOutline(target: Page) {
  await target
    .getByRole("tab", { name: label("desktop.modelo.side.outline") })
    .click();
  const tree = workspace(target).getByRole("tree", {
    name: label("desktop.modelo.outline.label"),
  });
  await expect(tree).toBeVisible();
  return tree;
}

test("the outline navigator jumps to a section of a long form", async ({
  page: target,
}) => {
  await openRenta(target);
  const tree = await openOutline(target);
  const read = await servedRenta(target);
  const form = read.form.form;
  // A section on another page than the one first shown.
  const page = form.pages.find(
    (candidate, index) =>
      index > 0 && candidate.sections.some((s) => s.applies !== false),
  )!;
  const section = page.sections.find((s) => s.applies !== false)!;
  const item = tree.locator(`[data-outline-section="${section.id}"]`);
  await item.click();
  await expect(item).toHaveAttribute("aria-current", "location");
  await expect(
    workspace(target).getByRole("tab", {
      name: new RegExp(`^${page.heading.text}`),
    }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    workspace(target).locator(`[id="section-${section.id}"]`),
  ).toBeInViewport();
  // The keyboard reaches the next section and jumps to it the same way.
  await item.press("ArrowDown");
  const next = tree.locator("[role=treeitem]:focus");
  await next.press("Enter");
  const nextId = await next.getAttribute("data-outline-section");
  if (nextId)
    await expect(
      workspace(target).locator(`[id="section-${nextId}"]`),
    ).toBeInViewport();
});

test("the outline's counts and applicability are the served ones", async ({
  page: target,
}) => {
  await openRenta(target);
  const tree = await openOutline(target);
  const read = await servedRenta(target);
  const groups = tree.locator("[data-outline-group]");
  await expect(groups).toHaveCount(read.form.form.outline.length);
  for (const group of read.form.form.outline) {
    const item = tree.locator(`[data-outline-group="${group.id}"]`);
    const row = item;
    await expect(row).toContainText(group.heading.text);
    await expect(item).toHaveAttribute("data-applies", String(group.applies));
    const needs = row.locator("[data-mark=needs_you]");
    const failed = row.locator("[data-mark=could_not_calculate]");
    if (group.applies !== false && group.counts.needs_you > 0) {
      await expect(needs).toHaveText(String(group.counts.needs_you));
      await expect(item).toHaveAccessibleName(
        new RegExp(
          label("desktop.modelo.outline.needs_you", {
            count: group.counts.needs_you,
          }),
        ),
      );
    } else await expect(needs).toHaveCount(0);
    if (group.applies !== false && group.counts.could_not_calculate > 0)
      await expect(failed).toHaveText(String(group.counts.could_not_calculate));
    else await expect(failed).toHaveCount(0);
  }
});

test("the lists kept apart from the pages are reached through the outline", async ({
  page: target,
}) => {
  await openRenta(target);
  const tree = await openOutline(target);
  const read = await servedRenta(target);
  const apart = read.form.form.outline.filter(
    (group) => group.kind !== "sections",
  );
  expect(apart.map((group) => group.kind).sort()).toEqual([
    "answers",
    "unplaced",
    "working_figures",
  ]);
  for (const group of apart) {
    const item = tree.locator(`[data-outline-group="${group.id}"]`);
    await item.click();
    await expect(item).toHaveAttribute("aria-current", "location");
    await expect(
      workspace(target).getByRole("tab", {
        name: new RegExp(`^${group.heading.text}`),
      }),
    ).toHaveAttribute("aria-selected", "true");
  }
});

test("withholding credit 0596 routes from the form to the register", async ({
  page: target,
}) => {
  await openRenta(target);
  const tree = await openOutline(target);
  const read = await servedRenta(target);
  const holder = read.form.form.pages
    .flatMap((page) => page.sections)
    .find((section) =>
      JSON.stringify(section.blocks).includes('"box":"0596"'),
    )!;
  await tree.locator(`[data-outline-section="${holder.id}"]`).click();
  const row = workspace(target).locator('[data-key="c:0596"]');
  await expect(row).toBeVisible();
  // The credit is never typed into here: it is corrected in the register.
  await expect(row.getByRole("textbox")).toHaveCount(0);
  await row
    .getByRole("button", {
      name: label("workspace.modelo.surface.correct.withholding"),
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
