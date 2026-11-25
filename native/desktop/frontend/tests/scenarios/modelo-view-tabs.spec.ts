import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The first press on a Modelo view tab opens that view, whenever it lands:
// straight after the declaration opens, after its read settles, and after a
// write settles. The press is a real pointer sequence at the tab's centre
// with the pause a native driver leaves between its events.

const workspace = (target: Page) => target.locator(".declarations-workspace");
const SIZES = [
  { width: 1441, height: 923 },
  { width: 1280, height: 800 },
  { width: 1024, height: 640 },
  { width: 900, height: 600 },
];

const tabNamed = (target: Page, words: string) =>
  workspace(target).getByRole("tab").filter({ hasText: words }).first();

/** A press at the centre of the tab, the way a native driver sends it. */
async function press(target: Page, words: string) {
  const tab = tabNamed(target, words);
  await expect(tab).toBeVisible();
  const box = (await tab.boundingBox())!;
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await target.mouse.move(x, y, { steps: 3 });
  await target.waitForTimeout(40);
  await target.mouse.down();
  await target.waitForTimeout(60);
  await target.mouse.up();
}

async function openDeclaration(target: Page, size: (typeof SIZES)[number]) {
  await target.setViewportSize(size);
  await target.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=checked",
  );
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

const review = label("workspace.modelo.step.review");
const filing = label("workspace.modelo.filing.title");
const form = label("desktop.modelo.view.form");

for (const size of SIZES) {
  test(`${size.width}x${size.height}: the first press opens the view, right after the declaration opens`, async ({
    page: target,
  }) => {
    await openDeclaration(target, size);
    await press(target, review);
    await expect(tabNamed(target, review)).toHaveAttribute(
      "aria-selected",
      "true",
      { timeout: 1000 },
    );
    await press(target, filing);
    await expect(tabNamed(target, filing)).toHaveAttribute(
      "aria-selected",
      "true",
      { timeout: 1000 },
    );
    await press(target, form);
    await expect(tabNamed(target, form)).toHaveAttribute(
      "aria-selected",
      "true",
      { timeout: 1000 },
    );
  });

  test(`${size.width}x${size.height}: the first press opens the view while the read settles and after a write`, async ({
    page: target,
  }) => {
    await target.setViewportSize(size);
    await target.goto(
      "/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=checked",
    );
    await target.locator("[data-rail=declarations]").click();
    await target.waitForFunction(() => !!window.__fixtureModelo);
    // The declaration read answers late and a verification settles, so the
    // header swaps its next step for the busy words while the press lands.
    await target.evaluate(() => {
      const port = window.__fixtureModelo!;
      const readForm = port.form;
      const submit = port.submit;
      port.form = async (...args) => {
        await new Promise((resolve) => setTimeout(resolve, 150));
        return readForm(...args);
      };
      port.submit = async (...args) => {
        if (args[0] !== "modelo.work.verify") return submit(...args);
        return {
          kind: "settled",
          operation_id: "verify-1",
          result: {},
        } as Awaited<ReturnType<typeof submit>>;
      };
    });
    await target
      .locator(".declarations-page")
      .getByRole("grid")
      .locator("[data-kind=data]")
      .filter({ hasText: "Modelo 130" })
      .first()
      .dblclick();
    await expect(tabNamed(target, review)).toBeVisible();
    // Pressed while the read is still in flight.
    await press(target, review);
    await expect(tabNamed(target, review)).toHaveAttribute(
      "aria-selected",
      "true",
      { timeout: 1000 },
    );
    await press(target, filing);
    await expect(tabNamed(target, filing)).toHaveAttribute(
      "aria-selected",
      "true",
      { timeout: 1000 },
    );
    // And right after a write settles: the next-step control swaps to the
    // busy words and back, and the press lands in that interval.
    await press(target, form);
    await expect(tabNamed(target, form)).toHaveAttribute(
      "aria-selected",
      "true",
      { timeout: 1000 },
    );
    const verify = workspace(target).getByRole("button", {
      name: label("workspace.modelo.next_button.verify"),
    });
    if (await verify.count()) {
      await verify.click();
      await press(target, review);
      await expect(tabNamed(target, review)).toHaveAttribute(
        "aria-selected",
        "true",
        { timeout: 1000 },
      );
    }
  });
}

const tablistTop = (target: Page) =>
  workspace(target)
    .getByRole("tablist", { name: label("desktop.modelo.views.label") })
    .evaluate((list) => Math.round(list.getBoundingClientRect().top));

for (const size of SIZES) {
  test(`${size.width}x${size.height}: opening a view or swapping the step for the busy words does not move the tabs`, async ({
    page: target,
  }) => {
    // The step that resolves a stale box is offered on the form and not on
    // the check it opens, which used to shorten the header by a row.
    await target.setViewportSize(size);
    await target.goto(
      "/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=stale",
    );
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
    await expect
      .poll(async () => {
        const first = await tablistTop(target);
        await target.waitForTimeout(150);
        return first === (await tablistTop(target));
      })
      .toBe(true);
    const settled = await tablistTop(target);
    for (const words of [review, filing, form, review, form]) {
      await press(target, words);
      await expect(tabNamed(target, words)).toHaveAttribute(
        "aria-selected",
        "true",
      );
      await target.waitForTimeout(150);
      expect(await tablistTop(target)).toBe(settled);
    }
  });

  test(`${size.width}x${size.height}: the tabs hold still while the write's own read replaces the step`, async ({
    page: target,
  }) => {
    await target.setViewportSize(size);
    await target.goto(
      "/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=checked",
    );
    await target.locator("[data-rail=declarations]").click();
    await target.waitForFunction(() => !!window.__fixtureModelo);
    await target.evaluate(() => {
      const port = window.__fixtureModelo!;
      const readForm = port.form;
      const submit = port.submit;
      let afterVerify = false;
      port.form = async (...args) => {
        const served = await readForm(...args);
        const verifying = {
          ...served,
          next_step: { ...served.next_step!, action: "verify" as const },
        };
        if (!afterVerify) return verifying;
        await new Promise((resolve) => setTimeout(resolve, 600));
        return verifying;
      };
      port.submit = async (...args) => {
        if (args[0] !== "modelo.work.verify") return submit(...args);
        afterVerify = true;
        return {
          kind: "settled",
          operation_id: "verify-1",
          result: {},
        } as Awaited<ReturnType<typeof submit>>;
      };
    });
    await target
      .locator(".declarations-page")
      .getByRole("grid")
      .locator("[data-kind=data]")
      .filter({ hasText: "Modelo 130" })
      .first()
      .dblclick();
    const verify = workspace(target).getByRole("button", {
      name: label("workspace.modelo.next_button.verify"),
    });
    await expect(verify).toBeVisible();
    await target.waitForTimeout(300);
    const tops = [await tablistTop(target)];
    await verify.click();
    for (let step = 0; step < 14; step++) {
      tops.push(await tablistTop(target));
      await target.waitForTimeout(80);
    }
    // The header may grow as the write's words arrive; it never gives the
    // room back while the busy words stand in for the step and the read
    // that replaces them answers.
    expect(tops).toEqual([...tops].sort((a, b) => a - b));
  });
}

test("a press opens the view from the pointer event alone and from the click alone", async ({
  page: target,
}) => {
  await openDeclaration(target, SIZES[0]!);
  await tabNamed(target, review).dispatchEvent("pointerdown", {
    button: 0,
    pointerType: "mouse",
  });
  await expect(tabNamed(target, review)).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await tabNamed(target, filing).dispatchEvent("click");
  await expect(tabNamed(target, filing)).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // A secondary button opens nothing.
  await tabNamed(target, form).dispatchEvent("pointerdown", {
    button: 2,
    pointerType: "mouse",
  });
  await expect(tabNamed(target, filing)).toHaveAttribute(
    "aria-selected",
    "true",
  );
});
