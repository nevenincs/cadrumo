import { expect, test } from "@playwright/test";
import {
  agentColumn,
  agentTurns,
  approvalPrompt,
  scenarioOnly,
  send,
  settled,
} from "../support/agent";
import { label } from "../support/strings";

// A reply that asks to read three attached files on a lane whose installation
// keeps documents on this computer: the service refuses each card, and the
// window says so once, for the run, rather than once per file.

const FILES = ["factura-enero.pdf", "factura-febrero.pdf", "factura-marzo.pdf"];

test.beforeEach(async ({ page: target }) => {
  scenarioOnly("the refusal is the scenario host's service answer");
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&asks=attachments",
  );
});

const notice = (target: import("@playwright/test").Page) =>
  agentColumn(target)
    .getByRole("status")
    .filter({
      hasText: label("desktop.agent.attachment_kept_here", {
        count: FILES.length,
        provider: "codex",
      }),
    });

test("files the installation keeps here are named once, and every request is declined", async ({
  page: target,
}) => {
  await send(target, "Lee mis tres facturas.");

  const one = notice(target);
  await expect(one).toHaveCount(1);
  for (const file of FILES) await expect(one).toContainText(file);
  await expect(one).toContainText(
    label("desktop.agent.attachment_refusal.cloud_upload_not_permitted"),
  );
  await expect(one).toContainText(
    label("desktop.agent.attachment_kept_here_way"),
  );

  // Not one dead-end card per file: neither a prompt nor a lone decline.
  await expect(approvalPrompt(target)).toHaveCount(0);
  await expect(
    agentColumn(target).getByRole("button", {
      name: label("desktop.agent.consent_decline"),
    }),
  ).toHaveCount(0);

  await settled(target);
  await expect(agentTurns(target).last()).toBeVisible();
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.filter((call) => call.startsWith("agentAttachmentCard ")),
  ).toHaveLength(3);
  const decided = calls.filter((call) =>
    call.startsWith("agentDecideApproval "),
  );
  expect(decided).toHaveLength(3);
  for (const call of decided) expect(call).toMatch(/ reject_once$/);
  expect(new Set(decided).size).toBe(3);
  // The notice outlives the declined requests.
  await expect(notice(target)).toHaveCount(1);
});

test("the way on opens the model picker", async ({ page: target }) => {
  await send(target, "Lee mis tres facturas.");
  await settled(target);
  await notice(target)
    .getByRole("button", {
      name: label("desktop.agent.attachment_kept_here_models"),
    })
    .click();
  await expect(
    target.getByRole("dialog", { name: label("desktop.agent.settings_title") }),
  ).toBeVisible();
});
