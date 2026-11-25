import { expect, test, type Locator, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import {
  agentColumn as column,
  matrixCell,
  matrixLane,
  matrixRows,
  offeredModels,
  openModelPicker,
  pickWay,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

// What the picker offers follows what the service says it has read. A lane
// the service is still reading, or one whose models could not be read, is
// held back with the way on, and the column asks again on a cue (the person
// coming back to the window, opening the picker, a published status), never
// on a timer, so the lane becomes choosable without a reload. A choice
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
/** The person comes back to the window. */
const comeBack = (target: Page) =>
  target.evaluate(() => window.dispatchEvent(new Event("focus")));

/** The cells of the lane `way`'s models that can be chosen. */
const choosableCells = (picker: Locator, way: string) =>
  matrixRows(picker, way).locator("[role=radio]:not([aria-disabled])");

/** The cells chosen on the lane `way`. */
const chosenCells = (picker: Locator, way: string) =>
  matrixRows(picker, way).locator("[role=radio][aria-checked=true]");

/** The steps offered in the heading of the lane `way`. */
const laneSteps = (picker: Locator, way: string, step?: string) =>
  matrixLane(picker, way).locator(
    step ? `[data-held-step="${step}"]` : "[data-held-step]",
  );

/** Opens the picker, reads one lane's heading and closes it: whether the
 * lane can be chosen, and what its heading says. */
async function rowState(target: Page, way: string) {
  const picker = await openModelPicker(target);
  const row = matrixLane(picker, way);
  await expect(row).toBeVisible();
  const state = {
    disabled: (await row.getAttribute("data-standing")) !== "ready",
    choosable: await choosableCells(picker, way).count(),
    text: (await row.textContent()) ?? "",
  };
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
  expect(held.choosable).toBe(0);
  expect(held.text).toContain(label("desktop.agent.lane_no_catalog"));

  // The service settles the lane. Time alone asks nothing; the person
  // coming back to the window does.
  await settle(target);
  const before = await reads(target);
  await target.waitForTimeout(2_500);
  expect(await reads(target)).toBe(before);
  await comeBack(target);
  await expect.poll(() => reads(target)).toBe(before + 1);
  const settled = await rowState(target, READ);
  expect(settled.disabled).toBe(false);
  expect(settled.choosable).toBeGreaterThan(0);
});

test("a lane whose sign-in the service has not yet read is read again until it is signed in", async ({
  page: target,
}) => {
  await served(target, { [READ]: SIGN_IN_UNKNOWN });
  await open(target);
  await expect.poll(() => reads(target)).toBe(1);
  const held = await rowState(target, READ);
  expect(held.disabled).toBe(true);
  expect(held.choosable).toBe(0);

  // The sign-in has completed: the read on the person's return states it,
  // with nothing opened.
  await settle(target);
  const before = await reads(target);
  await comeBack(target);
  await expect.poll(() => reads(target)).toBe(before + 1);
  const settled = await rowState(target, READ);
  expect(settled.disabled).toBe(false);
  expect(settled.choosable).toBeGreaterThan(0);
});

test("a lane held back for models that could not be read offers asking again, and is choosable after", async ({
  page: target,
}) => {
  await served(target, { [READ]: UNREAD });
  await open(target);
  const picker = await openModelPicker(target);
  const held = matrixLane(picker, READ);
  await expect(held).toHaveAttribute("data-standing", "setup");
  await expect(held).toContainText(label("desktop.agent.lane_no_catalog"));
  const retry = held.getByRole("button", {
    name: label("desktop.agent.retry"),
    exact: true,
  });
  await expect(retry).toBeVisible();
  await settle(target);
  await retry.click();
  // Asked again, the lane is read and can be chosen in the same picker.
  await expect(held).toHaveAttribute("data-standing", "ready");
  await expect(held).not.toContainText(label("desktop.agent.lane_no_catalog"));
  await expect(laneSteps(picker, READ)).toHaveCount(0);
  await expect(choosableCells(picker, READ).first()).toBeVisible();
});

test("a lane that is signed out offers signing in, which opens the settings", async ({
  page: target,
}) => {
  expect(laneOf(SIGNED_OUT).health.authentication).toBe("unauthenticated");
  await open(target);
  const picker = await openModelPicker(target);
  const held = matrixLane(picker, SIGNED_OUT);
  await expect(held).toHaveAttribute("data-standing", "setup");
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

test("a lane held back for what the person cannot repair here offers only the way to its settings", async ({
  page: target,
}) => {
  await open(target);
  const picker = await openModelPicker(target);
  // The lanes whose program is not installed or that have no key: neither
  // signing in, asking again nor a download brings them into use.
  const unrepairable = lanes.filter(
    (served) =>
      served.health.transport === "unavailable" ||
      served.health.configured === "unavailable",
  );
  expect(unrepairable.length).toBeGreaterThan(0);
  for (const served of unrepairable) {
    const way = wayOf(served);
    await expect(matrixLane(picker, way)).toHaveAttribute(
      "data-standing",
      "setup",
    );
    await expect(laneSteps(picker, way)).toHaveCount(1);
    await expect(laneSteps(picker, way, "set_up")).toHaveCount(1);
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
  const downloadOf = (way: string) =>
    matrixLane(picker, way).getByRole("button", {
      name: label("desktop.agent.download_models"),
      exact: true,
    });
  // The column starts on a hosted lane; the hint stays with the lane whose
  // models are downloaded whichever lane is chosen.
  await expect(chosenCells(picker, START)).toHaveCount(1);
  await expect(downloadOf(START)).toHaveCount(0);
  await expect(laneSteps(picker, LOCAL, "download")).toHaveCount(1);
  await expect(downloadOf(LOCAL)).toBeVisible();
  await pickWay(target, picker, LOCAL);
  await expect(chosenCells(picker, LOCAL)).toHaveCount(1);
  await expect(downloadOf(LOCAL)).toBeVisible();
  await expect(downloadOf(START)).toHaveCount(0);
  await pickWay(target, picker, START);
  await expect(chosenCells(picker, START)).toHaveCount(1);
  await expect(downloadOf(START)).toHaveCount(0);
});

test("with no provider to choose, the picker says why of each lane rather than saying there are no models", async ({
  page: target,
}) => {
  await open(target, "&catalog=hosted-signed-out&models=none");
  const picker = await openModelPicker(target);
  // Each lane is listed with what holds it back and the step that brings it
  // into use; no model can be chosen yet.
  await expect(matrixLane(picker, SIGNED_OUT)).toContainText(
    label("desktop.agent.lane_signed_out"),
  );
  await expect(laneSteps(picker, SIGNED_OUT, "sign_in")).toHaveCount(1);
  await expect(matrixLane(picker, LOCAL)).toContainText(
    label("desktop.agent.lane_no_installed_model"),
  );
  await expect(laneSteps(picker, LOCAL, "download")).toHaveCount(1);
  await expect(picker.locator("tr[data-slot=model-matrix-row]")).toHaveCount(0);
  await expect(picker.locator("[role=radio][data-matrix-cell]")).toHaveCount(0);
  await expect(picker.locator("[data-slot=model-matrix-empty]")).toHaveCount(0);
});

test("a model the person chose comes back with its lane after the lane is held back for a while", async ({
  page: target,
}) => {
  const model = laneOf(READ).catalog.models?.at(-1);
  if (!model) throw new Error("The fixture lane lists no model.");
  await open(target);
  let picker = await openModelPicker(target);
  await pickWay(target, picker, READ);
  await matrixCell(picker, READ, model.entry_id).click();
  await expect(matrixCell(picker, READ, model.entry_id)).toHaveAttribute(
    "aria-checked",
    "true",
  );
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();

  // The lane is not choosable for a while: nothing on it is chosen.
  await target.evaluate((state) => {
    window.__fixtureLaneStates = { "qwen/api": state } as never;
  }, UNREAD);
  const before = await reads(target);
  picker = await openModelPicker(target);
  await expect.poll(() => reads(target)).toBeGreaterThan(before);
  await expect(matrixLane(picker, READ)).toHaveAttribute(
    "data-standing",
    "setup",
  );
  await expect(chosenCells(picker, READ)).toHaveCount(0);
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();

  // It is read again and choosable: the choice is the one made before.
  await settle(target);
  const waited = await reads(target);
  await comeBack(target);
  await expect.poll(() => reads(target)).toBe(waited + 1);
  picker = await openModelPicker(target);
  await expect(chosenCells(picker, READ)).toHaveCount(1);
  await expect(matrixCell(picker, READ, model.entry_id)).toHaveAttribute(
    "aria-checked",
    "true",
  );
});

declare global {
  interface Window {
    /** The refusal the made-up list read answers, while one is set. */
    __listsRefusal?: string | null;
  }
}

const listReads = (target: Page) =>
  target.evaluate(
    () =>
      (window.__scenarioHostCalls ?? []).filter(
        (call) => call === "agentLocalModels",
      ).length,
  );

// The person's model lists that cannot be read are said in the picker,
// never replaced in silence by everything the catalogue lists: a fault with
// asking again, or where setup stands.
for (const [code, role, words] of [
  ["agent_gateway_503", "alert", "desktop.providers.local_models_failed"],
  [
    "agent_local_models_catalog_unavailable",
    "status",
    "desktop.agent.catalog_unavailable",
  ],
] as const)
  test(`model lists the picker cannot read (${code}) are said there with asking again`, async ({
    page: target,
  }) => {
    await target.addInitScript((code) => {
      window.__listsRefusal = code;
      window.__fixtureLocalModelsRead = async () => {
        const refusal = window.__listsRefusal;
        if (refusal) throw Object.assign(new Error(refusal), { code: refusal });
      };
    }, code);
    await open(target);
    const picker = await openModelPicker(target);
    const said = picker.locator("[data-slot=picker-lists]");
    await expect(said).toHaveAttribute("role", role);
    await expect(said).toContainText(label(words));
    await target.evaluate(() => {
      window.__listsRefusal = null;
    });
    const asked = await listReads(target);
    await said
      .getByRole("button", { name: label("desktop.agent.retry"), exact: true })
      .click();
    await expect.poll(() => listReads(target)).toBeGreaterThan(asked);
    await expect(said).toHaveCount(0);
    // Read, the lists apply again: the local lane offers its list alone,
    // leaving out the model it serves that nobody put on the list.
    await pickWay(target, picker, LOCAL);
    expect(await offeredModels(picker, LOCAL)).toEqual([
      "synthetic-text:1",
      "synthetic-vision:1",
    ]);
  });
