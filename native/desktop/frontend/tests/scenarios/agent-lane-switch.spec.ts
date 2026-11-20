import { expect, test, type Locator, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import { FIXTURE_RUNS } from "../../src/dev/fixtures/agent";
import {
  agentColumn as column,
  agentTurns,
  ask,
  messageField,
  openConversation,
  openModelPicker,
  personTurns,
  pickWay,
  scenarioOnly,
  send,
  settled,
} from "../support/agent";
import { label } from "../support/strings";

// A conversation that has run is fixed to the lane its newest reply ran on.
// Another lane is a new conversation that carries the old one; a change of
// model within the lane waits on the person's word; a model the lane no
// longer serves is answered with the way to choose another. What is sent is
// what the scenario host's agent recorded of the request, since the agent
// decides each of these and the column only says it and offers the answer.

const SOURCE = "IVA del tercer trimestre";
const SOURCE_ID = "c-iva-t3";
// The lane the source conversation ran on, and another one the picker offers.
const RAN = "kimi/api";
const OTHER = "qwen/api";

const lanes = FIXTURE_CATALOG.providers ?? [];
const laneOf = (way: string) => {
  const served = lanes.find(
    (held) => `${held.provider_id}/${held.transport}` === way,
  );
  if (!served) throw new Error(`The fixture catalog has no lane ${way}.`);
  return served;
};

const source = FIXTURE_RUNS[SOURCE_ID]?.at(-1);
if (!source) throw new Error("The fixture has no source conversation.");
// What the source conversation holds, counted here from its own messages: the
// four messages of its two turns.
const MESSAGES = source.messages;
const TURNS = MESSAGES.filter((message) => message.role === "user").length;
const THOUSANDS = new Intl.NumberFormat("en");

const open = (target: Page, query = "") =>
  target.goto(`/scenarios.html?scenario=signed-in&latency=0&bar=off${query}`);
const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);
/** The sends the host took, as `<conversation> <provider>/<transport>`. */
const sends = async (target: Page) =>
  (await calls(target))
    .filter((call) => call.startsWith("agentSend "))
    .map((call) => call.slice("agentSend ".length));
const notice = (target: Page, slot: string) =>
  column(target).locator(`[data-slot="${slot}"]`);

/** Chooses the lane `way` in the open model picker and closes the picker. */
async function chooseLane(target: Page, way: string) {
  const picker = await openModelPicker(target);
  await pickWay(target, picker, way);
  await picker
    .getByRole("button", { name: label("desktop.agent.provider") })
    .focus();
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();
}

/** Chooses `model` of the lane the picker is on and closes the picker. */
async function chooseModel(target: Page, model: string) {
  const picker = await openModelPicker(target);
  await picker.getByLabel(label("desktop.agent.model")).selectOption(model);
  await picker
    .getByRole("button", { name: label("desktop.agent.provider") })
    .focus();
  await target.keyboard.press("Escape");
  await expect(picker).toBeHidden();
}

const entry = (target: Page, way: string): Locator =>
  target.locator(`[role=option][data-way="${way}"]`);

test.beforeEach(async ({ page: target }) => {
  scenarioOnly("The conversations and the agent's answers are the host's.");
  await target.addInitScript(() => localStorage.clear());
});

test("a conversation that has run offers every other lane as a new conversation", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, SOURCE);
  const picker = await openModelPicker(target);
  await picker
    .getByRole("button", { name: label("desktop.agent.provider") })
    .click();
  const hint = label("desktop.agent.continue_in_new_conversation");
  await expect(entry(target, OTHER)).toContainText(hint);
  await expect(entry(target, RAN)).not.toContainText(hint);
  await target.keyboard.press("Escape");

  // A conversation that has not run is on no lane yet: no entry carries it.
  await target.keyboard.press("Escape");
  await column(target)
    .getByRole("button", { name: label("desktop.agent.new_conversation") })
    .click();
  const fresh = await openModelPicker(target);
  await fresh
    .getByRole("button", { name: label("desktop.agent.provider") })
    .click();
  await expect(entry(target, OTHER)).toBeVisible();
  await expect(entry(target, OTHER)).not.toContainText(hint);
  await expect(entry(target, RAN)).not.toContainText(hint);
});

test("choosing another lane leaves the conversation, and the next message carries it once", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, SOURCE);
  await expect(personTurns(target)).toHaveCount(2);
  await chooseLane(target, OTHER);

  // The column shows no conversation, and says what the next message does.
  await expect(personTurns(target)).toHaveCount(0);
  await expect(agentTurns(target)).toHaveCount(0);
  await expect(notice(target, "carry-pending")).toBeVisible();
  expect(await sends(target)).toEqual([]);

  await send(target, "Sigue con el modelo 303.");
  await settled(target);
  // It went to the lane the picker showed, as a conversation of its own, with
  // the source named and nothing sent into the source.
  const [first, ...more] = await sends(target);
  expect(more).toEqual([]);
  const [started, way] = (first ?? "").split(" ");
  expect(way).toBe(OTHER);
  expect(started).not.toBe(SOURCE_ID);
  expect(await calls(target)).toContain(
    `agentSendCarriesFrom ${started} ${SOURCE_ID}`,
  );
  // What the agent counted of the source's turns is shown, and the pending
  // notice is gone.
  const carried = 1;
  await expect(notice(target, "carried")).toContainText(
    label("desktop.agent.carried_turns", {
      carried,
      omitted: TURNS - carried,
    }),
  );
  await expect(notice(target, "carry-pending")).toHaveCount(0);

  // The source carries once: the next message of the new conversation names
  // no source.
  await send(target, "Y el 130.");
  await settled(target);
  const lines = await calls(target);
  expect(
    lines.filter((call) => call.startsWith("agentSendCarriesFrom")),
  ).toEqual([`agentSendCarriesFrom ${started} ${SOURCE_ID}`]);
  expect(await sends(target)).toEqual([
    `${started} ${OTHER}`,
    `${started} ${OTHER}`,
  ]);
});

test("the notice names the conversation it carries by its title", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, SOURCE);
  await chooseLane(target, OTHER);
  await expect(notice(target, "carry-pending")).toContainText(
    label("desktop.agent.carry_pending", { title: SOURCE }),
  );
});

test("back to the source conversation reopens it, with its own lane and nothing sent", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, SOURCE);
  await chooseLane(target, OTHER);
  await notice(target, "carry-pending")
    .getByRole("button", { name: label("desktop.agent.carry_back") })
    .click();

  await expect(notice(target, "carry-pending")).toHaveCount(0);
  await expect(personTurns(target)).toHaveCount(2);
  expect(await sends(target)).toEqual([]);
  // The source is on its own lane again, and a message goes there.
  const picker = await openModelPicker(target);
  await expect(
    picker.getByRole("button", { name: label("desktop.agent.provider") }),
  ).toHaveAccessibleName(new RegExp(`${laneOf(RAN).display_name}`));
  await target.keyboard.press("Escape");
  await send(target, "Una pregunta más.");
  expect(await sends(target)).toEqual([`${SOURCE_ID} ${RAN}`]);
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentSendCarries")),
  ).toEqual([]);
});

test("a send is never sent on a lane the picker did not show", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, SOURCE);
  // The picker is moved to another lane and back again before sending.
  await chooseLane(target, OTHER);
  await notice(target, "carry-pending")
    .getByRole("button", { name: label("desktop.agent.carry_back") })
    .click();
  await send(target, "¿Algo más del soportado?");
  await settled(target);
  const [only, ...more] = await sends(target);
  expect(more).toEqual([]);
  expect(only).toBe(`${SOURCE_ID} ${RAN}`);
});

test("the agent refuses a continuing send on another lane, and says which", async ({
  page: target,
}) => {
  await open(target);
  await expect(messageField(target)).toBeVisible();
  const refusal = await target.evaluate(async (id) => {
    try {
      await window.__fixtureAgentSession?.send({
        conversation_id: id,
        text: "Por otro carril.",
        selection: {
          provider: "qwen",
          transport: "api",
          model: "fixture-chat",
        },
      });
      return null;
    } catch (error) {
      const { code, lane } = error as {
        code?: string;
        lane?: { provider: string; transport: string };
      };
      return { code, lane };
    }
  }, SOURCE_ID);
  expect(refusal).toEqual({
    code: "agent_gateway_conversation_lane_fixed",
    lane: { provider: "kimi", transport: "api" },
  });
});

test("a change of model within the lane waits on the person, and is acknowledged once", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, SOURCE);
  await chooseModel(target, "fixture-quick");
  const text = "¿Y con otro modelo?";
  await ask(target, text);

  // The message is given back, and the agent's facts are said.
  const asked = notice(target, "selection-change");
  await expect(asked).toBeVisible();
  await expect(asked).toContainText("fixture-deep");
  await expect(asked).toContainText("fixture-quick");
  const tokens = Math.ceil(
    MESSAGES.reduce((sum, message) => sum + message.text.length, 0) / 4,
  );
  await expect(asked).toContainText(
    label("desktop.agent.selection_change_history", {
      retained: MESSAGES.length,
      tokens: THOUSANDS.format(tokens),
      omitted: 0,
    }),
  );
  await expect(messageField(target)).toHaveValue(text);
  await expect(personTurns(target)).toHaveCount(2);
  expect(await sends(target)).toEqual([`${SOURCE_ID} ${RAN}`]);
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentSendAck")),
  ).toEqual([]);

  // Confirming sends the same message again, acknowledged.
  await asked
    .getByRole("button", {
      name: label("desktop.agent.selection_change_confirm"),
    })
    .click();
  await expect(personTurns(target).filter({ hasText: text })).toBeVisible();
  await expect(asked).toHaveCount(0);
  await settled(target);
  expect(await sends(target)).toEqual([
    `${SOURCE_ID} ${RAN}`,
    `${SOURCE_ID} ${RAN}`,
  ]);
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentSendAck")),
  ).toEqual([`agentSendAcknowledged ${SOURCE_ID}`]);

  // The acknowledgement was for that one message: the next goes without it,
  // on the model now chosen.
  await send(target, "Gracias, una última duda.");
  await settled(target);
  expect((await sends(target)).length).toBe(3);
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentSendAck")),
  ).toEqual([`agentSendAcknowledged ${SOURCE_ID}`]);
  await expect(notice(target, "selection-change")).toHaveCount(0);
});

test("keeping the conversation's model leaves the message unsent in the composer", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, SOURCE);
  await chooseModel(target, "fixture-quick");
  const text = "¿Y con otro modelo?";
  await ask(target, text);
  const asked = notice(target, "selection-change");
  await expect(asked).toBeVisible();
  await asked
    .getByRole("button", { name: label("desktop.agent.selection_change_keep") })
    .click();

  await expect(asked).toHaveCount(0);
  await expect(messageField(target)).toHaveValue(text);
  await expect(personTurns(target)).toHaveCount(2);
  expect(await sends(target)).toEqual([`${SOURCE_ID} ${RAN}`]);
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentSendAck")),
  ).toEqual([]);
});

test("the agent states a change of model with the counts of what the new model reads", async ({
  page: target,
}) => {
  await open(target);
  await expect(messageField(target)).toBeVisible();
  const outcome = await target.evaluate(async (id) => {
    const session = window.__fixtureAgentSession;
    const request = {
      conversation_id: id,
      text: "Con otro esfuerzo.",
      selection: {
        provider: "kimi",
        transport: "api" as const,
        model: "fixture-deep",
        effort: "low" as const,
      },
    };
    try {
      await session?.send(request);
      return null;
    } catch (error) {
      const { code, selection_change } = error as {
        code?: string;
        selection_change?: unknown;
      };
      return { code, selection_change };
    }
  }, SOURCE_ID);
  expect(outcome?.code).toBe("agent_gateway_selection_change_unacknowledged");
  expect(outcome?.selection_change).toMatchObject({
    previous: { model: "fixture-deep", effort: "high" },
    requested: { model: "fixture-deep", effort: "low" },
    history: {
      retained_messages: MESSAGES.length,
      omitted_messages: 0,
    },
  });
});

test("a reply that failed for a model the lane no longer serves names it and offers another", async ({
  page: target,
}) => {
  await open(target);
  await send(target, "Este modelo no disponible falla.");
  await settled(target);

  const lane = laneOf(RAN);
  const model = lane.catalog.models?.find(
    (held) => held.model === "fixture-deep",
  );
  const failed = agentTurns(target);
  await expect(failed).toContainText(
    label("desktop.agent.condition_model_unavailable_named", {
      model: model?.display_name ?? "",
      provider: lane.display_name,
      connection: label("desktop.providers.connection_api"),
    }),
  );
  await expect(failed).not.toContainText("model not found");
  // It is not retried as it is: the way on is another model.
  await expect(
    failed.getByRole("button", { name: label("desktop.agent.retry") }),
  ).toHaveCount(0);
  await failed
    .getByRole("button", { name: label("desktop.agent.choose_another_model") })
    .click();
  await expect(
    target.getByRole("dialog", { name: label("desktop.agent.settings_title") }),
  ).toBeVisible();
});

test("a lane the agent cannot read moves the message to a new conversation that carries the old one", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, SOURCE);
  const text = "Con un carril ilegible.";
  await ask(target, text);

  await expect(notice(target, "carry-pending")).toBeVisible();
  await expect(column(target)).toContainText(
    label("desktop.agent.lane_unreadable_refused"),
  );
  await expect(messageField(target)).toHaveValue(text);
  await expect(personTurns(target)).toHaveCount(0);

  // Sent again, the message starts the new conversation with the source.
  await messageField(target).press("Enter");
  await expect(personTurns(target).filter({ hasText: text })).toBeVisible();
  const [refused, started] = await sends(target);
  expect(refused).toBe(`${SOURCE_ID} ${RAN}`);
  const [conversationId] = (started ?? "").split(" ");
  expect(conversationId).not.toBe(SOURCE_ID);
  expect(await calls(target)).toContain(
    `agentSendCarriesFrom ${conversationId} ${SOURCE_ID}`,
  );
  await expect(notice(target, "carried")).toBeVisible();
});

test.describe("a catalog that still shows the packaged model list", () => {
  test.describe.configure({ timeout: 60_000 });

  const resolved = async (target: Page) =>
    (await calls(target)).filter(
      (call) => call === "agentProviderCatalogResolved",
    ).length;

  test("is read again after a pause, and stops once the account's list is served", async ({
    page: target,
  }) => {
    await target.addInitScript(() => {
      window.__fixtureCatalogStaleReads = 1;
    });
    await open(target);
    await expect.poll(() => resolved(target)).toBe(1);
    // Not at once: the pause is about two seconds.
    await target.waitForTimeout(1_000);
    expect(await resolved(target)).toBe(1);
    await expect.poll(() => resolved(target), { timeout: 10_000 }).toBe(2);
    // The second answer is the account's: no third read follows.
    await target.waitForTimeout(3_000);
    expect(await resolved(target)).toBe(2);
  });

  test("keeps being read while it is stale, after pauses that grow", async ({
    page: target,
  }) => {
    await target.addInitScript(() => {
      window.__fixtureCatalogStaleReads = 100;
    });
    await open(target);
    await expect.poll(() => resolved(target)).toBe(1);
    // The pauses are about two, four and eight seconds, then sixteen: the
    // fourth read is not before the first three pauses have passed.
    await expect.poll(() => resolved(target), { timeout: 20_000 }).toBe(4);
    await target.waitForTimeout(5_000);
    expect(await resolved(target)).toBe(4);
    await expect.poll(() => resolved(target), { timeout: 30_000 }).toBe(5);
  });
});
