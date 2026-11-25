import { expect, type Locator, type Page, test } from "@playwright/test";
import { label } from "../support/strings";
import { form, openDeclaration } from "../support/scenarioModelo";
import {
  applyButton,
  calls,
  review,
  stage,
  TYPED_06,
} from "../support/scenarioModeloWrites";

// The window's own read of its own settled write: until it answers, the
// header offers no next step (the one it served belongs to the declaration
// before the write) and says that it is reading; when the read settles it
// offers the step the read served.

const ACTIONS = [
  "fill",
  "confirm",
  "resolve",
  "export",
  "export_again",
  "record_after_file",
  "calculate",
  "recalculate",
  "verify",
  "apply",
  "add_receipt",
];

const header = (target: Page) =>
  target.locator(".declarations-workspace").locator("header").first();

const offered = (target: Page): Locator =>
  header(target).getByRole("button", {
    name: new RegExp(
      `^(${ACTIONS.map((action) =>
        label(`workspace.modelo.next_button.${action}`).replace(
          /[.*+?^${}()|[\]\\]/g,
          "\\$&",
        ),
      ).join("|")})$`,
    ),
  });

const holdRead = (target: Page) =>
  target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const read = port.form;
    const gate = window as unknown as { __releaseRead?: () => void };
    port.form = async (...args) => {
      await new Promise<void>((release) => {
        gate.__releaseRead = release;
      });
      if (window.__headerReadFails)
        throw Object.assign(new Error("fixture read failure"), {
          code: "unavailable",
        });
      return read(...args);
    };
  });

const released = (target: Page) =>
  target.evaluate(
    () =>
      typeof (window as unknown as { __releaseRead?: () => void })
        .__releaseRead,
  );

async function applyHeldRead(target: Page, readFails = false) {
  await openDeclaration(target, "130", { shape: "edit" });
  await target.evaluate((fails) => {
    window.__headerReadFails = fails;
  }, readFails);
  await stage(target, "06", TYPED_06);
  await expect(offered(target).first()).toBeVisible();
  const dialog = await review(target);
  await holdRead(target);
  await applyButton(dialog).click();
  await expect(
    dialog.getByText(label("workspace.modelo.operation.done")),
  ).toBeVisible();
  await expect.poll(() => released(target)).toBe("function");
  await dialog
    .getByRole("button", { name: label("workspace.modelo.key.close") })
    .last()
    .click();
  await expect(dialog).toBeHidden();
}

declare global {
  interface Window {
    __headerReadFails?: boolean;
  }
}

test("while the window reads its own settled write the header offers no stale next step, then the served one", async ({
  page: target,
}) => {
  const served = form("130-1T-applied").next_step?.action;
  if (!served) throw new Error("the applied 130 serves no next step");
  await applyHeldRead(target);
  expect(await calls(target, "modelo edit modelo.edit.apply")).toHaveLength(1);
  // The window is reading: no step is offered, the header says it works.
  await expect(offered(target)).toHaveCount(0);
  await expect(
    header(target).getByText(label("desktop.navigation.busy")),
  ).toBeVisible();
  await target.evaluate(() =>
    (window as unknown as { __releaseRead: () => void }).__releaseRead(),
  );
  await expect(
    header(target).getByRole("button", {
      name: label(`workspace.modelo.next_button.${served}`),
    }),
  ).toBeVisible();
  await expect(
    header(target).getByText(label("desktop.navigation.busy")),
  ).toHaveCount(0);
});

test("a failed read of the window's own write restores the manual control", async ({
  page: target,
}) => {
  await applyHeldRead(target, true);
  await expect(offered(target)).toHaveCount(0);
  await target.evaluate(() =>
    (window as unknown as { __releaseRead: () => void }).__releaseRead(),
  );
  await expect(
    header(target).getByText(label("desktop.navigation.busy")),
  ).toHaveCount(0);
  await expect(target.locator(".modelo-write-hold").first()).toBeVisible();
});
