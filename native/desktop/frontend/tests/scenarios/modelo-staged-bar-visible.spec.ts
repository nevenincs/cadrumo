import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";
import { seedLayout } from "../support/layout";
import { openDeclaration } from "../support/scenarioModelo";
import { stage, TYPED_06 } from "../support/scenarioModeloWrites";

// The staged-edit bar under a declaration's form, with its count and its
// apply and discard actions, stays wholly in the window at every supported
// size, whatever panes are shown and wherever the details go: the person
// never scrolls to reach the action that applies what they typed. Where the
// workspace is too short for everything, it still scrolls as a whole, and
// the bar stays in view at either end of that scroll.

const SIZES = [
  { width: 1441, height: 923 },
  { width: 1280, height: 800 },
  { width: 1024, height: 640 },
  { width: 900, height: 600 },
  // The native window's inner sizes at the same four window sizes.
  { width: 1427, height: 915 },
  { width: 1267, height: 793 },
  { width: 1011, height: 632 },
  { width: 887, height: 592 },
  // The smallest window the shell supports.
  { width: 600, height: 700 },
];

type Placement = "side" | "bottom";

const workspace = (target: Page) => target.locator(".declarations-workspace");
const area = (target: Page) =>
  workspace(target).locator("[role=tabpanel][data-details]");
const toggle = (target: Page, pane: "side" | "details" | "placement") =>
  workspace(target).locator(`[data-pane-toggle=${pane}]`);

async function showPane(target: Page, pane: "side" | "details", on: boolean) {
  const control = toggle(target, pane);
  if ((await control.getAttribute("aria-pressed")) !== String(on))
    await control.click();
  await expect(control).toHaveAttribute("aria-pressed", String(on));
}

/** Asks for the details in `placement`; a held control keeps them beside.
 * Answers the arrangement drawn. */
async function place(target: Page, placement: Placement): Promise<Placement> {
  const control = toggle(target, "placement");
  if ((await control.getAttribute("aria-disabled")) === "true") return "side";
  if (
    (await control.getAttribute("aria-pressed")) !==
    String(placement === "side")
  )
    await control.click();
  await expect(area(target)).toHaveAttribute("data-details", placement);
  return placement;
}

/** Scrolls the workspace, the one scroller holding the form's area, to its
 * start or its end without moving anything else. */
const scrollWorkspace = (target: Page, to: "start" | "end") =>
  area(target).evaluate((element, end) => {
    let scroller = element.parentElement;
    while (scroller && getComputedStyle(scroller).overflowY !== "auto")
      scroller = scroller.parentElement;
    if (scroller) scroller.scrollTop = end ? scroller.scrollHeight : 0;
  }, to === "end");

async function expectBarInView(target: Page, state: string) {
  const bar = area(target);
  for (const key of [
    "workspace.modelo.next_button.apply",
    "workspace.modelo.review.discard",
  ])
    for (const to of ["start", "end"] as const) {
      await scrollWorkspace(target, to);
      await expect(
        bar.getByRole("button", { name: label(key), exact: true }),
        `${label(key)} is wholly in the window ${state}, the workspace scrolled to its ${to}`,
      ).toBeInViewport({ ratio: 1 });
    }
  await expect(
    bar.getByText(label("workspace.modelo.next.apply", { count: 1 })),
  ).toBeInViewport({ ratio: 1 });
}

for (const size of SIZES)
  test(`UX-27 at ${size.width} by ${size.height} the staged-edit bar stays in view with every pane arrangement`, async ({
    page: target,
  }) => {
    await seedLayout(target, {
      layout: {
        agentShown: false,
        tuiShown: false,
        docsShown: true,
        page: "docs",
      },
    });
    await target.setViewportSize(size);
    await openDeclaration(target, "130", { shape: "edit" });
    await stage(target, "06", TYPED_06);
    await expectBarInView(target, "as the declaration opens");
    for (const railOn of [true, false]) {
      await showPane(target, "side", railOn);
      await showPane(target, "details", false);
      await expectBarInView(
        target,
        `with the rail ${railOn ? "shown" : "hidden"} and the details hidden`,
      );
      await showPane(target, "details", true);
      for (const wanted of ["side", "bottom"] as const) {
        const drawn = await place(target, wanted);
        await expectBarInView(
          target,
          `with the rail ${railOn ? "shown" : "hidden"} and the details ${drawn === "side" ? "beside" : "under"} the form`,
        );
      }
    }
  });
