import { expect, test, type Page } from "@playwright/test";
import { agentColumn, scenarioOnly, send, settled } from "../support/agent";
import { label } from "../support/strings";

// The service refuses every read that would leave this computer for a bar that
// is not the file's: the installation's, the mode's or the profile's setting.
// The column words that once for all the files, names them and the setting that
// controls it, and still lets the person decline every read the agent waits on.

const FILES = ["escaneo.pdf", "foto.jpg", "factura.xml", "gastos.xlsx"];

const open = (target: Page) =>
  target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&asks=approval",
  );

const refusal = (target: Page) =>
  agentColumn(target).getByRole("region", {
    name: label("desktop.agent.attachment_refused_title"),
  });

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("four refused files are one refusal that names each file and the profile setting", async ({
  page: target,
}) => {
  scenarioOnly("the service's refusal is the scenario host's");
  await open(target);
  await send(target, "Lee los adjuntos sin enviar.");
  const group = refusal(target);
  await expect(group).toHaveCount(1);
  for (const name of FILES) await expect(group).toContainText(name);
  await expect(group).toContainText(
    label("desktop.agent.attachment_refusal.profile_not_eligible"),
  );
  // One refusal, not one card per file.
  await expect(
    agentColumn(target).getByRole("region", {
      name: label("desktop.agent.approval_tool_title"),
    }),
  ).toHaveCount(0);
  await expect(
    group.getByRole("button", {
      name: label("desktop.agent.attachment_open_profile"),
      exact: true,
    }),
  ).toBeVisible();
});

test("the way to the profile opens the profile page", async ({
  page: target,
}) => {
  scenarioOnly("the service's refusal is the scenario host's");
  await open(target);
  await send(target, "Lee los adjuntos sin enviar.");
  await refusal(target)
    .getByRole("button", {
      name: label("desktop.agent.attachment_open_profile"),
      exact: true,
    })
    .click();
  await expect(target.locator(".user-profile-page")).toBeVisible();
});

test("declining answers every read the agent waits on, and nothing is sent", async ({
  page: target,
}) => {
  scenarioOnly("the service's refusal is the scenario host's");
  await open(target);
  await send(target, "Lee los adjuntos sin enviar.");
  // The agent has asked for every file before the person answers.
  for (const name of FILES) await expect(refusal(target)).toContainText(name);
  await refusal(target)
    .getByRole("button", {
      name: label("desktop.agent.consent_decline"),
      exact: true,
    })
    .click();
  await expect(refusal(target)).toHaveCount(0);
  await settled(target);
  const calls = await target.evaluate(() => window.__scenarioHostCalls ?? []);
  const decided = calls.filter((call) =>
    call.startsWith("agentDecideApproval "),
  );
  expect(decided).toHaveLength(FILES.length);
  for (const call of decided) expect(call).toMatch(/ reject_once$/);
  expect(calls.some((call) => call.includes("attachmentRelease"))).toBe(false);
});

test("a bar the installation owns says so and offers no setting to open", async ({
  page: target,
}) => {
  scenarioOnly("the service's refusal is the scenario host's");
  await open(target);
  await send(
    target,
    "Lee los adjuntos sin enviar (cloud_upload_not_permitted).",
  );
  const group = refusal(target);
  await expect(group).toContainText(
    label("desktop.agent.attachment_refusal.cloud_upload_not_permitted"),
  );
  for (const name of FILES) await expect(group).toContainText(name);
  await expect(
    group.getByRole("button", {
      name: label("desktop.agent.attachment_open_profile"),
    }),
  ).toHaveCount(0);
  await expect(
    group.getByRole("button", {
      name: label("desktop.agent.consent_decline"),
      exact: true,
    }),
  ).toBeVisible();
});
