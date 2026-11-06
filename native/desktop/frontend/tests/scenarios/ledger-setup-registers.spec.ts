import { expect, test } from "@playwright/test";
import { windowFixture } from "../support/windowFixtures";
import { readFileSync } from "node:fs";
import { label } from "../support/strings";
import {
  button,
  field,
  openLedger,
  openSetup,
  openAssets,
  area,
} from "../support/ledgerSetup";

// The Ledger page's Setup sections over the scenario host's made-up ledger: an own capital good named from its year, and a prorrata election the register refuses until its reference is given.

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

/** The sentences the prorrata register serves with its refusals, in English,
 * as the generated fixture holds them. */
const PRORRATA_WORDS = (
  JSON.parse(
    readFileSync(
      windowFixture("ledger-served-words", "ledgerServedWords"),
      "utf8",
    ),
  ) as { prorrata: Record<string, Record<string, string>> }
).prorrata;

const prorrataRefused = (reason: string) => PRORRATA_WORDS[reason]!.en!;

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
