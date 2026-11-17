import { expect, test, type Page } from "@playwright/test";
import { openFromDialog, tab } from "../support/scenarioModelo";

// The details of a Modelo 100's form go under it and back by their
// arrangement control, and the form's scroller takes the wheel, as the
// package audit measures them in Spanish at the native window's inner sizes:
// with the bottom panel shut, and with it open at its default share, as the
// audited window had it. With the panel open the declaration's pane is 571px
// tall at 1425 by 914; the form column beside the details is narrower, so
// its toolbar wraps onto a second line, and the stacked arrangement used to
// be judged with that wrapped toolbar: once beside, the details could not
// come back under the form although the form had room above them there.

const LANGUAGE = "es";

type Placement = "side" | "bottom";

const workspace = (target: Page) =>
  target.locator("section.declarations-workspace");
const toggle = (target: Page, pane: "details" | "placement") =>
  workspace(target).locator(`[data-pane-toggle=${pane}]`);

/** Opens the Modelo 100's form with the bottom panel `panelOpen`, and the
 * pane preferences as a first launch has them. */
async function openForm(
  target: Page,
  size: { width: number; height: number },
  panelOpen: boolean,
) {
  await target.addInitScript((open) => {
    localStorage.setItem(
      "cadrumo-shell-layout",
      JSON.stringify({ layout: { panelOpen: open, tab: "console" } }),
    );
    localStorage.removeItem("cadrumo-pane-preferences");
  }, panelOpen);
  await target.setViewportSize(size);
  await openFromDialog(target, "100", LANGUAGE, "renta-married");
  await tab(target, "desktop.modelo.view.form", LANGUAGE).click();
  await expect(workspace(target).locator("[data-modelo-form]")).toBeVisible();
  const details = toggle(target, "details");
  if ((await details.getAttribute("aria-pressed")) !== "true")
    await details.click();
  await expect(details).toHaveAttribute("aria-pressed", "true");
}

/** The details and the form against each other, as the audit's placement
 * probe reads them, with the bottom of the declaration's pane. */
const split = (target: Page) =>
  workspace(target).evaluate((section) => {
    const area = section.querySelector("[role=tabpanel][data-details]");
    const detailsId = section
      .querySelector("[data-pane-toggle=placement]")
      ?.getAttribute("aria-controls");
    const details = detailsId ? document.getElementById(detailsId) : null;
    const form = section.querySelector("[data-modelo-form]");
    const d = details?.getBoundingClientRect();
    const f = form?.getBoundingClientRect();
    return {
      placement: area?.getAttribute("data-details") ?? null,
      pressed: section
        .querySelector("[data-pane-toggle=placement]")
        ?.getAttribute("aria-pressed"),
      beside: !!d && !!f && f.right <= d.left + 1,
      under: !!d && !!f && f.bottom <= d.top + 1,
      bottom: Math.round(Math.max(d?.bottom ?? 0, f?.bottom ?? 0)),
      paneBottom: Math.round(section.getBoundingClientRect().bottom),
    };
  });

/** Presses the arrangement control until the details are `wanted`. */
async function arrange(target: Page, wanted: Placement) {
  if ((await split(target)).placement !== wanted)
    await toggle(target, "placement").click();
  await expect(
    workspace(target).locator("[role=tabpanel][data-details]"),
  ).toHaveAttribute("data-details", wanted);
}

for (const panelOpen of [false, true]) {
  test(`at 1425 by 914 with the bottom panel ${panelOpen ? "open" : "shut"}, the arrangement control puts the details beside the form and back under it, down to the pane's bottom`, async ({
    page: target,
  }) => {
    test.setTimeout(120_000);
    await openForm(target, { width: 1425, height: 914 }, panelOpen);
    await arrange(target, "side");
    const on = await split(target);
    expect(on.beside, "pressed on, the details are beside the form").toBe(true);
    expect(on.pressed).toBe("true");
    // Pressed off, the window must not hold the details beside: the form
    // has room above them under it.
    await expect(toggle(target, "placement")).not.toHaveAttribute(
      "aria-disabled",
      "true",
    );
    await toggle(target, "placement").click();
    await expect
      .poll(async () => (await split(target)).placement)
      .toBe("bottom");
    const off = await split(target);
    expect(off.pressed).toBe("false");
    expect(off.under, "pressed off, the details are under the form").toBe(true);
    // The form and the details fill the pane down to its bottom, which is the
    // window's with the panel shut.
    expect(off.bottom).toBeGreaterThanOrEqual(off.paneBottom - 1);
    if (!panelOpen) expect(off.bottom).toBeGreaterThanOrEqual(914 - 1);
    // And beside again, as the person asks.
    await toggle(target, "placement").click();
    await expect.poll(async () => (await split(target)).placement).toBe("side");
  });
}

/** The audit's wheel point over the form's scroller: its centre within the
 * window, or within what its scrolling ancestors show of it when `clipped`,
 * moved off any nested scroller; with whether the element there is inside
 * the scroller. */
const wheelPoint = (target: Page, clipped: boolean) =>
  workspace(target)
    .locator("[data-modelo-form]")
    .evaluate((el, clip) => {
      const b = (() => {
        const own = el.getBoundingClientRect();
        const r = {
          left: Math.max(0, own.left),
          top: Math.max(0, own.top),
          right: Math.min(innerWidth, own.right),
          bottom: Math.min(innerHeight, own.bottom),
        };
        if (clip)
          for (let up = el.parentElement; up; up = up.parentElement) {
            if (!/auto|scroll|hidden/.test(getComputedStyle(up).overflowY))
              continue;
            const a = up.getBoundingClientRect();
            r.left = Math.max(r.left, a.left);
            r.top = Math.max(r.top, a.top);
            r.right = Math.min(r.right, a.right);
            r.bottom = Math.min(r.bottom, a.bottom);
          }
        return r;
      })();
      const nested = (hit: Element) => {
        for (
          let node: Element | null = hit;
          node && node !== el;
          node = node.parentElement
        )
          if (
            /auto|scroll/.test(getComputedStyle(node).overflowY) &&
            node.scrollHeight > node.clientHeight + 1
          )
            return true;
        return false;
      };
      let x = Math.floor((b.left + b.right) / 2);
      let y = Math.floor((b.top + b.bottom) / 2);
      let hit = document.elementFromPoint(x, y);
      if (hit && el.contains(hit) && nested(hit))
        search: for (let i = 1; i < 8; i += 1)
          for (let j = 1; j < 8; j += 1) {
            const px = Math.floor(b.left + ((b.right - b.left) * i) / 8);
            const py = Math.floor(b.top + ((b.bottom - b.top) * j) / 8);
            const at = document.elementFromPoint(px, py);
            if (at && el.contains(at) && !nested(at)) {
              [x, y, hit] = [px, py, at];
              break search;
            }
          }
      return {
        x,
        y,
        pointInside: !!hit && el.contains(hit),
        hit: hit
          ? `${hit.tagName.toLowerCase()}.${String(hit.className).split(/\s+/).slice(0, 3).join(".")}`
          : null,
        overflows: el.scrollHeight > el.clientHeight + 1,
        before: el.scrollTop,
      };
    }, clipped);

const SMALL = [
  { width: 1008, height: 631 },
  { width: 884, height: 591 },
];

for (const size of SMALL)
  for (const panelOpen of [false, true]) {
    test(`at ${size.width} by ${size.height} with the bottom panel ${panelOpen ? "open" : "shut"}, the wheel over the form's scroller scrolls it`, async ({
      page: target,
    }) => {
      test.setTimeout(120_000);
      await openForm(target, size, panelOpen);
      // With the panel open the declaration's pane is too short for the
      // header, the view bar and the form's least room, so the workspace
      // scrolls as a whole and shows the top of the form; the wheel goes
      // where the form is drawn.
      const point = await wheelPoint(target, panelOpen);
      expect(point.overflows, "the form has more than its room").toBe(true);
      expect(
        point.pointInside,
        `the wheel point ${point.x},${point.y} lies over ${point.hit}, not the form`,
      ).toBe(true);
      await target.mouse.move(point.x, point.y);
      await target.mouse.wheel(0, 300);
      await expect
        .poll(() =>
          workspace(target)
            .locator("[data-modelo-form]")
            .evaluate((el) => el.scrollTop),
        )
        .toBeGreaterThan(point.before);
    });
  }
