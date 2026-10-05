import { expect, test, type Frame, type Page } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { identity } from "../../scripts/configuration.mjs";

const local = (path: string) => fileURLToPath(new URL(path, import.meta.url));

// Expected labels come from the generated catalogue once it exists; before
// that the shell shows each key, and so do these expectations.
const catalogue = local("../src/generated/chrome-strings.json");
const english: Record<string, string> = existsSync(catalogue)
  ? ((
      JSON.parse(readFileSync(catalogue, "utf8")) as Record<
        string,
        Record<string, string>
      >
    ).en ?? {})
  : {};
const label = (key: string) => english[key] ?? key;

// A transport boundary fixture for presentation tests, never a live sign-in
// acceptance claim. The actual Tauri adapter and React shell run unchanged.
async function signInHost(
  target: Page,
  supported = true,
  deferInitial = false,
) {
  await target.addInitScript(
    ({ supported, docs, deferInitial }) => {
      const state = {
        presence: "absent",
        supported,
        runtimeAvailable: true,
        refusal: null as null | {
          code: string;
          retryAfterSeconds: number | null;
        },
        submitCode: "CREDENTIAL_REJECTED",
        retryAfterSeconds: null as number | null,
        submissions: 0,
        statusReads: 0,
        statusError: "",
        activeStatusReads: 0,
        signOuts: 0,
        tuiStarts: 0,
        tuiCloses: 0,
        rawPassword: false,
        tokenHeader: false,
        secretCleared: false,
        deferStatus: deferInitial,
        releaseStatus: null as (() => void) | null,
        exitTui: null as (() => void) | null,
      };
      let id = 0;
      Object.assign(window, {
        isTauri: true,
        __signInTest: state,
        __CADRUMO_SHELL__: { token: "a".repeat(64) },
        __TAURI_INTERNALS__: {
          transformCallback: () => ++id,
          unregisterCallback: () => undefined,
          async invoke(
            command: string,
            args: Record<string, unknown> | Uint8Array,
            options?: { headers?: Record<string, string> },
          ) {
            switch (command) {
              case "desktop_environment":
                return {
                  outputLanguage: "en",
                  docs: {
                    origin: docs,
                    languages: [{ code: "en", entry: `${docs}/index.html` }],
                  },
                };
              case "sign_in_status": {
                ++state.statusReads;
                if (state.activeStatusReads > 0) throw { code: "queue_full" };
                ++state.activeStatusReads;
                const snapshot = {
                  supported: state.supported,
                  state: state.presence,
                  active_profile: "Test profile",
                  runtimeAvailable: state.runtimeAvailable,
                  refusal: state.refusal,
                };
                if (state.deferStatus) {
                  state.deferStatus = false;
                  await new Promise<void>((resolve) => {
                    state.releaseStatus = resolve;
                  });
                }
                --state.activeStatusReads;
                if (state.statusError) throw { code: state.statusError };
                return snapshot;
              }
              case "sign_in_submit": {
                ++state.submissions;
                state.rawPassword =
                  args instanceof Uint8Array &&
                  new TextDecoder().decode(args) === "secret á漢";
                state.tokenHeader =
                  options?.headers?.["x-cadrumo-token"] === "a".repeat(64);
                setTimeout(() => {
                  state.secretCleared =
                    args instanceof Uint8Array &&
                    args.every((byte) => byte === 0);
                }, 0);
                if (state.submitCode)
                  return {
                    kind: "refused",
                    code: state.submitCode,
                    retryAfterSeconds: state.retryAfterSeconds,
                  };
                state.presence = "present";
                return { kind: "signed-in" };
              }
              case "sign_out":
                ++state.signOuts;
                state.presence = "absent";
                return {
                  remainingAccess: {
                    automationEnabled: true,
                    automationRevoked: false,
                  },
                };
              case "terminal_open":
                if (!(args instanceof Uint8Array) && args.kind === "tui") {
                  ++state.tuiStarts;
                  state.exitTui = () =>
                    (
                      args.frames as { onmessage: (data: ArrayBuffer) => void }
                    ).onmessage(
                      Uint8Array.from([
                        2,
                        ...new TextEncoder().encode('{"code":0}'),
                      ]).buffer,
                    );
                }
                return {
                  session:
                    !(args instanceof Uint8Array) && args.kind === "tui"
                      ? 99
                      : ++id,
                };
              case "terminal_close":
                if (!(args instanceof Uint8Array) && args.session === 99)
                  ++state.tuiCloses;
                return {};
              case "logs_subscribe":
                return {
                  subscription: 1,
                  state: { kind: "missing", detail: "" },
                };
              default:
                return null;
            }
          },
        },
      });
    },
    { supported, docs: DOCS, deferInitial },
  );
  await serveDocs(target);
  await target.goto("/");
}

const signInState = (target: Page) =>
  target.evaluate(
    () =>
      (window as unknown as { __signInTest: Record<string, unknown> })
        .__signInTest,
  );

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
  await expect(target.locator(".sign-in")).toContainText("queue_full");
  await target.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { statusError: "" },
    );
    window.dispatchEvent(new Event("focus"));
  });
  await expect(target.locator(".sign-in")).not.toContainText("queue_full");
  expect((await signInState(target)).statusReads).toBe(3);
  expect((await signInState(target)).submissions).toBe(0);
});

test("explicit sign-in waits for a pending status read and submits once", async ({
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
  expect((await signInState(target)).submissions).toBe(0);
  await target.evaluate(() =>
    (
      window as unknown as { __signInTest: { releaseStatus: () => void } }
    ).__signInTest.releaseStatus(),
  );
  await expect(
    target.getByText(label("desktop.signin.refused.invalid")),
  ).toBeVisible();
  expect((await signInState(target)).submissions).toBe(1);
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

test("throttling counts down without retry and a successful sign-in hands over to TUI", async ({
  page: target,
}) => {
  await signInHost(target);
  await target.evaluate(() =>
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { submitCode: "THROTTLED", retryAfterSeconds: 2 },
    ),
  );
  await target
    .getByLabel(label("desktop.signin.password"), { exact: true })
    .fill("secret á漢");
  const submit = target.getByRole("button", {
    name: label("desktop.signin.submit"),
    exact: true,
  });
  await submit.click();
  await expect(submit).toBeDisabled();
  await target.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(submit).toBeEnabled({ timeout: 5000 });
  expect((await signInState(target)).submissions).toBe(1);
  await target.evaluate(() =>
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { submitCode: "", retryAfterSeconds: null },
    ),
  );
  await target
    .getByLabel(label("desktop.signin.password"), { exact: true })
    .fill("secret á漢");
  await submit.click();
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  expect((await signInState(target)).tuiStarts).toBe(1);
  await target.getByRole("button", { name: /Settings/ }).click();
  await target.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { deferStatus: true },
    );
    window.dispatchEvent(new Event("focus"));
  });
  await target
    .getByRole("button", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  expect((await signInState(target)).signOuts).toBe(0);
  await target.evaluate(() =>
    (
      window as unknown as { __signInTest: { releaseStatus: () => void } }
    ).__signInTest.releaseStatus(),
  );
  await expect(
    target.getByText(label("desktop.account.remaining_access")),
  ).toBeVisible();
  // Signing out here leaves the signed-out pane; the dialog is not thrown
  // back at the person who has just chosen to sign out.
  await expect(
    target.getByText(label("desktop.signin.signed_out_lead")),
  ).toBeVisible();
  await expect(
    target.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
  await expect.poll(async () => (await signInState(target)).tuiCloses).toBe(1);
  await target.evaluate(async () => {
    (
      window as unknown as { __signInTest: { releaseStatus: () => void } }
    ).__signInTest.releaseStatus();
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
  });
  await target.keyboard.press("Escape");
  await target
    .locator(".pane-tui")
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(
    target.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toBeFocused();
  expect((await signInState(target)).tuiStarts).toBe(1);
});

test("TUI handover remains available for locked profiles and refreshes on focus", async ({
  page: target,
}) => {
  await signInHost(target);
  await target.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { refusal: { code: "PROFILE_LOCKED", retryAfterSeconds: null } },
    );
    window.dispatchEvent(new Event("focus"));
  });
  await expect(
    target.getByText(label("desktop.signin.refused.profile_locked")),
  ).toBeVisible();
  await target
    .getByRole("button", {
      name: label("desktop.signin.open_tui"),
      exact: true,
    })
    .click();
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  expect((await signInState(target)).submissions).toBe(0);
  const reads = (await signInState(target)).statusReads as number;
  await target.evaluate(() =>
    (
      window as unknown as { __signInTest: { exitTui: () => void } }
    ).__signInTest.exitTui(),
  );
  // Back at the gate, with the status read again: still locked, still said.
  await expect(target.locator(".sign-in")).toContainText(
    label("desktop.signin.refused.profile_locked"),
  );
  expect((await signInState(target)).statusReads).toBeGreaterThan(reads);
});

test("runtime-unavailable remains distinct from unknown presence", async ({
  page: target,
}) => {
  await signInHost(target);
  await target.evaluate(() => {
    Object.assign(
      (window as unknown as { __signInTest: object }).__signInTest,
      { presence: "unknown", runtimeAvailable: false },
    );
    window.dispatchEvent(new Event("focus"));
  });
  await expect(
    target.getByText(label("desktop.signin.refused.runtime_unavailable")),
  ).toBeVisible();
  // With no runtime to ask, a password is not asked for.
  await expect(
    target.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
  expect((await signInState(target)).submissions).toBe(0);
  expect((await signInState(target)).tuiStarts).toBe(0);
});

test("unsupported platforms hide desktop sign-in and Account", async ({
  page: target,
}) => {
  await signInHost(target, false);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  await expect(
    target.getByLabel(label("desktop.signin.password"), { exact: true }),
  ).toHaveCount(0);
  await target.getByRole("button", { name: /Settings/ }).click();
  await expect(
    target.getByRole("region", { name: label("desktop.account.title") }),
  ).toHaveCount(0);
});

// A stand-in documentation origin. It is a different origin from the shell,
// and its pages load the real desktop bridge script.
const DOCS = "http://docs.cadrumo.test";
const bridge = readFileSync(
  local("../../../../docs/_static/cadrumo-desktop-bridge.js"),
  "utf8",
);
const page = (title: string, body: string) =>
  `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${title}</title>` +
  `<script src="/bridge.js"></script></head><body data-theme="light">${body}</body></html>`;
const PAGES: Record<string, string> = {
  "/index.html": page(
    "Stand-in documentation",
    '<h1>Stand-in documentation</h1><p id="text">Casilla 01 total</p>' +
      '<a id="internal" href="/second.html">Second page</a> <a id="external" href="https://example.org/">External</a>',
  ),
  "/second.html": page("Second page", "<h1>Second page</h1>"),
};

async function serveDocs(target: Page) {
  await target.route(`${DOCS}/**`, (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/bridge.js")
      return route.fulfill({ contentType: "text/javascript", body: bridge });
    const html = PAGES[path];
    return html
      ? route.fulfill({ contentType: "text/html", body: html })
      : route.fulfill({ status: 404, body: "" });
  });
}

async function openWithDocs(target: Page) {
  await serveDocs(target);
  await target.goto(`/?docs=${encodeURIComponent(`${DOCS}/index.html`)}`);
  await expect(target.frameLocator(".docs-frame").locator("h1")).toHaveText(
    "Stand-in documentation",
  );
}

/** The documentation frame's own execution context, on the stand-in origin. */
function docsFrame(target: Page): Frame {
  const frame = target.frames().find((f) => f.url().startsWith(DOCS));
  if (!frame) throw new Error("The documentation frame is not loaded.");
  return frame;
}

test.beforeEach(async ({ page: target }) => {
  // Start each test from the default layout, once: a reload inside a test must
  // still see what that test stored.
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("without a host the shell lays out every area and invents nothing", async ({
  page: target,
}) => {
  await target.goto("/");
  await expect(target).toHaveTitle(identity().name);
  const rail = target.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  await expect(rail.getByRole("button")).toHaveCount(7);
  await expect(target.locator(".pane-docs")).toContainText(
    label("desktop.host.unavailable"),
  );
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  for (const rows of await target.locator(".xterm-rows").all())
    await expect(rows).toHaveText("");
  // Only the note shows: an idle terminal would draw its cursor over it.
  await expect(target.locator(".pane-tui .terminal-note")).toHaveText(
    label("desktop.host.unavailable"),
  );
  await expect(target.locator(".pane-tui .terminal-host")).toBeHidden();
  await rail.getByRole("button", { name: label("desktop.rail.logs") }).click();
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.logs") }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(target.locator(".source-banner")).toHaveText(
    label("desktop.host.unavailable"),
  );
  await expect(target.locator(".record")).toHaveCount(0);
});

test("the rail opens and closes the panel tabs and the TUI pane", async ({
  page: target,
}) => {
  await target.goto("/");
  const rail = target.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  const panel = target.locator("section.panel");
  await rail
    .getByRole("button", { name: label("desktop.rail.python") })
    .click();
  await expect(panel).toBeVisible();
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.python") }),
  ).toHaveAttribute("aria-selected", "true");
  await rail
    .getByRole("button", { name: label("desktop.rail.python") })
    .click();
  await expect(panel).toBeHidden();
  await target.keyboard.press("Control+Backquote");
  await expect(panel).toBeVisible();
  await rail.getByRole("button", { name: label("desktop.rail.tui") }).click();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await rail.getByRole("button", { name: label("desktop.rail.tui") }).click();
  await expect(target.locator(".pane-tui")).toBeVisible();
});

test("maximize, swap, orientation and hide never reload the documentation", async ({
  page: target,
}) => {
  await openWithDocs(target);
  // A marker in the page's own window survives only if the frame never
  // remounts or reloads.
  const docs = docsFrame(target);
  await docs.evaluate(() => {
    (window as unknown as { kept: boolean }).kept = true;
  });
  const docsHead = target.locator(".pane-docs .pane-head");
  await docsHead.getByRole("button").first().click();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await expect(target.locator("section.panel")).toBeHidden();
  await docsHead.getByRole("button").first().click();
  await expect(target.locator(".pane-tui")).toBeVisible();
  await docsHead
    .getByRole("button", { name: label("desktop.split.swap") })
    .click();
  await docsHead
    .getByRole("button", { name: label("desktop.split.stack") })
    .click();
  await expect(target.locator(".split")).toHaveClass(/split-column/);
  const rail = target.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  await rail.getByRole("button", { name: label("desktop.rail.tui") }).click();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await rail.getByRole("button", { name: label("desktop.rail.tui") }).click();
  const kept = await docs.evaluate(
    () => (window as unknown as { kept?: boolean }).kept === true,
  );
  expect(kept).toBe(true);
});

test("a window too narrow for side by side stacks without changing the choice", async ({
  page: target,
}) => {
  await target.goto("/");
  const docsHead = target.locator(".pane-docs .pane-head");
  const stack = docsHead.getByRole("button", {
    name: label("desktop.split.stack"),
  });
  await expect(target.locator(".split")).toHaveClass(/split-row/);
  await expect(stack).toBeVisible();
  await target.setViewportSize({ width: 520, height: 600 });
  await expect(target.locator(".split")).toHaveClass(/split-column/);
  // The choice cannot take effect here, so it is not offered.
  await expect(stack).toHaveCount(0);
  await target.setViewportSize({ width: 1280, height: 720 });
  await expect(target.locator(".split")).toHaveClass(/split-row/);
  await expect(stack).toBeVisible();
});

test("the documentation can relay only the chords the shell published to it", async ({
  page: target,
}) => {
  await openWithDocs(target);
  const docs = docsFrame(target);
  const post = (id: string) =>
    docs.evaluate((shortcut) => {
      parent.postMessage(
        {
          channel: "cadrumo-desktop",
          version: 1,
          type: "shortcut",
          id: shortcut,
        },
        "*",
      );
    }, id);
  // An action the shell never published to the frame is refused.
  await post("view.maximizeTui");
  await post("terminal.paste");
  await target.waitForTimeout(300);
  await expect(target.locator(".pane-docs")).toBeVisible();
  // A published chord is honoured, so the refusal above is not silence.
  await expect(async () => {
    await post("panel.logs");
    await expect(
      target.getByRole("tab", { name: label("desktop.rail.logs") }),
    ).toHaveAttribute("aria-selected", "true", { timeout: 500 });
  }).toPass();
});

test("bridge messages from any window but the documentation frame are ignored", async ({
  page: target,
}) => {
  await openWithDocs(target);
  await target.evaluate(() => {
    window.postMessage(
      {
        channel: "cadrumo-desktop",
        version: 1,
        type: "shortcut",
        id: "panel.logs",
      },
      "*",
    );
  });
  await target.waitForTimeout(300);
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.console") }),
  ).toHaveAttribute("aria-selected", "true");
});

test("the remembered layout survives a reload", async ({ page: target }) => {
  await target.goto("/");
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  const settings = target.getByRole("dialog", {
    name: label("desktop.settings.title"),
  });
  await settings
    .getByRole("radiogroup", { name: label("desktop.settings.docs_and_tui") })
    .getByRole("radio", { name: label("desktop.settings.stacked") })
    .click();
  await expect(target.locator(".split")).toHaveClass(/split-column/);
  await target.keyboard.press("Escape");
  await target
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.python") })
    .click();
  await target.reload();
  await expect(target.locator(".split")).toHaveClass(/split-column/);
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.python") }),
  ).toHaveAttribute("aria-selected", "true");
});

test("shell chords pressed inside the documentation reach the shell", async ({
  page: target,
}) => {
  await openWithDocs(target);
  const docs = target.frameLocator(".docs-frame");
  await docs.locator("#text").click();
  const palette = target.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  await expect(async () => {
    await target.keyboard.press("Control+KeyK");
    await expect(palette).toBeVisible({ timeout: 500 });
  }).toPass();
  await target.keyboard.press("Escape");
  await expect(palette).toBeHidden();
});

test("a context menu in the documentation offers copy, link and history", async ({
  page: target,
}) => {
  await openWithDocs(target);
  await target
    .frameLocator(".docs-frame")
    .locator("#external")
    .click({ button: "right" });
  const menu = target.getByRole("menu");
  await expect(menu).toBeVisible();
  await expect(
    menu.getByRole("menuitem", {
      name: label("desktop.menu.copy"),
      exact: true,
    }),
  ).toBeDisabled();
  await expect(
    menu.getByRole("menuitem", { name: label("desktop.menu.copy_link") }),
  ).toBeEnabled();
  await expect(
    menu.getByRole("menuitem", { name: label("desktop.action.docs_back") }),
  ).toBeEnabled();
  await expect(
    menu.getByRole("menuitem", { name: label("desktop.rail.docs_home") }),
  ).toBeEnabled();
  await target.keyboard.press("Escape");
  await expect(menu).toBeHidden();
});

test("external links never navigate the documentation frame", async ({
  page: target,
}) => {
  await openWithDocs(target);
  const docs = target.frameLocator(".docs-frame");
  await docs.locator("#external").click();
  await expect(docs.locator("h1")).toHaveText("Stand-in documentation");
  await docs.locator("#internal").click();
  await expect(docs.locator("h1")).toHaveText("Second page");
});

test("the palette lists actions and runs the chosen one", async ({
  page: target,
}) => {
  await target.goto("/");
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  await expect(palette.getByRole("option").first()).toBeVisible();
  await palette.getByRole("combobox").fill(label("desktop.pane.maximize_tui"));
  await target.keyboard.press("Enter");
  await expect(palette).toBeHidden();
  await expect(target.locator(".pane-docs")).toBeHidden();
  await expect(target.locator(".pane-tui")).toBeVisible();
});

test("a forced appearance reaches the documentation through the bridge", async ({
  page: target,
}) => {
  await openWithDocs(target);
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  await target
    .getByRole("radiogroup", { name: label("desktop.settings.appearance") })
    .getByRole("radio", { name: label("desktop.settings.dark") })
    .click();
  await expect
    .poll(() =>
      docsFrame(target).evaluate(() => document.body.dataset.theme ?? ""),
    )
    .toBe("dark");
  await expect(target.locator("html")).toHaveAttribute("data-scheme", "dark");
});
