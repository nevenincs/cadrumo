import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { label } from "../support/strings";

// The Documents section over the scenario's `documents` ledger: readings
// waiting for review, their findings, the confirmation bound to the reading
// shown, the catalogue's duplicate check, the link a confirmation offers,
// a read off this computer only with its acknowledgement, folder intake
// with an outcome per document, the evidence records, and what left this
// computer. Every value is synthetic.

const DOMESTIKA = "factura-domestika-lettering.pdf";
const PLENOIL = "ticket-plenoil-1015.jpg";
const ARROYO = "factura-arroyo-2026-10.pdf";

const section = (target: Page) => target.locator(".ledger-documents");
const draft = (target: Page) => section(target).locator(".ledger-draft");
const tab = (target: Page, name: string) =>
  section(target).getByRole("tab", {
    name: new RegExp(`^${label(`desktop.ledger.documents.tab.${name}`)}`),
  });

async function openDocuments(
  target: Page,
  scheme?: "light" | "dark",
  shape = "documents",
) {
  if (scheme)
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off&ledger=${shape}`,
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator(".ledger-movements")).toBeVisible();
  await target
    .getByRole("tab", { name: label("desktop.ledger.section.documents") })
    .click();
  await expect(section(target)).toBeVisible();
}

async function choose(target: Page, name: string) {
  await section(target)
    .locator(".ledger-review-item")
    .filter({ hasText: name })
    .click();
  await expect(draft(target).getByRole("heading", { name })).toBeVisible();
}

async function kind(target: Page, which: "received" | "issued") {
  await draft(target)
    .locator(".ledger-draft-kind")
    .getByRole("radio", {
      name: label(`desktop.ledger.invoices.kind_choice.${which}`),
    })
    .click();
}

const calls = (target: Page) =>
  target.evaluate(
    () =>
      (window as unknown as { __scenarioHostCalls?: string[] })
        .__scenarioHostCalls ?? [],
  );

test("the queue lists each reading with its open findings", async ({
  page: target,
}) => {
  await openDocuments(target);
  const items = section(target).locator(".ledger-review-item");
  await expect(items).toHaveCount(3);
  await expect(items.filter({ hasText: PLENOIL })).toContainText("2");
  await expect(items.filter({ hasText: DOMESTIKA })).toContainText(
    label("desktop.ledger.documents.ready_to_confirm"),
  );
  await expect(tab(target, "review")).toContainText("3");
});

test("a clean reading is confirmed only with a kind and a country, then offers its movement's link", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, DOMESTIKA);
  // Provenance in plain words.
  await expect(
    draft(target).locator("[data-field=grand_total] .ledger-provenance"),
  ).toHaveText(
    label("desktop.ledger.documents.provenance", {
      origin: label("desktop.ledger.documents.origin.text_layer"),
      grounding: label("desktop.ledger.documents.grounding.reconciled"),
    }),
  );
  const confirm = draft(target).locator(".ledger-draft-confirm");
  const holds = draft(target).locator(".ledger-draft-holds");
  // Neither the kind nor the country has a default.
  await expect(holds).toContainText(
    label("desktop.ledger.documents.hold.choose_kind"),
  );
  await expect(holds).toContainText(
    label("desktop.ledger.documents.hold.country"),
  );
  await expect(confirm).toHaveAttribute("aria-disabled", "true");
  await confirm.click({ force: true });
  await expect(draft(target)).toBeVisible();
  expect(await calls(target)).not.toContain("ledger ledger.evidence.confirm");

  await kind(target, "received");
  await draft(target).locator(".ledger-draft-country-read").click();
  await expect(draft(target).locator(".ledger-draft-country")).toHaveValue(
    "ES",
  );
  await expect(holds).toHaveCount(0);
  await confirm.click();

  const done = section(target).locator(".ledger-draft-confirmed");
  await expect(done).toContainText(
    label("desktop.ledger.documents.confirmed", { number: "DK-2026-55120" }),
  );
  const made = await calls(target);
  // The confirmation is bound to a reading made just before it.
  expect(made.lastIndexOf("ledger ledger.evidence.extract")).toBeLessThan(
    made.lastIndexOf("ledger ledger.evidence.confirm"),
  );

  // The movement that settles it is offered as a permanent link.
  const offer = done.locator(".ledger-draft-link-offer");
  await expect(offer).toContainText("DOMESTIKA CURSO LETTERING");
  await offer.locator(".ledger-match-link").click();
  await expect(done.locator(".ledger-draft-link-staged")).toBeVisible();
  await expect(target.locator(".ledger-tray")).toBeVisible();
});

test("a reading that changed before confirming is shown again instead of confirmed", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, DOMESTIKA);
  await kind(target, "received");
  await draft(target).locator(".ledger-draft-country").fill("ES");
  await target.evaluate(
    (name) => window.__scenarioDocuments?.changeReading(name),
    DOMESTIKA,
  );
  await draft(target).locator(".ledger-draft-confirm").click();
  await expect(draft(target).getByRole("alert")).toContainText(
    label("desktop.ledger.documents.reading_changed"),
  );
  expect(await calls(target)).not.toContain("ledger ledger.evidence.confirm");
  // Reviewed again, the new reading is the one confirmed.
  await draft(target).locator(".ledger-draft-confirm").click();
  await expect(
    section(target).locator(".ledger-draft-confirmed"),
  ).toBeVisible();
});

test("findings are answered by choosing a reading or attesting with a reason", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, PLENOIL);
  const findings = draft(target).locator(".ledger-finding");
  await expect(findings).toHaveCount(2);
  await kind(target, "received");
  await draft(target).locator(".ledger-draft-country").fill("ES");
  const holds = draft(target).locator(".ledger-draft-holds");
  await expect(holds).toHaveText(
    label("desktop.ledger.documents.hold.findings"),
  );

  const identity = findings.nth(0);
  await identity
    .getByRole("radio", {
      name: label("desktop.ledger.documents.action.choose_candidate"),
    })
    .click();
  await identity.getByRole("radio", { name: /B87000007/ }).check();
  await expect(identity).toHaveAttribute("data-answered", "true");

  const closure = findings.nth(1);
  // A reading to choose from exists only where the reader offered some.
  await expect(
    closure.getByRole("radio", {
      name: label("desktop.ledger.documents.action.choose_candidate"),
    }),
  ).toBeDisabled();
  await closure
    .getByRole("radio", {
      name: label("desktop.ledger.documents.action.attest"),
    })
    .click();
  // An attestation needs its reason.
  await expect(closure).not.toHaveAttribute("data-answered", "true");
  await closure
    .getByLabel(label("desktop.ledger.documents.why_right"))
    .fill("The ticket rounds the total up.");
  await expect(closure).toHaveAttribute("data-answered", "true");
  await expect(holds).toHaveCount(0);
  await draft(target).locator(".ledger-draft-confirm").click();
  await expect(
    section(target).locator(".ledger-draft-confirmed"),
  ).toBeVisible();
});

test("a reading already in the catalogue offers to attach it or confirm anyway", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, ARROYO);
  await kind(target, "received");
  await draft(target).locator(".ledger-draft-country").fill("ES");
  const duplicate = draft(target).locator(".ledger-draft-duplicate");
  await expect(duplicate).toContainText(
    label("desktop.ledger.documents.duplicate", { number: "AA-2026-104" }),
  );
  await expect(draft(target).locator(".ledger-draft-holds")).toHaveText(
    label("desktop.ledger.documents.hold.duplicate"),
  );
  await duplicate.locator(".ledger-draft-attach").click();
  await expect(duplicate).toContainText(
    label("desktop.ledger.documents.attach_staged"),
  );
  await expect(target.locator(".ledger-tray")).toBeVisible();
  const anyway = duplicate.locator(".ledger-draft-anyway");
  await anyway.click();
  await expect(anyway).toHaveAttribute("aria-pressed", "true");
  await expect(draft(target).locator(".ledger-draft-holds")).toHaveCount(0);
});

test("a read off this computer needs its own acknowledgement every time", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, DOMESTIKA);
  const dialog = target.locator(".ledger-off-host");
  await draft(target).locator(".ledger-draft-off-host").click();
  await expect(dialog).toContainText(DOMESTIKA);
  await expect(dialog).toContainText("AGENT");
  const send = dialog.locator(".ledger-off-host-send");
  await expect(send).toBeDisabled();
  await dialog.locator(".ledger-off-host-agree").check();
  await send.click();
  await expect(dialog).toHaveCount(0);
  await expect(draft(target).locator(".ledger-draft-reread")).toBeEnabled();
  // The next read asks again.
  await draft(target).locator(".ledger-draft-off-host").click();
  await expect(dialog.locator(".ledger-off-host-agree")).not.toBeChecked();
  await target.keyboard.press("Escape");

  await tab(target, "sent").click();
  const sent = section(target).locator(".ledger-consent-dispatch");
  await expect(sent).toHaveCount(2);
  await expect(sent.filter({ hasText: DOMESTIKA })).toHaveCount(1);
});

test("folder intake asks for a direction and says each document's outcome", async ({
  page: target,
}) => {
  await openDocuments(target, undefined, "fixture");
  await tab(target, "folder").click();
  const folder = section(target).locator(".ledger-folder");
  await folder.locator(".ledger-folder-pick").click();
  await expect(folder.locator(".ledger-folder-chosen li")).toHaveCount(3);
  const add = folder.locator(".ledger-folder-add");
  await expect(add).toHaveAttribute("aria-disabled", "true");
  await add.click({ force: true });
  expect(await calls(target)).not.toContain("ledger ledger.evidence.batch");
  await folder
    .getByRole("radio", {
      name: label("desktop.ledger.invoices.kind_choice.received"),
    })
    .click();
  await add.click();
  const items = folder.locator(".ledger-batch-item");
  await expect(items).toHaveCount(3);
  await expect(folder.locator("[data-status=pending_review]")).toHaveCount(1);
  await expect(folder.locator("[data-status=ingested]")).toHaveCount(2);
  // What was added is waiting for review.
  await tab(target, "review").click();
  await expect(section(target).locator(".ledger-review-item")).toHaveCount(3);
});

test("an evidence record is corrected and removed one at a time", async ({
  page: target,
}) => {
  await openDocuments(target);
  await tab(target, "records").click();
  const records = section(target).locator(".ledger-record-item");
  await records.filter({ hasText: ARROYO }).click();
  const detail = section(target).locator(".ledger-record");
  const supplier = detail.getByLabel(
    label("desktop.ledger.documents.record.supplier"),
  );
  await supplier.fill("Arroyo Asesores SL");
  await detail
    .getByLabel(label("desktop.ledger.documents.record.taxable_base"))
    .fill("60,00");
  await expect(detail.locator(".ledger-record-save")).toBeDisabled();
  await detail
    .getByLabel(label("desktop.ledger.documents.record.taxable_base"))
    .fill("60.00");
  await detail.locator(".ledger-record-save").click();
  await expect(records.filter({ hasText: ARROYO })).toContainText(
    "Arroyo Asesores SL",
  );
  const count = await records.count();
  await detail.locator(".ledger-record-remove").click();
  await detail.locator(".ledger-record-remove-confirm").click();
  await expect(records).toHaveCount(count - 1);
});

test("no path reaches the section", async ({ page: target }) => {
  await openDocuments(target);
  await tab(target, "records").click();
  const text = await section(target).innerText();
  expect(text).not.toMatch(/[A-Za-z]:[\\/]|\/(?:Users|home)\//);
  await tab(target, "attachments").click();
  await expect(section(target).locator(".ledger-attachment")).toHaveCount(2);
  expect(await section(target).innerText()).not.toContain("msg-18c2f0a1");
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
  test(`every documents tab has no accessibility violations (${scheme})`, async ({
    page: target,
  }) => {
    await openDocuments(target, scheme);
    await expect(target.locator("html")).toHaveAttribute("data-scheme", scheme);
    await choose(target, PLENOIL);
    await kind(target, "received");
    const findings = draft(target).locator(".ledger-finding");
    await findings
      .nth(0)
      .getByRole("radio", {
        name: label("desktop.ledger.documents.action.choose_candidate"),
      })
      .click();
    expect(await audit(target, section(target))).toEqual([]);
    for (const name of [
      "records",
      "attachments",
      "folder",
      "sent",
      "readers",
    ]) {
      await tab(target, name).click();
      await expect(
        section(target).locator("[role=tabpanel][data-state=active]"),
      ).toBeVisible();
      await expect(section(target).locator("[aria-busy=true]")).toHaveCount(0);
      expect(await audit(target, section(target))).toEqual([]);
    }
    await tab(target, "review").click();
    await choose(target, DOMESTIKA);
    await draft(target).locator(".ledger-draft-off-host").click();
    // A dialog fading in has text of partial contrast: audit it once drawn.
    const dialog = target.locator(".ledger-off-host");
    await expect(dialog).toBeVisible();
    await dialog.evaluate((element) =>
      Promise.all(
        element.getAnimations({ subtree: true }).map((a) => a.finished),
      ),
    );
    expect(await audit(target, dialog)).toEqual([]);
  });
