import { expect, type Locator, type Page, test } from "@playwright/test";
import { label } from "../support/strings";
import {
  boxRow,
  openDeclaration,
  openFromDialog,
} from "../support/scenarioModelo";
import { stage, TYPED_06 } from "../support/scenarioModeloWrites";

// Coming back to a declaration draws its last read at once, but that read is
// only the last one: until the fresh read lands the window says it is
// refreshing, and nothing on the form can be edited, staged or applied. When
// the fresh read lands the state clears and the form takes edits; a read that
// fails leaves the manual control to read again, not a form stuck read-only.

const SAMPLE_MS = 300;

const workspace = (target: Page) => target.locator(".declarations-workspace");
const header = (target: Page) => workspace(target).locator("header").first();
const busy = (target: Page) =>
  header(target).getByText(label("desktop.navigation.busy"));
const cell = (target: Page) =>
  boxRow(target, "06").getByRole("gridcell").nth(2).getByRole("button");
const nextSteps = (target: Page): Locator =>
  header(target).getByRole("button", {
    name: new RegExp(
      `^(${[
        "fill",
        "confirm",
        "resolve",
        "calculate",
        "recalculate",
        "verify",
        "apply",
      ]
        .map((action) => label(`workspace.modelo.next_button.${action}`))
        .join("|")})$`,
    ),
  });

declare global {
  interface Window {
    __keptReadFails?: boolean;
    __releaseKeptRead?: () => void;
  }
}

/** Opens the 130, goes to the Ledger and holds the next read of a form until
 * released, then comes back: the kept read is drawn while the read waits. */
async function returnWithHeldRead(target: Page, readFails = false) {
  await openDeclaration(target, "130", { shape: "edit" });
  await expect(cell(target)).toBeEnabled();
  await leaveAndReturn(target, readFails);
  await expect(boxRow(target, "06")).toBeVisible({ timeout: 2000 });
}

async function leaveAndReturn(target: Page, readFails: boolean) {
  await target.evaluate((fails) => {
    const port = window.__fixtureModelo!;
    const read = port.form;
    window.__keptReadFails = fails;
    port.form = async (...args) => {
      await new Promise<void>((release) => {
        window.__releaseKeptRead = release;
      });
      if (window.__keptReadFails)
        throw Object.assign(new Error("fixture read failure"), {
          code: "unavailable",
        });
      return read(...args);
    };
  }, readFails);
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator("section.ledger-page")).toBeVisible();
  await target.locator("[data-rail=declarations]").click();
}

const release = (target: Page) =>
  target.evaluate(() => {
    const open = window.__releaseKeptRead;
    window.__releaseKeptRead = undefined;
    open?.();
  });
const released = (target: Page) =>
  target.evaluate(() => typeof window.__releaseKeptRead);

/** What the form offers right now, sampled in one evaluation. */
const offers = async (target: Page) => ({
  busy: await busy(target).isVisible(),
  cellEnabled: await cell(target).isEnabled(),
  nextSteps: await nextSteps(target).count(),
});

test("the kept read is marked as refreshing and cannot be edited until the fresh read lands", async ({
  page: target,
}) => {
  await returnWithHeldRead(target);
  const samples: Awaited<ReturnType<typeof offers>>[] = [];
  for (let at = 0; at < 6; at += 1) {
    samples.push(await offers(target));
    await target.waitForTimeout(SAMPLE_MS);
  }
  // Every sample across the wait: drawn, refreshing, read-only, no step.
  for (const sample of samples)
    expect(sample).toEqual({ busy: true, cellEnabled: false, nextSteps: 0 });
  // Trying to enter a value does nothing.
  await boxRow(target, "06").click({ position: { x: 4, y: 4 } });
  await target.keyboard.press("Enter");
  await expect(
    target.getByRole("textbox", {
      name: label("workspace.modelo.editor.new_value_for_box", { box: "06" }),
    }),
  ).toHaveCount(0);
  await release(target);
  await expect(busy(target)).toHaveCount(0);
  await expect(cell(target)).toBeEnabled();
  await stage(target, "06", TYPED_06);
});

test("a failed fresh read leaves the manual control to read again, and the form read-only until it lands", async ({
  page: target,
}) => {
  await returnWithHeldRead(target, true);
  await release(target);
  await expect(busy(target)).toHaveCount(0);
  const again = target
    .locator(".modelo-write-hold")
    .getByRole("button", { name: label("workspace.modelo.read_again") });
  await expect(again).toBeVisible();
  // The last read is not a fresh one: still not editable.
  await expect(cell(target)).toBeDisabled();
  await target.evaluate(() => {
    window.__keptReadFails = false;
  });
  await again.click();
  // The read goes again, and the control and the form wait for it.
  await expect(busy(target)).toBeVisible();
  await expect(cell(target)).toBeDisabled();
  await expect.poll(() => released(target)).toBe("function");
  await release(target);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  await expect(cell(target)).toBeEnabled();
  await stage(target, "06", TYPED_06);
});

test("the offers of statements are shown and take no tick or staging until the fresh read lands", async ({
  page: target,
}) => {
  await openFromDialog(target, "100", "en", "rental-carry");
  const offer = target.locator("section[data-statements]");
  const ticks = offer.getByRole("checkbox");
  await expect(ticks.first()).toBeEnabled();
  await leaveAndReturn(target, false);
  await expect(offer).toBeVisible({ timeout: 2000 });
  await expect(busy(target)).toBeVisible();
  const count = await ticks.count();
  expect(count).toBeGreaterThan(0);
  for (let at = 0; at < count; at += 1)
    await expect(ticks.nth(at)).toBeDisabled();
  await expect(
    offer.getByRole("button", {
      name: label("desktop.modelo.statements.stage"),
    }),
  ).toBeDisabled();
  await release(target);
  await expect(busy(target)).toHaveCount(0);
  await expect(ticks.first()).toBeEnabled();
});
