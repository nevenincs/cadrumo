import { expect, type Page, test } from "@playwright/test";
import { label } from "./support/strings";
import {
  docsFrame,
  revealTui,
  signInHost,
  signInState,
} from "./support/desktopShell";

test.beforeEach(async ({ page: target }) => {
  // Start each test from the default layout, once: a reload inside a test must
  // still see what that test stored.
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("public sign-in signals update the gate without focus or another status read", async ({
  page,
}) => {
  await signInHost(page);
  await expect(page.locator(".sign-in")).toBeVisible();
  const before = (await signInState(page)).statusReads;
  let revision = 0;
  const emit = async (
    state: string,
    runtimeAvailable: boolean,
    active_profile: string,
  ) => {
    await page.evaluate(
      ({ state, runtimeAvailable, active_profile, revision }) => {
        const host = (
          window as unknown as {
            __signInTest: {
              signInUpdate: (signal: unknown) => void;
            };
          }
        ).__signInTest;
        host.signInUpdate({
          kind: "sign-in-state",
          revision,
          status: {
            supported: true,
            state,
            runtimeAvailable,
            active_profile,
            refusal: null,
          },
        });
      },
      { state, runtimeAvailable, active_profile, revision: ++revision },
    );
  };
  await emit("present", true, "Other profile");
  await expect(page.locator(".sign-in")).toHaveCount(0);
  await emit("absent", true, "Test profile");
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toBeVisible();
  await emit("unknown", false, "Test profile");
  await expect(
    page.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
  expect((await signInState(page)).statusReads).toBe(before);
});

test("startup focus events share one pending sign-in status read", async ({
  page: target,
}) => {
  await signInHost(target, true, true);
  await expect
    .poll(async () => (await signInState(target)).statusReads)
    .toBe(1);
  await target.evaluate(async () => {
    for (let index = 0; index < 5; index++)
      window.dispatchEvent(new Event("focus"));
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => resolve()),
    );
  });
  expect((await signInState(target)).statusReads).toBe(1);
  await target.evaluate(() =>
    (
      window as unknown as { __signInTest: { releaseStatus: () => void } }
    ).__signInTest.releaseStatus(),
  );
  await expect(
    target.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toBeVisible();
  expect((await signInState(target)).submissions).toBe(0);
  await expect(target.locator(".sign-in")).not.toContainText("queue_full");
});

test("a failed status read releases its slot for the next focus refresh", async ({
  page: target,
}) => {
  await signInHost(target);
  await expect(
    target.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toBeVisible();
  await target.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { statusError: "queue_full" },
    );
    window.dispatchEvent(new Event("focus"));
  });
  await expect(target.locator(".sign-in")).toContainText(
    label("desktop.signin.refused.other"),
  );
  await expect(target.locator(".sign-in")).not.toContainText("queue_full");
  await target.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { statusError: "" },
    );
    window.dispatchEvent(new Event("focus"));
  });
  await expect(target.locator(".sign-in")).not.toContainText("queue_full");
  await expect(target.locator(".sign-in")).not.toContainText(
    label("desktop.signin.refused.other"),
  );
  expect((await signInState(target)).statusReads).toBe(3);
  expect((await signInState(target)).submissions).toBe(0);
});

test("explicit sign-in dispatches beside a pending status read and submits once", async ({
  page: target,
}) => {
  await signInHost(target);
  const password = target.getByLabel(label("desktop.signin.password"), {
    exact: true,
  });
  await password.fill("secret á漢");
  await target.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { deferStatus: true },
    );
    window.dispatchEvent(new Event("focus"));
  });
  await expect
    .poll(async () => (await signInState(target)).statusReads)
    .toBe(2);
  await target
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  // Pending: the field holds, without leaving the tab order.
  await expect(password).toHaveAttribute("readonly", "");
  await expect(target.locator(".sign-in").locator(":focus")).toHaveCount(1);
  expect((await signInState(target)).submissions).toBe(1);
  await target.evaluate(() =>
    (
      window as unknown as { __signInTest: { releaseStatus: () => void } }
    ).__signInTest.releaseStatus(),
  );
  await expect(
    target.getByText(label("desktop.signin.refused.invalid")),
  ).toBeVisible();
  expect((await signInState(target)).submissions).toBe(1);
  await expect(target.locator(".sign-in")).not.toContainText(
    label("desktop.signin.refused.other"),
  );
  expect((await signInState(target)).statusReads).toBe(3);
});

test("sign-in gates TUI, sends a raw secret once, clears it and refreshes refusal status", async ({
  page: target,
}) => {
  await signInHost(target);
  const password = target.getByLabel(label("desktop.signin.password"), {
    exact: true,
  });
  await expect(password).toBeVisible();
  expect((await signInState(target)).tuiStarts).toBe(0);
  await password.fill("secret á漢");
  await target
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(
    target.getByText(label("desktop.signin.refused.invalid")),
  ).toBeVisible();
  await expect(password).toHaveValue("");
  await expect
    .poll(async () => (await signInState(target)).secretCleared)
    .toBe(true);
  expect(await signInState(target)).toMatchObject({
    submissions: 1,
    rawPassword: true,
    tokenHeader: true,
    statusReads: 2,
    tuiStarts: 0,
  });
  expect(
    await docsFrame(target).evaluate(() => document.body.textContent),
  ).not.toContain("secret á漢");
  expect(
    await target.evaluate(() => JSON.stringify(localStorage)),
  ).not.toContain("secret á漢");
});

const markSignedIn = (target: Page, extra: object = {}) =>
  target.evaluate((fields) => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { presence: "present", ...fields },
    );
    window.dispatchEvent(new Event("focus"));
  }, extra);

test("the agent is there only while a profile is signed in", async ({
  page: target,
}) => {
  await signInHost(target);
  const rail = target.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  const held = rail.getByRole("button", {
    name: `${label("desktop.rail.agent")}, ${label("desktop.agent.sign_in_first")}`,
    exact: true,
  });
  // Signed out, there is no agent: its column is not shown, and its button
  // stays in the rail, held, saying why. Pressing it does nothing. The
  // sign-in dialog is dismissed to reach the rail behind it.
  await expect(target.locator(".pane-agent")).toBeHidden();
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await expect(held).toHaveAttribute("aria-disabled", "true");
  await held.click({ force: true });
  await expect(target.locator(".pane-agent")).toBeHidden();
  await markSignedIn(target);
  await expect(target.locator(".pane-agent")).toBeVisible();
  const available = rail.getByRole("button", {
    name: label("desktop.rail.agent"),
    exact: true,
  });
  await expect(available).not.toHaveAttribute("aria-disabled", "true");
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await target
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect.poll(async () => (await signInState(target)).signOuts).toBe(1);
  await expect(target.locator(".pane-agent")).toBeHidden();
  await expect(held).toHaveAttribute("aria-disabled", "true");
});

// What a sign-out leaves standing is what the product reports of it. The
// saved setting is on in every case; only an issued key that can still admit
// is said, and what the product does not answer is not said.
for (const remains of [false, null, true] as const)
  test(`signing out with agent access remaining ${String(remains)} ${remains ? "says" : "says nothing of"} issued keys`, async ({
    page: target,
  }) => {
    await signInHost(target);
    await markSignedIn(target, { automationAccessRemains: remains });
    await expect(target.locator(".pane-agent")).toBeVisible();
    await target
      .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
      .click();
    await target
      .getByRole("menuitem", {
        name: label("desktop.account.sign_out"),
        exact: true,
      })
      .click();
    await expect.poll(async () => (await signInState(target)).signOuts).toBe(1);
    // The menu stays open on the sign-out and offers sign-in.
    const menu = target.locator(".account-menu");
    await expect(
      menu.getByRole("menuitem", { name: label("desktop.signin.submit") }),
    ).toBeVisible();
    await expect(
      menu.getByText(label("desktop.account.remaining_access")),
    ).toHaveCount(remains ? 1 : 0);
  });

for (const pending of ["status", "list"] as const)
  test(`persisted sign-in displays immediately beside a held ${pending} read without another status call`, async ({
    page: target,
  }) => {
    await signInHost(target, true, false, pending === "list");
    const password = target.getByLabel(label("desktop.signin.password"), {
      exact: true,
    });
    await expect(password).toBeVisible();
    await target.evaluate((pending) => {
      const state = (
        window as unknown as { __signInTest: Record<string, unknown> }
      ).__signInTest;
      state.submitCode = "";
      if (pending === "status") {
        state.deferStatus = true;
        state.runtimeAvailable = false;
        window.dispatchEvent(new Event("focus"));
      }
    }, pending);
    await expect
      .poll(
        async () =>
          (await signInState(target))[
            pending === "status" ? "activeStatusReads" : "activeListReads"
          ],
      )
      .toBe(1);
    const reads = (await signInState(target)).statusReads;
    await target.evaluate(() => {
      (
        window as unknown as { __signInTest: { runtimeAvailable: boolean } }
      ).__signInTest.runtimeAvailable = true;
    });
    await password.fill("secret á漢");
    await target
      .getByRole("button", {
        name: label("desktop.signin.submit"),
        exact: true,
      })
      .click();
    await expect(password).toHaveCount(0);
    expect((await signInState(target)).tuiStarts).toBe(0);
    await revealTui(target);
    await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
    await expect
      .poll(async () => (await signInState(target)).secretCleared)
      .toBe(true);
    expect((await signInState(target)).submissions).toBe(1);
    expect((await signInState(target)).statusReads).toBe(reads);
    expect(
      (await signInState(target))[
        pending === "status" ? "activeStatusReads" : "activeListReads"
      ],
    ).toBe(1);
    await target.evaluate(async (pending) => {
      const state = (
        window as unknown as {
          __signInTest: { releaseStatus: () => void; releaseList: () => void };
        }
      ).__signInTest;
      if (pending === "status") state.releaseStatus();
      else state.releaseList();
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      );
    }, pending);
    // An older absent/unavailable snapshot cannot undo the acknowledged login.
    expect((await signInState(target)).statusReads).toBe(reads);
    expect((await signInState(target)).tuiStarts).toBe(1);
    expect((await signInState(target)).tuiCloses).toBe(0);
    await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
    await target.evaluate(() => window.dispatchEvent(new Event("focus")));
    await expect
      .poll(async () => (await signInState(target)).statusReads)
      .toBe(Number(reads) + 1);
    await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
    expect((await signInState(target)).submissions).toBe(1);
  });

for (const pending of ["status", "list"] as const)
  test(`profile creation authenticates before a held ${pending} read settles`, async ({
    page: target,
  }) => {
    await signInHost(target, true, false, pending === "list");
    await target.evaluate(() => {
      (
        window as unknown as { __signInTest: { submitCode: string } }
      ).__signInTest.submitCode = "";
    });
    const dialog = target.locator(".sign-in");
    await expect(dialog).toBeVisible();
    if (pending === "status")
      await target.evaluate(() => {
        (
          window as unknown as { __signInTest: { deferStatus: boolean } }
        ).__signInTest.deferStatus = true;
        window.dispatchEvent(new Event("focus"));
      });
    await expect
      .poll(
        async () =>
          (await signInState(target))[
            pending === "status" ? "activeStatusReads" : "activeListReads"
          ],
      )
      .toBe(1);
    const reads = (await signInState(target)).statusReads;
    await dialog
      .getByRole("button", { name: label("desktop.account.new_profile") })
      .click();
    const form = dialog.locator(".create-profile");
    await form
      .getByLabel(label("desktop.account.create.name"), { exact: true })
      .fill("Marta Ruiz á漢");
    await form
      .getByLabel(label("desktop.signin.password"), { exact: true })
      .fill("secret á漢");
    await form
      .getByLabel(label("desktop.account.create.confirm"), { exact: true })
      .fill("secret á漢");
    await form
      .getByRole("button", { name: label("desktop.account.create.submit") })
      .click();
    await expect
      .poll(async () => (await signInState(target)).creations)
      .toBe(1);
    await expect
      .poll(async () => (await signInState(target)).createdSecretCleared)
      .toBe(true);
    expect((await signInState(target)).statusReads).toBe(reads);
    expect(
      (await signInState(target))[
        pending === "status" ? "activeStatusReads" : "activeListReads"
      ],
    ).toBe(1);
    await target.evaluate((pending) => {
      const state = (
        window as unknown as {
          __signInTest: { releaseStatus: () => void; releaseList: () => void };
        }
      ).__signInTest;
      if (pending === "status") state.releaseStatus();
      else state.releaseList();
    }, pending);
    await expect(dialog).toHaveCount(0);
    expect((await signInState(target)).tuiStarts).toBe(0);
    await revealTui(target);
    await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
    const state = await signInState(target);
    expect(state.creations).toBe(1);
    expect(state.statusReads).toBe(reads);
    expect(state.submissions).toBe(1);
    expect(state.profileHeader).toBe(state.createdHeader);
    expect(state.rawPassword).toBe(true);
    expect(state.secretCleared).toBe(true);
    expect(state.createdHeader).toBe("Marta%20Ruiz%20%C3%A1%E6%BC%A2");
    expect(state.createdRawPassword).toBe(true);
    expect(state.createdTokenHeader).toBe(true);
  });

test("a chosen profile is named to the host by its label, percent-encoded in a header", async ({
  page: target,
}) => {
  await signInHost(target);
  await target.evaluate(() => {
    const state = (
      window as unknown as {
        __signInTest: {
          profiles: { name: string; active: boolean }[];
          submitCode: string;
        };
      }
    ).__signInTest;
    state.profiles = [
      { name: "Taller Ribera, S.L. á漢", active: false },
      { name: "Test profile", active: true },
    ];
    state.submitCode = "";
    window.dispatchEvent(new Event("focus"));
  });
  const dialog = target.locator(".sign-in");
  const choice = dialog.getByLabel(label("desktop.signin.profile"), {
    exact: true,
  });
  await expect(choice.locator("option:checked")).toHaveText("Test profile");
  await choice.selectOption({ label: "Taller Ribera, S.L. á漢" });
  await target
    .getByLabel(label("desktop.signin.password"), { exact: true })
    .fill("secret á漢");
  await target
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect
    .poll(async () => (await signInState(target)).submissions)
    .toBe(1);
  const state = await signInState(target);
  expect(state.profileHeader).toBe(
    "Taller%20Ribera%2C%20S.L.%20%C3%A1%E6%BC%A2",
  );
  // The label is ASCII on the wire, and the password is not in it.
  expect(state.profileHeader).toMatch(/^[\x21-\x7e]+$/);
  expect(state.rawPassword).toBe(true);
  expect(state.tokenHeader).toBe(true);
});

test("a created profile remains available when automatic sign-in is refused", async ({
  page: target,
}) => {
  await signInHost(target);
  const dialog = target.locator(".sign-in");
  await dialog
    .getByRole("button", { name: label("desktop.account.new_profile") })
    .click();
  const form = dialog.locator(".create-profile");
  await form
    .getByLabel(label("desktop.account.create.name"), { exact: true })
    .fill("Marta Ruiz á漢");
  await form
    .getByLabel(label("desktop.signin.password"), { exact: true })
    .fill("secret á漢");
  await form
    .getByLabel(label("desktop.account.create.confirm"), { exact: true })
    .fill("secret á漢");
  await form
    .getByRole("button", { name: label("desktop.account.create.submit") })
    .click();
  // Creation succeeded, but the runtime refused the subsequent sign-in.
  await expect(dialog.locator("#profile-password")).toBeFocused();
  await expect(dialog.locator("#profile-choice option:checked")).toHaveText(
    "Marta Ruiz á漢",
  );
  const state = await signInState(target);
  expect(state.creations).toBe(1);
  expect(state.createdHeader).toBe("Marta%20Ruiz%20%C3%A1%E6%BC%A2");
  expect(state.createdRawPassword).toBe(true);
  expect(state.createdTokenHeader).toBe(true);
  expect(state.createdSecretCleared).toBe(true);
  expect(state.submissions).toBe(1);
  expect(state.profileHeader).toBe(state.createdHeader);
  expect(state.rawPassword).toBe(true);
  expect(state.secretCleared).toBe(true);
  expect(state.tuiStarts).toBe(0);
});
