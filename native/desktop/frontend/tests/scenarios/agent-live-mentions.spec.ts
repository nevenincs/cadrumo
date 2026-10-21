import { expect, test, type Page } from "@playwright/test";
import {
  agentColumn as column,
  agentTurns,
  approvalPrompt,
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
// the project attaches to the desktop. The test host's attach button takes
// the lane's synthetic files in place of its native dialog; everything after
// the pick is the real path: the policy, the digest, the streamed upload and
// the agent's own refusals.

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

const NOTES = "lane-notes.txt";
const LEDGER = "lane-ledger.csv";
const ASK = `Read ${NOTES} with your attachment tool and answer with only the word it names.`;

/** The files staged for the next message, as the composer's well lists them. */
const staged = (target: Page) =>
  column(target)
    .getByRole("region", { name: label("desktop.agent.attachments") })
    .getByRole("listitem");
const tile = (target: Page, name: string) =>
  staged(target).filter({ hasText: name });

/** Allows, once each, every read the agent asks for, until its reply says
 * `expected`. It may list the conversation's files before it reads one. */
async function allowEachRead(target: Page, expected: RegExp) {
  const prompt = approvalPrompt(target);
  const allowOnce = prompt.getByRole("button", {
    name: label("desktop.agent.approval_allow_once"),
  });
  await expect(allowOnce).toBeVisible();
  const replied = async () =>
    expected.test((await agentTurns(target).last().textContent()) ?? "");
  while (!(await replied())) {
    if (await prompt.isVisible()) await allowOnce.click();
    await expect
      .poll(async () => (await prompt.isVisible()) || (await replied()))
      .toBe(true);
  }
  await settled(target);
  await expect(agentTurns(target).last()).toContainText(expected);
}

test("live: attached files are stored, or refused for the reason the storage gives", async ({
  page: target,
}) => {
  await open(target);
  await column(target)
    .getByRole("button", { name: label("desktop.agent.add_files") })
    .click();
  await expect(staged(target)).toHaveCount(5);
  // Refused before anything was sent: a zip, and a name starting with a dot.
  await expect(tile(target, "lane-archive.zip")).toContainText(
    label("desktop.agent.upload_format_refused"),
  );
  await expect(tile(target, ".lane-hidden.txt")).toContainText(
    label("desktop.agent.upload_name_refused"),
  );
  // Refused by the storage: text under a PDF's name.
  await expect(tile(target, "lane-mismatch.pdf")).toContainText(
    label("desktop.agent.upload_format_refused"),
  );
  // Stored, and named for the next message.
  for (const name of [NOTES, LEDGER])
    await expect(tile(target, name)).not.toContainText(
      label("desktop.agent.upload_failed"),
    );
  for (const name of [
    "lane-archive.zip",
    ".lane-hidden.txt",
    "lane-mismatch.pdf",
  ])
    await tile(target, name)
      .getByRole("button", {
        name: label("desktop.agent.remove_file", { name }),
      })
      .click();
  await expect(staged(target)).toHaveCount(2);
  // @ lists what the conversation stored, and only that.
  await field(target).click();
  await field(target).pressSequentially("@lane");
  await expect(target.getByRole("option")).toHaveCount(2);
  await expect(target.getByRole("option").first()).toContainText(LEDGER);
  await expect(target.getByRole("option").last()).toContainText(NOTES);
  await field(target).press("ArrowDown");
  await field(target).press("Enter");
  await expect(field(target)).toHaveValue(`@${NOTES} `);
  await expect(staged(target)).toHaveCount(2);
  // The conversation's first message names them by reference; the agent asks
  // before it reads one, and its reply comes from the file.
  await field(target).pressSequentially(ASK);
  await field(target).press("Enter");
  await expect(personTurns(target).filter({ hasText: ASK })).toBeVisible();
  await allowEachRead(target, /GIRASOL/i);
  await expect(staged(target)).toHaveCount(0);
});

test("live: the documents a message named are shown with it when it is read again", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, `@${NOTES} ${ASK}`);
  const sent = personTurns(target).filter({ hasText: ASK });
  const files = sent.getByRole("list", {
    name: label("desktop.agent.sent_files"),
  });
  await expect(files).toContainText(NOTES);
  await expect(files).toContainText(LEDGER);
});

test("live: a document named on a follow-up message is read too", async ({
  page: target,
}) => {
  await open(target);
  await openConversation(target, `@${NOTES} ${ASK}`);
  const follow = `Read ${LEDGER} with your attachment tool and answer with only its amount.`;
  await field(target).click();
  await field(target).pressSequentially("@lane-ledger");
  await expect(target.getByRole("option")).toHaveCount(1);
  await field(target).press("Enter");
  await expect(staged(target)).toHaveCount(1);
  await field(target).pressSequentially(follow);
  await field(target).press("Enter");
  await expect(personTurns(target).filter({ hasText: follow })).toBeVisible();
  await allowEachRead(target, /12[.,]50/);
  await expect(
    personTurns(target)
      .filter({ hasText: follow })
      .getByRole("list", { name: label("desktop.agent.sent_files") }),
  ).toContainText(LEDGER);
});
