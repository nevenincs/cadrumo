import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { label } from "../support/strings";

// The Ledger page's Setup sections over the scenario host's made-up ledger:
// a rule made from a selection and its run staged, ratios by year, an own
// account added through the protected body and shown masked only, an
// account closed on a date it asks for, a prorrata election the register
// refuses until its reference is given, an inventory valuation preview, a
// readiness reason that opens the movements it names, and a reset whose
// dry run the sealed declarations block.

const engine = readFileSync(
  fileURLToPath(
    new URL("../../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);

/** A valid Spanish IBAN, made up: the check digits are right. */
const IBAN = "ES9121000418450200051332";

const head = (target: Page) => target.locator(".pane-docs .pane-head");
const page = (target: Page) => target.locator(".ledger-page");
const dataRows = (target: Page) =>
  page(target).getByRole("grid").locator("[data-kind=data]");
const button = (scope: Page | Locator, key: string, values = {}) =>
  scope.getByRole("button", { name: label(key, values), exact: true });
const field = (scope: Page | Locator, key: string, values = {}) =>
  scope.getByLabel(label(key, values), { exact: true });

async function openLedger(target: Page, scheme?: "light" | "dark") {
  if (scheme)
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(page(target).getByRole("grid")).toBeVisible();
}

async function openSetup(
  target: Page,
  section: "rules" | "registers" | "health",
) {
  await head(target).locator(".ledger-setup").click();
  await target
    .getByRole("menuitem", { name: label(`desktop.ledger.section.${section}`) })
    .click();
  await expect(target.locator(`.ledger-setup-${section}`)).toBeVisible();
  // The menu has closed and given the page back.
  await expect(target.getByRole("menu")).toHaveCount(0);
}

async function area(target: Page, key: string) {
  await target.getByRole("tab", { name: label(key), exact: true }).click();
}

async function audit(target: Page) {
  await target.evaluate(engine);
  return target.evaluate(async () => {
    const axe = (
      window as unknown as {
        axe: {
          run(
            context: unknown,
            options: unknown,
          ): Promise<{
            violations: { id: string; nodes: { target: string[] }[] }[];
          }>;
        };
      }
    ).axe;
    const result = await axe.run(
      { exclude: [[".docs-frame"], [".xterm"]] },
      { resultTypes: ["violations"] },
    );
    return result.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.map((node) => node.target.join(" ")),
    }));
  });
}

test("a rule made from a selection is prefilled, saved, and its run staged", async ({
  page: target,
}) => {
  await openLedger(target);
  // Two payments to one supplier, one still to classify.
  for (const invoice of ["FRA 2026-058", "FRA 2026-055"])
    await dataRows(target)
      .filter({ hasText: invoice })
      .locator("input[type=checkbox]")
      .click();
  await page(target).focus();
  await target.keyboard.press("Control+KeyK");
  const palette = target.locator(".palette");
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.ledger.rules.from_selection"));
  await target.keyboard.press("Enter");

  const dialog = target.getByRole("dialog", {
    name: label("desktop.ledger.rules.new_title"),
  });
  await expect(dialog).toBeVisible();
  // The words both descriptions share, without the invoice numbers; no
  // classification is chosen where they disagree.
  await expect(field(dialog, "desktop.ledger.rules.words")).toHaveValue(
    "TRANSFERENCIA COOPERATIVA OLIVAR DEL SUR FRA",
  );
  await expect(
    field(dialog, "desktop.ledger.rules.classification"),
  ).toHaveValue("");
  await expect(dialog.locator(".ledger-rule-matches")).toContainText(
    label("desktop.ledger.rules.matches", { count: 1 }),
  );
  // Saving waits for a classification.
  const save = button(dialog, "desktop.ledger.rules.save");
  await expect(save).toHaveAttribute("aria-disabled", "true");
  await field(dialog, "desktop.ledger.rules.classification").selectOption(
    "BUSINESS",
  );
  await field(dialog, "desktop.ledger.rules.category").selectOption(
    "suministros_cliente_directos",
  );
  await dialog
    .getByLabel(label("desktop.ledger.rules.classify_now"), { exact: true })
    .check();
  await save.click();
  await expect(dialog).toBeHidden();

  // The rule is stored and named by what it matches; running it is
  // staged, and the movement is still to classify until it is saved.
  await openSetup(target, "rules");
  const rules = target.locator(".ledger-rules-table");
  await expect(rules).toContainText(
    label("desktop.ledger.rules.contains", {
      words: "TRANSFERENCIA COOPERATIVA OLIVAR DEL SUR FRA",
    }),
  );
  await expect(target.locator(".ledger-rules-staged")).toContainText(
    label("desktop.ledger.rules.run_staged", { count: 1 }),
  );
});

test("a dry run of the rules says what they would classify and stages the run", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "rules");
  await button(target, "desktop.ledger.rules.preview").click();
  const preview = target.locator(".ledger-rules-dry-run");
  await expect(preview).toBeVisible();
  await expect(preview).toContainText(
    label("desktop.ledger.rules.contains", {
      words: "COMISION MANTENIMIENTO",
    }),
  );
  await button(target, "desktop.ledger.rules.stage_run").click();
  await expect(target.locator(".ledger-rules-staged")).toBeVisible();
  await expect(preview).toBeHidden();
});

test("a rule moves in the order with the writes that put it there", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "rules");
  const rows = target.locator(".ledger-rules-table tbody tr");
  await expect(rows).toHaveCount(3);
  const last = label("desktop.ledger.rules.contains", {
    words: "COMISION MANTENIMIENTO",
  });
  await expect(rows.nth(2)).toContainText(last);
  await button(target, "desktop.ledger.rules.move_up", { rule: last }).click();
  await expect(rows.nth(1)).toContainText(last);
});

test("ratios are set and unset for the year chosen", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "rules");
  await area(target, "desktop.ledger.rules.area.ratios");
  const category = label(
    "desktop.ledger.category.suministros_home_office_internet",
  );
  const table = target.locator(".ledger-ratios-table");
  await expect(table).toBeVisible();
  await target
    .getByRole("button", {
      name: `${label("desktop.ledger.ratios.set")} ${category}`,
      exact: true,
    })
    .click();
  const input = target.getByLabel(
    label("desktop.ledger.ratios.input", { category }),
  );
  // A fraction is refused: 0.4 could be 40% or 0.4%.
  await input.fill("0.4");
  await input.press("Enter");
  await expect(target.getByRole("alert").first()).toBeVisible();
  await input.fill("40");
  await input.press("Enter");
  const row = table.locator("tr", { hasText: category });
  await expect(row).toContainText("40%");

  // Another year: the selector reads the year's ratios.
  await target
    .getByRole("group", { name: label("desktop.ledger.ratios.year") })
    .getByRole("button", {
      name: label("desktop.ledger.period.year_previous"),
      exact: true,
    })
    .click();
  await expect(
    target.getByRole("group", {
      name: label("desktop.ledger.ratios.table", { year: 2025 }),
    }),
  ).toBeVisible();
  await target
    .getByRole("button", {
      name: `${label("desktop.ledger.ratios.unset")} ${category}`,
      exact: true,
    })
    .click();
  await expect(row).toContainText(label("desktop.ledger.ratios.not_set"));
});

test("an own account is added through the protected body and shown masked only", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "registers");
  await button(target, "desktop.ledger.accounts.add").first().click();
  const form = target.locator(".ledger-account-form");
  await field(form, "desktop.ledger.accounts.label").fill("Cuenta de ahorro");
  await field(form, "desktop.ledger.accounts.holding_label").selectOption(
    "titular",
  );
  await field(form, "desktop.ledger.accounts.currency").fill("EUR");
  await field(form, "desktop.ledger.accounts.opened").fill("2026-02-01");
  const number = field(form, "desktop.ledger.accounts.iban");
  await expect(number).toHaveAttribute("type", "password");
  // A wrong check digit is caught before anything is sent.
  await number.fill(IBAN.replace("91", "92"));
  await expect(form).toContainText(
    label("desktop.ledger.accounts.iban_problem.check"),
  );
  await number.fill(IBAN);
  await button(form, "desktop.ledger.accounts.submit.add").click();
  await expect(form).toBeHidden();

  const table = target.locator(".ledger-accounts-table");
  const added = table.locator("tr", { hasText: "Cuenta de ahorro" });
  await expect(added).toContainText("ES**1332");
  // The number is nowhere in the window: not in the page, not in a field,
  // not in its storage.
  const held = await target.evaluate(
    (iban) => ({
      page: document.documentElement.outerHTML.includes(iban),
      fields: [...document.querySelectorAll("input, textarea")].some((input) =>
        (input as HTMLInputElement).value.includes(iban),
      ),
      storage: [localStorage, sessionStorage].some((store) =>
        Object.keys(store).some((key) =>
          (store.getItem(key) ?? "").includes(iban),
        ),
      ),
    }),
    IBAN,
  );
  expect(held).toEqual({ page: false, fields: false, storage: false });
});

test("an account closes on a date the person gives, and one in use is not removed", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "registers");
  const actions = (account: string) =>
    target.getByRole("button", {
      name: label("desktop.ledger.accounts.actions", { account }),
    });
  await actions("Cuenta personal").click();
  await target
    .getByRole("menuitem", { name: label("desktop.ledger.accounts.close") })
    .click();
  const form = target.locator(".ledger-account-form");
  const submit = button(form, "desktop.ledger.accounts.submit.close");
  // No date is assumed.
  await expect(field(form, "desktop.ledger.accounts.closed_on")).toHaveValue(
    "",
  );
  await expect(submit).toHaveAttribute("aria-disabled", "true");
  await field(form, "desktop.ledger.accounts.closed_on").fill("31/10/2026");
  await expect(submit).toHaveAttribute("aria-disabled", "true");
  await field(form, "desktop.ledger.accounts.closed_on").fill("2026-10-31");
  await submit.click();
  await expect(form).toBeHidden();
  await expect(
    target.locator(".ledger-accounts-table tr", { hasText: "Cuenta personal" }),
  ).toContainText("2026");

  await actions("Cuenta del estudio").click();
  await target
    .getByRole("menuitem", { name: label("desktop.ledger.accounts.remove") })
    .click();
  await expect(target.locator(".setup-call-line")).toContainText(
    label("desktop.ledger.accounts.refused_remove"),
  );
  await expect(
    target.locator(".ledger-accounts-table tr", {
      hasText: "Cuenta del estudio",
    }),
  ).toBeVisible();
});

test("a prorrata election is refused until it names its document", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "registers");
  await area(target, "desktop.ledger.registers.area.prorrata");
  await button(target, "desktop.ledger.prorrata.action.elect_especial").click();
  const form = target.locator(".ledger-prorrata-form");
  await field(form, "desktop.ledger.prorrata.percentage").fill("80");
  await field(form, "desktop.ledger.prorrata.provenance_label").selectOption(
    "aeat_autorizada",
  );
  await form
    .getByRole("button", {
      name: label("desktop.ledger.prorrata.action.elect_especial"),
    })
    .click();
  await expect(target.locator(".setup-call-line")).toContainText(
    label("desktop.ledger.prorrata.refusal.reference_required"),
  );
  await field(form, "desktop.ledger.prorrata.reference").fill("AEAT-2026-0117");
  await form
    .getByRole("button", {
      name: label("desktop.ledger.prorrata.action.elect_especial"),
    })
    .click();
  await expect(form).toBeHidden();
  const row = target.locator(".ledger-prorrata-table tr", { hasText: "2026" });
  await expect(row).toContainText(
    label("desktop.ledger.prorrata.regime.especial"),
  );
  await expect(row).toContainText("80%");

  // A year already in the register is not seeded over.
  await button(target, "desktop.ledger.prorrata.action.seed").click();
  await target
    .locator(".ledger-prorrata-form")
    .getByRole("button", {
      name: label("desktop.ledger.prorrata.action.seed"),
    })
    .click();
  await expect(target.locator(".setup-call-line")).toContainText(
    label("desktop.ledger.prorrata.refusal.seed_existing_blocked"),
  );
});

test("an inventory valuation preview records nothing", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "registers");
  await area(target, "desktop.ledger.registers.area.inventory");
  await button(target, "desktop.ledger.inventory.preview").click();
  const valuation = target.locator(".ledger-inventory-valuation");
  await expect(valuation).toContainText(
    label("desktop.ledger.inventory.valuation", {
      closing: "410.00",
      cogs: "0.00",
      method: label("desktop.ledger.inventory.method.fifo"),
    }),
  );
  await expect(valuation).toContainText(
    label("desktop.ledger.inventory.preview_note"),
  );
});

test("a closing authority or a purchase's cost is read from a file the person picks", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "registers");
  await area(target, "desktop.ledger.registers.area.inventory");
  await button(target, "desktop.ledger.inventory.task.closing").click();
  const record = field(target, "desktop.ledger.inventory.authority");
  const picker = target.locator(".ledger-setup-registers input[type=file]");
  const document = JSON.stringify({ decision: {}, prior_closing_link: {} });
  await picker.setInputFiles({
    name: "cierre.json",
    mimeType: "application/json",
    buffer: Buffer.from(document),
  });
  await expect(record).toHaveValue(document);
  // A file past the bound is not read, and says so; the field keeps its text.
  await picker.setInputFiles({
    name: "grande.json",
    mimeType: "application/json",
    buffer: Buffer.alloc(1024 * 1024 + 1, 0x20),
  });
  await expect(target.locator(".ledger-setup-registers")).toContainText(
    label("desktop.ledger.inventory.authority_file_too_large"),
  );
  await expect(record).toHaveValue(document);

  // Purchase-cost evidence is offered for a purchase alone.
  await button(target, "desktop.ledger.inventory.task.movement").click();
  const cost = field(target, "desktop.ledger.inventory.acquisition");
  await expect(cost).toHaveCount(0);
  await field(target, "desktop.ledger.inventory.kind_label").selectOption(
    "purchase",
  );
  await expect(cost).toBeVisible();
  await field(target, "desktop.ledger.inventory.kind_label").selectOption(
    "cogs",
  );
  await expect(cost).toHaveCount(0);
});

test("what is missing opens the movements each reason names", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "health");
  await button(target, "desktop.ledger.health.check").click();
  const reasons = target.locator(".ledger-health-reasons li");
  await expect(reasons.first()).toBeVisible();
  const first = reasons.first();
  const counted = Number(
    (await first.locator(".tabular-nums").textContent())?.replace(/\D/g, ""),
  );
  await first.locator(".ledger-health-show").click();
  await expect(
    head(target).getByRole("tab", {
      name: new RegExp(`^${label("desktop.ledger.section.movements")}`),
    }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(dataRows(target)).toHaveCount(counted);
});

test("a reset is previewed first and blocked by sealed declarations", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "health");
  const zone = target.locator(".ledger-health-reset");
  const opener = button(zone, "desktop.ledger.health.reset");
  // Folded until asked: nothing of the reset is in the tab order.
  await expect(opener).toHaveAttribute("aria-expanded", "false");
  await expect(field(zone, "desktop.ledger.health.reset_reason")).toBeHidden();
  await opener.click();
  await expect(opener).toHaveAttribute("aria-expanded", "true");
  const dryRun = button(zone, "desktop.ledger.health.dry_run");
  await expect(dryRun).toHaveAttribute("aria-disabled", "true");
  await field(zone, "desktop.ledger.health.reset_reason").fill(
    "Empezar de cero",
  );
  await dryRun.click();
  const blocked = zone.locator(".ledger-health-reset-blocked");
  await expect(blocked).toContainText(
    label("desktop.ledger.health.reset_blocked"),
  );
  await expect(blocked).toContainText("303");
  await expect(zone.locator(".ledger-health-reset-confirm")).toHaveCount(0);
});

for (const scheme of ["light", "dark"] as const)
  test(`the Setup sections pass an accessibility audit in the ${scheme} scheme`, async ({
    page: target,
  }) => {
    await openLedger(target, scheme);
    await openSetup(target, "rules");
    await expect(target.locator(".ledger-rules-table")).toBeVisible();
    expect(await audit(target)).toEqual([]);
    await area(target, "desktop.ledger.rules.area.ratios");
    await expect(target.locator(".ledger-ratios-table")).toBeVisible();
    expect(await audit(target)).toEqual([]);
    await openSetup(target, "registers");
    await expect(target.locator(".ledger-accounts-table")).toBeVisible();
    expect(await audit(target)).toEqual([]);
    await area(target, "desktop.ledger.registers.area.prorrata");
    await expect(target.locator(".ledger-prorrata-table")).toBeVisible();
    expect(await audit(target)).toEqual([]);
    await openSetup(target, "health");
    await expect(target.locator(".ledger-health-status")).toBeVisible();
    expect(await audit(target)).toEqual([]);
  });
