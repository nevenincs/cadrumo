import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The three controls in the form's toolbar that arrange the panes around a
// declaration's form: the rail at its start, the details at its end or under
// it, and where the details go. At every window size the app is used at and
// after any sequence of presses, with the declaration opened again between
// them, all three are drawn inside the window and unclipped, each says
// whether it is pressed as the panes are drawn, each has its own icon, and
// every line between the panes, the notes above the form's line among them,
// moves.

const SIZES = [
  { width: 1441, height: 923 },
  { width: 1280, height: 800 },
  { width: 1024, height: 640 },
  { width: 900, height: 600 },
];

type Control = "side" | "details" | "placement";
const CONTROLS: Control[] = ["side", "details", "placement"];

// Every control pressed once and twice in a row, every pair in either order
// and every order of all three.
const SEQUENCES: Control[][] = [];
for (const first of CONTROLS) {
  SEQUENCES.push([first]);
  for (const second of CONTROLS) SEQUENCES.push([first, second]);
}
for (const a of CONTROLS)
  for (const b of CONTROLS)
    for (const c of CONTROLS)
      if (a !== b && b !== c && a !== c) SEQUENCES.push([a, b, c]);

const workspace = (target: Page) => target.locator(".declarations-workspace");
const area = (target: Page) =>
  workspace(target).locator("[role=tabpanel][data-details]");
const toggle = (target: Page, control: Control) =>
  workspace(target).locator(`[data-pane-toggle=${control}]`);
const rail = (target: Page) =>
  workspace(target).getByRole("complementary", {
    name: label("desktop.modelo.side.label"),
  });
const details = (target: Page) =>
  workspace(target).getByRole("complementary", {
    name: label("desktop.modelo.details.label"),
  });
const bandLine = (target: Page) =>
  workspace(target).getByRole("separator", {
    name: label("desktop.modelo.band.resize"),
  });

async function openDeclaration(target: Page) {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=declarations]").click();
  await target
    .locator(".declarations-page")
    .getByRole("grid")
    .locator("[data-kind=data]")
    .filter({ hasText: "Modelo 130" })
    .first()
    .dblclick();
  await expect(
    workspace(target).getByRole("heading", { level: 1 }),
  ).toBeVisible();
}

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() =>
    localStorage.removeItem("cadrumo-shell-layout"),
  );
});

type Shown = { side: boolean; details: boolean; beside: boolean };

const pressed = async (target: Page, control: Control) =>
  (await toggle(target, control).getAttribute("aria-pressed")) === "true";

async function shownNow(target: Page): Promise<Shown> {
  return {
    side: await pressed(target, "side"),
    details: await pressed(target, "details"),
    beside: await pressed(target, "placement"),
  };
}

/** Each control drawn once, inside the window, on top where it is drawn,
 * with an icon of its own. */
async function expectControlsReachable(target: Page) {
  const seen = await workspace(target).evaluate((root) =>
    ["side", "details", "placement"].map((name) => {
      const found = root.querySelectorAll<HTMLElement>(
        `[data-pane-toggle=${name}]`,
      );
      const button = found[0];
      const box = button?.getBoundingClientRect();
      const hit =
        box &&
        document.elementFromPoint(
          box.left + box.width / 2,
          box.top + box.height / 2,
        );
      return {
        name,
        count: found.length,
        inside:
          !!box &&
          box.width > 0 &&
          box.left >= 0 &&
          box.top >= 0 &&
          box.right <= window.innerWidth &&
          box.bottom <= window.innerHeight,
        onTop: !!hit && !!button?.contains(hit),
        icon: button
          ?.querySelector("svg[data-icon]")
          ?.getAttribute("data-icon"),
        glyph: button?.querySelector("svg")?.innerHTML ?? "",
      };
    }),
  );
  for (const control of seen) {
    expect(control.count, `${control.name} drawn once`).toBe(1);
    expect(control.inside, `${control.name} inside the window`).toBe(true);
    expect(control.onTop, `${control.name} not covered or clipped`).toBe(true);
  }
  expect(new Set(seen.map((control) => control.icon)).size).toBe(3);
  expect(new Set(seen.map((control) => control.glyph)).size).toBe(3);
  return Object.fromEntries(seen.map((c) => [c.name, c.icon]));
}

/** The panes are drawn as the controls say, with the icons that say it. */
async function expectDrawnAs(target: Page, shown: Shown) {
  for (const [control, on] of [
    ["side", shown.side],
    ["details", shown.details],
    ["placement", shown.beside],
  ] as const)
    await expect(toggle(target, control)).toHaveAttribute(
      "aria-pressed",
      String(on),
    );
  await expect(rail(target)).toHaveCount(shown.side ? 1 : 0);
  await expect(details(target)).toHaveCount(shown.details ? 1 : 0);
  await expect(area(target)).toHaveAttribute(
    "data-details",
    shown.details ? (shown.beside ? "side" : "bottom") : "closed",
  );
  const icons = await expectControlsReachable(target);
  expect(icons).toEqual({
    side: "panelLeft",
    details: shown.beside ? "panelRight" : "panelBottom",
    placement: shown.beside ? "splitBeside" : "splitUnder",
  });
}

const valueOf = async (target: Page, index: number) =>
  Number(
    await workspace(target)
      .locator("[data-slot=resize-handle]")
      .nth(index)
      .getAttribute("aria-valuenow"),
  );

/** Every line in the form's area moves from its least to its most, and the
 * rail and details each have one while they are shown. */
async function expectLinesMove(target: Page, shown: Shown) {
  const lines = workspace(target).locator("[data-slot=resize-handle]");
  const names = await lines.evaluateAll((all) =>
    all.map((line) => line.getAttribute("aria-label")),
  );
  if (shown.side) expect(names).toContain(label("desktop.modelo.side.resize"));
  if (shown.details)
    expect(names).toContain(label("desktop.modelo.details.resize"));
  for (let index = 0; index < names.length; index++) {
    await lines.nth(index).focus();
    const where = `${names[index]} with ${JSON.stringify(shown)}`;
    await target.keyboard.press("Home");
    await expect.poll(() => valueOf(target, index), where).toBe(0);
    await target.keyboard.press("End");
    await expect.poll(() => valueOf(target, index), where).toBe(100);
    await target.keyboard.press("Enter");
  }
}

function press(shown: Shown, control: Control): Shown {
  if (control === "side") return { ...shown, side: !shown.side };
  if (control === "details") return { ...shown, details: !shown.details };
  return { ...shown, beside: !shown.beside };
}

for (const size of SIZES) {
  test(`UX-19 at ${size.width} by ${size.height} the three pane controls stay, say their state and draw distinct icons after every sequence of presses`, async ({
    page: target,
  }) => {
    test.setTimeout(600_000);
    await target.setViewportSize(size);
    await openDeclaration(target);
    for (const sequence of SEQUENCES) {
      await target.evaluate(() =>
        localStorage.removeItem("cadrumo-pane-preferences"),
      );
      await openDeclaration(target);
      let shown = await shownNow(target);
      await expectDrawnAs(target, shown);
      for (const control of sequence) {
        await toggle(target, control).click();
        shown = press(shown, control);
        await expectDrawnAs(target, shown);
      }
      await expectLinesMove(target, shown);
      // The arrangement is the viewer's and comes back with the declaration.
      await openDeclaration(target);
      await expectDrawnAs(target, shown);
    }
  });

  test(`UX-19 at ${size.width} by ${size.height} the notes above the form are sized by their line and keep their height`, async ({
    page: target,
  }) => {
    await target.setViewportSize(size);
    await openDeclaration(target);
    const band = workspace(target).locator("aside[data-form-gives-way]");
    const height = () =>
      band.evaluate((element) => element.getBoundingClientRect().height);
    const line = bandLine(target);
    await expect(line).toHaveAttribute("aria-orientation", "horizontal");
    await line.focus();
    await target.keyboard.press("Home");
    const least = await height();
    await target.keyboard.press("ArrowDown");
    await expect.poll(height).toBeGreaterThan(least);
    await target.keyboard.press("Home");
    const box = await line.boundingBox();
    if (!box) throw new Error("the line is not drawn");
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    await target.mouse.move(x, y);
    await target.mouse.down();
    await target.mouse.move(x, y + 30, { steps: 4 });
    await target.mouse.up();
    await expect.poll(height).toBeGreaterThan(least + 20);
    const drawn = await height();
    // The form keeps its least room under the notes at their most.
    await line.focus();
    await target.keyboard.press("End");
    const form = workspace(target).locator("[data-modelo-form]");
    const formLeast = await form.evaluate(
      (element) => parseFloat(getComputedStyle(element).minHeight) || 0,
    );
    expect(
      await form.evaluate((element) => element.getBoundingClientRect().height),
    ).toBeGreaterThanOrEqual(formLeast - 1);
    await target.keyboard.press("Home");
    await target.keyboard.press("ArrowDown");
    const chosen = await height();
    expect(chosen).not.toBeCloseTo(drawn, 0);
    await openDeclaration(target);
    await expect.poll(height).toBeCloseTo(chosen, 0);
  });
}

// The native window audit's own sequence (window-ux-audit.test.mjs, UX-19
// and UX-16), step for step at the native window's inner sizes: details on,
// then at each size the form view with the rail and details on, the rail
// off and on, the details off and on, the arrangement off and on, another
// view and back; after each step all three controls are drawn inside the
// window with distinct icons and the group does not move. Then the details
// under the form: their line takes focus and moves from Home to End, inside
// the window, and the arrangement chosen survives another view and a new
// opening.
const NATIVE_SIZES = [
  { width: 1427, height: 915 },
  { width: 1267, height: 793 },
  { width: 1011, height: 632 },
  { width: 887, height: 592 },
];

async function setControl(target: Page, control: Control, on: boolean) {
  if ((await pressed(target, control)) !== on)
    await toggle(target, control).click();
  await expect(toggle(target, control)).toHaveAttribute(
    "aria-pressed",
    String(on),
  );
}

async function chooseView(target: Page, key: string) {
  await workspace(target)
    .getByRole("tablist", { name: label("desktop.modelo.views.label") })
    .getByRole("tab", { name: label(key) })
    .click();
}

const groupLeft = (target: Page) =>
  workspace(target)
    .locator("[data-pane-toggles]")
    .evaluate((element) => Math.round(element.getBoundingClientRect().left));

test("UX-19 and UX-16 the native audit's toggle sequence at the native inner sizes", async ({
  page: target,
}) => {
  test.setTimeout(300_000);
  await target.setViewportSize(NATIVE_SIZES[0]!);
  await openDeclaration(target);
  await chooseView(target, "desktop.modelo.view.form");
  await setControl(target, "details", true);
  for (const size of NATIVE_SIZES) {
    await target.setViewportSize(size);
    const steps: [string, () => Promise<void>][] = [
      [
        "form view",
        async () => {
          await chooseView(target, "desktop.modelo.view.form");
          await setControl(target, "side", true);
          await setControl(target, "details", true);
        },
      ],
      ["side off", () => setControl(target, "side", false)],
      ["side on", () => setControl(target, "side", true)],
      ["details off", () => setControl(target, "details", false)],
      ["details on", () => setControl(target, "details", true)],
      ["placement off", () => setControl(target, "placement", false)],
      ["placement on", () => setControl(target, "placement", true)],
      [
        "other view and back",
        async () => {
          await chooseView(target, "workspace.modelo.step.review");
          await chooseView(target, "desktop.modelo.view.form");
        },
      ],
    ];
    let left: number | null = null;
    for (const [name, act] of steps) {
      await test.step(`${name} at ${size.width}x${size.height}`, async () => {
        await act();
        await expectDrawnAs(target, await shownNow(target));
        const now = await groupLeft(target);
        if (left !== null) expect(now, "the group stays put").toBe(left);
        left = now;
      });
    }
    await test.step(`the stacked line at ${size.width}x${size.height}`, async () => {
      for (const side of [true, false]) {
        await setControl(target, "side", side);
        await setControl(target, "details", true);
        await setControl(target, "placement", false);
        const line = workspace(target).getByRole("separator", {
          name: label("desktop.modelo.details.resize"),
        });
        await line.focus();
        await expect(line).toBeFocused();
        const height = () =>
          details(target).evaluate((e) => e.getBoundingClientRect().height);
        await target.keyboard.press("Home");
        const least = await height();
        await target.keyboard.press("End");
        await expect.poll(height).toBeGreaterThan(least);
        await target.keyboard.press("Enter");
        // The arrangement survives another view and a new opening.
        await chooseView(target, "workspace.modelo.step.review");
        await chooseView(target, "desktop.modelo.view.form");
        await expect(area(target)).toHaveAttribute("data-details", "bottom");
      }
      await openDeclaration(target);
      await expect(area(target)).toHaveAttribute("data-details", "bottom");
      await setControl(target, "placement", true);
      await openDeclaration(target);
      await expect(area(target)).toHaveAttribute("data-details", "side");
    });
  }
});
