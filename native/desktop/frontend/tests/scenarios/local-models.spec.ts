import { expect, test, type Locator, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import { catalogLanes } from "../../src/shell/localModelLanes";
import {
  offeredModels,
  openModelPicker,
  pickWay,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

// The local lane's model list: the catalog's recommended models, the ones the
// person adds by name, and a download and removal on each. The scenario host
// performs no real transfer.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

const LOCAL = "local_api";
const ADDED = "synthetic-named:test";
const localLane = catalogLanes(FIXTURE_CATALOG).find(
  (lane) => lane.id === LOCAL,
)!;

const open = (target: Page, setup = "ready") =>
  target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=${setup}`,
  );

const settings = (target: Page) =>
  target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title"),
  });

async function openLane(target: Page) {
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  await expect(settings(target)).toBeVisible();
  await settings(target)
    .locator('li[data-provider="local"] > details')
    .evaluate((node) => ((node as HTMLDetailsElement).open = true));
  return settings(target).locator(`[data-lane="${LOCAL}"]`);
}

/** The models the made-up service holds on the person's list. */
const storedList = (target: Page) =>
  target.evaluate(async () => {
    const list = await window.__fixtureAgentSession?.localModels?.();
    return list?.state === "readable" ? list.models : null;
  });

const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

/** Adds `model` to the open lane's list by name. */
async function addByName(lane: Locator, model: string) {
  await lane
    .getByLabel(label("desktop.providers.local_model_add_label"))
    .fill(model);
  await lane
    .getByRole("button", {
      name: label("desktop.providers.local_model_add"),
      exact: true,
    })
    .click();
}

test("the list holds the catalog's recommended models alone, with no capability labels", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  const models = lane.locator("[data-slot=local-models] li[data-model]");
  expect(localLane.recommended).toEqual([
    "synthetic-vision:1",
    "synthetic-text:1",
  ]);
  await expect(models).toHaveCount(localLane.recommended.length);
  expect(
    await models.evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-model")),
    ),
  ).toEqual(localLane.recommended);
  await expect(models.first()).toContainText(
    label("desktop.providers.local_model_absent"),
  );
  await expect(models.nth(1)).toContainText(
    label("desktop.providers.local_model_installed"),
  );
  // No model is said to be for one kind of reading, and no task picker shows.
  await expect(lane.locator("[data-recommended]")).toHaveCount(0);
  await expect(lane.getByRole("combobox")).toHaveCount(0);
  await expect(lane.getByRole("checkbox")).toHaveCount(0);
  await expect(
    target.locator(".pane-agent").getByText(/reading (images|text)/i),
  ).toHaveCount(0);
  expect(await storedList(target)).toEqual([]);
});

test("a model added by name joins the list after the recommended ones and is stored", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  await addByName(lane, ADDED);
  const models = lane.locator("[data-slot=local-models] li[data-model]");
  await expect(models).toHaveCount(localLane.recommended.length + 1);
  const added = models.last();
  await expect(added).toHaveAttribute("data-model", ADDED);
  await expect(added).toHaveAttribute("data-added", "true");
  await expect(
    lane.getByLabel(label("desktop.providers.local_model_add_label")),
  ).toHaveValue("");
  await expect
    .poll(() => storedList(target))
    .toEqual([{ lane: LOCAL, model: ADDED }]);
  // Adding a recommended model changes nothing.
  await addByName(lane, "synthetic-text:1");
  await expect(models).toHaveCount(localLane.recommended.length + 1);
  expect(await storedList(target)).toEqual([{ lane: LOCAL, model: ADDED }]);
});

test("the model picker offers the local lane's list, and a model added to it joins the picker", async ({
  page: target,
}) => {
  await open(target);
  let picker = await openModelPicker(target);
  await pickWay(target, picker, "local/api");
  // The lane serves a model nobody put on its list: the picker leaves it out.
  expect(await offeredModels(picker)).toEqual([
    "synthetic-text:1",
    "synthetic-vision:1",
  ]);
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();
  const lane = await openLane(target);
  await addByName(lane, "synthetic-plain:1");
  await expect(
    lane.locator('[data-slot=local-models] li[data-model="synthetic-plain:1"]'),
  ).toBeVisible();
  // Settings cover the composer; closing them brings the picker back.
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.settings") })
    .click();
  await expect(settings(target)).toBeHidden();
  picker = await openModelPicker(target);
  expect(await offeredModels(picker)).toContain("synthetic-plain:1");
});

/** The plan a model download awaits an answer on, in the local AI's own row
 * inside the lane. */
const laneReview = (lane: Locator) =>
  lane.locator('[data-setup-row="local_ai"] [data-setup-review]');

test("Download plans that model's setup in the lane, sized by the catalog where it states one", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  const vision = lane.locator('li[data-model="synthetic-vision:1"]');
  await vision
    .getByRole("button", {
      name: label("desktop.providers.local_model_download"),
    })
    .click();
  const review = laneReview(lane);
  await expect(review).toContainText(label("desktop.setup.lead_review"));
  // No other window opens: the plan is answered where it was asked for.
  await expect(target.getByRole("dialog")).toHaveCount(0);
  await expect(review.locator('[data-setup-plan="local_ai"]')).toHaveCount(1);
  await expect(review.locator('[data-setup-plan="browser"]')).toHaveCount(0);
  await expect
    .poll(() => calls(target))
    .toContain("setup.download local_api synthetic-vision:1");
  expect(await calls(target)).not.toContain("setup.answer apply");
  await expect(review).toContainText(label("desktop.setup.part_download"));
  await expect(review).toContainText("synthetic-vision:1");
  await review
    .getByRole("button", {
      name: label("desktop.setup.approve_size", { size: "3.2 GB" }),
    })
    .click();
  // The model's own entry shows its download; the program row shows none,
  // since the program is not part of this setup. Nothing opens over it.
  await expect(vision.locator("[data-setup-progress]")).toBeVisible();
  await expect(
    lane.locator('[data-setup-row="local_ai"] [data-setup-progress]'),
  ).toHaveCount(0);
  await expect(target.getByRole("dialog")).toHaveCount(0);
});

test("an added model downloads with its size unknown", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  await addByName(lane, ADDED);
  await lane
    .locator(`li[data-model="${ADDED}"]`)
    .getByRole("button", {
      name: label("desktop.providers.local_model_download"),
    })
    .click();
  await expect
    .poll(() => calls(target))
    .toContain(`setup.download local_api ${ADDED}`);
  const review = laneReview(lane);
  await expect(review).toContainText(ADDED);
  await expect(review).not.toContainText(
    label("desktop.setup.plan_size", { size: "3.2 GB" }),
  );
});

test("removing an added model deletes its download, then takes it off the list", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  await addByName(lane, ADDED);
  const entry = lane.locator(`li[data-model="${ADDED}"]`);
  await entry
    .getByRole("button", {
      name: label("desktop.providers.local_model_remove"),
    })
    .click();
  await expect(entry).toHaveCount(0);
  await expect.poll(() => storedList(target)).toEqual([]);
  // A model that is only listed, not downloaded, has nothing to delete here.
  expect(await calls(target)).not.toContain(`setup.removeModel ${ADDED}`);
});

test("removing a recommended model deletes its download and keeps it listed", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  const text = lane.locator('li[data-model="synthetic-text:1"]');
  await text
    .getByRole("button", {
      name: label("desktop.providers.local_model_remove"),
    })
    .click();
  await expect
    .poll(() => calls(target))
    .toContain("setup.removeModel synthetic-text:1");
  await expect(text).toHaveCount(1);
  expect(await storedList(target)).toEqual([]);
});

test("a recommended model not on this computer offers no removal", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  await expect(
    lane.locator('li[data-model="synthetic-vision:1"]').getByRole("button", {
      name: label("desktop.providers.local_model_remove"),
    }),
  ).toHaveCount(0);
});

test("a change made against an out-of-date list is refused and the list read again", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  await expect(
    lane.locator("[data-slot=local-models] li[data-model]"),
  ).toHaveCount(localLane.recommended.length);
  await target.evaluate(() => window.__scenarioLocalModelsChangeElsewhere?.());
  await lane
    .getByLabel(label("desktop.providers.local_model_add_label"))
    .fill(ADDED);
  await lane
    .getByRole("button", {
      name: label("desktop.providers.local_model_add"),
      exact: true,
    })
    .click();
  await expect(lane.getByRole("alert")).toContainText(
    label("desktop.providers.local_models_refused_revision_conflict"),
  );
  expect(await storedList(target)).toEqual([]);
});

test("window settings holds one provisioning section that opens the panel, with no door of its own to the local AI", async ({
  page: target,
}) => {
  await open(target);
  await target.locator("[data-rail=settings]").click();
  const section = target.locator(".settings [data-settings-provisioning]");
  await expect(section).toContainText(label("desktop.setup.outcome_completed"));
  await expect(
    target.locator(".settings").getByRole("button", {
      name: label("desktop.setup.item.local_ai"),
      exact: true,
    }),
  ).toHaveCount(0);
  await section
    .getByRole("button", { name: label("desktop.setup.open"), exact: true })
    .click();
  const panel = target.getByRole("dialog", {
    name: label("desktop.setup.title"),
  });
  await expect(panel).toBeVisible();
  await expect(panel.locator('[data-setup-element="local_ai"]')).toBeVisible();
  expect(await calls(target)).not.toContain("setup.start local_ai");
});

test("the panel's local AI holds the same model list without starting a download", async ({
  page: target,
}) => {
  await open(target, "partial");
  const setup = target.getByRole("dialog", {
    name: label("desktop.setup.title"),
  });
  const localAi = setup.locator('[data-setup-element="local_ai"]');
  await localAi
    .getByRole("button", { name: label("desktop.setup.item.local_ai") })
    .click();
  await expect(localAi.locator('[data-setup-row="local_ai"]')).toContainText(
    label("desktop.setup.failure.damaged_download"),
  );
  const models = localAi.locator("[data-slot=local-models] li[data-model]");
  await expect(models).toHaveCount(localLane.recommended.length);
  for (const model of localLane.recommended)
    await expect(
      localAi.locator(`[data-slot=local-models] li[data-model="${model}"]`),
    ).toHaveCount(1);
  expect(await calls(target)).not.toContain("setup.start local_ai");
});

test("a lane turned off shows no models", async ({ page: target }) => {
  await open(target);
  const lane = await openLane(target);
  await expect(lane.locator("[data-slot=local-models]")).toBeVisible();
  await lane.getByRole("switch").click();
  await expect(lane.locator("[data-slot=local-models]")).toHaveCount(0);
});

test("a host without setup cannot offer a model download", async ({
  page: target,
}) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  const lane = await openLane(target);
  await expect(
    lane.locator('li[data-model="synthetic-vision:1"]').getByRole("button", {
      name: label("desktop.providers.local_model_download"),
    }),
  ).toBeDisabled();
  await target.locator("[data-rail=settings]").click();
  await expect(target.locator(".settings")).toBeVisible();
  await expect(
    target.locator(".settings [data-settings-provisioning]"),
  ).toHaveCount(0);
});
