import { expect, test, type Locator, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import { formatSize } from "../../src/shared/numbers";
import { catalogLanes } from "../../src/shell/localModelLanes";
import {
  ask,
  messageField,
  offeredModels,
  openModelPicker,
  pickWay,
  scenarioOnly,
} from "../support/agent";
import { servedLocalLanes } from "../support/servedLocalLanes";
import { label } from "../support/strings";

// The two local engines give the person one experience. Each engine's lane,
// with the window started on that engine, reaches the same states in the same
// words and through the same doors: a model this computer lacks and the way
// to download it, a download under way, its refusal, a model that is held and
// can be removed, the agent's picker and a refused send, a change of engine
// in flight, and the placement. One table of states runs on both engines; the
// calls the host records say each state reached the engine's own lane.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

declare global {
  interface Window {
    __localEngineRelease?: () => void;
  }
}

const ENGINES = ["llamacpp", "ollama"] as const;
type Engine = (typeof ENGINES)[number];

const ENGINE_WORDS = {
  llamacpp: "desktop.providers.local_engine_llamacpp",
  ollama: "desktop.providers.local_engine_ollama",
} as const;
const PLACEMENT_WORDS = {
  auto: "desktop.providers.local_placement_auto",
  cpu_only: "desktop.providers.local_placement_cpu_only",
} as const;

const otherOf = (engine: Engine): Engine =>
  engine === "ollama" ? "llamacpp" : "ollama";

const served = catalogLanes(FIXTURE_CATALOG);

/** What the host makes up for an engine's lane, from the host's own catalog:
 * the lane, the recommended models, the one this computer lacks and the one
 * it holds. */
function lanePlan(engine: Engine) {
  const lane = served.find((held) => held.id === `${engine}_api`);
  const missing = lane?.models.find((model) => model.installed === false);
  const held = lane?.models.find((model) => model.installed === true);
  if (!lane || !missing || !held)
    throw new Error(`The host makes up no ${engine} lane to compare`);
  return {
    lane: lane.id,
    way: `${engine}/api`,
    recommended: lane.recommended,
    missing,
    held,
    size: formatSize("en", missing.sizeBytes ?? 0),
  };
}

const open = (target: Page, engine: Engine, extra = "") =>
  target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready&engine=${engine}${extra}`,
  );

const settings = (target: Page) =>
  target.locator(".pane-agent").getByRole("region", {
    name: label("desktop.providers.title"),
  });

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
  return settings(target);
}

const engineGroup = (target: Page) =>
  settings(target).locator("[data-slot=local-engine-choice]");
const placementGroup = (target: Page) =>
  settings(target).locator("[data-slot=local-placement-choice]");
const choice = (group: Locator, key: string) =>
  group.getByRole("radio", { name: label(key) });
const modelRows = (target: Page, engine: Engine) =>
  settings(target).locator(
    `li[data-provider="${engine}"] [data-slot=local-models] li[data-model]`,
  );
const lane = (target: Page, engine: Engine) =>
  settings(target).locator(`[data-lane="${engine}_api"]`);
const rowOf = (scope: Locator, model: string) =>
  scope.locator(`li[data-model="${model}"]`);
const download = (row: Locator) =>
  row.getByRole("button", {
    name: label("desktop.providers.local_model_download"),
    exact: true,
  });
const remove = (row: Locator) =>
  row.getByRole("button", {
    name: label("desktop.providers.local_model_remove"),
  });
const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);
const setupStep = (target: Page) =>
  target.evaluate(() => window.__scenarioSetup?.step("local_ai"));

/** Asks for the download of `model` on its row and returns the plan the row
 * then holds for the person's answer. */
async function askDownload(row: Locator) {
  await download(row).click();
  const review = row.locator("[data-setup-review]");
  await expect(review).toContainText(label("desktop.setup.lead_review"));
  return review;
}

for (const engine of ENGINES) {
  const {
    lane: laneId,
    way,
    recommended,
    missing,
    held,
    size,
  } = lanePlan(engine);
  const other = otherOf(engine);

  test.describe(`${engine}`, () => {
    test("the window starts on the engine and shows its lane alone", async ({
      page: target,
    }) => {
      await open(target, engine);
      await openSettings(target);
      await expect(
        choice(engineGroup(target), ENGINE_WORDS[engine]),
      ).toBeChecked();
      await expect(
        choice(engineGroup(target), ENGINE_WORDS[other]),
      ).not.toBeChecked();
      await expect(
        choice(placementGroup(target), PLACEMENT_WORDS.auto),
      ).toBeChecked();
      const models = modelRows(target, engine);
      await expect(models).toHaveCount(recommended.length);
      expect(
        await models.evaluateAll((nodes) =>
          nodes.map((node) => node.getAttribute("data-model")),
        ),
      ).toEqual(recommended);
      await expect(modelRows(target, other)).toHaveCount(0);
      expect(
        (await calls(target)).filter((call) => call === "agentLocalEngine"),
      ).not.toHaveLength(0);
    });

    test("the setup panel lists that engine's models alone, each with its own download door", async ({
      page: target,
    }) => {
      await target.goto(
        `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=fresh&engine=${engine}`,
      );
      const panel = target.getByRole("dialog", {
        name: label("desktop.setup.title"),
      });
      const localAi = panel.locator('[data-setup-element="local_ai"]');
      await localAi
        .getByRole("button", { name: label("desktop.setup.item.local_ai") })
        .click();
      const listed = servedLocalLanes(engine).flatMap(
        (held) => held.recommended,
      );
      const models = localAi.locator("[data-slot=local-models] li[data-model]");
      await expect(models).toHaveCount(listed.length);
      for (const model of listed)
        await expect(rowOf(localAi, model)).toHaveCount(1);
      for (const model of lanePlan(other).recommended)
        await expect(rowOf(localAi, model)).toHaveCount(0);
      await download(rowOf(localAi, missing.id)).click();
      await expect
        .poll(() => calls(target))
        .toContain(`setup.download ${laneId} ${missing.id}`);
    });

    test("a model this computer lacks says so and offers its download alone", async ({
      page: target,
    }) => {
      await open(target, engine);
      await openSettings(target);
      const row = rowOf(lane(target, engine), missing.id);
      await expect(row).toHaveAttribute("data-installed", "false");
      await expect(row).toContainText(
        label("desktop.providers.local_model_absent"),
      );
      await expect(row).not.toContainText(
        label("desktop.providers.local_model_installed"),
      );
      await expect(row.locator("[data-fact=size]")).toHaveText(
        label("desktop.providers.local_model_size", { size }),
      );
      await expect(download(row)).toBeEnabled();
      await expect(remove(row)).toHaveCount(0);
    });

    test("a model this computer holds says so, hides its download and offers its removal", async ({
      page: target,
    }) => {
      await open(target, engine);
      await openSettings(target);
      const row = rowOf(lane(target, engine), held.id);
      await expect(row).toHaveAttribute("data-installed", "true");
      await expect(row).toContainText(
        label("desktop.providers.local_model_installed"),
      );
      await expect(row).not.toContainText(
        label("desktop.providers.local_model_absent"),
      );
      await expect(download(row)).toHaveCount(0);
      await expect(remove(row)).toBeEnabled();
      await remove(row).click();
      await expect
        .poll(() => calls(target))
        .toContain(`setup.removeModel ${held.id}`);
      await expect(row).toHaveAttribute("data-installed", "false");
      // A recommended model stays listed, now with its download door.
      await expect(download(row)).toBeEnabled();
    });

    test("a download plans on the model's row, runs with its badge and doors disabled, and ends held", async ({
      page: target,
    }) => {
      await open(target, engine);
      await openSettings(target);
      const scope = lane(target, engine);
      const row = rowOf(scope, missing.id);
      const review = await askDownload(row);
      await expect
        .poll(() => calls(target))
        .toContain(`setup.download ${laneId} ${missing.id}`);
      await review
        .getByRole("button", {
          name: label("desktop.setup.approve_size", { size }),
        })
        .click();
      expect(await calls(target)).toContain("setup.answer apply");
      await expect(row.locator("[data-setup-progress]")).toBeVisible();
      await expect(row).toContainText(
        label("desktop.setup.state.provisioning"),
      );
      await expect(row).not.toContainText(
        label("desktop.providers.local_model_absent"),
      );
      await expect(download(row)).toBeDisabled();
      for (let index = 0; index < 40; index += 1) {
        if ((await row.getAttribute("data-installed")) === "true") break;
        await setupStep(target);
      }
      await expect(row).toHaveAttribute("data-installed", "true");
      await expect(row).toContainText(
        label("desktop.providers.local_model_installed"),
      );
      await expect(download(row)).toHaveCount(0);
      await expect(remove(row)).toBeEnabled();
    });

    for (const refusal of [
      {
        name: "the setup refuses the plan",
        shape: "ready",
        words: label("desktop.setup.failure.not_in_this_build"),
      },
      {
        name: "another setup is already running",
        shape: "busy",
        words: label("desktop.setup.refused_busy"),
      },
    ] as const)
      test(`a download refused because ${refusal.name} says why on that model's row alone`, async ({
        page: target,
      }) => {
        await target.goto(
          `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=${refusal.shape}&engine=${engine}`,
        );
        if (refusal.shape === "busy")
          await target
            .getByRole("dialog", { name: label("desktop.setup.title") })
            .getByRole("button", { name: label("desktop.setup.not_now") })
            .click();
        else
          await target.evaluate(() =>
            window.__scenarioSetup?.refuseStarts("not_in_this_build"),
          );
        await openSettings(target);
        const scope = lane(target, engine);
        const row = rowOf(scope, missing.id);
        await download(row).click();
        await expect(row.getByRole("alert")).toContainText(refusal.words);
        await expect(row).toHaveAttribute("data-installed", "false");
        await expect(download(row)).toBeEnabled();
        await expect(
          scope
            .locator(`li[data-model]:not([data-model="${missing.id}"])`)
            .getByRole("alert"),
        ).toHaveCount(0);
      });

    test("the agent's picker lists the missing model disabled, starts on a held one and offers the download", async ({
      page: target,
    }) => {
      await open(target, engine);
      const picker = await openModelPicker(target);
      await pickWay(target, picker, way);
      const field = picker.getByLabel(label("desktop.agent.model"));
      const option = field.locator(`option[value="${missing.id}"]`);
      await expect(option).toBeDisabled();
      await expect(option).toHaveText(
        label("desktop.agent.model_not_installed", { name: missing.name }),
      );
      await expect(field.locator(`option[value="${held.id}"]`)).toBeEnabled();
      expect([...(await offeredModels(picker))].sort()).toEqual(
        [...recommended].sort(),
      );
      expect(await field.inputValue()).toBe(held.id);
      await expect(picker).toContainText(
        label("desktop.agent.models_to_download"),
      );
      await picker
        .getByRole("button", {
          name: label("desktop.agent.download_models"),
          exact: true,
        })
        .click();
      await expect(picker).toBeHidden();
      await expect(settings(target)).toBeVisible();
    });

    test("a send for a model this computer no longer holds is refused in words and leads to the engine's local models", async ({
      page: target,
    }) => {
      await open(target, engine);
      const picker = await openModelPicker(target);
      await pickWay(target, picker, way);
      expect(
        await picker.getByLabel(label("desktop.agent.model")).inputValue(),
      ).toBe(held.id);
      await target.keyboard.press("Escape");
      await expect(picker).toBeHidden();
      // The model is removed behind the window's back, after the picker
      // offered it as held.
      await target.evaluate(
        (model) => window.__scenarioModelPresence!.mark(model, false),
        held.id,
      );
      await ask(target, "Hello");
      const alert = target
        .locator(".pane-agent")
        .getByRole("alert")
        .filter({
          hasText: label("desktop.agent.model_not_installed_refused"),
        });
      await expect(alert).toBeVisible();
      await expect(alert).not.toContainText(
        label("desktop.agent.request_failed"),
      );
      await expect(messageField(target)).toHaveValue("Hello");
      expect(
        (await calls(target)).some(
          (call) => call.startsWith("agentSend ") && call.endsWith(` ${way}`),
        ),
      ).toBe(true);
      await alert
        .getByRole("button", {
          name: label("desktop.agent.download_models"),
          exact: true,
        })
        .click();
      await expect(settings(target)).toBeVisible();
      await settings(target)
        .locator("li[data-provider] > details")
        .evaluateAll((nodes) =>
          nodes.forEach((node) => ((node as HTMLDetailsElement).open = true)),
        );
      await expect(modelRows(target, engine)).toHaveCount(recommended.length);
      await expect(
        download(rowOf(lane(target, engine), held.id)),
      ).toBeEnabled();
    });

    test("with no model on this computer the lane cannot be chosen and says why", async ({
      page: target,
    }) => {
      await open(target, engine, "&models=none");
      const picker = await openModelPicker(target);
      await picker
        .getByRole("button", { name: label("desktop.agent.provider") })
        .click();
      const entry = target.locator(`[role=option][data-way="${way}"]`);
      await expect(entry).toHaveAttribute("data-disabled", "true");
      await expect(entry).toContainText(
        label("desktop.agent.lane_no_installed_model"),
      );
      await target.keyboard.press("Escape");
      await expect(picker).toContainText(
        label("desktop.agent.models_to_download"),
      );
      await target.keyboard.press("Escape");
      await openSettings(target);
      for (const model of recommended) {
        const row = rowOf(lane(target, engine), model);
        await expect(row).toContainText(
          label("desktop.providers.local_model_absent"),
        );
        await expect(download(row)).toBeEnabled();
      }
    });

    test("an engine change in flight says it is changing and disables both choices until it ends", async ({
      page: target,
    }) => {
      await open(target, engine);
      await openSettings(target);
      const read = await target.evaluate(async () => {
        const stored = await window.__fixtureAgentSession?.localEngine?.();
        return stored?.revision;
      });
      await target.evaluate(() => {
        window.__fixtureLocalEngineChange = () =>
          new Promise<void>((resolve) => {
            window.__localEngineRelease = resolve;
          });
      });
      await choice(engineGroup(target), ENGINE_WORDS[other]).click();
      await expect(
        settings(target)
          .getByRole("status")
          .filter({
            hasText: label("desktop.providers.local_engine_changing"),
          }),
      ).toBeVisible();
      for (const group of [engineGroup(target), placementGroup(target)])
        for (const radio of await group.getByRole("radio").all())
          await expect(radio).toBeDisabled();
      expect(await calls(target)).toContain(
        `agentLocalEngineChoose ${other} auto ${read}`,
      );
      await expect
        .poll(() => target.evaluate(() => Boolean(window.__localEngineRelease)))
        .toBe(true);
      await target.evaluate(() => {
        window.__fixtureLocalEngineChange = undefined;
        window.__localEngineRelease!();
      });
      await expect(
        settings(target)
          .getByRole("status")
          .filter({
            hasText: label("desktop.providers.local_engine_changing"),
          }),
      ).toHaveCount(0);
      await expect(
        choice(engineGroup(target), ENGINE_WORDS[other]),
      ).toBeChecked();
      await expect(modelRows(target, other)).toHaveCount(
        lanePlan(other).recommended.length,
      );
      await expect(modelRows(target, engine)).toHaveCount(0);
    });

    test("the processor-only placement is stored for the engine and keeps its lane", async ({
      page: target,
    }) => {
      await open(target, engine);
      await openSettings(target);
      await choice(placementGroup(target), PLACEMENT_WORDS.cpu_only).click();
      await expect(
        choice(placementGroup(target), PLACEMENT_WORDS.cpu_only),
      ).toBeChecked();
      await expect
        .poll(async () =>
          (await calls(target)).some((call) =>
            call.startsWith(`agentLocalEngineChoose ${engine} cpu_only `),
          ),
        )
        .toBe(true);
      const stored = await target.evaluate(async () => {
        const record = await window.__fixtureAgentSession?.localEngine?.();
        return record?.state === "readable"
          ? { engine: record.engine, placement: record.placement }
          : null;
      });
      expect(stored).toEqual({ engine, placement: "cpu_only" });
      await expect(
        choice(engineGroup(target), ENGINE_WORDS[engine]),
      ).toBeChecked();
      await expect(modelRows(target, engine)).toHaveCount(recommended.length);
      await expect(modelRows(target, other)).toHaveCount(0);
    });

    test("a model added by name joins the engine's list and can be taken off again", async ({
      page: target,
    }) => {
      const added = `synthetic-named-${engine}:test`;
      await open(target, engine);
      await openSettings(target);
      const scope = lane(target, engine);
      await scope
        .getByLabel(label("desktop.providers.local_model_add_label"))
        .fill(added);
      await scope
        .getByRole("button", {
          name: label("desktop.providers.local_model_add"),
          exact: true,
        })
        .click();
      const row = rowOf(scope, added);
      await expect(row).toHaveAttribute("data-added", "true");
      await expect(modelRows(target, engine)).toHaveCount(
        recommended.length + 1,
      );
      const stored = () =>
        target.evaluate(async () => {
          const list = await window.__fixtureAgentSession?.localModels?.();
          return list?.state === "readable" ? list.models : null;
        });
      await expect.poll(stored).toEqual([{ lane: laneId, model: added }]);
      await remove(row).click();
      await expect(row).toHaveCount(0);
      await expect.poll(stored).toEqual([]);
    });
  });
}
