import { expect, test, type Page } from "@playwright/test";
import {
  agentColumn as column,
  live,
  messageField as field,
  openConversation,
  personTurns,
  settled,
} from "../support/agent";
import { label } from "../support/strings";

// `@` and the attach button against the real cadrumo-agent, in the desktop's
// own window: the listing is the conversation's own storage as the agent
// serves it, and a message's references are what the agent's history echoes.
// The scenario host has its own specs for every path; these run only where
// the project attaches to the desktop. The host's file dialog is native, so a
// file is never picked here.

test.describe.configure({ mode: "serial" });

test.beforeEach(() => {
  test.skip(!live(), "These read the real agent's conversation storage.");
});

const open = (target: Page) =>
  target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");

const suggestions = (target: Page) =>
  target.locator('[data-slot="composer-suggestions"][data-source="documents"]');

const WORDS = "Mentions check: answer with the single word ok.";

test("live: a conversation that has stored nothing lists nothing for @, and says so", async ({
  page: target,
}) => {
  await open(target);
  await field(target).fill(WORDS);
  await field(target).press("Enter");
  await expect(personTurns(target).filter({ hasText: WORDS })).toBeVisible();
  await settled(target);
  // The conversation's storage is read now that its first run exists.
  await field(target).click();
  await field(target).pressSequentially("@");
  await expect(suggestions(target)).toContainText(
    label("desktop.agent.mention_empty"),
  );
  await expect(suggestions(target)).not.toContainText(
    label("desktop.agent.mention_failed"),
  );
  await expect(target.getByRole("option")).toHaveCount(0);
  await field(target).press("Escape");
  await field(target).fill("");
  // The host serves attaching files to it.
  await expect(
    column(target).getByRole("button", {
      name: label("desktop.agent.add_files"),
    }),
  ).not.toHaveAttribute("aria-disabled", "true");
});

test("live: a message that named nothing is read back naming nothing", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, WORDS);
  const sent = personTurns(target).filter({ hasText: WORDS });
  await expect(sent).toBeVisible();
  await expect(
    sent.getByRole("list", { name: label("desktop.agent.sent_files") }),
  ).toHaveCount(0);
});
