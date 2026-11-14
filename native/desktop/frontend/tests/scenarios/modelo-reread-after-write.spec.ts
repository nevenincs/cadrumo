import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// A write the window sent and saw settle is followed by one read of the
// declaration. A read that a newer one overtakes is answered by the newer
// read; only a read that really failed says so, and leaves the manual
// control that reads again.

type RereadTest = {
  afterVerify: boolean;
  formCalls: number;
  verifies: number;
  holdFirst: boolean;
  release: (() => void) | null;
  fail: boolean;
};
declare global {
  interface Window {
    __rereadTest?: RereadTest;
  }
}

const workspace = (target: Page) => target.locator(".declarations-workspace");

async function openCheckedDeclaration(
  target: Page,
  before: (target: Page) => Promise<void>,
) {
  await target.goto(
    "/scenarios.html?scenario=ledger&latency=0&bar=off&modelo=checked",
  );
  await target.locator("[data-rail=declarations]").click();
  await target.waitForFunction(() => !!window.__fixtureModelo);
  await before(target);
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

/** The checked quarter offers Verificar as its next action, and the
 * application settles a verification. Reads after it are counted, and the
 * first can be held or failed. */
async function serveVerification(target: Page) {
  await target.evaluate(() => {
    const state: RereadTest = (window.__rereadTest = {
      afterVerify: false,
      formCalls: 0,
      verifies: 0,
      holdFirst: false,
      release: null,
      fail: false,
    });
    const port = window.__fixtureModelo!;
    const form = port.form;
    const submit = port.submit;
    port.form = async (...args) => {
      const served = await form(...args);
      const verifying = {
        ...served,
        next_step: { ...served.next_step!, action: "verify" as const },
      };
      if (!state.afterVerify) return verifying;
      const call = ++state.formCalls;
      if (state.fail) throw { code: "unavailable" };
      if (state.holdFirst && call === 1)
        await new Promise<void>((resolve) => {
          state.release = resolve;
        });
      return verifying;
    };
    port.submit = async (...args) => {
      if (args[0] !== "modelo.work.verify") return submit(...args);
      state.verifies++;
      state.afterVerify = true;
      return {
        kind: "settled",
        operation_id: "verify-1",
        result: {},
      } as Awaited<ReturnType<typeof submit>>;
    };
  });
}

const verify = (target: Page) =>
  workspace(target).getByRole("button", {
    name: label("workspace.modelo.next_button.verify"),
  });
const failedWords = (target: Page) =>
  workspace(target).getByText(label("workspace.modelo.outcome.failed"));
const readAgain = (target: Page) =>
  workspace(target).getByRole("button", {
    name: label("workspace.modelo.read_again"),
  });

test("the write's own read is not offered to be read again while it runs and releases the hold", async ({
  page: target,
}) => {
  await openCheckedDeclaration(target, serveVerification);
  await target.evaluate(() => {
    window.__rereadTest!.holdFirst = true;
  });
  await verify(target).click();
  // The write's own read is under way: the notice does not ask the person to
  // read again, and the hold is gone once that read answers.
  await expect
    .poll(() => target.evaluate(() => !!window.__rereadTest!.release))
    .toBe(true);
  await expect(readAgain(target)).toHaveCount(0);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  await target.evaluate(() => window.__rereadTest!.release!());
  await expect(failedWords(target)).toHaveCount(0);
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
  const state = await target.evaluate(() => window.__rereadTest!);
  expect(state.verifies).toBe(1);
  expect(state.formCalls).toBe(1);
});

test("a read that really failed says so and keeps the control that reads again", async ({
  page: target,
}) => {
  await openCheckedDeclaration(target, serveVerification);
  await target.evaluate(() => {
    window.__rereadTest!.fail = true;
  });
  await verify(target).click();
  await expect(failedWords(target)).toBeVisible();
  await expect(readAgain(target)).toBeVisible();
  await target.evaluate(() => {
    window.__rereadTest!.fail = false;
  });
  await readAgain(target).click();
  await expect(target.locator(".modelo-write-hold")).toHaveCount(0);
});
