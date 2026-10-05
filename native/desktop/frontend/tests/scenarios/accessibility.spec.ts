import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { label } from "../support/strings";

// An automated accessibility audit of each major surface, in both schemes.
// It finds what a rule engine can find: names, roles, relationships and
// contrast. Keyboard operation is exercised in keyboard.spec.ts; a screen
// reader pass in the desktop window is a manual check.
const engine = readFileSync(
  fileURLToPath(
    new URL("../../node_modules/axe-core/axe.min.js", import.meta.url),
  ),
  "utf8",
);

type Finding = { id: string; impact: string | null; nodes: string[] };

async function audit(target: Page): Promise<Finding[]> {
  await target.evaluate(engine);
  return target.evaluate(async () => {
    const axe = (
      window as unknown as {
        axe: {
          run(
            context: unknown,
            options: unknown,
          ): Promise<{
            violations: {
              id: string;
              impact: string | null;
              nodes: { target: string[] }[];
            }[];
          }>;
        };
      }
    ).axe;
    const result = await axe.run(
      {
        // The documentation is another origin's document, audited where it
        // is built. xterm draws its own rows and input; its internals are
        // the library's, and the pane around it is audited here.
        exclude: [[".docs-frame"], [".xterm"]],
      },
      { resultTypes: ["violations"] },
    );
    return result.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.map((node) => node.target.join(" ")),
    }));
  });
}

const open = (target: Page, scenario: string) =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);

const SURFACES: {
  name: string;
  scenario: string;
  reach: (target: Page) => Promise<void>;
}[] = [
  {
    name: "the sign-in dialog",
    scenario: "signed-out",
    reach: async (target) => {
      await expect(target.locator(".sign-in")).toBeVisible();
    },
  },
  {
    name: "a refused sign-in",
    scenario: "wrong-password",
    reach: async (target) => {
      await target.locator("#profile-password").fill("anything");
      await target.keyboard.press("Enter");
      await expect(
        target.getByText(label("desktop.signin.refused.invalid")),
      ).toBeVisible();
    },
  },
  {
    name: "the signed-out pane",
    scenario: "signed-out",
    reach: async (target) => {
      await expect(target.locator(".sign-in")).toBeVisible();
      await target.keyboard.press("Escape");
      await expect(target.locator(".sign-in")).toHaveCount(0);
    },
  },
  {
    name: "the shell",
    scenario: "signed-in",
    reach: async (target) => {
      await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
    },
  },
  {
    name: "the palette",
    scenario: "signed-in",
    reach: async (target) => {
      await target
        .getByRole("button", { name: label("desktop.rail.search") })
        .click();
      await expect(target.locator(".palette")).toBeVisible();
      await target.locator(".palette [role=combobox]").fill("sign");
      await expect(
        target.locator(".palette").getByRole("option").first(),
      ).toBeVisible();
    },
  },
  {
    name: "settings",
    scenario: "signed-in",
    reach: async (target) => {
      await target
        .getByRole("button", { name: label("desktop.rail.settings") })
        .click();
      await expect(target.locator(".settings")).toBeVisible();
    },
  },
  {
    name: "the log view",
    scenario: "signed-in",
    reach: async (target) => {
      await target
        .getByRole("navigation", { name: label("desktop.rail.label") })
        .getByRole("button", { name: label("desktop.rail.logs") })
        .click();
      await expect(target.locator(".record").first()).toBeVisible();
    },
  },
  {
    name: "an unreadable log and a failed environment",
    scenario: "error",
    reach: async (target) => {
      await expect(target.locator(".sign-in")).toBeVisible();
      await target.keyboard.press("Escape");
      await target
        .getByRole("navigation", { name: label("desktop.rail.label") })
        .getByRole("button", { name: label("desktop.rail.logs") })
        .click();
      await expect(target.locator(".source-banner")).toBeVisible();
    },
  },
];

for (const scheme of ["light", "dark"] as const)
  for (const surface of SURFACES)
    test(`${surface.name} has no accessibility violations (${scheme})`, async ({
      page: target,
    }) => {
      await target.addInitScript((appearance) => {
        localStorage.setItem(
          "cadrumo-shell-layout",
          JSON.stringify({ prefs: { appearance } }),
        );
      }, scheme);
      await open(target, surface.scenario);
      await surface.reach(target);
      await expect(target.locator("html")).toHaveAttribute(
        "data-scheme",
        scheme,
      );
      expect(await audit(target)).toEqual([]);
    });
