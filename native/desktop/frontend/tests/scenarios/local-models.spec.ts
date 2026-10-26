import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import { localModelOrder, roleLanes } from "../../src/shell/agentModelRoles";
import { scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// The models of a lane on this computer, in its provider settings: listed in
// the order the agent's catalog serves them with what it recommends leading,
// each with what it is and whether it is here. A model is downloaded by
// choosing what it reads for, which stores the selection, and then by setup's
// own review. Turned off, the lane shows no models. Every lane and model is
// the scenario host's made-up catalog.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

const LOCAL = "local_api";
const localLane = roleLanes(FIXTURE_CATALOG).find((lane) => lane.id === LOCAL)!;

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

const storedRoles = (target: Page) =>
  target.evaluate(async () => {
    const roles = await window.__fixtureAgentSession?.modelRoles?.();
    return roles?.state === "readable"
      ? roles.roles.filter((held) => held.model !== null)
      : [];
  });

test("the lane's models are listed with the agent's recommendations leading, vision first", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  const models = lane.locator("[data-slot=local-models] li[data-model]");
  const expected = localModelOrder(localLane).map(({ model }) => model.id);
  await expect(models).toHaveCount(expected.length);
  expect(
    await models.evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-model")),
    ),
  ).toEqual(expected);
  // The recommended vision model leads, then the recommended text model.
  expect(expected.slice(0, 2)).toEqual([
    "synthetic-vision:1",
    "synthetic-text:1",
  ]);
  const vision = models.first();
  await expect(vision).toHaveAttribute("data-recommended", "vision");
  await expect(vision).toContainText(
    label("desktop.providers.local_model_recommended", {
      capability: label("desktop.agent.model_role_capability_vision"),
    }),
  );
  await expect(vision).toContainText(
    label("desktop.providers.local_model_absent"),
  );
  await expect(models.nth(1)).toContainText(
    label("desktop.providers.local_model_installed"),
  );
  // Nothing is selected for the person.
  expect(await storedRoles(target)).toEqual([]);
});

test("downloading a model stores the roles chosen for it and opens setup on the local AI", async ({
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
  // Downloading waits until a role is chosen.
  const confirm = vision.getByRole("button", {
    name: label("desktop.providers.local_model_download"),
  });
  await expect(confirm).toBeDisabled();
  await vision
    .getByRole("checkbox", {
      name: label("desktop.setup.role.vision_transcription"),
    })
    .check();
  // The selected model is missing, but the window still has its earlier
  // ready snapshot. Planning must re-read the host rather than trust it.
  await target.evaluate(() => window.__scenarioSetup?.setAbsent("local_ai"));
  await confirm.click();
  const review = target.getByRole("dialog", {
    name: label("desktop.setup.title"),
  });
  await expect(review).toContainText(label("desktop.setup.lead_review"));
  await review
    .getByText(label("desktop.setup.details"), { exact: true })
    .click();
  await expect(review.locator('[data-setup-plan="local_ai"]')).toHaveCount(1);
  await expect(review.locator('[data-setup-plan="browser"]')).toHaveCount(0);
  await expect
    .poll(() => target.evaluate(() => window.__scenarioHostCalls ?? []))
    .toContain("setup.start local_ai");
  expect(
    await target.evaluate(() => window.__scenarioHostCalls ?? []),
  ).not.toContain("setup.answer apply");
  expect(await storedRoles(target)).toEqual([
    { role: "vision_transcription", lane: LOCAL, model: "synthetic-vision:1" },
  ]);
  await review
    .getByRole("button", {
      name: label("desktop.setup.approve_at_least", { size: "3.4 GB" }),
    })
    .click();
  await expect(review).toContainText(label("desktop.setup.lead_running"));
});

test("window settings opens the existing local provider with setup status and model controls", async ({
  page: target,
}) => {
  await open(target);
  await target.locator("[data-rail=settings]").click();
  await target
    .locator(".settings")
    .getByRole("button", {
      name: label("desktop.setup.item.local_ai"),
      exact: true,
    })
    .click();
  const provider = settings(target).locator(
    'li[data-provider="local"] > details',
  );
  await expect(provider).toHaveAttribute("open", "");
  await expect(provider.locator("summary")).toBeFocused();
  await expect(provider.locator('[data-setup-row="local_ai"]')).toContainText(
    label("desktop.setup.state.ready"),
  );
  await expect(provider.locator('[data-slot="local-models"]')).toBeVisible();
  expect(await storedRoles(target)).toEqual([]);
  expect(
    await target.evaluate(() => window.__scenarioHostCalls ?? []),
  ).not.toContain("setup.start local_ai");
});

test("setup leads to the same local model controls without starting a download", async ({
  page: target,
}) => {
  await open(target, "partial");
  const setup = target.getByRole("dialog", {
    name: label("desktop.setup.title"),
  });
  await setup
    .getByRole("button", {
      name: label("desktop.providers.local_models_title"),
    })
    .click();
  await expect(setup).toBeHidden();
  await expect(
    settings(target).locator('[data-slot="local-models"]'),
  ).toBeVisible();
  await expect(
    settings(target).locator('[data-setup-row="local_ai"]'),
  ).toContainText(label("desktop.setup.failure.damaged_download"));
  expect(
    await target.evaluate(() => window.__scenarioHostCalls ?? []),
  ).not.toContain("setup.start local_ai");
});

test("a role the model cannot serve is refused by the service and said in words", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  const plain = lane.locator('li[data-model="synthetic-text:1"]');
  await plain
    .getByRole("button", {
      name: label("desktop.providers.local_model_choose_roles"),
    })
    .click();
  await plain
    .getByRole("checkbox", {
      name: label("desktop.setup.role.vision_transcription"),
    })
    .check();
  await plain
    .getByRole("button", { name: label("desktop.providers.local_model_use") })
    .click();
  await expect(plain.getByRole("alert")).toHaveText(
    label("desktop.agent.model_role_refused_vision_required"),
  );
  expect(await storedRoles(target)).toEqual([]);
});

test("a lane turned off shows no models", async ({ page: target }) => {
  await open(target);
  const lane = await openLane(target);
  await expect(lane.locator("[data-slot=local-models]")).toBeVisible();
  await lane.getByRole("switch").click();
  await expect(lane.locator("[data-slot=local-models]")).toHaveCount(0);
});

test("removing a model clears the roles that read with it first, then removes it from this computer", async ({
  page: target,
}) => {
  await open(target);
  const lane = await openLane(target);
  const text = lane.locator('li[data-model="synthetic-text:1"]');
  await text
    .getByRole("button", {
      name: label("desktop.providers.local_model_choose_roles"),
    })
    .click();
  await text
    .getByRole("checkbox", {
      name: label("desktop.setup.role.text_extraction"),
    })
    .check();
  await text
    .getByRole("button", { name: label("desktop.providers.local_model_use") })
    .click();
  await expect(text).toContainText(
    label("desktop.providers.local_model_used_by", {
      roles: label("desktop.setup.role.text_extraction"),
    }),
  );
  await text
    .getByRole("button", {
      name: label("desktop.providers.local_model_remove"),
    })
    .click();
  await expect(text).toContainText(
    label("desktop.providers.local_model_unused"),
  );
  expect(await storedRoles(target)).toEqual([]);
  await expect
    .poll(() => target.evaluate(() => window.__scenarioHostCalls ?? []))
    .toContain("setup.removeModel synthetic-text:1");
});

test("a model not on this computer offers no removal", async ({
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
  await expect(
    target.locator(".settings").getByRole("button", {
      name: label("desktop.setup.item.local_ai"),
      exact: true,
    }),
  ).toHaveCount(0);
  expect(await storedRoles(target)).toEqual([]);
});
