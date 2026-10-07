import { expect, test, type Page } from "@playwright/test";
import { label } from "./support/strings";

// Exercise the shipped renderer through its real transport adapter. This host
// emits deterministic VT bytes; no private TUI output or credentials are used.
async function openTerminal(page: Page, fontSize = "medium") {
  await page.addInitScript((fontSize) => {
    let callback = 0;
    const state = {
      opens: 0,
      cols: 0,
      rows: 0,
      written: 0,
      acknowledged: 0,
      write: (_text: string) => {
        void _text;
      },
    };
    localStorage.setItem(
      "cadrumo-shell-layout",
      JSON.stringify({
        layout: { panelOpen: true, tab: "console" },
        prefs: { fontSize },
      }),
    );
    Object.assign(window, {
      isTauri: true,
      __renderTest: state,
      __CADRUMO_SHELL__: { token: "a".repeat(64) },
      __TAURI_INTERNALS__: {
        transformCallback: () => ++callback,
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
                state: "absent",
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
              ++state.opens;
              state.cols = Number(args.cols);
              state.rows = Number(args.rows);
              const frames = args.frames as {
                onmessage(data: ArrayBuffer): void;
              };
              state.write = (text) => {
                const bytes = new TextEncoder().encode(text);
                state.written += bytes.length;
                frames.onmessage(Uint8Array.from([0, ...bytes]).buffer);
              };
              return { session: 1 };
            }
            case "terminal_resize":
              state.cols = Number(args.cols);
              state.rows = Number(args.rows);
              return {};
            case "terminal_ack":
              state.acknowledged = Number(args.offset);
              return {};
            case "logs_subscribe":
              return {
                subscription: 1,
                state: { kind: "missing", detail: "" },
              };
            default:
              return {};
          }
        },
      },
    });
  }, fontSize);
  await page.route("http://docs.cadrumo.test/**", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: "<!doctype html><title>Fixture</title>",
    }),
  );
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".sign-in")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator(".sign-in")).toBeHidden();
}

type Probe = {
  opens: number;
  cols: number;
  rows: number;
  written: number;
  acknowledged: number;
  write(text: string): void;
};
async function drawGrid(page: Page) {
  await page.evaluate(() => {
    const state = (window as unknown as { __renderTest: Probe }).__renderTest;
    const count = Math.min(120, state.cols - 3);
    const runs = ["W", "i", " ", "─", "á", "ă"];
    state.write(
      "\x1b[?1049h\x1b[?25l\x1b[2J\x1b[H" +
        runs
          .map(
            (char, row) =>
              `\x1b[${row + 1};1H\x1b[0;38;2;0;255;0m${row % 2 ? "\x1b[1m" : ""}${char.repeat(count)}\x1b[0;38;2;255;0;0m|\x1b[0m`,
          )
          .join(""),
    );
  });
  await expect
    .poll(() =>
      page.evaluate(() => {
        const state = (window as unknown as { __renderTest: Probe })
          .__renderTest;
        return state.acknowledged === state.written;
      }),
    )
    .toBe(true);
}

async function columnSpread(page: Page) {
  const screenshot = await page
    .locator('[data-terminal="console"] .xterm-screen')
    .screenshot();
  await test
    .info()
    .attach("rendered-grid", { body: screenshot, contentType: "image/png" });
  // Measure the rendered pixels, not xterm's internal model of where a glyph
  // should be. This catches both stale font metrics and DOM rounding drift.
  return page.evaluate(
    async (bytes) => {
      const image = await createImageBitmap(
        new Blob([Uint8Array.from(bytes)], { type: "image/png" }),
      );
      const canvas = new OffscreenCanvas(image.width, image.height);
      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(image, 0, 0);
      image.close();
      const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const rows = (window as unknown as { __renderTest: Probe }).__renderTest
        .rows;
      const markers = Array.from({ length: 6 }, (_, row) => {
        let left = Infinity;
        for (
          let y = Math.ceil((row * canvas.height) / rows);
          y < Math.floor(((row + 1) * canvas.height) / rows);
          y++
        ) {
          for (let x = 0; x < canvas.width; x++) {
            const at = (y * canvas.width + x) * 4;
            if (data[at]! - Math.max(data[at + 1]!, data[at + 2]!) > 40)
              left = Math.min(left, x);
          }
        }
        if (!Number.isFinite(left))
          throw new Error(`Missing painted column marker on row ${row}`);
        return left;
      });
      return (Math.max(...markers) - Math.min(...markers)) / devicePixelRatio;
    },
    [...screenshot],
  );
}

test("cold font loads preserve equal columns across text and TUI borders", async ({
  page,
}) => {
  const waiting: (() => Promise<void>)[] = [];
  await page.route(/jetbrains-mono.*\.woff2/, (route) => {
    waiting.push(() => route.continue());
  });
  await openTerminal(page);
  await expect.poll(() => waiting.length).toBeGreaterThan(0);
  const consoleButton = page
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.console") });
  await consoleButton.click();
  await consoleButton.click();
  // Exceed the normal focus-wish timeout while terminal initialization waits.
  await page.waitForTimeout(1200);
  expect(
    await page.evaluate(
      () => (window as unknown as { __renderTest: Probe }).__renderTest.opens,
    ),
  ).toBe(0);
  // Release every requested subset, then allow later requests normally.
  await page.unroute(/jetbrains-mono.*\.woff2/);
  await Promise.all(waiting.map((release) => release()));
  await page.evaluate(() => document.fonts.ready);
  await expect
    .poll(() =>
      page.evaluate(
        () => (window as unknown as { __renderTest: Probe }).__renderTest.opens,
      ),
    )
    .toBe(1);
  await drawGrid(page);
  expect(await columnSpread(page)).toBeLessThan(1);
  await expect(
    page.locator('[data-terminal="console"] textarea'),
  ).toBeFocused();
});

for (const scale of [1, 1.25, 1.5]) {
  test.describe(`display scale ${scale}`, () => {
    for (const fontSize of ["small", "medium", "large", "x-large"]) {
      test(`${fontSize} cell columns stay aligned after resize`, async ({
        playwright,
        baseURL,
      }) => {
        // Chromium's context-only DPR emulation leaves ResizeObserver's
        // physical pixel box at the host scale. Match the browser scale too.
        const browser = await playwright.chromium.launch({
          args: [`--force-device-scale-factor=${scale}`],
        });
        const page = await browser.newPage({
          baseURL,
          viewport: { width: 1440, height: 1050 },
          deviceScaleFactor: scale,
        });
        try {
          await openTerminal(page, fontSize);
          await expect
            .poll(() =>
              page.evaluate(
                () =>
                  (window as unknown as { __renderTest: Probe }).__renderTest
                    .opens,
              ),
            )
            .toBe(1);
          await drawGrid(page);
          expect(await columnSpread(page)).toBeLessThan(1);
          const before = await page.evaluate(
            () =>
              (window as unknown as { __renderTest: Probe }).__renderTest.cols,
          );
          await page.setViewportSize({ width: 1024, height: 768 });
          await expect
            .poll(() =>
              page.evaluate(
                () =>
                  (window as unknown as { __renderTest: Probe }).__renderTest
                    .cols,
              ),
            )
            .toBeLessThan(before);
          await drawGrid(page);
          expect(await columnSpread(page)).toBeLessThan(1);
          const pane = page.locator('[data-terminal="console"]');
          await expect(pane.locator("canvas").first()).toBeVisible();
        } finally {
          await browser.close();
        }
      });
    }
  });
}

test("user input cancels focus owed to a terminal awaiting fonts", async ({
  page,
}) => {
  const waiting: (() => Promise<void>)[] = [];
  const fonts = /jetbrains-mono.*\.woff2/;
  await page.route(fonts, (route) => {
    waiting.push(() => route.continue());
  });
  await openTerminal(page);
  await expect.poll(() => waiting.length).toBeGreaterThan(0);
  const rail = page.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  const consoleButton = rail.getByRole("button", {
    name: label("desktop.rail.console"),
  });
  await consoleButton.click();
  await consoleButton.click();
  await rail
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  const size = page.getByRole("radiogroup", {
    name: label("desktop.settings.terminal_text"),
  });
  await size.getByRole("radio", { name: "16", exact: true }).click();
  await page.unroute(fonts);
  await Promise.all(waiting.map((release) => release()));
  await expect
    .poll(() =>
      page.evaluate(
        () => (window as unknown as { __renderTest: Probe }).__renderTest.opens,
      ),
    )
    .toBe(1);
  await expect(
    size.getByRole("radio", { name: "16", exact: true }),
  ).toBeFocused();
});

test("failed fonts use a stable fallback and hiding retains the grid", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      this: HTMLCanvasElement,
      ...args: Parameters<typeof getContext>
    ) {
      return args[0] === "webgl2" ? null : getContext.apply(this, args);
    } as typeof getContext;
  });
  await page.route(/jetbrains-mono.*\.woff2/, (route) => route.abort());
  await openTerminal(page);
  await expect
    .poll(() =>
      page.evaluate(
        () => (window as unknown as { __renderTest: Probe }).__renderTest.opens,
      ),
    )
    .toBe(1);
  await drawGrid(page);
  expect(await columnSpread(page)).toBeLessThan(1);
  const pane = page.locator('[data-terminal="console"]');
  expect(
    await pane
      .locator(".xterm-rows")
      .evaluate((node) => getComputedStyle(node).fontFamily),
  ).not.toContain("JetBrains");
  await page.keyboard.press("Escape");
  const button = page
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.console") });
  await button.click();
  await expect(pane).toBeHidden();
  await page.setViewportSize({ width: 1100, height: 850 });
  await button.click();
  await expect(pane).toBeVisible();
  await drawGrid(page);
  expect(await columnSpread(page)).toBeLessThan(1);
  expect(
    await page.evaluate(
      () => (window as unknown as { __renderTest: Probe }).__renderTest.opens,
    ),
  ).toBe(1);
});

test("lost graphics context falls back without reopening the terminal", async ({
  page,
}) => {
  const failures: string[] = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await openTerminal(page);
  const pane = page.locator('[data-terminal="console"]');
  await expect(pane.locator("canvas").last()).toBeVisible();
  await drawGrid(page);
  await pane.locator(".xterm-screen > canvas:last-child").evaluate((node) => {
    const gl = (node as HTMLCanvasElement).getContext("webgl2")!;
    const extension = gl.getExtension("WEBGL_lose_context");
    if (!extension)
      throw new Error("Test browser cannot simulate context loss");
    extension.loseContext();
  });
  await expect(pane.locator(".xterm-rows")).toBeVisible({ timeout: 8000 });
  await drawGrid(page);
  expect(await columnSpread(page)).toBeLessThan(1);
  expect(
    await page.evaluate(
      () => (window as unknown as { __renderTest: Probe }).__renderTest.opens,
    ),
  ).toBe(1);
  expect(failures).toEqual([]);
});

test("TUI box borders join across rows without gaps or protruding strokes", async ({
  page,
}) => {
  await openTerminal(page);
  await expect(
    page.locator('[data-terminal="console"] canvas').last(),
  ).toBeVisible();
  await page.evaluate(() => {
    const state = (window as unknown as { __renderTest: Probe }).__renderTest;
    const lines = [
      "┌──────┐",
      "│      │",
      "│      │",
      "│      │",
      "│      │",
      "└──────┘",
    ];
    state.write(
      "\x1b[?1049h\x1b[?25l\x1b[2J\x1b[0;38;2;0;255;0m" +
        lines.map((line, row) => `\x1b[${row + 3};3H${line}`).join(""),
    );
  });
  await expect
    .poll(() =>
      page.evaluate(() => {
        const state = (window as unknown as { __renderTest: Probe })
          .__renderTest;
        return state.acknowledged === state.written;
      }),
    )
    .toBe(true);
  const screenshot = await page
    .locator('[data-terminal="console"] .xterm-screen')
    .screenshot();
  await test
    .info()
    .attach("box-border", { body: screenshot, contentType: "image/png" });
  const result = await page.evaluate(
    async (bytes) => {
      const image = await createImageBitmap(
        new Blob([Uint8Array.from(bytes)], { type: "image/png" }),
      );
      const canvas = new OffscreenCanvas(image.width, image.height);
      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(image, 0, 0);
      image.close();
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      const { cols, rows } = (window as unknown as { __renderTest: Probe })
        .__renderTest;
      const width = canvas.width / cols,
        height = canvas.height / rows;
      const green = (x: number, y: number) => {
        const at = (y * canvas.width + x) * 4;
        return data[at + 1]! - Math.max(data[at]!, data[at + 2]!) > 40;
      };
      let gaps = 0;
      const left: number[] = [],
        right: number[] = [];
      for (let y = Math.ceil(3 * height); y < Math.floor(7 * height); y++) {
        const stroke = [];
        for (let x = Math.floor(2 * width); x < Math.ceil(3 * width); x++)
          if (green(x, y)) stroke.push(x);
        if (!stroke.length) gaps++;
        else {
          left.push(Math.min(...stroke));
          right.push(Math.max(...stroke));
        }
      }
      return { gaps, wobble: Math.max(...right) - Math.min(...left) };
    },
    [...screenshot],
  );
  expect(result.gaps).toBe(0);
  expect(result.wobble).toBeLessThanOrEqual(1);
});

test("font changes while hidden preserve the PTY size until the pane is shown", async ({
  page,
}) => {
  await openTerminal(page);
  await expect
    .poll(() =>
      page.evaluate(
        () => (window as unknown as { __renderTest: Probe }).__renderTest.opens,
      ),
    )
    .toBe(1);
  const rail = page.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  const consoleButton = rail.getByRole("button", {
    name: label("desktop.rail.console"),
  });
  await consoleButton.click();
  await expect(page.locator('[data-terminal="console"]')).toBeHidden();
  const before = await page.evaluate(() => {
    const { cols, rows } = (window as unknown as { __renderTest: Probe })
      .__renderTest;
    return { cols, rows };
  });
  await rail
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  await page
    .getByRole("radiogroup", { name: label("desktop.settings.terminal_text") })
    .getByRole("radio", { name: "16", exact: true })
    .click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          JSON.parse(localStorage.getItem("cadrumo-shell-layout")!).prefs
            .fontSize,
      ),
    )
    .toBe("x-large");
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  expect(
    await page.evaluate(() => {
      const { cols, rows } = (window as unknown as { __renderTest: Probe })
        .__renderTest;
      return { cols, rows };
    }),
  ).toEqual(before);
  await page.keyboard.press("Escape");
  await consoleButton.click();
  await expect
    .poll(() =>
      page.evaluate(
        () => (window as unknown as { __renderTest: Probe }).__renderTest.cols,
      ),
    )
    .toBeLessThan(before.cols);
  await drawGrid(page);
  expect(await columnSpread(page)).toBeLessThan(1);
});
