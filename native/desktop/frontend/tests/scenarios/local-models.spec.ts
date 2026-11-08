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
declare global {
  interface Window {
    __localAiReadRelease?: () => void;
  }
}
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

test("a failed local model list can be read again without resetting it", async ({
  page: target,
}) => {
  await open(target);
  await target.evaluate(() => {
    window.__fixtureLocalModelsRead = async () => {
      throw Object.assign(new Error("fixture read failure"), {
        code: "agent_gateway_503",
      });
    };
  });
  const lane = await openLane(target);
  await expect(lane.getByRole("alert")).toContainText(
    label("desktop.providers.local_models_failed"),
  );
  await target.evaluate(() => {
    window.__fixtureLocalModelsRead = () =>
      new Promise<void>((resolve) => {
        window.__localAiReadRelease = resolve;
      });
  });
  await lane
    .getByRole("button", { name: label("desktop.agent.retry"), exact: true })
    .click();
  await expect(lane).toContainText(
    label("desktop.providers.local_models_loading"),
  );
  await expect(
    lane.getByRole("button", {
      name: label("desktop.agent.retry"),
      exact: true,
    }),
  ).toHaveCount(0);
  await expect
    .poll(() => target.evaluate(() => Boolean(window.__localAiReadRelease)))
    .toBe(true);
  await target.evaluate(() => {
    window.__fixtureLocalModelsRead = undefined;
    window.__localAiReadRelease!();
  });
  await expect(
    lane.locator("[data-slot=local-models] li[data-model]"),
  ).toHaveCount(localLane.recommended.length);
  expect(
    (await calls(target)).some((call) =>
      call.startsWith("agentLocalModelsReset"),
    ),
  ).toBe(false);
});

for (const source of ["catalog", "settings"] as const) {
  test(`Local AI ${source} failure stays distinct from an empty lane list and can retry`, async ({
    page: target,
  }) => {
    await open(target, "partial");
    const setup = target.getByRole("dialog", {
      name: label("desktop.setup.title"),
    });
    const localAi = setup.locator('[data-setup-element="local_ai"]');
    await expect(localAi).toBeVisible();
    await expect
      .poll(() => target.evaluate(() => Boolean(window.__fixtureAgentSession)))
      .toBe(true);
    await target.evaluate((source) => {
      if (source === "settings") {
        window.__scenarioProviderSignIn!.failNextSettingsRead();
        return;
      }
      const session = window.__fixtureAgentSession!;
      const read = session.providerCatalog;
      session.providerCatalog = async () => {
        await new Promise<void>((resolve) => {
          window.__localAiReadRelease = resolve;
        });
        session.providerCatalog = read;
        throw Object.assign(new Error("fixture catalog failure"), {
          code: "agent_gateway_503",
        });
      };
    }, source);
    await localAi
      .getByRole("button", {
        name: label("desktop.setup.item.local_ai"),
        exact: true,
      })
      .click();
    if (source === "catalog") {
      await expect(localAi.getByRole("status")).toContainText(
        label("desktop.providers.local_models_loading"),
      );
      await expect(localAi).not.toContainText(
        label("desktop.providers.local_models_none"),
      );
      await expect
        .poll(() => target.evaluate(() => Boolean(window.__localAiReadRelease)))
        .toBe(true);
      await target.evaluate(() => window.__localAiReadRelease!());
    }
    await expect(
      localAi
        .getByRole("alert")
        .filter({ hasText: label("desktop.providers.load_failed") }),
    ).toBeVisible();
    await expect(localAi).not.toContainText(
      label("desktop.providers.local_models_none"),
    );
    await expect(localAi.locator('[data-setup-row="local_ai"]')).toBeVisible();
    await localAi
      .getByRole("alert")
      .filter({ hasText: label("desktop.providers.load_failed") })
      .getByRole("button", { name: label("desktop.agent.retry"), exact: true })
      .click();
    await expect(
      localAi.locator("[data-slot=local-models] li[data-model]"),
    ).toHaveCount(localLane.recommended.length);
  });
}

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

/** The plan a model download awaits an answer on, where the lane shows it:
 * on the asked model's row, never also on the local AI's own row. */
const laneReview = (lane: Locator) => lane.locator("[data-setup-review]");

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
  const review = vision.locator("[data-setup-review]");
  await expect(review).toContainText(label("desktop.setup.lead_review"));
  // The plan appears where the click was: in view, with the keyboard on its
  // approve button.
  await expect(review).toBeInViewport();
  await expect(
    review.getByRole("button", {
      name: label("desktop.setup.approve_size", { size: "3.2 GB" }),
    }),
  ).toBeFocused();
  // The asked model's row is the one place the plan is answered, and it does
  // not say the model waits to start while the plan awaits the person.
  await expect(laneReview(lane)).toHaveCount(1);
  await expect(
    lane.locator('[data-setup-row="local_ai"] [data-setup-review]'),
  ).toHaveCount(0);
  await expect(vision).not.toContainText(label("desktop.setup.step_waiting"));
  await expect(vision.locator("[data-setup-progress]")).toHaveCount(0);
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
  // The answer moved the run on: the model's own entry shows its download;
  // the program row shows none, since the program is not part of this setup.
  // Nothing opens over it.
  await expect(vision.locator("[data-setup-progress]")).toBeVisible();
  await expect(laneReview(lane)).toHaveCount(0);
  expect(await calls(target)).toContain("setup.answer apply");
  await expect(
    lane.locator('[data-setup-row="local_ai"] [data-setup-progress]'),
  ).toHaveCount(0);
  await expect(target.getByRole("dialog")).toHaveCount(0);
});

test("a download still being planned says it is checking, on its row and the local AI's, not that it waits", async ({
  page: target,
}) => {
  await open(target, "start_held");
  const lane = await openLane(target);
  const vision = lane.locator('li[data-model="synthetic-vision:1"]');
  const other = lane.locator('li[data-model="synthetic-text:1"]');
  await vision
    .getByRole("button", {
      name: label("desktop.providers.local_model_download"),
    })
    .click();
  await expect
    .poll(() => calls(target))
    .toContain("setup.download local_api synthetic-vision:1");
  // The host has planned nothing yet, so no part is named: the asked model's
  // row and the local AI's row say the same thing, and keep their spinner.
  const checking = label("desktop.setup.step_checking");
  const figure = vision.locator("[data-setup-planning]");
  await expect(figure).toHaveText(checking);
  await expect(figure.locator("[data-slot=spinner]")).toBeVisible();
  await expect(
    lane.locator('[data-setup-row="local_ai"] [data-setup-planning]'),
  ).toHaveText(checking);
  await expect(vision).not.toContainText(label("desktop.setup.step_waiting"));
  await expect(lane.locator('[data-setup-row="local_ai"]')).not.toContainText(
    label("desktop.setup.step_waiting"),
  );
  // No other model claims it, and nobody can start a second download.
  await expect(other.locator("[data-setup-planning]")).toHaveCount(0);
  for (const button of await lane
    .getByRole("button", {
      name: label("desktop.providers.local_model_download"),
    })
    .all())
    await expect(button).toBeDisabled();
  // Once the plan awaits its answer, the checking is over.
  await target.evaluate(() => window.__scenarioSetup?.finishPlanning());
  await expect(vision.locator("[data-setup-review]")).toBeVisible();
  await expect(vision.locator("[data-setup-planning]")).toHaveCount(0);
  await expect(vision).not.toContainText(label("desktop.setup.step_waiting"));
});

test("a plan whose asked row leaves the screen is answered on the program's row, and returns to the model's row once the list is read again", async ({
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
  await expect(vision.locator("[data-setup-review]")).toBeVisible();
  const program = lane.locator(
    '[data-setup-row="local_ai"] [data-setup-review]',
  );
  await expect(program).toHaveCount(0);
  // The list is changed elsewhere and then cannot be read: the rows go, and
  // the plan must still be answerable.
  await target.evaluate(() => {
    window.__scenarioLocalModelsChangeElsewhere?.();
    window.__fixtureLocalModelsRead = async () => {
      throw Object.assign(new Error("fixture read failure"), {
        code: "agent_gateway_503",
      });
    };
  });
  await addByName(lane, ADDED);
  await expect(
    lane.locator("[data-slot=local-models] li[data-model]"),
  ).toHaveCount(0);
  await expect(laneReview(lane)).toHaveCount(1);
  await expect(program).toBeVisible();
  // Read again, the model's row owns the plan and the program's row yields.
  await target.evaluate(() => {
    window.__fixtureLocalModelsRead = undefined;
  });
  await lane
    .getByRole("button", { name: label("desktop.agent.retry"), exact: true })
    .click();
  await expect(vision.locator("[data-setup-review]")).toBeVisible();
  await expect(laneReview(lane)).toHaveCount(1);
  await expect(program).toHaveCount(0);
});

test("while the local AI sets up, no model offers its download again", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  const downloads = lane.getByRole("button", {
    name: label("desktop.providers.local_model_download"),
  });
  const vision = lane.locator('li[data-model="synthetic-vision:1"]');
  await expect(
    vision.getByRole("button", {
      name: label("desktop.providers.local_model_download"),
    }),
  ).toBeEnabled();
  await vision
    .getByRole("button", {
      name: label("desktop.providers.local_model_download"),
    })
    .click();
  await expect(laneReview(lane)).toBeVisible();
  // The plan awaits its approval: the setup is live, so another click would
  // start nothing and say nothing.
  for (const button of await downloads.all())
    await expect(button).toBeDisabled();
  expect(
    (await calls(target)).filter((call) => call.startsWith("setup.start")),
  ).toHaveLength(1);
});

test("a download the setup refuses says why on that model's row alone", async ({
  page: target,
}) => {
  await open(target, "busy");
  const lane = await openLane(target);
  const vision = lane.locator('li[data-model="synthetic-vision:1"]');
  await vision
    .getByRole("button", {
      name: label("desktop.providers.local_model_download"),
    })
    .click();
  await expect(vision.getByRole("alert")).toHaveText(
    label("desktop.setup.refused_busy"),
  );
  expect(await calls(target)).toContain("setup.start local_ai");
  await expect(
    lane
      .locator("li[data-model]:not([data-model='synthetic-vision:1'])")
      .getByRole("alert"),
  ).toHaveCount(0);
});

test("a model whose download succeeds is on this computer, as the catalog then reports it", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  await expect(
    lane.locator('li[data-model="synthetic-vision:1"]'),
  ).toContainText(label("desktop.providers.local_model_absent"));
  // The made-up setup moves only when the scenario steps it, and a step
  // before the approval has started it is lost: the run shows first.
  const vision = await downloadVision(target, lane);
  await expect(vision).toContainText(
    label("desktop.providers.local_model_installed"),
  );
  await expect(vision).not.toContainText(
    label("desktop.providers.local_model_absent"),
  );
  await expect(
    vision.getByRole("button", {
      name: label("desktop.providers.local_model_download"),
    }),
  ).toHaveCount(0);
  // Removed again, the catalog reports it gone.
  await vision
    .getByRole("button", {
      name: label("desktop.providers.local_model_remove"),
    })
    .click();
  await expect(vision).toHaveAttribute("data-installed", "false");
});

/** Downloads the vision model through to its end, as the made-up setup is
 * stepped, and leaves the setup settled. */
async function downloadVision(target: Page, lane: Locator) {
  const vision = lane.locator('li[data-model="synthetic-vision:1"]');
  await vision
    .getByRole("button", {
      name: label("desktop.providers.local_model_download"),
    })
    .click();
  await laneReview(lane)
    .getByRole("button", {
      name: label("desktop.setup.approve_size", { size: "3.2 GB" }),
    })
    .click();
  await expect(vision.locator("[data-setup-progress]")).toBeVisible();
  for (
    let index = 0;
    index < 40 && (await vision.getAttribute("data-installed")) !== "true";
    index += 1
  )
    await target.evaluate(() => window.__scenarioSetup?.step("local_ai"));
  await expect(vision).toHaveAttribute("data-installed", "true");
  return vision;
}

/** Asks for a check of the setup from the command palette. */
async function checkFromPalette(target: Page) {
  const palette = target.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  await target.keyboard.press("Control+k");
  await expect(palette).toBeVisible();
  await target.keyboard.type(label("desktop.setup.palette_check"));
  await palette
    .getByRole("option", {
      name: label("desktop.setup.palette_check"),
      exact: true,
    })
    .click();
}

test("a check after a finished download shows no Checking on that model's row", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  const vision = await downloadVision(target, lane);
  await target.evaluate(() => window.__scenarioSetup?.holdChecks());
  await checkFromPalette(target);
  await expect.poll(() => calls(target)).toContain("setup.check full");
  // The check waits for its answer; it is not the download's.
  await expect(vision.locator("[data-setup-planning]")).toHaveCount(0);
  await target.evaluate(() => window.__scenarioSetup?.releaseChecks());
  await expect(vision.locator("[data-setup-planning]")).toHaveCount(0);
});

test("a check the setup refuses is not told as a model's download refusal", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  await downloadVision(target, lane);
  await target.evaluate(() => window.__scenarioSetup?.holdChecks());
  await checkFromPalette(target);
  await expect.poll(() => calls(target)).toContain("setup.check full");
  await target.evaluate(() => window.__scenarioSetup?.releaseChecks("busy"));
  // The panel the check opened says it; no model row does.
  await expect(
    target
      .getByRole("dialog", { name: label("desktop.setup.title") })
      .getByRole("alert")
      .filter({ hasText: label("desktop.setup.refused_busy") }),
  ).toBeVisible();
  await expect(lane.locator('li[data-model] [role="alert"]')).toHaveCount(0);
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

test("while the setup status cannot be read, Download is disabled and the list says why", async ({
  page: target,
}) => {
  await open(target, "unavailable");
  const lane = await openLane(target);
  const vision = lane.locator('li[data-model="synthetic-vision:1"]');
  const download = vision.getByRole("button", {
    name: label("desktop.providers.local_model_download"),
  });
  await expect(download).toBeDisabled();
  await expect(
    lane.locator("[data-slot=local-models-setup-unread]"),
  ).toHaveText(label("desktop.setup.unavailable"));
  await download.click({ force: true });
  expect(
    (await calls(target)).filter((call) => call.startsWith("setup.start")),
  ).toHaveLength(0);
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
