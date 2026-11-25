import { expect, test, type Page } from "@playwright/test";
import {
  agentColumn as column,
  messageField as field,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

// Opening a Libro movement in a conversation with the agent: the agent
// column opens with the movement staged on the next message, stored as the
// ledger's movement read served it and named from its own date and id. The
// column says what the attachment holds and who would read it; nothing is
// sent until the person sends the message, and the attachment can be taken
// away. A refusal is said in its own words.

const open = async (target: Page) => {
  await target.goto("/scenarios.html?scenario=ledger&latency=0&bar=off");
  await target.locator("[data-rail=ledger]").click();
  await expect(grid(target).locator("[data-kind=data]").first()).toBeVisible();
};

const grid = (target: Page) => target.locator(".ledger-page").getByRole("grid");

const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);
const named = async (target: Page, prefix: string) =>
  (await calls(target)).filter((call) => call.startsWith(prefix));

/** The files staged for the next message, as the composer's well lists them. */
const staged = (target: Page) =>
  column(target)
    .getByRole("region", { name: label("desktop.agent.attachments") })
    .getByRole("listitem");

const notice = (target: Page) =>
  column(target).locator("[data-movement-notice]");

/** Opens the first movement's row menu and chooses to open it with the
 * agent; answers the movement's id. */
async function openFirstInAgent(target: Page): Promise<string> {
  const first = grid(target).locator("[data-kind=data]").first();
  const id = (await first.getAttribute("data-key"))!;
  await first.locator("[data-column=description]").click({ button: "right" });
  await target
    .getByRole("menu")
    .getByRole("menuitem", { name: label("desktop.ledger.open_in_agent") })
    .click();
  return id;
}

const fileOf = (id: string) =>
  new RegExp(`^movimiento-\\d{4}-\\d{2}-\\d{2}-${id.slice(0, 8)}\\.json$`);

test.beforeEach(() => {
  scenarioOnly(
    "the ledger and the conversation storage are the scenario host's",
  );
});

test("the row menu opens the agent column with the movement staged and says what it holds and who reads it", async ({
  page: target,
}) => {
  await open(target);
  const id = await openFirstInAgent(target);
  await expect(column(target)).toBeVisible();
  await expect(staged(target)).toHaveCount(1);
  const [stored] = await named(target, "agentAttachLedgerMovement ");
  expect(stored).toMatch(
    new RegExp(`^agentAttachLedgerMovement r-\\d+ ${id}$`),
  );
  const shown = notice(target);
  await expect(shown).toHaveAttribute("data-movement-notice", "staged");
  const name = (await staged(target).first().innerText())
    .split("\n")
    .find((line) => fileOf(id).test(line.trim()))
    ?.trim();
  expect(name).toMatch(fileOf(id));
  await expect(shown).toContainText(
    label("desktop.agent.movement_staged", { name: name! }),
  );
  // The lane the conversation would send on reads off this computer.
  await expect(shown.locator("[data-movement-shared]")).toBeVisible();
  // Staging it sent nothing.
  expect(await named(target, "agentSend ")).toEqual([]);
});

test("Send is what sends the movement, and a removed movement goes nowhere", async ({
  page: target,
}) => {
  await open(target);
  const id = await openFirstInAgent(target);
  await expect(staged(target)).toHaveCount(1);
  const [stored] = await named(target, "agentAttachLedgerMovement ");
  const conversation = stored!.split(" ")[1]!;
  const name = (await staged(target).first().innerText())
    .split("\n")
    .map((line) => line.trim())
    .find((line) => fileOf(id).test(line))!;
  // Taken away, it is no longer staged and its words go with it.
  await staged(target)
    .getByRole("button", { name: label("desktop.agent.remove_file", { name }) })
    .click();
  await expect(staged(target)).toHaveCount(0);
  await expect(notice(target)).toHaveCount(0);
  expect(await named(target, "agentSend ")).toEqual([]);
  // Opened again, it is staged again, and the message the person sends names
  // it by name.
  // The Libro stays beside the column.
  await openFirstInAgent(target);
  await expect(staged(target)).toHaveCount(1);
  await field(target).fill("¿Cómo clasifico este movimiento?");
  await field(target).press("Enter");
  await expect
    .poll(() => named(target, "agentSend "))
    .toEqual([
      expect.stringMatching(
        new RegExp(`^agentSend ${conversation} \\S+ attachments ${name}$`),
      ) as unknown as string,
    ]);
  await expect(staged(target)).toHaveCount(0);
});

test("the inspector's actions open the movement with the agent too", async ({
  page: target,
}) => {
  await open(target);
  const first = grid(target).locator("[data-kind=data]").first();
  const id = (await first.getAttribute("data-key"))!;
  await first.locator("[data-column=status]").click();
  const panel = target.locator("aside.ledger-panel");
  if (!(await panel.isVisible())) await target.keyboard.press("Alt+KeyI");
  await panel
    .getByRole("button", { name: label("desktop.ledger.inspector.actions") })
    .click();
  await target
    .getByRole("menuitem", { name: label("desktop.ledger.open_in_agent") })
    .click();
  await expect(staged(target)).toHaveCount(1);
  await expect(staged(target).first()).toContainText(id.slice(0, 8));
});

test("a refused movement says the words the ledger served, or the storage's own", async ({
  page: target,
}) => {
  await open(target);
  const words = "Este movimiento ya no está en el Libro.";
  await target.evaluate((served) => {
    window.__fixtureMovementRefusal = {
      code: "agent_movement_unreadable",
      refusal_words: served,
    };
  }, words);
  await openFirstInAgent(target);
  const refused = column(target).locator('[data-movement-notice="refused"]');
  await expect(refused).toHaveText(words);
  await expect(refused).toHaveAttribute("role", "alert");
  await expect(staged(target)).toHaveCount(0);
  // The storage's refusal is said in the attachment's words.
  await target.evaluate(() => {
    window.__fixtureMovementRefusal = {
      code: "agent_attachment_format_refused",
    };
  });
  // The Libro stays beside the column.
  await openFirstInAgent(target);
  await expect(refused).toHaveText(
    label("desktop.agent.upload_format_refused"),
  );
  await refused
    .getByRole("button", { name: label("desktop.agent.movement_dismiss") })
    .click();
  await expect(refused).toHaveCount(0);
  expect(await named(target, "agentSend ")).toEqual([]);
});
