import { expect, test } from "@playwright/test";
import {
  RATIO_ELIGIBLE_FIXTURE,
  ratioWording,
} from "../../src/dev/fixtures/ledgerRatios";
import { label } from "../support/strings";
import {
  page,
  dataRows,
  button,
  field,
  openLedger,
  openSetup,
  area,
} from "../support/ledgerSetup";

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
    label("desktop.ledger.rules.matches_split", { count: 2, pending: 1 }),
  );
  // Saving waits for a classification.
  const save = button(dialog, "desktop.ledger.rules.save");
  await expect(save).toHaveAttribute("aria-disabled", "true");
  await field(dialog, "desktop.ledger.rules.classification").selectOption(
    "BUSINESS",
  );
  // The category is the grouped, searchable list used everywhere else.
  await dialog.locator(".ledger-rule-category button").click();
  const list = target.locator("[data-slot=combobox]");
  await expect(list).toBeVisible();
  await target.keyboard.type(
    label("desktop.ledger.category.suministros_cliente_directos"),
  );
  await target.keyboard.press("Enter");
  await expect(list).toBeHidden();
  await expect(dialog.locator(".ledger-rule-category button")).toHaveText(
    label("desktop.ledger.category.suministros_cliente_directos"),
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
  // The pane names a category by the label the backend serves for it, and
  // explains it by the notes served beside it.
  const served = ratioWording(
    RATIO_ELIGIBLE_FIXTURE.suministros_home_office_internet!,
    "en",
  );
  const category = served.label;
  const table = target.locator(".ledger-ratios-table");
  await expect(table).toBeVisible();
  await expect(table.locator("tr", { hasText: category })).toContainText(
    served.notes,
  );
  await target
    .getByRole("button", {
      name: `${label("desktop.ledger.ratios.set")} ${category}`,
      exact: true,
    })
    .click();
  const input = target.getByLabel(
    label("desktop.ledger.ratios.input", { category }),
  );
  // Typing is in points, so more than a hundred is refused.
  await input.fill("101");
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

test("an unsaved pattern is answered by the backend, and without an answer the save waits", async ({
  page: target,
}) => {
  await openLedger(target);
  await dataRows(target)
    .filter({ hasText: "PAPELERIA TRAZO" })
    .first()
    .locator("input[type=checkbox]")
    .click();
  await page(target).focus();
  await target.keyboard.press("Control+KeyK");
  await target
    .locator(".palette")
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.ledger.rules.from_selection"));
  await target.keyboard.press("Enter");
  const dialog = target.locator(".ledger-rule-dialog");
  await expect(dialog).toBeVisible();
  await dialog
    .getByLabel(label("desktop.ledger.rules.classification"), { exact: true })
    .selectOption("PERSONAL");
  await dialog
    .getByRole("switch", { name: label("desktop.ledger.rules.advanced") })
    .click();
  const expression = field(dialog, "desktop.ledger.rules.expression");
  const save = dialog.locator(".ledger-rule-save");

  await expression.fill("[unclosed");
  await expect(dialog).toContainText(
    label("desktop.ledger.rules.expression_unread"),
  );
  await expect(save).toHaveAttribute("aria-disabled", "true");

  // The fixture has no answer for this one, as a ledger that did not reply.
  await expression.fill("NOT RECORDED");
  await expect(dialog.locator(".ledger-rule-matches")).toContainText(
    label("desktop.ledger.rules.matches_unknown"),
  );
  await expect(save).toHaveAttribute("aria-disabled", "true");
  await expect(expression).toHaveValue("NOT RECORDED");
  // No answer is said, the draft stays, and it can be asked again.
  const failed = dialog.locator(".ledger-rule-trial-failed");
  await expect(failed).toContainText(
    label("desktop.ledger.rules.trial_failed"),
  );
  await failed
    .getByRole("button", { name: label("desktop.ledger.rules.trial_retry") })
    .click();
  await expect(failed).toBeVisible();
  await expect(expression).toHaveValue("NOT RECORDED");

  // The backend's own answers: one that could not compile, one too costly.
  await expression.fill("a{99999999999}");
  await expect(failed).toBeHidden();
  await expect(dialog).toContainText(
    label("desktop.ledger.rules.expression_unread"),
  );
  await expect(save).toHaveAttribute("aria-disabled", "true");
  await expression.fill("(.+)+#");
  await expect(dialog).toContainText(
    label("desktop.ledger.rules.expression_overrun"),
  );
  await expect(save).toHaveAttribute("aria-disabled", "true");

  await expression.fill(String.raw`PAPELERIA\s+TRAZO`);
  await expect(save).not.toHaveAttribute("aria-disabled", "true");
});

/** A valid Spanish IBAN, made up: the check digits are right. */
const IBAN = "ES9121000418450200051332";

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
  // How it is written is seen here; a wrong check digit is the backend's to
  // refuse, and the number goes with the attempt.
  await number.fill("ES91");
  await expect(form).toContainText(
    label("desktop.ledger.accounts.iban_problem.shape"),
  );
  await number.fill(IBAN.replace("91", "92"));
  await button(form, "desktop.ledger.accounts.submit.add").click();
  await expect(
    target.getByText(label("desktop.ledger.accounts.refused")),
  ).toBeVisible();
  await expect(number).toHaveValue("");
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
