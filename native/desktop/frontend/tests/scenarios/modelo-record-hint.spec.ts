import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { filing } from "../support/scenarioModeloWrites";

// After an export settles, the window reads the declaration again. While that
// read is outstanding the record button is closed; the words beside it must
// say why (the busy words), never the served "available" sentence. Once the
// read answers, the button is open with the served words.

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

type Gates = {
  releaseRead: (() => void) | null;
  holdReads: boolean;
};
declare global {
  interface Window {
    __recordHintGates?: Gates;
  }
}

test("while the window re-reads after an export, the record button's words say why it is closed", async ({
  page: target,
}) => {
  await filing(target, "exported");
  await target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const state: Gates = (window.__recordHintGates = {
      releaseRead: null,
      holdReads: false,
    });
    const form = port.form;
    port.form = async (...args) => {
      if (state.holdReads)
        await new Promise<void>((release) => {
          state.releaseRead = release;
        });
      return form(...args);
    };
  });
  await expect(recordButton(target)).toBeEnabled();
  await expect(recordRow(target)).toContainText(AVAILABLE());
  await target.evaluate(() => {
    window.__recordHintGates!.holdReads = true;
  });
  await exportButton(target).click();
  await expect
    .poll(() => target.evaluate(() => !!window.__recordHintGates!.releaseRead))
    .toBe(true);

  // Sample the held read for six seconds.
  const samples: { disabled: boolean; row: string; busy: boolean }[] = [];
  for (let at = 0; at < 12; at++) {
    samples.push({
      disabled: await recordButton(target).isDisabled(),
      row: (await recordRow(target).innerText()).replace(/\s+/g, " "),
      busy: (await busyNotice(target).count()) > 0,
    });
    await target.waitForTimeout(500);
  }
  expect(samples.every((sample) => sample.disabled)).toBe(true);
  for (const sample of samples) {
    expect(sample.row).not.toContain(AVAILABLE());
    expect(sample.row).toContain(BUSY());
    expect(sample.busy).toBe(true);
  }

  await target.evaluate(() => {
    window.__recordHintGates!.holdReads = false;
    window.__recordHintGates!.releaseRead!();
  });
  await expect(busyNotice(target)).toHaveCount(0);
  await expect(recordButton(target)).toBeEnabled();
  await expect(recordRow(target)).toContainText(AVAILABLE());
  await expect(recordRow(target)).not.toContainText(BUSY());
});
