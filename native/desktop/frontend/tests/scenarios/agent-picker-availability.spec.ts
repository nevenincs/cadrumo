import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import {
  agentColumn as column,
  openModelPicker,
  pickWay,
  scenarioOnly,
} from "../support/agent";
import { connectionLabel } from "../support/connection";
import { label } from "../support/strings";

// What the picker offers follows what the service says it has read. A lane
// the service is still reading, or one whose models could not be read, is
// held back with the way on, and the column keeps asking until the service
// has settled it, so the lane becomes choosable without a reload. A choice
// the person made survives the lane being held back for a while. Hints about
// downloading models belong to the lanes whose models are downloaded.

test.beforeEach(() => {
  scenarioOnly("The scenario host decides what the service has read.");
});

test.describe.configure({ timeout: 90_000 });

const lanes = FIXTURE_CATALOG.providers ?? [];
const wayOf = (served: { provider_id: string; transport: string }) =>
  `${served.provider_id}/${served.transport}`;
const laneOf = (way: string) => {
  const served = lanes.find((held) => wayOf(held) === way);
  if (!served) throw new Error(`The fixture catalog has no lane ${way}.`);
  return served;
};

// The lane the column starts on, a hosted lane it can switch to, a hosted lane
// that is signed out, and the lane whose models are downloaded.
const START = "kimi/api";
const READ = "qwen/api";
const SIGNED_OUT = "kimi/cli";
const LOCAL = "zai/api";

/** The service has not yet read the lane's catalog: nothing is known of its
 * sign-in, models or admission, and it cannot be chosen. */
const UNREAD = {
  health: {
    authentication: "unknown",
    catalog: "unknown",
    admission: "unknown",
    selectable: false,
  },
  catalogStatus: "unknown",
} as const;
/** The service has read the lane's models, but not yet whether it is signed
 * in. */
const SIGN_IN_UNKNOWN = {
  health: { authentication: "unknown", selectable: false },
} as const;

const open = (target: Page, extra = "") =>
  target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready${extra}`,
  );
const reads = (target: Page) =>
  target.evaluate(
    () =>
      (window.__scenarioHostCalls ?? []).filter(
        (call) => call === "agentProviderCatalogResolved",
      ).length,
  );
/** Serves the lanes as `states` says from the start of the page. */
const served = (target: Page, states: Record<string, unknown>) =>
  target.addInitScript((held) => {
    window.__fixtureLaneStates = held as typeof window.__fixtureLaneStates;
  }, states);
/** The service has settled every lane it was reading. */
const settle = (target: Page) =>
  target.evaluate(() => {
    window.__fixtureLaneStates = {};
  });

const laneRow = (target: Page, way: string) =>
  target.locator(`[role=option][data-way="${way}"]`);

/** Opens the picker's provider list, reads one lane's row and closes it. */
async function rowState(target: Page, way: string) {
  const picker = await openModelPicker(target);
  await picker
    .getByRole("button", { name: label("desktop.agent.provider") })
    .click();
  const row = laneRow(target, way);
  await expect(row).toBeVisible();
  const state = {
    disabled: (await row.getAttribute("data-disabled")) === "true",
    text: (await row.textContent()) ?? "",
  };
  await target.keyboard.press("Escape");
  await expect(target.getByRole("listbox")).toBeHidden();
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();
  return state;
}

test("a lane first served as still being read becomes choosable without a reload", async ({
  page: target,
}) => {
  await served(target, { [READ]: UNREAD });
  await open(target);
  await expect.poll(() => reads(target)).toBe(1);
  const held = await rowState(target, READ);
  expect(held.disabled).toBe(true);
  expect(held.text).toContain(label("desktop.agent.lane_no_catalog"));

  // The service settles the lane; the column asks again by itself.
  await settle(target);
  const before = await reads(target);
  await expect
    .poll(() => reads(target), { timeout: 20_000 })
    .toBeGreaterThan(before);
  const settled = await rowState(target, READ);
  expect(settled.disabled).toBe(false);
});

test("a lane whose sign-in the service has not yet read is read again until it is signed in", async ({
  page: target,
}) => {
  await served(target, { [READ]: SIGN_IN_UNKNOWN });
  await open(target);
  await expect.poll(() => reads(target)).toBe(1);
  expect((await rowState(target, READ)).disabled).toBe(true);

  // The sign-in has completed: the next read states it, with nothing opened.
  await settle(target);
  const before = await reads(target);
  await expect
    .poll(() => reads(target), { timeout: 20_000 })
    .toBeGreaterThan(before);
  expect((await rowState(target, READ)).disabled).toBe(false);
});

test("a lane held back for models that could not be read offers asking again, and is choosable after", async ({
  page: target,
}) => {
  await served(target, { [READ]: UNREAD });
  await open(target);
  const picker = await openModelPicker(target);
  const held = picker.locator(`[data-held-way="${READ}"]`);
  await expect(held).toContainText(label("desktop.agent.lane_no_catalog"));
  const retry = held.getByRole("button", {
    name: label("desktop.agent.retry"),
    exact: true,
  });
  await expect(retry).toBeVisible();
  await settle(target);
  await retry.click();
  await expect(held).toHaveCount(0);
  await picker
    .getByRole("button", { name: label("desktop.agent.provider") })
    .click();
  await expect(laneRow(target, READ)).not.toHaveAttribute(
    "data-disabled",
    "true",
  );
});

test("a lane that is signed out offers signing in, which opens the settings", async ({
  page: target,
}) => {
  expect(laneOf(SIGNED_OUT).health.authentication).toBe("unauthenticated");
  await open(target);
  const picker = await openModelPicker(target);
  const held = picker.locator(`[data-held-way="${SIGNED_OUT}"]`);
  await expect(held).toContainText(label("desktop.agent.lane_signed_out"));
  await held
    .getByRole("button", {
      name: label("desktop.providers.sign_in_action"),
      exact: true,
    })
    .click();
  await expect(picker).toBeHidden();
  await expect(
    column(target).getByRole("region", {
      name: label("desktop.providers.title"),
    }),
  ).toBeVisible();
});

test("a lane held back for what the person cannot repair here offers no step", async ({
  page: target,
}) => {
  await open(target);
  const picker = await openModelPicker(target);
  // The lanes whose program is not installed or that have no key.
  for (const served of lanes) {
    if (
      served.health.transport === "unavailable" ||
      served.health.configured === "unavailable"
    )
      await expect(
        picker.locator(`[data-held-way="${wayOf(served)}"]`),
      ).toHaveCount(0);
  }
});

test("opening the model picker reads the catalog again, once", async ({
  page: target,
}) => {
  await open(target);
  await expect.poll(() => reads(target)).toBe(1);
  const picker = await openModelPicker(target);
  await expect.poll(() => reads(target)).toBe(2);
  await target.waitForTimeout(500);
  expect(await reads(target)).toBe(2);
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();
  await openModelPicker(target);
  await expect.poll(() => reads(target)).toBe(3);
});

test("the hint to download models shows under the lane whose models are downloaded, never under a hosted one", async ({
  page: target,
}) => {
  expect(laneOf(START).model_download).toBe("none");
  expect(laneOf(LOCAL).model_download).toBe("required");
  await open(target);
  const picker = await openModelPicker(target);
  // The column starts on a hosted lane.
  await expect(picker).not.toContainText(
    label("desktop.agent.models_to_download"),
  );
  await expect(
    picker.getByRole("button", {
      name: label("desktop.agent.download_models"),
      exact: true,
    }),
  ).toHaveCount(0);
  await pickWay(target, picker, LOCAL);
  await expect(picker).toContainText(label("desktop.agent.models_to_download"));
  await pickWay(target, picker, START);
  await expect(picker).not.toContainText(
    label("desktop.agent.models_to_download"),
  );
});

test("with no provider to choose, the model field asks for a provider rather than saying there are no models", async ({
  page: target,
}) => {
  await open(target, "&catalog=hosted-signed-out&models=none");
  const picker = await openModelPicker(target);
  await expect(picker).toContainText(
    label("desktop.agent.choose_provider_first"),
  );
  await expect(picker).not.toContainText(label("desktop.agent.no_models"));
});

test("a model the person chose comes back with its lane after the lane is held back for a while", async ({
  page: target,
}) => {
  const model = laneOf(READ).catalog.models?.at(-1);
  if (!model) throw new Error("The fixture lane lists no model.");
  await open(target);
  let picker = await openModelPicker(target);
  await pickWay(target, picker, READ);
  await picker
    .getByLabel(label("desktop.agent.model"))
    .selectOption(model.entry_id);
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();

  // The lane is not choosable for a while: the picker is on another lane.
  await target.evaluate((state) => {
    window.__fixtureLaneStates = { "qwen/api": state } as never;
  }, UNREAD);
  const before = await reads(target);
  picker = await openModelPicker(target);
  await expect.poll(() => reads(target)).toBeGreaterThan(before);
  const provider = picker.getByRole("button", {
    name: label("desktop.agent.provider"),
  });
  await expect(provider).not.toHaveAccessibleName(
    `${label("desktop.agent.provider")}: ${laneOf(READ).display_name}, ${connectionLabel(laneOf(READ))}`,
  );
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();

  // It is read again and choosable: the choice is the one made before.
  await settle(target);
  const waited = await reads(target);
  await expect
    .poll(() => reads(target), { timeout: 20_000 })
    .toBeGreaterThan(waited);
  picker = await openModelPicker(target);
  await expect(
    picker.getByRole("button", { name: label("desktop.agent.provider") }),
  ).toHaveAccessibleName(
    `${label("desktop.agent.provider")}: ${laneOf(READ).display_name}, ${connectionLabel(laneOf(READ))}`,
  );
  await expect(picker.getByLabel(label("desktop.agent.model"))).toHaveValue(
    model.entry_id,
  );
});
