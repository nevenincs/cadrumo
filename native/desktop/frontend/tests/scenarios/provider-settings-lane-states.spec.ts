import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_SETTINGS_LANES } from "../../src/dev/providerSettingsFixture";
import { label } from "../support/strings";

// What a lane's card says of itself stays true to what the host served: a
// settled standing is not unsaid by an answer that is still being completed,
// a signed-in lane offers only to sign out, and a key lane without a key does
// not read as on.

const open = (target: Page) =>
  target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off&lang=en");

const settings = (target: Page) =>
  target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title"),
  });

const lane = (target: Page, id: string) =>
  settings(target).locator(`[data-lane="${id}"]`);

const settingsButton = (target: Page) =>
  target.locator(".pane-agent").getByRole("button", {
    name: label("desktop.agent.settings"),
  });

async function openSettings(target: Page) {
  await settingsButton(target).click();
  await expect(settings(target)).toBeVisible();
  await settings(target)
    .locator("li[data-provider] > details")
    .evaluateAll((nodes) =>
      nodes.forEach((node) => ((node as HTMLDetailsElement).open = true)),
    );
}

// The made-up lane whose provider declares a logout, so a signed-in one can
// be signed out.
const SIGN_OUT_LANE = FIXTURE_SETTINGS_LANES.find(
  (declared) => declared.id === "antigravity_cli",
)!;
const KEY_LANE = FIXTURE_SETTINGS_LANES.find(
  (declared) => declared.auth_kind === "api_key",
)!;

const SIGNED_IN = {
  cli_state: "installed_signed_in",
  readiness: "ready",
} as const;
const UNREAD = { cli_state: "unknown", readiness: "not_verified" } as const;

test("a settled connected status is not unsaid while a later answer is still being completed", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(
    ([id, state]) => {
      const controls = window.__scenarioProviderSignIn!;
      controls.offerSignIn(["antigravity"]);
      controls.setMethods(["browser"]);
      controls.leaveLaneUnconfirmed(id, state);
      // Every status the card shows, in order, from here on.
      const seen: string[] = [];
      (window as unknown as { __seen: string[] }).__seen = seen;
      new MutationObserver(() => {
        const mark = document.querySelector(
          `[data-lane="${id}"] [data-slot="provider-status"]`,
        );
        const status = mark?.getAttribute("data-status");
        if (status && seen[seen.length - 1] !== status) seen.push(status);
      }).observe(document.body, {
        subtree: true,
        childList: true,
        attributes: true,
      });
    },
    [SIGN_OUT_LANE.id, SIGNED_IN] as const,
  );
  await openSettings(target);
  await expect(
    lane(target, SIGN_OUT_LANE.id).locator("[data-slot=provider-status]"),
  ).toHaveAttribute("data-status", "ready");

  // The settings are read again; the service answers while its apps are still
  // being read (nothing settled yet), then completes.
  await settingsButton(target).click();
  await target.evaluate(
    ([id, state]) => {
      const controls = window.__scenarioProviderSignIn!;
      controls.leaveLaneUnconfirmed(id, state);
      controls.pendSignInReads(1);
      controls.deferNextStatus();
    },
    [SIGN_OUT_LANE.id, UNREAD] as const,
  );
  await settingsButton(target).click();
  await expect(settings(target)).toBeVisible();
  const resolvedReads = () =>
    target.evaluate(
      () =>
        (window.__scenarioHostCalls ?? []).filter(
          (call) => call === "providerStatusResolved",
        ).length,
    );
  const before = await resolvedReads();
  await target.evaluate(() =>
    window.__scenarioProviderSignIn!.completeStatus(),
  );
  // The pending answer has been served; only now does the app report again.
  await expect.poll(resolvedReads).toBe(before + 1);
  // The app reports again, and the service cues the window that its reads
  // behind the pending answer have ended.
  await target.evaluate(
    ([id, state]) => {
      const controls = window.__scenarioProviderSignIn!;
      controls.leaveLaneUnconfirmed(id, state);
      controls.settleReads();
    },
    [SIGN_OUT_LANE.id, SIGNED_IN] as const,
  );
  await expect.poll(resolvedReads).toBe(before + 2);
  await expect(
    lane(target, SIGN_OUT_LANE.id).locator("[data-slot=provider-status]"),
  ).toHaveAttribute("data-status", "ready");
  const seen = await target.evaluate(
    () => (window as unknown as { __seen: string[] }).__seen,
  );
  expect(seen).toEqual(["ready"]);
});

test("a lane that was turned on and signed out in the host shows the change at once", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(
    ([id, state]) => {
      const controls = window.__scenarioProviderSignIn!;
      controls.leaveLaneUnconfirmed(id, state);
    },
    [SIGN_OUT_LANE.id, SIGNED_IN] as const,
  );
  await openSettings(target);
  const card = lane(target, SIGN_OUT_LANE.id);
  await expect(card.locator("[data-slot=provider-status]")).toHaveAttribute(
    "data-status",
    "ready",
  );
  await card
    .getByRole("button", {
      name: label("desktop.providers.sign_out_label", {
        provider: SIGN_OUT_LANE.display_name,
      }),
    })
    .click();
  await expect(card.locator("[data-slot=provider-status]")).toHaveAttribute(
    "data-status",
    "sign_in_needed",
  );
});

test("a signed-in lane offers only to sign out, and a signed-out one only to sign in", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(
    ([id, state]) => {
      const controls = window.__scenarioProviderSignIn!;
      controls.offerSignIn(["antigravity"]);
      controls.setMethods(["browser"]);
      controls.leaveLaneUnconfirmed(id, state);
    },
    [SIGN_OUT_LANE.id, SIGNED_IN] as const,
  );
  await openSettings(target);
  const card = lane(target, SIGN_OUT_LANE.id);
  await expect(
    card.getByRole("button", {
      name: label("desktop.providers.sign_out_label", {
        provider: SIGN_OUT_LANE.display_name,
      }),
    }),
  ).toBeVisible();
  await expect(
    card.getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    }),
  ).toHaveCount(0);

  await card
    .getByRole("button", {
      name: label("desktop.providers.sign_out_label", {
        provider: SIGN_OUT_LANE.display_name,
      }),
    })
    .click();
  await expect(
    card.getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
    }),
  ).toBeVisible();
  await expect(
    card.getByRole("button", {
      name: label("desktop.providers.sign_out_label", {
        provider: SIGN_OUT_LANE.display_name,
      }),
    }),
  ).toHaveCount(0);
});

test("a key lane with no key is not on, and adding a key turns it on", async ({
  page: target,
}) => {
  await open(target);
  await openSettings(target);
  const card = lane(target, KEY_LANE.id);
  const toggle = card.getByRole("switch");
  await expect(toggle).not.toBeChecked();
  await expect(toggle).toBeDisabled();
  await card
    .getByRole("button", { name: label("desktop.providers.add_key") })
    .click();
  await card
    .getByLabel(new RegExp(`^${KEY_LANE.display_name} `))
    .fill("FAKE-KEY-not-a-real-key-0000");
  await card
    .getByRole("button", { name: label("desktop.providers.save") })
    .click();
  await expect(toggle).toBeChecked();
  await expect(toggle).toBeEnabled();
});
