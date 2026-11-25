import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { filing } from "../support/scenarioModeloWrites";
import { list, openList, rowsOf, views } from "../support/scenarioModelo";

// What the Export and record view rests on is read through the filing state,
// not through the whole form: after a write the window settled, one filing
// state read renews it, and only a filing state read that failed falls back to
// the whole form read. Opening a declaration still reads the form.

const BUSY = () => label("desktop.navigation.busy");
const AVAILABLE = () => label("workspace.modelo.filing.also_other_way");
const exportButton = (target: Page) =>
  target.getByRole("button", {
    name: label("workspace.modelo.filing.export_again"),
  });
const recordButton = (target: Page) =>
  target.getByRole("button", {
    name: label("workspace.modelo.filing.record_as_filed"),
  });
/** The row the record button and its words share. */
const recordRow = (target: Page) => recordButton(target).locator("xpath=..");
const busyNotice = (target: Page) =>
  target.locator('[data-slot="alert"]').filter({ hasText: BUSY() });

type Reads = {
  form: number;
  filingState: number;
  exports: number;
  files: number;
  holdFilingState: boolean;
  releaseFilingState: (() => void) | null;
};
declare global {
  interface Window {
    __filingStateReads?: Reads;
  }
}

/** Counts the form and filing state reads and the writes that follow them,
 * and lets a spec hold the filing state read. */
const watch = (target: Page) =>
  target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const state: Reads = (window.__filingStateReads = {
      form: 0,
      filingState: 0,
      exports: 0,
      files: 0,
      holdFilingState: false,
      releaseFilingState: null,
    });
    const form = port.form;
    const submit = port.submit;
    port.form = (...args) => {
      state.form += 1;
      return form(...args);
    };
    port.submit = async (...args) => {
      if (args[0] === "modelo.export") state.exports += 1;
      if (args[0] === "modelo.work.file") state.files += 1;
      if (args[0] === "modelo.work.filing_state") {
        state.filingState += 1;
        if (state.holdFilingState)
          await new Promise<void>((release) => {
            state.releaseFilingState = release;
          });
      }
      return submit(...args);
    };
  });
const reads = (target: Page) =>
  target.evaluate(() => {
    const { form, filingState, exports, files } = window.__filingStateReads!;
    return { form, filingState, exports, files };
  });
/** Starts counting afresh from now. */
const reset = (target: Page) =>
  target.evaluate(() => {
    const state = window.__filingStateReads!;
    state.form = 0;
    state.filingState = 0;
    state.exports = 0;
    state.files = 0;
  });

/** Opens the exported 130's Export and record view and starts counting once it
 * is ready. */
async function ready(target: Page) {
  await filing(target, "exported");
  await expect(recordButton(target)).toBeEnabled();
  await expect(recordRow(target)).toContainText(AVAILABLE());
  await watch(target);
}

async function settled(target: Page) {
  await expect(busyNotice(target)).toHaveCount(0);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  await expect(recordButton(target)).toBeEnabled();
  // A repeat starts after the first read lands, so give it the time it needs.
  await target.waitForTimeout(1500);
}

async function recordFiling(target: Page) {
  await recordButton(target).click();
  await target
    .getByRole("dialog")
    .getByRole("button", {
      name: label("application.modelo.lifecycle.file_confirm_accept"),
    })
    .click();
}

test("after an export the window reads the filing state, not the whole form", async ({
  page: target,
}) => {
  await ready(target);
  await reset(target);
  await exportButton(target).click();
  await expect.poll(async () => (await reads(target)).exports).toBe(1);
  await settled(target);
  const counted = await reads(target);
  expect(counted.exports).toBe(1);
  expect(counted.form).toBe(0);
  expect(counted.filingState).toBe(1);
});

test("after recording the filing the window reads the filing state alone, not the whole form", async ({
  page: target,
}) => {
  await ready(target);
  await reset(target);
  await recordFiling(target);
  await expect.poll(async () => (await reads(target)).files).toBe(1);
  await expect(
    target.getByText(label("workspace.modelo.filing.recorded_here")).first(),
  ).toBeVisible();
  // Recorded, the record button is gone; the view is no longer busy.
  await expect(busyNotice(target)).toHaveCount(0);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  // A repeat starts after the first read lands, so give it the time it needs.
  await target.waitForTimeout(1500);
  const counted = await reads(target);
  expect(counted.files).toBe(1);
  // The header's step, the journey and the next step are the filing state's:
  // the whole form is not read behind it.
  expect(counted.form).toBe(0);
  expect(counted.filingState).toBe(1);
});

test("while the filing state is read the record button stays closed, and it opens by itself when read", async ({
  page: target,
}) => {
  await ready(target);
  await reset(target);
  await target.evaluate(() => {
    window.__filingStateReads!.holdFilingState = true;
  });
  await exportButton(target).click();
  await expect
    .poll(() =>
      target.evaluate(() => !!window.__filingStateReads!.releaseFilingState),
    )
    .toBe(true);

  // Sample the held read for three seconds.
  for (let at = 0; at < 6; at++) {
    await expect(recordButton(target)).toBeDisabled();
    await expect(busyNotice(target)).toHaveCount(1);
    expect(
      (await recordRow(target).innerText()).replace(/\s+/g, " "),
    ).toContain(BUSY());
    await target.waitForTimeout(500);
  }

  // Released, the read lands and nothing more is pressed.
  await target.evaluate(() => {
    window.__filingStateReads!.holdFilingState = false;
    window.__filingStateReads!.releaseFilingState!();
  });
  await expect(busyNotice(target)).toHaveCount(0);
  await expect(recordButton(target)).toBeEnabled();
  await expect(recordRow(target)).toContainText(AVAILABLE());
  await expect(recordRow(target)).not.toContainText(BUSY());
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  const counted = await reads(target);
  expect(counted.exports).toBe(1);
  expect(counted.form).toBe(0);
  expect(counted.filingState).toBe(1);
});

test("the record button opens within a second of the filing state answer, with nothing else gating it", async ({
  page: target,
}) => {
  await ready(target);
  await reset(target);
  await target.evaluate(() => {
    window.__filingStateReads!.holdFilingState = true;
  });
  await exportButton(target).click();
  await expect
    .poll(() =>
      target.evaluate(() => !!window.__filingStateReads!.releaseFilingState),
    )
    .toBe(true);
  // From the moment the answer is let through to the first frame in which
  // the record button is open, sampled on every frame.
  const openedAfterMs = await target.evaluate(
    ([name]) =>
      new Promise<number>((resolve) => {
        const state = window.__filingStateReads!;
        state.holdFilingState = false;
        const answered = performance.now();
        state.releaseFilingState!();
        const sample = () => {
          const button = [...document.querySelectorAll("button")].find(
            (candidate) => candidate.textContent?.trim() === name,
          );
          if (button && !button.disabled && !button.ariaDisabled)
            resolve(performance.now() - answered);
          else requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
      }),
    [label("workspace.modelo.filing.record_as_filed")],
  );
  expect(openedAfterMs).toBeLessThan(1000);
  // No second read, timer or hold stands behind it.
  await target.waitForTimeout(1500);
  expect(await reads(target)).toMatchObject({ form: 0, filingState: 1 });
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
});

test("a filing state read that fails falls back to the whole form read", async ({
  page: target,
}) => {
  await ready(target);
  await reset(target);
  await target.evaluate(() => {
    window.__filingStateFails = true;
  });
  await exportButton(target).click();
  await expect.poll(async () => (await reads(target)).form).toBe(1);
  await settled(target);
  const counted = await reads(target);
  expect(counted.exports).toBe(1);
  expect(counted.filingState).toBe(1);
  expect(counted.form).toBe(1);
  // The view ends consistent: open, with the served words and no busy notice.
  await expect(recordButton(target)).toBeEnabled();
  await expect(recordRow(target)).toContainText(AVAILABLE());
  await expect(recordRow(target)).not.toContainText(BUSY());
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
});

test("opening a declaration still reads the whole form once", async ({
  page: target,
}) => {
  const grid = await openList(target, { shape: "exported" });
  await watch(target);
  const local = list().rows.find(
    (row) => row.modelo === "130" && row.opens_local_work,
  );
  if (!local) throw new Error("no local declaration of 130 is listed");
  await target
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label"),
    })
    .fill("130");
  await rowsOf(grid, "130")
    .filter({ hasText: local.period_words ?? local.modelo_title })
    .filter({ hasText: local.state_words })
    .first()
    .dblclick();
  await expect(views(target)).toBeVisible();
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  await target.waitForTimeout(1500);
  const counted = await reads(target);
  expect(counted.form).toBe(1);
  expect(counted.filingState).toBe(0);
});
