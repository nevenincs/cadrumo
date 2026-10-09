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
      fail: false,
      publish: (next: { maximized: boolean; fullscreen: boolean }) => {
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
            case "shell_window_subscribe": {
              const channel = args.updates as {
                onmessage: typeof state.publish;
                id: number;
              };
              state.publish = (next) => channel.onmessage(next);
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
                runtimeAvailable: false,
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
  await expect
    .poll(async () => (await read()).actions)
    .toEqual([
      "toggle_maximize",
      "toggle_maximize",
      "drag",
      "minimize",
      "close",
    ]);
  expect((await read()).tokens.every((token) => token === "a".repeat(64))).toBe(
    true,
  );
  await page.evaluate(() => {
    const state = (
      window as unknown as {
        __windowTest: {
          fullscreen: boolean;
          publish: (next: { maximized: boolean; fullscreen: boolean }) => void;
        };
      }
    ).__windowTest;
    state.fullscreen = true;
    state.publish({ maximized: false, fullscreen: true });
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
});
