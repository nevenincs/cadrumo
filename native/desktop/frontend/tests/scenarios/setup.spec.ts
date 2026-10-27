import { expect, test, type Locator, type Page } from "@playwright/test";
import { scenarioOnly, send, settled, toolRow } from "../support/agent";
import { label } from "../support/strings";

// Component setup: the browser and the local AI (its program and models, one
// item), and, apart from setup, the profile's Google account. The fixture
// host stands in for the desktop host's commands, with no latency, so each
// test moves a setup on itself through `window.__scenarioSetup`. The dialog
// opens once per launch while setup is unfinished, never holds the window,
// leads with one summary and one action, keeps each component's detail in a
// closed disclosure, and words every code the host sends from its own
// strings: no closed value, code or internal name reaches the screen.

type Controls = {
  readRows(): void;
  step(): void;
  retry(attempt: number, delaySeconds: number): void;
  fail(category: string): void;
  interrupt(): void;
  finishGoogle(succeeded: boolean): void;
};

/** Closed values and internal names that must never reach the screen. */
const INTERNAL = [
  "absent",
  "provisioning",
  "verifying",
  "needs_person",
  "not_in_this_build",
  "damaged_download",
  "host_unreachable",
  "blocked_by_network",
  "disk_full",
  "interrupted",
  "plan_changed",
  "not_enough_space",
  "nothing_to_do",
  "not_pending",
  "not_cancellable",
  "not_signed_in",
  "signed_out",
  "local_ai",
  "model_runtime",
  "local_model",
  "plan_digest",
  "operation_id",
  "set_up",
  "try_again",
  "check_again",
  "provision",
  "Playwright",
  "headless",
  "digest",
];

/** The fixture's plan: the browser's 180 MB and the local AI's 3.4 GB. */
const PLAN_SIZE = "3.6 GB";
/** The same plan once it has grown by 100 MB an entry. */
const GROWN_SIZE = "3.8 GB";

async function open(target: Page, setup: string, scenario = "signed-in") {
  await target.goto(
    `/scenarios.html?scenario=${scenario}&latency=0&bar=off&setup=${setup}`,
  );
}

const dialog = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.setup.title") });

/** The browser's own setup flow. */
const browserDialog = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.setup.browser_title") });

const hostCalls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

/** Calls one of the fixture's controls in the page. */
const act = <Name extends keyof Controls>(
  target: Page,
  name: Name,
  ...values: Parameters<Controls[Name]>
) =>
  target.evaluate(
    ([called, given]) => {
      const setup = (window as unknown as { __scenarioSetup?: Controls })
        .__scenarioSetup;
      if (!setup) throw new Error("no setup controls");
      (setup[called] as (...args: unknown[]) => void)(...given);
    },
    [name, values] as [Name, unknown[]],
  );

/** Moves a running setup on by `count` steps. */
async function steps(target: Page, count: number) {
  for (let index = 0; index < count; index += 1) await act(target, "step");
}

async function noInternalWords(target: Page) {
  const text = await target.locator("body").innerText();
  for (const word of INTERNAL)
    expect(text, `shows "${word}"`).not.toMatch(
      new RegExp(`(^|[^A-Za-z])${word}([^A-Za-z]|$)`),
    );
}

/** Opens the dialog's per-component detail, which starts closed. */
async function details(shown: Locator) {
  const disclosure = shown.locator("[data-setup-details]");
  await expect(disclosure).not.toHaveAttribute("open", "");
  await disclosure.getByText(label("desktop.setup.details")).click();
  await expect(disclosure).toHaveAttribute("open", "");
  return disclosure;
}

async function openSettings(target: Page) {
  await target.locator("[data-rail=settings]").click();
  const settings = target.getByRole("dialog", {
    name: label("desktop.settings.title"),
  });
  await expect(settings).toBeVisible();
  return settings;
}

async function palette(target: Page, name: string) {
  await target.keyboard.press("Control+KeyK");
  const box = target.getByRole("combobox", {
    name: label("desktop.palette.label"),
  });
  await box.fill(name);
  return target.getByRole("listbox").getByRole("option", { name });
}

const approveButton = (shown: Locator, size: string) =>
  shown.getByRole("button", {
    name: label("desktop.setup.approve_at_least", { size }),
  });

async function startAndApprove(target: Page) {
  const shown = dialog(target);
  await shown
    .getByRole("button", { name: label("desktop.setup.start"), exact: true })
    .click();
  await approveButton(shown, PLAN_SIZE).click();
  await expect(shown).toContainText(label("desktop.setup.lead_running"));
  return shown;
}

test("an unfinished setup opens one summary with one action, and Settings leads back to it", async ({
  page: target,
}) => {
  await open(target, "fresh");
  const shown = dialog(target);
  await expect(shown).toBeVisible();
  await expect(shown.locator("[data-setup-summary]")).toHaveText(
    label("desktop.setup.summary_incomplete"),
  );
  // One primary action; the components wait in a closed disclosure.
  await expect(
    shown.getByRole("button", {
      name: label("desktop.setup.start"),
      exact: true,
    }),
  ).toHaveCount(1);
  await expect(shown.locator("[data-setup-row]").first()).toBeHidden();
  await noInternalWords(target);
  await shown
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await expect(shown).toBeHidden();
  const rail = target.locator("[data-rail=settings]");
  await expect(rail.locator("[data-pin=attention]")).toHaveCount(1);
  await expect(rail).toHaveAccessibleName(
    new RegExp(label("desktop.setup.rail_incomplete")),
  );
  // Settings carries no component list, only the one line into setup.
  const settings = await openSettings(target);
  await expect(settings.locator("[data-setup-row]")).toHaveCount(0);
  const advisory = settings.locator("[data-setup-advisory=incomplete]");
  await expect(advisory).toHaveText(label("desktop.setup.advisory_incomplete"));
  await advisory.click();
  await expect(dialog(target)).toBeVisible();
  await dialog(target)
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  // The window is not held: the documentation and the palette still work.
  await target.locator("[data-rail=docs]").click();
  await target.keyboard.press("Control+KeyK");
  await expect(
    target.getByRole("combobox", { name: label("desktop.palette.label") }),
  ).toBeVisible();
});

test("the local AI is one component, and each component says its state once", async ({
  page: target,
}) => {
  await open(target, "fresh");
  const shown = dialog(target);
  const disclosure = await details(shown);
  const rows = disclosure.locator("[data-setup-row]");
  await expect(rows).toHaveCount(2);
  await expect(disclosure.locator("[data-setup-row=browser]")).toContainText(
    "Browser for the tax agency website",
  );
  await expect(disclosure.locator("[data-setup-row=local_ai]")).toContainText(
    "Local AI",
  );
  await expect(shown).not.toContainText("Local AI model");
  for (const row of await rows.all()) {
    const sentence = (
      await row.locator("[data-setup-sentence]").innerText()
    ).trim();
    const text = await row.innerText();
    expect(text.split(sentence).length - 1, `"${sentence}" once`).toBe(1);
    expect(text.match(/not set up/gi)?.length ?? 0).toBeLessThanOrEqual(1);
  }
  await noInternalWords(target);
});

test("the plan is summed up, its detail stays closed, and approving runs every component in order", async ({
  page: target,
}) => {
  await open(target, "fresh");
  const shown = dialog(target);
  await shown
    .getByRole("button", { name: label("desktop.setup.start"), exact: true })
    .click();
  await expect(shown).toContainText(label("desktop.setup.lead_review"));
  await expect(shown.locator("[data-setup-plan-size]")).toHaveText(
    label("desktop.setup.plan_size_at_least", { size: PLAN_SIZE }),
  );
  // What approving also agrees to is said without opening anything.
  await expect(shown).toContainText(
    label("desktop.setup.plan_outside_program"),
  );
  await expect(shown.locator("[data-setup-plan]").first()).toBeHidden();
  const disclosure = await details(shown);
  await expect(disclosure.locator("[data-setup-plan]")).toHaveCount(2);
  const localAi = disclosure.locator("[data-setup-plan=local_ai]");
  await expect(localAi.locator("[data-setup-part]")).toHaveCount(5);
  await expect(localAi.locator("[data-setup-part=program]")).toContainText(
    label("desktop.setup.size_unknown"),
  );
  await expect(disclosure.locator("[data-setup-plan=browser]")).toContainText(
    label("desktop.setup.plan_from", { hosts: "cdn.playwright.dev" }),
  );
  const approve = approveButton(shown, PLAN_SIZE);
  await expect(approve).toBeEnabled();
  await noInternalWords(target);
  await approve.click();
  await expect(shown).toContainText(label("desktop.setup.lead_running"));
  await expect(
    target.locator("[data-rail=settings] [data-pin=busy]"),
  ).toHaveCount(1);

  // One overall figure leads; each component's own progress is in the detail.
  const overall = shown.locator("[data-setup-overall]");
  await expect(
    overall.getByRole("progressbar", {
      name: label("desktop.setup.overall_progress"),
    }),
  ).toBeVisible();
  await steps(target, 2);
  await expect(overall).toContainText(
    label("desktop.setup.progress_item", {
      index: 1,
      count: 2,
      name: "Browser for the tax agency website",
      step: label("desktop.setup.step_downloading"),
    }),
  );
  await act(target, "retry", 2, 8);
  await expect(overall).toContainText(
    label("desktop.setup.retry", { attempt: 2, seconds: 8 }),
  );
  const running = await details(shown);
  const browser = running.locator("[data-setup-progress=browser]");
  await expect(browser.getByRole("progressbar")).toBeVisible();
  await steps(target, 5);
  await expect(browser).toContainText(label("desktop.setup.result_done"));
  // The local AI installs its program, then fetches its models.
  await steps(target, 2);
  await expect(overall).toContainText(
    label("desktop.setup.progress_item", {
      index: 2,
      count: 2,
      name: "Local AI",
      step: label("desktop.setup.step_installing"),
    }),
  );
  await steps(target, 20);
  await expect(shown).toContainText(label("desktop.setup.outcome_completed"));
  await expect(
    target.getByRole("status").filter({
      hasText: label("desktop.setup.toast_done"),
    }),
  ).toBeVisible();
  // Everything Cadrumo needs is set up: the Google account is not part of it.
  await expect(target.locator("[data-rail=settings] [data-pin]")).toHaveCount(
    0,
  );
  await noInternalWords(target);
});

test("a plan turned down downloads nothing", async ({ page: target }) => {
  await open(target, "fresh");
  const shown = dialog(target);
  await shown
    .getByRole("button", { name: label("desktop.setup.start"), exact: true })
    .click();
  await shown
    .getByRole("button", { name: label("desktop.setup.reject") })
    .click();
  await expect(shown).toContainText(label("desktop.setup.outcome_rejected"));
  expect(
    await target.evaluate(() => window.__scenarioHostCalls ?? []),
  ).toContain("setup.answer reject");
});

test("a running setup can be cancelled and keeps what it downloaded", async ({
  page: target,
}) => {
  await open(target, "fresh");
  const shown = await startAndApprove(target);
  await steps(target, 1);
  await shown
    .getByRole("button", { name: label("desktop.setup.cancel") })
    .click();
  await expect(shown).toContainText(label("desktop.setup.cancelling"));
  await steps(target, 1);
  await expect(shown).toContainText(label("desktop.setup.outcome_cancelled"));
  await expect(
    target.getByRole("status").filter({
      hasText: label("desktop.setup.toast_cancelled"),
    }),
  ).toBeVisible();
});

test("while setup runs, Settings says so and leads back to it", async ({
  page: target,
}) => {
  await open(target, "fresh");
  const shown = await startAndApprove(target);
  await shown
    .getByRole("button", { name: label("desktop.setup.hide") })
    .click();
  const settings = await openSettings(target);
  const advisory = settings.locator("[data-setup-advisory=running]");
  await expect(advisory).toHaveText(label("desktop.setup.advisory_running"));
  await advisory.click();
  await expect(dialog(target)).toContainText(
    label("desktop.setup.lead_running"),
  );
});

test("a plan that changed before its approval is shown again for a new approval", async ({
  page: target,
}) => {
  await open(target, "plan_changes");
  const shown = dialog(target);
  await shown
    .getByRole("button", { name: label("desktop.setup.start"), exact: true })
    .click();
  await approveButton(shown, PLAN_SIZE).click();
  await expect(shown).toContainText(
    label("desktop.setup.refused_plan_changed"),
  );
  const again = approveButton(shown, GROWN_SIZE);
  await expect(again).toBeVisible();
  await again.click();
  await expect(shown).toContainText(label("desktop.setup.lead_running"));
  await noInternalWords(target);
});

test("too little free space is said before anything is downloaded", async ({
  page: target,
}) => {
  await open(target, "low_space");
  const shown = dialog(target);
  await shown
    .getByRole("button", { name: label("desktop.setup.start"), exact: true })
    .click();
  await expect(shown.getByRole("alert")).toContainText(
    label("desktop.setup.space_short"),
  );
  await expect(approveButton(shown, PLAN_SIZE)).toBeDisabled();
  await noInternalWords(target);
});

test("offline, the items that need the network say so and offer a check", async ({
  page: target,
}) => {
  await open(target, "offline");
  const shown = dialog(target);
  const disclosure = await details(shown);
  const browser = disclosure.locator("[data-setup-row=browser]");
  await expect(browser).toContainText(label("desktop.setup.blocked.offline"));
  await browser
    .getByRole("button", { name: label("desktop.setup.action.check_again") })
    .click();
  expect(
    await target.evaluate(() => window.__scenarioHostCalls ?? []),
  ).toContain("setup.verify browser");
  await noInternalWords(target);
});

test("an interrupted setup resumes without a second approval while its plan is unchanged", async ({
  page: target,
}) => {
  await open(target, "fresh");
  const shown = await startAndApprove(target);
  await steps(target, 3);
  await act(target, "interrupt");
  await expect(shown).toContainText(label("desktop.setup.outcome_interrupted"));
  await shown
    .getByRole("button", { name: label("desktop.setup.resume") })
    .click();
  await expect(shown).toContainText(label("desktop.setup.lead_running"));
  await expect(shown.locator("[data-setup-plan]")).toHaveCount(0);
  expect(
    await target.evaluate(() => window.__scenarioHostCalls ?? []),
  ).toContain("setup.start all resume");
});

test("an interrupted setup whose plan changed asks for approval again", async ({
  page: target,
}) => {
  await open(target, "resume_changes");
  const shown = await startAndApprove(target);
  await steps(target, 1);
  await act(target, "interrupt");
  await shown
    .getByRole("button", { name: label("desktop.setup.resume") })
    .click();
  await expect(shown).toContainText(label("desktop.setup.lead_review"));
  await expect(approveButton(shown, GROWN_SIZE)).toBeVisible();
});

test("Google authentication belongs to the profile menu, apart from Settings and setup", async ({
  page: target,
}) => {
  await open(target, "google_signed_out", "google-account");
  // Everything is set up: no dialog, no badge, no setup line.
  await expect(dialog(target)).toHaveCount(0);
  await expect(target.locator("[data-rail=settings] [data-pin]")).toHaveCount(
    0,
  );
  const settings = await openSettings(target);
  await expect(settings.locator("[data-setup-advisory]")).toHaveCount(0);
  await expect(settings.locator("[data-google-account]")).toHaveCount(0);
  await target.keyboard.press("Escape");
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  const google = target.getByRole("region", {
    name: label("desktop.google.title"),
  });
  await expect(google).toContainText(label("desktop.google.signed_out"));
  await google
    .getByRole("menuitem", { name: label("desktop.google.sign_in_label") })
    .click();
  await expect(google).toContainText(label("desktop.google.waiting"));
  await act(target, "finishGoogle", true);
  await expect(google).toContainText(
    label("desktop.google.signed_in", { email: "persona@example.com" }),
  );
  await google
    .getByRole("menuitem", { name: label("desktop.google.sign_out_label") })
    .click();
  await expect(google).toContainText(label("desktop.google.signed_out"));
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls).toContain("google.signIn");
  expect(calls).toContain("google.signOut");
  await noInternalWords(target);
});

test("a Google sign-in that does not finish says so on the account's row", async ({
  page: target,
}) => {
  await open(target, "google_signed_out", "google-account");
  const settings = await openSettings(target);
  await expect(settings.locator("[data-google-account]")).toHaveCount(0);
  await target.keyboard.press("Escape");
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  const google = target.getByRole("region", {
    name: label("desktop.google.title"),
  });
  await google
    .getByRole("menuitem", { name: label("desktop.google.sign_in_label") })
    .click();
  await act(target, "finishGoogle", false);
  await expect(google).toContainText(
    label("desktop.setup.failure.needs_sign_in"),
  );
  await expect(
    google.getByRole("menuitem", {
      name: label("desktop.google.sign_in_label"),
    }),
  ).toBeEnabled();
});

test("Cmd+K authenticates with Google, and setup offers no Google action", async ({
  page: target,
}) => {
  await open(target, "google_signed_out", "google-account");
  await expect(
    await palette(target, label("desktop.setup.palette_open")),
  ).toHaveCount(1);
  await target.keyboard.press("Escape");
  const google = await palette(target, label("desktop.google.palette_sign_in"));
  await expect(google).toHaveCount(1);
  await google.click();
  expect(
    await target.evaluate(() => window.__scenarioHostCalls ?? []),
  ).toContain("google.signIn");
  // No setup action names Google.
  await target.keyboard.press("Control+KeyK");
  await target
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill("Google");
  await expect(
    target
      .getByRole("listbox")
      .getByRole("option")
      .filter({ hasText: /set up|setup/i }),
  ).toHaveCount(0);
});

test("the palette offers the setup actions and runs them", async ({
  page: target,
}) => {
  await open(target, "partial");
  const shown = dialog(target);
  await shown
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await expect(
    await palette(target, label("desktop.setup.palette_cancel")),
  ).toHaveCount(0);
  await target.keyboard.press("Escape");
  const option = await palette(target, label("desktop.setup.palette_local_ai"));
  await option.click();
  await expect(shown).toContainText(label("desktop.setup.lead_review"));
  const disclosure = await details(shown);
  await expect(disclosure.locator("[data-setup-plan]")).toHaveCount(1);
  await shown
    .getByRole("button", { name: label("desktop.setup.reject") })
    .click();
  await shown
    .getByRole("button", { name: label("desktop.setup.close") })
    .first()
    .click();
  const retry = await palette(target, label("desktop.setup.palette_retry"));
  await expect(retry).toHaveCount(1);
});

test("signed out, setup is nowhere to be found", async ({ page: target }) => {
  await open(target, "fresh", "signed-out");
  await expect(dialog(target)).toHaveCount(0);
  await expect(target.locator("[data-rail=settings] [data-pin]")).toHaveCount(
    0,
  );
  expect(
    (await target.evaluate(() => window.__scenarioHostCalls ?? [])).filter(
      (call) => call.startsWith("setup.") || call.startsWith("google."),
    ),
  ).toEqual([]);
});

test("Copy details puts the report on the clipboard", async ({
  page: target,
}) => {
  await open(target, "partial");
  await dialog(target)
    .getByRole("button", { name: label("desktop.setup.copy_details") })
    .click();
  await expect(
    target.getByRole("status").filter({
      hasText: label("desktop.toast.copied"),
    }),
  ).toBeVisible();
});

test("a local AI setup blocker leads to model settings without starting setup", async ({
  page: target,
}) => {
  await open(target, "hardware");
  await dialog(target)
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await (
    await palette(target, label("desktop.setup.palette_local_ai"))
  ).click();
  const prompt = target.getByRole("dialog", { name: "Local AI" });
  const sentence = "This computer does not have enough memory for this.";
  await expect(prompt).toContainText(sentence);
  expect((await prompt.innerText()).split(sentence).length - 1).toBe(1);
  await noInternalWords(target);
  // A different model may help; the setup blocker still grants no download.
  await expect(prompt.getByRole("button")).toHaveText([
    label("desktop.providers.local_models_title"),
    label("desktop.setup.close"),
  ]);
  await prompt
    .getByRole("button", {
      name: label("desktop.providers.local_models_title"),
    })
    .click();
  await expect(prompt).toBeHidden();
  await expect(
    target.locator('.pane-agent [data-slot="local-models"]'),
  ).toBeVisible();
  expect(
    await target.evaluate(() => window.__scenarioHostCalls ?? []),
  ).not.toContain("setup.start local_ai");
});

/** Opens the window with setup unfinished, puts its dialog away, and has the
 * agent call a tool the product refuses as `message` says. */
async function refusedTool(target: Page, message: string) {
  scenarioOnly("the scenario host refuses a tool when it is asked to");
  await open(target, "fresh");
  await dialog(target)
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await expect(dialog(target)).toBeHidden();
  await send(target, message);
  await settled(target);
}

const browserPrompt = (target: Page) =>
  target.getByRole("dialog", { name: "Browser for the tax agency website" });

test("a tool refused for a missing component opens that component's prompt once", async ({
  page: target,
}) => {
  await refusedTool(target, "Captura el censo, aunque falta el navegador.");
  const prompt = browserPrompt(target);
  await expect(prompt).toBeVisible();
  // The prompt says the component's state once: its own sentence.
  expect((await prompt.innerText()).match(/not set up/gi)?.length).toBe(1);
  await expect(toolRow(target, "aeat_capture_censo")).toContainText(
    label("desktop.agent.tool_failed"),
  );
  // It opened while the person was in the message field, and left the
  // keyboard there.
  // The modal prompt hides the column from the accessibility tree, so the
  // field is found by where it is rather than by its role.
  expect(
    await target.evaluate(
      () =>
        document.activeElement?.closest(".pane-agent") !== null &&
        document.activeElement?.matches("textarea, [contenteditable=true]"),
    ),
  ).toBe(true);
  // The refusal's code is the agent's to route by, never shown.
  await expect(target.locator("body")).not.toContainText(
    "operation_not_successful",
  );
  await expect(target.locator("body")).not.toContainText("operator.");
  await noInternalWords(target);
  await prompt
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await expect(prompt).toBeHidden();
  // Read again, the conversation does not raise the same refusal twice.
  await target.locator("[data-rail=docs]").click();
  await expect(prompt).toBeHidden();
  await expect(target.getByRole("dialog")).toHaveCount(0);
});

test("the prompt a refused tool opens leads into setting the component up", async ({
  page: target,
}) => {
  await refusedTool(target, "Captura el censo, aunque falta el navegador.");
  const prompt = browserPrompt(target);
  await expect(prompt).toBeVisible();
  // The host's own words for the row's button.
  await prompt.getByRole("button", { name: "Set up", exact: true }).click();
  await expect(prompt).toBeHidden();
  // The browser's own flow, planning the browser alone.
  const shown = browserDialog(target);
  await expect(shown).toBeVisible();
  await expect(shown.locator("[data-setup-plan]")).toHaveCount(1);
  await expect(shown.locator("[data-setup-plan=browser]")).toHaveCount(1);
  await expect(shown).not.toContainText("Local AI");
  expect(await hostCalls(target)).toContain("setup.start browser");
});

test("each new sync refused for the missing browser opens the prompt again", async ({
  page: target,
}) => {
  await refusedTool(target, "Captura el censo, aunque falta el navegador.");
  const prompt = browserPrompt(target);
  await expect(prompt).toBeVisible();
  await prompt
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await expect(prompt).toBeHidden();
  // Another call, refused the same way, is a refusal of its own.
  await send(target, "Sincroniza otra vez, aunque falta el navegador.");
  await settled(target);
  await expect(prompt).toBeVisible();
  await prompt
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await expect(prompt).toBeHidden();
  await target.locator("[data-rail=docs]").click();
  await expect(target.getByRole("dialog")).toHaveCount(0);
});

test("a refusal that arrives before the setup status is read opens its prompt once it is", async ({
  page: target,
}) => {
  scenarioOnly("the scenario host holds the first status read");
  await open(target, "unread");
  await send(target, "Captura el censo, aunque falta el navegador.");
  await settled(target);
  const prompt = browserPrompt(target);
  await expect(prompt).toBeHidden();
  await act(target, "readRows");
  await expect(prompt).toBeVisible();
  await expect(prompt).toContainText("Not set up yet.");
  // The prompt stands in for the dialog that opens once per launch.
  await expect(dialog(target)).toHaveCount(0);
});

test("a Censo pull that stops for the missing browser opens its prompt, each pull again", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=censo-browser-missing&latency=0&bar=off",
  );
  await dialog(target)
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await target
    .locator(".rail")
    .getByRole("button", { name: label("desktop.profile.title"), exact: true })
    .click();
  const band = target.getByRole("region", {
    name: label("desktop.profile.censo.band"),
    exact: true,
  });
  const pull = band.getByRole("button", {
    name: label("desktop.profile.censo.pull"),
    exact: true,
  });
  const prompt = browserPrompt(target);
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await pull.click();
    await expect(prompt).toBeVisible();
    await prompt
      .getByRole("button", { name: label("desktop.setup.not_now") })
      .click();
    await expect(prompt).toBeHidden();
    // The band still says the pull failed, beside the prompt it raised.
    await expect(band).toContainText(label("desktop.profile.censo.failed"));
  }
  await expect(target.locator("body")).not.toContainText("operator.");
});

test("the palette opens the browser's own flow, which sets up the browser alone", async ({
  page: target,
}) => {
  await open(target, "fresh");
  await dialog(target)
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  // Found by what a person looking for it types, too.
  await target.keyboard.press("Control+KeyK");
  await target
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill("chromium");
  await target
    .getByRole("listbox")
    .getByRole("option", { name: label("desktop.setup.palette_browser") })
    .click();
  const shown = browserDialog(target);
  await expect(shown).toBeVisible();
  await expect(shown).toContainText(label("desktop.setup.lead_review"));
  await expect(shown.locator("[data-setup-plan]")).toHaveCount(1);
  await expect(shown).not.toContainText("Local AI");
  expect(await hostCalls(target)).toContain("setup.start browser");
  expect(await hostCalls(target)).not.toContain("setup.start all");
  await shown
    .getByRole("button", {
      name: label("desktop.setup.approve_size", { size: "180 MB" }),
    })
    .click();
  await expect(shown.locator("[data-setup-overall]")).toContainText("1 of 1");
  await expect(shown).not.toContainText("Local AI");
  await steps(target, 8);
  await expect(shown).toContainText(label("desktop.setup.outcome_completed"));
  await expect(shown.locator("[data-setup-row=browser]")).toContainText(
    label("desktop.setup.state.ready"),
  );
  await expect(shown.locator("[data-setup-row=local_ai]")).toHaveCount(0);
  await noInternalWords(target);
});

test("the palette opens the browser's flow on a ready browser, to check it again", async ({
  page: target,
}) => {
  await open(target, "ready");
  await (await palette(target, label("desktop.setup.palette_browser"))).click();
  const shown = browserDialog(target);
  await expect(shown).toBeVisible();
  await expect(shown).toContainText(label("desktop.setup.browser_lead"));
  await expect(shown.locator("[data-setup-row=browser]")).toContainText(
    label("desktop.setup.state.ready"),
  );
  await expect(shown).not.toContainText("Local AI");
  await shown
    .getByRole("button", { name: label("desktop.setup.action.check_again") })
    .click();
  expect(await hostCalls(target)).toContain("setup.verify browser");
  expect(
    (await hostCalls(target)).filter((call) => call.startsWith("setup.start")),
  ).toEqual([]);
});

test("the browser's flow names a local AI setup that is running instead of showing it", async ({
  page: target,
}) => {
  await open(target, "fresh");
  await dialog(target)
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await (
    await palette(target, label("desktop.setup.palette_local_ai"))
  ).click();
  await approveButton(dialog(target), "3.4 GB").click();
  await expect(dialog(target)).toContainText(
    label("desktop.setup.lead_running"),
  );
  await dialog(target)
    .getByRole("button", { name: label("desktop.setup.hide") })
    .click();
  await (await palette(target, label("desktop.setup.palette_browser"))).click();
  const shown = browserDialog(target);
  await expect(shown).toBeVisible();
  await expect(shown).toContainText(
    label("desktop.setup.browser_other_running"),
  );
  await expect(shown).not.toContainText("Local AI");
  await expect(shown.locator("[data-setup-overall]")).toHaveCount(0);
  await expect(shown.locator("[data-setup-row=browser]")).toHaveCount(1);
  // Joining the running setup is not setting the browser up.
  expect(await hostCalls(target)).not.toContain("setup.start browser");
  await shown
    .getByRole("button", { name: label("desktop.setup.show_running") })
    .click();
  await expect(dialog(target)).toContainText(
    label("desktop.setup.lead_running"),
  );
});

test("Settings has a Browser section of its own that opens the browser's flow", async ({
  page: target,
}) => {
  await open(target, "partial");
  await dialog(target)
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  const settings = await openSettings(target);
  const section = settings.getByRole("region", {
    name: label("desktop.setup.item.browser"),
  });
  await expect(section).toContainText(label("desktop.setup.state.ready"));
  // Apart from the local AI, which keeps its own entry.
  await expect(section).not.toContainText("Local AI");
  await section
    .getByRole("button", { name: label("desktop.setup.browser_open") })
    .click();
  const shown = browserDialog(target);
  await expect(shown).toBeVisible();
  await expect(shown).not.toContainText("Local AI");
  await expect(shown).not.toContainText(
    label("desktop.setup.failure.damaged_download"),
  );
});

test("a tool refused for something setup does not recover opens nothing", async ({
  page: target,
}) => {
  await refusedTool(target, "Importa el extracto: rechazo ajeno.");
  await expect(toolRow(target, "ledger_import")).toContainText(
    label("desktop.agent.tool_failed"),
  );
  await expect(target.getByRole("dialog")).toHaveCount(0);
  await expect(target.locator("body")).not.toContainText("operator.");
});

test("a tool refusal whose recovery is malformed opens nothing", async ({
  page: target,
}) => {
  await refusedTool(target, "Captura el censo con un rechazo malformado.");
  await expect(toolRow(target, "aeat_capture_censo")).toContainText(
    label("desktop.agent.tool_failed"),
  );
  await expect(target.getByRole("dialog")).toHaveCount(0);
  await expect(target.locator("body")).not.toContainText(
    "OPERATION_NOT_SUCCESSFUL",
  );
});

test("Drive opens the profile folder and disappears when either account signs out", async ({
  page,
}) => {
  await open(page, "google_signed_out", "google-account");
  const drive = page.locator("[data-rail=drive]");
  await expect(drive).toHaveCount(0);
  await page
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await page
    .getByRole("menuitem", { name: label("desktop.google.sign_in_label") })
    .click();
  await expect(drive).toHaveCount(0);
  await act(page, "finishGoogle", true);
  await expect(drive).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: label("desktop.titlebar.profile_menu") }),
  ).toBeFocused();
  await drive.click();
  expect(await page.evaluate(() => window.__scenarioHostCalls ?? [])).toContain(
    "openExternal https://drive.google.com/drive/folders/profile-drive-folder",
  );
  await page
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await page
    .getByRole("menuitem", { name: label("desktop.google.sign_out_label") })
    .click();
  await expect(drive).toHaveCount(0);
  await page
    .getByRole("menuitem", { name: label("desktop.google.sign_in_label") })
    .click();
  await act(page, "finishGoogle", true);
  await expect(drive).toBeVisible();
  await page
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(drive).toHaveCount(0);
  await expect(page.locator("[data-google-account]")).toHaveCount(0);
});

test("Drive stays hidden without a usable folder and while Google authentication changes", async ({
  page,
}) => {
  await open(page, "ready", "google-account");
  const drive = page.locator("[data-rail=drive]");
  await expect(drive).toBeVisible();
  for (const google of [
    { state: "signed_in", drive_folder_id: null, stage: "idle" },
    { state: "unknown", drive_folder_id: null, stage: "idle" },
    {
      state: "signed_in",
      drive_folder_id: "../other?query=bad",
      stage: "idle",
    },
    {
      state: "signed_in",
      drive_folder_id: "profile-folder",
      stage: "signing_out",
    },
  ] as const) {
    await page.evaluate(
      (google) =>
        window.__scenarioSetup?.setGoogle({
          ...google,
          email: null,
          failure: null,
        }),
      google,
    );
    await expect(drive).toHaveCount(0);
  }
});

test("Google authentication supports keyboard navigation inside the profile menu", async ({
  page,
}) => {
  await open(page, "google_signed_out", "google-account");
  const trigger = page.getByRole("button", {
    name: label("desktop.titlebar.profile_menu"),
  });
  await trigger.focus();
  await page.keyboard.press("Enter");
  await page.keyboard.press("End");
  const signIn = page.getByRole("menuitem", {
    name: label("desktop.google.sign_in_label"),
  });
  await expect(signIn).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-google-account]")).toContainText(
    label("desktop.google.waiting"),
  );
  await expect(signIn).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
});
