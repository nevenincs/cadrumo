import { expect, test, type Page } from "@playwright/test";
import {
  FIXTURE_SETTINGS_LANES,
  type ProviderSignInFixtureCall,
} from "../../src/dev/providerSettingsFixture";
import type { ProviderSignInMethod } from "../../src/shell/providerSettings";
import { label } from "../support/strings";

// Every way a provider sign-in can fail is said in the dialog with its cause,
// and Retry is always a fresh attempt: a new start, never a status read or a
// cancel of the attempt that already ended. Each case runs for both shapes a
// provider's sign-in takes: one that opens the provider's page or shows a
// device code, and one whose page hands back a code to paste.

const open = (target: Page) =>
  target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off&lang=en");

const settings = (target: Page) =>
  target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title"),
  });

const lane = (target: Page, id: string) =>
  settings(target).locator(`[data-lane="${id}"]`);

const SIGN_IN_LANES = FIXTURE_SETTINGS_LANES.filter(
  (declared) => declared.auth_kind === "provider_sign_in_only",
);

type Shape = {
  name: string;
  laneId: string;
  provider: string;
  displayName: string;
  methods: readonly ProviderSignInMethod[];
  /** The provider's page asks for a code to be pasted back. */
  asksForCode: boolean;
};

const SHAPES: readonly Shape[] = [
  {
    name: "browser or device sign-in",
    lane: SIGN_IN_LANES[0]!,
    methods: ["browser", "device"] as const,
    asksForCode: false,
  },
  {
    name: "browser sign-in that asks for a pasted code",
    lane: SIGN_IN_LANES[1]!,
    methods: ["browser"] as const,
    asksForCode: true,
  },
].map(({ lane: declared, ...shape }) => ({
  ...shape,
  laneId: declared.id,
  provider: declared.provider,
  displayName: declared.display_name,
}));

/** A synthetic diagnostic id, as the host names a failure in its log. */
const LOG_REF = "diag-7f3a9c2e";

async function prepare(target: Page, shape: Shape) {
  await open(target);
  await target.evaluate(
    ({ providers, methods, asksForCode }) => {
      const controls = window.__scenarioProviderSignIn!;
      controls.offerSignIn(providers);
      controls.setMethods(methods);
      if (asksForCode) controls.askForCode();
    },
    {
      providers: SIGN_IN_LANES.map((declared) => declared.provider),
      methods: [...shape.methods],
      asksForCode: shape.asksForCode,
    },
  );
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  await expect(settings(target)).toBeVisible();
  await settings(target)
    .locator("li[data-provider] > details")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => ((node as HTMLDetailsElement).open = true)),
    );
}

const signInCalls = (target: Page) =>
  target.evaluate(() => window.__scenarioProviderSignIn!.signInCalls());

const starts = (calls: ProviderSignInFixtureCall[]) =>
  calls.filter((call) => call.op === "start").length;

async function startSignIn(target: Page, shape: Shape) {
  await lane(target, shape.laneId)
    .getByRole("button", { name: label("desktop.providers.sign_in_action") })
    .click();
  return target.getByRole("dialog");
}

/** The attempt the window is observing, once it has asked about it. */
async function observedAttempt(target: Page): Promise<string> {
  await expect
    .poll(async () =>
      (await signInCalls(target)).some((call) => call.op === "status"),
    )
    .toBe(true);
  const calls = await signInCalls(target);
  return calls.find((call) => call.op === "status")!.attempt_id!;
}

async function expectLogRef(dialog: ReturnType<Page["getByRole"]>) {
  const line = dialog.locator('[data-slot="sign-in-log-ref"]');
  await expect(line).toContainText(label("desktop.providers.sign_in_log_ref"));
  await expect(line.locator("code")).toHaveText(LOG_REF);
}

/** Retry starts a new attempt, which succeeds and leaves the lane signed in;
 * nothing after `from` asks about `dead` again. */
async function retryToSuccess(
  target: Page,
  dialog: ReturnType<Page["getByRole"]>,
  from: number,
  dead: string | null,
) {
  const before = starts(await signInCalls(target));
  await dialog
    .getByRole("button", { name: label("desktop.providers.sign_in_retry") })
    .click();
  await expect
    .poll(async () => starts(await signInCalls(target)))
    .toBe(before + 1);
  await expect(dialog.getByRole("alert")).toHaveCount(0);
  const freshAttempt = async () =>
    (await signInCalls(target)).slice(from).find((call) => call.op === "status")
      ?.attempt_id ?? null;
  await expect.poll(freshAttempt).not.toBeNull();
  const fresh = await freshAttempt();
  expect(fresh).not.toBe(dead);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.succeedCurrentAttempt(true),
  );
  await expect(dialog).toHaveCount(0);
  return fresh;
}

const asked = (calls: ProviderSignInFixtureCall[], attempt: string | null) =>
  calls.filter(
    (call) =>
      attempt !== null &&
      call.attempt_id === attempt &&
      (call.op === "status" || call.op === "cancel"),
  );

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("the fixture catalogue offers two lanes that sign in through their app", () => {
  expect(SIGN_IN_LANES).toHaveLength(2);
});

for (const shape of SHAPES) {
  test.describe(shape.name, () => {
    test("a refused start says why, with its diagnostic reference, and Retry starts afresh", async ({
      page: target,
    }) => {
      await prepare(target, shape);
      await target.evaluate(
        (logRef) =>
          window.__scenarioProviderSignIn!.rejectNextStart("busy", {
            cause: "login_already_running",
            next_step: "close_other_sign_in",
            log_ref: logRef,
          }),
        LOG_REF,
      );
      const dialog = await startSignIn(target, shape);
      await expect(dialog.getByRole("alert").first()).toContainText(
        label("desktop.providers.sign_in_busy", {
          provider: shape.displayName,
        }),
      );
      await expect(dialog).toContainText(
        label("desktop.providers.sign_in_cause.login_already_running"),
      );
      await expect(dialog).toContainText(
        label("desktop.providers.next_step.close_other_sign_in"),
      );
      await expectLogRef(dialog);
      await expect(dialog).not.toContainText(
        label("desktop.providers.sign_in_failure"),
      );
      const from = (await signInCalls(target)).length;
      await retryToSuccess(target, dialog, from, null);
      await expect(
        lane(target, shape.laneId).locator('[data-slot="provider-status"]'),
      ).toHaveAttribute("data-status", "ready");
    });

    test("a refusal whose code the window does not name says its reason instead of the generic words", async ({
      page: target,
    }) => {
      await prepare(target, shape);
      await target.evaluate(
        (logRef) =>
          window.__scenarioProviderSignIn!.rejectNextStart("read_failed", {
            reason: "provider_unavailable",
            log_ref: logRef,
          }),
        LOG_REF,
      );
      const dialog = await startSignIn(target, shape);
      await expect(dialog.getByRole("alert").first()).toContainText(
        label("desktop.providers.sign_in_provider_unavailable", {
          provider: shape.displayName,
        }),
      );
      await expectLogRef(dialog);
      await expect(dialog).not.toContainText(
        label("desktop.providers.sign_in_failure"),
      );
      await expect(dialog).not.toContainText("read_failed");
      await expect(
        dialog.getByRole("button", {
          name: label("desktop.providers.sign_in_retry"),
        }),
      ).toBeVisible();
    });

    test("an attempt that turns failed says why, stops being observed, and Retry starts afresh", async ({
      page: target,
    }) => {
      await prepare(target, shape);
      const dialog = await startSignIn(target, shape);
      const dead = await observedAttempt(target);
      await target.evaluate(
        (logRef) =>
          window.__scenarioProviderSignIn!.failCurrentAttempt({
            reason: "provider_error",
            cause: "cli_reported_error",
            next_step: "retry",
            log_ref: logRef,
          }),
        LOG_REF,
      );
      await expect(dialog.getByRole("alert").first()).toContainText(
        label("desktop.providers.sign_in_provider_error", {
          provider: shape.displayName,
        }),
      );
      await expect(dialog).toContainText(
        label("desktop.providers.sign_in_cause.cli_reported_error"),
      );
      await expect(dialog).toContainText(
        label("desktop.providers.next_step.retry"),
      );
      await expectLogRef(dialog);
      await expect(
        dialog.getByRole("button", {
          name: label("desktop.providers.sign_in_retry"),
        }),
      ).toBeVisible();
      const from = (await signInCalls(target)).length;
      // Observation of the ended attempt stops.
      await target.waitForTimeout(2_500);
      expect(asked((await signInCalls(target)).slice(from), dead)).toEqual([]);
      await retryToSuccess(target, dialog, from, dead);
      expect(asked((await signInCalls(target)).slice(from), dead)).toEqual([]);
      await expect(
        lane(target, shape.laneId).locator('[data-slot="provider-status"]'),
      ).toHaveAttribute("data-status", "ready");
    });

    test("status reads that keep failing end the attempt with their cause instead of waiting it out", async ({
      page: target,
    }) => {
      await prepare(target, shape);
      const dialog = await startSignIn(target, shape);
      await observedAttempt(target);
      await target.evaluate(
        (logRef) =>
          window.__scenarioProviderSignIn!.failNextStatus(
            "read_failed",
            { cause: "host_disconnected", log_ref: logRef },
            1_000,
          ),
        LOG_REF,
      );
      await expect(dialog.getByRole("alert").first()).toContainText(
        label("desktop.providers.sign_in_host_disconnected", {
          provider: shape.displayName,
        }),
        { timeout: 15_000 },
      );
      await expect(dialog).toContainText(
        label("desktop.providers.sign_in_cause.host_disconnected"),
      );
      await expectLogRef(dialog);
      await expect(
        dialog.getByRole("button", {
          name: label("desktop.providers.sign_in_retry"),
        }),
      ).toBeVisible();
    });

    test("a refused code says why, and Retry starts afresh without asking about the abandoned attempt", async ({
      page: target,
    }) => {
      await prepare(target, shape);
      await target.evaluate(() =>
        window.__scenarioProviderSignIn!.askForCode(),
      );
      const dialog = await startSignIn(target, shape);
      const input = dialog.getByLabel(
        label("desktop.providers.sign_in_code_label"),
      );
      await expect(input).toBeVisible();
      const dead = await observedAttempt(target);
      await target.evaluate(
        (logRef) =>
          window.__scenarioProviderSignIn!.failNextSubmit("read_failed", {
            reason: "provider_error",
            cause: "cli_reported_error",
            log_ref: logRef,
          }),
        LOG_REF,
      );
      await input.fill("FAKE-refused-code-123");
      await dialog
        .getByRole("button", {
          name: label("desktop.providers.sign_in_code_submit"),
        })
        .click();
      await expect(dialog.getByRole("alert").first()).toContainText(
        label("desktop.providers.sign_in_provider_error", {
          provider: shape.displayName,
        }),
      );
      await expect(dialog).toContainText(
        label("desktop.providers.sign_in_cause.cli_reported_error"),
      );
      await expectLogRef(dialog);
      await expect(
        dialog.getByRole("button", {
          name: label("desktop.providers.sign_in_retry"),
        }),
      ).toBeVisible();
      // The abandoned attempt is cancelled once, before Retry is offered.
      const settled = await signInCalls(target);
      expect(
        settled.filter(
          (call) => call.op === "cancel" && call.attempt_id === dead,
        ),
      ).toHaveLength(1);
      const from = settled.length;
      await retryToSuccess(target, dialog, from, dead);
      expect(asked((await signInCalls(target)).slice(from), dead)).toEqual([]);
    });
  });
}
