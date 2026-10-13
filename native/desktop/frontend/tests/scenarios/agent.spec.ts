import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The agent column at work: a message goes only once the person consents,
// its reply streams into the conversation as the host writes it, and a
// reply can be stopped. The scenario host's reply repeats the message; its
// stream sends one piece twice, or with `stream=gap` leaves one out.

const open = (target: Page, scenario = "signed-in", query = "") =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off${query}`);

const column = (target: Page) => target.locator(".pane-agent");
const field = (target: Page) =>
  target.getByRole("textbox", { name: label("desktop.agent.message_label") });
const conversation = (target: Page) =>
  column(target).getByRole("log", { name: label("desktop.agent.transcript") });
const consent = (target: Page) =>
  column(target).getByRole("region", {
    name: label("desktop.agent.consent_title", {
      provider: "Fixture provider",
    }),
  });
const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

/** The reply the scenario host writes to `text`, as it ends. */
const replyTo = (text: string) =>
  `Has escrito: «${text}». En estos datos de prueba no hay nada que revisar.`;

const ask = async (target: Page, text: string) => {
  await field(target).fill(text);
  await field(target).press("Enter");
};

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("a message goes only with consent, and its reply streams in once", async ({
  page: target,
}) => {
  await open(target);
  // The development lane says so for as long as it is used.
  await expect(column(target).getByRole("note")).toHaveText(
    label("desktop.agent.lane_notice"),
  );
  await ask(target, "¿Cuánto IVA pagué en julio?");
  await expect(consent(target)).toBeVisible();
  await expect(consent(target)).toContainText(
    label("desktop.agent.consent_messages"),
  );
  // Declining sends nothing and gives the message back.
  await consent(target)
    .getByRole("button", { name: label("desktop.agent.consent_decline") })
    .click();
  await expect(consent(target)).toHaveCount(0);
  await expect(field(target)).toHaveValue("¿Cuánto IVA pagué en julio?");
  expect(await calls(target)).not.toContainEqual(
    expect.stringMatching(/^agentSend /),
  );

  await field(target).press("Enter");
  await consent(target)
    .getByRole("button", {
      name: label("desktop.agent.consent_allow", {
        provider: "Fixture provider",
      }),
    })
    .click();
  const log = conversation(target);
  await expect(log).toContainText("¿Cuánto IVA pagué en julio?");
  await expect(log).toContainText("Leer los apuntes del libro del trimestre");
  const replies = log.getByRole("article", {
    name: label("desktop.agent.agent_replied"),
  });
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

  // The consent given covers the next message to the same model.
  await ask(target, "¿Y en agosto?");
  await expect(replies.last()).toHaveText(replyTo("¿Y en agosto?"));
  await expect(consent(target)).toHaveCount(0);
  expect(
    (await calls(target)).filter((call) =>
      call.startsWith("agentGrantConsent "),
    ),
  ).toHaveLength(1);
});

test("a reply stopped while it is written says it was stopped", async ({
  page: target,
}) => {
  await open(target);
  await ask(target, "Repasa el trimestre");
  await consent(target)
    .getByRole("button", {
      name: label("desktop.agent.consent_allow", {
        provider: "Fixture provider",
      }),
    })
    .click();
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
  await consent(target)
    .getByRole("button", {
      name: label("desktop.agent.consent_allow", {
        provider: "Fixture provider",
      }),
    })
    .click();
  const replies = conversation(target).getByRole("article", {
    name: label("desktop.agent.agent_replied"),
  });
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
