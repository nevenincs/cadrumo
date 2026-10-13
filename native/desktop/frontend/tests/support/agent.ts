import { expect, test, type Locator, type Page } from "@playwright/test";
import type {
  AgentApproval,
  AgentQuestionnaire,
  AgentQuestionnaireAnswer,
  AgentSendRequest,
} from "../../src/shell/agentSession";
import { label } from "./strings";

// The agent column as a person finds it: by its roles and its words, never
// by how a host makes it. The same helpers drive the scenario host and the
// desktop app, so they wait on what is shown rather than on time, and they
// name no provider or model.

/** Whether the specs run against the desktop's own window and the real agent,
 * which the project says in its metadata. The scenario project says nothing. */
export const live = () => test.info().project.metadata.agentHost === "live";

/** Skips the test where it runs against the desktop: what it checks is the
 * scenario host's alone, such as its call log, its replies' words or a trigger
 * only it answers. */
export function scenarioOnly(reason: string) {
  test.skip(live(), reason);
}

const escaped = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** A chrome string as a pattern, with any value it names left open. */
export const worded = (key: string) =>
  new RegExp(`^${escaped(label(key)).replace(/\\\{\w+\\\}/g, ".+")}$`);

export const agentColumn = (target: Page) => target.locator(".pane-agent");

export const messageField = (target: Page) =>
  agentColumn(target).getByRole("textbox", {
    name: label("desktop.agent.message_label"),
  });

export const conversation = (target: Page) =>
  agentColumn(target).getByRole("log", {
    name: label("desktop.agent.transcript"),
  });

/** What the agent wrote, one article per turn. */
export const agentTurns = (target: Page) =>
  conversation(target).getByRole("article", {
    name: label("desktop.agent.agent_replied"),
  });

/** What the person wrote, one article per message. */
export const personTurns = (target: Page) =>
  conversation(target).getByRole("article", {
    name: label("desktop.agent.you_said"),
  });

/** The rows of the tools the agent called: the list items that hold no
 * message. */
export const toolRows = (target: Page) =>
  conversation(target)
    .getByRole("listitem")
    .filter({ hasNot: target.getByRole("article") });

/** The row of the tool called `title`. */
export const toolRow = (target: Page, title: string): Locator =>
  toolRows(target).filter({ hasText: title });

/** What the agent served of the conversation beside its words. */
export const replyState = (target: Page) =>
  agentColumn(target).locator(".agent-reply-state");
export const replyFacts = (target: Page) =>
  agentColumn(target).locator(".agent-reply-facts");

/** The history's door, opened. */
export async function openHistory(target: Page) {
  await agentColumn(target)
    .getByRole("button", { name: label("desktop.agent.history") })
    .click();
  return agentColumn(target).locator(".agent-body");
}

/** Opens the conversation titled `title` from the history. */
export async function openConversation(target: Page, title: string) {
  const body = await openHistory(target);
  await body.getByText(title, { exact: true }).click();
}

export const questionsPrompt = (target: Page) =>
  agentColumn(target).getByRole("region", {
    name: label("desktop.agent.questions_title"),
  });

export const approvalPrompt = (
  target: Page,
  source: "agent_tool" | "cadrumo_review" = "agent_tool",
) =>
  agentColumn(target).getByRole("region", {
    name: label(
      source === "agent_tool"
        ? "desktop.agent.approval_tool_title"
        : "desktop.agent.approval_review_title",
    ),
  });

/** Writes `text` in the message field and presses Enter. */
export async function ask(target: Page, text: string) {
  await messageField(target).fill(text);
  await messageField(target).press("Enter");
}

/** Sends `text` as a new message and waits until it is in the
 * conversation. */
export async function send(target: Page, text: string) {
  await ask(target, text);
  await expect(personTurns(target).filter({ hasText: text })).toBeVisible();
}

/** Waits until no reply is being written. */
export async function settled(target: Page) {
  await expect(
    agentColumn(target).getByRole("button", {
      name: label("desktop.agent.stop"),
    }),
  ).toHaveCount(0);
  await expect(conversation(target)).not.toContainText(
    label("desktop.agent.working"),
  );
}

// What follows is for the scenario host only: it reaches the agent session the
// host made, which a desktop app does not give a page. Nothing here drives
// the column; it reads what the agent waits on, records what the column
// hands over, and hands the agent what the column would not.

/** What the conversation's reply waits on, as the agent asked it. */
export async function waitingOn(target: Page): Promise<{
  questionnaires: AgentQuestionnaire[];
  approvals: AgentApproval[];
}> {
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  const sent = calls.filter((call) => call.startsWith("agentSend ")).at(-1);
  if (!sent) throw new Error("Nothing has been sent yet");
  const conversationId = sent.slice("agentSend ".length).split(" ")[0] ?? "";
  return target.evaluate(async (id) => {
    const session = window.__fixtureAgentSession;
    if (!session) throw new Error("The scenario host has no agent session");
    return session.pending(id);
  }, conversationId);
}

/** Every resolution of a questionnaire the column has handed the host, in
 * order. */
export const recordedAnswers = (
  target: Page,
): Promise<AgentQuestionnaireAnswer[]> =>
  target.evaluate(() => window.__fixtureAgentAnswers ?? []);

/** How the agent refuses something handed to it directly: the code the host
 * reports, and the sentence the agent explains it with. */
export type Refusal = { code: string; message: string };

/** The refusal of `resolution` of a questionnaire, by default the one the
 * agent waits on; null when the agent takes it. */
export async function refusalOfAnswer(
  target: Page,
  resolution: AgentQuestionnaireAnswer,
  questionnaire?: Pick<AgentQuestionnaire, "reply_id" | "request_id">,
): Promise<Refusal | null> {
  const asked = questionnaire ?? (await waitingOn(target)).questionnaires[0];
  if (!asked) throw new Error("No questions are waiting");
  return target.evaluate(
    async ({ request, reply }) => {
      try {
        await window.__fixtureAgentSession?.answerQuestions(request, reply);
        return null;
      } catch (error) {
        const { code, message } = error as { code?: string; message?: string };
        return { code: code ?? "", message: message ?? String(error) };
      }
    },
    {
      request: { reply_id: asked.reply_id, request_id: asked.request_id },
      reply: resolution,
    },
  );
}

/** The refusal of the decision `optionId` of an approval, by default the one
 * the agent waits on; null when the agent takes it. */
export async function refusalOfDecision(
  target: Page,
  optionId: string,
  approval?: Pick<AgentApproval, "reply_id" | "request_id">,
): Promise<Refusal | null> {
  const asked = approval ?? (await waitingOn(target)).approvals[0];
  if (!asked) throw new Error("No approval is waiting");
  return target.evaluate(
    async ({ request, option }) => {
      try {
        await window.__fixtureAgentSession?.decideApproval(request, option);
        return null;
      } catch (error) {
        const { code, message } = error as { code?: string; message?: string };
        return { code: code ?? "", message: message ?? String(error) };
      }
    },
    {
      request: { reply_id: asked.reply_id, request_id: asked.request_id },
      option: optionId,
    },
  );
}

/** The refusal of a send handed to the agent session directly, where the
 * column would not make it: its code, or null when the host takes it. */
export async function refusalOfSend(
  target: Page,
  text: string,
): Promise<string | null> {
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  const sent = calls.filter((call) => call.startsWith("agentSend ")).at(-1);
  if (!sent) throw new Error("Nothing has been sent yet");
  const conversation_id = sent.slice("agentSend ".length).split(" ")[0] ?? "";
  return target.evaluate(
    async ({ conversation_id, text }) => {
      const session = window.__fixtureAgentSession;
      if (!session) throw new Error("The scenario host has no agent session");
      const request: AgentSendRequest = {
        conversation_id,
        text,
        selection: {
          provider: "claude",
          transport: "api",
          model: "fixture-deep",
        },
      };
      try {
        await session.send(request);
        return null;
      } catch (error) {
        return (error as { code?: string }).code ?? String(error);
      }
    },
    { conversation_id, text },
  );
}
