import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { label } from "../support/strings";
import { seedLayout } from "../support/layout";
import { MODELO_FIXTURES } from "../support/windowFixtures";

type Language = "en" | "es" | "ca" | "hu";
declare global {
  interface Window {
    __walletTest?: {
      sent: { definition: string; payload: unknown }[];
      failBalance: boolean;
      failForm: boolean;
      loseSettlement: boolean;
      balanceFailures: number;
      formFailures: number;
      release?: () => void;
    };
  }
}
/** A wallet write the scenario answers, as the backend wrote it: the window
 * must send what it carries for the scenario to answer it. */
type Written = {
  period: { filing_year: number; code: string };
  amount: string;
  reason?: string;
  evidence_locator?: string;
};
const served = <T>(name: string): T =>
  JSON.parse(
    readFileSync(new URL(`${name}.json`, MODELO_FIXTURES), "utf8"),
  ) as T;
const SEEDED = served<Written>("iva-wallet-seed");
const CORRECTED = served<Written>("iva-wallet-correct");
const OVERRIDDEN = served<Written>("iva-wallet-override");
/** The year the scenario's balance was read at. */
const AS_OF_YEAR = served<{ as_of_year: number }>(
  "iva-wallet-balance-empty",
).as_of_year;
const words = (key: string, language: Language = "en") =>
  label(`workspace.modelo.iva_wallet.${key}`, {}, language);
const wallet = (page: Page, language: Language = "en") =>
  page.getByRole("region", { name: words("title", language) });
const fact = (root: Locator, key: string, language: Language = "en") =>
  root
    .getByText(words(key, language), { exact: true })
    .locator("..")
    .locator("dd");

async function openWalletForm(
  page: Page,
  language: Language = "en",
  shape = "wallet",
  modelo = "303",
  offersIvaWallet?: boolean,
) {
  await seedLayout(page, {
    layout: {
      agentShown: false,
      tuiShown: false,
      docsShown: true,
      page: "docs",
    },
  });
  await page.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&lang=${language}&modelo=${shape}`,
  );
  await page.locator("[data-rail=declarations]").click();
  const grid = page.getByRole("grid", {
    name: label("workspace.declarations.destination.overview", {}, language),
  });
  await expect(grid.getByRole("row").nth(1)).toBeVisible({ timeout: 15_000 });
  if (offersIvaWallet !== undefined) {
    await page.evaluate((offers) => {
      const port = window.__fixtureModelo!;
      const form = port.form;
      port.form = async (...args) => {
        const answer = await form(...args);
        return {
          ...answer,
          form: {
            ...answer.form,
            form: { ...answer.form.form, offers_iva_wallet: offers },
          },
        };
      };
    }, offersIvaWallet);
  }
  await page
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label", {}, language),
    })
    .fill(modelo);
  await grid
    .getByRole("row")
    .filter({ has: page.getByRole("gridcell", { name: modelo, exact: true }) })
    .first()
    .dblclick();
  await expect(
    page.getByRole("tab", {
      name: new RegExp(`^${label("desktop.modelo.view.form", {}, language)}`),
    }),
  ).toBeVisible();
}

async function openWallet(
  page: Page,
  language: Language = "en",
  shape = "wallet",
) {
  await openWalletForm(page, language, shape);
  await page
    .getByRole("tab", {
      name: label("desktop.modelo.view.iva_wallet", {}, language),
      exact: true,
    })
    .click();
  await expect(wallet(page, language)).toBeVisible();
}

async function observeRequests(page: Page) {
  await page.evaluate(() => {
    const state = (window.__walletTest = {
      sent: [] as { definition: string; payload: unknown }[],
      failBalance: false,
      failForm: false,
      loseSettlement: false,
      balanceFailures: 0,
      formFailures: 0,
    });
    const port = window.__fixtureModelo!;
    const submit = port.submit;
    const form = port.form;
    port.form = (...args) => {
      if (state.failForm) {
        state.formFailures++;
        return Promise.reject({ code: "unavailable" });
      }
      return form(...args);
    };
    port.submit = async (...args) => {
      state.sent.push({
        definition: args[0],
        payload: structuredClone(args[1]),
      });
      if (args[0] === "modelo.iva-wallet.balance" && state.failBalance) {
        state.balanceFailures++;
        throw { code: "unavailable" };
      }
      const answer = await submit(...args);
      if (args[0] === "modelo.iva-wallet.seed" && state.loseSettlement)
        throw { code: "unknown", operation_id: answer.operation_id };
      return answer;
    };
  });
}

async function manage(page: Page) {
  await wallet(page)
    .getByRole("button", { name: words("manage") })
    .click();
  return page.getByRole("dialog", { name: words("title") });
}
async function sourcePeriod(dialog: Locator) {
  // The declaration's 1T -> 4T two years before; use the existing period editor's actual controls.
  for (let i = 0; i < 5; i++)
    await dialog
      .getByRole("button", {
        name: label("desktop.ledger.period.previous"),
        exact: true,
      })
      .click();
}
async function seed(page: Page) {
  const dialog = await manage(page);
  await sourcePeriod(dialog);
  await dialog.getByLabel(words("amount"), { exact: true }).fill(SEEDED.amount);
  await dialog
    .getByRole("button", { name: words("mode.seed"), exact: true })
    .click();
  return dialog;
}

for (const language of ["en", "es", "ca", "hu"] as const) {
  test(`IVA wallet balance and empty expiry use served facts in ${language}`, async ({
    page,
  }, info) => {
    await openWallet(page, language);
    const root = wallet(page, language);
    await expect(fact(root, "lot_count", language)).toHaveText("0");
    await expect(fact(root, "next_expiry_year", language)).toHaveText(
      words("expiry_not_reported", language),
    );
    for (const key of [
      "total_balance",
      "active_balance",
      "expired_balance",
      "unallocated_applied_amount",
    ])
      await expect(fact(root, key, language)).toContainText("0");
    await expect(root).not.toContainText("workspace.modelo.");
    await page.setViewportSize({ width: 760, height: 900 });
    await expect(
      root.getByRole("button", { name: words("manage", language) }),
    ).toBeVisible();
    if (language === "en")
      await page.screenshot({ path: info.outputPath("wallet-balance.png") });
  });
}

for (const [modelo, offers] of [
  ["303", false],
  ["130", true],
] as const) {
  test(`served wallet capability ${offers} controls entry for modelo ${modelo}`, async ({
    page,
  }) => {
    await openWalletForm(page, "en", "fixture", modelo, offers);
    const tab = page.getByRole("tab", {
      name: label("desktop.modelo.view.iva_wallet"),
      exact: true,
    });
    if (offers) {
      await expect(tab).toBeVisible();
      await tab.click();
      await expect(wallet(page)).toBeVisible();
    } else {
      await expect(tab).toHaveCount(0);
      await expect(wallet(page)).toHaveCount(0);
    }
  });
}

test("normal uncalculated 303 exposes the wallet and read failure never becomes a zero balance", async ({
  page,
}) => {
  await openWallet(page, "en", "fixture");
  await expect(wallet(page).getByRole("alert")).toContainText(
    words("read_failed"),
  );
  await expect(wallet(page).locator("dd")).toHaveCount(0);
  await expect(
    wallet(page).getByRole("button", { name: words("manage") }),
  ).toBeEnabled();
});

test("wallet records exact amounts, preserves separate drafts, and does not recalculate the declaration", async ({
  page,
}, info) => {
  await openWallet(page);
  await expect(fact(wallet(page), "lot_count")).toHaveText("0");
  await observeRequests(page);
  const dialog = await seed(page);
  await expect(dialog.getByRole("status")).toContainText(words("recorded"));
  await expect(dialog.getByRole("status")).toContainText(
    words("receipt.provenance.operator_seed"),
  );
  await expect(dialog.getByRole("status")).toContainText(
    words("receipt.not_reported"),
  );
  await expect(
    dialog.getByLabel(words("action"), { exact: true }),
  ).toBeEnabled();
  await dialog
    .getByLabel(words("action"), { exact: true })
    .selectOption("correct");
  await expect(dialog.getByLabel(words("amount"), { exact: true })).toHaveValue(
    "",
  );
  await sourcePeriod(dialog);
  await dialog
    .getByLabel(words("amount"), { exact: true })
    .fill(CORRECTED.amount);
  await expect(
    dialog.getByRole("button", { name: words("mode.correct"), exact: true }),
  ).toBeDisabled();
  await dialog
    .getByLabel(words("reason"), { exact: true })
    .fill(CORRECTED.reason!);
  await dialog
    .getByRole("button", { name: words("mode.correct"), exact: true })
    .click();
  await expect(dialog.getByRole("status")).toContainText(
    words("previous_amount"),
  );
  await expect(
    dialog.getByLabel(words("action"), { exact: true }),
  ).toBeEnabled();
  await dialog
    .getByLabel(words("action"), { exact: true })
    .selectOption("override");
  await dialog
    .getByLabel(words("amount"), { exact: true })
    .fill(OVERRIDDEN.amount);
  await dialog
    .getByLabel(words("reason"), { exact: true })
    .fill(OVERRIDDEN.reason!);
  await expect(
    dialog.getByRole("button", { name: words("mode.override"), exact: true }),
  ).toBeDisabled();
  await dialog
    .getByLabel(words("evidence_locator"), { exact: true })
    .fill(OVERRIDDEN.evidence_locator!);
  await dialog
    .getByRole("button", { name: words("mode.override"), exact: true })
    .click();
  await expect(dialog.getByRole("status")).toContainText(
    words("receipt.authority.taxpayer_override"),
  );
  await expect(dialog.getByRole("status")).toContainText(
    words("receipt.divergence.override"),
  );
  await page.screenshot({ path: info.outputPath("wallet-override.png") });
  await dialog
    .getByRole("button", {
      name: label("workspace.modelo.key.close"),
      exact: true,
    })
    .click();
  await expect(fact(wallet(page), "lot_count")).toHaveText("1");
  await expect(fact(wallet(page), "active_balance")).toContainText(
    CORRECTED.amount,
  );
  const sent = await page.evaluate(() => window.__walletTest!.sent);
  expect(
    sent
      .filter((call) => call.definition === "modelo.iva-wallet.seed")
      .map((call) => call.payload),
  ).toEqual([{ period: SEEDED.period, amount: SEEDED.amount }]);
  expect(
    sent.filter((call) => call.definition === "modelo.iva-wallet.override"),
  ).toHaveLength(1);
  expect(
    sent.some((call) => /recalculate|calculate/.test(call.definition)),
  ).toBe(false);
});

test("closing a pending wallet dialog keeps its owner visible and does not imply settlement", async ({
  page,
}) => {
  await openWallet(page);
  await expect(fact(wallet(page), "lot_count")).toHaveText("0");
  await observeRequests(page);
  await page.evaluate(() => {
    const port = window.__fixtureModelo!;
    const submit = port.submit;
    port.submit = async (...args) => {
      const answer = await submit(...args);
      if (args[0] === "modelo.iva-wallet.seed")
        await new Promise<void>((resolve) => {
          window.__walletTest!.release = resolve;
        });
      return answer;
    };
  });
  const dialog = await seed(page);
  await expect
    .poll(() => page.evaluate(() => !!window.__walletTest!.release))
    .toBe(true);
  await dialog
    .getByRole("button", {
      name: label("workspace.modelo.key.close"),
      exact: true,
    })
    .click();
  await expect(
    page
      .locator("[aria-busy=true]")
      .filter({ hasText: words("title") })
      .first(),
  ).toBeVisible();
  await expect(wallet(page).locator("dd")).toHaveCount(0);
  await expect(
    wallet(page).getByRole("button", { name: words("manage") }),
  ).toBeDisabled();
  await page.evaluate(() => {
    window.__walletTest!.release!();
  });
  const notice = page.locator(".modelo-write-hold");
  await expect(notice).toBeVisible();
  await notice
    .getByRole("button", { name: label("workspace.modelo.read_again") })
    .click();
  await expect(notice).toHaveCount(0);
  await expect(fact(wallet(page), "lot_count")).toHaveText("1");
});

test("an unknown wallet write survives dialog close and requires both balance and declaration recovery", async ({
  page,
}) => {
  await openWallet(page);
  await expect(fact(wallet(page), "lot_count")).toHaveText("0");
  await observeRequests(page);
  await page.evaluate(() => {
    window.__walletTest!.loseSettlement = true;
  });
  const dialog = await seed(page);
  await expect(dialog.locator(".modelo-write-hold")).toBeVisible();
  await dialog
    .getByRole("button", {
      name: label("workspace.modelo.key.close"),
      exact: true,
    })
    .click();
  const notice = page.locator(".modelo-write-hold");
  await expect(notice).toBeVisible();
  await expect(wallet(page).locator("dd")).toHaveCount(0);
  await expect(
    wallet(page).getByRole("button", { name: words("manage") }),
  ).toBeDisabled();
  await page
    .locator(".declarations-workspace")
    .getByRole("button", {
      name: label("workspace.declarations.destination.overview"),
      exact: true,
    })
    .click();
  await page
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label"),
    })
    .fill("130");
  const grid = page.getByRole("grid", {
    name: label("workspace.declarations.destination.overview"),
  });
  await grid
    .getByRole("row")
    .filter({ has: page.getByRole("gridcell", { name: "130", exact: true }) })
    .first()
    .dblclick();
  await expect(notice).toBeVisible();
  await expect(
    notice.getByRole("button", { name: label("workspace.modelo.read_again") }),
  ).toHaveCount(0);
  const row = page
    .getByRole("tabpanel")
    .filter({ has: page.getByRole("row") })
    .first()
    .getByRole("row")
    .filter({ has: page.getByRole("gridcell", { name: "06", exact: true }) });
  await row.getByRole("gridcell").nth(2).getByRole("button").click();
  const entry = page.getByRole("textbox", {
    name: label("workspace.modelo.editor.new_value_for_box", { box: "06" }),
  });
  await entry.fill("1,234.56");
  await entry.press("Enter");
  await expect(row).toContainText(label("workspace.modelo.attention.staged"));
  const ownerLink = page.getByRole("button", {
    name: new RegExp(`^${words("title")}.*303`),
  });
  await ownerLink.click();
  const leaving = page.getByRole("dialog", {
    name: label("desktop.ledger.leave.title"),
  });
  await leaving
    .getByRole("button", {
      name: label("desktop.ledger.leave.cancel"),
      exact: true,
    })
    .last()
    .click();
  await expect(row).toContainText(label("workspace.modelo.attention.staged"));
  await ownerLink.click();
  await leaving
    .getByRole("button", {
      name: label("workspace.modelo.leave.discard"),
      exact: true,
    })
    .click();
  await page
    .getByRole("tab", {
      name: label("desktop.modelo.view.iva_wallet"),
      exact: true,
    })
    .click();
  await notice
    .getByRole("button", {
      name: label("workspace.modelo.write_hold.check_status"),
    })
    .click();
  await page.evaluate(() => {
    window.__walletTest!.failBalance = true;
  });
  const reload = notice.getByRole("button", {
    name: label("workspace.modelo.read_again"),
  });
  await reload.click();
  await expect
    .poll(() => page.evaluate(() => window.__walletTest!.balanceFailures))
    .toBe(1);
  await expect(reload).toBeEnabled();
  await expect(notice).toBeVisible();
  expect(await page.evaluate(() => window.__walletTest!.formFailures)).toBe(0);
  await page.evaluate(() => {
    window.__walletTest!.failBalance = false;
    window.__walletTest!.failForm = true;
  });
  await reload.click();
  await expect
    .poll(() => page.evaluate(() => window.__walletTest!.formFailures))
    .toBe(1);
  await expect(reload).toBeEnabled();
  await expect(notice).toBeVisible();
  await page.evaluate(() => {
    window.__walletTest!.failForm = false;
  });
  await reload.click();
  await expect(notice).toHaveCount(0);
  await expect(fact(wallet(page), "lot_count")).toHaveText("1");
  expect(
    await page.evaluate(
      () =>
        window.__walletTest!.sent.filter(
          (call) => call.definition === "modelo.iva-wallet.seed",
        ).length,
    ),
  ).toBe(1);
});

test("changing the reference year cannot retain figures from the previous read", async ({
  page,
}) => {
  await openWallet(page);
  await expect(fact(wallet(page), "lot_count")).toHaveText("0");
  await observeRequests(page);
  await page.evaluate(() => {
    const port = window.__fixtureModelo!;
    const submit = port.submit;
    let deferred = false;
    port.submit = async (...args) => {
      const answer = await submit(...args);
      if (args[0] === "modelo.iva-wallet.balance" && !deferred) {
        deferred = true;
        await new Promise<void>((resolve) => {
          window.__walletTest!.release = resolve;
        });
      }
      return answer;
    };
  });
  await wallet(page)
    .getByRole("button", { name: words("reload") })
    .click();
  await expect
    .poll(() => page.evaluate(() => !!window.__walletTest!.release))
    .toBe(true);
  const year = wallet(page).getByLabel(words("as_of_year"), { exact: true });
  await year.fill(String(AS_OF_YEAR - 1));
  await year.blur();
  await expect(wallet(page).getByRole("alert")).toBeVisible();
  await page.evaluate(() => {
    window.__walletTest!.release!();
  });
  await expect(wallet(page).locator("dd")).toHaveCount(0);
  await year.fill(String(AS_OF_YEAR));
  await year.blur();
  await expect(fact(wallet(page), "lot_count")).toHaveText("0");
});

/** The 130's export is sent again and its settlement lost, so the declaration
 * holds an operation the window cannot yet place; a later status check finds
 * it settled. */
async function loseExport(page: Page) {
  await page
    .locator(".declarations-workspace")
    .getByRole("tab", { name: label("workspace.modelo.filing.title") })
    .click();
  await page
    .getByRole("button", {
      name: label("workspace.modelo.filing.export_again"),
    })
    .click();
  await expect(
    page
      .locator(".modelo-write-hold")
      .filter({ hasText: label("workspace.modelo.write_hold.unknown") })
      .first(),
  ).toBeVisible();
  await page.evaluate(() => {
    window.__fixtureModelo!.observe = async (operation) => ({
      kind: "settled",
      operation_id: operation,
      revision: 3,
      result: {},
    });
  });
}

async function openOtherDeclaration(page: Page, modelo: string) {
  await page
    .locator(".declarations-workspace")
    .getByRole("button", {
      name: label("workspace.declarations.destination.overview"),
      exact: true,
    })
    .click();
  await page
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label"),
    })
    .fill(modelo);
  await page
    .getByRole("grid", {
      name: label("workspace.declarations.destination.overview"),
    })
    .getByRole("row")
    .filter({ has: page.getByRole("gridcell", { name: modelo, exact: true }) })
    .first()
    .dblclick();
  await page
    .getByRole("tab", {
      name: label("desktop.modelo.view.iva_wallet"),
      exact: true,
    })
    .click();
  await expect(wallet(page)).toBeVisible();
}

test("another declaration that reads no IVA wallet neither shows its operation on the wallet nor locks it", async ({
  page,
}) => {
  await openWalletForm(page, "en", "export-unknown", "130");
  await loseExport(page);
  await openOtherDeclaration(page, "303");
  // The fixture serves no balance: a read that ran says so; a held one shows nothing.
  await expect(
    wallet(page)
      .getByRole("alert")
      .filter({ hasText: words("read_failed") }),
  ).toBeVisible();
  await expect(wallet(page).locator(".modelo-write-hold")).toHaveCount(0);
  await expect(
    wallet(page).getByRole("button", { name: words("reload") }),
  ).toBeEnabled();
  await expect(
    wallet(page).getByRole("button", { name: words("manage") }),
  ).toBeEnabled();
});

test("another wallet-reading declaration locks the wallet only until Check status finds its operation finished", async ({
  page,
}) => {
  // Both declarations read the wallet here, so the other's open operation
  // may still change the basis the wallet's actions read.
  await openWalletForm(page, "en", "export-unknown", "130", true);
  await loseExport(page);
  await openOtherDeclaration(page, "303");
  const notice = wallet(page).locator(".modelo-write-hold");
  await expect(notice).toHaveCount(1);
  await expect(
    wallet(page).getByRole("button", { name: words("manage") }),
  ).toBeDisabled();
  await notice
    .getByRole("button", {
      name: label("workspace.modelo.write_hold.check_status"),
    })
    .click();
  // Settled: what stays to reload belongs to the other declaration.
  await expect(notice).toHaveCount(0);
  // The fixture serves no balance: a read that ran says so; a held one shows nothing.
  await expect(
    wallet(page)
      .getByRole("alert")
      .filter({ hasText: words("read_failed") }),
  ).toBeVisible();
  await expect(
    wallet(page).getByRole("button", { name: words("manage") }),
  ).toBeEnabled();
});
