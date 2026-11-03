import { expect, test, type Locator, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { seedLayout } from "../support/layout";

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
const words = (key: string, language: Language = "en") =>
  label(`workspace.modelo.iva_wallet.${key}`, {}, language);
const wallet = (page: Page, language: Language = "en") =>
  page.getByRole("region", { name: words("title", language) });
const fact = (root: Locator, key: string, language: Language = "en") =>
  root
    .getByText(words(key, language), { exact: true })
    .locator("..")
    .locator("dd");

async function openWallet(
  page: Page,
  language: Language = "en",
  shape = "wallet",
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
  await page
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label", {}, language),
    })
    .fill("303");
  await grid
    .getByRole("row")
    .filter({ has: page.getByRole("gridcell", { name: "303", exact: true }) })
    .first()
    .dblclick();
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
  // 2026/1T -> 2024/4T; use the existing period editor's actual controls.
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
  await dialog.getByLabel(words("amount"), { exact: true }).fill("1200.50");
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
  await dialog.getByLabel(words("amount"), { exact: true }).fill("900.25");
  await expect(
    dialog.getByRole("button", { name: words("mode.correct"), exact: true }),
  ).toBeDisabled();
  await dialog
    .getByLabel(words("reason"), { exact: true })
    .fill("Correct the recorded opening balance.");
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
  await dialog.getByLabel(words("amount"), { exact: true }).fill("850.00");
  await dialog
    .getByLabel(words("reason"), { exact: true })
    .fill("Use the taxpayer's reviewed carry balance.");
  await expect(
    dialog.getByRole("button", { name: words("mode.override"), exact: true }),
  ).toBeDisabled();
  await dialog
    .getByLabel(words("evidence_locator"), { exact: true })
    .fill("fixture:reviewed-iva-balance-2026-1T");
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
  await expect(fact(wallet(page), "active_balance")).toContainText("900.25");
  const sent = await page.evaluate(() => window.__walletTest!.sent);
  expect(
    sent
      .filter((call) => call.definition === "modelo.iva-wallet.seed")
      .map((call) => call.payload),
  ).toEqual([{ period: { filing_year: 2024, code: "4T" }, amount: "1200.50" }]);
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
  await year.fill("2025");
  await year.blur();
  await expect(wallet(page).getByRole("alert")).toBeVisible();
  await page.evaluate(() => {
    window.__walletTest!.release!();
  });
  await expect(wallet(page).locator("dd")).toHaveCount(0);
  await year.fill("2026");
  await year.blur();
  await expect(fact(wallet(page), "lot_count")).toHaveText("0");
});
