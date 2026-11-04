import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  RATIO_ELIGIBLE_FIXTURE,
  ratioWording,
} from "../../src/dev/fixtures/ledgerRatios";
import { label } from "../support/strings";
import type { JsonObject } from "../../src/shell/ledger";

declare global {
  interface Window {
    __counterpartyReply?: (at: number) => void;
    __counterpartyRequests?: JsonObject[];
    __counterpartyPending?: number;
  }
}

// The Ledger page's Setup sections, and the Assets tab's Stock area, over the
// scenario host's made-up ledger:
// a rule made from a selection and its run staged, ratios by year, an own
// account added through the protected body and shown masked only, an
// account closed on a date it asks for, a prorrata election the register
// refuses until its reference is given, an inventory valuation preview, a
// readiness reason that opens the movements it names, and a reset whose
// dry run the sealed declarations block.

/** The sentences the prorrata register serves with its refusals, in English,
 * as the generated fixture holds them. */
const PRORRATA_WORDS = (
  JSON.parse(
    readFileSync(
      new URL("../../src/dev/fixtures/ledgerServedWords.json", import.meta.url),
      "utf8",
    ),
  ) as { prorrata: Record<string, Record<string, string>> }
).prorrata;
const prorrataRefused = (reason: string) => PRORRATA_WORDS[reason]!.en!;

/** The sentences the backend serves with every refusal of the withholding
 * record and absence operations, by reason and language, as the generated
 * fixture holds them. */
const REFUSAL_WORDS = JSON.parse(
  readFileSync(
    new URL(
      "../../src/dev/fixtures/ledgerWithholdingRefusalWords.json",
      import.meta.url,
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

async function openLedger(
  target: Page,
  scheme?: "light" | "dark",
  language = "en",
  shape?: string,
) {
  if (scheme)
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&lang=${language}${shape ? `&ledger=${shape}` : ""}`,
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(page(target).getByRole("grid")).toBeVisible();
}

test("a capital good names its purchase from the year typed", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "registers");
  await area(target, "desktop.ledger.registers.area.capital");
  await target.locator(".ledger-capital-add").click();
  const form = target.locator(".ledger-capital-form");
  const description = field(form, "desktop.ledger.capital.description");
  const year = field(form, "desktop.ledger.capital.year");
  const cuota = field(form, "desktop.ledger.capital.cuota");
  await year.fill("2026");
  await form.locator(".ledger-capital-movement").click();
  const options = target.getByRole("listbox").getByRole("option");
  await expect(options.first()).toBeVisible();
  const picked = await options.first().innerText();
  await options.first().click();
  await expect(form.locator(".ledger-capital-movement")).toContainText(
    picked.split("\n")[0]!.slice(0, 12),
  );
  await expect(description).not.toHaveValue("");
  await expect(year).toHaveValue("2026");
  // Nothing states that a movement's IVA is the good's cuota soportada.
  await expect(cuota).toHaveValue("");
  await year.fill("2025");
  await expect(form.locator(".ledger-capital-movement")).toContainText(
    label("desktop.ledger.form.choose"),
  );
});

async function openSetup(
  target: Page,
  section: "rules" | "registers" | "health",
  language = "en",
) {
  await head(target).locator(".ledger-setup").click();
  await target
    .getByRole("menuitem", {
      name: label(`desktop.ledger.section.${section}`, {}, language),
    })
    .click();
  await expect(target.locator(`.ledger-setup-${section}`)).toBeVisible();
  // The menu has closed and given the page back.
  await expect(target.getByRole("menu")).toHaveCount(0);
}

/** Opens the Assets tab, on its Stock area where `stock` is given. */
async function openAssets(target: Page, stock = false, language = "en") {
  await head(target)
    .getByRole("tab", {
      name: label("desktop.ledger.section.assets", {}, language),
    })
    .click();
  await expect(target.locator(".ledger-assets")).toBeVisible();
  if (stock) await area(target, "desktop.ledger.assets.area.stock");
}

async function area(target: Page, key: string, language = "en") {
  await target
    .getByRole("tab", { name: label(key, {}, language), exact: true })
    .click();
}

test("counterparty replies and drafts belong to the exact lookup identity", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.evaluate(() => {
    const port = window.__fixtureLedger!;
    const submit = port.submit;
    const pending: (() => void)[] = [];
    window.__counterpartyPending = 0;
    window.__counterpartyRequests = [];
    window.__counterpartyReply = (at) => pending[at]!();
    port.submit = async (definition, payload) => {
      const answer = await submit(definition, payload);
      if (definition === "ledger.counterparty") {
        const request = payload as JsonObject;
        window.__counterpartyRequests!.push(request);
        if (request.action === "view")
          await new Promise<void>((resolve) => {
            pending.push(resolve);
            window.__counterpartyPending = pending.length;
          });
      }
      return answer;
    };
  });
  await openSetup(target, "rules");
  await area(target, "desktop.ledger.rules.area.counterparties");
  const tax = field(target, "desktop.ledger.counterparty.tax_id");
  const country = field(target, "desktop.ledger.counterparty.country");
  const answer = target.locator(".ledger-counterparty-answer");
  const lookup = async (id: string, hint: string, count: number) => {
    await tax.fill(id);
    await country.focus();
    await country.fill(hint);
    await expect(country).toHaveValue(hint);
    await target.locator(".ledger-counterparty-view").click();
    await expect
      .poll(() => target.evaluate(() => window.__counterpartyPending))
      .toBe(count);
  };
  const reply = (at: number) =>
    target.evaluate((at) => window.__counterpartyReply!(at), at);
  await lookup("LU20260001", "LU", 1);
  await lookup("B12345678", "ES", 2);
  await reply(1);
  await expect(answer).toContainText("B12345678");
  await reply(0);
  await expect(answer).not.toContainText("LU20260001");
  const note = field(answer, "desktop.ledger.counterparty.note");
  await note.fill("This draft belongs to B in ES");
  await country.focus();
  await country.fill("FR");
  await expect(answer).toHaveCount(0);
  await lookup("B12345678", "FR", 3);
  await reply(2);
  await expect(note).toHaveValue("");
  await lookup("B12345678", "ES", 4);
  await reply(3);
  await expect(note).toHaveValue("This draft belongs to B in ES");
  await field(answer, "desktop.ledger.counterparty.scope_label").selectOption(
    "es_mainland",
  );
  await field(answer, "desktop.ledger.counterparty.asserted_by").fill(
    "Fixture operator",
  );
  await target.locator(".ledger-counterparty-confirm").click();
  await expect
    .poll(() => target.evaluate(() => window.__counterpartyPending))
    .toBe(5);
  await reply(4);
  await expect(
    button(answer, "desktop.ledger.counterparty.withdraw"),
  ).toBeVisible();
  await expect(answer).not.toContainText(
    label("desktop.ledger.counterparty.not_confirmed"),
  );
  await button(answer, "desktop.ledger.counterparty.withdraw").click();
  await expect(
    answer.getByText(label("desktop.ledger.counterparty.withdraw_what"), {
      exact: false,
    }),
  ).toContainText("B12345678");
  await target.locator(".ledger-counterparty-withdraw").click();
  await expect
    .poll(() => target.evaluate(() => window.__counterpartyPending))
    .toBe(6);
  await reply(5);
  const writes = await target.evaluate(() =>
    window.__counterpartyRequests!.filter(
      (request) => request.action !== "view",
    ),
  );
  expect(writes).toMatchObject([
    {
      action: "confirm",
      tax_identifier: "B12345678",
      country_code: "ES",
      note: "This draft belongs to B in ES",
    },
    { action: "withdraw", tax_identifier: "B12345678", country_code: "ES" },
  ]);
  expect(writes[1]).not.toHaveProperty("note");
});

for (const action of ["confirm", "withdraw"] as const) {
  test(`an uncertain counterparty ${action} is not settled by a resolution-only lookup`, async ({
    page: target,
  }) => {
    await openLedger(target);
    await openSetup(target, "rules");
    await area(target, "desktop.ledger.rules.area.counterparties");
    await field(target, "desktop.ledger.counterparty.tax_id").fill(
      "LU20260001",
    );
    await field(target, "desktop.ledger.counterparty.country").fill("LU");
    await target.locator(".ledger-counterparty-view").click();
    const answer = target.locator(".ledger-counterparty-answer");
    await expect(answer).toBeVisible();
    await expect(answer).not.toContainText(
      label("desktop.ledger.counterparty.not_confirmed"),
    );
    await target.evaluate(() =>
      window.__scenarioLedger!.nextWrites(["unknown"]),
    );
    if (action === "confirm") {
      await field(
        answer,
        "desktop.ledger.counterparty.scope_label",
      ).selectOption("eu_member");
      await field(answer, "desktop.ledger.counterparty.asserted_by").fill(
        "Fixture operator",
      );
      await target.locator(".ledger-counterparty-confirm").click();
    } else {
      await button(answer, "desktop.ledger.counterparty.withdraw").click();
      await target.locator(".ledger-counterparty-withdraw").click();
    }
    const pause = target.locator(".ledger-paused");
    await expect(pause).toBeVisible();
    const before = await target.evaluate(
      () =>
        window.__scenarioHostCalls!.filter(
          (call) => call === "ledger ledger.counterparty",
        ).length,
    );
    await pause.locator(".ledger-paused-reread").click();
    await expect(pause).toContainText(
      label("desktop.ledger.paused.untold", {
        movement: label("desktop.ledger.counterparty.title"),
      }),
    );
    expect(
      await target.evaluate(
        () =>
          window.__scenarioHostCalls!.filter(
            (call) => call === "ledger ledger.counterparty",
          ).length,
      ),
    ).toBe(before);
  });
}

test("a counterparty conflict keeps the draft and shows both authoritative values", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.evaluate(() => {
    const port = window.__fixtureLedger!;
    const submit = port.submit;
    port.submit = async (definition, payload) => {
      const request = payload as JsonObject;
      if (
        definition === "ledger.counterparty" &&
        request.action === "confirm"
      ) {
        const answer = await submit(definition, {
          action: "view",
          tax_identifier: request.tax_identifier,
          country_code: request.country_code,
        } as typeof payload);
        if (answer.kind !== "settled") return answer;
        return {
          ...answer,
          result: {
            ...answer.result,
            action: "confirm",
            resolution: null,
            facts: null,
            recorded: null,
            changed: false,
            conflict_context: [
              ["confirmed_scope", "eu_member"],
              ["asserted_scope", "es_mainland"],
            ],
          },
        } as typeof answer;
      }
      return submit(definition, payload);
    };
  });
  await openSetup(target, "rules");
  await area(target, "desktop.ledger.rules.area.counterparties");
  await field(target, "desktop.ledger.counterparty.tax_id").fill("LU20260001");
  await target.locator(".ledger-counterparty-view").click();
  const answer = target.locator(".ledger-counterparty-answer");
  await field(answer, "desktop.ledger.counterparty.scope_label").selectOption(
    "es_mainland",
  );
  await field(answer, "desktop.ledger.counterparty.asserted_by").fill(
    "Fixture operator",
  );
  await field(answer, "desktop.ledger.counterparty.note").fill(
    "Retain this proposed correction",
  );
  await target.locator(".ledger-counterparty-confirm").click();
  const conflict = answer
    .getByRole("alert")
    .filter({ hasText: label("desktop.ledger.counterparty.conflict") });
  await expect(conflict).toBeVisible();
  await expect(conflict).toContainText(
    label("desktop.ledger.counterparty.scope.eu_member"),
  );
  await expect(conflict).toContainText(
    label("desktop.ledger.counterparty.scope.es_mainland"),
  );
  await expect(field(answer, "desktop.ledger.counterparty.note")).toHaveValue(
    "Retain this proposed correction",
  );
  await expect(
    field(answer, "desktop.ledger.counterparty.asserted_by"),
  ).toHaveValue("Fixture operator");
  await expect(target.locator(".ledger-paused")).toHaveCount(0);
  await button(answer, "desktop.ledger.counterparty.withdraw").click();
  await target.locator(".ledger-counterparty-withdraw").click();
  await expect(conflict).toHaveCount(0);
});

test("a settled counterparty answer that omits a proposed value keeps the draft", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.evaluate(() => {
    const port = window.__fixtureLedger!;
    const submit = port.submit;
    port.submit = async (definition, payload) => {
      const answer = await submit(definition, payload);
      if (
        definition === "ledger.counterparty" &&
        (payload as JsonObject).action === "confirm" &&
        answer.kind === "settled"
      ) {
        const result = answer.result as unknown as {
          facts: Record<string, unknown>;
        };
        return {
          ...answer,
          result: {
            ...answer.result,
            facts: { ...result.facts, territorial_scope: null },
          },
        } as typeof answer;
      }
      return answer;
    };
  });
  await openSetup(target, "rules");
  await area(target, "desktop.ledger.rules.area.counterparties");
  await field(target, "desktop.ledger.counterparty.tax_id").fill("LU20260001");
  await target.locator(".ledger-counterparty-view").click();
  const answer = target.locator(".ledger-counterparty-answer");
  await field(answer, "desktop.ledger.counterparty.scope_label").selectOption(
    "eu_member",
  );
  await field(answer, "desktop.ledger.counterparty.asserted_by").fill(
    "Fixture operator",
  );
  await field(answer, "desktop.ledger.counterparty.note").fill(
    "Keep the proposed scope",
  );
  await target.locator(".ledger-counterparty-confirm").click();
  await expect(answer.getByRole("alert")).toContainText(
    label("desktop.ledger.counterparty.not_applied"),
  );
  await expect(field(answer, "desktop.ledger.counterparty.note")).toHaveValue(
    "Keep the proposed scope",
  );
  await expect(target.locator(".ledger-paused")).toHaveCount(0);
});

test("a successful counterparty update keeps its attribution through a failed refresh without keeping a saved draft", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.evaluate(() => {
    const port = window.__fixtureLedger!;
    const submit = port.submit;
    let failView = false;
    port.submit = async (definition, payload) => {
      if (
        definition === "ledger.counterparty" &&
        (payload as JsonObject).action === "view" &&
        failView
      ) {
        failView = false;
        throw Object.assign(new Error("fixture read failure"), {
          code: "unavailable",
        });
      }
      const answer = await submit(definition, payload);
      if (
        definition === "ledger.counterparty" &&
        (payload as JsonObject).action === "confirm" &&
        answer.kind === "settled"
      ) {
        const result = answer.result as unknown as {
          facts: Record<string, unknown>;
        };
        failView = true;
        return {
          ...answer,
          result: {
            ...answer.result,
            facts: { ...result.facts, asserted_by: "Original operator" },
          },
        } as typeof answer;
      }
      return answer;
    };
  });
  await openSetup(target, "rules");
  await area(target, "desktop.ledger.rules.area.counterparties");
  await field(target, "desktop.ledger.counterparty.tax_id").fill("LU20260001");
  await target.locator(".ledger-counterparty-view").click();
  const answer = target.locator(".ledger-counterparty-answer");
  await field(answer, "desktop.ledger.counterparty.scope_label").selectOption(
    "eu_member",
  );
  await field(answer, "desktop.ledger.counterparty.asserted_by").fill(
    "Current operator",
  );
  await field(answer, "desktop.ledger.counterparty.note").fill("Updated note");
  await target.locator(".ledger-counterparty-confirm").click();
  await expect(
    target.getByRole("status").filter({ hasText: "Original operator" }),
  ).toBeVisible();
  await expect(answer).toHaveCount(0);
  await target.locator(".ledger-counterparty-view").click();
  await expect(field(answer, "desktop.ledger.counterparty.note")).toHaveValue(
    "",
  );
  await expect(
    field(answer, "desktop.ledger.counterparty.asserted_by"),
  ).toHaveValue("");
  await expect(answer).not.toContainText(
    label("desktop.ledger.counterparty.not_applied"),
  );
  await target.locator(".ledger-counterparty-view").click();
  await expect(
    target.getByRole("status").filter({ hasText: "Original operator" }),
  ).toBeVisible();
  await field(target, "desktop.ledger.counterparty.tax_id").fill("B12345678");
  await expect(
    target.getByRole("status").filter({ hasText: "Original operator" }),
  ).toHaveCount(0);
});

test("a counterparty can confirm only its VAT state and keeps edits made while saving", async ({
  page: target,
}) => {
  await openLedger(target);
  await target.evaluate(() => {
    const port = window.__fixtureLedger!;
    const submit = port.submit;
    window.__counterpartyRequests = [];
    port.submit = async (definition, payload) => {
      const request = payload as JsonObject;
      const answer = await submit(definition, payload);
      if (
        definition === "ledger.counterparty" &&
        request.action === "confirm"
      ) {
        window.__counterpartyRequests!.push(request);
        await new Promise<void>((resolve) => {
          window.__counterpartyReply = () => resolve();
        });
      }
      return answer;
    };
  });
  await openSetup(target, "rules");
  await area(target, "desktop.ledger.rules.area.counterparties");
  await field(target, "desktop.ledger.counterparty.tax_id").fill("LU20260001");
  await target.locator(".ledger-counterparty-view").click();
  const answer = target.locator(".ledger-counterparty-answer");
  await field(answer, "desktop.ledger.counterparty.state").fill("LU");
  const confirm = target.locator(".ledger-counterparty-confirm");
  await expect(confirm).toHaveAttribute("aria-disabled", "true");
  const actor = field(answer, "desktop.ledger.counterparty.asserted_by");
  await expect(actor).toHaveAttribute("maxlength", "256");
  await actor.fill("Fixture operator");
  const note = field(answer, "desktop.ledger.counterparty.note");
  await note.fill("Submitted note");
  await confirm.click();
  await expect
    .poll(() => target.evaluate(() => window.__counterpartyRequests!.length))
    .toBe(1);
  await note.fill("A later unsaved edit");
  await target.evaluate(() => window.__counterpartyReply!(0));
  await expect(note).toHaveValue("A later unsaved edit");
  expect(
    await target.evaluate(() => window.__counterpartyRequests),
  ).toMatchObject([
    {
      action: "confirm",
      country_code: null,
      territorial_scope: null,
      identification_state: "LU",
      asserted_by: "Fixture operator",
      note: "Submitted note",
    },
  ]);
});

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
    prorrataRefused("reference_required"),
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
    prorrataRefused("seed_existing_blocked"),
  );
});

test("the prorrata register lists a declared gross cuota and removes it once confirmed", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "registers");
  await area(target, "desktop.ledger.registers.area.prorrata");
  const gross = target.locator(".ledger-prorrata-gross");
  const row = gross.locator(".ledger-prorrata-gross-table tr", {
    hasText: "LIQ-2026-1T",
  });
  // The period, the cuota as the register serves it and its document.
  await expect(row).toContainText("2026");
  await expect(row).toContainText("1T");
  await expect(row).toContainText("1,234.56");
  await row
    .getByRole("button", {
      name: label("desktop.ledger.prorrata.gross.remove_of", {
        liquidation: "2026 · 1T",
      }),
    })
    .click();
  // Nothing is removed until the person confirms.
  const confirmation = gross.locator(".ledger-prorrata-gross-removing");
  await expect(confirmation).toContainText(
    label("desktop.ledger.prorrata.gross.remove_what", {
      liquidation: "2026 · 1T",
    }),
  );
  await expect(row).toBeVisible();
  await confirmation
    .getByRole("button", {
      name: label("desktop.ledger.prorrata.gross.remove_confirm"),
    })
    .click();
  await expect(gross.locator(".ledger-prorrata-gross-empty")).toHaveText(
    label("desktop.ledger.prorrata.gross.empty"),
  );
  await expect(confirmation).toBeHidden();
  await expect(target.locator(".setup-call-line")).toBeHidden();
});

test("a gross cuota is declared, refused while one stands and replaced when asked", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "registers");
  await area(target, "desktop.ledger.registers.area.prorrata");
  const declare = async (period: string, amount: string, replace = false) => {
    const opened = target.locator(".ledger-prorrata-form");
    if (!(await opened.isVisible()))
      await button(
        target,
        "desktop.ledger.prorrata.action.declare_gross",
      ).click();
    const form = target.locator(".ledger-prorrata-form");
    await field(form, "desktop.ledger.prorrata.gross.period").selectOption(
      period,
    );
    await field(form, "desktop.ledger.prorrata.gross.gross_cuota").fill(amount);
    await field(form, "desktop.ledger.prorrata.gross.evidence").fill(
      `LIQ-2026-${period}`,
    );
    const replacing = field(form, "desktop.ledger.prorrata.gross.replace");
    if ((await replacing.isChecked()) !== replace)
      await replacing.setChecked(replace);
    await form
      .getByRole("button", {
        name: label("desktop.ledger.prorrata.action.declare_gross"),
      })
      .click();
    return form;
  };
  const table = target.locator(".ledger-prorrata-gross-table");

  const form = await declare("2T", "500");
  await expect(form).toBeHidden();
  const row = table.locator("tr", { hasText: "LIQ-2026-2T" });
  await expect(row).toContainText("500.00");

  // The register keeps the cuota it holds until the person asks to replace it.
  await declare("2T", "600");
  await expect(target.locator(".setup-call-line")).toContainText(
    prorrataRefused("gross_declaration_duplicate"),
  );
  await expect(row).toContainText("500.00");
  await declare("2T", "600", true);
  await expect(target.locator(".ledger-prorrata-form")).toBeHidden();
  await expect(row).toContainText("600.00");
  await expect(row).not.toContainText("500.00");
  await expect(table.locator("tr", { hasText: "LIQ-2026-2T" })).toHaveCount(1);
});

for (const language of ["en", "es", "ca", "hu"]) {
  test(`the register's name, kind, method and state words are whole and unclipped in ${language}`, async ({
    page: target,
  }) => {
    // A window narrow enough that the register's columns compete for width.
    await target.setViewportSize({ width: 1000, height: 900 });
    await openLedger(target, undefined, language);
    await openAssets(target, false, language);
    const list = target.locator(".ledger-assets-list");
    await expect(list.locator("tbody tr").first()).toBeVisible();
    const found = await list.evaluate((table) => {
      const split = (cell: Element) => {
        const words: string[] = [];
        const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
          for (const word of (node.textContent ?? "").matchAll(/\S+/g)) {
            const range = document.createRange();
            range.setStart(node, word.index);
            range.setEnd(node, word.index + word[0].length);
            if (range.getClientRects().length > 1) words.push(word[0]);
          }
        }
        return words;
      };
      const heads = [...table.querySelectorAll("thead th")];
      const columns = ["name", "kind", "method", "state"].map((id) =>
        heads.findIndex((head) => head.getAttribute("data-column") === id),
      );
      const cells = [...table.querySelectorAll("tbody tr")].flatMap((row) =>
        columns.map((at) => row.children[at]!),
      );
      return {
        columns,
        cells: cells.length,
        clipped: cells
          .filter((cell) => cell.scrollWidth > cell.clientWidth)
          .map((cell) => cell.textContent),
        broken: cells.flatMap(split),
        words: cells.map((cell) => getComputedStyle(cell).overflowWrap),
        // An identifier keeps breaking anywhere to fit its column.
        serial: getComputedStyle(table.querySelectorAll("tbody td")[1]!)
          .overflowWrap,
      };
    });
    expect(found.columns.every((at) => at >= 0)).toBe(true);
    expect(found.cells).toBeGreaterThan(8);
    expect(found.clipped).toEqual([]);
    expect(found.broken).toEqual([]);
    expect(new Set(found.words)).toEqual(new Set(["normal"]));
    expect(found.serial).toBe("anywhere");
  });
}

test("an inventory valuation preview records nothing", async ({
  page: target,
}) => {
  await openLedger(target);
  await openAssets(target, true);
  const books = target.locator(".ledger-stock-table");
  await expect(books).toBeVisible();
  const listed = books.locator("tr", { hasText: "Papelería y reprografía" });
  const before = await listed.textContent();
  await button(target, "desktop.ledger.stock.action.preview").first().click();
  const valuation = target.locator(".ledger-stock-valuation");
  await expect(valuation).toContainText(
    label("desktop.ledger.inventory.valuation", {
      name: "Papelería y reprografía",
      closing: "410.00",
      cogs: "0.00",
      method: label("application.inventory.labels.valuation_method.fifo"),
    }),
  );
  await expect(valuation).toContainText(
    label("desktop.ledger.inventory.preview_note"),
  );
  // Nothing was recorded: the book lists as it did.
  expect(await listed.textContent()).toBe(before);
});

test("a stock movement's unit cost reads to two places beside its cost", async ({
  page: target,
}) => {
  await openLedger(target);
  await openAssets(target, true);
  await target
    .locator(".ledger-stock-table")
    .getByRole("button", { name: "Papelería y reprografía", exact: true })
    .click();
  const movement = target.locator(".ledger-stock-movements tbody tr").first();
  // The book holds 4.1 and 410: the unit cost shows the cents the cost does.
  await expect(movement.locator("td").nth(3)).toHaveText("4.10");
  await expect(movement.locator("td").nth(4)).toHaveText("410.00");
});

test("a closing value's files and a purchase's files are chosen in the file dialog, and a file the book refuses is said so", async ({
  page: target,
}) => {
  await openLedger(target);
  await openAssets(target, true);
  await button(target, "desktop.ledger.stock.action.closing").first().click();
  const form = target.locator(".ledger-stock-form-closing");
  await expect(form).toBeVisible();
  await field(form, "desktop.ledger.stock.closing.authority").selectOption(
    "physical_observation",
  );
  await expect(
    field(form, "desktop.ledger.stock.closing.counted_on"),
  ).toBeVisible();

  const choose = label("desktop.ledger.stock.proof.choose_file");
  const change = label("desktop.ledger.stock.proof.change_file");
  const counted = label(
    "application.inventory.labels.physical_evidence_role.physical_count",
  );
  const reconciliation = label(
    "application.inventory.labels.decision_evidence_role.authority_reconciliation",
  );

  // A file the book refuses is said so, and the file stays unchosen.
  await target.evaluate(() => window.__scenarioLedger?.nextWrites(["refused"]));
  await form.getByRole("button", { name: `${counted}: ${choose}` }).click();
  await expect(form).toContainText(label("desktop.ledger.stock.refused"));
  await expect(
    form.getByRole("button", { name: `${counted}: ${choose}` }),
  ).toBeVisible();

  // One the book keeps shows its name, and can be changed.
  await form.getByRole("button", { name: `${counted}: ${choose}` }).click();
  await expect(
    form.getByRole("button", { name: `${counted}: ${change}` }),
  ).toBeVisible();
  await expect(form).toContainText("ticket-gasolinera-ruta7.jpg");
  await expect(form).not.toContainText(label("desktop.ledger.stock.refused"));
  await form
    .getByRole("button", { name: `${reconciliation}: ${choose}` })
    .click();
  await expect(
    form.getByRole("button", { name: `${reconciliation}: ${change}` }),
  ).toBeVisible();
  await button(form, "desktop.ledger.form.cancel").click();
  await expect(form).toBeHidden();

  // A purchase's files are offered for a purchase alone.
  await button(target, "desktop.ledger.stock.action.add_movement")
    .first()
    .click();
  const movement = target.locator(".ledger-stock-form-movement");
  const priceFile = movement.getByRole("button", {
    name: `${label("desktop.ledger.stock.proof.price")}: ${choose}`,
  });
  await expect(priceFile).toHaveCount(0);
  await field(movement, "desktop.ledger.inventory.kind_label").selectOption(
    "purchase",
  );
  await expect(priceFile).toBeVisible();
  await field(movement, "desktop.ledger.inventory.kind_label").selectOption(
    "cogs",
  );
  await expect(priceFile).toHaveCount(0);
});

/** What a readiness strip shows, pill by pill and chip by chip. */
const stripOf = (scope: Locator) =>
  scope
    .locator(
      ".ledger-readiness [data-readiness], .ledger-reasons [data-reason]",
    )
    .evaluateAll((items) =>
      items.map(
        (item) =>
          `${item.getAttribute("data-readiness") ?? item.getAttribute("data-reason")}:${item.textContent}`,
      ),
    );

test("what is missing opens on the strip's check and says it the same way", async ({
  page: target,
}) => {
  await openLedger(target);
  const strip = page(target).locator(".ledger-movements");
  await expect(
    strip.locator(".ledger-readiness [data-readiness]"),
  ).not.toHaveCount(0);
  await expect(strip.locator("[data-readiness=unknown]")).toHaveCount(0);
  const onMovements = await stripOf(strip);
  await openSetup(target, "health");
  const health = target.locator(".ledger-setup-health");
  // The page's last check, without checking again: the same pills and chips.
  await expect.poll(() => stripOf(health)).toEqual(onMovements);
  const recheck = health.locator(".ledger-health-preflight");
  await expect(recheck).toHaveText(label("desktop.ledger.health.check_again"));
  await recheck.hover();
  await expect(target.locator(".ledger-health-checked-at")).toBeVisible();
  // Checking again measures the same stored rows the same way.
  await recheck.click();
  await expect.poll(() => stripOf(health)).toEqual(onMovements);
});

test("a readiness reason in Health opens the movements it counts", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "health");
  const chip = target
    .locator(".ledger-setup-health .ledger-reasons [data-reason] button")
    .first();
  await expect(chip).toBeVisible();
  const counted = Number(
    (await chip.locator(".tabular-nums").textContent())?.replace(/\D/g, ""),
  );
  await chip.click();
  await expect(
    head(target).getByRole("tab", {
      name: new RegExp(`^${label("desktop.ledger.section.movements")}`),
    }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(dataRows(target)).toHaveCount(counted);
});

test("the to-classify pill in Health opens the movements to classify", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "health");
  const pill = target.locator(
    ".ledger-setup-health .ledger-readiness [data-readiness=to_classify] button",
  );
  // The count is what is drawn; the sentence is for the screen reader.
  const counted = Number(
    (
      await pill.locator("span[aria-hidden=true]").first().textContent()
    )?.replace(/\D/g, ""),
  );
  expect(counted).toBeGreaterThan(0);
  await pill.click();
  await expect(dataRows(target)).toHaveCount(counted);
});

test("Health's status says each count beside its label and names what the states leave", async ({
  page: target,
}) => {
  await openLedger(target);
  await openSetup(target, "health");
  // The review states are counted over the whole ledger, apart from what
  // is read for the period.
  await expect(target.locator(".ledger-health-status")).not.toContainText(
    label("desktop.ledger.health.count.pending"),
  );
  const status = target.locator(".ledger-health-ledger");
  await expect(status).toBeVisible();
  const value = async (name: string) =>
    Number(
      (
        await status
          .locator("dt", { hasText: new RegExp(`^${name}$`) })
          .locator("xpath=following-sibling::dd[1]")
          .textContent()
      )?.replace(/\D/g, ""),
    );
  const active = await value(label("desktop.ledger.health.count.active"));
  const states =
    (await value(label("desktop.ledger.health.count.pending"))) +
    (await value(label("desktop.ledger.health.count.reviewed"))) +
    (await value(label("desktop.ledger.health.count.skipped")));
  const excluded = status.locator("[data-count=excluded] dd");
  if (active === states) await expect(excluded).toHaveCount(0);
  else await expect(excluded).toHaveText(String(active - states));
  // Each number sits beside its label, not across the panel.
  const gaps = await status.locator("dl").evaluateAll((lists) =>
    lists.flatMap((list) =>
      [...list.querySelectorAll("dt")].map((term) => {
        const number = term.nextElementSibling as HTMLElement;
        return (
          number.getBoundingClientRect().left -
          term.getBoundingClientRect().right
        );
      }),
    ),
  );
  for (const gap of gaps) expect(gap).toBeLessThan(160);
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
    await area(target, "desktop.ledger.registers.area.withholding");
    await expect(target.locator(".ledger-withholding-table")).toBeVisible();
    expect(await audit(target)).toEqual([]);
    await openSetup(target, "health");
    await expect(target.locator(".ledger-health-status")).toBeVisible();
    expect(await audit(target)).toEqual([]);
  });

/** Opens Setup › Registers › Withholding. */
async function openWithholding(target: Page, shape?: string, language = "en") {
  await openLedger(target, undefined, language, shape);
  await openSetup(target, "registers", language);
  await area(target, "desktop.ledger.registers.area.withholding", language);
  await expect(
    target.locator(".ledger-withholding-class").first(),
  ).toBeVisible();
}

const withholdingForm = (target: Page) =>
  target.locator(".ledger-withholding-form");

/** A made-up payer tax ID, which no real taxpayer holds. */
const PAYER_TAX_ID = "B00000281";

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
    label("desktop.ledger.withholding.empty", { ejercicio: 2025 }),
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
  // Nothing is chosen for the person, and the figures start at zero.
  await expect(submit).toHaveAttribute("aria-disabled", "true");
  await expect(
    field(form, "desktop.ledger.withholding.amount.retencion"),
  ).toHaveValue("0.00");
  await field(form, "desktop.ledger.withholding.income_class").selectOption(
    "capital_mobiliario",
  );
  await field(form, "desktop.ledger.withholding.payer_tax_id").fill(
    PAYER_TAX_ID,
  );
  await field(form, "desktop.ledger.withholding.payer_legal_name").fill(
    "Banco de Ejemplo SA",
  );
  await field(form, "desktop.ledger.withholding.amount.retencion").fill(
    "150.00",
  );
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
    await labelled("desktop.ledger.withholding.amount.ingreso_a_cuenta").fill(
      "20",
    );
    await labelled(
      "desktop.ledger.withholding.amount.ingreso_a_cuenta_repercutido",
    ).fill("30");
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
    await labelled(
      "desktop.ledger.withholding.amount.ingreso_a_cuenta_repercutido",
    ).fill("0");
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

test("Health for another period counts only that period's own check, and says so until it is checked", async ({
  page: target,
}) => {
  await openLedger(target);
  const movements = head(target).getByRole("tab", {
    name: new RegExp(`^${label("desktop.ledger.section.movements")}`),
  });
  await expect(movements.locator("[data-slot=badge]")).toHaveCount(1);
  await openSetup(target, "health");
  const health = target.locator(".ledger-setup-health");
  await head(target)
    .getByRole("group", { name: label("desktop.ledger.period.label") })
    .getByRole("button", {
      name: label("desktop.ledger.period.previous"),
      exact: true,
    })
    .click();
  const strip = health.locator(".ledger-readiness");
  // Nothing of the page's earlier period is counted: only the muted pill,
  // and no count on the Movements tab.
  await expect(strip.locator("[data-readiness]")).toHaveCount(1);
  await expect(strip.locator("[data-readiness=unknown]")).toHaveCount(1);
  await expect(health.locator(".ledger-reasons")).toHaveCount(0);
  await expect(movements.locator("[data-slot=badge]")).toHaveCount(0);
  await health.locator(".ledger-health-preflight").click();
  await expect(strip.locator("[data-readiness=unknown]")).toHaveCount(0);
  const onHealth = await stripOf(health);
  // The Movements strip of the same period counts the same.
  await movements.click();
  const own = page(target).locator(".ledger-movements");
  await expect(own.locator("[data-readiness=unknown]")).toHaveCount(0);
  await expect.poll(() => stripOf(own)).toEqual(onHealth);
});
