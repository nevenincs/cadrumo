import { expect, test, type Page } from "@playwright/test";

// Every button of the left rail, Settings and the bottom-panel toggle among
// them, lies inside the window at each size the window is audited at: the
// rail compacts its spacing rather than hiding its last buttons below the
// window's edge behind a scroll nobody can see.
const SIZES = [
  [1441, 923],
  [1280, 800],
  [1024, 640],
  [900, 600],
] as const;

// The least side a rail button keeps with a mouse; a finger-sized rail is
// held to its own floor in touch.spec.ts.
const BUTTON_FLOOR = 32;

const open = async (
  target: Page,
  scenario: string,
  size: readonly [number, number],
) => {
  await target.setViewportSize({ width: size[0], height: size[1] });
  await target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);
  await expect(target.locator("[data-rail=settings]")).toBeVisible();
};

const railBoxes = (target: Page) =>
  target.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>(".rail button")]
      .filter((button) => button.getClientRects().length > 0)
      .map((button) => {
        const { left, top, right, bottom } = button.getBoundingClientRect();
        return {
          name: button.dataset.rail ?? button.getAttribute("aria-label") ?? "",
          left: Math.round(left),
          top: Math.round(top),
          right: Math.round(right),
          bottom: Math.round(bottom),
        };
      }),
  );

for (const scenario of ["signed-in", "ledger"])
  for (const size of SIZES)
    test(`every rail button lies inside the window (${scenario}) at ${size[0]}x${size[1]}`, async ({
      page: target,
    }) => {
      await target.addInitScript(() =>
        localStorage.removeItem("cadrumo-shell-layout"),
      );
      await open(target, scenario, size);
      const [width, height] = size;
      const buttons = await railBoxes(target);
      expect(buttons.map((button) => button.name)).toEqual(
        expect.arrayContaining(["settings", "panel"]),
      );
      for (const button of buttons) {
        const { name, left, top, right, bottom } = button;
        expect(
          left >= 0 && top >= 0 && right <= width && bottom <= height,
          `rail button ${name} [${left},${top},${right},${bottom}] lies inside the ${width}x${height} window`,
        ).toBe(true);
        expect(right - left, `${name} is wide enough`).toBeGreaterThanOrEqual(
          BUTTON_FLOOR,
        );
        expect(bottom - top, `${name} is high enough`).toBeGreaterThanOrEqual(
          BUTTON_FLOOR,
        );
      }
      // Compacting never lets two buttons overlap.
      const sorted = [...buttons].sort((a, b) => a.top - b.top);
      sorted.forEach((button, index) => {
        const before = sorted[index - 1];
        if (before)
          expect(
            button.top >= before.bottom,
            `${button.name} does not overlap ${before.name}`,
          ).toBe(true);
      });
    });
