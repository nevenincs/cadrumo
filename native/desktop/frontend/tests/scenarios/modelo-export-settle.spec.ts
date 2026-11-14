import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { calls, filing } from "../support/scenarioModeloWrites";

// The export of a filing file runs for seconds. From the press to the
// moment the window has read the declaration again, the page says that it is
// working; once that read has answered, the next step (recording the filing)
// is open without the person pressing "read again".

const BUSY = () => label("desktop.navigation.busy");
const exportButton = (target: Page) =>
  target.getByRole("button", {
    name: label("workspace.modelo.filing.export_again"),
  });
const recordButton = (target: Page) =>
  target.getByRole("button", {
    name: label("workspace.modelo.filing.record_as_filed"),
  });
/** The filing view's own busy notice, apart from the header's. */
const busyNotice = (target: Page) =>
  target.locator('[data-slot="alert"]').filter({ hasText: BUSY() });
const readAgain = (target: Page) =>
  target.getByRole("button", { name: label("workspace.modelo.read_again") });

type Gates = {
  releaseExport: (() => void) | null;
  released: boolean;
  releaseRead: (() => void) | null;
  holdReads: boolean;
};
declare global {
  interface Window {
    __settleGates?: Gates;
  }
}

/** The export settles only when released, as a slow export does; the reads
 * after it are held too once `holdReads` is set. */
async function gate(target: Page) {
  await target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const state: Gates = (window.__settleGates = {
      releaseExport: null,
      released: false,
      releaseRead: null,
      holdReads: false,
    });
    const submit = port.submit;
    // The export answers "running" and is followed with observe, as the
    // runtime's does; it settles when released.
    let settled: Awaited<ReturnType<typeof submit>> | null = null;
    port.submit = async (...args) => {
      const result = await submit(...args);
      if (args[0] !== "modelo.export") return result;
      settled = result;
      return {
        kind: "running",
        operation_id: "operation-export-running",
        revision: 1,
        cancellable: false,
      } as Awaited<ReturnType<typeof submit>>;
    };
    port.observe = async (operation) => {
      if (operation !== "operation-export-running")
        throw { code: "unavailable" };
      if (!state.releaseExport || !state.released)
        state.releaseExport ??= () => {
          state.released = true;
        };
      return state.released && settled
        ? (settled as Awaited<ReturnType<typeof port.observe>>)
        : ({
            kind: "running",
            operation_id: operation,
            revision: 1,
            cancellable: false,
          } as Awaited<ReturnType<typeof port.observe>>);
    };
    const form = port.form;
    port.form = async (...args) => {
      if (state.holdReads)
        await new Promise<void>((release) => {
          state.releaseRead = release;
        });
      return form(...args);
    };
  });
}

test("an export shows that it is working from the press to the answer, then opens recording by itself", async ({
  page: target,
}) => {
  await filing(target, "exported");
  await gate(target);
  await expect(recordButton(target)).toBeEnabled();
  await expect(target.getByText(BUSY())).toHaveCount(0);
  // From the press on, a frame without the busy notice is a gap.
  await target.evaluate((words) => {
    const seen = { frames: 0, runs: "", on: true };
    (window as unknown as { __busyFrames: typeof seen }).__busyFrames = seen;
    const sample = () => {
      if (!seen.on) return;
      seen.frames++;
      const drawn = [...document.querySelectorAll('[data-slot="alert"]')].some(
        (alert) => alert.textContent?.includes(words),
      );
      const mark = drawn ? "1" : "0";
      if (!seen.runs.endsWith(mark)) seen.runs += mark;
      requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  }, BUSY());
  await exportButton(target).click();
  // The export is in flight: the page says so and nothing else is open.
  await expect
    .poll(() => target.evaluate(() => !!window.__settleGates!.releaseExport))
    .toBe(true);
  await expect(busyNotice(target)).toBeVisible();
  await expect(
    exportButton(target).locator('[data-slot="spinner"], [role="progressbar"]'),
  ).not.toHaveCount(0);
  await expect(recordButton(target)).toBeDisabled();
  // It settles and the window reads the declaration again; that read is held.
  await target.evaluate(() => {
    window.__settleGates!.holdReads = true;
  });
  await target.evaluate(() => window.__settleGates!.releaseExport!());
  await expect
    .poll(() => target.evaluate(() => !!window.__settleGates!.releaseRead))
    .toBe(true);
  await expect(busyNotice(target)).toBeVisible();
  await expect(recordButton(target)).toBeDisabled();
  await expect(readAgain(target)).toHaveCount(0);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  const reads = (await calls(target, "modelo form")).length;
  await target.evaluate(() => {
    window.__settleGates!.holdReads = false;
    window.__settleGates!.releaseRead!();
  });
  // The read answered: no hold, no busy words, recording is open, and the
  // person pressed nothing to get here.
  await expect(busyNotice(target)).toHaveCount(0);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  await expect(recordButton(target)).toBeEnabled();
  await expect(exportButton(target)).toBeEnabled();
  const frames = await target.evaluate(() => {
    const seen = (
      window as unknown as {
        __busyFrames: { frames: number; runs: string; on: boolean };
      }
    ).__busyFrames;
    seen.on = false;
    return seen;
  });
  expect(frames.frames).toBeGreaterThan(10);
  // Not drawn before the press is taken, drawn without a break until the
  // read answers, then not drawn: "01", never "0101".
  expect(frames.runs).toMatch(/^0?10$/);
  expect((await calls(target, "modelo form")).length).toBeLessThanOrEqual(
    reads + 1,
  );
  expect(await calls(target, "modelo submit modelo.export")).toHaveLength(1);
});
