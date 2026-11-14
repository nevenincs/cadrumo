import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The details beside or under a Modelo 100's form as the packaged window
// measures them: at the native window's inner sizes, with the rail shown and
// hidden, in either arrangement, every pane lies inside the window and the
// details' line takes the keyboard. The Modelo 100's header, view bar and
// prior-values band make the chrome above the form tall: at 1011 by 632 the
// stacked details used to start at 597px and end at 692px, under the
// window's edge. Coming back from another page draws the form at once, in
// the arrangement chosen, rather than an empty pane while its read arrives.

const SIZES = [
  { width: 1427, height: 915 },
  { width: 1267, height: 793 },
  { width: 1011, height: 632 },
  { width: 887, height: 592 },
];
// UX-04: the form keeps room to work.
const FORM_ROOM = 150;

type Placement = "side" | "bottom";

const workspace = (target: Page) => target.locator(".declarations-workspace");
const area = (target: Page) =>
  workspace(target).locator("[role=tabpanel][data-details]");
const toggle = (target: Page, pane: "side" | "details" | "placement") =>
  workspace(target).locator(`[data-pane-toggle=${pane}]`);
const line = (target: Page) =>
  workspace(target).getByRole("separator", {
    name: label("desktop.modelo.details.resize"),
  });

/** Opens the filer's 2025 Modelo 100 from the new-declaration dialog, its
 * reads answered after `latency` milliseconds. */
async function openRenta(target: Page, latency = 0) {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=${latency}&bar=off&modelo=renta`,
  );
  await target.locator("[data-rail=declarations]").click();
  const read = await target.evaluate(async () =>
    window.__fixtureModelo!.declarations("en"),
  );
  const existing = read.creation_targets.find(
    (entry) => entry.modelo === "100" && entry.existing,
  )!;
  await target
    .getByRole("button", { name: label("workspace.declarations.list.key.new") })
    .first()
    .click();
  const dialog = target.getByRole("dialog");
  await dialog.getByText(existing.modelo_title, { exact: true }).click();
  await dialog.getByRole("radio", { name: existing.period_words! }).click();
  await dialog
    .getByRole("button", {
      name: label("workspace.declarations.list.new.open_it"),
    })
    .click();
  await expect(area(target)).toBeVisible({ timeout: 30_000 });
}

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    localStorage.removeItem("cadrumo-shell-layout");
    localStorage.removeItem("cadrumo-pane-preferences");
  });
});

async function press(target: Page, pane: "side" | "details", on: boolean) {
  const control = toggle(target, pane);
  if ((await control.getAttribute("aria-pressed")) !== String(on))
    await control.click();
  await expect(control).toHaveAttribute("aria-pressed", String(on));
}

/** Asks for `wanted` by the arrangement control; where the window is too
 * short to stack, the control is held pressed and the details stay beside.
 * Answers the arrangement drawn. */
async function arrange(target: Page, wanted: Placement): Promise<Placement> {
  const control = toggle(target, "placement");
  const held = (await control.getAttribute("aria-disabled")) === "true";
  if (held) {
    // The control says why it does nothing, to the eye and to a reader.
    await expect(control).toHaveAccessibleDescription(
      label("desktop.modelo.details.under_held"),
    );
    await expect(control).toHaveAccessibleName(
      label("desktop.modelo.details.beside"),
    );
    await expect(control).toHaveAttribute("aria-pressed", "true");
    await expect(area(target)).toHaveAttribute("data-details", "side");
    // Pressing a held control changes nothing.
    await control.focus();
    await target.keyboard.press("Enter");
    await expect(area(target)).toHaveAttribute("data-details", "side");
    return "side";
  }
  // Where the window can stack the details, the control gives no reason.
  await expect(control).not.toHaveAttribute("aria-disabled", "true");
  await expect(control).toHaveAccessibleDescription("");
  if ((await area(target).getAttribute("data-details")) !== wanted)
    await control.click();
  await expect(area(target)).toHaveAttribute("data-details", wanted);
  return wanted;
}

/** The panes' boxes against the window, and the form's room. */
const geometry = (target: Page) =>
  workspace(target).evaluate((section) => {
    const inside = (element: Element | null | undefined) => {
      if (!element) return false;
      const box = element.getBoundingClientRect();
      return (
        box.left >= 0 &&
        box.top >= 0 &&
        Math.round(box.right) <= innerWidth &&
        Math.round(box.bottom) <= innerHeight
      );
    };
    const detailsName = section
      .querySelector("[data-pane-toggle=placement]")
      ?.getAttribute("aria-controls");
    const details = detailsName ? document.getElementById(detailsName) : null;
    const form = section.querySelector<HTMLElement>("[data-modelo-form]");
    const box = details?.getBoundingClientRect();
    return {
      detailsInside: inside(details),
      formInside: inside(form),
      detailsBottom: Math.round(box?.bottom ?? 0),
      extent: Math.round(box?.height ?? 0),
      width: Math.round(box?.width ?? 0),
      formRoom: form?.clientHeight ?? 0,
    };
  });

for (const size of SIZES) {
  for (const railOn of [true, false]) {
    for (const wanted of ["side", "bottom"] as const) {
      test(`UX-16 at ${size.width} by ${size.height} with the rail ${railOn ? "shown" : "hidden"}, asking for the details ${wanted === "side" ? "beside" : "under"} the form, every pane lies inside the window`, async ({
        page: target,
      }) => {
        await target.setViewportSize(size);
        await openRenta(target);
        await press(target, "side", railOn);
        await press(target, "details", true);
        const drawn = await arrange(target, wanted);
        const along = (g: Awaited<ReturnType<typeof geometry>>) =>
          drawn === "side" ? g.width : g.extent;
        await line(target).focus();
        await expect(line(target)).toBeFocused();
        await target.keyboard.press("Home");
        await expect(line(target)).toHaveAttribute("aria-valuenow", "0");
        const least = await geometry(target);
        await target.keyboard.press("End");
        await expect(line(target)).toHaveAttribute("aria-valuenow", "100");
        const most = await geometry(target);
        for (const [end, g] of [
          ["least", least],
          ["most", most],
        ] as const) {
          expect(
            g.detailsInside && g.formInside,
            `at the details' ${end} (bottom ${g.detailsBottom}) a pane lies outside the window`,
          ).toBe(true);
          expect(g.formRoom).toBeGreaterThanOrEqual(FORM_ROOM);
        }
        expect(along(most), "the line moves").toBeGreaterThan(along(least));
        expect(
          await workspace(target).evaluate((element) => element.scrollTop),
        ).toBe(0);
      });
    }
  }
}

test("UX-16 coming back from the Ledger draws the form at once with the arrangement chosen, and its line takes the keyboard", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 1427, height: 915 });
  // Reads answer after three seconds, as a large Modelo 100 read does.
  await openRenta(target, 3000);
  await press(target, "details", true);
  await arrange(target, "side");
  await target.locator("[data-rail=ledger]").click();
  await expect(target.locator("section.ledger-page")).toBeVisible();
  await target.locator("[data-rail=declarations]").click();
  // Well before the form's read can answer again.
  await expect(area(target)).toHaveAttribute("data-details", "side", {
    timeout: 1000,
  });
  await expect(toggle(target, "placement")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(
    workspace(target)
      .getByRole("tablist", { name: label("desktop.modelo.views.label") })
      .getByRole("tab", { name: label("desktop.modelo.view.form") }),
  ).toHaveAttribute("aria-selected", "true");
  await line(target).focus();
  await expect(line(target)).toBeFocused();
});

for (const size of SIZES.slice(2)) {
  for (const railOn of [true, false]) {
    test(`UX-16 at ${size.width} by ${size.height} with the rail ${railOn ? "shown" : "hidden"}, a window too short to stack holds the arrangement control and says why`, async ({
      page: target,
    }) => {
      await target.setViewportSize(size);
      await openRenta(target);
      await press(target, "side", railOn);
      await press(target, "details", true);
      const control = toggle(target, "placement");
      await target.mouse.move(0, 0);
      await expect(control).toHaveAttribute("aria-disabled", "true");
      await expect(control).toHaveAccessibleDescription(
        label("desktop.modelo.details.under_held"),
      );
      // Its tooltip says it too, on the pointer.
      await control.hover();
      await expect(
        target.getByRole("tooltip").filter({
          hasText: label("desktop.modelo.details.under_held"),
        }),
      ).toBeVisible();
    });
  }
}
