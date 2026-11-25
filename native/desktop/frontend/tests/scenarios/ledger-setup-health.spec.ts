import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { label } from "../support/strings";
import {
  head,
  page,
  dataRows,
  button,
  field,
  openLedger,
  openSetup,
  area,
} from "../support/ledgerSetup";

// The Ledger page's Setup sections over the scenario host's made-up ledger: a readiness reason that opens the movements it names, Health's counts, a reset whose dry run the sealed declarations block, and an accessibility audit.

const engine = readFileSync(
  fileURLToPath(
    new URL("../../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);

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
