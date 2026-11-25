import { expect, test, type Page } from "@playwright/test";
import { scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// A lane the service can sign out serves `sign_out_available`; only then does
// the lane offer Sign out, beside its switch. Signing out answers with the
// lane as the service then serves it, signed out. A refusal says its cause
// and the reference of the log line that records it.

test.beforeEach(() => {
  scenarioOnly("The scenario host decides which lanes it can sign out.");
});

// The made-up agent declares a logout for this lane alone.
const SIGNED_OUT_BY_AGENT = "antigravity_cli";
// Signed in as well, but the made-up agent declares no logout for it.
const NO_LOGOUT = "qwen_cli";

const SIGNED_IN = {
  cli_state: "installed_signed_in",
  mode: "provider_sign_in",
  available: true,
  readiness: "ready",
  reason: null,
} as const;

const settings = (target: Page, language = "en") =>
  target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title", {}, language),
  });

const lane = (target: Page, id: string, language = "en") =>
  settings(target, language).locator(`li[data-lane="${id}"]`);

const signOut = (target: Page, id: string, language = "en") =>
  lane(target, id, language).getByRole("button", {
    name: label("desktop.providers.sign_out_action", {}, language),
  });

async function openSignedIn(target: Page, language = "en") {
  await target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&lang=${language}`,
  );
  await target.evaluate(
    ({ ids, state }) => {
      for (const id of ids)
        window.__scenarioProviderSignIn!.leaveLaneUnconfirmed(id, state);
    },
    { ids: [SIGNED_OUT_BY_AGENT, NO_LOGOUT], state: SIGNED_IN },
  );
  await target
    .locator(".pane-agent")
    .getByRole("button", {
      name: label("desktop.agent.settings", {}, language),
    })
    .click();
  await expect(settings(target, language)).toBeVisible();
  await settings(target, language)
    .locator("[data-slot=lane-expander][aria-expanded=false]")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => (node as HTMLElement).click()),
    );
}

const signOutCalls = (target: Page) =>
  target.evaluate(() =>
    (window.__scenarioHostCalls ?? []).filter((call) =>
      call.startsWith("providerSignOut "),
    ),
  );

for (const language of ["en", "es", "ca", "hu"] as const) {
  test(`a signed-in lane signs out from beside its switch in ${language}`, async ({
    page: target,
  }) => {
    await openSignedIn(target, language);
    const button = signOut(target, SIGNED_OUT_BY_AGENT, language);
    await expect(button).toBeVisible();
    await expect(button).toHaveAccessibleName(
      label(
        "desktop.providers.sign_out_label",
        { provider: "Example Gamma" },
        language,
      ),
    );
    // Only a lane the service serves as one it can sign out offers it.
    await expect(signOut(target, NO_LOGOUT, language)).toHaveCount(0);

    await button.click();
    await expect
      .poll(() => signOutCalls(target))
      .toEqual([`providerSignOut ${SIGNED_OUT_BY_AGENT}`]);
    await expect(signOut(target, SIGNED_OUT_BY_AGENT, language)).toHaveCount(0);
    await expect(
      lane(target, SIGNED_OUT_BY_AGENT, language).getByRole("button", {
        name: label("desktop.providers.sign_in_action", {}, language),
      }),
    ).toBeVisible();
  });
}

test("a refused sign-out says its cause and its log reference", async ({
  page: target,
}) => {
  await openSignedIn(target);
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.failNextSignOut("busy", {
      cause: "sign_in_in_progress",
      log_ref: "0a1b2c3d4e5f",
    }),
  );
  await signOut(target, SIGNED_OUT_BY_AGENT).click();
  const alert = lane(target, SIGNED_OUT_BY_AGENT).getByRole("alert");
  await expect(alert).toContainText(
    label("desktop.providers.sign_in_cause.sign_in_in_progress"),
  );
  await expect(alert).toContainText("0a1b2c3d4e5f");
  await expect(alert).not.toContainText("busy");
  // Still signed in, so it can be asked again.
  await expect(signOut(target, SIGNED_OUT_BY_AGENT)).toBeVisible();
});
