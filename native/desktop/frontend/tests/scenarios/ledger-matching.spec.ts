import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { label } from "../support/strings";

// The To match pair queue over the scenario's `documents` ledger: one best
// invoice per movement, ranked on its evidence; tied invoices open a
// chooser and tied movements point at each other; staging a link takes
// away every suggestion that competes with it; one-sided links get a
// staged repair where a link mends both sides. Every value is synthetic.

const queue = (target: Page) => target.locator(".ledger-match-queue");
const item = (target: Page, description: string) =>
  queue(target).locator(".ledger-match-item").filter({ hasText: description });

async function openQueue(target: Page, scheme?: "light" | "dark") {
  if (scheme)
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
  await target.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&ledger=documents",
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-movements")).toBeVisible();
  await target.locator(".ledger-views").click();
  await target
    .getByRole("menuitemradio", { name: label("desktop.ledger.view.to_match") })
    .click();
  // The views menu stays open on a choice; it closes on Escape.
  await target.keyboard.press("Escape");
  await expect(target.getByRole("menu")).toHaveCount(0);
  // The view's side list; where the panel is closed, open it on its queue.
  const opened = await queue(target)
    .waitFor({ timeout: 2000 })
    .then(() => true)
    .catch(() => false);
  if (!opened) {
    await target.locator(".ledger-movements [role=gridcell]").nth(2).focus();
    await target.keyboard.press("Alt+KeyI");
    await target
      .locator(".ledger-panel")
      .getByRole("radio", {
        name: label("desktop.ledger.inspector.mode_match"),
      })
      .click();
  }
  await expect(queue(target)).toBeVisible();
  await expect(queue(target).locator(".ledger-match-list")).toBeVisible();
}

test("each movement shows its one best invoice with the evidence it stands on", async ({
  page: target,
}) => {
  await openQueue(target);
  const turia = item(target, "TRANSF IMPRENTA TURIA");
  await expect(turia).toContainText("GT-2026-0917");
  await expect(turia.locator(".ledger-match-chip").first()).toHaveText(
    label("desktop.ledger.matching.chip.number"),
  );
  await expect(turia).not.toHaveAttribute("data-ambiguous", "true");
  await expect(turia.locator(".ledger-match-link")).toHaveAccessibleDescription(
    label("desktop.ledger.matching.link_named", {
      number: "GT-2026-0917",
      description: "TRANSF IMPRENTA TURIA FRA GT-2026-0917",
    }),
  );
  // A movement already linked is never offered again.
  await expect(item(target, "ARROYO ASESORES SEPT")).toHaveCount(0);
});

test("tied invoices open a chooser, and the link chosen is staged", async ({
  page: target,
}) => {
  await openQueue(target);
  const arroyo = item(target, "ARROYO ASESORES CUOTA OCT");
  await expect(arroyo).toHaveAttribute("data-ambiguous", "true");
  await expect(arroyo.locator(".ledger-match-link")).toHaveCount(0);
  await arroyo.locator(".ledger-match-choose").click();
  const chooser = arroyo.locator(".ledger-match-chooser");
  await expect(chooser.getByRole("radio")).toHaveCount(2);
  const chosen = arroyo.locator(".ledger-match-chosen");
  await expect(chosen).toBeDisabled();
  await chooser.getByRole("radio", { name: /AA-2026-119/ }).check();
  await chosen.click();
  await expect(queue(target).locator(".ledger-match-toast")).toHaveText(
    label("desktop.ledger.matching.staged_toast"),
  );
  await expect(arroyo).toHaveCount(0);
  await expect(queue(target).locator(".ledger-match-staged")).toBeVisible();
  await expect(target.locator(".ledger-tray")).toBeVisible();
});

test("staging a link takes away the suggestions that compete for the same invoice", async ({
  page: target,
}) => {
  await openQueue(target);
  const norte = queue(target)
    .locator(".ledger-match-item")
    .filter({ hasText: "NORTE DIGITAL PAGO" });
  await expect(norte).toHaveCount(2);
  for (const at of [0, 1]) {
    await expect(norte.nth(at)).toHaveAttribute("data-ambiguous", "true");
    await expect(norte.nth(at)).toContainText(
      label("desktop.ledger.matching.partial"),
    );
  }
  await norte.first().locator(".ledger-match-link").click();
  await expect(norte).toHaveCount(0);
});

test("one-sided links get a staged repair where a link mends both sides", async ({
  page: target,
}) => {
  await openQueue(target);
  const oneSided = queue(target).locator(".ledger-match-inconsistency");
  const listed = oneSided.filter({ hasText: "CORREOS ENVIO PAQUETE" });
  await expect(listed).toHaveAttribute("data-direction", "invoice-only");
  const citing = oneSided.filter({ hasText: "PAPELERIA TRAZO 0412" });
  await expect(citing).toHaveAttribute("data-direction", "transaction-only");
  const lost = oneSided.filter({ hasText: "COPISTERIA CENTRO" });
  await expect(lost.locator(".ledger-match-no-repair")).toHaveText(
    label("desktop.ledger.matching.no_repair.invoice_missing"),
  );
  await listed.locator(".ledger-match-repair").click();
  await expect(listed).toContainText(
    label("desktop.ledger.matching.repair_staged"),
  );
  await expect(target.locator(".ledger-tray")).toBeVisible();
});

test("choosing a pair opens that movement in the same panel", async ({
  page: target,
}) => {
  await openQueue(target);
  await item(target, "TRANSF IMPRENTA TURIA")
    .locator(".ledger-match-pick")
    .click();
  await expect(target.locator(".ledger-panel")).toHaveAttribute(
    "data-mode",
    "movement",
  );
  await expect(queue(target)).toHaveCount(0);
});

// ---- Accessibility -------------------------------------------------------------

const engine = readFileSync(
  fileURLToPath(
    new URL("../../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);
async function audit(target: Page, scope: Locator) {
  await target.evaluate(engine);
  const selector = await scope.evaluate((node) => {
    node.setAttribute("data-audit", "");
    return "[data-audit]";
  });
  return target.evaluate(async (context) => {
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
    const result = await axe.run(context, { resultTypes: ["violations"] });
    return result.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.map((node) => node.target.join(" ")),
    }));
  }, selector);
}

for (const scheme of ["light", "dark"] as const)
  test(`the pair queue has no accessibility violations (${scheme})`, async ({
    page: target,
  }) => {
    await openQueue(target, scheme);
    await expect(target.locator("html")).toHaveAttribute("data-scheme", scheme);
    const arroyo = item(target, "ARROYO ASESORES CUOTA OCT");
    await arroyo.locator(".ledger-match-choose").click();
    expect(await audit(target, queue(target))).toEqual([]);
  });
