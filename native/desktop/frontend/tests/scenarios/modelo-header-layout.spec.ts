import { expect, type Page, test } from "@playwright/test";
import { label } from "../support/strings";
import { openDeclaration } from "../support/scenarioModelo";
import {
  applyButton,
  review,
  stage,
  TYPED_06,
} from "../support/scenarioModeloWrites";

// The declaration's header keeps its geometry while what it says changes:
// the result, the next step and the words of an operation still running are
// swapped for each other as the declaration is edited, applied and read
// again, and none of that moves the tabs below, the result's figure or the
// step's place. Long words are cut to their room with the whole text one
// hover or focus away; the layout follows the window's width, never the
// words.

const WIDTHS = [
  { name: "desktop", width: 1440 },
  { name: "narrow", width: 820 },
] as const;

/** Whole pixels; sub-pixel rounding differs between two draws. */
const SLACK = 1;

const header = (target: Page) =>
  target.locator(".declarations-workspace").locator("header").first();

type Box = { x: number; y: number; width: number; height: number };

/** The header's frame and the places of the parts the tests hold still. */
async function geometry(target: Page, amountText: string | null) {
  const head = await header(target).boundingBox();
  const tabs = await target
    .locator(".declarations-workspace")
    .getByRole("tablist")
    .first()
    .boundingBox();
  const amount = amountText
    ? await header(target)
        .getByText(amountText, { exact: true })
        .first()
        .boundingBox()
    : null;
  return { head: head!, tabs: tabs!, amount };
}

const right = (box: Box) => box.x + box.width;
const middle = (box: Box) => box.y + box.height / 2;

/** Holds the window's read of its own settled write until released. */
const holdRead = (target: Page) =>
  target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const read = port.form;
    const gate = window as unknown as { __releaseRead?: () => void };
    port.form = async (...args) => {
      await new Promise<void>((release) => {
        gate.__releaseRead = release;
      });
      return read(...args);
    };
  });

const releaseRead = (target: Page) =>
  target.evaluate(() =>
    (window as unknown as { __releaseRead: () => void }).__releaseRead(),
  );

for (const { name, width } of WIDTHS) {
  test(`${name}: the header keeps its geometry while its status changes`, async ({
    page: target,
  }) => {
    await target.setViewportSize({ width, height: 1000 });
    await openDeclaration(target, "130", { shape: "edit" });
    // The figure as the edit shape serves it, read where the header draws it.
    const amount = await header(target)
      .locator("[data-header-figure]")
      .textContent();
    if (!amount) throw new Error("the 130 serves no stated result");

    const initial = await geometry(target, amount);
    expect(initial.amount).not.toBeNull();
    const step = await header(target)
      .locator("[data-header-step]")
      .getByRole("button")
      .boundingBox();
    // The figure and the step share one line: their middles agree.
    expect
      .soft(
        Math.abs(middle(initial.amount!) - middle(step!)),
        "figure and step",
      )
      .toBeLessThanOrEqual(SLACK);

    await stage(target, "06", TYPED_06);
    const staged = await geometry(target, amount);

    const dialog = await review(target);
    await holdRead(target);
    await applyButton(dialog).click();
    await expect(
      dialog.getByText(label("workspace.modelo.operation.done")),
    ).toBeVisible();
    await dialog
      .getByRole("button", { name: label("workspace.modelo.key.close") })
      .last()
      .click();
    await expect(
      header(target).getByText(label("desktop.navigation.busy")),
    ).toBeVisible();
    const reading = await geometry(target, amount);

    await releaseRead(target);
    await expect(
      header(target).getByText(label("desktop.navigation.busy")),
    ).toHaveCount(0);
    const settled = await geometry(target, null);
    // The result's sentence starts on the step's line: its first line and
    // the step's button share one middle.
    const sentence = await header(target)
      .locator("[data-header-result] .line-clamp-2")
      .evaluate((node) => {
        const box = node.getBoundingClientRect();
        return box.top + parseFloat(getComputedStyle(node).lineHeight) / 2;
      });
    const settledStep = await header(target)
      .locator("[data-header-step]")
      .getByRole("button")
      .boundingBox();
    expect
      .soft(Math.abs(sentence - middle(settledStep!)), "sentence and step")
      .toBeLessThanOrEqual(SLACK);

    for (const [state, drawn] of Object.entries({ staged, reading, settled })) {
      // The tabs never move under a press.
      expect
        .soft(drawn.tabs.y, `tabs in ${state}`)
        .toBeCloseTo(initial.tabs.y, 0);
      expect
        .soft(drawn.head.height, `header in ${state}`)
        .toBeCloseTo(initial.head.height, 0);
    }
    for (const [state, drawn] of Object.entries({ staged, reading })) {
      // The figure keeps its place whatever stands beside it.
      expect
        .soft(
          Math.abs(right(drawn.amount!) - right(initial.amount!)),
          `figure's edge in ${state}`,
        )
        .toBeLessThanOrEqual(SLACK);
      expect
        .soft(
          Math.abs(drawn.amount!.y - initial.amount!.y),
          `figure's line in ${state}`,
        )
        .toBeLessThanOrEqual(SLACK);
    }
  });
}

const LONG =
  " and this sentence goes on to say a great deal more than the room that the header keeps for it could ever hold on one line";

/** Lengthens every sentence the header serves before the window reads it. */
const lengthenServedWords = (target: Page) =>
  target.addInitScript((tail) => {
    type Served = {
      header: {
        deadline: { text: string } | null;
        file: { words: string } | null;
        result: { words: string | null; short_text: string } | null;
      };
    };
    type Port = { form: (...args: unknown[]) => Promise<Served> };
    const wrapped = new WeakSet<object>();
    let held: Port | undefined;
    Object.defineProperty(window, "__fixtureModelo", {
      configurable: true,
      get: () => held,
      set(port: Port) {
        held = port;
        if (wrapped.has(port)) return;
        wrapped.add(port);
        const read = port.form.bind(port);
        port.form = async (...args: unknown[]) => {
          const envelope = structuredClone(await read(...args));
          const header = envelope.header;
          if (header.deadline) header.deadline.text += tail;
          if (header.file) header.file.words += tail;
          if (header.result) {
            if (header.result.words) header.result.words += tail;
            header.result.short_text += tail;
          }
          return envelope;
        };
      },
    });
  }, LONG);

for (const { name, width } of WIDTHS) {
  test(`${name}: long words keep the header's height and are reachable whole`, async ({
    browser,
    page: target,
  }) => {
    await target.setViewportSize({ width, height: 1000 });
    await openDeclaration(target, "130", { shape: "edit" });
    const short = await geometry(target, null);
    const deadline = await header(target)
      .getByText(/^Deadline/)
      .first()
      .textContent();
    if (!deadline) throw new Error("the 130 serves no deadline");

    // A window of its own: a reload would reopen the declaration last shown.
    const context = await browser.newContext({
      viewport: { width, height: 1000 },
    });
    const longer = await context.newPage();
    await lengthenServedWords(longer);
    await openDeclaration(longer, "130", { shape: "edit" });
    const long = await geometry(longer, null);
    expect.soft(long.head.height, "header").toBeCloseTo(short.head.height, 0);
    expect.soft(long.tabs.y, "tabs").toBeCloseTo(short.tabs.y, 0);

    // Nothing in the header runs past its edge.
    const overflow = await header(longer).evaluate(
      (node) => node.scrollWidth - node.clientWidth,
    );
    expect.soft(overflow, "overflow").toBeLessThanOrEqual(0);

    // The deadline cut to its room is read whole on hover.
    await header(longer).getByText(deadline, { exact: false }).first().hover();
    await expect
      .soft(longer.getByRole("tooltip").filter({ hasText: deadline + LONG }))
      .toBeVisible();
    await context.close();
  });
}
