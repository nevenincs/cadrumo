import { expect, test } from "@playwright/test";
import { label } from "./support/strings";

// Runs the production adapter with a transport fixture. Native operations are
// verified separately; these checks cover authentication and UI state routing.
test("window controls use authenticated commands and native presentation", async ({
  page,
}) => {
  await page.addInitScript(() => {
    let id = 0;
    const state = {
      actions: [] as string[],
      tokens: [] as unknown[],
      maximized: false,
      fullscreen: false,
      chrome: "custom" as "custom" | "native",
      fail: false,
      diagnostics: [] as Record<string, unknown>[],
      crash: () => undefined as void,
      publish: (next: {
        maximized: boolean;
        fullscreen: boolean;
        chrome: "custom" | "native";
      }) => {
        void next;
      },
    };
    Object.assign(window, {
      isTauri: true,
      __windowTest: state,
      __CADRUMO_SHELL__: { token: "a".repeat(64) },
      __TAURI_INTERNALS__: {
        transformCallback: () => ++id,
        unregisterCallback: () => undefined,
        async invoke(command: string, args: Record<string, unknown>) {
          if (command.startsWith("shell_window_"))
            state.tokens.push(args.token);
          switch (command) {
            case "desktop_frontend_diagnostic":
              state.diagnostics.push(args.report as Record<string, unknown>);
              return null;
            case "manager_status":
              return { state: "ready", failure: null };
            case "manager_subscribe":
              (
                args.updates as { onmessage: (signal: unknown) => void }
              ).onmessage({
                kind: "manager-state",
                revision: 1,
                status: { state: "ready", failure: null },
              });
              return ++id;
            case "manager_unsubscribe":
              return null;
            case "shell_window_subscribe": {
              const channel = args.updates as {
                onmessage: typeof state.publish;
                id: number;
              };
              state.publish = (next) => channel.onmessage({ ...next });
              state.crash = () =>
                channel.onmessage(
                  new Proxy(
                    { maximized: false, fullscreen: false, chrome: "custom" },
                    {
                      get(target, name) {
                        if (name === "fullscreen")
                          throw new Error("private-react-canary");
                        return Reflect.get(target, name);
                      },
                    },
                  ),
                );
              state.publish(state);
              return channel.id;
            }
            case "shell_window_unsubscribe":
            case "sign_in_unsubscribe":
              return;
            case "shell_window_action":
              state.actions.push(args.action as string);
              if (state.fail) throw { code: "webview_failed" };
              if (args.action === "toggle_maximize") {
                state.maximized = !state.maximized;
                state.publish(state);
              }
              return;
            case "sign_in_subscribe":
              return 1;
            case "sign_in_status":
              return {
                supported: false,
                state: "unknown",
                runtimeAvailable: true,
                active_profile: null,
                refusal: null,
              };
            case "logs_subscribe":
              return { subscription: 1 };
            default:
              throw { code: "unsupported" };
          }
        },
      },
    });
  });
  await page.goto("/");
  const maximize = page.getByRole("button", {
    name: label("desktop.titlebar.maximize"),
    exact: true,
  });
  await expect(maximize).toBeEnabled();
  await maximize.click();
  await expect(
    page.getByRole("button", {
      name: label("desktop.titlebar.restore"),
      exact: true,
    }),
  ).toBeEnabled();
  await page
    .locator(".titlebar-drag-space")
    .dispatchEvent("mousedown", { button: 0, detail: 2 });
  await expect(maximize).toBeEnabled();
  await page
    .locator(".titlebar-brand")
    .dispatchEvent("mousedown", { button: 0, detail: 1 });
  await page
    .locator(".titlebar-brand")
    .dispatchEvent("mousedown", { button: 2, detail: 1 });
  await page
    .locator(".profile-trigger")
    .dispatchEvent("mousedown", { button: 0, detail: 1 });
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", {
      name: label("desktop.titlebar.minimize"),
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: label("desktop.titlebar.close"), exact: true })
    .click();
  const read = () =>
    page.evaluate(
      () =>
        (
          window as unknown as {
            __windowTest: { actions: string[]; tokens: unknown[] };
          }
        ).__windowTest,
    );
  // The page asks before its own close button closes, so the close it sends
  // is the answer that the host does not hold to ask the page again.
  await expect
    .poll(async () => (await read()).actions)
    .toEqual([
      "toggle_maximize",
      "toggle_maximize",
      "drag",
      "minimize",
      "close_now",
    ]);
  expect((await read()).tokens.every((token) => token === "a".repeat(64))).toBe(
    true,
  );
  await page.evaluate(() => {
    const state = (
      window as unknown as {
        __windowTest: {
          fullscreen: boolean;
          publish: (next: {
            maximized: boolean;
            fullscreen: boolean;
            chrome: "custom" | "native";
          }) => void;
        };
      }
    ).__windowTest;
    state.fullscreen = true;
    state.publish({ maximized: false, fullscreen: true, chrome: "custom" });
  });
  await expect(maximize).toBeDisabled();
  await page.evaluate(() => {
    const state = (
      window as unknown as {
        __windowTest: {
          publish: (next: {
            maximized: boolean;
            fullscreen: boolean;
            chrome: "custom" | "native";
          }) => void;
        };
      }
    ).__windowTest;
    state.publish({ maximized: false, fullscreen: false, chrome: "native" });
  });
  // A native window shows the system's controls, not the page's.
  await expect(maximize).toHaveCount(0);
  await expect(page.locator("header.titlebar")).toHaveAttribute(
    "data-chrome",
    "native",
  );
  await page.evaluate(() => {
    (
      window as unknown as {
        __windowTest: {
          publish: (next: {
            maximized: boolean;
            fullscreen: boolean;
            chrome: "custom" | "native";
          }) => void;
        };
      }
    ).__windowTest.publish({
      maximized: false,
      fullscreen: true,
      chrome: "custom",
    });
  });
  await expect(maximize).toBeDisabled();
  await page.evaluate(() => {
    (
      window as unknown as { __windowTest: { fail: boolean } }
    ).__windowTest.fail = true;
  });
  await page
    .getByRole("button", {
      name: label("desktop.titlebar.minimize"),
      exact: true,
    })
    .click();
  await expect(
    page.getByText(label("desktop.titlebar.failed"), { exact: true }),
  ).toBeVisible();
  const diagnostics = () =>
    page.evaluate(
      () =>
        (
          window as unknown as {
            __windowTest: { diagnostics: Record<string, unknown>[] };
          }
        ).__windowTest.diagnostics,
    );
  await expect
    .poll(async () =>
      (await diagnostics()).some(
        (record) =>
          record.event === "command_rejected" &&
          record.command === "shell_window_action" &&
          record.code === "webview_failed",
      ),
    )
    .toBe(true);
  await page.evaluate(() => {
    console.debug("private-diagnostic-canary");
    console.info("private-diagnostic-canary");
    console.warn("private-diagnostic-canary");
    console.error("private-diagnostic-canary");
    window.dispatchEvent(
      new ErrorEvent("error", { message: "private-diagnostic-canary" }),
    );
    window.dispatchEvent(
      new PromiseRejectionEvent("unhandledrejection", {
        promise: Promise.resolve(),
        reason: new Error("private-diagnostic-canary"),
      }),
    );
  });
  await expect(
    page.getByText(label("desktop.error.internal"), { exact: true }),
  ).toBeVisible();
  await expect
    .poll(async () =>
      (await diagnostics())
        .filter((record) => record.event === "console")
        .map((record) => record.level),
    )
    .toEqual(["DEBUG", "INFO", "WARNING", "ERROR"]);
  const reports = await diagnostics();
  expect(reports.some((record) => record.event === "uncaught_error")).toBe(
    true,
  );
  expect(reports.some((record) => record.event === "unhandled_rejection")).toBe(
    true,
  );
  expect(JSON.stringify(reports)).not.toContain("private-diagnostic-canary");
  await page.evaluate(() => {
    (
      window as unknown as { __windowTest: { crash: () => void } }
    ).__windowTest.crash();
  });
  await expect(page.getByRole("alert")).toContainText(
    label("desktop.error.internal"),
  );
  await expect
    .poll(async () =>
      (await diagnostics()).some((record) => record.event === "react_error"),
    )
    .toBe(true);
  expect(JSON.stringify(await diagnostics())).not.toContain(
    "private-react-canary",
  );
  // Even a fatal render error leaves the principal close control usable.
  await page.evaluate(() => {
    (
      window as unknown as { __windowTest: { fail: boolean } }
    ).__windowTest.fail = false;
  });
  await page
    .getByRole("button", { name: label("desktop.titlebar.close"), exact: true })
    .click();
  await expect
    .poll(async () => (await read()).actions.at(-1))
    .toBe("close_now");
});
