import { expect, test, type Page } from "@playwright/test";
import {
  FIXTURE_SETTINGS_LANES,
  FIXTURE_SIGN_IN_PROVIDERS,
} from "../../src/dev/providerSettingsFixture";
import { label } from "../support/strings";

// Why a provider sign-in or a status read did not settle, and what to do about
// it: the closed words the service serves, said in the window's own language,
// with the console command to run where the step is a console sign-in. A word
// the window does not know is dropped, and a lane whose state could not be
// confirmed is never called signed out.

const open = (target: Page) =>
  target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off&lang=en");

const settings = (target: Page) =>
  target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title"),
  });

const lane = (target: Page, id: string) =>
  settings(target).locator(`[data-lane="${id}"]`);

const statusMark = (card: ReturnType<typeof lane>) =>
  card.locator('[data-slot="provider-status"]');

const nameOf = (id: string) =>
  FIXTURE_SETTINGS_LANES.find((declared) => declared.id === id)?.display_name ??
  id;

const signInCapableLane = FIXTURE_SETTINGS_LANES.find(
  (declared) =>
    declared.auth_kind === "provider_sign_in_only" &&
    FIXTURE_SIGN_IN_PROVIDERS.includes(declared.provider),
)!;

async function openSettings(target: Page) {
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

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

const CONSOLE_COMMAND = (provider: string) =>
  `aeat config provider-login --provider ${provider}`;

test("a failed sign-in says why and what to do, with the console command to run when the step is a console sign-in", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextStart("provider_error", {
      cause: "cli_exited_early",
      next_step: "console_sign_in",
    }),
  );
  await lane(target, signInCapableLane.id)
    .getByRole("button", { name: label("desktop.providers.sign_in_action") })
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_provider_error", {
      provider: nameOf(signInCapableLane.id),
    }),
  );
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_cause.cli_exited_early"),
  );
  await expect(dialog).toContainText(
    label("desktop.providers.next_step.console_sign_in"),
  );
  await expect(dialog).toContainText(
    label("desktop.providers.console_command_label"),
  );
  await expect(dialog.locator("code")).toHaveText(
    CONSOLE_COMMAND(signInCapableLane.provider),
  );
  await expect(dialog).not.toContainText("cli_exited_early");
  await expect(dialog).not.toContainText("{provider}");
});

test("a next step that is not a console sign-in offers no command", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextStart("busy", {
      cause: "login_already_running",
      next_step: "close_other_sign_in",
    }),
  );
  await lane(target, signInCapableLane.id)
    .getByRole("button", { name: label("desktop.providers.sign_in_action") })
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_cause.login_already_running"),
  );
  await expect(dialog).toContainText(
    label("desktop.providers.next_step.close_other_sign_in"),
  );
  await expect(dialog.locator("code")).toHaveCount(0);
  await expect(dialog).not.toContainText(
    label("desktop.providers.console_command_label"),
  );
});

test("a word the window does not know is dropped, not shown", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextStart("provider_error", {
      cause: "raw provider output",
      next_step: "reboot",
    }),
  );
  await lane(target, signInCapableLane.id)
    .getByRole("button", { name: label("desktop.providers.sign_in_action") })
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toContainText(
    label("desktop.providers.sign_in_provider_error", {
      provider: nameOf(signInCapableLane.id),
    }),
  );
  await expect(dialog).not.toContainText("raw provider output");
  await expect(dialog).not.toContainText("reboot");
});

test("a lane whose state could not be confirmed does not say it is signed out", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate((id) => {
    window.__scenarioProviderSignIn!.leaveLaneUnconfirmed(id, {
      cli_state_cause: "probe_timed_out",
      next_step: "console_sign_in",
    });
  }, signInCapableLane.id);
  await openSettings(target);
  const card = lane(target, signInCapableLane.id);
  await expect(statusMark(card)).toHaveAttribute("data-status", "unconfirmed");
  await expect(statusMark(card)).toHaveText(
    label("desktop.providers.status_unconfirmed"),
  );
  await expect(card).toContainText(
    label("desktop.providers.sign_in_cause.probe_timed_out"),
  );
  await expect(card).toContainText(
    label("desktop.providers.next_step.console_sign_in"),
  );
  await expect(card.locator("code")).toHaveText(
    CONSOLE_COMMAND(signInCapableLane.provider),
  );
  await expect(card).not.toContainText(
    label("desktop.providers.status_sign_in_needed"),
  );
  await expect(card).not.toContainText(
    label("desktop.providers.detail_sign_in", {
      provider: nameOf(signInCapableLane.id),
    }),
  );
});

test("a lane signed out for certain still says it is not signed in", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate((id) => {
    window.__scenarioProviderSignIn!.leaveLaneUnconfirmed(id, {
      cli_state: "installed_signed_out",
    });
  }, signInCapableLane.id);
  await openSettings(target);
  const card = lane(target, signInCapableLane.id);
  await expect(statusMark(card)).toHaveAttribute(
    "data-status",
    "sign_in_needed",
  );
  await expect(card).toContainText(
    label("desktop.providers.detail_sign_in", {
      provider: nameOf(signInCapableLane.id),
    }),
  );
});
