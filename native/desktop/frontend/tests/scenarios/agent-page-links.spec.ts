import { expect, test, type Page } from "@playwright/test";
import { cadrumoLink } from "../../src/components/agent/cadrumoLink";
import {
  agentColumn,
  agentTurns,
  ask,
  personTurns,
  settled,
} from "../support/agent";
import { label } from "../support/strings";

const PROFILE = "5aa00000-0000-4000-8000-0000000000aa";

const calls = (page: Page) =>
  page.evaluate(() => window.__scenarioHostCalls ?? []);

test("a page link names one exact profile and one closed page", () => {
  for (const [page, destination] of [
    ["home", "home"],
    ["ledger", "ledger"],
    ["withholding", "withholding"],
    ["declarations", "declarations"],
    ["aeat-sync", "aeat-sync"],
    ["operations", "operations"],
    ["installation", "installation"],
    ["setup", "setup"],
    ["reference", "reference"],
    ["profile", "profile"],
    ["aeat-auth", "profile/aeat-access"],
  ])
    expect(cadrumoLink(`cadrumo://profiles/${PROFILE}/${page}`)).toEqual({
      kind: "page",
      profile: PROFILE,
      destination,
    });
  for (const url of [
    `cadrumo://profiles/${PROFILE}/aeat-auth?password=x`,
    `cadrumo://profiles/${PROFILE}/aeat-auth#x`,
    `cadrumo://profiles/${PROFILE}/aeat-auth/extra`,
    `cadrumo://profiles/${PROFILE}/aeat_auth`,
    `cadrumo://profiles/${PROFILE}/Ledger`,
    `cadrumo://profiles/${PROFILE}/__proto__`,
    `cadrumo://profiles/${PROFILE.toUpperCase()}/aeat-auth`,
    "cadrumo://profiles/00000000-0000-0000-0000-000000000000/aeat-auth",
    "cadrumo://status",
    "CADRUMO://profiles/x/ledger",
  ])
    expect(cadrumoLink(url), url).toEqual({ kind: "malformed" });
  for (const url of [
    "https://profiles/example/aeat-auth",
    "mailto:someone@example.com",
    "cadrumos://profiles/x",
  ])
    expect(cadrumoLink(url), url).toEqual({ kind: "other" });
});

test("a setup link shows the TUI with the keyboard on its page and offers a fresh check", async ({
  page,
}) => {
  await page.goto("/scenarios.html?scenario=aeat-setup&latency=0&bar=off");
  await ask(page, "Respóndeme con formato");
  await settled(page);
  await agentTurns(page)
    .getByRole("link", { name: "Set up AEAT access" })
    .click();
  await expect
    .poll(() => calls(page))
    .toContain("presentView profile/aeat-access presented");
  const tui = page.locator('[data-terminal="tui"]');
  await expect(tui).toBeVisible();
  await expect(tui.locator(".xterm-helper-textarea")).toBeFocused();
  await agentColumn(page)
    .getByRole("button", { name: label("desktop.agent.aeat_setup_check") })
    .click();
  await expect(personTurns(page).last()).toContainText(
    label("desktop.agent.aeat_setup_resume_message"),
  );
  const made = await calls(page);
  expect(
    made.filter((call) => call.startsWith("openTerminal tui ")),
  ).toHaveLength(1);
  expect(made.some((call) => call.startsWith("openExternal cadrumo:"))).toBe(
    false,
  );
});
