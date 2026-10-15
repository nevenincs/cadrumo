import { expect, test } from "@playwright/test";

test("loading page paints before assembly and follows actual startup stages", async ({
  page,
}, testInfo) => {
  await page.addInitScript(() => {
    const state = {
      phase: "environment",
      locale: "en",
      failure: null as { code: string } | null,
      calls: [] as string[],
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
  await expect(page.getByRole("status")).toContainText("Preparing application");
  expect(
    await page.evaluate(
      () =>
        (window as unknown as { __startupTest: { painted: boolean } })
          .__startupTest.painted,
    ),
  ).toBe(true);
  await page.evaluate(() =>
    Object.assign(
      (window as unknown as { __startupTest: object }).__startupTest,
      { phase: "runtime" },
    ),
  );
  await expect(page.getByRole("status")).toContainText("Starting and checking");
  await page.setViewportSize({ width: 480, height: 300 });
  await page.screenshot({ path: testInfo.outputPath("startup.png") });
  await expect(page.locator('[data-phase="environment"]')).toHaveAttribute(
    "data-complete",
    "",
  );
  await page.evaluate(() =>
    Object.assign(
      (window as unknown as { __startupTest: object }).__startupTest,
      { phase: "workspace", locale: "es" },
    ),
  );
  await expect(page.getByRole("status")).toContainText(
    "Abriendo el espacio de trabajo",
  );
  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  await page.evaluate(() =>
    Object.assign(
      (window as unknown as { __startupTest: object }).__startupTest,
      { failure: { code: "manager_unavailable" } },
    ),
  );
  await expect(page.getByRole("alert")).toContainText("manager_unavailable");
  await expect(page.locator("main")).toHaveAttribute("aria-busy", "false");
  await expect(page.getByRole("status")).toContainText(
    "No se ha podido iniciar",
  );
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
