import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { label } from "./support/strings";

const root = fileURLToPath(new URL("../../../../", import.meta.url));
const python = fileURLToPath(
  new URL(
    process.platform === "win32"
      ? "../../../../.venv/Scripts/python.exe"
      : "../../../../.venv/bin/python",
    import.meta.url,
  ),
);
const environment: NodeJS.ProcessEnv = {
  ...process.env,
  TERM_PROGRAM: "cadrumo",
};
delete environment.NO_COLOR;
// Real Textual rendering, transported to the unchanged product xterm pane.
// This tests color ownership, not authentication or native PTY transport.
const sample: string = JSON.parse(
  execFileSync(
    python,
    ["-m", "cadrumo.entrypoints.tui.tests.terminal_theme_sample"],
    { cwd: root, env: environment, encoding: "utf8" },
  ),
);

type Kind = "tui" | "console" | "python";
type Probe = {
  opens: string[];
  writes: number;
  write(kind: Kind, text: string): void;
};

async function openHost(page: Page) {
  await page.addInitScript(() => {
    const streams = new Map<string, (text: string) => void>();
    const state = {
      opens: [] as string[],
      writes: 0,
      write(kind: string, text: string) {
        streams.get(kind)?.(text);
      },
    };
    let id = 0;
    localStorage.setItem(
      "cadrumo-shell-layout",
      JSON.stringify({
        layout: { panelOpen: true, tab: "console" },
        prefs: { appearance: "dark", terminals: "match" },
      }),
    );
    Object.assign(window, {
      isTauri: true,
      __themeTest: state,
      __CADRUMO_SHELL__: { token: "a".repeat(64) },
      __TAURI_INTERNALS__: {
        transformCallback: () => ++id,
        unregisterCallback: () => {},
        async invoke(command: string, args: Record<string, unknown>) {
          switch (command) {
            case "desktop_environment":
              return {
                outputLanguage: "en",
                docs: {
                  origin: "http://docs.cadrumo.test",
                  languages: [
                    {
                      code: "en",
                      entry: "http://docs.cadrumo.test/index.html",
                    },
                  ],
                },
              };
            case "sign_in_status":
              return {
                supported: true,
                state: "present",
                active_profile: "Fixture",
                runtimeAvailable: true,
                refusal: null,
              };
            case "profile_list":
              return {
                profiles: [{ name: "Fixture", active: true }],
                complete: true,
              };
            case "terminal_open": {
              const kind = String(args.kind);
              state.opens.push(kind);
              const frames = args.frames as {
                onmessage(data: ArrayBuffer): void;
              };
              streams.set(kind, (text) =>
                frames.onmessage(
                  Uint8Array.from([0, ...new TextEncoder().encode(text)])
                    .buffer,
                ),
              );
              return { session: ++id };
            }
            case "terminal_write":
              ++state.writes;
              return {};
            case "logs_subscribe":
              return {
                subscription: 1,
                states: {
                  python: { kind: "missing", detail: "" },
                  manager: { kind: "missing", detail: "" },
                },
              };
            default:
              return {};
          }
        },
      },
    });
  });
  await page.route("http://docs.cadrumo.test/**", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: "<!doctype html><title>Fixture</title>",
    }),
  );
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator('[data-terminal="tui"] .xterm')).toBeVisible();
  await expect(page.locator('[data-terminal="console"] .xterm')).toBeVisible();
  await write(page, "tui", sample);
  await write(
    page,
    "console",
    "\x1b[2J\x1b[HExisting shell output\r\n\x1b[34mBlue text\x1b[0m",
  );
}

async function write(page: Page, kind: Kind, text: string) {
  await page.evaluate(
    ({ kind, text }) => {
      (window as unknown as { __themeTest: Probe }).__themeTest.write(
        kind,
        text,
      );
    },
    { kind, text },
  );
}

async function choose(page: Page, key: string, value: string) {
  await page
    .getByRole("button", { name: label("desktop.rail.settings"), exact: true })
    .click();
  await page
    .getByRole("radiogroup", { name: label(key) })
    .getByRole("radio", { name: label(value), exact: true })
    .click();
  await page.keyboard.press("Escape");
}

async function colors(page: Page, kind: Kind): Promise<Record<string, number>> {
  const screenshot = await page
    .locator(`[data-terminal="${kind}"] .xterm-screen`)
    .screenshot();
  await test
    .info()
    .attach(`${kind}-palette`, { body: screenshot, contentType: "image/png" });
  return page.evaluate(
    async (bytes) => {
      const image = await createImageBitmap(
        new Blob([Uint8Array.from(bytes)], { type: "image/png" }),
      );
      const canvas = new OffscreenCanvas(image.width, image.height);
      const context = canvas.getContext("2d")!;
      context.drawImage(image, 0, 0);
      const { data } = context.getImageData(0, 0, image.width, image.height);
      image.close();
      const counts: Record<string, number> = {};
      for (let at = 0; at < data.length; at += 4) {
        const key = [data[at], data[at + 1], data[at + 2]]
          .map((part) => part!.toString(16).padStart(2, "0"))
          .join("");
        counts[key] = (counts[key] ?? 0) + 1;
      }
      return counts;
    },
    [...screenshot],
  );
}

test("live appearance recolors existing TUI and shell content without restarting", async ({
  page,
}) => {
  await openHost(page);
  let pixels = await colors(page, "tui");
  expect(pixels["1a1815"]).toBeGreaterThan(1000);
  expect(pixels["232019"]).toBeGreaterThan(100);
  expect(pixels["7fb3e0"]).toBeGreaterThan(100);
  expect(pixels["9ab8d8"]).toBeGreaterThan(10);
  // This sample uses surface, not panel. Bold border-title ink must stay
  // accent, rather than being promoted to the bright-magenta panel slot.
  expect(pixels["2e2a22"] ?? 0).toBe(0);
  await choose(page, "desktop.settings.appearance", "desktop.settings.light");
  await expect(page.locator(".pane-tui")).toHaveAttribute(
    "data-scheme",
    "light",
  );
  pixels = await colors(page, "tui");
  expect(pixels["faf8f4"]).toBeGreaterThan(1000);
  expect(pixels["f1eee7"]).toBeGreaterThan(100);
  expect(pixels["2b5f8a"]).toBeGreaterThan(100);
  expect(pixels["35587a"]).toBeGreaterThan(10);
  expect(pixels["e9e3da"] ?? 0).toBe(0);
  await page
    .locator(".pane-tui")
    .screenshot({ path: test.info().outputPath("light-tui.png") });
  expect(pixels["1a1815"] ?? 0).toBe(0);
  expect((await colors(page, "console"))["faf8f4"]).toBeGreaterThan(1000);
  await choose(page, "desktop.settings.appearance", "desktop.settings.dark");
  expect((await colors(page, "tui"))["1a1815"]).toBeGreaterThan(1000);
  expect((await colors(page, "console"))["1c1a17"]).toBeGreaterThan(1000);
  const state = await page.evaluate(() => {
    const { opens, writes } = (window as unknown as { __themeTest: Probe })
      .__themeTest;
    return { opens, writes };
  });
  expect(state.opens.sort()).toEqual(["console", "tui"]);
  expect(state.writes).toBe(0);
});

test("hidden Python pane adopts the latest palette and explicit dark override remains effective", async ({
  page,
}) => {
  await openHost(page);
  await page
    .getByRole("tab", { name: label("desktop.rail.python"), exact: true })
    .click();
  await expect(page.locator('[data-terminal="python"] .xterm')).toBeVisible();
  await write(page, "python", ">>> retained Python session");
  await page
    .getByRole("tab", { name: label("desktop.rail.console"), exact: true })
    .click();
  await choose(page, "desktop.settings.appearance", "desktop.settings.light");
  await page
    .getByRole("tab", { name: label("desktop.rail.python"), exact: true })
    .click();
  expect((await colors(page, "python"))["faf8f4"]).toBeGreaterThan(1000);
  await choose(
    page,
    "desktop.settings.terminals",
    "desktop.settings.always_dark",
  );
  expect((await colors(page, "python"))["1c1a17"]).toBeGreaterThan(1000);
  expect((await colors(page, "tui"))["faf8f4"]).toBeGreaterThan(1000);
  expect(
    await page.evaluate(
      () =>
        (window as unknown as { __themeTest: Probe }).__themeTest.opens.length,
    ),
  ).toBe(3);
});

test("only the TUI's exact appearance request changes the desktop preference", async ({
  page,
}) => {
  await openHost(page);
  const request = "\x1b]777;cadrumo;appearance;toggle\x1b\\";
  await write(page, "console", request);
  await write(page, "tui", "\x1b]777;cadrumo;appearance;invalid\x1b\\");
  expect((await colors(page, "tui"))["1a1815"]).toBeGreaterThan(1000);
  await write(page, "tui", request);
  await expect(page.locator(".pane-tui")).toHaveAttribute(
    "data-scheme",
    "light",
  );
  expect((await colors(page, "tui"))["faf8f4"]).toBeGreaterThan(1000);
});

test("automatic appearance updates terminals with the DOM renderer too", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      this: HTMLCanvasElement,
      ...args
    ) {
      if (args[0] === "webgl2") return null;
      return original.apply(this, args);
    } as typeof original;
  });
  await page.emulateMedia({ colorScheme: "light" });
  await openHost(page);
  await choose(
    page,
    "desktop.settings.appearance",
    "desktop.settings.follow_docs",
  );
  expect((await colors(page, "tui"))["faf8f4"]).toBeGreaterThan(1000);
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator(".pane-tui")).toHaveAttribute(
    "data-scheme",
    "dark",
  );
  expect((await colors(page, "tui"))["1a1815"]).toBeGreaterThan(1000);
  expect((await colors(page, "console"))["1c1a17"]).toBeGreaterThan(1000);
});
