import { expect, test, type Page } from "@playwright/test";
import {
  agentTurns,
  ask,
  conversation,
  settled,
  toolRow,
  toolRows,
} from "../support/agent";
import { label } from "../support/strings";

// A reply as the agent writes it: Markdown read into rich text, links opened
// outside the window, and what the agent thought and what a tool call took
// and gave each behind a line the person opens and closes. The scenario
// host's reply to a message asking for "formato" thinks aloud, records its
// tool call's input and result, and answers in Markdown; the expected values
// are its words, written out here.

const open = (target: Page) =>
  target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");

const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);

test.beforeEach(async ({ page: target }) => {
  await open(target);
  await ask(target, "Respóndeme con formato");
  await settled(target);
});

test("a reply's Markdown is rich text, and its link opens outside the window", async ({
  page: target,
}) => {
  const reply = agentTurns(target);
  await expect(reply).toHaveCount(1);
  await expect(
    reply.getByRole("heading", { name: "Resumen del trimestre" }),
  ).toBeVisible();
  await expect(reply.locator("strong")).toHaveText("repercutido");
  await expect(reply.locator("em")).toHaveText("3.150,00 €");
  // Its paragraphs stay paragraphs, apart from each other.
  await expect(reply.locator("p").first()).toHaveText(
    "Lo miro en tus apuntes.",
  );
  await expect(reply.getByRole("listitem")).toHaveText([
    "42 apuntes leídos",
    "1 factura por revisar: 2026-031",
  ]);
  await expect(reply.locator("code")).toHaveText("2026-031");
  await expect(reply.getByRole("cell")).toHaveText(["27", "3.150,00"]);
  // A list the agent wrote is not a tool row.
  await expect(toolRows(target)).toHaveCount(1);

  const before = target.url();
  await reply.getByRole("link", { name: "la sede electrónica" }).click();
  await expect
    .poll(() => calls(target))
    .toContain("openExternal https://sede.agenciatributaria.gob.es");
  expect(target.url()).toBe(before);
});

test("what the agent thought opens and closes beneath its line", async ({
  page: target,
}) => {
  const toggle = conversation(target).getByRole("button", {
    name: label("desktop.agent.thinking"),
  });
  const thoughts = conversation(target).getByRole("region", {
    name: label("desktop.agent.thoughts"),
  });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(thoughts).toHaveCount(0);
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  // Its two chunks are one thought: the agent's message of them.
  await expect(thoughts).toHaveText(
    "Busco los apuntes del tercer trimestre. Sumo el IVA repercutido de las facturas emitidas.",
  );
  // The thinking is the agent's, beside its reply and not part of it.
  await expect(agentTurns(target)).not.toContainText("Busco los apuntes");
  await toggle.click();
  await expect(thoughts).toHaveCount(0);
});

test("what a tool call took and gave opens beneath its row", async ({
  page: target,
}) => {
  const row = toolRow(target, "ledger_list");
  const opener = row.getByRole("button");
  const details = row.getByRole("region", {
    name: label("desktop.agent.tool_details"),
  });
  await expect(opener).toHaveAttribute("aria-expanded", "false");
  await opener.click();
  await expect(details.locator("pre")).toHaveText([
    '{"trimestre":"3T","ejercicio":2026}',
    "Tool result:\n42 apuntes",
  ]);
  await opener.click();
  await expect(details).toHaveCount(0);
});
