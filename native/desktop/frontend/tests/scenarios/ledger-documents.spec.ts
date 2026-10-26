import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { agentColumn } from "../support/agent";
import { seedLayout } from "../support/layout";
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
  // The button that answered the country went away: confirming is next.
  await expect(confirm).toBeFocused();
  await expect(holds).toHaveCount(0);
  await target.keyboard.press("Enter");

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
  // The confirm button is gone: its link is the next step.
  const link = offer.locator(".ledger-match-link");
  await expect(link).toBeFocused();
  await target.keyboard.press("Enter");
  await expect(done.locator(".ledger-draft-link-staged")).toBeVisible();
  await expect(target.locator(".ledger-tray")).toBeVisible();
  // And once linked, the next document still to review.
  const focused = section(target).locator(".ledger-review-item:focus");
  await expect(focused).toHaveCount(1);
  await expect(focused).not.toContainText(DOMESTIKA);
});

test("fields are as wide as what they hold", async ({ page: target }) => {
  await openDocuments(target);
  await choose(target, DOMESTIKA);
  await kind(target, "received");
  const width = async (field: string) =>
    (await draft(target)
      .locator(`[data-field=${field}] .ledger-draft-input`)
      .boundingBox())!.width;
  const amount = await width("taxable_base");
  const rate = await width("iva_rate");
  const date = await width("invoice_date");
  const number = await width("invoice_number");
  const name = await width("counterparty_name");
  // A figure and a rate share one narrow width; a date is wider, other text
  // wider still, and a name takes the row.
  expect(Math.abs(amount - rate)).toBeLessThan(1);
  expect(date).toBeGreaterThan(amount);
  expect(number).toBeGreaterThan(date);
  expect(name).toBeGreaterThan(number);
});

test("a flagged field's glyph goes to the question about it", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, PLENOIL);
  for (const [field, reason] of [
    ["supplier_tax_id", "ambiguous_identity"],
    ["grand_total", "closure_discrepancy"],
  ] as const) {
    const glyph = draft(target).locator(
      `[data-field=${field}] .ledger-provenance-question`,
    );
    await expect(glyph).toHaveAccessibleName(
      new RegExp(
        label("desktop.ledger.documents.go_to_question", {
          reason: label(`desktop.ledger.documents.reason.${reason}`),
        }),
      ),
    );
    await glyph.click();
    const finding = draft(target).locator(".ledger-finding:focus");
    await expect(finding).toContainText(
      label(`desktop.ledger.documents.reason.${reason}`),
    );
    await expect(finding).toBeInViewport();
  }
  // A field no finding asks about keeps its plain glyph.
  await expect(
    draft(target).locator("[data-field=iva_rate] .ledger-provenance-question"),
  ).toHaveCount(0);
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
  // The total is worked out from the base and the IVA whatever the ticket
  // prints: the finding says what is saved, and asks only for the reason
  // it is accepted.
  await expect(closure.locator(".ledger-finding-worked")).toHaveText(
    label("desktop.ledger.documents.worked_out", {
      field: label("desktop.ledger.documents.field.grand_total"),
      printed: "58.40",
    }),
  );
  await expect(closure.getByRole("radio")).toHaveCount(0);
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

const viewer = (target: Page) => draft(target).locator(".ledger-document");
const pageRequests = (target: Page) =>
  calls(target).then((all) =>
    all.filter((call) => call === "ledger ledger.evidence.page"),
  );

test("a PDF's page is shown beside what was read, with its pages and zoom", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, DOMESTIKA);
  const image = viewer(target).getByRole("img", {
    name: label("desktop.ledger.documents.viewer.image", {
      file: DOMESTIKA,
      page: 1,
    }),
  });
  await expect(image).toBeVisible();
  await expect(image).toHaveAttribute("src", /^data:image\/png;base64,/);
  const pages = viewer(target).locator(".ledger-document-page");
  await expect(pages).toHaveText(
    label("desktop.ledger.documents.viewer.page", { page: 1, count: 2 }),
  );
  const previous = viewer(target).getByRole("button", {
    name: label("desktop.ledger.documents.viewer.previous"),
  });
  const next = viewer(target).getByRole("button", {
    name: label("desktop.ledger.documents.viewer.next"),
  });
  await expect(previous).toBeDisabled();
  await next.click();
  await expect(pages).toHaveText(
    label("desktop.ledger.documents.viewer.page", { page: 2, count: 2 }),
  );
  await expect(
    viewer(target).getByRole("img", {
      name: label("desktop.ledger.documents.viewer.image", {
        file: DOMESTIKA,
        page: 2,
      }),
    }),
  ).toBeVisible();
  await expect(next).toBeDisabled();

  // Zooming widens the page inside its frame; fit returns it to the width.
  const zoom = viewer(target).locator(".ledger-document-zoom");
  await expect(zoom).toHaveText(
    label("desktop.ledger.documents.viewer.zoom", { percent: 100 }),
  );
  const frame = viewer(target).locator(".ledger-document-frame");
  const fitted = await frame.evaluate((at) => at.clientWidth);
  await viewer(target)
    .getByRole("button", {
      name: label("desktop.ledger.documents.viewer.zoom_in"),
    })
    .click();
  await expect(zoom).toHaveText(
    label("desktop.ledger.documents.viewer.zoom", { percent: 150 }),
  );
  await expect
    .poll(() =>
      viewer(target)
        .locator(".ledger-document-image")
        .evaluate((at) => at.getBoundingClientRect().width),
    )
    .toBeGreaterThan(fitted * 1.4);
  await viewer(target)
    .getByRole("button", { name: label("desktop.ledger.documents.viewer.fit") })
    .click();
  await expect(zoom).toHaveText(
    label("desktop.ledger.documents.viewer.zoom", { percent: 100 }),
  );
});

test("an image has no page buttons, and another document drops the page shown", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, PLENOIL);
  await expect(
    viewer(target).getByRole("img", {
      name: label("desktop.ledger.documents.viewer.image", {
        file: PLENOIL,
        page: 1,
      }),
    }),
  ).toBeVisible();
  await expect(viewer(target).locator(".ledger-document-next")).toHaveCount(0);

  await choose(target, ARROYO);
  await expect(
    viewer(target).getByRole("img", {
      name: label("desktop.ledger.documents.viewer.image", {
        file: ARROYO,
        page: 1,
      }),
    }),
  ).toBeVisible();
  await expect(
    viewer(target).getByRole("img", {
      name: label("desktop.ledger.documents.viewer.image", {
        file: PLENOIL,
        page: 1,
      }),
    }),
  ).toHaveCount(0);
  expect((await pageRequests(target)).length).toBeGreaterThanOrEqual(2);
});

test("a page the runtime refuses to draw is said in words", async ({
  page: target,
}) => {
  await openDocuments(target);
  await target.evaluate(
    (name) =>
      (
        window as unknown as {
          __scenarioDocuments: {
            refusePage(file: string, reason: string | null): void;
          };
        }
      ).__scenarioDocuments.refusePage(name, "TOO_LARGE"),
    ARROYO,
  );
  // The queue may have opened this document already; showing it again
  // reads its page again.
  await choose(target, DOMESTIKA);
  await choose(target, ARROYO);
  const refused = viewer(target).locator(".ledger-document-refused");
  await expect(refused).toHaveText(
    label("desktop.ledger.documents.viewer.refused.too_large"),
  );
  await expect(viewer(target).getByRole("img")).toHaveCount(0);
  // The reading itself stays reviewable.
  await expect(
    draft(target).getByRole("heading", { name: ARROYO }),
  ).toBeVisible();
});

const paused = (target: Page) =>
  target.locator(".ledger-page .ledger-paused [role=alert]");
const pauseFindings = (target: Page) =>
  target.locator(".ledger-page .ledger-findings");
const nextWrites = (target: Page, outcomes: "unknown"[]) =>
  target.evaluate(
    (next) =>
      (
        window as unknown as {
          __scenarioLedger: { nextWrites(outcomes: string[]): void };
        }
      ).__scenarioLedger.nextWrites(next),
    outcomes,
  );

test("a confirmation not seen to settle is settled by reading the queue and the catalogue", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, DOMESTIKA);
  await kind(target, "received");
  await draft(target).locator(".ledger-draft-country-read").click();
  // Bound to a fresh reading first, so the confirmation is the one write.
  await draft(target).locator(".ledger-draft-reread").click();
  await expect(draft(target).locator(".ledger-draft-reread")).toBeEnabled();
  await nextWrites(target, ["unknown"]);
  await draft(target).locator(".ledger-draft-confirm").click();
  await expect(paused(target)).toBeVisible();
  await paused(target).locator(".ledger-paused-reread").click();
  await expect(pauseFindings(target)).toContainText(
    label("desktop.ledger.paused.found_saved", {
      movement: label("desktop.ledger.section.documents"),
    }),
  );
  await expect(paused(target)).toHaveCount(0);
});

test("a record correction not seen to settle is settled by reading the record back", async ({
  page: target,
}) => {
  await openDocuments(target);
  await tab(target, "records").click();
  await section(target)
    .locator(".ledger-record-item")
    .filter({ hasText: ARROYO })
    .click();
  const detail = section(target).locator(".ledger-record");
  await detail
    .getByLabel(label("desktop.ledger.documents.record.supplier"))
    .fill("Arroyo Asesores SL");
  await nextWrites(target, ["unknown"]);
  await detail.locator(".ledger-record-save").click();
  await expect(paused(target)).toBeVisible();
  await paused(target).locator(".ledger-paused-reread").click();
  await expect(pauseFindings(target)).toContainText(
    label("desktop.ledger.paused.found_saved", { movement: ARROYO }),
  );
  await expect(paused(target)).toHaveCount(0);
});

test("the ticket stays on screen beside the question it is needed for, and after it is confirmed", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1440, height: 900 });
  await openDocuments(target);
  await choose(target, PLENOIL);
  // With a document open the list is a rail that keeps the open findings.
  const list = section(target).locator(".ledger-review-list");
  const rail = (await list.boundingBox())!;
  expect(rail.width).toBeLessThan(100);
  await expect(
    section(target).locator(".ledger-review-item").filter({ hasText: PLENOIL }),
  ).toContainText("2");
  const image = viewer(target).getByRole("img");
  await expect(image).toBeVisible();
  await draft(target)
    .locator("[data-field=supplier_tax_id] .ledger-provenance-question")
    .click();
  const finding = draft(target).locator(".ledger-finding:focus");
  await expect(finding).toBeInViewport();
  // The page is beside the question, not scrolled away above it.
  await expect(image).toBeInViewport();
  const page = (await image.boundingBox())!;
  const question = (await finding.boundingBox())!;
  expect(page.x + page.width).toBeLessThanOrEqual(question.x);

  await kind(target, "received");
  await draft(target).locator(".ledger-draft-country").fill("ES");
  const findings = draft(target).locator(".ledger-finding");
  await findings
    .nth(0)
    .getByRole("radio", {
      name: label("desktop.ledger.documents.action.choose_candidate"),
    })
    .click();
  await findings
    .nth(0)
    .getByRole("radio", { name: /B87000001/ })
    .check();
  await findings
    .nth(1)
    .getByLabel(label("desktop.ledger.documents.why_right"))
    .fill("Rounding");
  await draft(target).locator(".ledger-draft-confirm").click();
  await expect(
    section(target).locator(".ledger-draft-confirmed"),
  ).toBeVisible();
  await expect(viewer(target).getByRole("img")).toBeInViewport();

  // The list opens again in full, and folds back.
  await list.locator(".ledger-review-list-toggle").click();
  await expect(list).toHaveAttribute("data-open", "true");
  expect((await list.boundingBox())!.width).toBeGreaterThan(rail.width * 3);
});

test("a confirmed ticket no movement settles offers the movements near its day, and stages a permanent link", async ({
  page: target,
}) => {
  await openDocuments(target);
  await choose(target, PLENOIL);
  await kind(target, "received");
  await draft(target).locator(".ledger-draft-country").fill("ES");
  const findings = draft(target).locator(".ledger-finding");
  await findings
    .nth(0)
    .getByRole("radio", {
      name: label("desktop.ledger.documents.action.choose_candidate"),
    })
    .click();
  await findings
    .nth(0)
    .getByRole("radio", { name: /B87000001/ })
    .check();
  await findings
    .nth(1)
    .getByLabel(label("desktop.ledger.documents.why_right"))
    .fill("Rounding");
  await draft(target).locator(".ledger-draft-confirm").click();
  const done = section(target).locator(".ledger-draft-confirmed");
  await expect(done).toBeVisible();
  const none = done.locator(".ledger-draft-no-match");
  await expect(none).toContainText(
    label("desktop.ledger.documents.no_movement"),
  );
  await none.locator(".ledger-draft-find-movement").click();
  const list = target.locator("[data-slot=combobox]");
  await expect(list).toBeVisible();
  const options = list.getByRole("option");
  await expect(options).not.toHaveCount(0);
  await options.first().click();
  await expect(done.locator(".ledger-draft-link-staged")).toBeVisible();
  await expect(target.locator(".ledger-tray")).toBeVisible();
});

test("a reader with no model chosen is named in words, says so and leads to the agent", async ({
  page: target,
}) => {
  await seedLayout(target, { layout: { agentShown: false } });
  await openDocuments(target, undefined, "reader_unselected");
  await tab(target, "readers").click();
  const readers = section(target).locator(".ledger-readers");
  const roles = readers.locator(".ledger-reader-role");
  await expect(roles).toHaveCount(2);
  // Each role is named in words, never by the id the service uses.
  const served = ["text_extraction", "vision_transcription"];
  for (const [index, role] of served.entries()) {
    await expect(roles.nth(index)).toContainText(
      label("desktop.agent.model_role_heading", {
        role: label(`desktop.setup.role.${role}`),
      }),
    );
    await expect(roles.nth(index)).not.toContainText(role);
  }
  // The role that reads asks for nothing.
  await expect(roles.first()).toContainText(
    label("desktop.ledger.documents.reader.ready"),
  );
  await expect(roles.first().locator(".ledger-reader-no-model")).toHaveCount(0);
  await expect(roles.first().getByRole("button")).toHaveCount(0);
  // The role with no model says so, and setup, which cannot choose one, is
  // not what it offers.
  const vision = roles.nth(1);
  await expect(vision).toContainText(
    label("desktop.ledger.documents.reader.not_ready"),
  );
  await expect(vision.locator(".ledger-reader-no-model")).toHaveText(
    label("desktop.ledger.documents.reader.no_model"),
  );
  await expect(readers.locator(".setup-offer")).toHaveCount(0);
  // It leads to the agent, where the model of each role is chosen.
  await expect(agentColumn(target)).toBeHidden();
  await vision
    .getByRole("button", {
      name: label("desktop.ledger.documents.reader.choose_model"),
    })
    .click();
  await expect(agentColumn(target)).toBeVisible();
});
