import { expect, test, type Locator, type Page } from "@playwright/test";
import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import {
  agentColumn as column,
  agentTurns,
  approvalPrompt,
  ask,
  conversation,
  live,
  messageField as field,
  openConversation,
  openHistory,
  personTurns,
  refusalOfSend,
  replyFacts,
  replyState,
  scenarioOnly,
  send,
  settled,
  toolRow,
  toolRows,
  worded,
} from "../support/agent";
import { label } from "../support/strings";

// The agent column at work: a message goes when the person sends it, its
// reply streams into the conversation as the host writes it, a reply can be
// stopped, and what can run it is the agent's own catalog. The scenario
// host's reply repeats the message; its stream sends one frame twice, or with
// `stream=gap` loses the stream once.
//
// These specs also run against the desktop and the real agent. Whatever only
// the scenario host can answer, such as its call log, the words of its replies
// or a message it answers in a way of its own, is left to it.

const open = (target: Page, scenario = "signed-in", query = "") =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off${query}`);

const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

/** The reply the scenario host writes to `text`, as one message: what it says
 * before the tool and what it says after, a paragraph apart. */
const replyTo = (text: string) =>
  `Lo miro en tus apuntes. Has escrito: «${text}». En estos datos de prueba no hay nada que revisar.`;

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
  await settled(target);
  await expect(personTurns(target)).toHaveCount(1);
  await expect(agentTurns(target)).toHaveCount(1);
  await expect(log).not.toContainText(label("desktop.agent.working"));
  await expect(
    column(target).getByRole("region", {
      name: worded("desktop.agent.consent_title"),
    }),
  ).toHaveCount(0);

  if (live()) return;
  // The reply is one message, whole: the frame sent twice is applied once, and
  // the tool between its two parts does not start another message.
  await expect(agentTurns(target)).toHaveText([
    replyTo("¿Cuánto IVA pagué en julio?"),
  ]);
  // The tool is named as the agent names it, with its kind and where it got to.
  const row = toolRow(target, "ledger_list");
  await expect(row).toHaveCount(1);
  await expect(row).toContainText(label("desktop.agent.tool_kind_read"));
  await expect(row).toContainText(label("desktop.agent.tool_done"));
  // The conversation is named after its first message once the reply ends.
  await expect(
    column(target).getByRole("heading", {
      name: "¿Cuánto IVA pagué en julio?",
    }),
  ).toBeVisible();
  // What the agent served of the reply: what it ran with and its tokens.
  await expect(replyFacts(target)).toHaveText([
    "Ran with: Claude, Fixture Deep",
    /^Tokens: [\d,]+ in, [\d,]+ out$/,
  ]);

  // The conversation was watched before anything was sent to it, and read
  // when it opened and again when the reply ended.
  const made = await calls(target);
  const observed = made.findIndex((call) => call.startsWith("agentObserve "));
  const sent = made.findIndex((call) => call.startsWith("agentSend "));
  expect(observed).toBeGreaterThanOrEqual(0);
  expect(sent).toBeGreaterThan(observed);
  expect(made.filter((call) => call.startsWith("agentObserve "))).toHaveLength(
    1,
  );
  expect(made.filter((call) => call.startsWith("agentHistory "))).toHaveLength(
    2,
  );

  // The next message continues the conversation in a run of its own, and the
  // first message is not shown twice for it.
  await send(target, "¿Y en agosto?");
  await settled(target);
  await expect(personTurns(target)).toHaveCount(2);
  await expect(agentTurns(target)).toHaveText([
    replyTo("¿Cuánto IVA pagué en julio?"),
    replyTo("¿Y en agosto?"),
  ]);
  // Two messages, two sends, and no question in between.
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentSend ")),
  ).toHaveLength(2);
});

test("two identical messages are two messages", async ({ page: target }) => {
  scenarioOnly("the scenario host's replies are what lets each one finish");
  await open(target);
  await send(target, "Hola");
  await settled(target);
  await ask(target, "Hola");
  await expect(personTurns(target)).toHaveCount(2);
  await settled(target);
  // The history gives both one id; only their order tells them apart.
  await expect(personTurns(target)).toHaveText([/Hola/, /Hola/]);
  await expect(agentTurns(target)).toHaveCount(2);
});

test("a reply stopped while it is written says it is stopping, and then that it was stopped", async ({
  page: target,
}) => {
  await open(target);
  await ask(target, "Repasa el trimestre");
  const stop = column(target).getByRole("button", {
    name: label("desktop.agent.stop"),
  });
  await expect(stop).toBeVisible();
  await stop.click();
  if (!live())
    // The agent stops a run in two steps, and the column says so between them.
    await expect(replyState(target)).toHaveText(
      label("desktop.agent.reply_stopping"),
    );
  await expect(conversation(target)).toContainText(
    label("desktop.agent.stopped"),
  );
  await expect(replyState(target)).toHaveCount(0);
  await expect(
    column(target).getByRole("button", {
      name: label("desktop.agent.send"),
      exact: false,
    }),
  ).toBeVisible();
  if (!live())
    await expect(conversation(target)).not.toContainText(
      replyTo("Repasa el trimestre"),
    );
});

test("a lost stream is recovered by reading again and watching anew", async ({
  page: target,
}) => {
  scenarioOnly("the scenario host loses the stream where `stream=gap` asks");
  await open(target, "signed-in", "&stream=gap");
  await ask(target, "Hola");
  // The text the lost stream missed comes back with the replay the new watch
  // is given, and the reply is whole.
  await expect(agentTurns(target)).toHaveText([replyTo("Hola")]);
  await settled(target);
  const made = (await calls(target)).filter((call) =>
    /^agent(Observe|History) /.test(call),
  );
  // Watched and read, then the loss: watched anew and read again, and read
  // once more when the reply ended.
  expect(made.map((call) => call.split(" ")[0])).toEqual([
    "agentObserve",
    "agentHistory",
    "agentObserve",
    "agentHistory",
    "agentHistory",
  ]);
});

test("a tool that failed is shown as failed", async ({ page: target }) => {
  scenarioOnly("the scenario host fails a tool when it is asked to");
  await open(target);
  await send(target, "La herramienta falla, prueba otra cosa.");
  await settled(target);
  const row = toolRow(target, "ledger_list");
  await expect(row).toHaveCount(1);
  await expect(row).toContainText(label("desktop.agent.tool_failed"));
  await expect(row).toContainText(label("desktop.agent.tool_kind_read"));
  // The reply goes on, and the failure is not hidden by it.
  await expect(agentTurns(target)).toHaveCount(1);
  await expect(toolRows(target)).toHaveCount(1);
});

test("a run that failed before it wrote shows why, from the run, with no message of the agent's", async ({
  page: target,
}) => {
  scenarioOnly("the scenario host fails a run when it is asked to");
  await open(target);
  await send(target, "Esto falla antes de escribir.");
  const failure = agentTurns(target);
  await expect(failure).toHaveCount(1);
  await expect(failure).toContainText(
    `${label("desktop.agent.condition_provider_overloaded")}: The provider answered 529 overloaded_error.`,
  );
  await expect(toolRows(target)).toHaveCount(0);
  await expect(conversation(target)).not.toContainText(
    label("desktop.agent.working"),
  );
  // Reading the conversation again gives the same, from the history.
  await column(target)
    .getByRole("button", { name: label("desktop.agent.new_conversation") })
    .click();
  await openConversation(target, "Esto falla antes de escribir.");
  await expect(agentTurns(target)).toHaveCount(1);
  await expect(agentTurns(target)).toContainText(
    label("desktop.agent.condition_provider_overloaded"),
  );
});

test("a conversation from the host that failed before it wrote shows the same", async ({
  page: target,
}) => {
  scenarioOnly("the conversations are the scenario host's");
  await open(target);
  await openConversation(target, "Pago fraccionado del 130");
  await expect(personTurns(target)).toHaveCount(1);
  await expect(agentTurns(target)).toHaveCount(1);
  await expect(agentTurns(target)).toContainText(
    `${label("desktop.agent.condition_provider_overloaded")}: The provider answered 529 overloaded_error.`,
  );
});

test("a run stopped before it wrote says it was stopped", async ({
  page: target,
}) => {
  scenarioOnly("the conversations are the scenario host's");
  await open(target);
  await openConversation(target, "Facturas de septiembre");
  await expect(agentTurns(target)).toHaveCount(1);
  await expect(agentTurns(target)).toContainText(
    label("desktop.agent.stopped"),
  );
});

test("a conversation of several runs shows each message once, the tools before the reply they belong to", async ({
  page: target,
}) => {
  scenarioOnly("the conversations are the scenario host's");
  await open(target);
  await openConversation(target, "IVA del tercer trimestre");
  // The second run was seeded with the first's messages under new ids; the
  // host leaves them out.
  await expect(personTurns(target)).toHaveCount(2);
  await expect(personTurns(target).first()).toContainText(
    "¿Me preparas el 303?",
  );
  await expect(personTurns(target).last()).toContainText(
    "¿Y qué parte del soportado es deducible?",
  );
  await expect(agentTurns(target)).toHaveCount(2);
  await expect(agentTurns(target).first()).toContainText(
    "He leído 42 apuntes del trimestre.",
  );
  // Each tool as the agent named it, and where it got to.
  const read = toolRow(target, "ledger_list");
  await expect(read).toContainText(label("desktop.agent.tool_done"));
  const register = toolRow(target, "ledger_register_invoice");
  await expect(register).toContainText(label("desktop.agent.tool_failed"));
  await expect(register).toContainText(label("desktop.agent.tool_kind_edit"));
  // The tools come before the first reply's message, after the person's.
  const order = await conversation(target)
    .getByRole("listitem")
    .evaluateAll((items) =>
      items.map((item) =>
        item.querySelector("article")
          ? (item.querySelector("article")?.getAttribute("aria-label") ?? "")
          : "tool",
      ),
    );
  expect(order).toEqual([
    label("desktop.agent.you_said"),
    "tool",
    "tool",
    label("desktop.agent.agent_replied"),
    label("desktop.agent.you_said"),
    label("desktop.agent.agent_replied"),
  ]);
  // What the replies ran with and the tokens they used, all of them counted.
  await expect(replyFacts(target)).toHaveText([
    "Ran with: Claude, Fixture Deep, High",
    "Tokens: 39,290 in, 1,950 out",
  ]);
});

test("a conversation the agent was given no title for says it is not available yet", async ({
  page: target,
}) => {
  scenarioOnly("the conversations are the scenario host's");
  await open(target);
  const body = await openHistory(target);
  await expect(
    body.getByText(label("desktop.agent.unavailable"), { exact: true }),
  ).toHaveCount(1);
  await body
    .getByText(label("desktop.agent.unavailable"), { exact: true })
    .click();
  await expect(
    column(target).getByRole("heading", {
      name: label("desktop.agent.unavailable"),
    }),
  ).toBeVisible();
  await expect(personTurns(target)).toContainText("¿Cuándo vence el 303?");
});

test("a run that needs repair, or is being reconciled, says so and takes no message", async ({
  page: target,
}) => {
  scenarioOnly("the conversations are the scenario host's");
  await open(target);
  const send = column(target).getByRole("button", {
    name: label("desktop.agent.send"),
    exact: false,
  });
  await openConversation(target, "Una respuesta que se quedó a medias");
  await expect(replyState(target)).toHaveText(
    label("desktop.agent.reply_repair_needed"),
  );
  // The transcript draws neither Working nor Stopped for it, and the agent
  // takes no message while it is so.
  await expect(conversation(target)).not.toContainText(
    label("desktop.agent.working"),
  );
  await expect(send).toHaveAttribute("aria-disabled", "true");
  await openConversation(target, "Una respuesta que se está conciliando");
  await expect(replyState(target)).toHaveText(
    label("desktop.agent.reply_reconciling"),
  );
  await expect(send).toHaveAttribute("aria-disabled", "true");
});

test("messages queued behind a run are counted, and the run is still going", async ({
  page: target,
}) => {
  scenarioOnly("the conversations are the scenario host's");
  await open(target);
  await openConversation(target, "Una respuesta con un mensaje en cola");
  await expect(replyState(target)).toHaveText(
    label("desktop.agent.reply_queued", { count: 2 }),
  );
  await expect(conversation(target)).toContainText(
    label("desktop.agent.working"),
  );
  await expect(toolRow(target, "ledger_list")).toBeVisible();
  await expect(
    column(target).getByRole("button", { name: label("desktop.agent.stop") }),
  ).toBeVisible();
});

test("a message sent while a reply is going is refused, and the column says a reply is in progress", async ({
  page: target,
}) => {
  scenarioOnly("the scenario host answers a message that says it is busy");
  await open(target);
  // Another client has a run going: the host refuses the send, and nothing is
  // queued.
  await ask(target, "Estoy ocupado, ¿puedes responder?");
  await expect(column(target).getByRole("alert")).toHaveText(
    label("desktop.agent.reply_in_progress"),
  );
  // The message is given back to be sent again.
  await expect(field(target)).toHaveValue("Estoy ocupado, ¿puedes responder?");
  await expect(personTurns(target)).toHaveCount(0);
  await expect(agentTurns(target)).toHaveCount(0);
});

test("a reply that is waiting on the person takes no second message", async ({
  page: target,
}) => {
  scenarioOnly("the session is reached through the scenario host");
  await open(target, "signed-in", "&asks=approval");
  await send(target, "Lee mis apuntes del trimestre.");
  await expect(approvalPrompt(target)).toBeVisible();
  // The column would not offer it; the host refuses it all the same.
  expect(await refusalOfSend(target, "Otra cosa más")).toBe(
    "agent_reply_in_progress",
  );
  await expect(approvalPrompt(target)).toBeVisible();
  await expect(personTurns(target)).toHaveCount(1);
});

test("a message is held at the agent's limit of 65536 characters", async ({
  page: target,
}) => {
  scenarioOnly("sending needs the scenario host's catalog to be ready");
  await open(target);
  const sendButton = column(target).getByRole("button", {
    name: label("desktop.agent.send"),
    exact: true,
  });
  await field(target).fill("a".repeat(65536));
  await expect(sendButton).not.toHaveAttribute("aria-disabled", "true");
  // Characters are code points: an emoji is one.
  await field(target).fill("😀".repeat(65536));
  await expect(sendButton).not.toHaveAttribute("aria-disabled", "true");
  await field(target).fill("a".repeat(65537));
  await expect(
    column(target).getByRole("button", {
      name: `${label("desktop.agent.send")}, ${label("desktop.agent.send_too_long", { count: 65537, max: 65536 })}`,
    }),
  ).toHaveAttribute("aria-disabled", "true");
  await field(target).press("Enter");
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentSend ")),
  ).toHaveLength(0);
});

test("the documents are not available yet, and the door says so", async ({
  page: target,
}) => {
  await open(target);
  const door = column(target)
    .getByRole("button", { name: label("desktop.agent.documents") })
    .first();
  await expect(door).toHaveAttribute("aria-disabled", "true");
  // A control that cannot act is not enabled for a click; the press is made
  // all the same, as a person makes it.
  await door.click({ force: true });
  // Nothing opens in its place: the conversation's own area stays.
  await expect(
    column(target).getByRole("button", {
      name: label("desktop.agent.close_documents"),
    }),
  ).toHaveCount(0);
  await expect(
    column(target).getByRole("heading", {
      name: label("desktop.agent.welcome_title"),
    }),
  ).toBeVisible();
  // And a conversation that has files in a custody that does not exist yet has
  // no document counted, and none asked for.
  if (live()) return;
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentDocuments")),
  ).toEqual([]);
  await openConversation(target, "IVA del tercer trimestre");
  // A control that cannot act is not enabled for a click; the press is made
  // all the same, as a person makes it.
  await door.click({ force: true });
  await expect(door).toHaveAttribute("aria-disabled", "true");
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentDocuments")),
  ).toEqual([]);
});

const rowOf = (body: Locator, title: string) =>
  body.getByRole("listitem").filter({ hasText: title });

test("a conversation is archived from the history for good, and cannot be restored", async ({
  page: target,
}) => {
  scenarioOnly("the conversations are the scenario host's");
  await open(target);
  const body = await openHistory(target);
  const archived = (count: number) =>
    label("desktop.agent.archived_toggle", { count });
  await expect(body.getByRole("button", { name: archived(2) })).toBeVisible();
  await rowOf(body, "Facturas de septiembre")
    .getByRole("button", { name: label("desktop.agent.archive") })
    .click();
  await expect(body.getByText("Facturas de septiembre")).toHaveCount(0);
  await expect(body.getByRole("button", { name: archived(3) })).toBeVisible();
  await body.getByRole("button", { name: archived(3) }).click();
  await expect(body.getByText("Facturas de septiembre")).toBeVisible();
  // The agent has no way to unarchive a run.
  await expect(
    rowOf(body, "Facturas de septiembre").getByRole("button", {
      name: new RegExp(`^${label("desktop.agent.restore")}`),
    }),
  ).toHaveAttribute("aria-disabled", "true");
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentArchive ")),
  ).toEqual(["agentArchive c-facturas-septiembre"]);
});

test("a conversation with a reply going cannot be archived, and the history says why", async ({
  page: target,
}) => {
  scenarioOnly("the conversations are the scenario host's");
  await open(target);
  const body = await openHistory(target);
  await rowOf(body, "Una respuesta con un mensaje en cola")
    .getByRole("button", { name: label("desktop.agent.archive") })
    .click();
  await expect(body.getByRole("alert")).toHaveText(
    label("desktop.agent.reply_in_progress"),
  );
  await expect(
    body.getByText("Una respuesta con un mensaje en cola"),
  ).toBeVisible();
});

test("an agent that cannot serve says why, and nothing can be sent", async ({
  page: target,
}) => {
  scenarioOnly("only the scenario host can be signed out");
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

// What the fixture catalog holds, read straight from it: the checks below
// compare the column with this, and none restates a provider.
const lanes = FIXTURE_CATALOG.providers ?? [];
const nameOf = (id: string) =>
  lanes.find((lane) => lane.provider_id === id)?.display_name ?? id;

const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const settingsButton = (target: Page) =>
  column(target).getByRole("button", {
    name: new RegExp(
      `^${escaped(label("desktop.agent.settings_label", { current: "" }))}`,
    ),
  });

/** Opens the model settings from the composer. */
async function openSettings(target: Page) {
  await settingsButton(target).first().click();
  return target.getByRole("dialog", {
    name: label("desktop.agent.settings_title"),
  });
}

const providerBox = (settings: Locator) =>
  settings.getByRole("combobox", { name: label("desktop.agent.provider") });
const modelBox = (settings: Locator) =>
  settings.getByRole("combobox", { name: label("desktop.agent.model") });
const effortBox = (settings: Locator) =>
  settings.getByRole("combobox", { name: label("desktop.agent.effort") });

/** Chooses a catalog lane by identity when providers share a name. */
async function chooseLane(target: Page, settings: Locator, way: string) {
  await providerBox(settings).click();
  await target.locator(`[role=option][data-way="${way}"]`).click();
}

test("each catalog lane is one entry of the list with its provider's mark", async ({
  page: target,
}) => {
  scenarioOnly("the providers are the scenario host's catalog");
  await open(target);
  const settings = await openSettings(target);
  await providerBox(settings).click();
  const options = target.getByRole("option");
  await expect(options).toHaveCount(lanes.length);
  await expect(options.locator("[data-slot=provider-mark]")).toHaveCount(
    lanes.length,
  );
  // Neither Claude nor Codex is listed a second time under the name of the
  // company behind its API.
  for (const name of ["Anthropic", "OpenAI"])
    await expect(options.filter({ hasText: name })).toHaveCount(0);
  for (const lane of lanes) {
    const entry = target.locator(
      `[role=option][data-way="${lane.provider_id}/${lane.transport}"]`,
    );
    await expect(entry).toContainText(lane.display_name);
    await expect(entry.locator("[data-slot=provider-mark]")).toHaveAttribute(
      "data-provider",
      lane.provider_id,
    );
    if (!lane.health.selectable)
      await expect(entry).toHaveAttribute("aria-disabled", "true");
  }
  // Those that cannot run stay in the list, disabled, with their reason.
  await expect(target.locator("[role=option][aria-disabled=true]")).toHaveCount(
    lanes.filter((lane) => !lane.health.selectable).length,
  );
  await expect(options.filter({ hasText: nameOf("kimi") })).toContainText(
    label("desktop.agent.lane_not_configured"),
  );
});

test("a provider's separate catalog lanes each offer their own models", async ({
  page: target,
}) => {
  scenarioOnly("the providers are the scenario host's catalog");
  await open(target);
  const settings = await openSettings(target);
  await expect(providerBox(settings)).toContainText(nameOf("claude"));
  await providerBox(settings).click();
  const held = target.locator('[role=option][data-way="claude/cli"]');
  await expect(held).toHaveAttribute("aria-disabled", "true");
  await expect(held).toContainText(label("desktop.agent.lane_signed_out"));
  await target.keyboard.press("Escape");
  // Codex runs both ways, with models of their own.
  await chooseLane(target, settings, "codex/api");
  await expect(modelBox(settings).locator("option")).toHaveText([
    "Fixture Coder",
    "Fixture Chat",
  ]);
  await chooseLane(target, settings, "codex/cli");
  await expect(modelBox(settings).locator("option")).toHaveText([
    "Fixture Tiered",
    "Fixture Ultra",
  ]);
  // The composer names the provider and the model it is on.
  await expect(settingsButton(target).first()).toHaveAccessibleName(
    new RegExp(`${escaped(nameOf("codex"))}, Fixture Ultra`),
  );
  await chooseLane(target, settings, "deepseek/cli");
  await expect(settings.getByRole("radiogroup")).toHaveCount(0);
});

test("the efforts offered follow the model chosen", async ({
  page: target,
}) => {
  scenarioOnly("the providers are the scenario host's catalog");
  await open(target);
  const settings = await openSettings(target);
  const efforts = effortBox(settings).locator("option");
  const words = (...keys: string[]) => keys.map((key) => label(key));
  // A model that takes every effort and names no default leaves the choice to
  // the provider, which is its own first option.
  await expect(modelBox(settings)).toHaveValue("fixture-deep");
  await expect(efforts).toHaveText(
    words(
      "desktop.agent.effort_default",
      "desktop.agent.effort_low",
      "desktop.agent.effort_medium",
      "desktop.agent.effort_high",
      "desktop.agent.effort_xhigh",
      "desktop.agent.effort_max",
    ),
  );
  await expect(effortBox(settings)).toHaveValue("");
  await effortBox(settings).selectOption({
    label: label("desktop.agent.effort_max"),
  });
  await expect(settingsButton(target).first()).toContainText(
    `Fixture Deep · ${label("desktop.agent.effort_max")}`,
  );
  // Another model takes fewer, and starts at the one its catalog names.
  await modelBox(settings).selectOption("fixture-quick");
  await expect(efforts).toHaveText(
    words("desktop.agent.effort_low", "desktop.agent.effort_medium"),
  );
  await expect(effortBox(settings)).toHaveValue("medium");
  // One that takes none has no effort to choose.
  await modelBox(settings).selectOption("fixture-plain");
  await expect(effortBox(settings)).toHaveCount(0);
  // Another provider's models take their own: Codex over its API takes none,
  // over its app it takes these.
  await chooseLane(target, settings, "codex/api");
  await expect(effortBox(settings)).toHaveCount(0);
  await chooseLane(target, settings, "codex/cli");
  await expect(modelBox(settings)).toHaveValue("fixture-ultra");
  await expect(efforts).toHaveText(
    words("desktop.agent.effort_high", "desktop.agent.effort_ultra"),
  );
  await expect(effortBox(settings)).toHaveValue("high");
  await modelBox(settings).selectOption("fixture-tiered");
  await expect(efforts).toHaveText(
    words(
      "desktop.agent.effort_low",
      "desktop.agent.effort_medium",
      "desktop.agent.effort_high",
    ),
  );
  // Nothing was chosen on the last model, so this one applies its own
  // default, not the last one's.
  await expect(effortBox(settings)).toHaveValue("medium");
  // An effort the person chose is kept for another model that takes it, and
  // dropped for one that does not.
  await effortBox(settings).selectOption({
    label: label("desktop.agent.effort_high"),
  });
  await modelBox(settings).selectOption("fixture-ultra");
  await expect(effortBox(settings)).toHaveValue("high");
  await effortBox(settings).selectOption({
    label: label("desktop.agent.effort_ultra"),
  });
  await modelBox(settings).selectOption("fixture-tiered");
  await expect(effortBox(settings)).toHaveValue("medium");
  // A model's other settings are not offered: a run does not take them.
  await expect(settings.getByRole("combobox")).toHaveCount(3);
  await expect(settings).not.toContainText("Fixture service tier");
});

test("a provider that lists no models is given the model's id, and sends only with one", async ({
  page: target,
}) => {
  scenarioOnly("the providers are the scenario host's catalog");
  await open(target);
  const settings = await openSettings(target);
  await chooseLane(target, settings, "deepseek/cli");
  const model = settings.getByRole("textbox", {
    name: label("desktop.agent.model"),
  });
  await expect(model).toHaveValue("");
  await expect(settings).toContainText(label("desktop.agent.model_written"));
  // The efforts its row declares, and the provider's own.
  await expect(effortBox(settings).locator("option")).toHaveText([
    label("desktop.agent.effort_default"),
    label("desktop.agent.effort_max"),
  ]);
  await target.keyboard.press("Escape");
  // No model, nothing to send.
  await field(target).fill("Hola");
  await expect(
    column(target).getByRole("button", {
      name: `${label("desktop.agent.send")}, ${label("desktop.agent.unavailable")}`,
    }),
  ).toBeVisible();
  const reopened = await openSettings(target);
  await reopened
    .getByRole("textbox", { name: label("desktop.agent.model") })
    .fill("a-model-id");
  await target.keyboard.press("Escape");
  await expect(settingsButton(target).first()).toContainText("a-model-id");
  await field(target).press("Enter");
  await expect(conversation(target)).toContainText("Hola");
  expect(
    (await calls(target)).filter((call) => call.startsWith("agentSend ")),
  ).toHaveLength(1);
});
