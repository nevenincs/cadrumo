import { expect, test, type Page } from "@playwright/test";
import {
  agentColumn as column,
  agentTurns,
  ask,
  conversation,
  messageField as field,
  worded,
} from "../support/agent";
import { label } from "../support/strings";

// The agent column at work: a message goes when the person sends it, its
// reply streams into the conversation as the host writes it, a reply can be
// stopped, and what can run it is the agent's own catalog. The scenario
// host's reply repeats the message; its stream sends one piece twice, or with
// `stream=gap` leaves one out.

const open = (target: Page, scenario = "signed-in", query = "") =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off${query}`);

const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

/** The reply the scenario host writes to `text`, as it ends. */
const replyTo = (text: string) =>
  `Has escrito: «${text}». En estos datos de prueba no hay nada que revisar.`;

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("a message goes when it is sent, and its reply streams in once", async ({
  page: target,
}) => {
  await open(target);
  // The development lane says so for as long as it is used.
  await expect(column(target).getByRole("note")).toHaveText(
    label("desktop.agent.lane_notice"),
  );
  // Sending is the person's decision: nothing asks them to confirm it.
  await ask(target, "¿Cuánto IVA pagué en julio?");
  const log = conversation(target);
  await expect(log).toContainText("¿Cuánto IVA pagué en julio?");
  await expect(log).toContainText("Leer los apuntes del libro del trimestre");
  const replies = agentTurns(target);
  // Every piece once, the one the stream sent twice included.
  await expect(replies).toHaveText([
    "Lo miro en tus apuntes.",
    replyTo("¿Cuánto IVA pagué en julio?"),
  ]);
  await expect(log).not.toContainText(label("desktop.agent.working"));
  // The conversation is named after its first message once the reply ends.
  await expect(
    column(target).getByRole("heading", {
      name: "¿Cuánto IVA pagué en julio?",
    }),
  ).toBeVisible();

  // The conversation was watched before anything was sent to it.
  const made = await calls(target);
  const observed = made.findIndex((call) => call.startsWith("agentObserve "));
  const sent = made.findIndex((call) => call.startsWith("agentSend "));
  expect(observed).toBeGreaterThanOrEqual(0);
  expect(sent).toBeGreaterThan(observed);

  await ask(target, "¿Y en agosto?");
  await expect(replies.last()).toHaveText(replyTo("¿Y en agosto?"));
  // Two messages, two sends, and no question in between.
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentSend ")),
  ).toHaveLength(2);
  await expect(
    column(target).getByRole("region", {
      name: worded("desktop.agent.consent_title"),
    }),
  ).toHaveCount(0);
});

test("a reply stopped while it is written says it was stopped", async ({
  page: target,
}) => {
  await open(target);
  await ask(target, "Repasa el trimestre");
  await expect(conversation(target)).toContainText("Lo miro");
  await column(target)
    .getByRole("button", { name: label("desktop.agent.stop") })
    .click();
  await expect(conversation(target)).toContainText(
    label("desktop.agent.stopped"),
  );
  await expect(
    column(target).getByRole("button", {
      name: label("desktop.agent.send"),
      exact: false,
    }),
  ).toBeVisible();
  await expect(conversation(target)).not.toContainText(
    replyTo("Repasa el trimestre"),
  );
});

test("text the stream never sent is recovered from the history", async ({
  page: target,
}) => {
  await open(target, "signed-in", "&stream=gap");
  await ask(target, "Hola");
  const replies = agentTurns(target);
  await expect(replies).toHaveText([
    "Lo miro en tus apuntes.",
    replyTo("Hola"),
  ]);
  // Read once when the conversation opened, and again for the gap.
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentHistory ")),
  ).toHaveLength(2);
});

test("an agent that cannot serve says why, and nothing can be sent", async ({
  page: target,
}) => {
  await open(target, "views-refused");
  await expect(column(target).getByRole("note")).toBeVisible();
  await expect(column(target).getByRole("status")).toContainText(
    label("desktop.agent.service_signed_out"),
  );
  await field(target).fill("Hola");
  await expect(
    column(target).getByRole("button", {
      name: `${label("desktop.agent.send")}, ${label("desktop.agent.unavailable")}`,
    }),
  ).toBeVisible();
});

test("the providers, models and efforts offered are the agent's own catalog", async ({
  page: target,
}) => {
  await open(target);
  await column(target)
    .getByRole("button", { name: /^Model and effort|^Modelo/ })
    .first()
    .click();
  const settings = target.getByRole("dialog", {
    name: label("desktop.agent.settings_title"),
  });
  const provider = settings.getByRole("combobox", {
    name: label("desktop.agent.provider"),
  });
  // Every lane the catalog lists, and those that cannot run held back.
  await expect(provider.locator("option")).toHaveCount(12);
  await expect(provider.locator("option:disabled")).toHaveCount(8);
  await provider.selectOption({ label: "OpenAI" });
  const model = settings.getByRole("combobox", {
    name: label("desktop.agent.model"),
  });
  const effort = settings.getByRole("combobox", {
    name: label("desktop.agent.effort"),
  });
  // The lane's recommended model, with the efforts that model takes.
  await expect(model).toHaveValue("fixture-ultra");
  await expect(effort.locator("option")).toHaveText([
    label("desktop.agent.effort_high"),
    label("desktop.agent.effort_ultra"),
  ]);
  // Another model takes other efforts, and a setting of its own.
  await model.selectOption("fixture-tiered");
  await expect(effort.locator("option")).toHaveText([
    label("desktop.agent.effort_low"),
    label("desktop.agent.effort_medium"),
    label("desktop.agent.effort_high"),
  ]);
  await expect(
    settings.getByRole("combobox", { name: "Fixture service tier" }),
  ).toHaveValue("standard");
});
