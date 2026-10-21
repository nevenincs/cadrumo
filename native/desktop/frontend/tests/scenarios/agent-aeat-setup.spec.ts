import { expect, test } from "@playwright/test";
import { aeatSetupProfile } from "../../src/components/agent/aeatSetupLink";
import {
  agentColumn,
  agentTurns,
  ask,
  personTurns,
  settled,
} from "../support/agent";
import { label } from "../support/strings";

const PROFILE = "5aa00000-0000-4000-8000-0000000000aa";

test("setup navigation rejects credentials, extra paths and ambiguous profiles", () => {
  expect(aeatSetupProfile(`cadrumo://profiles/${PROFILE}/aeat-auth`)).toBe(
    PROFILE,
  );
  for (const url of [
    `cadrumo://profiles/${PROFILE}/aeat-auth?password=x`,
    `cadrumo://profiles/${PROFILE}/aeat-auth#x`,
    `cadrumo://profiles/${PROFILE}/aeat-auth/extra`,
    `cadrumo://profiles/${PROFILE.toUpperCase()}/aeat-auth`,
    "cadrumo://profiles/00000000-0000-0000-0000-000000000000/aeat-auth",
    "https://profiles/example/aeat-auth",
  ])
    expect(aeatSetupProfile(url)).toBeNull();
});

test("the setup handoff preserves the workbench and resumes with a fresh check", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=aeat-setup&latency=0&bar=off");
  await ask(page, "Respóndeme con formato");
  await settled(page);
  const started = performance.now();
  await agentTurns(page)
    .getByRole("link", { name: "Set up AEAT access" })
    .click();
  const dialog = page.getByRole("dialog", {
    name: label("desktop.agent.aeat_setup_title"),
  });
  await expect(dialog).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => window.__scenarioHostCalls ?? []))
    .toContainEqual(
      expect.stringContaining(
        `openTerminal {"aeat_setup":{"profile_id":"${PROFILE}"}}`,
      ),
    );
  const input = dialog.locator(".xterm-helper-textarea");
  await expect(input).toHaveCount(1);
  await input.press("q");
  const done = dialog.getByRole("button", {
    name: label("desktop.agent.aeat_setup_return"),
  });
  await expect(done).toBeEnabled();
  const editorMs = performance.now() - started;
  await done.click();
  await expect(dialog).toHaveCount(0);
  await agentColumn(page)
    .getByRole("button", { name: label("desktop.agent.aeat_setup_check") })
    .click();
  await expect(personTurns(page).last()).toContainText(
    label("desktop.agent.aeat_setup_resume_message"),
  );
  const calls = await page.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.filter((call) => call.startsWith("openTerminal tui ")),
  ).toHaveLength(1);
  expect(calls.some((call) => call.startsWith("openExternal cadrumo:"))).toBe(
    false,
  );
  await test.info().attach("setup-presentation-timing", {
    body: JSON.stringify({
      scope: "browser fixture presentation, not native startup",
      editor_roundtrip_ms: editorMs,
    }),
    contentType: "application/json",
  });
});

test("a setup link for another profile opens neither editor nor browser", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await ask(page, "Respóndeme con formato");
  await settled(page);
  await agentTurns(page)
    .getByRole("link", { name: "Set up AEAT access" })
    .click();
  await expect(
    page.getByRole("dialog", { name: label("desktop.agent.aeat_setup_title") }),
  ).toHaveCount(0);
  const calls = await page.evaluate(() => window.__scenarioHostCalls ?? []);
  expect(
    calls.some((call) => call.includes('openTerminal {"aeat_setup"')),
  ).toBe(false);
  expect(calls.some((call) => call.startsWith("openExternal cadrumo:"))).toBe(
    false,
  );
});
