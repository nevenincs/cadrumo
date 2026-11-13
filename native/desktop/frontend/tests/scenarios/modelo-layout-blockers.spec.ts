import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// What is said above a declaration's form can run longer than the window:
// a Modelo 100 with fourteen earlier-return amounts offers a list 2122px
// tall. The form keeps room to work beside it, and the workspace's header,
// view tabs and next action stay at the top of the pane however the form is
// scrolled or focused. The served offer is stood in for by the same height
// added to the band above the form, which every declaration draws.

const OFFER_HEIGHT = 2122;
const workspace = (target: Page) => target.locator(".declarations-workspace");

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

for (const size of [
  { width: 1280, height: 800 },
  { width: 1024, height: 640 },
  { width: 900, height: 600 },
]) {
  test(`at ${size.width} by ${size.height} a tall offer over the form leaves the form room and the header in view`, async ({
    page: target,
  }) => {
    await target.setViewportSize(size);
    await openDeclaration(target);
    await workspace(target)
      .locator("[data-year-projection]")
      .evaluate((element, height) => {
        const offer = document.createElement("span");
        offer.style.display = "block";
        offer.style.height = `${height}px`;
        element.append(offer);
      }, OFFER_HEIGHT);
    const form = workspace(target).locator("[data-modelo-form]");
    // Focus and a jump into the form are what scrolled the pane before.
    await form.evaluate((element) => {
      element.focus();
      element.scrollIntoView({ block: "end" });
    });
    // UX-01: the form keeps room to work.
    expect(
      await form.evaluate((element) => element.clientHeight),
    ).toBeGreaterThanOrEqual(100);
    // UX-02: the pane is not scrolled, and the header, the view tabs and
    // the next action are on screen.
    expect(
      await workspace(target).evaluate((element) => element.scrollTop),
    ).toBe(0);
    await expect(workspace(target).locator("header").first()).toBeInViewport();
    await expect(
      workspace(target).getByRole("tablist", {
        name: label("desktop.modelo.views.label"),
      }),
    ).toBeInViewport();
    await expect(
      workspace(target).getByRole("button", {
        name: label("workspace.modelo.next_button.fill"),
      }),
    ).toBeInViewport();
  });
}
