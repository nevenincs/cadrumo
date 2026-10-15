import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const engine = readFileSync(
  fileURLToPath(
    new URL("../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);
type StartupState = {
  phase: string;
  locale: string;
  failure: { code: string } | null;
  calls: string[];
  painted: boolean;
};
type StartupWindow = Window & { __startupTest: StartupState };

async function open(page: Page) {
  await page.addInitScript(() => {
    const state: StartupState = {
      phase: "environment",
      locale: "en",
      failure: null,
      calls: [],
      painted: false,
    };
    Object.assign(window, {
      isTauri: true,
      __startupTest: state,
      __CADRUMO_SHELL__: { token: "a".repeat(64) },
      __TAURI_INTERNALS__: {
        async invoke(command: string, args: { token: string }) {
          if (args.token !== "a".repeat(64))
            throw new Error("Missing launch token");
          state.calls.push(command);
          if (command === "startup_begin") {
            state.painted =
              document.querySelector(".spinner")!.getBoundingClientRect()
                .width > 0;
            return;
          }
          if (command === "startup_status") return { ...state };
          throw new Error("Unexpected backend call");
        },
      },
    });
  });
  await page.goto("/startup.html");
  await expect(page.locator("main")).toHaveAttribute(
    "data-phase",
    "environment",
  );
  await page.evaluate(() => document.fonts.ready);
  expect(
    await page
      .locator("#logo")
      .evaluate((element) => (element as HTMLImageElement).naturalWidth),
  ).toBeGreaterThan(0);
}
async function update(page: Page, state: Partial<StartupState>) {
  await page.evaluate(
    (next) =>
      Object.assign((window as unknown as StartupWindow).__startupTest, next),
    state,
  );
}
async function geometry(page: Page) {
  return page.evaluate(() => {
    const rect = (selector: string) => {
      const { x, y, width, height } = document
        .querySelector(selector)!
        .getBoundingClientRect();
      return { x, y, width, height };
    };
    return {
      main: rect("main"),
      brand: rect("h1"),
      logo: rect("#logo"),
      viewport: { width: innerWidth, height: innerHeight },
      document: {
        width: document.documentElement.scrollWidth,
        height: document.documentElement.scrollHeight,
      },
    };
  });
}

test("loading paints before assembly and follows actual stages accessibly", async ({
  page,
}) => {
  await open(page);
  await expect(page.getByRole("status")).toContainText("Preparing application");
  expect(
    await page.evaluate(
      () => (window as unknown as StartupWindow).__startupTest.painted,
    ),
  ).toBe(true);
  await update(page, { phase: "runtime" });
  await expect(page.getByRole("status")).toContainText("Starting and checking");
  await update(page, { phase: "workspace", locale: "es" });
  await expect(page.getByRole("status")).toContainText(
    "Abriendo el espacio de trabajo",
  );
  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  await update(page, { failure: { code: "manager_unavailable" } });
  await expect(page.getByRole("alert")).toContainText("manager_unavailable");
  await expect(page.locator("main")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator(".spinner")).toBeHidden();
  await expect(page.getByRole("status")).toContainText(
    "No se ha podido iniciar",
  );
});

for (const screen of [
  { name: "desktop", width: 480, height: 300, touch: false },
  { name: "workspace", width: 1440, height: 1050, touch: false },
  { name: "phone", width: 320, height: 568, touch: true },
  { name: "landscape", width: 568, height: 240, touch: true },
]) {
  test.describe(screen.name, () => {
    test.use({
      viewport: { width: screen.width, height: screen.height },
      hasTouch: screen.touch,
      isMobile: screen.touch,
    });
    for (const colorScheme of ["light", "dark"] as const) {
      test(`stable centered loading and elided failures in ${colorScheme}`, async ({
        page,
      }, testInfo) => {
        await page.emulateMedia({ colorScheme });
        await open(page);
        const initial = await geometry(page);
        expect(initial.document).toEqual(initial.viewport);
        expect(initial.main.x + initial.main.width / 2).toBeCloseTo(
          initial.viewport.width / 2,
        );
        expect(initial.main.y + initial.main.height / 2).toBeCloseTo(
          initial.viewport.height / 2,
        );
        expect(initial.logo.x + initial.logo.width / 2).toBeCloseTo(
          initial.viewport.width / 2,
        );
        expect(initial.main.y).toBeGreaterThanOrEqual(0);
        expect(initial.main.y + initial.main.height).toBeLessThanOrEqual(
          initial.viewport.height,
        );
        await expect(page.locator("html")).toHaveAttribute(
          "data-scheme",
          colorScheme,
        );
        for (const locale of ["en", "es", "ca", "hu"]) {
          for (const phase of ["environment", "runtime", "workspace"]) {
            await update(page, { locale, phase });
            await expect(page.locator("main")).toHaveAttribute(
              "data-phase",
              phase,
            );
            await expect(page.locator("html")).toHaveAttribute("lang", locale);
            expect(await geometry(page)).toEqual(initial);
            // Localized status stays accessible without painting text.
            expect(
              await page.locator("#status").evaluate((element) => ({
                clip: getComputedStyle(element).clipPath,
                position: getComputedStyle(element).position,
              })),
            ).toEqual({ clip: "inset(50%)", position: "absolute" });
          }
        }
        await page.screenshot({ path: testInfo.outputPath("loading.png") });
        const code = "startup_failure_".repeat(80);
        await update(page, { failure: { code } });
        const failure = page.getByRole("alert");
        await expect(failure).toContainText(code);
        expect(await geometry(page)).toEqual(initial);
        expect(
          await failure.evaluate((element) => ({
            clipped: element.scrollWidth > element.clientWidth,
            ellipsis: getComputedStyle(element).textOverflow,
            lines: getComputedStyle(element).whiteSpace,
            title: element.getAttribute("title") === element.textContent,
          })),
        ).toEqual({
          clipped: true,
          ellipsis: "ellipsis",
          lines: "nowrap",
          title: true,
        });
        await page.keyboard.press("Tab");
        await expect(failure).toBeFocused();
        await page.evaluate(engine);
        const violations = await page.evaluate(async () => {
          const axe = (window as unknown as { axe: typeof import("axe-core") })
            .axe;
          return (await axe.run()).violations;
        });
        expect(violations).toEqual([]);
        await page.screenshot({ path: testInfo.outputPath("failure.png") });
      });
    }
  });
}

test("reduced motion keeps a static loading indicator", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page);
  await expect(page.locator(".spinner")).toBeVisible();
  expect(
    await page
      .locator(".spinner")
      .evaluate((element) => getComputedStyle(element).animationName),
  ).toBe("none");
});

test("startup transport failure leaves a readable error", async ({ page }) => {
  await page.addInitScript(() => {
    Object.assign(window, {
      isTauri: true,
      __CADRUMO_SHELL__: { token: "b".repeat(64) },
      __TAURI_INTERNALS__: {
        invoke: () => Promise.reject(new Error("Disconnected")),
      },
    });
  });
  await page.goto("/startup.html");
  await expect(page.getByRole("alert")).toContainText(
    "connection was interrupted",
  );
  await expect(page.locator("main")).toHaveAttribute("aria-busy", "false");
});
