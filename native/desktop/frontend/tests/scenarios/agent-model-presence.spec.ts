import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import { catalogLanes } from "../../src/shell/localModelLanes";
import {
  agentColumn as column,
  ask,
  messageField,
  openModelPicker,
  pickWay,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

// Whether this computer holds a model is what the agent's catalog serves. The
// picker lists a model it lacks, marked and not choosable, with the way to
// download it; a lane that holds none of its models cannot be chosen; and a
// send the agent refuses for a model this computer lost is said in words,
// with the same way on, never as a bare failure.

test.beforeEach(() => {
  scenarioOnly("The scenario host stands in for the agent service.");
});

const LOCAL = "local/api";
const servedLocal = (FIXTURE_CATALOG.providers ?? []).find(
  (lane) => `${lane.provider_id}/${lane.transport}` === LOCAL,
)!;
// The picker offers a local lane's list: the models the lane recommends, and
// those the person added, none here.
const recommended = catalogLanes(FIXTURE_CATALOG).find(
  (lane) => lane.id === LOCAL.replace("/", "_"),
)!.recommended;
const servedModels = (servedLocal.catalog.models ?? []).filter((entry) =>
  recommended.includes(entry.model),
);
const absent = servedModels.filter((entry) => entry.installed === false);
const held = servedModels.filter((entry) => entry.installed !== false);

const open = (target: Page, extra = "") =>
  target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&setup=ready${extra}`,
  );

const settings = (target: Page) =>
  column(target).getByRole("region", {
    name: label("desktop.providers.title"),
  });

const download = (scope: ReturnType<typeof column>) =>
  scope.getByRole("button", {
    name: label("desktop.agent.download_models"),
    exact: true,
  });

const catalogReads = (target: Page) =>
  target.evaluate(
    () =>
      (window.__scenarioHostCalls ?? []).filter(
        (call) => call === "agentProviderCatalog",
      ).length,
  );

test("a model this computer lacks is listed but cannot be chosen, and the picker offers its download", async ({
  page: target,
}) => {
  expect(absent.length).toBeGreaterThan(0);
  expect(held.length).toBeGreaterThan(0);
  await open(target);
  const picker = await openModelPicker(target);
  await pickWay(target, picker, LOCAL);
  const field = picker.getByLabel(label("desktop.agent.model"));
  for (const entry of absent) {
    const option = field.locator(`option[value="${entry.entry_id}"]`);
    await expect(option).toBeDisabled();
    await expect(option).toHaveText(
      label("desktop.agent.model_not_installed", {
        name: entry.display_name,
      }),
    );
  }
  for (const entry of held) {
    const option = field.locator(`option[value="${entry.entry_id}"]`);
    await expect(option).toBeEnabled();
    await expect(option).toHaveText(entry.display_name);
  }
  // The way starts on a model this computer holds.
  expect(held.map((entry) => entry.entry_id)).toContain(
    await field.inputValue(),
  );
  await expect(picker).toContainText(label("desktop.agent.models_to_download"));
  await download(picker).click();
  await expect(picker).toBeHidden();
  await expect(settings(target)).toBeVisible();
});

test("with no model on this computer the local lane cannot be chosen, and the column offers the download", async ({
  page: target,
}) => {
  await open(target, "&catalog=local-only&models=none");
  const notice = column(target)
    .getByRole("status")
    .filter({
      hasText: label("desktop.agent.no_installed_model"),
    });
  await expect(notice).toBeVisible();
  await expect(
    notice.getByRole("button", {
      name: label("desktop.agent.set_up_providers"),
    }),
  ).toHaveCount(0);
  // Nothing can be sent with a model this computer does not hold.
  await messageField(target).fill("Hello");
  await messageField(target).press("Enter");
  expect(
    (await target.evaluate(() => window.__scenarioHostCalls ?? [])).some(
      (call) => call.startsWith("agentSend "),
    ),
  ).toBe(false);

  const picker = await openModelPicker(target);
  await picker
    .getByRole("button", { name: label("desktop.agent.provider") })
    .click();
  const lane = target.locator(`[role=option][data-way="${LOCAL}"]`);
  await expect(lane).toHaveAttribute("data-disabled", "true");
  await expect(lane).toContainText(
    label("desktop.agent.lane_no_installed_model"),
  );
  await target.keyboard.press("Escape");
  await expect(target.getByRole("listbox")).toBeHidden();
  await expect(picker).toContainText(label("desktop.agent.models_to_download"));
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();

  await download(notice).click();
  await expect(settings(target)).toBeVisible();
});

test("a send for a model this computer no longer holds is refused in words with the way to download it", async ({
  page: target,
}) => {
  await open(target);
  const picker = await openModelPicker(target);
  await pickWay(target, picker, LOCAL);
  const chosen = await picker
    .getByLabel(label("desktop.agent.model"))
    .inputValue();
  expect(held.map((entry) => entry.entry_id)).toContain(chosen);
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();
  // The model is removed behind the window's back: the catalog it chose
  // from still lists it as held.
  await target.evaluate(
    (model) => window.__scenarioModelPresence!.mark(model, false),
    held.find((entry) => entry.entry_id === chosen)!.model,
  );
  const readsBefore = await catalogReads(target);

  await ask(target, "Hello");
  const alert = column(target)
    .getByRole("alert")
    .filter({
      hasText: label("desktop.agent.model_not_installed_refused"),
    });
  await expect(alert).toBeVisible();
  await expect(alert).not.toContainText(label("desktop.agent.request_failed"));
  // The message is given back to try again.
  await expect(messageField(target)).toHaveValue("Hello");
  // What is offered is read again, and the lost model is no longer chosen.
  await expect.poll(() => catalogReads(target)).toBeGreaterThan(readsBefore);
  const again = await openModelPicker(target);
  await expect(again.getByLabel(label("desktop.agent.model"))).not.toHaveValue(
    chosen,
  );
  await target.keyboard.press("Escape");
  await expect(again).toBeHidden();

  await download(alert).click();
  await expect(settings(target)).toBeVisible();
});

// A model this computer cannot run is refused with its own sentence and the
// way on, the local AI's settings, on either engine's lane; the generic
// failure is never shown for it.
for (const lane of ["llamacpp/api", "ollama/api"]) {
  test(`a send for a model that does not fit on ${lane} is refused in the served words with the way on`, async ({
    page: target,
  }) => {
    await open(target);
    const picker = await openModelPicker(target);
    await pickWay(target, picker, lane);
    await target.keyboard.press("Escape");
    await expect(picker).toBeHidden();
    await ask(target, "Esto no cabe");
    const alert = column(target)
      .getByRole("alert")
      .filter({ hasText: label("desktop.agent.model_does_not_fit_refused") });
    await expect(alert).toBeVisible();
    await expect(alert).not.toContainText(
      label("desktop.agent.request_failed"),
    );
    // The message is given back to try again.
    await expect(messageField(target)).toHaveValue("Esto no cabe");
    await download(alert).click();
    await expect(settings(target)).toBeVisible();
  });
}
