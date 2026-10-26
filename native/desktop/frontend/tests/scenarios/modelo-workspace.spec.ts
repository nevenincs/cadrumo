import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// One declaration's workspace over the scenario's modelo family, which
// answers the forms the application read for a synthetic taxpayer: the
// header, the next action, the Check lines and the source groups are the
// read model's. The window routes the next action to a view, opens a box
// from a finding or a source, says why a declaration cannot be changed, and
// says an operation whose settlement was not seen is unknown.
// The rules-incomplete banner is shown by the stories: the list does not
// open the scenario's 390, which its read model says could not be read.

const workspace = (target: Page) => target.locator(".declarations-workspace");
const tab = (target: Page, key: string) =>
  workspace(target).getByRole("tab", { name: new RegExp(`^${label(key)}`) });

async function openDeclaration(target: Page, modelo: string, shape = "") {
  await target.goto(
    `/scenarios.html?scenario=ledger&latency=0&bar=off${shape ? `&modelo=${shape}` : ""}`,
  );
  await target.locator("[data-rail=declarations]").click();
  const rows = target
    .locator(".declarations-page")
    .getByRole("grid")
    .locator("[data-kind=data]");
  await rows
    .filter({ hasText: `Modelo ${modelo}` })
    .first()
    .dblclick();
  await expect(
    workspace(target).getByRole("heading", { level: 1 }),
  ).toBeVisible();
}

test("the header states the read model's result, deadline and next action", async ({
  page: target,
}) => {
  await openDeclaration(target, "130");
  const header = workspace(target).locator("header").first();
  await expect(header).toContainText("Result: could not be calculated");
  await expect(header).toContainText("Deadline passed on 20/04/2026");
  await expect(
    header.getByRole("button", {
      name: label("workspace.modelo.next_button.resolve"),
    }),
  ).toBeVisible();
  // What blocks filing is counted on the Check tab, in words for the reader.
  await expect(
    tab(target, "workspace.modelo.step.review").getByRole("img", {
      name: /blocking: \d+/,
    }),
  ).toBeVisible();
});

test("resolving opens the check's lines, and a line opens its box", async ({
  page: target,
}) => {
  await openDeclaration(target, "130", "checked");
  await workspace(target)
    .getByRole("button", {
      name: label("workspace.modelo.next_button.resolve"),
    })
    .click();
  await expect(tab(target, "workspace.modelo.step.review")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  const blocks = workspace(target).getByRole("region", {
    name: label("workspace.modelo.level.blocks"),
  });
  await expect(blocks).toContainText("modelo 100");
  await blocks
    .getByRole("button")
    .filter({ has: target.getByText("19", { exact: true }) })
    .click();
  await expect(tab(target, "desktop.modelo.view.form")).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("a source group's box opens it in the form", async ({ page: target }) => {
  await openDeclaration(target, "130");
  await tab(target, "workspace.modelo.key.sources").click();
  await expect(
    workspace(target).getByRole("heading", {
      name: label("workspace.modelo.sources.title"),
    }),
  ).toBeVisible();
  await workspace(target)
    .getByRole("button", {
      name: label("workspace.modelo.sources.go_to_box", { box: "03" }),
    })
    .click();
  await expect(tab(target, "desktop.modelo.view.form")).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("a declaration recorded as filed is read only and offers a correction", async ({
  page: target,
}) => {
  await openDeclaration(target, "130", "filed");
  await expect(workspace(target).getByRole("status").first()).toContainText(
    label("workspace.modelo.filed.read_only"),
  );
  await workspace(target)
    .getByRole("button", { name: label("workspace.modelo.correction.title") })
    .first()
    .click();
  // The correction opens over the History view.
  const correction = target.getByRole("dialog");
  await expect(correction).toContainText(
    label("workspace.modelo.correction.lead"),
  );
  await correction
    .getByRole("button", { name: label("workspace.modelo.editor.cancel") })
    .click();
  await expect(tab(target, "workspace.modelo.history.title")).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("a calculation whose settlement was not seen is unknown and holds", async ({
  page: target,
}) => {
  await openDeclaration(target, "303", "unknown");
  const calculate = workspace(target).getByRole("button", {
    name: label("workspace.modelo.next_button.calculate"),
  });
  await calculate.click();
  // Values nobody is recorded as having typed here are at risk: it asks.
  const proceed = target.getByRole("button", {
    name: label("workspace.modelo.calculate.at_risk_proceed"),
  });
  if (await proceed.isVisible()) await proceed.click();
  const alert = workspace(target)
    .getByRole("status")
    .filter({
      hasText: label("workspace.modelo.outcome.unknown"),
    });
  await expect(alert).toBeVisible();
  await expect(
    alert.getByRole("button", { name: label("workspace.modelo.read_again") }),
  ).toBeVisible();
});
