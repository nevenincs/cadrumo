import { expect, test, type Locator, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import {
  agentColumn as column,
  openConversation,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

// The provider, way, model and effort the person last chose for the agent
// are where a new conversation starts, after a reload and a new sign-in, for
// the profile that chose them only. A conversation opened from the history
// runs with what it last ran with. Whatever was kept is checked against the
// catalog the agent serves now: what it no longer offers is not chosen.

const STORE = "cadrumo-agent-choice";

const lanes = FIXTURE_CATALOG.providers ?? [];
const wayOf = (served: { provider_id: string; transport: string }) =>
  `${served.provider_id}/${served.transport}`;
const laneOf = (way: string) => {
  const served = lanes.find((held) => wayOf(held) === way);
  if (!served) throw new Error(`The fixture catalog has no lane ${way}.`);
  return served;
};
// The lane the column starts on, another it lists models for, and one it
// holds back.
const START = "alpha/api";
const OTHER = "beta/cli";
const HELD = "alpha/cli";

const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const composerButton = (target: Page) =>
  column(target)
    .getByRole("button", {
      name: new RegExp(
        `^${escaped(label("desktop.agent.settings_label", { current: "" }))}`,
      ),
    })
    .first();

async function openSettings(target: Page) {
  await composerButton(target).click();
  const settings = target.getByRole("dialog", {
    name: label("desktop.agent.settings_title"),
  });
  await expect(settings).toBeVisible();
  return settings;
}

const providerBox = (settings: Locator) =>
  settings.getByRole("button", { name: label("desktop.agent.provider") });

/** The settings say the lane `way` is the one chosen. */
async function expectChosen(target: Page, way: string) {
  const settings = await openSettings(target);
  const served = laneOf(way);
  await expect(providerBox(settings)).toHaveAccessibleName(
    `${label("desktop.agent.provider")}: ${served.display_name}, ${label(
      served.transport === "api"
        ? "desktop.providers.connection_api"
        : "desktop.providers.connection_app",
    )}`,
  );
  await target.keyboard.press("Escape");
  await expect(settings).toBeHidden();
}

async function choose(target: Page, way: string) {
  const settings = await openSettings(target);
  await providerBox(settings).click();
  await target.locator(`[role=option][data-way="${way}"]`).click();
  await expect(target.getByRole("listbox")).toBeHidden();
  // The settings close from where the keyboard is in them.
  await providerBox(settings).focus();
  await target.keyboard.press("Escape");
  await expect(settings).toBeHidden();
}

/** What the shell keeps, by key. */
const kept = (target: Page) =>
  target.evaluate((prefix) => {
    const held: Record<string, string> = {};
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index);
      if (key?.startsWith(prefix)) held[key] = localStorage.getItem(key) ?? "";
    }
    return held;
  }, STORE);

/** Signs in from the scenario's sign-in to the profile named `profile`. */
async function signIn(target: Page, profile: string) {
  const dialog = target.locator(".sign-in");
  await dialog
    .getByLabel(label("desktop.signin.profile"), { exact: true })
    .selectOption({ label: profile });
  await target.locator("#profile-password").fill("anything");
  await dialog
    .getByRole("button", { name: label("desktop.signin.submit"), exact: true })
    .click();
  await expect(composerButton(target)).toBeVisible();
}

const open = (target: Page, scenario: string) =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);

test.beforeEach(async ({ page: target }) => {
  scenarioOnly("The kept choice is read off the scenario host's catalog.");
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("the last choice is where the next start begins, for the profile that made it", async ({
  page: target,
}) => {
  expect(laneOf(OTHER).health.selectable).toBe(true);
  expect(laneOf(OTHER).catalog.models?.length).toBeGreaterThan(0);
  expect(laneOf(HELD).health.selectable).toBe(false);
  await open(target, "signed-out");
  await signIn(target, "Demo profile");
  await expectChosen(target, START);
  await choose(target, OTHER);

  // One record, under a key that names no profile.
  const held = await kept(target);
  expect(Object.keys(held)).toHaveLength(1);
  for (const [key, value] of Object.entries(held)) {
    expect(key).toMatch(new RegExp(`^${STORE}:[0-9a-f]{64}$`));
    expect(`${key}${value}`).not.toContain("Demo");
  }

  // A restart signs in again and starts with it.
  await target.reload();
  await signIn(target, "Demo profile");
  await expectChosen(target, OTHER);

  // Another profile has none of it.
  await target.reload();
  await signIn(target, "Ana Soler Vidal");
  await expectChosen(target, START);
  await target.reload();
  await signIn(target, "Demo profile");
  await expectChosen(target, OTHER);
});

test("a kept choice the catalog no longer offers gives way to the starting one", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await choose(target, OTHER);
  const [key, value] = Object.entries(await kept(target))[0] ?? [];
  if (!key || !value) throw new Error("The choice was not kept.");
  const stored = JSON.parse(value) as Record<string, unknown>;
  const rewrite = (next: Record<string, unknown>) =>
    target.evaluate(([at, text]) => localStorage.setItem(at, text), [
      key,
      JSON.stringify({ ...stored, ...next }),
    ] as const);

  // A provider the catalog does not serve.
  await rewrite({ providerId: "retired", wayId: "retired/api" });
  await target.reload();
  await expectChosen(target, START);

  // A lane it serves but holds back.
  const held = laneOf(HELD);
  await rewrite({ providerId: held.provider_id, wayId: HELD });
  await target.reload();
  await expectChosen(target, START);

  // A model the lane no longer lists.
  await rewrite({ modelId: "retired-model" });
  await target.reload();
  await expectChosen(target, START);

  // An effort the model no longer takes is left out; the rest is kept.
  await rewrite({ effort: "retired-effort" });
  await target.reload();
  await expectChosen(target, OTHER);

  // Something that is not a choice at all.
  await target.evaluate((at) => localStorage.setItem(at, "{"), key);
  await target.reload();
  await expectChosen(target, START);
});

test("a conversation opened runs with its own choice, and a new one with the last", async ({
  page: target,
}) => {
  await open(target, "signed-in");
  await choose(target, OTHER);
  // The fixture conversation last ran on the starting lane.
  await openConversation(target, "IVA del tercer trimestre");
  await expectChosen(target, START);
  await column(target)
    .getByRole("button", { name: label("desktop.agent.new_conversation") })
    .click();
  await expectChosen(target, OTHER);
});
