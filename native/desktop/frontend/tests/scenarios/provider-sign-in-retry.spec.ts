import { expect, test, type Page } from "@playwright/test";
import {
  FIXTURE_SETTINGS_LANES,
  type ProviderSignInFixtureCall,
} from "../../src/dev/providerSettingsFixture";
import type { ProviderSignInMethod } from "../../src/shell/providerSettingsContract";
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
    .locator("[data-slot=lane-expander][aria-expanded=false]")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => (node as HTMLElement).click()),
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

test("the fixture catalogue's app lanes sign in through their app, save those that take a key with its endpoint", () => {
  // As the agent derives it: a provider's key goes to its API lane, so its
  // app lane signs in; an app-only provider's key lane names its endpoint.
  expect(SIGN_IN_LANES.map((declared) => declared.id)).toEqual([
    "antigravity_cli",
    "kimi_cli",
    "qwen_cli",
    "deepseek_cli",
    "moonshot_cli",
  ]);
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
      ).toHaveAttribute("data-status", "signed_in");
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
      ).toHaveAttribute("data-status", "signed_in");
    });

    test("an attempt the service cancels because the profile signed out says so, never as the person's own cancel", async ({
      page: target,
    }) => {
      await prepare(target, shape);
      const dialog = await startSignIn(target, shape);
      const dead = await observedAttempt(target);
      await target.evaluate(
        (logRef) =>
          window.__scenarioProviderSignIn!.cancelCurrentAttempt({
            reason: "profile_required",
            cause: "profile_signed_out",
            next_step: "retry",
            log_ref: logRef,
          }),
        LOG_REF,
      );
      await expect(dialog.getByRole("alert").first()).toContainText(
        label("desktop.providers.sign_in_profile_required", {
          provider: shape.displayName,
        }),
      );
      await expect(dialog).toContainText(
        label("desktop.providers.sign_in_cause.profile_signed_out"),
      );
      await expect(dialog).not.toContainText(
        label("desktop.providers.sign_in_cancelled"),
      );
      await expect(dialog.locator('[data-slot="sign-in-attempt"]')).toHaveCount(
        0,
      );
      await expectLogRef(dialog);
      await expect(
        dialog.getByRole("button", {
          name: label("desktop.providers.sign_in_retry"),
        }),
      ).toBeVisible();
      const from = (await signInCalls(target)).length;
      await target.waitForTimeout(2_500);
      expect(asked((await signInCalls(target)).slice(from), dead)).toEqual([]);
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

    test("the dialog states its live attempt and its failure as data, and a retry is a different attempt", async ({
      page: target,
    }) => {
      await prepare(target, shape);
      const dialog = await startSignIn(target, shape);
      const dead = await observedAttempt(target);
      await expect(dialog.locator("[data-attempt-id]")).toHaveAttribute(
        "data-attempt-id",
        dead,
      );
      await target.evaluate(
        (logRef) =>
          window.__scenarioProviderSignIn!.failCurrentAttempt({
            reason: "provider_error",
            cause: "cli_reported_error",
            next_step: "retry",
            status_cause: "status_not_confirmed",
            log_ref: logRef,
          }),
        LOG_REF,
      );
      const alert = dialog.locator('p[role="alert"]');
      await expect(alert).toHaveAttribute("data-reason", "provider_error");
      await expect(alert).toHaveAttribute("data-cause", "cli_reported_error");
      await expect(alert).toHaveAttribute("data-next-step", "retry");
      await expect(alert).toHaveAttribute("data-log-ref", LOG_REF);
      // A failed attempt is no longer live.
      await expect(dialog.locator("[data-attempt-id]")).toHaveCount(0);
      await dialog
        .getByRole("button", { name: label("desktop.providers.sign_in_retry") })
        .click();
      const fresh = dialog.locator("[data-attempt-id]");
      await expect(fresh).toHaveCount(1);
      const id = await fresh.getAttribute("data-attempt-id");
      expect(id).toMatch(/^[0-9a-f-]{36}$/);
      expect(id).not.toBe(dead);
      await expect(dialog.locator('p[role="alert"]')).toHaveCount(0);
    });

    test("a failure with no cause or log reference states only its reason as data", async ({
      page: target,
    }) => {
      await prepare(target, shape);
      await target.evaluate(() =>
        window.__scenarioProviderSignIn!.rejectNextStart("busy"),
      );
      const dialog = await startSignIn(target, shape);
      const alert = dialog.locator('p[role="alert"]');
      await expect(alert).toHaveAttribute("data-reason", "busy");
      await expect(alert).not.toHaveAttribute("data-cause", /.*/);
      await expect(alert).not.toHaveAttribute("data-next-step", /.*/);
      await expect(alert).not.toHaveAttribute("data-log-ref", /.*/);
    });

    test("the window's own timeout says the last cause and log reference it was told, and none it was not", async ({
      page: target,
    }) => {
      await target.clock.install();
      await prepare(target, shape);
      const dialog = await startSignIn(target, shape);
      const dead = await observedAttempt(target);
      await target.evaluate(
        (logRef) =>
          window.__scenarioProviderSignIn!.noteCurrentAttempt({
            cause: "login_not_completed",
            next_step: "retry",
            log_ref: logRef,
          }),
        LOG_REF,
      );
      // The next status read carries the note.
      const reads = async () =>
        (await signInCalls(target)).filter(
          (call) => call.op === "status" && call.attempt_id === dead,
        ).length;
      const before = await reads();
      await target.clock.runFor(2_500);
      await expect.poll(reads).toBeGreaterThan(before);
      await target.clock.fastForward("05:10");
      const alert = dialog.locator('p[role="alert"]').first();
      await expect(alert).toContainText(
        label("desktop.providers.sign_in_timeout"),
      );
      await expect(alert).toHaveAttribute("data-reason", "timeout");
      await expect(alert).toHaveAttribute("data-cause", "login_not_completed");
      await expect(alert).toHaveAttribute("data-next-step", "retry");
      await expect(alert).toHaveAttribute("data-log-ref", LOG_REF);
      await expect(dialog).toContainText(
        label("desktop.providers.sign_in_cause.login_not_completed"),
      );
      await expect(dialog).toContainText(
        label("desktop.providers.next_step.retry"),
      );
      await expectLogRef(dialog);
    });

    test("a timeout shows what the cancel it sends is answered with, and invents nothing when nothing is said", async ({
      page: target,
    }) => {
      await target.clock.install();
      await prepare(target, shape);
      const dialog = await startSignIn(target, shape);
      await observedAttempt(target);
      await target.evaluate(
        (logRef) =>
          window.__scenarioProviderSignIn!.answerNextCancelWith({
            cause: "cleanup_unconfirmed",
            next_step: "close_other_sign_in",
            log_ref: logRef,
          }),
        LOG_REF,
      );
      await target.clock.fastForward("05:10");
      const alert = dialog.locator('p[role="alert"]').first();
      await expect(alert).toContainText(
        label("desktop.providers.sign_in_timeout"),
      );
      await expect(alert).toHaveAttribute("data-cause", "cleanup_unconfirmed");
      await expect(alert).toHaveAttribute("data-log-ref", LOG_REF);
      await expect(dialog).toContainText(
        label("desktop.providers.sign_in_cause.cleanup_unconfirmed"),
      );
      await expectLogRef(dialog);
    });

    test("a timeout of an attempt about which nothing was said states no cause", async ({
      page: target,
    }) => {
      await target.clock.install();
      await prepare(target, shape);
      const dialog = await startSignIn(target, shape);
      await observedAttempt(target);
      await target.clock.fastForward("05:10");
      const alert = dialog.locator('p[role="alert"]').first();
      await expect(alert).toContainText(
        label("desktop.providers.sign_in_timeout"),
      );
      await expect(alert).toHaveAttribute("data-reason", "timeout");
      await expect(alert).not.toHaveAttribute("data-cause", /.*/);
      await expect(alert).not.toHaveAttribute("data-log-ref", /.*/);
      await expect(dialog.locator('[data-slot="sign-in-log-ref"]')).toHaveCount(
        0,
      );
      await expect(dialog.locator('[data-slot="sign-in-advice"]')).toHaveCount(
        0,
      );
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

test.describe("a start refused while the agent is stopped for a terminal sign-in", () => {
  const shape = SHAPES[0]!;
  const AGENT_STOPPING = {
    cause: "agent_tree_running",
    next_step: "retry",
    log_ref: LOG_REF,
  };

  test("says the agent is being stopped as progress and starts again on its own once it is gone", async ({
    page: target,
  }) => {
    await prepare(target, shape);
    await target.evaluate(
      (detail) =>
        window.__scenarioProviderSignIn!.rejectNextStart("busy", detail, 2),
      AGENT_STOPPING,
    );
    const dialog = await startSignIn(target, shape);
    const progress = dialog.locator('[data-slot="sign-in-agent-stopping"]');
    await expect(progress).toHaveAttribute("role", "status");
    await expect(progress).toContainText(
      label("desktop.providers.sign_in_agent_stopping", {
        provider: shape.displayName,
      }),
    );
    await expect(progress).toHaveAttribute("data-reason", "busy");
    await expect(progress).toHaveAttribute("data-cause", "agent_tree_running");
    await expect(progress).toHaveAttribute("data-next-step", "retry");
    await expect(progress).toHaveAttribute("data-log-ref", LOG_REF);
    await expect(dialog.getByRole("alert")).toHaveCount(0);
    await expect(dialog).not.toContainText(
      label("desktop.providers.sign_in_busy", { provider: shape.displayName }),
    );
    await expect(
      dialog.getByRole("button", {
        name: label("desktop.providers.sign_in_retry"),
      }),
    ).toHaveCount(0);
    // Two refusals, then the third start, made by the window alone, is let
    // through and reaches the provider's page.
    await expect
      .poll(async () => starts(await signInCalls(target)), { timeout: 15_000 })
      .toBe(3);
    await expect(dialog.locator("[data-attempt-id]")).toHaveCount(1, {
      timeout: 10_000,
    });
    await expect(progress).toHaveCount(0);
    await expect(dialog.getByRole("alert")).toHaveCount(0);
    await target.evaluate(() =>
      window.__scenarioProviderSignIn!.succeedCurrentAttempt(true),
    );
    await expect(dialog).toHaveCount(0);
  });

  test("another busy cause is still said as another sign-in and waits for the person's retry", async ({
    page: target,
  }) => {
    await prepare(target, shape);
    await target.evaluate(
      (logRef) =>
        window.__scenarioProviderSignIn!.rejectNextStart("busy", {
          cause: "sign_in_owner_held",
          next_step: "close_other_sign_in",
          log_ref: logRef,
        }),
      LOG_REF,
    );
    const dialog = await startSignIn(target, shape);
    const alert = dialog.locator('p[role="alert"]');
    await expect(alert).toContainText(
      label("desktop.providers.sign_in_busy", { provider: shape.displayName }),
    );
    await expect(alert).toHaveAttribute("data-cause", "sign_in_owner_held");
    await expect(
      dialog.locator('[data-slot="sign-in-agent-stopping"]'),
    ).toHaveCount(0);
    await expect(
      dialog.getByRole("button", {
        name: label("desktop.providers.sign_in_retry"),
      }),
    ).toBeVisible();
    await target.waitForTimeout(4_000);
    expect(starts(await signInCalls(target))).toBe(1);
  });

  test("gives up on its own retries after their bound and offers the person's retry with the cause", async ({
    page: target,
  }) => {
    await target.clock.install();
    await prepare(target, shape);
    await target.evaluate(
      (detail) =>
        window.__scenarioProviderSignIn!.rejectNextStart("busy", detail, 1_000),
      AGENT_STOPPING,
    );
    const dialog = await startSignIn(target, shape);
    const progress = dialog.locator('[data-slot="sign-in-agent-stopping"]');
    await expect(progress).toBeVisible();
    for (let elapsed = 0; elapsed < 75_000; elapsed += 2_500)
      await target.clock.runFor(2_500);
    const alert = dialog.locator('p[role="alert"]').first();
    await expect(alert).toContainText(
      label("desktop.providers.sign_in_agent_still_running", {
        provider: shape.displayName,
      }),
    );
    await expect(alert).toHaveAttribute("data-cause", "agent_tree_running");
    await expect(alert).toHaveAttribute("data-log-ref", LOG_REF);
    await expect(progress).toHaveCount(0);
    await expect(
      dialog.getByRole("button", {
        name: label("desktop.providers.sign_in_retry"),
      }),
    ).toBeVisible();
    const given = starts(await signInCalls(target));
    expect(given).toBeGreaterThan(1);
    // Retries stop at the bound: nothing more is started without the person.
    await target.clock.runFor(15_000);
    expect(starts(await signInCalls(target))).toBe(given);
  });
});
