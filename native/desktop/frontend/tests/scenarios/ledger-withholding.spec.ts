import { expect, test, type Locator, type Page } from "@playwright/test";
import { windowFixture } from "../support/windowFixtures";
import { readFileSync } from "node:fs";
import { label } from "../support/strings";
import {
  button,
  field,
  openLedger,
  openSetup,
  area,
} from "../support/ledgerSetup";
import { fixtureYear } from "../../src/dev/fixtureDates";

// The Ledger's withholding register: certificates listed, recorded and picked as files, and every refusal said in the backend's words.

/** The sentences the backend serves with every refusal of the withholding
 * record and absence operations, by reason and language, as the generated
 * fixture holds them. */
const REFUSAL_WORDS = JSON.parse(
  readFileSync(
    windowFixture(
      "desktop-withholding-refusal-words",
      "ledgerWithholdingRefusalWords",
    ),
    "utf8",
  ),
) as Record<
  "record" | "absence",
  Record<string, Record<string, { refusal_words: string }>>
>;

const servedWords = (
  operation: "record" | "absence",
  reason: string,
  language = "en",
) => REFUSAL_WORDS[operation][reason]![language]!.refusal_words;

const WITHHOLDING_LANGUAGES = ["en", "es", "ca", "hu"] as const;

/** Opens Setup › Registers › Withholding. */
async function openWithholding(target: Page, shape?: string, language = "en") {
  await openLedger(target, undefined, language, shape);
  await openSetup(target, "registers", language);
  await area(target, "desktop.ledger.registers.area.withholding", language);
  await expect(
    target.locator(".ledger-withholding-class").first(),
  ).toBeVisible();
}

/** The served key of a certificate figure's words. */
const FIGURE =
  "application.ledger.entry_options.withholding_certificate_figure.";

const withholdingForm = (target: Page) =>
  target.locator(".ledger-withholding-form");

/** A made-up payer tax ID, which no real taxpayer holds. */
const PAYER_TAX_ID = "B00010157";

test("the withholding register lists a payer's certificate under its class and reads an empty year as empty", async ({
  page: target,
}) => {
  await openWithholding(target);
  const group = target.locator(".ledger-withholding-class").first();
  // The class is worded as the backend served it, the payer by name, and the
  // figures as the register holds them.
  await expect(group.getByRole("heading")).toHaveText("Employment income");
  const row = group.locator(".ledger-withholding-table tr", {
    hasText: "Empresa Ejemplo SL",
  });
  await expect(row).toContainText("30,000.00");
  await expect(row).toContainText("4,500.00");
  await expect(row).toContainText(
    label("desktop.ledger.withholding.origin.payer_certificate"),
  );
  // The statements of the year are listed as the backend holds them: the
  // active one in words it served, the withdrawn one in history by its token.
  const active = target.locator(".ledger-withholding-attested tr", {
    hasText: "No professional fees were withheld.",
  });
  await expect(active).toContainText("Economic activity income");
  await expect(active).toContainText(/Stated on/);
  await expect(
    active.getByRole("button", {
      name: label("desktop.ledger.withholding.withdraw_of", {
        class: "Economic activity income",
      }),
    }),
  ).toBeVisible();
  const past = target.locator(".ledger-withholding-history");
  await expect(past.getByRole("heading")).toHaveText(
    label("desktop.ledger.withholding.absence.history"),
  );
  const history = past.locator("tr", { hasText: "No dividends were paid." });
  await expect(history).toContainText("capital_mobiliario");
  await expect(history).toContainText(/Withdrawn on/);
  await expect(history.getByRole("button")).toHaveCount(0);
  await target
    .getByRole("group", { name: label("desktop.ledger.withholding.ejercicio") })
    .getByRole("button", {
      name: label("desktop.ledger.period.year_previous"),
      exact: true,
    })
    .click();
  await expect(target.locator(".ledger-withholding-empty")).toHaveText(
    label("desktop.ledger.withholding.empty", { ejercicio: fixtureYear - 1 }),
  );
  await expect(target.locator(".ledger-withholding-class")).toHaveCount(0);
});

test("a certificate is recorded, and the payer's tax ID is nowhere in the window afterwards", async ({
  page: target,
}) => {
  await openWithholding(target);
  await button(target, "desktop.ledger.withholding.action.record").click();
  const form = withholdingForm(target);
  const submit = button(form, "desktop.ledger.withholding.action.record");
  // Nothing is chosen for the person, and no figure is asked until a class
  // says which its certificate states; those every certificate states start
  // at zero.
  await expect(submit).toHaveAttribute("aria-disabled", "true");
  await expect(field(form, FIGURE + "retencion")).toHaveCount(0);
  await field(form, "desktop.ledger.withholding.income_class").selectOption(
    "capital_mobiliario",
  );
  await expect(field(form, FIGURE + "retencion")).toHaveValue("0.00");
  await field(form, "desktop.ledger.withholding.payer_tax_id").fill(
    PAYER_TAX_ID,
  );
  await field(form, "desktop.ledger.withholding.payer_legal_name").fill(
    "Banco de Ejemplo SA",
  );
  await field(form, FIGURE + "retencion").fill("150.00");
  await field(form, "desktop.ledger.withholding.origin_label").selectOption(
    "operator_declaration",
  );
  await submit.click();
  await expect(form).toBeHidden();
  const row = target.locator(".ledger-withholding-table tr", {
    hasText: "Banco de Ejemplo SA",
  });
  await expect(row).toContainText("150.00");
  // The class is shown as its token while the backend serves no label.
  await expect(
    target
      .locator(".ledger-withholding-class")
      .filter({ has: row })
      .getByRole("heading"),
  ).toHaveText("capital_mobiliario");
  const held = await target.evaluate(
    (taxId) => ({
      page: document.documentElement.outerHTML.includes(taxId),
      fields: [...document.querySelectorAll("input, textarea")].some((input) =>
        (input as HTMLInputElement).value.includes(taxId),
      ),
      storage: [localStorage, sessionStorage].some((store) =>
        Object.keys(store).some((key) =>
          (store.getItem(key) ?? "").includes(taxId),
        ),
      ),
    }),
    PAYER_TAX_ID,
  );
  expect(held).toEqual({ page: false, fields: false, storage: false });
});

for (const language of WITHHOLDING_LANGUAGES) {
  test(`a withholding record refused for its figures or its source is said in the words the backend served in ${language}, and keeps the form`, async ({
    page: target,
  }) => {
    await openWithholding(target, undefined, language);
    await target
      .getByRole("button", {
        name: label("desktop.ledger.withholding.action.record", {}, language),
        exact: true,
      })
      .click();
    const form = withholdingForm(target);
    const labelled = (key: string) =>
      form.getByLabel(label(key, {}, language), { exact: true });
    await labelled("desktop.ledger.withholding.income_class").selectOption(
      "trabajo",
    );
    await labelled("desktop.ledger.withholding.payer_tax_id").fill(
      PAYER_TAX_ID,
    );
    await labelled(FIGURE + "ingreso_a_cuenta").fill("20");
    await labelled(FIGURE + "reducciones_aplicables").fill("0");
    await labelled(FIGURE + "gastos_deducibles").fill("0");
    await labelled(FIGURE + "ingreso_a_cuenta_repercutido").fill("30");
    await labelled("desktop.ledger.withholding.origin_label").selectOption(
      "operator_declaration",
    );
    const line = target.locator(".setup-call-line");
    await recordButton(form, language).click();
    // The sentence as served: neither the reason's token nor a notice of the
    // window's own stands in for it.
    await expect(line).toHaveText(
      servedWords("record", "repercutido_exceeds_ingreso_a_cuenta", language),
    );
    await expect(line).not.toContainText(
      "repercutido_exceeds_ingreso_a_cuenta",
    );
    await expect(form).toBeVisible();
    await expect(
      labelled("desktop.ledger.withholding.payer_tax_id"),
    ).toHaveValue(PAYER_TAX_ID);
    await labelled(FIGURE + "ingreso_a_cuenta_repercutido").fill("0");
    await labelled("desktop.ledger.withholding.origin_label").selectOption(
      "payer_certificate",
    );
    await recordButton(form, language).click();
    await expect(line).toHaveText(
      servedWords("record", "certificate_fingerprint_required", language),
    );
    await expect(line).not.toContainText("certificate_fingerprint_required");
    await expect(form).toBeVisible();
  });
}

test("the figures of a certificate are the ones the ledger serves for its class, and a work-income one sent without its own two is refused in the served words", async ({
  page: target,
}) => {
  await openWithholding(target);
  await button(target, "desktop.ledger.withholding.action.record").click();
  const form = withholdingForm(target);
  const incomeClass = field(form, "desktop.ledger.withholding.income_class");
  await incomeClass.selectOption("trabajo");
  for (const served of [
    "importe_integro_dinerario",
    "valoracion_especie",
    "retencion",
    "ingreso_a_cuenta",
    "ingreso_a_cuenta_repercutido",
    "reducciones_aplicables",
    "gastos_deducibles",
  ])
    await expect(field(form, FIGURE + served)).toBeVisible();
  // The two only work-income certificates state start blank, not at zero.
  await expect(field(form, FIGURE + "reducciones_aplicables")).toHaveValue("");
  await incomeClass.selectOption("capital_mobiliario");
  await expect(field(form, FIGURE + "retencion")).toBeVisible();
  await expect(field(form, FIGURE + "reducciones_aplicables")).toHaveCount(0);
  await expect(field(form, FIGURE + "gastos_deducibles")).toHaveCount(0);
  await incomeClass.selectOption("trabajo");
  await field(form, "desktop.ledger.withholding.payer_tax_id").fill(
    PAYER_TAX_ID,
  );
  await field(form, "desktop.ledger.withholding.origin_label").selectOption(
    "operator_declaration",
  );
  await recordButton(form).click();
  const line = target.locator(".setup-call-line");
  await expect(line).toHaveText(
    servedWords("record", "trabajo_certificate_figure_missing"),
  );
  await expect(form).toBeVisible();
  await field(form, FIGURE + "reducciones_aplicables").fill("1200");
  await field(form, FIGURE + "gastos_deducibles").fill("0");
  await recordButton(form).click();
  await expect(form).toBeHidden();
});

test("a withholding record refused with no words served says only that it was not saved, and keeps the form", async ({
  page: target,
}) => {
  await openWithholding(target);
  const form = await startCertificate(target);
  await target.evaluate(() =>
    window.__scenarioWithholding!.nextRecords(["wordless"]),
  );
  await button(form, "desktop.ledger.withholding.action.record").click();
  const line = target.locator(".setup-call-line");
  // No reason token or sentence of the window's own stands in for words the
  // backend did not serve.
  await expect(line).toHaveText(label("desktop.ledger.form.refused"));
  await expect(line).not.toContainText("validation");
  await expect(form).toBeVisible();
  await expect(
    field(form, "desktop.ledger.withholding.payer_tax_id"),
  ).toHaveValue(PAYER_TAX_ID);
});

/** Starts a certificate record the way a payer's certificate is: a class, a
 * payer, the payer-certificate source. The figures stay at zero. */
async function startCertificate(target: Page, language = "en") {
  const word = (key: string) => label(key, {}, language);
  await target
    .getByRole("button", {
      name: word("desktop.ledger.withholding.action.record"),
      exact: true,
    })
    .click();
  const form = withholdingForm(target);
  const labelled = (key: string) => form.getByLabel(word(key), { exact: true });
  await labelled("desktop.ledger.withholding.income_class").selectOption(
    "capital_mobiliario",
  );
  await labelled("desktop.ledger.withholding.payer_tax_id").fill(PAYER_TAX_ID);
  await labelled("desktop.ledger.withholding.payer_legal_name").fill(
    "Banco de Ejemplo SA",
  );
  await labelled("desktop.ledger.withholding.origin_label").selectOption(
    "payer_certificate",
  );
  return form;
}

/** The form's own record button, in the window's language. */
const recordButton = (form: Locator, language = "en") =>
  form.getByRole("button", {
    name: label("desktop.ledger.withholding.action.record", {}, language),
    exact: true,
  });

/** Chooses the certificate file in the made-up computer's dialog. */
async function chooseCertificateFile(form: Locator, language = "en") {
  await form
    .getByRole("button", {
      name: `${label("desktop.ledger.withholding.file", {}, language)}: ${label("desktop.ledger.withholding.file_choose", {}, language)}`,
      exact: true,
    })
    .click();
  await expect(form.locator(".ledger-withholding-file-name")).toHaveText(
    "ticket-gasolinera-ruta7.jpg",
  );
}

test("a certificate file is picked, kept by the backend and recorded under the fingerprint it answers", async ({
  page: target,
}) => {
  await openWithholding(target);
  const form = await startCertificate(target);
  await expect(form.locator(".ledger-withholding-file-name")).toHaveCount(0);
  await chooseCertificateFile(form);
  await button(form, "desktop.ledger.withholding.action.record").click();
  await expect(form).toBeHidden();
  const row = target.locator(".ledger-withholding-table tr", {
    hasText: "Banco de Ejemplo SA",
  });
  // The document column holds the fingerprint the backend answered for the
  // bytes it kept: the window never computed one.
  await expect(row.locator(".font-mono")).toHaveText(/^[0-9a-f]{12}$/);
  // Neither the file's path nor its token stays in the window.
  const held = await target.evaluate(() =>
    /file-[0-9a-f]{32}/.test(document.documentElement.outerHTML),
  );
  expect(held).toBe(false);
});

for (const language of WITHHOLDING_LANGUAGES) {
  test(`a certificate file that cannot be read is refused in the words the backend served in ${language}, and the form keeps the file`, async ({
    page: target,
  }) => {
    await openWithholding(target, undefined, language);
    const form = await startCertificate(target, language);
    await chooseCertificateFile(form, language);
    await target.evaluate(() =>
      window.__scenarioWithholding!.nextRecords(["unreadable"]),
    );
    await recordButton(form, language).click();
    const line = target.locator(".setup-call-line");
    // The sentence as served: neither the reason's token nor a notice of the
    // window's own stands in for it.
    await expect(line).toHaveText(
      servedWords("record", "certificate_file_unreadable", language),
    );
    await expect(line).not.toContainText("certificate_file_unreadable");
    await expect(form).toBeVisible();
    await expect(form.locator(".ledger-withholding-file-name")).toBeVisible();
    // Sent again, the same file is recorded.
    await recordButton(form, language).click();
    await expect(form).toBeHidden();
    await expect(
      target.locator(".ledger-withholding-table tr", {
        hasText: "Banco de Ejemplo SA",
      }),
    ).toBeVisible();
  });

  test(`a stored document that is not the chosen file, or that custody does not hold, is refused in the words the backend served in ${language}`, async ({
    page: target,
  }) => {
    await openWithholding(target, "documents", language);
    const form = await startCertificate(target, language);
    const stored = form.getByLabel(
      label("desktop.ledger.withholding.document", {}, language),
      { exact: true },
    );
    await expect
      .poll(() => stored.locator("option").count())
      .toBeGreaterThan(1);
    await stored.selectOption({ index: 1 });
    const line = target.locator(".setup-call-line");
    // The register's custody holds no such document.
    await recordButton(form, language).click();
    await expect(line).toHaveText(
      servedWords("record", "certificate_not_in_custody", language),
    );
    await expect(line).not.toContainText("certificate_not_in_custody");
    // A file chosen beside it must be that document.
    await chooseCertificateFile(form, language);
    await recordButton(form, language).click();
    await expect(line).toHaveText(
      servedWords("record", "certificate_fingerprint_mismatch", language),
    );
    await expect(line).not.toContainText("certificate_fingerprint_mismatch");
    await expect(form).toBeVisible();
    await expect(
      target.locator(".ledger-withholding-table tr", {
        hasText: "Banco de Ejemplo SA",
      }),
    ).toHaveCount(0);
  });
}

test("a refusal that kept the file is shown as partial, apart from a write whose outcome is unknown", async ({
  page: target,
}) => {
  await openWithholding(target);
  const form = await startCertificate(target);
  await chooseCertificateFile(form);
  await target.evaluate(() =>
    window.__scenarioWithholding!.nextRecords(["kept_in_part"]),
  );
  await button(form, "desktop.ledger.withholding.action.record").click();
  const line = target.locator(".setup-call-line");
  await expect(line).toContainText(label("desktop.ledger.form.partial"));
  await expect(line).not.toContainText(label("desktop.ledger.form.unknown"));
  // The outcome is known, so there is nothing to refresh to find out.
  await expect(line.locator(".setup-call-reread")).toHaveCount(0);
  await expect(form).toBeVisible();
  await expect(
    target.locator(".ledger-withholding-table tr", {
      hasText: "Banco de Ejemplo SA",
    }),
  ).toHaveCount(0);
  // The form keeps its fields to send again.
  await expect(
    field(form, "desktop.ledger.withholding.payer_tax_id"),
  ).toHaveValue(PAYER_TAX_ID);
});

test("a certificate is removed only once the person confirms, against the revision listed", async ({
  page: target,
}) => {
  await openWithholding(target);
  const row = target.locator(".ledger-withholding-table tr", {
    hasText: "Empresa Ejemplo SL",
  });
  await row
    .getByRole("button", {
      name: label("desktop.ledger.withholding.remove_of", {
        payer: "Empresa Ejemplo SL",
      }),
    })
    .click();
  const confirmation = target.locator(".ledger-withholding-removing");
  await expect(confirmation).toContainText(
    label("desktop.ledger.withholding.remove_what", {
      payer: "Empresa Ejemplo SL",
      class: "Employment income",
    }),
  );
  await expect(confirmation).toContainText(
    label("desktop.ledger.withholding.correct_hint"),
  );
  await expect(row).toBeVisible();
  await confirmation
    .getByRole("button", {
      name: label("desktop.ledger.withholding.remove_confirm"),
    })
    .click();
  await expect(target.locator(".ledger-withholding-empty")).toBeVisible();
  await expect(confirmation).toBeHidden();
  await expect(target.locator(".setup-call-line")).toBeHidden();
});

test("an income class is stated to have no withholding, the statement is withdrawn into history and stated again against its revision", async ({
  page: target,
}) => {
  await openWithholding(target);
  await button(target, "desktop.ledger.withholding.action.attest").click();
  const form = withholdingForm(target);
  const submit = button(form, "desktop.ledger.withholding.action.attest");
  await expect(submit).toHaveAttribute("aria-disabled", "true");
  await field(form, "desktop.ledger.withholding.income_class").selectOption(
    "ganancia_patrimonial",
  );
  await field(form, "desktop.ledger.withholding.note").fill(
    "No sales this year.",
  );
  await submit.click();
  await expect(form).toBeHidden();
  const attested = target.locator(".ledger-withholding-attested");
  const row = attested.locator("tr", { hasText: "ganancia_patrimonial" });
  // The statement is listed as the backend returned it, by its token where
  // it served no words for the class.
  await expect(row).toContainText("No sales this year.");
  await expect(row).toContainText(/Stated on/);
  const withdraw = row.getByRole("button", {
    name: label("desktop.ledger.withholding.withdraw_of", {
      class: "ganancia_patrimonial",
    }),
  });
  await withdraw.click();
  // It leaves the active statements for the history, and offers nothing more.
  await expect(withdraw).toHaveCount(0);
  const history = target
    .locator(".ledger-withholding-history tr")
    .filter({ hasText: "ganancia_patrimonial" });
  await expect(history).toContainText("No sales this year.");
  await expect(history).toContainText(/Withdrawn on/);
  await expect(history.getByRole("button")).toHaveCount(0);
  // A withdrawn statement is stated again against the revision it was left at.
  await button(target, "desktop.ledger.withholding.action.attest").click();
  const restate = withholdingForm(target);
  await field(restate, "desktop.ledger.withholding.income_class").selectOption(
    "ganancia_patrimonial",
  );
  await field(restate, "desktop.ledger.withholding.note").fill(
    "Still no sales.",
  );
  await button(restate, "desktop.ledger.withholding.action.attest").click();
  await expect(restate).toBeHidden();
  const again = attested.locator("tr", { hasText: "Still no sales." });
  await expect(again).toContainText(/Stated on/);
  await expect(
    target
      .locator(".ledger-withholding-history tr")
      .filter({ hasText: "ganancia_patrimonial" }),
  ).toHaveCount(0);
  await expect(target.locator(".setup-call-line")).toBeHidden();
  // A class with certificates cannot be stated to have none.
  await button(target, "desktop.ledger.withholding.action.attest").click();
  const refused = withholdingForm(target);
  await field(refused, "desktop.ledger.withholding.income_class").selectOption(
    "trabajo",
  );
  await field(refused, "desktop.ledger.withholding.note").fill("None.");
  await button(refused, "desktop.ledger.withholding.action.attest").click();
  await expect(target.locator(".setup-call-line")).toHaveText(
    servedWords("absence", "records_present"),
  );
});

for (const language of WITHHOLDING_LANGUAGES) {
  test(`a statement refused for its class is said in the words the backend served in ${language}, without the reason's token`, async ({
    page: target,
  }) => {
    await openWithholding(target, undefined, language);
    const line = target.locator(".setup-call-line");
    for (const [incomeClass, reason] of [
      ["trabajo", "records_present"],
      ["actividad_economica", "already_attested"],
    ] as const) {
      await target
        .getByRole("button", {
          name: label("desktop.ledger.withholding.action.attest", {}, language),
          exact: true,
        })
        .click();
      const form = withholdingForm(target);
      await form
        .getByLabel(
          label("desktop.ledger.withholding.income_class", {}, language),
          {
            exact: true,
          },
        )
        .selectOption(incomeClass);
      await form
        .getByLabel(label("desktop.ledger.withholding.note", {}, language), {
          exact: true,
        })
        .fill("Note.");
      await form
        .getByRole("button", {
          name: label("desktop.ledger.withholding.action.attest", {}, language),
          exact: true,
        })
        .click();
      await expect(line).toHaveText(servedWords("absence", reason, language));
      await expect(line).not.toContainText(reason);
      await expect(form).toBeVisible();
      await target
        .getByRole("button", {
          name: label("desktop.ledger.withholding.action.attest", {}, language),
          exact: true,
        })
        .first()
        .click();
    }
  });
}

test("a statement that is already active offers its withdrawal against the revision listed, and is refused if stated again", async ({
  page: target,
}) => {
  await openWithholding(target);
  await button(target, "desktop.ledger.withholding.action.attest").click();
  const form = withholdingForm(target);
  await field(form, "desktop.ledger.withholding.income_class").selectOption(
    "actividad_economica",
  );
  await field(form, "desktop.ledger.withholding.note").fill("Again.");
  await button(form, "desktop.ledger.withholding.action.attest").click();
  await expect(target.locator(".setup-call-line")).toHaveText(
    servedWords("absence", "already_attested"),
  );
  // Nothing was doubled: the listed statement stands, and withdraws.
  const row = target.locator(".ledger-withholding-attested tr", {
    hasText: "No professional fees were withheld.",
  });
  await row
    .getByRole("button", {
      name: label("desktop.ledger.withholding.withdraw_of", {
        class: "Economic activity income",
      }),
    })
    .click();
  await expect(
    target
      .locator(".ledger-withholding-history tr")
      .filter({ hasText: "No professional fees were withheld." }),
  ).toContainText(/Withdrawn on/);
});
