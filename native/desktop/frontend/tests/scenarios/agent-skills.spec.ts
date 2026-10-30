import { expect, test, type Page } from "@playwright/test";
import {
  FIXTURE_SKILLS,
  MANY_FIXTURE_SKILLS,
} from "../../src/dev/fixtures/agentSkills";
import {
  agentColumn as column,
  messageField as field,
  personTurns,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

// `/` in the composer: cadrumo-agent's skills and the composer's own
// commands, listed above the field while the focus stays in it. A skill
// chosen goes with the message as the skill the run loads; a command runs
// on the desktop and is never sent.

const open = (target: Page, query = "") =>
  target.goto(`/scenarios.html?scenario=signed-in&latency=0&bar=off${query}`);

const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

const list = (target: Page) => target.getByRole("listbox");
const options = (target: Page) => list(target).getByRole("option");
const highlighted = (target: Page) =>
  list(target).locator('[role="option"][aria-selected="true"]');

test.beforeEach(async ({ page: target }) => {
  scenarioOnly("The scenario host serves these skills and records the send.");
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("slash opens every skill and command above the field, focus staying in it", async ({
  page: target,
}) => {
  await open(target);
  await field(target).click();
  await field(target).pressSequentially("/");
  await expect(list(target)).toBeVisible();
  await expect(list(target)).toHaveAccessibleName(
    label("desktop.agent.slash_label"),
  );
  // Both commands, then every skill.
  await expect(options(target)).toHaveCount(FIXTURE_SKILLS.length + 2);
  await expect(field(target)).toBeFocused();
  // Above the composer: a drop-up.
  const listBox = await list(target).boundingBox();
  const fieldBox = await field(target).boundingBox();
  expect(listBox && fieldBox && listBox.y + listBox.height).toBeLessThanOrEqual(
    fieldBox?.y ?? 0,
  );
  // The field names the list and the option highlighted in it.
  const controls = await field(target).getAttribute("aria-controls");
  expect(controls).toBe(await list(target).getAttribute("id"));
  const active = await field(target).getAttribute("aria-activedescendant");
  expect(active).toBe(await highlighted(target).getAttribute("id"));
});

test("slash after text opens, and inside a word does not", async ({
  page: target,
}) => {
  await open(target);
  await field(target).pressSequentially("hola /");
  await expect(list(target)).toBeVisible();
  await field(target).fill("");
  await field(target).pressSequentially("a/b");
  await expect(list(target)).toHaveCount(0);
});

test("typing filters, arrows move, Escape closes until the token changes", async ({
  page: target,
}) => {
  await open(target);
  await field(target).pressSequentially("/reten");
  await expect(options(target)).toHaveCount(1);
  await expect(options(target)).toContainText("/cadrumo-retenciones");
  await field(target).fill("");
  await field(target).pressSequentially("/cadrumo-");
  const count = FIXTURE_SKILLS.length;
  await expect(options(target)).toHaveCount(count);
  await expect(highlighted(target)).toContainText(FIXTURE_SKILLS[0]!.name);
  await field(target).press("ArrowDown");
  await expect(highlighted(target)).toContainText(FIXTURE_SKILLS[1]!.name);
  await field(target).press("ArrowUp");
  await field(target).press("ArrowUp");
  // It wraps to the last.
  await expect(highlighted(target)).toContainText(
    FIXTURE_SKILLS[count - 1]!.name,
  );
  await field(target).press("Escape");
  await expect(list(target)).toHaveCount(0);
  await expect(field(target)).toHaveValue("/cadrumo-");
  await expect(field(target)).toBeFocused();
  await field(target).pressSequentially("f");
  await expect(options(target)).toHaveCount(1);
});

test("Enter or Tab writes the skill's token; nothing is sent", async ({
  page: target,
}) => {
  await open(target);
  await field(target).pressSequentially("mira /factu");
  await field(target).press("Enter");
  await expect(field(target)).toHaveValue("mira /cadrumo-facturas ");
  await expect(list(target)).toHaveCount(0);
  await field(target).pressSequentially("y /calen");
  await field(target).press("Tab");
  await expect(field(target)).toHaveValue(
    "mira /cadrumo-facturas y /cadrumo-calendario ",
  );
  await expect(field(target)).toBeFocused();
  expect(
    (await calls(target)).some((call) => call.startsWith("agentSend")),
  ).toBe(false);
});

test("a press on an option chooses it and keeps the focus", async ({
  page: target,
}) => {
  await open(target);
  await field(target).pressSequentially("/");
  await options(target).filter({ hasText: "/cadrumo-renta-anual" }).click();
  await expect(field(target)).toHaveValue("/cadrumo-renta-anual ");
  await expect(field(target)).toBeFocused();
});

test("the send carries the skills the message names", async ({
  page: target,
}) => {
  await open(target);
  await field(target).pressSequentially("/factu");
  await field(target).press("Enter");
  await field(target).pressSequentially("revisa esta factura");
  await field(target).press("Enter");
  await expect(
    personTurns(target).filter({ hasText: "revisa esta factura" }),
  ).toBeVisible();
  expect(await calls(target)).toContain("agentSendSkills cadrumo-facturas");
  // The person's turn says which skill it loaded, as history echoes it.
  await expect(
    personTurns(target)
      .filter({ hasText: "revisa esta factura" })
      .getByRole("list", { name: label("desktop.agent.sent_skills") }),
  ).toHaveText("/cadrumo-facturas");
});

test("hundreds of skills are all listed and the list scrolls", async ({
  page: target,
}) => {
  await open(target, "&skills=many");
  await field(target).pressSequentially("/cadrumo-");
  await expect(options(target)).toHaveCount(MANY_FIXTURE_SKILLS.length);
  const scroller = list(target);
  const overflow = await scroller.evaluate(
    (element) => element.scrollHeight > element.clientHeight,
  );
  expect(overflow).toBe(true);
  await field(target).press("ArrowUp");
  const last = MANY_FIXTURE_SKILLS.at(-1)!.name;
  await expect(highlighted(target)).toContainText(last);
  await expect(highlighted(target)).toBeInViewport();
  // It fits the window, above or below the composer.
  const box = await scroller.boundingBox();
  const height = target.viewportSize()?.height ?? 0;
  expect(box && box.y >= 0 && box.y + box.height <= height).toBe(true);
});

test("a skill read that fails says so", async ({ page: target }) => {
  await open(target, "&skills=failed");
  await field(target).pressSequentially("/");
  await expect(
    target.getByText(label("desktop.agent.slash_failed")),
  ).toBeVisible();
  await expect(column(target)).toBeVisible();
});

test("review shows a skill's description, when it applies, files and SKILL.md", async ({
  page: target,
}) => {
  await open(target);
  await field(target).pressSequentially("/skill-rev");
  await field(target).press("Enter");
  await expect(field(target)).toHaveValue("/skill-review ");
  // The list now asks for the skill it is for.
  await expect(options(target)).toHaveCount(FIXTURE_SKILLS.length);
  await field(target).pressSequentially("iva");
  await field(target).press("Enter");
  const dialog = target.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("cadrumo-iva-trimestral");
  await expect(dialog).toContainText(
    FIXTURE_SKILLS.find((skill) => skill.name === "cadrumo-iva-trimestral")!
      .description,
  );
  await expect(dialog).toContainText(
    label("desktop.agent.skill_applies_profile_all"),
  );
  await expect(dialog).toContainText("references/casillas.md");
  await expect(dialog.getByLabel("SKILL.md")).toContainText(
    "name: cadrumo-iva-trimestral",
  );
  expect(await calls(target)).toContain("agentSkill cadrumo-iva-trimestral");
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  // The command is never sent, leaves the field empty and gives it back
  // the focus.
  await expect(field(target)).toHaveValue("");
  await expect(field(target)).toBeFocused();
  expect(
    (await calls(target)).some((call) => call.startsWith("agentSend")),
  ).toBe(false);
});

test("verify typed in full and sent shows the agent's findings", async ({
  page: target,
}) => {
  await open(target);
  await field(target).fill("/skill-verify cadrumo-revision-fuentes");
  await field(target).press("Escape");
  await field(target).press("Enter");
  const dialog = target.getByRole("dialog");
  await expect(dialog.getByRole("status")).toHaveText(
    label("desktop.agent.skill_verify_failed"),
  );
  await expect(dialog).not.toContainText("applies_when_empty");
  await expect(dialog).toContainText("applies_when names no condition.");
  await expect(dialog).toContainText(
    label("desktop.agent.skill_finding_error"),
  );
  expect(await calls(target)).toContain(
    "agentSkillVerify cadrumo-revision-fuentes",
  );
});

test("verify of an unknown skill says the agent has none", async ({
  page: target,
}) => {
  await open(target);
  await field(target).fill("/skill-verify cadrumo-no-existe");
  await field(target).press("Escape");
  await field(target).press("Enter");
  await expect(target.getByRole("dialog").getByRole("alert")).toHaveText(
    label("desktop.agent.skill_not_found").replace(
      "{name}",
      "cadrumo-no-existe",
    ),
  );
});
