import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_SETTINGS_LANES } from "../../src/dev/providerSettingsFixture";
import { label } from "../support/strings";

// The service answers the provider status at once and reads the sign-in
// routes behind that answer, which then offers none and says so with
// `reads_pending`. Once that read ends the service cues the window, whose
// host publishes the status again, and the settings read the status on that
// cue, so a provider's sign-in is offered without the settings being opened
// again; a complete answer is not read again, by a cue or by time.

const open = (target: Page) =>
  target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off&lang=en");

const settings = (target: Page) =>
  target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title"),
  });

// The made-up command-line lane that signs in through its provider, as
// Claude's and Codex's do.
const SIGN_IN_LANE = FIXTURE_SETTINGS_LANES.find(
  (declared) => declared.auth_kind === "provider_sign_in_only",
)!;

const statusReads = async (target: Page) =>
  (await target.evaluate(() => window.__scenarioHostCalls ?? [])).filter(
    (call) => call === "providerStatus",
  ).length;

test("a provider's sign-in read behind a pending status is offered without opening the settings again, and a complete status is not read again", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate((provider) => {
    const controls = window.__scenarioProviderSignIn!;
    controls.offerSignIn([provider]);
    controls.setMethods(["browser"]);
    controls.pendSignInReads(1);
  }, SIGN_IN_LANE.provider);
  const before = await statusReads(target);
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  const lane = settings(target).locator(`[data-lane="${SIGN_IN_LANE.id}"]`);
  await expect(lane).toBeAttached();
  await settings(target)
    .locator("li[data-provider] > details")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => ((node as HTMLDetailsElement).open = true)),
    );
  const signIn = lane.getByRole("button", {
    name: label("desktop.providers.sign_in_action"),
  });
  // The pending answer offers no sign-in, and nothing reads it again by time.
  await expect(lane).toHaveAttribute("data-sign-in", "pending");
  await target.waitForTimeout(1_500);
  expect((await statusReads(target)) - before).toBe(1);
  // The service's read behind it ends and it cues the window: the complete
  // answer that follows offers the sign-in.
  await target.evaluate(() => window.__scenarioProviderSignIn!.settleReads());
  await expect(signIn).toBeVisible();
  const settled = await statusReads(target);
  expect(settled - before).toBe(2);

  // A complete answer is not read again, on a later publication or by time.
  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await target.waitForTimeout(1_500);
  expect(await statusReads(target)).toBe(settled);
});
