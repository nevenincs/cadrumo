import { expect, test, type Locator, type Page } from "@playwright/test";
import {
  FIXTURE_CATALOG,
  FIXTURE_DECLARED_CATALOG,
} from "../../src/dev/fixtures/agentCatalog";
import { catalogChoices } from "../../src/shell/agentCatalog";
import { roleLanes, roleRefusalWords } from "../../src/shell/agentModelRoles";
import { agentColumn as column, scenarioOnly } from "../support/agent";
import { label } from "../support/strings";

// The person's model for each role that reads documents, chosen in the agent
// settings from the agent's catalog. The roles are the service's selections
// read, every lane and model is the scenario host's made-up catalog, and
// nothing is chosen for the person: a lane starts with no model, and the
// agent's recommendation is a button. A refusal of the service is shown in
// words.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const open = (target: Page, query = "") =>
  target.goto(`/scenarios.html?scenario=signed-in&latency=0&bar=off${query}`);

/** The roles the service names, read from the session the column uses. */
const servedRoles = (target: Page) =>
  target.evaluate(async () => {
    const session = window.__fixtureAgentSession;
    const roles = await session?.modelRoles?.();
    return roles?.state === "readable"
      ? roles.roles.map((held) => held.role)
      : [];
  });

const settingsButton = (target: Page) =>
  column(target)
    .getByRole("button", {
      name: new RegExp(
        `^${escaped(label("desktop.agent.settings_label", { current: "" }))}`,
      ),
    })
    .first();

async function openRoles(target: Page) {
  await settingsButton(target).click();
  await target
    .getByRole("dialog", { name: label("desktop.agent.settings_title") })
    .getByRole("button", { name: label("desktop.agent.model_roles_open") })
    .click();
  const dialog = target.getByRole("dialog", {
    name: label("desktop.agent.model_roles_title"),
  });
  await expect(dialog).toBeVisible();
  return dialog;
}

const roleSection = (dialog: Locator, role: string) =>
  dialog.locator(`section[data-role="${role}"]`);
const laneBox = (section: Locator) =>
  section.getByRole("combobox", { name: /./ }).first();
const modelBox = (section: Locator) =>
  section.getByRole("combobox", { name: /./ }).nth(1);

const localLane = FIXTURE_CATALOG.providers?.find(
  (lane) => lane.provider_id === "local",
);
const localWords = `${localLane?.display_name}, ${label("desktop.providers.connection_api")}`;

test("every role the service names is listed, none chosen, each choosable from the catalog", async ({
  page: target,
}) => {
  await open(target);
  const dialog = await openRoles(target);
  const roles = await servedRoles(target);
  expect(roles.length).toBeGreaterThan(0);
  await expect(dialog.locator("section[data-role]")).toHaveCount(roles.length);
  for (const role of roles) {
    const section = roleSection(dialog, role);
    await expect(section.locator("[data-slot=role-current]")).toHaveText(
      label("desktop.agent.model_role_none"),
    );
    // Nothing to clear, nothing to save, no model offered before a lane.
    await expect(
      section.getByRole("button", {
        name: label("desktop.agent.model_role_clear"),
      }),
    ).toBeDisabled();
    await expect(section.getByRole("combobox")).toHaveCount(1);
  }
  // The lanes offered are the catalog's lanes that list models, every one.
  const offered = await laneBox(roleSection(dialog, roles[0] ?? "")).evaluate(
    (select: HTMLSelectElement) =>
      [...select.options].map((option) => option.value).filter(Boolean),
  );
  expect(offered).toEqual(roleLanes(FIXTURE_CATALOG).map((lane) => lane.id));
});

test("a lane starts with no model; the recommendation is offered, shown with its licence, vision and size, and saved only on Save", async ({
  page: target,
}) => {
  await open(target);
  const dialog = await openRoles(target);
  const section = roleSection(dialog, "vision_transcription");
  await laneBox(section).selectOption({ label: localWords });
  // The model is not preselected, not even the recommended one.
  await expect(modelBox(section)).toHaveValue("");
  await expect(section.locator("[data-slot=model-facts]")).toHaveCount(0);
  const recommended = section.locator("button[data-recommended]");
  await expect(recommended).toHaveCount(2);
  const vision = section.locator('button[data-recommended="vision"]');
  await expect(vision).toHaveText(
    label("desktop.agent.model_role_recommended", {
      capability: label("desktop.agent.model_role_capability_vision"),
      model: "Synthetic Vision 1",
    }),
  );
  await expect(
    section.locator("[data-slot=role-current]"),
    "offering is not choosing",
  ).toHaveText(label("desktop.agent.model_role_none"));

  await vision.click();
  await expect(modelBox(section)).toHaveValue("synthetic-vision:1");
  const facts = section.locator("[data-slot=model-facts]");
  await expect(facts.locator("[data-fact=licence]")).toHaveText(
    label("desktop.agent.model_role_licence", {
      licence: "Example community licence",
    }),
  );
  await expect(facts.locator("[data-fact=vision]")).toHaveText(
    label("desktop.agent.model_role_vision_yes"),
  );
  await expect(facts.locator("[data-fact=size]")).toHaveText(
    label("desktop.agent.model_role_size", { size: "3.2 GB" }),
  );
  // Still not saved until the person saves it.
  await expect(section.locator("[data-slot=role-current]")).toHaveText(
    label("desktop.agent.model_role_none"),
  );

  // The licence text comes from the ready agent.
  await section
    .getByRole("button", {
      name: label("desktop.agent.model_role_licence_show"),
    })
    .click();
  await expect(
    section.getByLabel("Example community licence", { exact: true }),
  ).toContainText("A made-up licence text for synthetic-vision:1");

  await section
    .getByRole("button", { name: label("desktop.agent.model_role_save") })
    .click();
  await expect(section.getByRole("status")).toHaveText(
    label("desktop.agent.model_role_saved"),
  );
  await expect(section.locator("[data-slot=role-current]")).toHaveText(
    label("desktop.agent.model_role_current", {
      model: "Synthetic Vision 1",
      lane: localWords,
    }),
  );
  expect(
    await target.evaluate(async () => {
      const roles = await window.__fixtureAgentSession?.modelRoles?.();
      return roles?.state === "readable"
        ? roles.roles.find((held) => held.role === "vision_transcription")
        : null;
    }),
  ).toEqual({
    role: "vision_transcription",
    lane: "local_api",
    model: "synthetic-vision:1",
  });

  // A model the catalog states less of says so.
  await modelBox(section).selectOption("synthetic-plain:1");
  await expect(facts.locator("[data-fact=licence]")).toHaveText(
    label("desktop.agent.model_role_licence_unknown"),
  );
  await expect(facts.locator("[data-fact=vision]")).toHaveText(
    label("desktop.agent.model_role_vision_unknown"),
  );
  await expect(facts.locator("[data-fact=size]")).toHaveCount(0);

  // Clearing leaves the role with no model, and no other chosen in its place.
  await section
    .getByRole("button", { name: label("desktop.agent.model_role_clear") })
    .click();
  await expect(section.locator("[data-slot=role-current]")).toHaveText(
    label("desktop.agent.model_role_none"),
  );
  expect(
    await target.evaluate(async () => {
      const roles = await window.__fixtureAgentSession?.modelRoles?.();
      return roles?.state === "readable"
        ? roles.roles.every((held) => held.lane === null && held.model === null)
        : false;
    }),
  ).toBe(true);
});

test("the service's refusals are shown in words, and a conflict reads the choices again", async ({
  page: target,
}) => {
  await open(target);
  const dialog = await openRoles(target);
  const save = (section: Locator) =>
    section
      .getByRole("button", { name: label("desktop.agent.model_role_save") })
      .click();

  // A role that reads images, given a model that does not.
  const vision = roleSection(dialog, "vision_transcription");
  await laneBox(vision).selectOption({ label: localWords });
  await modelBox(vision).selectOption("synthetic-text:1");
  await expect(
    vision.locator("[data-slot=model-facts] [data-fact=vision]"),
  ).toHaveText(label("desktop.agent.model_role_vision_no"));
  await save(vision);
  await expect(vision.getByRole("alert")).toHaveText(
    label("desktop.agent.model_role_refused_vision_required"),
  );

  // A lane that runs no background reading.
  const text = roleSection(dialog, "text_extraction");
  const beta = FIXTURE_CATALOG.providers?.find(
    (lane) => lane.provider_id === "beta" && lane.transport === "api",
  );
  await laneBox(text).selectOption({
    label: `${beta?.display_name}, ${label("desktop.providers.connection_api")}`,
  });
  await modelBox(text).selectOption({ index: 1 });
  await save(text);
  await expect(text.getByRole("alert")).toHaveText(
    label("desktop.agent.model_role_refused_lane_not_runnable"),
  );

  // Changed elsewhere since this window read it: refused, read again, and
  // the next save goes through.
  await laneBox(text).selectOption({ label: localWords });
  await modelBox(text).selectOption("synthetic-text:1");
  await target.evaluate(() => window.__scenarioModelRolesChangeElsewhere?.());
  await save(text);
  await expect(text.getByRole("alert")).toHaveText(
    label("desktop.agent.model_role_refused_revision_conflict"),
  );
  await save(text);
  await expect(text.getByRole("status")).toHaveText(
    label("desktop.agent.model_role_saved"),
  );
  await expect(text.getByRole("alert")).toHaveCount(0);
});

test("every refusal the service gives a selection has words of its own", () => {
  const words = (key: string) => label(key);
  const codes = {
    agent_model_role_unknown_role: "model_role_refused_unknown_role",
    agent_model_role_model_not_in_catalogue:
      "model_role_refused_model_not_in_catalogue",
    agent_model_role_lane_not_runnable: "model_role_refused_lane_not_runnable",
    agent_model_role_vision_required: "model_role_refused_vision_required",
    agent_model_role_revision_conflict: "model_role_refused_revision_conflict",
    agent_model_role_committed_readback_failed:
      "model_role_refused_committed_readback_failed",
    agent_model_role_catalog_unavailable:
      "model_role_refused_catalog_unavailable",
    agent_model_role_unknown: "model_role_refused_unknown",
  };
  for (const [code, key] of Object.entries(codes))
    expect(roleRefusalWords(words, code), code).toBe(
      label(`desktop.agent.${key}`),
    );
  expect(roleRefusalWords(words, "agent_signed_out")).toBe(
    label("desktop.agent.service_signed_out"),
  );
});

async function openPicker(target: Page) {
  await settingsButton(target).click();
  const settings = target.getByRole("dialog", {
    name: label("desktop.agent.settings_title"),
  });
  await settings
    .getByRole("button", { name: label("desktop.agent.provider") })
    .click();
  return settings;
}

/** Each entry of the open provider list: disabled or not, and its words. */
const pickerRows = (target: Page) =>
  target
    .getByRole("listbox")
    .getByRole("option")
    .evaluateAll((nodes) =>
      nodes.map((node) => ({
        disabled: node.getAttribute("aria-disabled") === "true",
        text: node.textContent ?? "",
      })),
    );

test("before the agent is ready its declared lanes are listed, none choosable, and become choosable once it is", async ({
  page: target,
}) => {
  await open(target, "&catalog=declared");
  await expect(
    column(target).getByText(label("desktop.agent.service_starting")),
  ).toBeVisible();
  const settings = await openPicker(target);
  const options = target.getByRole("listbox").getByRole("option");
  const declared = FIXTURE_DECLARED_CATALOG.catalog.providers ?? [];
  await expect(options).toHaveCount(declared.length);
  for (const row of await pickerRows(target)) {
    expect(row.disabled, row.text).toBe(true);
    expect(row.text).toContain(label("desktop.agent.lane_not_observed"));
  }
  // The column deduces the same: lanes listed, none observed.
  const choices = catalogChoices(label, FIXTURE_DECLARED_CATALOG);
  expect(choices.observed).toBe(false);
  expect(choices.providers.flatMap((provider) => provider.ways)).toHaveLength(
    declared.length,
  );
  await target.keyboard.press("Escape");
  await expect(target.getByRole("listbox")).toHaveCount(0);
  await target.keyboard.press("Escape");
  await expect(settings).toHaveCount(0);

  // The agent is ready: the served catalog replaces the declared one.
  await target.evaluate(() => window.__scenarioAgentPublishStatus?.());
  await expect(
    column(target).getByText(label("desktop.agent.service_starting")),
  ).toHaveCount(0);
  await openPicker(target);
  const served = FIXTURE_CATALOG.providers ?? [];
  await expect(options).toHaveCount(served.length);
  expect((await pickerRows(target)).filter((row) => row.disabled)).toHaveLength(
    served.filter((lane) => !lane.health.selectable).length,
  );
});

test("before the agent is ready a role is chosen from the declared models, and the licence text waits for the agent", async ({
  page: target,
}) => {
  await open(target, "&catalog=declared");
  const dialog = await openRoles(target);
  const section = roleSection(dialog, "text_extraction");
  await laneBox(section).selectOption({ label: localWords });
  await expect(modelBox(section)).toHaveValue("");
  await modelBox(section).selectOption("synthetic-text:1");
  await expect(
    section.locator("[data-slot=model-facts] [data-fact=licence]"),
  ).toHaveText(
    label("desktop.agent.model_role_licence", {
      licence: "Example Apache-style licence (Apache-2.0)",
    }),
  );
  await section
    .getByRole("button", {
      name: label("desktop.agent.model_role_licence_show"),
    })
    .click();
  await expect(
    section.getByText(label("desktop.agent.model_role_licence_unavailable")),
  ).toBeVisible();
  await section
    .getByRole("button", { name: label("desktop.agent.model_role_save") })
    .click();
  await expect(section.locator("[data-slot=role-current]")).toHaveText(
    label("desktop.agent.model_role_current", {
      model: "Synthetic Text 1",
      lane: localWords,
    }),
  );
});
