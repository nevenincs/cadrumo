import { expect, test, type Page } from "@playwright/test";
import type { AgentDropSignal } from "../../src/shell/agentSession";
import {
  agentColumn,
  messageField,
  openConversation,
  scenarioOnly,
} from "../support/agent";
import { label } from "../support/strings";

const open = async (page: Page) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect
    .poll(() => page.evaluate(() => typeof window.__fixtureAgentDrop))
    .toBe("function");
};
const calls = (page: Page) =>
  page.evaluate(() => window.__scenarioHostCalls ?? []);
const staged = (page: Page) =>
  agentColumn(page)
    .getByRole("region", { name: label("desktop.agent.attachments") })
    .getByRole("listitem");
const overlay = (page: Page) =>
  agentColumn(page)
    .getByRole("status")
    .filter({ hasText: label("desktop.agent.drop_title") });

async function signal(
  page: Page,
  kind: "over" | "dropped",
  shift: boolean | null,
  outside = false,
) {
  const box = await agentColumn(page).boundingBox();
  if (!box) throw new Error("Agent column is not visible");
  const position = {
    x: outside ? box.x + box.width + 10 : box.x + box.width / 2,
    y: box.y + box.height / 2,
    count: 3,
    shift,
  };
  const event: AgentDropSignal =
    kind === "over"
      ? { kind, ...position }
      : { kind, ...position, drop_id: "native-drop" };
  await page.evaluate((event) => window.__fixtureAgentDrop?.(event), event);
}

test.beforeEach(() =>
  scenarioOnly("Native drop signals are supplied by the scenario host."),
);

test("dragging shows the design's overlay; Shift arms it and leaving clears it", async ({
  page,
}) => {
  await open(page);
  await signal(page, "over", false);
  await expect(overlay(page)).toBeVisible();
  await expect(agentColumn(page).locator("[data-armed=true]")).toHaveCount(0);
  await page.keyboard.down("Shift");
  await expect(agentColumn(page).locator("[data-armed=true]")).toBeVisible();
  await page.keyboard.up("Shift");
  await expect(overlay(page)).toBeVisible();
  await page.evaluate(() => window.__fixtureAgentDrop?.({ kind: "left" }));
  await expect(overlay(page)).toHaveCount(0);
  expect(
    (await calls(page)).filter((call) => call.startsWith("agentAttach")),
  ).toEqual([]);
});

test("unarmed drops and drops outside the panel never attach files", async ({
  page,
}) => {
  await open(page);
  await signal(page, "dropped", false);
  await signal(page, "over", true, true);
  await expect(agentColumn(page).locator("[data-armed=true]")).toHaveCount(0);
  await signal(page, "dropped", true, true);
  await expect(staged(page)).toHaveCount(0);
  expect(
    (await calls(page)).filter((call) => call.startsWith("agentAttach")),
  ).toEqual([]);
});

test("a Shift-drop reserves a new conversation and stages uploads and their refusals", async ({
  page,
}) => {
  await open(page);
  await signal(page, "over", true);
  await signal(page, "dropped", true);
  await expect(staged(page)).toHaveCount(3);
  await expect(staged(page).filter({ hasText: "copias.zip" })).toContainText(
    label("desktop.agent.upload_format_refused"),
  );
  await expect(
    staged(page).filter({ hasText: "escaneo-anual.pdf" }),
  ).toContainText(label("desktop.agent.upload_quota_exceeded"));
  expect(
    (await calls(page)).filter((call) => call === "agentStartConversation"),
  ).toHaveLength(1);
  expect(
    (await calls(page)).filter((call) => call.startsWith("agentAttachDrop")),
  ).toEqual([expect.stringMatching(/^agentAttachDrop r-\d+ native-drop$/)]);
  await messageField(page).fill("@recibo");
  await expect(page.getByRole("option")).toContainText("recibo-luz.pdf");
});

test("a fast dropped upload stays ready and is sent by reference in the selected conversation", async ({
  page,
}) => {
  await open(page);
  await openConversation(page, "IVA del tercer trimestre");
  await page.evaluate(() => {
    const session = window.__fixtureAgentSession;
    const attach = session?.attach?.bind(session);
    if (!session || !attach) throw new Error("Missing fixture attachment host");
    session.attach = async (id, label, onEvent, dropId) => {
      // A native upload can finish before the invoke result arrives.
      const picked = await attach(id, label, onEvent, dropId);
      onEvent({
        kind: "stored",
        id: picked[0]!.id,
        document: {
          name: "recibo-luz.pdf",
          size_bytes: 120_000,
          modified_at: "2026-10-26T00:00:00Z",
          sha256: "a".repeat(64),
          media_type: "application/pdf",
        },
      });
      return picked;
    };
  });
  await page.keyboard.down("Shift");
  await signal(page, "dropped", null);
  await page.keyboard.up("Shift");
  await expect(staged(page)).toHaveCount(3);
  for (const name of ["copias.zip", "escaneo-anual.pdf"])
    await staged(page)
      .getByRole("button", {
        name: label("desktop.agent.remove_file", { name }),
      })
      .click();
  await messageField(page).fill("Revisa el recibo");
  await messageField(page).press("Enter");
  await expect
    .poll(async () =>
      (await calls(page)).filter((call) => call.startsWith("agentSend ")),
    )
    .toEqual(["agentSend c-iva-t3 alpha/api attachments recibo-luz.pdf"]);
});

test("history stops observing drops and ignores a late native event", async ({
  page,
}) => {
  await open(page);
  await page.evaluate(() => {
    const listener = window.__fixtureAgentDrop;
    window.addEventListener("late-native-drop", () =>
      listener?.({
        kind: "dropped",
        x: 150,
        y: 300,
        count: 1,
        shift: true,
        drop_id: "retired-drop",
      }),
    );
  });
  await agentColumn(page)
    .getByRole("button", { name: label("desktop.agent.history") })
    .click();
  await expect
    .poll(() => page.evaluate(() => typeof window.__fixtureAgentDrop))
    .toBe("undefined");
  await page.evaluate(() =>
    window.dispatchEvent(new Event("late-native-drop")),
  );
  expect(
    (await calls(page)).filter((call) => call.startsWith("agentAttach")),
  ).toEqual([]);
});
