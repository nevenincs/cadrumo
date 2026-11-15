import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { filing } from "../support/scenarioModeloWrites";
import { openDeclaration, tab } from "../support/scenarioModelo";

// Recording the filing locally. The runtime answers the write as running and
// the window follows it; the filing state it then reads is slow. The filing
// state serves the filed header's step, the journey and the next step as well
// as the filing words, so after the write settles the window reads by itself,
// says it is reading while it does, draws all of them when the filing state
// answers, never reads the whole form behind it and never leaves a write hold
// asking the person to read again.

const BUSY = () => label("desktop.navigation.busy");
const recordButton = (target: Page) =>
  target.getByRole("button", {
    name: label("workspace.modelo.filing.record_as_filed"),
  });
/** The header's words once the declaration is recorded; they are the served
 * next step's. */
const headerRecorded = (target: Page) =>
  target
    .locator("header")
    .getByText(label("workspace.modelo.next.recorded", { date: "" }).trim(), {
      exact: false,
    });
const readAgain = (target: Page) =>
  target.getByRole("button", { name: label("workspace.modelo.read_again") });
const busyNotice = (target: Page) =>
  target.locator('[data-slot="alert"]').filter({ hasText: BUSY() });
const fileStep = (target: Page) =>
  target.locator('[data-journey] [data-step="file"]').first();
const recordedHere = (target: Page) =>
  target.getByText(label("workspace.modelo.filing.recorded_here")).first();

type Gates = {
  filingStateMs: number;
  holdFilingState: boolean;
  releaseFilingState: (() => void) | null;
  holdForm: boolean;
  releaseForm: (() => void) | null;
  answeredFilingState: number | null;
  answeredForm: number | null;
  forms: number;
  filingStates: number;
};
declare global {
  interface Window {
    __fileGates?: Gates;
  }
}

/** The local filing answers "running" and settles on the second look, as the
 * runtime's does; the filing state takes `filingStateMs` and can be held, and
 * the form read can be held. */
async function gate(target: Page, filingStateMs: number) {
  await target.evaluate((filingStateMs) => {
    const port = window.__fixtureModelo!;
    const state: Gates = (window.__fileGates = {
      filingStateMs,
      holdFilingState: false,
      releaseFilingState: null,
      holdForm: false,
      releaseForm: null,
      answeredFilingState: null,
      answeredForm: null,
      forms: 0,
      filingStates: 0,
    });
    const submit = port.submit;
    const form = port.form;
    let settled: Awaited<ReturnType<typeof submit>> | null = null;
    let looks = 0;
    port.submit = async (...args) => {
      if (args[0] === "modelo.work.filing_state") {
        state.filingStates += 1;
        if (state.holdFilingState)
          await new Promise<void>((release) => {
            state.releaseFilingState = release;
          });
        else await new Promise((done) => setTimeout(done, state.filingStateMs));
        const answer = await submit(...args);
        state.answeredFilingState = performance.now();
        return answer;
      }
      const result = await submit(...args);
      if (args[0] !== "modelo.work.file") return result;
      settled = result;
      return {
        kind: "running",
        operation_id: "operation-file-running",
        revision: 1,
        cancellable: false,
      } as Awaited<ReturnType<typeof submit>>;
    };
    port.observe = async (operation) => {
      if (operation !== "operation-file-running") throw { code: "unavailable" };
      looks += 1;
      return looks > 1 && settled
        ? (settled as Awaited<ReturnType<typeof port.observe>>)
        : ({
            kind: "running",
            operation_id: operation,
            revision: 1,
            cancellable: false,
          } as Awaited<ReturnType<typeof port.observe>>);
    };
    port.form = async (...args) => {
      state.forms += 1;
      if (state.holdForm)
        await new Promise<void>((release) => {
          state.releaseForm = release;
        });
      const answer = await form(...args);
      state.answeredForm = performance.now();
      return answer;
    };
  }, filingStateMs);
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

/** Opens the exported 130's Export and record view, ready to record. */
async function ready(target: Page, filingStateMs: number) {
  await filing(target, "exported");
  await expect(recordButton(target)).toBeEnabled();
  // Before the filing the header says nothing of a record, and the file step
  // is the current one.
  await expect(headerRecorded(target)).toHaveCount(0);
  await expect(fileStep(target)).toHaveAttribute("data-status", "current");
  await gate(target, filingStateMs);
}

test("after recording the filing, with the filing state slow, the window reads by itself and ends filed with no hold", async ({
  page: target,
}) => {
  await ready(target, 1000);
  await recordFiling(target);
  // Within the time of both reads, nothing is pressed.
  await expect(recordedHere(target)).toBeVisible({ timeout: 5000 });
  await expect(fileStep(target)).toHaveAttribute("data-status", "done", {
    timeout: 5000,
  });
  await expect(headerRecorded(target)).toBeVisible();
  await expect(busyNotice(target)).toHaveCount(0);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  await expect(readAgain(target)).toHaveCount(0);
  // It stays so: no hold comes back behind it.
  await target.waitForTimeout(1500);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  await expect(readAgain(target)).toHaveCount(0);
  await expect(fileStep(target)).toHaveAttribute("data-status", "done");
});

test("while the filing state is read the page says it is reading and asks nobody to read again", async ({
  page: target,
}) => {
  await ready(target, 0);
  await target.evaluate(() => {
    window.__fileGates!.holdFilingState = true;
  });
  await recordFiling(target);
  await expect
    .poll(() => target.evaluate(() => !!window.__fileGates!.releaseFilingState))
    .toBe(true);
  for (let at = 0; at < 4; at++) {
    await expect(busyNotice(target)).toHaveCount(1);
    await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
    await expect(readAgain(target)).toHaveCount(0);
    await target.waitForTimeout(500);
  }
  await target.evaluate(() => {
    window.__fileGates!.holdFilingState = false;
    window.__fileGates!.releaseFilingState!();
  });
  await expect(recordedHere(target)).toBeVisible();
  await expect(fileStep(target)).toHaveAttribute("data-status", "done");
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
});

test("the filed header, the next step and the filing words show within a second of the filing state, with the whole form held and never read", async ({
  page: target,
}) => {
  await ready(target, 0);
  // The whole form read is held and never released: nothing the header shows
  // may wait for it.
  await target.evaluate(() => {
    window.__fileGates!.holdForm = true;
  });
  await recordFiling(target);
  await expect
    .poll(() => target.evaluate(() => window.__fileGates!.answeredFilingState))
    .not.toBeNull();
  const answered = await target.evaluate(
    () => window.__fileGates!.answeredFilingState!,
  );
  await expect(recordedHere(target)).toBeVisible({ timeout: 1000 });
  await expect(fileStep(target)).toHaveAttribute("data-status", "done", {
    timeout: 1000,
  });
  await expect(headerRecorded(target)).toBeVisible({ timeout: 1000 });
  await expect(busyNotice(target)).toHaveCount(0, { timeout: 1000 });
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0, {
    timeout: 1000,
  });
  await expect(readAgain(target)).toHaveCount(0);
  const drawn = await target.evaluate(() => performance.now());
  expect(drawn - answered).toBeLessThan(2000);
  // It stays so, and the whole form is never read after the record.
  await target.waitForTimeout(1500);
  await expect(fileStep(target)).toHaveAttribute("data-status", "done");
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  expect(
    await target.evaluate(() => ({
      forms: window.__fileGates!.forms,
      filingStates: window.__fileGates!.filingStates,
    })),
  ).toEqual({ forms: 0, filingStates: 1 });
});

test("after a receipt write the filing state alone renews the page, with the whole form held and never read", async ({
  page: target,
}) => {
  await openDeclaration(target, "130", { shape: "filed" });
  await tab(target, "workspace.modelo.filing.title").click();
  const addReceipt = target.getByRole("button", {
    name: label("workspace.modelo.filing.add_receipt_pdf"),
  });
  await expect(addReceipt).toBeEnabled();
  await target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const state = {
      forms: 0,
      filingStates: 0,
      holdForm: true,
    };
    (window as unknown as { __receiptReads: typeof state }).__receiptReads =
      state;
    const submit = port.submit;
    const form = port.form;
    port.submit = (...args) => {
      if (args[0] === "modelo.work.filing_state") state.filingStates += 1;
      return submit(...args);
    };
    port.form = async (...args) => {
      state.forms += 1;
      if (state.holdForm) await new Promise<void>(() => undefined);
      return form(...args);
    };
  });
  await addReceipt.click();
  await expect(target.locator(".modelo-reconciliation")).toBeVisible();
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0, {
    timeout: 1000,
  });
  await expect(busyNotice(target)).toHaveCount(0, { timeout: 1000 });
  await target.waitForTimeout(1500);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  expect(
    await target.evaluate(
      () =>
        (
          window as unknown as {
            __receiptReads: { forms: number; filingStates: number };
          }
        ).__receiptReads,
    ),
  ).toMatchObject({ forms: 0, filingStates: 1 });
});
