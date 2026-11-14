import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The packaged window's audit of the Modelo workspace, measured the same way
// in the scenario host: the same geometry and the same names, read from the
// page, at the window sizes the audit found short. Each test fails on the
// defect its UX id names.

const SECTION = "section.declarations-workspace";
const workspace = (target: Page) => target.locator(SECTION);

async function openDeclaration(target: Page, extra = "") {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off${extra}`,
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

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() =>
    localStorage.removeItem("cadrumo-shell-layout"),
  );
});

const chooseView = (target: Page, key: string) =>
  workspace(target)
    .getByRole("tablist", { name: label("desktop.modelo.views.label") })
    .getByRole("tab", { name: label(key) })
    .click();

/** Collapses the prior-values offer when it is open. */
async function hidePriorValues(target: Page) {
  const hide = workspace(target)
    .locator("section[data-prior-values]")
    .getByRole("button", { name: label("desktop.modelo.statements.hide") });
  if ((await hide.count()) > 0) await hide.click();
}

const formGeometry = (target: Page) =>
  workspace(target).evaluate((section) => {
    const form = section.querySelector("[data-modelo-form]");
    const box = section.getBoundingClientRect();
    return {
      pane: Math.round(box.height),
      client: form?.clientHeight ?? 0,
      scroll: form?.scrollHeight ?? 0,
    };
  });

test("UX-03 the hidden prior-values offer stays hidden after a view change", async ({
  page: target,
}) => {
  await openDeclaration(target);
  const listed = workspace(target).locator("section[data-prior-values] li");
  await expect(listed.first()).toBeVisible();
  await hidePriorValues(target);
  await expect(listed, "the offer is collapsed after hiding it").toHaveCount(0);
  await chooseView(target, "workspace.modelo.step.review");
  await chooseView(target, "desktop.modelo.view.form");
  await expect(
    listed,
    "the offer the person hid is open again after switching views",
  ).toHaveCount(0);
});

for (const [width, height] of [
  [1280, 800] as const,
  [1024, 640] as const,
  [900, 600] as const,
]) {
  test(`UX-04 form keeps room to work at ${width}x${height}`, async ({
    page: target,
  }) => {
    await target.setViewportSize({ width, height });
    await openDeclaration(target);
    await hidePriorValues(target);
    const g = await formGeometry(target);
    expect(
      g.client,
      `form scroller is ${g.client}px high (scrollHeight ${g.scroll}) in a ${g.pane}px pane at ${width}x${height}`,
    ).toBeGreaterThanOrEqual(150);
  });
}

const visibleSeparators = (target: Page) =>
  workspace(target).evaluate(
    (section) =>
      [...section.querySelectorAll('[role="separator"]')].filter(
        (element) => element.getClientRects().length > 0,
      ).length,
  );

test("UX-05 the details and side panels beside the form can be resized", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1441, height: 923 });
  await openDeclaration(target);
  const handles = await visibleSeparators(target);
  expect(
    handles,
    `resize handles (role=separator) in the workspace: ${handles}`,
  ).toBeGreaterThanOrEqual(1);
});

// On a small window the panes may start hidden; each one shown from its
// control is resizable.
for (const [width, height] of [[1024, 640] as const, [900, 600] as const]) {
  test(`UX-05 a pane shown beside the form at ${width}x${height} can be resized`, async ({
    page: target,
  }) => {
    await target.setViewportSize({ width, height });
    await openDeclaration(target);
    for (const pane of ["side", "details"]) {
      const control = workspace(target).locator(
        `[data-pane-toggle=${pane}][aria-pressed=false]`,
      );
      if ((await control.count()) > 0) await control.click();
    }
    const handles = await visibleSeparators(target);
    expect(
      handles,
      `resize handles (role=separator) in the workspace: ${handles}`,
    ).toBeGreaterThanOrEqual(2);
  });
}

for (const [width, height] of [[1024, 640] as const, [900, 600] as const]) {
  test(`UX-06 the side panel (to do and outline) stays reachable at ${width}x${height}`, async ({
    page: target,
  }) => {
    await target.setViewportSize({ width, height });
    await openDeclaration(target);
    const reachable = await workspace(target).evaluate((section, name) => {
      const side = section.querySelector(
        `aside[aria-label=${JSON.stringify(name)}]`,
      );
      const shown = !!side && side.getClientRects().length > 0;
      const opener = [...section.querySelectorAll("button")].some(
        (button) =>
          button.getClientRects().length > 0 &&
          (button.getAttribute("aria-label") ?? "").includes(name),
      );
      return {
        shown,
        opener,
        display: side ? getComputedStyle(side).display : null,
      };
    }, label("desktop.modelo.side.label"));
    expect(
      reachable.shown || reachable.opener,
      `the side panel is display:${reachable.display} at ${width}x${height} and no control opens it`,
    ).toBe(true);
  });
}
