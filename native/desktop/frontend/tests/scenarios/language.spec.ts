import { expect, test, type Page } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";

async function settings(page: Page) {
  await page
    .getByRole("button", { name: label("desktop.rail.settings"), exact: true })
    .click();
  return page.getByRole("combobox", {
    name: label("desktop.settings.language"),
  });
}

async function settleRendering(page: Page) {
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
}

test("external canonical updates reach settings, palette and docs; older observations are refused", async ({
  page,
}) => {
  await seedLayout(page, { layout: { docsShown: true, agentShown: false } });
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await settings(page);
  await page.evaluate(() =>
    window.__scenarioLanguage!.publish({
      language: "es",
      persisted: true,
      profile: "Demo profile",
      revision: 10,
    }),
  );
  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  await expect(
    page.getByRole("combobox", {
      name: label("desktop.settings.language", {}, "es"),
    }),
  ).toHaveValue("es");
  await expect(
    page.frameLocator(".docs-frame").locator("html"),
  ).toHaveAttribute("lang", "es");
  await page.evaluate(() =>
    window.__scenarioLanguage!.publish({
      language: "hu",
      persisted: true,
      profile: "Demo profile",
      revision: 9,
    }),
  );
  await settleRendering(page);
  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  await page.keyboard.press("Escape");
  await page.keyboard.press("Control+k");
  await expect(
    page.getByRole("dialog").getByRole("combobox", {
      name: label("desktop.settings.language", {}, "es"),
    }),
  ).toHaveValue("es");
  expect(
    await page.evaluate(() =>
      (window.__scenarioHostCalls ?? []).filter((call) =>
        call.startsWith("language.set"),
      ),
    ),
  ).toEqual([]);
});

test("a previous account's delayed write response cannot replace the new account language", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  const choice = await settings(page);
  await page.evaluate(() => window.__scenarioLanguage!.deferNextSet());
  await choice.selectOption("es");
  await expect(choice).toBeDisabled();
  await page.evaluate(() =>
    window.__scenarioLanguage!.switchAccount("Other profile", "ca"),
  );
  await expect(page.locator("html")).toHaveAttribute("lang", "ca");
  await settleRendering(page);
  await page.evaluate(() =>
    window.__scenarioLanguage!.completeSet({
      language: "es",
      persisted: true,
      profile: "Demo profile",
      revision: 100,
    }),
  );
  await settleRendering(page);
  await expect(page.locator("html")).toHaveAttribute("lang", "ca");
  await expect(
    page.getByRole("combobox", {
      name: label("desktop.settings.language", {}, "ca"),
    }),
  ).toHaveValue("ca");
});

test("a refused write keeps the canonical language and reports the failure", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  const choice = await settings(page);
  await page.evaluate(() => window.__scenarioLanguage!.refuseNextSet());
  await choice.selectOption("hu");
  await expect(page.getByRole("alert")).toContainText("language_change_failed");
  await expect(choice).toHaveValue("en");
  await expect(choice).toBeEnabled();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  expect(
    await page.evaluate(() =>
      (window.__scenarioHostCalls ?? []).filter((call) =>
        call.startsWith("language.set"),
      ),
    ),
  ).toEqual(["language.set hu"]);
});

test("a cached previous profile observation is refused and a fresh current profile update clears failure", async ({
  page,
}) => {
  await seedLayout(page, { layout: { docsShown: true, agentShown: false } });
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await settings(page);
  await page.evaluate(() =>
    window.__scenarioLanguage!.publish({
      language: "hu",
      persisted: true,
      profile: "Demo profile",
      revision: 10,
    }),
  );
  await expect(page.locator("html")).toHaveAttribute("lang", "hu");
  await page.evaluate(() => {
    window.__scenarioLanguage!.cacheNextObservation({
      language: "es",
      persisted: true,
      profile: "Demo profile",
      revision: 100,
    });
    window.__scenarioLanguage!.refuseNextRead();
    window.__scenarioLanguage!.switchAccount("Other profile", "ca");
  });
  await expect(page.getByRole("alert")).toContainText("language_change_failed");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(
    page.frameLocator(".docs-frame").locator("html"),
  ).toHaveAttribute("lang", "en");
  await page.evaluate(() =>
    window.__scenarioLanguage!.publish({
      language: "ca",
      persisted: true,
      profile: "Other profile",
      revision: 12,
    }),
  );
  await expect(page.locator("html")).toHaveAttribute("lang", "ca");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(
    page.frameLocator(".docs-frame").locator("html"),
  ).toHaveAttribute("lang", "ca");

  await page.evaluate(() => window.__scenarioLanguage!.refuseNextSet());
  await page
    .getByRole("combobox", {
      name: label("desktop.settings.language", {}, "ca"),
    })
    .selectOption("es");
  await expect(page.getByRole("alert")).toContainText("language_change_failed");
  await page.evaluate(() => {
    const controls = window.__scenarioLanguage!;
    controls.publish({
      language: "hu",
      persisted: true,
      profile: "Other profile",
      revision: 11,
    });
    controls.publish({
      language: "ca",
      persisted: true,
      profile: "Other profile",
      revision: 12,
    });
    controls.publish({
      language: "es",
      persisted: true,
      profile: "Demo profile",
      revision: 100,
    });
  });
  await settleRendering(page);
  await expect(page.getByRole("alert")).toContainText("language_change_failed");
  await expect(page.locator("html")).toHaveAttribute("lang", "ca");
  await page.evaluate(() =>
    window.__scenarioLanguage!.publish({
      language: "hu",
      persisted: true,
      profile: "Other profile",
      revision: 13,
    }),
  );
  await expect(page.locator("html")).toHaveAttribute("lang", "hu");
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("all four languages remain selectable without bundled documentation", async ({
  page,
}) => {
  await page.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&docs=none",
  );
  const choice = await settings(page);
  expect(
    await choice
      .locator("option")
      .evaluateAll((options) =>
        options.map((option) => (option as HTMLOptionElement).value).sort(),
      ),
  ).toEqual(["ca", "en", "es", "hu"]);
  for (const language of ["es", "ca", "hu", "en"]) {
    await page
      .getByRole("combobox", {
        name: label(
          "desktop.settings.language",
          {},
          (await page.locator("html").getAttribute("lang")) ?? "en",
        ),
      })
      .selectOption(language);
    await expect(page.locator("html")).toHaveAttribute("lang", language);
  }
  await expect(page.locator(".docs-frame")).toHaveCount(0);
});

test("settings, palette and docs share the language without restarting terminals", async ({
  page,
}) => {
  await seedLayout(page, {
    prefs: { language: "hu" },
    layout: { docsShown: true, agentShown: false },
  });
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const terminalStarts = await page.evaluate(
    () =>
      (window.__scenarioHostCalls ?? []).filter((call) =>
        call.startsWith("openTerminal tui"),
      ).length,
  );
  await expect
    .poll(() =>
      page.evaluate(() => {
        const stored = JSON.parse(
          localStorage.getItem("cadrumo-shell-layout") ?? "{}",
        );
        return Object.hasOwn(stored.prefs ?? {}, "language");
      }),
    )
    .toBe(false);
  const frame = page.frameLocator(".docs-frame");
  await frame.locator("#internal").click();
  await expect
    .poll(() =>
      page.frames().some((entry) => entry.url().includes("/guide.html")),
    )
    .toBe(true);
  await frame.locator("html").evaluate(() => {
    history.replaceState(
      null,
      "",
      `${location.pathname}${location.search}#kept`,
    );
  });
  await page
    .getByRole("button", { name: label("desktop.rail.settings"), exact: true })
    .click();
  await page
    .getByRole("combobox", { name: label("desktop.settings.language") })
    .selectOption("es");
  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  await expect(frame.locator("html")).toHaveAttribute("lang", "es");
  await expect(page.locator(".docs-frame")).toBeVisible();
  await expect
    .poll(() =>
      page
        .frames()
        .find((entry) => entry.url().includes("/es/guide.html"))
        ?.url(),
    )
    .toContain("#kept");
  await page.keyboard.press("Escape");
  await page.keyboard.press("Control+k");
  const palette = page.getByRole("dialog");
  await expect(
    palette.getByRole("combobox", {
      name: label("desktop.settings.language", {}, "es"),
    }),
  ).toHaveValue("es");
  await palette
    .getByRole("combobox", {
      name: label("desktop.settings.language", {}, "es"),
    })
    .selectOption("ca");
  await expect(page.locator("html")).toHaveAttribute("lang", "ca");
  await page.keyboard.press("Escape");
  await frame.locator('a.cadrumo-header-lang-item[lang="hu"]').click();
  await expect(page.locator("html")).toHaveAttribute("lang", "hu");
  await expect(frame.locator("html")).toHaveAttribute("lang", "hu");
  const calls = await page.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls.filter((call) => call.startsWith("language.set"))).toEqual([
    "language.set es",
    "language.set ca",
    "language.set hu",
  ]);
  expect(
    calls.filter((call) => call.startsWith("openTerminal tui")),
  ).toHaveLength(terminalStarts);
});
