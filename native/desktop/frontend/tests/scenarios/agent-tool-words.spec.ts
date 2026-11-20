import { expect, test, type Page } from "@playwright/test";
import { formatClock } from "../../src/shared/dateFormats";
import {
  agentColumn,
  approvalPrompt,
  conversation,
  openConversation,
  personTurns,
  agentTurns,
  scenarioOnly,
  send,
  settled,
  toolRows,
} from "../support/agent";
import { label } from "../support/strings";

// What a person reads of a tool the agent calls and of a turn carried from an
// earlier conversation: words for the tool by the identity the agent serves,
// how far it reaches, why it failed, and where a carried turn came from.

const open = (target: Page, query = "") =>
  target.goto(`/scenarios.html?scenario=signed-in&latency=0&bar=off${query}`);

const DAY = 24 * 60 * 60 * 1000;

test("a tool the agent serves an identity for is named in words, never by its raw name", async ({
  page: target,
}) => {
  scenarioOnly("the scenario host calls the tool its message asks for");
  await open(target);
  await send(target, "Dime el estado de la sesión.");
  await settled(target);
  const row = toolRows(target);
  await expect(row).toHaveCount(1);
  await expect(row).toContainText(
    label("desktop.agent.tool.cadrumo.status.label"),
  );
  await expect(row).not.toContainText("mcp__");
  await expect(row).not.toContainText("cadrumo__status");
  await expect(row).toContainText(label("desktop.agent.tool_done"));
});

test("a tool of the agent's own server is named by its own words", async ({
  page: target,
}) => {
  scenarioOnly("the scenario host calls the tool its message asks for");
  await open(target);
  await send(target, "Busca en internet el plazo del 303.");
  await settled(target);
  await expect(toolRows(target)).toContainText(
    label("desktop.agent.tool.cadrumo_agent_tools.web_search.label"),
  );
  await expect(toolRows(target)).not.toContainText("mcp__");
});

test("a tool the catalogue has no words for is named generically by its own name", async ({
  page: target,
}) => {
  scenarioOnly("the scenario host calls the tool its message asks for");
  await open(target);
  await send(target, "Usa una herramienta sin palabras.");
  await settled(target);
  await expect(toolRows(target)).toContainText(
    label("desktop.agent.tool_generic", { name: "ledger_unheard_of" }),
  );
  await expect(toolRows(target)).not.toContainText("mcp__");
});

test("a failed tool says why, in the words the tool gave", async ({
  page: target,
}) => {
  scenarioOnly("the scenario host fails a tool when it is asked to");
  await open(target);
  await send(target, "Dime el estado de la sesión. La herramienta falla.");
  await settled(target);
  const row = toolRows(target);
  await expect(row).toContainText(label("desktop.agent.tool_failed"));
  await expect(row).toContainText("The session is not signed in to a profile.");
  // A failure that gave no reason keeps the plain wording.
  await open(target);
  await send(target, "La herramienta falla, prueba otra cosa.");
  await settled(target);
  await expect(toolRows(target)).toContainText(
    label("desktop.agent.tool_failed"),
  );
  await expect(toolRows(target)).not.toContainText("not signed in");
});

test("a failed tool of the history says why too", async ({ page: target }) => {
  scenarioOnly("the scenario host serves a conversation with a failed tool");
  await open(target);
  await openConversation(target, "Turnos trasladados");
  const row = toolRows(target);
  await expect(row).toContainText(
    label("desktop.agent.tool.cadrumo.status.label"),
  );
  await expect(row).toContainText("The session is not signed in to a profile.");
  await expect(row).not.toContainText("mcp__");
});

for (const [asked, key, reach] of [
  ["status", "cadrumo.status", "local_read"],
  ["operation", "cadrumo.execute", "local_write"],
  ["web", "cadrumo_agent_tools.web_search", "online"],
] as const) {
  test(`a permission card for ${asked} says what the tool does and how far it reaches`, async ({
    page: target,
  }) => {
    scenarioOnly("the scenario host asks for the permission its message names");
    await open(target, "&asks=approval");
    await send(target, `permission ${asked}`);
    const prompt = approvalPrompt(target);
    await expect(prompt).toBeVisible();
    await expect(prompt.getByRole("heading")).toHaveText(
      label(`desktop.agent.tool.${key}.label`),
    );
    await expect(prompt).toContainText(
      label(`desktop.agent.tool.${key}.description`),
    );
    await expect(prompt).toContainText(
      label(`desktop.agent.tool_reach.${reach}`),
    );
    await expect(prompt).not.toContainText("Permission required:");
  });
}

test("a carried turn keeps the time it was first said and says where it came from", async ({
  page: target,
}) => {
  scenarioOnly("the scenario host serves a conversation with carried turns");
  await open(target);
  const before = Date.now();
  await openConversation(target, "Turnos trasladados");
  const turns = personTurns(target);
  await expect(turns).toHaveCount(3);
  const said = (days: number) =>
    // A minute either way: the fixture reads its clock when the page loads.
    new RegExp(
      [0, 60_000]
        .map((slack) =>
          formatClock("en", before - days * DAY - slack, {
            withDay: true,
          }).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
        )
        .join("|"),
    );
  // Carried from a conversation the window lists: named by its title.
  await expect(turns.nth(0)).toContainText(
    label("desktop.agent.carried_from", { title: "IVA del tercer trimestre" }),
  );
  await expect(turns.nth(0)).toContainText(said(60));
  // From one it does not list: only that it is an earlier one.
  await expect(turns.nth(1)).toContainText(
    label("desktop.agent.carried_from_unknown"),
  );
  await expect(turns.nth(1)).toContainText(said(59));
  // A turn said here carries no marker.
  await expect(turns.nth(2)).not.toContainText(
    label("desktop.agent.carried_from_unknown"),
  );
  await expect(turns.nth(2)).not.toContainText("IVA del tercer trimestre");
  await expect(turns.nth(2)).toContainText(said(40));
  // The agent's own carried message is marked the same way.
  await expect(agentTurns(target).first()).toContainText(
    label("desktop.agent.carried_from", { title: "IVA del tercer trimestre" }),
  );
  await expect(agentTurns(target).last()).not.toContainText(
    label("desktop.agent.carried_from_unknown"),
  );
  await expect(conversation(target)).toContainText("Seguimos aquí.");
  // The column of this conversation, not another.
  await expect(agentColumn(target)).toBeVisible();
});
