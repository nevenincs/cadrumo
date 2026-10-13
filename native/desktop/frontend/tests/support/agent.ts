import { expect, type Page } from "@playwright/test";
import { label } from "./strings";

// The agent column as a person finds it: by its roles and its words, never
// by how a host makes it. The same helpers drive the scenario host and the
// desktop app, so they wait on what is shown rather than on time, and they
// name no provider or model.

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
