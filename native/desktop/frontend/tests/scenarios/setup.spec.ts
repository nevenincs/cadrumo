import { expect, test, type Locator, type Page } from "@playwright/test";
import { scenarioOnly, send, settled, toolRow } from "../support/agent";
import { label } from "../support/strings";

// Component setup through the one provisioning panel: one row per element
// the host reports -- the browser, and the local AI as a dropdown holding
// its program and its model list -- each with its own status said once, its
// size, its own action, plan review, progress and cancel. Elements set up on
// their own and at the same time; closing the panel never stops one. Apart
// from setup, the profile's Google account. The fixture host stands in for
// the desktop host's commands, with no latency, so each test moves a setup
// on itself through `window.__scenarioSetup`. Every code the host sends is
// worded from the window's own strings: no closed value, code or internal
// name reaches the screen.

type Controls = {
  readRows(): void;
  step(item?: string): void;
  retry(attempt: number, delaySeconds: number): void;
  fail(category: string): void;
  interrupt(item?: string): void;
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

const BROWSER = "Browser for the tax agency website";
const LOCAL_AI = "Local AI";
const NOT_SET_UP = "Not set up yet.";
/** The fixture browser's download. */
const BROWSER_SIZE = "180 MB";

async function open(target: Page, setup: string, scenario = "signed-in") {
  await target.goto(
    `/scenarios.html?scenario=${scenario}&latency=0&bar=off&setup=${setup}`,
  );
}

const panel = (target: Page) =>
  target.getByRole("dialog", { name: label("desktop.setup.title") });
const browserRow = (target: Page) =>
  panel(target).locator('[data-setup-row="browser"]');
/** The local AI's dropdown element. */
const localAi = (target: Page) =>
  panel(target).locator('[data-setup-element="local_ai"]');
/** The local AI's program row, inside its open dropdown. */
const programRow = (target: Page) =>
  localAi(target).locator('[data-setup-row="local_ai"]');

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

/** Moves `item`'s running setup, or the first, on by `count` steps. */
async function steps(target: Page, count: number, item?: string) {
  for (let index = 0; index < count; index += 1)
    await act(target, "step", item);
}

/** Moves `item`'s setup on until `done` holds, within a bound. */
async function stepUntil(
  target: Page,
  item: string,
  done: () => Promise<boolean>,
) {
  for (let index = 0; index < 40 && !(await done()); index += 1)
    await act(target, "step", item);
  expect(await done()).toBe(true);
}

async function noInternalWords(target: Page) {
  const text = await target.locator("body").innerText();
  for (const word of INTERNAL)
    expect(text, `shows "${word}"`).not.toMatch(
      new RegExp(`(^|[^A-Za-z])${word}([^A-Za-z]|$)`),
    );
}

/** `text` appears exactly once in `scope`. */
async function once(scope: Locator, text: string) {
  expect(
    (await scope.innerText()).split(text).length - 1,
    `"${text}" once`,
  ).toBe(1);
}

async function palette(target: Page, name: string) {
  await target.keyboard.press("Control+KeyK");
  const box = target.getByRole("combobox", {
    name: label("desktop.palette.label"),
  });
  await box.fill(name);
  return target.getByRole("listbox").getByRole("option", { name });
}

const paletteItem = (name: string) =>
  label("desktop.setup.palette_item", { name });

async function closePanel(target: Page) {
  await panel(target)
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await expect(panel(target)).toBeHidden();
}

const setUpButton = (row: Locator) =>
  row.getByRole("button", {
    name: label("desktop.setup.action.set_up"),
    exact: true,
  });

const approveBrowser = (target: Page) =>
  browserRow(target).getByRole("button", {
    name: label("desktop.setup.approve_size", { size: BROWSER_SIZE }),
  });

async function openLocalAi(target: Page) {
  await localAi(target).getByRole("button", { name: LOCAL_AI }).click();
  await expect(programRow(target)).toBeVisible();
}

/** Starts the browser's setup and approves its plan. */
async function startBrowser(target: Page) {
  await setUpButton(browserRow(target)).click();
  await approveBrowser(target).click();
  await expect(browserRow(target).locator("[data-setup-progress]")).toHaveCount(
    1,
  );
}

test("an unfinished setup opens the panel once, one row per element, each status said once", async ({
  page: target,
}) => {
  await open(target, "fresh");
  await expect(panel(target)).toBeVisible();
  await expect(browserRow(target)).toContainText(BROWSER);
  await expect(localAi(target)).toContainText(LOCAL_AI);
  // Each element has its own action, its own size and its own status.
  await expect(setUpButton(browserRow(target))).toHaveCount(1);
  await expect(browserRow(target)).toContainText(BROWSER_SIZE);
  await once(browserRow(target), NOT_SET_UP);
  await once(localAi(target), NOT_SET_UP);
  // No summary or primary action speaks for every element at once.
  await expect(
    panel(target).getByRole("button", {
      name: label("desktop.setup.action.set_up"),
      exact: true,
    }),
  ).toHaveCount(1);
  await noInternalWords(target);
  await closePanel(target);
  const rail = target.locator("[data-rail=settings]");
  await expect(rail.locator("[data-pin=attention]")).toHaveCount(1);
  await expect(rail).toHaveAccessibleName(
    new RegExp(label("desktop.setup.rail_incomplete")),
  );
  // Not opened again by itself; the palette leads back to it.
  await target.locator("[data-rail=docs]").click();
  await expect(panel(target)).toBeHidden();
  await (await palette(target, label("desktop.setup.palette_open"))).click();
  await expect(panel(target)).toBeVisible();
});

test("the local AI is a dropdown holding its program and the model list", async ({
  page: target,
}) => {
  await open(target, "fresh");
  const toggle = localAi(target).getByRole("button", { name: LOCAL_AI });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await openLocalAi(target);
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  // Open, the program row says the element's status; the header does not.
  await once(localAi(target), NOT_SET_UP);
  await expect(programRow(target)).toContainText(
    label("desktop.setup.part_program"),
  );
  // The program's size is not known before its download starts.
  await expect(programRow(target)).toContainText(
    label("desktop.setup.size_unknown"),
  );
  await expect(setUpButton(programRow(target))).toHaveCount(1);
  // Beneath it, the model list, each model with its own download.
  const models = localAi(target).locator(
    '[data-slot="local-models"] li[data-model]',
  );
  await expect(models.first()).toBeVisible();
  await expect(
    models.first().getByRole("button", {
      name: label("desktop.providers.local_model_download"),
    }),
  ).toHaveCount(1);
  await noInternalWords(target);
});

test("an element's plan is reviewed inside its own row", async ({
  page: target,
}) => {
  await open(target, "fresh");
  await setUpButton(browserRow(target)).click();
  const row = browserRow(target);
  await expect(row).toContainText(label("desktop.setup.lead_review"));
  await expect(row.locator("[data-setup-plan-size]")).toHaveText(
    label("desktop.setup.plan_size", { size: BROWSER_SIZE }),
  );
  await expect(row).toContainText(
    label("desktop.setup.plan_from", { hosts: "cdn.playwright.dev" }),
  );
  // The plan is the browser's alone; the local AI still waits on its own.
  await expect(panel(target).locator("[data-setup-review]")).toHaveCount(1);
  await expect(localAi(target)).not.toContainText(
    label("desktop.setup.lead_review"),
  );
  await expect(approveBrowser(target)).toBeEnabled();
  expect(await hostCalls(target)).toContain("setup.start browser");
  await noInternalWords(target);
});

test("an approved setup shows its own progress, spins the rail, and settles ready", async ({
  page: target,
}) => {
  await open(target, "fresh");
  await startBrowser(target);
  const rail = target.locator("[data-rail=settings]");
  await expect(rail.locator("[data-pin=busy]")).toHaveCount(1);
  // The open panel hides the rail from the accessibility tree; its label is
  // read where it is set.
  await expect(rail).toHaveAttribute(
    "aria-label",
    new RegExp(label("desktop.setup.rail_busy")),
  );
  await steps(target, 2, "browser");
  const row = browserRow(target);
  await expect(row).toContainText(label("desktop.setup.step_downloading"));
  await expect(
    row.getByRole("progressbar", {
      name: label("desktop.setup.progress_label", { name: BROWSER }),
    }),
  ).toBeVisible();
  await act(target, "retry", 2, 8);
  await expect(row).toContainText(
    label("desktop.setup.retry", { attempt: 2, seconds: 8 }),
  );
  await stepUntil(target, "browser", async () =>
    (await row.innerText()).includes(label("desktop.setup.state.ready")),
  );
  await expect(
    target.getByRole("status").filter({
      hasText: label("desktop.setup.toast_done"),
    }),
  ).toBeVisible();
  // Nothing runs any more; the local AI is still to set up.
  await expect(rail.locator("[data-pin=busy]")).toHaveCount(0);
  await expect(rail.locator("[data-pin=attention]")).toHaveCount(1);
  await noInternalWords(target);
});

test("the browser and the local AI set up at the same time, each on its own", async ({
  page: target,
}) => {
  await open(target, "fresh");
  await startBrowser(target);
  await openLocalAi(target);
  await setUpButton(programRow(target)).click();
  // The program's installer is sized only once it starts.
  await expect(programRow(target).locator("[data-setup-plan-size]")).toHaveText(
    label("desktop.setup.size_unknown"),
  );
  await programRow(target)
    .getByRole("button", { name: label("desktop.setup.approve") })
    .click();
  await expect(panel(target).locator("[data-setup-progress]")).toHaveCount(2);
  // Moving one on leaves the other where it was.
  await steps(target, 2, "local_ai");
  await expect(programRow(target)).toContainText(
    label("desktop.setup.step_downloading"),
  );
  await expect(browserRow(target)).toContainText(
    label("desktop.setup.step_waiting"),
  );
  // Cancelling the local AI's setup leaves the browser's running.
  await programRow(target)
    .getByRole("button", { name: label("desktop.setup.cancel") })
    .click();
  await expect(programRow(target)).toContainText(
    label("desktop.setup.cancelling"),
  );
  await steps(target, 1, "local_ai");
  await expect(programRow(target)).toContainText(
    label("desktop.setup.outcome_cancelled"),
  );
  await expect(browserRow(target).locator("[data-setup-progress]")).toHaveCount(
    1,
  );
  await expect(
    target.locator("[data-rail=settings] [data-pin=busy]"),
  ).toHaveCount(1);
  const calls = await hostCalls(target);
  expect(calls).toContain("setup.start browser");
  expect(calls).toContain("setup.start local_ai");
  await noInternalWords(target);
});

test("closing the panel leaves a setup running, and the panel shows it again", async ({
  page: target,
}) => {
  await open(target, "fresh");
  await startBrowser(target);
  await panel(target)
    .getByRole("button", { name: label("desktop.setup.close") })
    .first()
    .click();
  await expect(panel(target)).toBeHidden();
  await steps(target, 2, "browser");
  await expect(
    target.locator("[data-rail=settings] [data-pin=busy]"),
  ).toHaveCount(1);
  await (await palette(target, label("desktop.setup.palette_open"))).click();
  await expect(browserRow(target)).toContainText(
    label("desktop.setup.step_downloading"),
  );
});

test("a plan turned down downloads nothing", async ({ page: target }) => {
  await open(target, "fresh");
  await setUpButton(browserRow(target)).click();
  await browserRow(target)
    .getByRole("button", { name: label("desktop.setup.reject") })
    .click();
  await expect(browserRow(target)).toContainText(
    label("desktop.setup.outcome_rejected"),
  );
  // Said once: the row's sentence gives way to the outcome.
  await expect(browserRow(target)).not.toContainText(NOT_SET_UP);
  expect(await hostCalls(target)).toContain("setup.answer reject");
});

test("a running setup can be cancelled and keeps what it downloaded", async ({
  page: target,
}) => {
  await open(target, "fresh");
  await startBrowser(target);
  await steps(target, 1, "browser");
  await browserRow(target)
    .getByRole("button", { name: label("desktop.setup.cancel") })
    .click();
  await expect(browserRow(target)).toContainText(
    label("desktop.setup.cancelling"),
  );
  await steps(target, 1, "browser");
  await expect(browserRow(target)).toContainText(
    label("desktop.setup.outcome_cancelled"),
  );
  await expect(
    target.getByRole("status").filter({
      hasText: label("desktop.setup.toast_cancelled"),
    }),
  ).toBeVisible();
});

test("a plan that changed before its approval is shown again for a new approval", async ({
  page: target,
}) => {
  await open(target, "plan_changes");
  await setUpButton(browserRow(target)).click();
  await approveBrowser(target).click();
  await expect(panel(target)).toContainText(
    label("desktop.setup.refused_plan_changed"),
  );
  const again = browserRow(target).getByRole("button", {
    name: label("desktop.setup.approve_size", { size: "280 MB" }),
  });
  await expect(again).toBeVisible();
  await again.click();
  await expect(browserRow(target).locator("[data-setup-progress]")).toHaveCount(
    1,
  );
  await noInternalWords(target);
});

test("too little free space is said before anything is downloaded", async ({
  page: target,
}) => {
  await open(target, "low_space");
  await setUpButton(browserRow(target)).click();
  await expect(browserRow(target).getByRole("alert")).toContainText(
    label("desktop.setup.space_short"),
  );
  await expect(approveBrowser(target)).toBeDisabled();
  await noInternalWords(target);
});

test("offline, the elements that need the network say so and offer a check", async ({
  page: target,
}) => {
  await open(target, "offline");
  await expect(browserRow(target)).toContainText(
    label("desktop.setup.blocked.offline"),
  );
  await browserRow(target)
    .getByRole("button", { name: label("desktop.setup.action.check_again") })
    .click();
  expect(await hostCalls(target)).toContain("setup.verify browser");
  await noInternalWords(target);
});

test("builds no current receipt records are checked again, with no download, and the check reads them ready", async ({
  page: target,
}) => {
  await open(target, "unrecorded");
  const row = browserRow(target);
  await once(row, label("desktop.setup.state.unknown"));
  await expect(row).not.toContainText(NOT_SET_UP);
  // Checked again, not set up: no size, not even a zero one.
  await expect(row.locator("[data-setup-size]")).toHaveCount(0);
  await expect(setUpButton(row)).toHaveCount(0);
  await row
    .getByRole("button", { name: label("desktop.setup.action.check_again") })
    .click();
  await expect(row).toContainText(label("desktop.setup.state.ready"));
  const calls = await hostCalls(target);
  expect(calls).toContain("setup.verify browser");
  expect(calls.filter((call) => call.startsWith("setup.start"))).toEqual([]);
  await noInternalWords(target);
});

test("an interrupted setup resumes without a second approval while its plan is unchanged", async ({
  page: target,
}) => {
  await open(target, "fresh");
  await startBrowser(target);
  await steps(target, 3, "browser");
  await act(target, "interrupt", "browser");
  await expect(browserRow(target)).toContainText(
    label("desktop.setup.failure.interrupted"),
  );
  await browserRow(target)
    .getByRole("button", { name: label("desktop.setup.action.resume") })
    .click();
  await expect(browserRow(target).locator("[data-setup-progress]")).toHaveCount(
    1,
  );
  await expect(panel(target).locator("[data-setup-review]")).toHaveCount(0);
  expect(await hostCalls(target)).toContain("setup.start browser resume");
});

test("an interrupted setup whose plan changed asks for approval again", async ({
  page: target,
}) => {
  await open(target, "resume_changes");
  await startBrowser(target);
  await steps(target, 1, "browser");
  await act(target, "interrupt", "browser");
  await browserRow(target)
    .getByRole("button", { name: label("desktop.setup.action.resume") })
    .click();
  await expect(browserRow(target)).toContainText(
    label("desktop.setup.lead_review"),
  );
  await expect(
    browserRow(target).getByRole("button", {
      name: label("desktop.setup.approve_size", { size: "280 MB" }),
    }),
  ).toBeVisible();
});

test("Google authentication belongs to the profile menu, apart from setup", async ({
  page: target,
}) => {
  await open(target, "google_signed_out", "google-account");
  // Everything is set up: no panel and no pin.
  await expect(panel(target)).toHaveCount(0);
  await expect(target.locator("[data-rail=settings] [data-pin]")).toHaveCount(
    0,
  );
  await target.locator("[data-rail=settings]").click();
  await expect(target.locator(".settings [data-google-account]")).toHaveCount(
    0,
  );
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
  const calls = await hostCalls(target);
  expect(calls).toContain("google.signIn");
  expect(calls).toContain("google.signOut");
  await noInternalWords(target);
});

test("a Google sign-in that does not finish says so on the account's row", async ({
  page: target,
}) => {
  await open(target, "google_signed_out", "google-account");
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
  expect(await hostCalls(target)).toContain("google.signIn");
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

test("the palette has a way to each element, which opens the panel on it", async ({
  page: target,
}) => {
  await open(target, "partial");
  await closePanel(target);
  await expect(
    await palette(target, label("desktop.setup.palette_cancel")),
  ).toHaveCount(0);
  await target.keyboard.press("Escape");
  await (await palette(target, paletteItem(LOCAL_AI))).click();
  // Opened on the local AI, its dropdown is open and its plan awaits an
  // answer in the program row.
  await expect(programRow(target)).toContainText(
    label("desktop.setup.lead_review"),
  );
  await expect(panel(target).locator("[data-setup-review]")).toHaveCount(1);
  await programRow(target)
    .getByRole("button", { name: label("desktop.setup.reject") })
    .click();
  await expect(programRow(target)).toContainText(
    label("desktop.setup.outcome_rejected"),
  );
  await panel(target)
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  const retry = await palette(target, label("desktop.setup.palette_retry"));
  await expect(retry).toHaveCount(1);
});

test("signed out, setup is nowhere to be found", async ({ page: target }) => {
  await open(target, "fresh", "signed-out");
  await expect(panel(target)).toHaveCount(0);
  await expect(target.locator("[data-rail=settings] [data-pin]")).toHaveCount(
    0,
  );
  expect(
    (await hostCalls(target)).filter(
      (call) => call.startsWith("setup.") || call.startsWith("google."),
    ),
  ).toEqual([]);
});

test("Copy details puts the report on the clipboard", async ({
  page: target,
}) => {
  await open(target, "partial");
  await panel(target)
    .getByRole("button", { name: label("desktop.setup.copy_details") })
    .click();
  await expect(
    target.getByRole("status").filter({
      hasText: label("desktop.toast.copied"),
    }),
  ).toBeVisible();
});

test("a local AI this computer cannot run says so once, offers no setup, and keeps its model list", async ({
  page: target,
}) => {
  await open(target, "hardware");
  await closePanel(target);
  await (await palette(target, paletteItem(LOCAL_AI))).click();
  const sentence = label("desktop.setup.blocked.hardware");
  await expect(programRow(target)).toContainText(sentence);
  await once(localAi(target), sentence);
  await expect(programRow(target).getByRole("button")).toHaveCount(0);
  await expect(
    localAi(target).locator('[data-slot="local-models"]'),
  ).toBeVisible();
  await noInternalWords(target);
  expect(await hostCalls(target)).not.toContain("setup.start local_ai");
});

/** Opens the window with setup unfinished, puts its panel away, and has the
 * agent call a tool the product refuses as `message` says. */
async function refusedTool(target: Page, message: string) {
  scenarioOnly("the scenario host refuses a tool when it is asked to");
  await open(target, "fresh");
  await closePanel(target);
  await send(target, message);
  await settled(target);
}

test("a tool refused for a missing component opens the panel on it, once", async ({
  page: target,
}) => {
  await refusedTool(target, "Captura el censo, aunque falta el navegador.");
  await expect(panel(target)).toBeVisible();
  await expect(browserRow(target)).toBeInViewport();
  await once(browserRow(target), NOT_SET_UP);
  await expect(toolRow(target, "aeat_capture_censo")).toContainText(
    label("desktop.agent.tool_failed"),
  );
  // It opened while the person was in the message field, and left the
  // keyboard there. The modal panel hides the column from the accessibility
  // tree, so the field is found by where it is rather than by its role.
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
  await closePanel(target);
  // Read again, the conversation does not raise the same refusal twice.
  await target.locator("[data-rail=docs]").click();
  await expect(target.getByRole("dialog")).toHaveCount(0);
});

test("the panel a refused tool opens sets the component up from its row", async ({
  page: target,
}) => {
  await refusedTool(target, "Captura el censo, aunque falta el navegador.");
  await setUpButton(browserRow(target)).click();
  await expect(browserRow(target).locator("[data-setup-review]")).toHaveCount(
    1,
  );
  await expect(panel(target).locator("[data-setup-review]")).toHaveCount(1);
  expect(await hostCalls(target)).toContain("setup.start browser");
});

test("each new sync refused for the missing browser opens the panel again", async ({
  page: target,
}) => {
  await refusedTool(target, "Captura el censo, aunque falta el navegador.");
  await expect(panel(target)).toBeVisible();
  await closePanel(target);
  // Another call, refused the same way, is a refusal of its own.
  await send(target, "Sincroniza otra vez, aunque falta el navegador.");
  await settled(target);
  await expect(panel(target)).toBeVisible();
  await closePanel(target);
  await target.locator("[data-rail=docs]").click();
  await expect(target.getByRole("dialog")).toHaveCount(0);
});

test("a refusal that arrives before the setup status is read opens the panel once it is", async ({
  page: target,
}) => {
  scenarioOnly("the scenario host holds the first status read");
  await open(target, "unread");
  await send(target, "Captura el censo, aunque falta el navegador.");
  await settled(target);
  await expect(panel(target)).toBeHidden();
  await act(target, "readRows");
  await expect(panel(target)).toBeVisible();
  await expect(browserRow(target)).toContainText(NOT_SET_UP);
  // The panel the refusal opened stands in for the one opened once per
  // launch: there is one panel, not two.
  await expect(target.getByRole("dialog")).toHaveCount(1);
});

test("a Censo pull that stops for the missing browser opens the panel, each pull again", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=censo-browser-missing&latency=0&bar=off",
  );
  await closePanel(target);
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
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await pull.click();
    await expect(browserRow(target)).toBeVisible();
    await closePanel(target);
    // The band still says the pull failed, beside the panel it raised.
    await expect(band).toContainText(label("desktop.profile.censo.failed"));
  }
  await expect(target.locator("body")).not.toContainText("operator.");
});

test("the palette sets up the browser alone", async ({ page: target }) => {
  await open(target, "fresh");
  await closePanel(target);
  await (await palette(target, paletteItem(BROWSER))).click();
  await expect(browserRow(target)).toContainText(
    label("desktop.setup.lead_review"),
  );
  const calls = await hostCalls(target);
  expect(calls).toContain("setup.start browser");
  expect(calls).not.toContain("setup.start local_ai");
  await approveBrowser(target).click();
  const row = browserRow(target);
  await stepUntil(target, "browser", async () =>
    (await row.innerText()).includes(label("desktop.setup.state.ready")),
  );
  // The local AI was not touched.
  await once(localAi(target), NOT_SET_UP);
  expect(await hostCalls(target)).not.toContain("setup.start local_ai");
  await noInternalWords(target);
});

test("a ready element says so and offers nothing to do", async ({
  page: target,
}) => {
  await open(target, "ready");
  await (await palette(target, paletteItem(BROWSER))).click();
  await expect(browserRow(target)).toContainText(
    label("desktop.setup.state.ready"),
  );
  // Only its removal: nothing to set up or check.
  await expect(browserRow(target).getByRole("button")).toHaveCount(1);
  await expect(
    browserRow(target).getByRole("button", {
      name: label("desktop.setup.remove"),
    }),
  ).toBeVisible();
  expect(
    (await hostCalls(target)).filter((call) => call.startsWith("setup.start")),
  ).toEqual([]);
});

test("a ready browser is removed only after a second confirmation, and then offers its setup again", async ({
  page: target,
}) => {
  await open(target, "ready");
  await (await palette(target, paletteItem(BROWSER))).click();
  const row = browserRow(target);
  const remove = row.getByRole("button", {
    name: label("desktop.setup.remove"),
    exact: true,
  });
  await remove.click();
  await expect(row).toContainText(label("desktop.setup.remove_confirm"));
  // Keeping it asks nothing of the host.
  await row
    .getByRole("button", { name: label("desktop.setup.remove_keep") })
    .click();
  await expect(remove).toBeVisible();
  expect(await hostCalls(target)).not.toContain("setup.remove browser");
  await remove.click();
  await row
    .getByRole("button", { name: label("desktop.setup.remove_confirm_yes") })
    .click();
  await expect(row).toContainText(NOT_SET_UP);
  expect(await hostCalls(target)).toContain("setup.remove browser");
  await expect(setUpButton(row)).toBeVisible();
  // Nothing is left to remove.
  await expect(remove).toHaveCount(0);
  await noInternalWords(target);
});

test("a ready local AI offers its removal two ways, each after a second confirmation", async ({
  page: target,
}) => {
  await open(target, "ready");
  await (await palette(target, paletteItem(LOCAL_AI))).click();
  const row = programRow(target);
  const removeAll = row.getByRole("button", {
    name: label("desktop.setup.remove_local_ai"),
    exact: true,
  });
  const removeProgram = row.getByRole("button", {
    name: label("desktop.setup.remove_local_ai_program"),
    exact: true,
  });
  await expect(removeAll).toBeVisible();
  await expect(removeProgram).toBeVisible();
  // Keeping it asks nothing of the host.
  await removeProgram.click();
  await expect(row).toContainText(
    label("desktop.setup.remove_local_ai_program_confirm"),
  );
  await row
    .getByRole("button", { name: label("desktop.setup.remove_keep") })
    .click();
  await expect(removeProgram).toBeVisible();
  expect(
    (await hostCalls(target)).filter((call) => call.startsWith("setup.remove")),
  ).toEqual([]);
  // The program alone goes, and the local AI offers its setup again.
  await removeProgram.click();
  await row
    .getByRole("button", { name: label("desktop.setup.remove_confirm_yes") })
    .click();
  await once(localAi(target), NOT_SET_UP);
  expect(await hostCalls(target)).toContain("setup.remove local_ai_program");
  await expect(removeAll).toHaveCount(0);
  await noInternalWords(target);
});

test("removing the whole local AI asks for a second confirmation and names the models", async ({
  page: target,
}) => {
  await open(target, "ready");
  await (await palette(target, paletteItem(LOCAL_AI))).click();
  const row = programRow(target);
  await row
    .getByRole("button", {
      name: label("desktop.setup.remove_local_ai"),
      exact: true,
    })
    .click();
  await expect(row).toContainText(
    label("desktop.setup.remove_local_ai_confirm"),
  );
  await row
    .getByRole("button", { name: label("desktop.setup.remove_confirm_yes") })
    .click();
  await once(localAi(target), NOT_SET_UP);
  expect(await hostCalls(target)).toContain("setup.remove local_ai");
  await expect(
    localAi(target).locator(
      '[data-slot="local-models"] li[data-installed="true"]',
    ),
  ).toHaveCount(0);
  await noInternalWords(target);
});

test("a browser that is not on this computer offers no removal", async ({
  page: target,
}) => {
  await open(target, "fresh");
  await expect(panel(target)).toBeVisible();
  await expect(
    browserRow(target).getByRole("button", {
      name: label("desktop.setup.remove"),
    }),
  ).toHaveCount(0);
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
