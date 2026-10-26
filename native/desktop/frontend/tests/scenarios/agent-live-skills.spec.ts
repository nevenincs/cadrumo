import { expect, test, type Locator, type Page } from "@playwright/test";
import {
  agentColumn as column,
  agentTurns,
  live,
  messageField as field,
  openConversation,
  openHistory,
  personTurns,
  settled,
} from "../support/agent";
import { label } from "../support/strings";

// `/` skills and conversation renames against the real cadrumo-agent, in the
// desktop's own window: the skills are the agent's bundled inventory, a skill
// named in a message reaches the run, and a title the person gives is the
// one the agent keeps. The scenario host has its own specs for all of it, so
// these run only where the project attaches to the desktop.

test.describe.configure({ mode: "serial" });

test.beforeEach(() => {
  test.skip(!live(), "These read the real agent's skills and conversations.");
});

const open = (target: Page) =>
  target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");

const list = (target: Page) => target.getByRole("listbox");
const options = (target: Page) => list(target).getByRole("option");
const skillOptions = (target: Page) =>
  options(target).filter({ hasText: /^\/cadrumo-/ });
const highlighted = (target: Page) =>
  list(target).locator('[role="option"][aria-selected="true"]');

/** The name an option offers, as its `/name` line writes it. */
async function optionName(option: Locator): Promise<string> {
  const line = (await option.locator("span").nth(1).textContent()) ?? "";
  return line.replace(/^\//, "").trim();
}

let firstSkill = "";

test("live: slash lists every skill the agent serves, and the list scrolls", async ({
  page: target,
}) => {
  await open(target);
  await field(target).click();
  await field(target).pressSequentially("/");
  await expect(skillOptions(target).first()).toBeVisible();
  const count = await skillOptions(target).count();
  test.info().annotations.push({ type: "skills", description: `${count}` });
  expect(count).toBeGreaterThan(0);
  // The two commands, then every skill: none is left out.
  await expect(options(target)).toHaveCount(count + 2);
  firstSkill = await optionName(skillOptions(target).first());
  // The last option can be reached, scrolled into view.
  await field(target).press("ArrowUp");
  await expect(highlighted(target)).toBeInViewport();
  const box = await list(target).boundingBox();
  const height = target.viewportSize()?.height ?? Number.POSITIVE_INFINITY;
  expect(box && box.y >= 0 && box.y + box.height <= height).toBe(true);
  await expect(field(target)).toBeFocused();
  await field(target).press("Escape");
  await field(target).fill("");
});

test("live: review shows the skill's SKILL.md", async ({ page: target }) => {
  await open(target);
  await field(target).fill("");
  await field(target).pressSequentially("/skill-review ");
  await expect(skillOptions(target).first()).toBeVisible();
  const name = await optionName(skillOptions(target).first());
  await field(target).press("Enter");
  const dialog = target.getByRole("dialog");
  await expect(dialog.getByLabel("SKILL.md")).toContainText(`name: ${name}`);
  await expect(dialog).toContainText(label("desktop.agent.skill_files"));
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
});

test("live: verify shows the agent's checks", async ({ page: target }) => {
  await open(target);
  await field(target).fill("");
  await field(target).pressSequentially("/skill-verify ");
  await expect(skillOptions(target).first()).toBeVisible();
  await field(target).press("Enter");
  const dialog = target.getByRole("dialog");
  await expect(dialog.getByRole("status")).toHaveText(
    new RegExp(
      [
        "desktop.agent.skill_verify_clean",
        "desktop.agent.skill_verify_warned",
        "desktop.agent.skill_verify_failed",
      ]
        .map((key) => label(key).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        .join("|"),
    ),
  );
  test.info().annotations.push({
    type: "verification",
    description: (await dialog.textContent()) ?? "",
  });
  await target.keyboard.press("Escape");
});

const TITLE_FROM_HEADER = "Skill check renamed in the header";
const TITLE_FROM_MENU = "Skill check renamed from the history";

const titleField = (target: Page) =>
  column(target).getByRole("textbox", {
    name: label("desktop.agent.rename_label"),
  });

test("live: a message naming a skill reaches the run, and its renames persist", async ({
  page: target,
}) => {
  expect(firstSkill, "the listing test ran first").not.toBe("");
  await open(target);
  const words = "Answer with the single word: ok.";
  await field(target).fill("");
  await field(target).pressSequentially(`/${firstSkill.slice(0, 12)}`);
  await expect(highlighted(target)).toContainText(`/${firstSkill}`);
  await field(target).press("Enter");
  await field(target).pressSequentially(words);
  await field(target).press("Enter");
  // The run took the skill: the agent answers rather than refusing it.
  await expect(
    personTurns(target).filter({ hasText: `/${firstSkill} ${words}` }),
  ).toBeVisible();
  await settled(target);
  await expect(agentTurns(target).last()).toBeVisible();
  await expect(column(target).getByRole("alert")).toHaveCount(0);

  // A double click on the title renames the conversation.
  const heading = column(target).getByRole("heading", {
    name: new RegExp(`^/${firstSkill}`),
  });
  await heading.dblclick();
  await titleField(target).fill(TITLE_FROM_HEADER);
  await target.keyboard.press("Enter");
  await expect(
    column(target).getByRole("heading", { name: TITLE_FROM_HEADER }),
  ).toBeVisible();
  // The history reads the conversations from the agent again: the title is
  // the one it kept.
  let body = await openHistory(target);
  const row = (title: string) =>
    body.getByRole("listitem").filter({ hasText: title });
  await expect(row(TITLE_FROM_HEADER)).toBeVisible();

  // The history's own context menu renames it too.
  await row(TITLE_FROM_HEADER).click({ button: "right" });
  await target
    .getByRole("menuitem", { name: label("desktop.agent.rename") })
    .click();
  await titleField(target).fill(TITLE_FROM_MENU);
  await target.keyboard.press("Enter");
  await expect(row(TITLE_FROM_MENU)).toBeVisible();
  // Reopened, the history reads it back from the agent.
  await openConversation(target, TITLE_FROM_MENU);
  await expect(
    column(target).getByRole("heading", { name: TITLE_FROM_MENU }),
  ).toBeVisible();
  await open(target);
  body = await openHistory(target);
  await expect(row(TITLE_FROM_MENU)).toBeVisible();
  await expect(row(TITLE_FROM_HEADER)).toHaveCount(0);
  // Read back from the agent's history, the message still names its skill.
  await body.getByText(TITLE_FROM_MENU, { exact: true }).click();
  await expect(
    personTurns(target)
      .first()
      .getByRole("list", { name: label("desktop.agent.sent_skills") }),
  ).toHaveText(`/${firstSkill}`);
});
