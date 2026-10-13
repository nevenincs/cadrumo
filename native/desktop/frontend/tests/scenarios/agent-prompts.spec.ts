import { expect, test, type Page } from "@playwright/test";
import {
  agentColumn,
  agentTurns,
  approvalPrompt,
  ask,
  conversation,
  personTurns,
  questionsPrompt,
  send,
  settled,
} from "../support/agent";
import { label } from "../support/strings";

// What a reply waits on: questions the agent asks, and decisions only the
// person makes. Each message asks for what it needs in words, as an agent
// would be asked; the scenario host stops every reply for it, by `asks`.
// What the agent then writes is the host's own, so these specs check what
// the column does, and only the scenario host's replies by their words.

const open = (target: Page, asks: "questions" | "approval" | "review") =>
  target.goto(
    `/scenarios.html?scenario=signed-in&latency=0&bar=off&asks=${asks}`,
  );

const button = (target: Page, key: string) =>
  agentColumn(target).getByRole("button", { name: label(key), exact: true });

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("questions are answered by choosing, and Answer waits for the required ones", async ({
  page: target,
}) => {
  await open(target, "questions");
  await send(target, "Antes de preparar el 303, pregúntame qué trimestre.");
  const prompt = questionsPrompt(target);
  await expect(prompt).toBeVisible();
  // The reply says it waits for the person, not that it is working.
  await expect(conversation(target)).toContainText(
    label("desktop.agent.waiting_on_you"),
  );
  await expect(conversation(target)).not.toContainText(
    label("desktop.agent.working"),
  );
  // The required choice has no answer yet, and Answer says so. It is named
  // alone, or with why it waits.
  const answer = prompt.getByRole("button", {
    name: new RegExp(`^${label("desktop.agent.questions_answer")}\\s*(,|$)`),
  });
  await expect(answer).toHaveAttribute("aria-disabled", "true");
  const choice = prompt.getByRole("radiogroup").first();
  await choice.getByRole("radio").last().click();
  await expect(answer).not.toHaveAttribute("aria-disabled", "true");
  const chosen = await choice.getByRole("radio").last().innerText();
  await answer.click();
  await expect(prompt).toHaveCount(0);
  await settled(target);
  // The scenario host goes on with what was chosen.
  await expect(agentTurns(target).last()).toContainText(chosen);
});

test("questions answered by a message go on with the same reply", async ({
  page: target,
}) => {
  await open(target, "questions");
  await send(target, "Antes de seguir, pregúntame si aplico la prorrata.");
  await expect(questionsPrompt(target)).toBeVisible();
  // Send stays while questions are asked: a message answers them.
  await ask(target, "No aplico la prorrata.");
  await expect(questionsPrompt(target)).toHaveCount(0);
  await expect(
    personTurns(target).filter({ hasText: "No aplico la prorrata." }),
  ).toBeVisible();
  await settled(target);
  await expect(agentTurns(target).last()).toContainText(
    "No aplico la prorrata.",
  );
  // An answer, not a new message: one send, one answer.
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(calls.filter((call) => call.startsWith("agentSend "))).toHaveLength(1);
  expect(
    calls.filter((call) => call.startsWith("agentAnswerQuestions ")),
  ).toEqual([expect.stringMatching(/ message$/)]);
});

test("declined questions are gone, and the reply goes on without them", async ({
  page: target,
}) => {
  await open(target, "questions");
  await send(target, "Pregúntame lo que necesites del 303.");
  await questionsPrompt(target)
    .getByRole("button", { name: label("desktop.agent.questions_decline") })
    .click();
  await expect(questionsPrompt(target)).toHaveCount(0);
  await settled(target);
});

test("questions still waiting are asked again when the conversation is opened again", async ({
  page: target,
}) => {
  await open(target, "questions");
  const text = "Pregúntame qué trimestre antes de nada.";
  await send(target, text);
  await expect(questionsPrompt(target)).toBeVisible();
  await button(target, "desktop.agent.new_conversation").click();
  await expect(questionsPrompt(target)).toHaveCount(0);
  await button(target, "desktop.agent.history").click();
  await agentColumn(target).getByText(text).click();
  await expect(questionsPrompt(target)).toBeVisible();
  await expect(conversation(target)).toContainText(text);
});

test("a tool waits for the person to allow it, once", async ({
  page: target,
}) => {
  await open(target, "approval");
  await send(target, "Lee mis apuntes del trimestre.");
  const prompt = approvalPrompt(target);
  await expect(prompt).toBeVisible();
  // Every way of deciding is offered, and none is chosen beforehand.
  for (const key of [
    "desktop.agent.approval_allow_once",
    "desktop.agent.approval_allow_always",
    "desktop.agent.approval_reject_once",
    "desktop.agent.approval_reject_always",
  ])
    await expect(
      prompt.getByRole("button", { name: label(key) }),
    ).toBeVisible();
  await prompt
    .getByRole("button", { name: label("desktop.agent.approval_allow_once") })
    .click();
  await expect(prompt).toHaveCount(0);
  await settled(target);
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.filter((call) => call.startsWith("agentDecideApproval ")),
  ).toEqual([expect.stringMatching(/ allow-once$/)]);
});

test("a tool refused does not run", async ({ page: target }) => {
  await open(target, "approval");
  await send(target, "Lee mis apuntes del trimestre.");
  await approvalPrompt(target)
    .getByRole("button", { name: label("desktop.agent.approval_reject_once") })
    .click();
  await expect(approvalPrompt(target)).toHaveCount(0);
  await settled(target);
  await expect(conversation(target)).not.toContainText(
    "Leer los apuntes del libro",
  );
});

test("a Cadrumo operation is reviewed before it commits", async ({
  page: target,
}) => {
  await open(target, "review");
  await send(target, "Registra la factura 2026-031.");
  const prompt = approvalPrompt(target, "cadrumo_review");
  await expect(prompt).toBeVisible();
  await expect(prompt).toContainText("Registrar la factura 2026-031");
  await prompt
    .getByRole("button", { name: label("desktop.agent.approval_allow_once") })
    .click();
  await expect(prompt).toHaveCount(0);
  await settled(target);
});
