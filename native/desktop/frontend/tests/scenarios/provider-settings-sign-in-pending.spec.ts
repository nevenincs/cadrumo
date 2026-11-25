import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_SETTINGS_LANES } from "../../src/dev/providerSettingsFixture";
import { label } from "../support/strings";

// While the service still reads a lane's sign-in methods (`reads_pending`), a
// lane that signs in only through its provider and has no served method says
// sign-in is being checked; only a complete answer without a method says
// sign-in is unavailable. Each such lane names where it stands in
// `data-sign-in`, which the package smoke waits on.

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

async function openLane(target: Page) {
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  const lane = settings(target).locator(`[data-lane="${SIGN_IN_LANE.id}"]`);
  await expect(lane).toBeAttached();
  await settings(target)
    .locator("[data-slot=lane-expander][aria-expanded=false]")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => (node as HTMLElement).click()),
    );
  return lane;
}

const unavailable = () =>
  label("desktop.providers.sign_in_unavailable", {
    provider: SIGN_IN_LANE.display_name,
  });

test("a sign-in lane whose methods are still being read says it is checking, then offers sign-in once they are served", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate((provider) => {
    const controls = window.__scenarioProviderSignIn!;
    controls.offerSignIn([provider]);
    controls.setMethods(["browser"]);
    controls.pendSignInReads(1);
  }, SIGN_IN_LANE.provider);
  const lane = await openLane(target);

  const checking = lane
    .getByRole("status")
    .filter({ hasText: label("desktop.providers.sign_in_checking") });
  await expect(lane).toHaveAttribute("data-sign-in", "pending");
  await expect(checking).toBeVisible();
  await expect(lane.getByRole("note")).toHaveCount(0);
  await expect(lane.getByText(unavailable())).toHaveCount(0);

  // The service's read of the methods ends and it cues the window: the next
  // read serves them and says the answer is complete.
  await target.evaluate(() => window.__scenarioProviderSignIn!.settleReads());
  await expect(lane).toHaveAttribute("data-sign-in", "offered");
  await expect(
    lane.getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    }),
  ).toBeVisible();
  await expect(checking).toHaveCount(0);
  await expect(lane.getByText(unavailable())).toHaveCount(0);
});

test("a complete answer without a sign-in method says sign-in is unavailable", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(() => {
    window.__scenarioProviderSignIn!.offerSignIn([]);
  });
  const lane = await openLane(target);

  await expect(lane).toHaveAttribute("data-sign-in", "unavailable");
  await expect(
    lane.getByRole("note").filter({ hasText: unavailable() }),
  ).toBeVisible();
  await expect(
    lane
      .getByRole("status")
      .filter({ hasText: label("desktop.providers.sign_in_checking") }),
  ).toHaveCount(0);
});
