import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { label } from "../support/strings";

// The panel beside the Movements grid over the scenario's ledger: the
// inspector of one movement, with its jump index, sections and actions,
// and of several, with fields set for all. Every change it makes is staged
// into the page's tray; the model's suggestion is answered bound to the
// review the page read, a link is permanent and guarded, a split's last
// part takes the remainder, and a removal is previewed by the ledger first.

const engine = readFileSync(
  fileURLToPath(
    new URL("../../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);

async function open(target: Page, scheme?: "light" | "dark") {
  if (scheme)
    await target.addInitScript((appearance) => {
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ prefs: { appearance } }),
      );
    }, scheme);
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
}

const page = (target: Page) => target.locator(".ledger-page");
const grid = (target: Page) => page(target).getByRole("grid");
const dataRows = (target: Page) => grid(target).locator("[data-kind=data]");
const panel = (target: Page) => target.locator("aside.ledger-panel");
const index = (target: Page) => panel(target).locator(".ledger-jump-index");
const body = (target: Page) => panel(target).locator(".ledger-inspector-body");
const tray = (target: Page) => target.locator(".ledger-tray");
const review = (target: Page) => target.locator(".ledger-review");
const search = (target: Page) =>
  page(target).getByRole("searchbox", {
    name: label("desktop.ledger.search.label"),
  });

async function openLedger(target: Page, scheme?: "light" | "dark") {
  await open(target, scheme);
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target)).toBeVisible();
  await expect(dataRows(target).first()).toBeVisible();
}

const rowOf = (target: Page, text: string) =>
  dataRows(target)
    .filter({
      has: target.locator("[data-column=description]", { hasText: text }),
    })
    .first();
const cellOf = (row: Locator, column: string) =>
  row.locator(`[data-column=${column}]`);

async function choosePeriod(target: Page, year: number, code: string) {
  await target.locator(".pane-docs .pane-head .ledger-period").click();
  const periods = target.getByRole("dialog", {
    name: label("desktop.ledger.period.choose"),
  });
  const shown = periods.locator("[aria-live=polite]");
  for (let guard = 0; guard < 40; guard += 1) {
    const at = Number(await shown.textContent());
    if (at === year) break;
    await periods
      .getByRole("button", {
        name: label(
          at > year
            ? "desktop.ledger.period.year_previous"
            : "desktop.ledger.period.year_next",
        ),
        exact: true,
      })
      .click();
  }
  await periods
    .getByRole("group", {
      name: label("desktop.ledger.period.of_year", { year }),
    })
    .getByRole("button", { name: code, exact: true })
    .click();
  await expect(periods).toBeHidden();
  await expect(dataRows(target).first()).toBeVisible();
}

/** Selects the movement and opens the inspector on it with Alt+I. */
async function inspect(target: Page, text: string) {
  await cellOf(rowOf(target, text), "status").click();
  if (!(await panel(target).isVisible()))
    await target.keyboard.press("Alt+KeyI");
  await expect(panel(target).locator(".ledger-inspector h2")).toContainText(
    text,
  );
}

/** Jumps to a section through the index, or its More menu where the
 * entry did not fit. */
async function jumpTo(target: Page, section: string, name: string) {
  const entry = index(target).locator(`[data-section=${section}]`);
  if (await entry.count()) await entry.click();
  else {
    await index(target).locator(".ledger-jump-more").click();
    await target.getByRole("menuitem", { name, exact: true }).click();
  }
  // The jump lands once the section's heading has the focus.
  await expect(body(target).locator(`#inspector-${section}`)).toBeFocused();
}

/** How many changes the tray counts: none where there is no tray. */
const trayCount = async (target: Page) =>
  (await tray(target).count())
    ? Number(
        await tray(target)
          .locator(".ledger-tray-toggle span[aria-hidden=true]")
          .textContent(),
      )
    : 0;

async function openReview(target: Page) {
  await tray(target).locator(".ledger-tray-review").click();
  await expect(review(target)).toBeVisible();
  await expect(review(target).locator(".ledger-review-summary")).not.toHaveText(
    label("desktop.ledger.apply.reading"),
  );
}
async function save(target: Page) {
  await review(target).locator(".ledger-apply-save").click();
  await expect(review(target).locator(".ledger-apply-done")).toBeVisible({
    timeout: 20_000,
  });
}

/** Chooses `option` in the combobox the focused trigger opened. */
async function choose(target: Page, option: string) {
  const list = target.locator("[data-slot=combobox]");
  await expect(list).toBeVisible();
  await target.keyboard.type(option);
  await list.getByRole("option", { name: option }).first().click();
  await expect(list).toHaveCount(0);
}

test("Alt+I opens the inspector on its index, moves there from the grid and closes back to the cell", async ({
  page: target,
}) => {
  await openLedger(target);
  await cellOf(rowOf(target, "PAPELERIA TRAZO"), "status").click();
  await expect(panel(target)).toHaveCount(0);
  await target.keyboard.press("Alt+KeyI");
  await expect(panel(target)).toHaveAttribute(
    "aria-label",
    label("desktop.ledger.inspector.panel"),
  );
  // The index has the focus, on its first entry.
  await expect(index(target).locator("[data-section=classify]")).toBeFocused();
  // From the grid, Alt+I moves focus to the index without closing it.
  await cellOf(rowOf(target, "PAPELERIA TRAZO"), "amount").click();
  await target.keyboard.press("Alt+KeyI");
  await expect(index(target).locator("[data-section=classify]")).toBeFocused();
  // From inside it, Alt+I closes it and hands focus back to the cell.
  await target.keyboard.press("Alt+KeyI");
  await expect(panel(target)).toHaveCount(0);
  await expect(
    cellOf(rowOf(target, "PAPELERIA TRAZO"), "amount"),
  ).toBeFocused();
});

test("Escape closes the inspector and focus returns to the active cell", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "PAPELERIA TRAZO");
  await body(target).focus();
  await target.keyboard.press("Escape");
  await expect(panel(target)).toHaveCount(0);
  await expect(
    cellOf(rowOf(target, "PAPELERIA TRAZO"), "status"),
  ).toBeFocused();
});

for (const width of [1280, 1440])
  test(`the jump index follows the reading, marks where it is and leaves nothing cut off (${width})`, async ({
    page: target,
  }) => {
    await target.setViewportSize({ width, height: 900 });
    await openLedger(target);
    await inspect(target, "PAPELERIA TRAZO");
    const nav = index(target);
    await expect(nav.locator("[aria-current=location]")).toHaveCount(1);
    const box = (await nav.boundingBox())!;
    // Every entry shown lies inside the bar; the rest are in More.
    const entries = nav.locator(":scope > button");
    const shown = await entries.count();
    for (let at = 0; at < shown; at += 1) {
      const entry = (await entries.nth(at).boundingBox())!;
      expect(entry.x).toBeGreaterThanOrEqual(box.x - 1);
      expect(entry.x + entry.width).toBeLessThanOrEqual(box.x + box.width + 1);
    }
    const named = await nav.locator("[data-section]").count();
    const more = nav.locator(".ledger-jump-more");
    if (named < 5) {
      await expect(more).toBeVisible();
      await more.click();
      await expect(target.getByRole("menuitem")).toHaveCount(5 - named);
      await target.keyboard.press("Escape");
    } else await expect(more).toHaveCount(0);
    // Scrolling to the end makes History the current place.
    await body(target).evaluate((element) => {
      element.scrollTop = element.scrollHeight;
    });
    const last = nav.locator("[data-section=history]");
    if (await last.count())
      await expect(last).toHaveAttribute("aria-current", "location");
    else await expect(more).toHaveAttribute("aria-current", "location");
    await body(target).evaluate((element) => {
      element.scrollTop = 0;
    });
    await expect(nav.locator("[data-section=classify]")).toHaveAttribute(
      "aria-current",
      "location",
    );
  });

test("jumping to a section scrolls to it and focuses its heading", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1920, height: 900 });
  await openLedger(target);
  await inspect(target, "PAPELERIA TRAZO");
  await jumpTo(
    target,
    "details",
    label("desktop.ledger.inspector.section.details"),
  );
  await expect(body(target).locator("#inspector-details")).toBeFocused();
  const entry = index(target).locator("[data-section=details]");
  await expect(
    (await entry.count()) ? entry : index(target).locator(".ledger-jump-more"),
  ).toHaveAttribute("aria-current", "location");
  // The section reads its lineage once shown: an imported movement names
  // its file.
  await expect(body(target).locator(".ledger-provenance")).toContainText(
    "extracto-",
  );
});

test("classifying from the inspector goes through the one command and stages it", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "PAPELERIA TRAZO");
  const decision = body(target).locator("[data-field=business_classification]");
  await decision
    .getByRole("radio", {
      name: label("desktop.ledger.classification.personal"),
    })
    .click();
  expect(await trayCount(target)).toBe(1);
  // The header still says what is stored; the decision says what is staged.
  await expect(panel(target).locator(".ledger-inspector-head")).toContainText(
    label("desktop.ledger.status.pending"),
  );
  await expect(body(target).locator(".ledger-unsaved")).toBeVisible();
  // Business asks its category in the same step, through the page's dialog.
  await decision
    .getByRole("radio", {
      name: label("desktop.ledger.classification.business"),
    })
    .click();
  await expect(target.locator(".ledger-classify")).toBeVisible();
  await target.keyboard.press("Escape");
});

test("a list field opens a combobox that moves without choosing, and hands focus back", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "SOFTNUBE IRELAND SUSCRIPCION");
  const before = await trayCount(target).catch(() => 0);
  const field = body(target).locator("[data-field=iva_category]");
  await field.click();
  const list = target.locator("[data-slot=combobox]");
  await expect(list).toBeVisible();
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("ArrowDown");
  await target.keyboard.press("Escape");
  await expect(list).toHaveCount(0);
  await expect(field).toBeFocused();
  expect(await trayCount(target).catch(() => 0)).toBe(before);
  await field.click();
  await choose(target, label("desktop.ledger.iva_category.domestic_reduced"));
  await expect(field).toBeFocused();
  await expect(field).toContainText(
    label("desktop.ledger.iva_category.domestic_reduced"),
  );
  expect(await trayCount(target)).toBe(before + 1);
});

test("a typed field refuses what the grammar refuses and stages a correction", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "PAPELERIA TRAZO");
  await jumpTo(
    target,
    "details",
    label("desktop.ledger.inspector.section.details"),
  );
  const counterparty = body(target).locator("[data-field=counterparty]");
  await counterparty.click();
  const input = body(target).locator("input:focus");
  await input.fill("Trazo Papelería SL");
  await target.keyboard.press("Enter");
  await expect(counterparty).toBeFocused();
  await expect(counterparty).toContainText("Trazo Papelería SL");
  expect(await trayCount(target)).toBe(1);
  const amount = body(target).locator("[data-field=amount]");
  await amount.click();
  const typed = body(target).locator("input:focus");
  await typed.fill("1.000");
  await target.keyboard.press("Enter");
  await expect(typed).toHaveAttribute("aria-invalid", "true");
  await target.keyboard.press("Escape");
  expect(await trayCount(target)).toBe(1);
  // A decimal comma is refused with its meaning offered in one press,
  // never taken silently.
  await amount.click();
  const comma = body(target).locator("input:focus");
  await comma.fill("77,45");
  await target.keyboard.press("Enter");
  await expect(comma).toHaveAttribute("aria-invalid", "true");
  expect(await trayCount(target)).toBe(1);
  await body(target)
    .getByRole("button", {
      name: label("desktop.ledger.edit.refusal.use", { suggestion: "77.45" }),
    })
    .click();
  await expect(amount).toContainText("77.45");
  // The tray counts movements: still the one.
  expect(await trayCount(target)).toBe(1);
});

test("the selection inspector counts by glyph once and asks to classify before tax fields", async ({
  page: target,
}) => {
  await openLedger(target);
  await cellOf(rowOf(target, "PAPELERIA TRAZO"), "status").click();
  await cellOf(rowOf(target, "SOFTNUBE IRELAND"), "status").click({
    modifiers: ["Control"],
  });
  if (!(await panel(target).isVisible()))
    await target.keyboard.press("Alt+KeyI");
  const selection = panel(target).locator(".ledger-selection");
  const statuses = selection.locator(".ledger-selection-statuses li");
  await expect(statuses).toHaveCount(1);
  await expect(statuses.first()).toHaveAttribute("data-status", "pending");
  await expect(statuses.first()).toHaveText(/2/);
  await expect(
    selection.locator("[data-common=business_classification]"),
  ).toHaveCount(0);
  await expect(selection.locator(".ledger-selection-sums")).not.toContainText(
    "· EUR",
  );
  await expect(selection.locator(".ledger-classify-first")).toHaveText(
    label("desktop.ledger.inspector.selection.classify_first_hint"),
  );
  await expect(selection.locator("[data-set=category_id]")).toHaveCount(0);
});

test("the model's approval is staged with what it writes, and is answered bound to the review read", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "PAPELERIA TRAZO");
  const model = body(target).locator(".ledger-model");
  await model
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.ask"),
      exact: true,
    })
    .click();
  const card = model.locator(".ledger-suggestion");
  await expect(card).toBeVisible();
  await expect(card).toContainText(
    label("desktop.ledger.classification.business"),
  );
  await card
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.approve"),
    })
    .click();
  await expect(model).toContainText(
    label("desktop.ledger.inspector.model.approval_staged"),
  );
  expect(await trayCount(target)).toBe(1);
  await openReview(target);
  await save(target);
  await review(target).locator(".ledger-apply-done").click();
  // Saved, the movement is classified by the model with the person's
  // approval.
  await inspect(target, "PAPELERIA TRAZO");
  await expect(body(target).locator(".ledger-decision")).toContainText(
    label("desktop.ledger.inspector.by.model", { model: "llm:local-medium" }),
  );
});

test("an approval of a review that changed since it was read is refused and stays staged", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "PAPELERIA TRAZO");
  const model = body(target).locator(".ledger-model");
  await model
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.ask"),
      exact: true,
    })
    .click();
  await model
    .locator(".ledger-suggestion")
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.approve"),
    })
    .click();
  await target.evaluate(() => window.__scenarioLedger!.changeReviews());
  await openReview(target);
  await save(target);
  await expect(review(target).locator("[data-outcome=refused]")).toHaveCount(1);
  await review(target).locator(".ledger-apply-done").click();
  expect(await trayCount(target)).toBe(1);
});

test("a rejection asks for its reason and is staged against the review asked with it", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "PAPELERIA TRAZO");
  const model = body(target).locator(".ledger-model");
  await model
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.ask"),
      exact: true,
    })
    .click();
  const card = model.locator(".ledger-suggestion");
  await card
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.reject"),
    })
    .click();
  const proceed = card.getByRole("button", {
    name: label("desktop.ledger.inspector.model.continue_reject"),
  });
  await expect(proceed).toBeDisabled();
  await card
    .getByLabel(label("desktop.ledger.inspector.model.reason"))
    .fill("Una compra personal");
  await proceed.click();
  await expect(card).toContainText(
    label("desktop.ledger.inspector.model.rejecting", {
      reason: "Una compra personal",
    }),
  );
  await card
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.stage_rejection"),
    })
    .click();
  await expect(model).toContainText(
    label("desktop.ledger.inspector.model.rejection_staged"),
  );
  expect(await trayCount(target)).toBe(1);
});

test("a Mixed proposal without a share is held until it is asked again with one", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "FIBRA HOGAR ALBOR");
  const model = body(target).locator(".ledger-model");
  await model
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.ask"),
      exact: true,
    })
    .click();
  const card = model.locator(".ledger-suggestion");
  const approve = card.getByRole("button", {
    name: label("desktop.ledger.inspector.model.approve"),
  });
  await expect(approve).toBeDisabled();
  await card
    .getByLabel(label("desktop.ledger.inspector.model.share_needed"))
    .fill("30");
  await card
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.ask_with_share"),
    })
    .click();
  await expect(approve).toBeEnabled();
  await approve.click();
  expect(await trayCount(target)).toBe(1);
});

/** The movements whose model review waits in the scenario's runtime. */
const waitingReviews = (target: Page) =>
  target.evaluate(() =>
    window
      .__scenarioLedger!.waitingReviews()
      .map((review) => review.transaction)
      .sort(),
  );
const hostCalls = (target: Page) =>
  target.evaluate(
    () =>
      (window as unknown as { __scenarioHostCalls?: string[] })
        .__scenarioHostCalls ?? [],
  );
const keyOf = async (target: Page, text: string) =>
  (await rowOf(target, text).getAttribute("data-key"))!;

async function askModel(target: Page) {
  const model = body(target).locator(".ledger-model");
  await model
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.ask"),
      exact: true,
    })
    .click();
  await expect(model.locator(".ledger-suggestion")).toBeVisible();
  return model;
}

test("two movements are reviewed at once, each holding its own review until it is saved", async ({
  page: target,
}) => {
  await openLedger(target);
  const trazo = await keyOf(target, "PAPELERIA TRAZO");
  const softnube = await keyOf(target, "SOFTNUBE IRELAND SUSCRIPCION");
  await inspect(target, "PAPELERIA TRAZO");
  const model = await askModel(target);
  await model
    .locator(".ledger-suggestion")
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.approve"),
    })
    .click();
  // The staged approval holds its review while another movement is asked.
  await inspect(target, "SOFTNUBE IRELAND SUSCRIPCION");
  const other = await askModel(target);
  await expect(other.locator("[role=alert]")).toHaveCount(0);
  expect(await waitingReviews(target)).toEqual([trazo, softnube].sort());
  await other
    .locator(".ledger-suggestion")
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.approve"),
    })
    .click();
  expect(await trayCount(target)).toBe(2);
  await openReview(target);
  await save(target);
  await expect(review(target).locator("[data-outcome=refused]")).toHaveCount(0);
  await review(target).locator(".ledger-apply-done").click();
  expect(await waitingReviews(target)).toEqual([]);
});

test("asking again about the same movement cancels the review it replaces, and leaving a movement cancels its unstaged review", async ({
  page: target,
}) => {
  await openLedger(target);
  const trazo = await keyOf(target, "PAPELERIA TRAZO");
  await inspect(target, "PAPELERIA TRAZO");
  const model = await askModel(target);
  const card = model.locator(".ledger-suggestion");
  await card
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.reject"),
    })
    .click();
  await card
    .getByLabel(label("desktop.ledger.inspector.model.reason"))
    .fill("Una compra personal");
  const before = (await hostCalls(target)).filter(
    (call) => call === "ledger cancel",
  ).length;
  await card
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.continue_reject"),
    })
    .click();
  // The first review is cancelled before the second is asked, so the
  // runtime's one review per movement does not refuse it.
  await expect(card).toContainText(
    label("desktop.ledger.inspector.model.rejecting", {
      reason: "Una compra personal",
    }),
  );
  await expect(model.locator("[role=alert]")).toHaveCount(0);
  expect(
    (await hostCalls(target)).filter((call) => call === "ledger cancel").length,
  ).toBe(before + 1);
  expect(await waitingReviews(target)).toEqual([trazo]);
  // Another movement shown, the review nobody staged is let go.
  await inspect(target, "SOFTNUBE IRELAND SUSCRIPCION");
  await expect.poll(() => waitingReviews(target)).toEqual([]);
});

test("a review of the movement still open elsewhere is refused in words", async ({
  page: target,
}) => {
  await openLedger(target);
  const trazo = await keyOf(target, "PAPELERIA TRAZO");
  await target.evaluate(
    (id) => window.__scenarioLedger!.reviewElsewhere(id),
    trazo,
  );
  await inspect(target, "PAPELERIA TRAZO");
  const model = body(target).locator(".ledger-model");
  await model
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.ask"),
      exact: true,
    })
    .click();
  const refusal = model.locator("[role=alert]");
  await expect(refusal).toContainText(
    label("desktop.ledger.inspector.model.busy"),
  );
  await expect(refusal).not.toContainText("subject_busy");
});

test("asking the model for each of three movements keeps one review waiting for each, and lets go of those not approved", async ({
  page: target,
}) => {
  await openLedger(target);
  const texts = [
    "PAPELERIA TRAZO",
    "SOFTNUBE IRELAND SUSCRIPCION",
    "FIBRA HOGAR ALBOR",
  ];
  const keys = await Promise.all(texts.map((text) => keyOf(target, text)));
  const selectThree = async () => {
    await cellOf(rowOf(target, texts[0]!), "status").click();
    for (const text of texts.slice(1))
      await cellOf(rowOf(target, text), "status").click({
        modifiers: ["Control"],
      });
    if (!(await panel(target).isVisible()))
      await target.keyboard.press("Alt+KeyI");
    await expect(panel(target).locator(".ledger-selection")).toBeVisible();
  };
  await selectThree();
  const selection = panel(target).locator(".ledger-selection");
  await selection
    .getByRole("button", {
      name: label("desktop.ledger.inspector.selection.ask_each"),
    })
    .click();
  const asked = selection.locator(".ledger-asked");
  await expect(asked).toContainText(
    label("desktop.ledger.inspector.selection.asked", { count: 3 }),
  );
  await expect(asked.locator("li")).toHaveCount(3);
  await expect(asked.locator("[data-code]")).toHaveCount(0);
  expect(await waitingReviews(target)).toEqual([...keys].sort());
  // Approve the first; closing the selection lets the other two go, and
  // the staged approval keeps its own.
  await asked
    .locator("li")
    .filter({ hasText: texts[0]! })
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.approve"),
    })
    .click();
  expect(await trayCount(target)).toBe(1);
  await selection
    .getByRole("button", {
      name: label("desktop.ledger.inspector.selection.clear"),
    })
    .click();
  await expect.poll(() => waitingReviews(target)).toEqual([keys[0]]);
  // Discarding the staged approval from the tray lets its review go too.
  await tray(target).locator(".ledger-tray-toggle").click();
  await tray(target).locator(".ledger-tray-discard").click();
  await expect.poll(() => waitingReviews(target)).toEqual([]);
});

test("a staged approval left with the page lets its review go", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "PAPELERIA TRAZO");
  const model = await askModel(target);
  await model
    .locator(".ledger-suggestion")
    .getByRole("button", {
      name: label("desktop.ledger.inspector.model.approve"),
    })
    .click();
  expect(await waitingReviews(target)).toHaveLength(1);
  await target.keyboard.press("Control+Shift+KeyD");
  await target.locator(".ledger-leave .ledger-leave-discard").click();
  await expect(page(target)).toHaveCount(0);
  await expect.poll(() => waitingReviews(target)).toEqual([]);
});

test("IVA worked out from a category is staged as its own write", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "SOFTNUBE IRELAND SUSCRIPCION");
  const derive = body(target).locator(".ledger-derive");
  await derive.locator("[data-field=iva-derive]").click();
  await choose(target, label("desktop.ledger.iva_category.domestic_general"));
  await derive
    .getByRole("button", {
      name: label("desktop.ledger.inspector.derive.stage"),
    })
    .click();
  await expect(derive).toContainText(
    label("desktop.ledger.inspector.derive.staged", {
      category: label("desktop.ledger.iva_category.domestic_general"),
    }),
  );
  expect(await trayCount(target)).toBe(1);
});

test("a link is permanent, and an invoice staged for one movement is held for every other", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "PAPELERIA TRAZO");
  await jumpTo(
    target,
    "invoice",
    label("desktop.ledger.inspector.section.invoice"),
  );
  const section = body(target).locator("[data-section-body=invoice]");
  await expect(section).toContainText(
    label("desktop.ledger.inspector.invoice.permanent"),
  );
  await section
    .getByRole("button", {
      name: label("desktop.ledger.inspector.invoice.pick"),
    })
    .click();
  await choose(target, "INV-88412");
  await expect(section).toContainText(
    label("desktop.ledger.inspector.invoice.staged", { invoice: "INV-88412" }),
  );
  expect(await trayCount(target)).toBe(1);
  // Another movement's picker shows the invoice held, with the movement
  // it is staged for.
  await inspect(target, "SOFTNUBE IRELAND SUSCRIPCION");
  const other = body(target).locator("[data-section-body=invoice]");
  await other.scrollIntoViewIfNeeded();
  await other
    .getByRole("button", {
      name: label("desktop.ledger.inspector.invoice.pick"),
    })
    .click();
  const option = target
    .locator("[data-slot=combobox]")
    .getByRole("option", { name: /INV-88412/ });
  await expect(option).toHaveAttribute("aria-disabled", "true");
  await target.keyboard.press("Escape");
});

test("a split's last part takes the remainder, and its parts may be classified", async ({
  page: target,
}) => {
  await openLedger(target);
  const amount = Number(
    (await cellOf(
      rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION"),
      "amount",
    ).textContent())!.replace(/[^\d.]/g, ""),
  );
  await inspect(target, "SOFTNUBE IRELAND SUSCRIPCION");
  await panel(target)
    .getByRole("button", { name: label("desktop.ledger.inspector.actions") })
    .click();
  await target
    .getByRole("menuitem", {
      name: `${label("desktop.ledger.inspector.action.split")}…`,
    })
    .click();
  const dialog = target.locator(".ledger-split");
  await expect(dialog).toBeVisible();
  await dialog.locator(".ledger-split-amount").first().fill("20");
  const rest = dialog.locator(".ledger-split-part input[readonly]");
  await expect(rest).toHaveValue(String(Math.round((amount - 20) * 100) / 100));
  const descriptions = dialog.locator(".ledger-split-description");
  await descriptions.nth(0).fill("Licencia");
  await descriptions.nth(1).fill("Soporte");
  await dialog
    .locator(".ledger-split-part")
    .first()
    .locator("select")
    .selectOption("PERSONAL");
  await dialog
    .getByRole("button", {
      name: label("desktop.ledger.inspector.split.stage"),
    })
    .click();
  await expect(dialog).toHaveCount(0);
  expect(await trayCount(target)).toBe(1);
});

test("removing is previewed by the ledger, and a movement a finalized declaration cites cannot be", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "PAPELERIA TRAZO");
  await panel(target)
    .getByRole("button", { name: label("desktop.ledger.inspector.actions") })
    .click();
  await target
    .getByRole("menuitem", {
      name: `${label("desktop.ledger.inspector.action.remove")}…`,
    })
    .click();
  const dialog = target.locator(".ledger-action-dialog");
  await expect(dialog.locator(".ledger-remove-preview")).toBeVisible();
  await expect(dialog).toContainText(
    label("desktop.ledger.inspector.remove.attachments", { count: 0 }),
  );
  const remove = dialog.getByRole("button", {
    name: label("desktop.ledger.inspector.remove.stage"),
  });
  await expect(remove).toBeEnabled();
  await remove.click();
  expect(await trayCount(target)).toBe(1);

  // A movement of the first quarter, which a filed Modelo 303 cites.
  await choosePeriod(target, 2026, "1T");
  await inspect(target, "CUOTA AUTONOMOS TGSS");
  await expect(panel(target).locator(".ledger-inspector-head")).toContainText(
    label("desktop.ledger.inspector.used.name", {
      modelo: "303",
      year: 2026,
      period: "1T",
    }),
  );
  await panel(target)
    .getByRole("button", { name: label("desktop.ledger.inspector.actions") })
    .click();
  await target
    .getByRole("menuitem", {
      name: `${label("desktop.ledger.inspector.action.remove")}…`,
    })
    .click();
  const blocked = target.locator(".ledger-action-dialog");
  await expect(blocked).toContainText(
    label("desktop.ledger.inspector.remove.blocked"),
  );
  await expect(
    blocked.getByRole("button", {
      name: label("desktop.ledger.inspector.remove.stage"),
    }),
  ).toBeDisabled();
});

test("set for all applies as chosen and says how many hidden movements it reaches", async ({
  page: target,
}) => {
  await openLedger(target);
  await cellOf(rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION"), "status").click();
  await cellOf(rowOf(target, "RECIBO TELEFONIA ALBOR"), "status").click({
    modifiers: ["Control"],
  });
  await target.keyboard.press("Alt+KeyI");
  const selection = panel(target).locator(".ledger-selection");
  await expect(selection.locator("h2")).toHaveText(
    label("desktop.ledger.inspector.selection.title", { count: 2 }),
  );
  // Hide one of them with a search.
  await search(target).fill("SOFTNUBE");
  await expect(selection).toContainText(
    label("desktop.ledger.selection.hidden", { hidden: 1, selected: 2 }),
  );
  // Both are still to classify: the tax fields wait for a classification,
  // a group label reaches both, the hidden one said so.
  await expect(selection.locator(".ledger-classify-first")).toBeVisible();
  await expect(selection.locator("[data-set=iva_category]")).toHaveCount(0);
  const group = selection.locator("form").filter({
    has: target.getByLabel(label("desktop.ledger.column.group_label")),
  });
  await group.getByRole("textbox").fill("Suscripciones");
  const set = group.getByRole("button");
  await expect(set).toHaveText(
    label("desktop.ledger.inspector.selection.set_hidden", {
      visible: 1,
      hidden: 1,
    }),
  );
  await set.click();
  // The tray counts movements changed: both.
  expect(await trayCount(target)).toBe(2);
  // With none of them drawn, nothing is set until the person chooses.
  await search(target).fill("NO SUCH MOVEMENT");
  await expect(group.getByRole("button")).toBeDisabled();
  await selection
    .getByRole("button", {
      name: label("desktop.ledger.selection.keep_visible"),
    })
    .click();
  await expect(panel(target).locator(".ledger-inspector-empty")).toBeVisible();
});

test("the selection's totals are per currency and direction, and shared values say Mixed", async ({
  page: target,
}) => {
  await openLedger(target);
  await cellOf(rowOf(target, "SWIFT BRIGHT HARBOR"), "status").click();
  await cellOf(rowOf(target, "PAPELERIA TRAZO"), "status").click({
    modifiers: ["Control"],
  });
  await target.keyboard.press("Alt+KeyI");
  const selection = panel(target).locator(".ledger-selection");
  const sums = selection.locator(".ledger-selection-sums");
  await expect(sums).toContainText("USD");
  await expect(sums).toContainText("EUR");
  await expect(selection.locator("[data-common=direction]")).toHaveText(
    label("desktop.ledger.inspector.selection.mixed_values", { count: 2 }),
  );
});

test("while readiness is not measured, neither inspector draws a reviewed movement as done", async ({
  page: target,
}) => {
  await open(target);
  // The page's first readiness check fails, so nothing is measured.
  await target.evaluate(() =>
    window.__scenarioLedger!.nextReads("ledger.preflight", 1),
  );
  await target.locator("[data-rail=ledger]").click();
  await expect(dataRows(target).first()).toBeVisible();
  const reviewed = rowOf(target, "SUPERMERCADO HOJA");
  await expect(
    cellOf(reviewed, "status").locator("[data-status]"),
  ).toHaveAttribute("data-status", "unmeasured");
  await inspect(target, "SUPERMERCADO HOJA");
  const head = panel(target).locator(".ledger-inspector-head");
  await expect(head.locator("[data-status]")).toHaveAttribute(
    "data-status",
    "unmeasured",
  );
  await expect(head.locator("[data-status]")).toHaveText(
    label("desktop.ledger.readiness.not_measured"),
  );
  await cellOf(rowOf(target, "FIBRA HOGAR"), "status").click({
    modifiers: ["Control"],
  });
  const statuses = panel(target).locator(
    ".ledger-selection-statuses li[data-status]",
  );
  await expect(statuses).toHaveCount(1);
  await expect(statuses.first()).toHaveAttribute("data-status", "unmeasured");
  await expect(statuses.first()).toHaveText(/2/);
});

test("at 1280 with the agent open, the inspector narrows the agent so the grid keeps 40rem, Description stays pinned, and a revealed cell is shown whole", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1280, height: 800 });
  await openLedger(target);
  await expect(target.locator("[data-rail=agent]")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  // The agent laid out as wide as it goes, which leaves the page the least
  // any pane keeps.
  const agent = target.locator("aside.agent-column");
  await target.locator(".agent-separator").focus();
  await target.keyboard.press("End");
  const agentBefore = (await agent.boundingBox())!.width;
  expect(agentBefore).toBeGreaterThan(640);
  await inspect(target, "PAPELERIA TRAZO");
  // The agent stays open, narrower, and the room is the grid's.
  await expect(agent).toBeVisible();
  expect((await agent.boundingBox())!.width).toBeLessThan(agentBefore);
  const rem = await target.evaluate(() =>
    parseFloat(getComputedStyle(document.documentElement).fontSize),
  );
  const panelBox = (await panel(target).boundingBox())!;
  expect(panelBox.width).toBeGreaterThanOrEqual(17.5 * rem - 0.5);
  expect(panelBox.width).toBeLessThan(20 * rem);
  // The grid's column of the row keeps its own 40rem.
  const column = (await grid(target)
    .locator("xpath=ancestor::*[@data-slot='data-grid']/..")
    .boundingBox())!;
  expect(column.width).toBeGreaterThanOrEqual(40 * rem - 1);
  // And the band between the pinned groups shows the widest scrolling
  // column whole.
  const band = await target.evaluate(() => {
    const heads = [
      ...document.querySelectorAll<HTMLElement>(
        ".ledger-grid [data-header-column]",
      ),
    ];
    const pinned = heads.filter(
      (head) => getComputedStyle(head).position === "sticky",
    );
    const widest = Math.max(
      ...heads
        .filter((head) => !pinned.includes(head))
        .map((head) => head.offsetWidth),
    );
    const scroller = document.querySelector<HTMLElement>(
      ".ledger-grid [role=grid]",
    )!;
    const covered = pinned.reduce((sum, head) => sum + head.offsetWidth, 0);
    return { room: scroller.clientWidth - covered, widest };
  });
  expect(band.room).toBeGreaterThanOrEqual(band.widest - 1);
  // Moving to Classification shows the whole cell between the pinned
  // groups, and Description stays pinned beside it.
  const row = rowOf(target, "PAPELERIA TRAZO");
  const pinnedAt = (await cellOf(row, "description").boundingBox())!.x;
  await cellOf(row, "description").click();
  for (let step = 0; step < 3; step += 1)
    await target.keyboard.press("ArrowRight");
  const classification = cellOf(row, "classification");
  await expect(classification).toBeFocused();
  const cell = (await classification.boundingBox())!;
  const date = (await cellOf(row, "date").boundingBox())!;
  const amount = (await cellOf(row, "amount").boundingBox())!;
  expect(cell.x).toBeGreaterThanOrEqual(date.x + date.width - 1);
  expect(cell.x + cell.width).toBeLessThanOrEqual(amount.x + 1);
  const covering = await target.evaluate(
    ([x, y]) =>
      document
        .elementFromPoint(x!, y!)
        ?.closest("[data-column]")
        ?.getAttribute("data-column"),
    [cell.x + 4, cell.y + cell.height / 2],
  );
  expect(covering).toBe("classification");
  const description = (await cellOf(row, "description").boundingBox())!;
  expect(Math.abs(description.x - pinnedAt)).toBeLessThan(1);
  expect(cell.x).toBeGreaterThanOrEqual(description.x + description.width - 1);
  // Closed, the panel gives the agent back the width it was laid out at.
  await body(target).focus();
  await target.keyboard.press("Escape");
  await expect(panel(target)).toHaveCount(0);
  await expect
    .poll(async () => (await agent.boundingBox())!.width)
    .toBeCloseTo(agentBefore, 0);
});

test("the inspector is resized by its separator within its limits", async ({
  page: target,
}) => {
  await openLedger(target);
  await inspect(target, "PAPELERIA TRAZO");
  const handle = target.locator(".ledger-panel-resize");
  const before = (await panel(target).boundingBox())!.width;
  await handle.focus();
  await target.keyboard.press("ArrowLeft");
  const wider = (await panel(target).boundingBox())!.width;
  expect(wider).toBeGreaterThan(before);
  await target.keyboard.press("Home");
  const least = (await panel(target).boundingBox())!.width;
  const rem = await target.evaluate(() =>
    parseFloat(getComputedStyle(document.documentElement).fontSize),
  );
  expect(Math.round(least)).toBe(Math.round(17.5 * rem));
  await expect(handle).toHaveAttribute("aria-valuenow", "0");
  // The grid keeps its own width beside it.
  await target.keyboard.press("End");
  const gridBox = (await grid(target).boundingBox())!;
  expect(gridBox.width).toBeGreaterThanOrEqual(40 * rem - 32);
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

for (const scheme of ["light", "dark"] as const)
  test(`the inspector has no accessibility violations (${scheme})`, async ({
    page: target,
  }) => {
    await openLedger(target, scheme);
    await expect(target.locator("html")).toHaveAttribute("data-scheme", scheme);
    await inspect(target, "PAPELERIA TRAZO");
    await body(target)
      .locator("details")
      .first()
      .evaluate((element) => {
        (element as HTMLDetailsElement).open = true;
      });
    expect(await audit(target)).toEqual([]);
    await cellOf(rowOf(target, "SOFTNUBE IRELAND SUSCRIPCION"), "status").click(
      {
        modifiers: ["Control"],
      },
    );
    await expect(panel(target).locator(".ledger-selection")).toBeVisible();
    expect(await audit(target)).toEqual([]);
  });
