import { expect, test, type Page } from "@playwright/test";
import { seedLayout } from "../support/layout";
import { label } from "../support/strings";

// The window's columns: the agent beside the rail, then the TUI and the
// documentation. Each is shown and put away on its own, and with none of
// them shown the main area says so.

const open = (target: Page, scenario = "signed-in") =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);

const rail = (target: Page) =>
  target.getByRole("navigation", { name: label("desktop.rail.label") });

const railButton = (target: Page, key: string) =>
  rail(target).getByRole("button", { name: label(key), exact: true });

const left = async (target: Page, selector: string) =>
  (await target.locator(selector).boundingBox())?.x ?? Number.NaN;

// A column's own controls are in its header bar; the agent's bar is the
// conversation's, so they are found within the column.
const close = (target: Page, pane: string, key: string) =>
  target
    .locator(`.${pane}`)
    .getByRole("button", { name: label(key) })
    .click();

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("the window opens on the agent and the TUI, with the documentation put away", async ({
  page: target,
}) => {
  await open(target);
  await expect(target.locator(".pane-agent")).toBeVisible();
  await expect(target.locator(".pane-tui")).toBeVisible();
  await expect(target.locator(".pane-docs")).toBeHidden();
  expect(await left(target, ".pane-agent")).toBeLessThan(
    await left(target, ".pane-tui"),
  );
  await expect(railButton(target, "desktop.rail.agent")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(railButton(target, "desktop.rail.tui")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(railButton(target, "desktop.rail.docs")).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  // Asked for, the documentation takes its place after the TUI.
  await railButton(target, "desktop.rail.docs").click();
  await expect(target.locator(".docs-frame")).toBeVisible();
  expect(await left(target, ".pane-tui")).toBeLessThan(
    await left(target, ".pane-docs"),
  );
});

test("each column closes on its own, and with none left the main area offers them back", async ({
  page: target,
}) => {
  await open(target);
  const canvas = target.locator(".canvas");
  await railButton(target, "desktop.rail.docs").click();
  await expect(target.locator(".docs-frame")).toBeVisible();
  await expect(canvas).toHaveCount(0);
  await close(target, "pane-agent", "desktop.agent.hide");
  await expect(target.locator(".pane-agent")).toBeHidden();
  await close(target, "pane-tui", "desktop.tui.hide");
  await expect(target.locator(".pane-tui")).toBeHidden();
  await expect(canvas).toHaveCount(0);
  await close(target, "pane-docs", "desktop.docs.hide");
  await expect(target.locator(".pane-docs")).toBeHidden();
  await expect(canvas).toBeVisible();
  await expect(canvas).toContainText(label("desktop.canvas.title"));
  // The keyboard is not lost with the last column: the rail holds it.
  await expect(rail(target).locator(":focus")).toHaveCount(1);
  for (const key of [
    "desktop.agent.show",
    "desktop.tui.show",
    "desktop.docs.show",
  ])
    await expect(
      canvas.getByRole("button", { name: label(key) }),
    ).toBeVisible();
  await canvas
    .getByRole("button", { name: label("desktop.docs.show") })
    .click();
  await expect(target.locator(".docs-frame")).toBeVisible();
  await expect(canvas).toHaveCount(0);
  await railButton(target, "desktop.rail.docs").click();
  await expect(canvas).toBeVisible();
  // The agent alone beside the rail still leaves the main area empty.
  await canvas
    .getByRole("button", { name: label("desktop.agent.show") })
    .click();
  await expect(target.locator(".pane-agent")).toBeVisible();
  await expect(canvas).toBeVisible();
  await expect(
    canvas.getByRole("button", { name: label("desktop.agent.show") }),
  ).toHaveCount(0);
});

test("a maximized column fills the window and its close restores the rest", async ({
  page: target,
}) => {
  await open(target);
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.pane.maximize_agent") })
    .click();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await close(target, "pane-agent", "desktop.agent.hide");
  await expect(target.locator(".pane-agent")).toBeHidden();
  await expect(target.locator(".pane-tui")).toBeVisible();
});

test("a layout stored before the documentation could be put away opens in today's order", async ({
  page: target,
}) => {
  await seedLayout(target, {
    prefs: { order: "docs" },
    layout: { tuiShown: true },
  });
  await open(target);
  await expect(target.locator(".pane-docs")).toBeHidden();
  await railButton(target, "desktop.rail.docs").click();
  await expect(target.locator(".docs-frame")).toBeVisible();
  expect(await left(target, ".pane-tui")).toBeLessThan(
    await left(target, ".pane-docs"),
  );
});

test("F6 goes through the columns in the order they are laid out", async ({
  page: target,
}) => {
  await open(target);
  await railButton(target, "desktop.rail.docs").click();
  await expect(target.locator(".docs-frame")).toBeVisible();
  // The panel takes the keyboard as it opens; the walk starts after that.
  await target.keyboard.press("Control+Backquote");
  await expect(
    target.locator('[data-terminal="console"] textarea'),
  ).toBeFocused();
  await rail(target).getByRole("button").first().focus();
  await target.keyboard.press("F6");
  await expect(
    target.getByRole("region", { name: label("desktop.pane.agent") }),
  ).toBeFocused();
  await target.keyboard.press("F6");
  await expect(target.locator('[data-terminal="tui"] textarea')).toBeFocused();
  await target.keyboard.press("F6");
  await expect(target.locator(".docs-frame")).toBeFocused();
  await target.keyboard.press("F6");
  await expect(
    target.locator('[data-terminal="console"] textarea'),
  ).toBeFocused();
  await target.keyboard.press("F6");
  await expect(rail(target).locator(":focus")).toHaveCount(1);
});

test("the agent's splitter moves by the arrow keys within its bounds", async ({
  page: target,
}) => {
  await open(target);
  const handle = target.getByRole("separator", {
    name: label("desktop.agent.resize"),
  });
  const width = async () =>
    (await target.locator(".agent-column").boundingBox())?.width ?? 0;
  await handle.focus();
  const before = await width();
  await target.keyboard.press("ArrowRight");
  await expect.poll(width).toBeGreaterThan(before);
  await target.keyboard.press("Home");
  const smallest = await width();
  await target.keyboard.press("ArrowLeft");
  // Its floor holds: a step past it changes nothing.
  await expect.poll(width).toBe(smallest);
  await target.keyboard.press("End");
  await expect.poll(width).toBeGreaterThan(smallest);
  await expect(target.locator(".pane-tui")).toBeVisible();
});

test("a window too narrow for the agent beside the rest shows it on its own", async ({
  page: target,
}) => {
  await target.setViewportSize({ width: 520, height: 600 });
  await open(target);
  await expect(target.locator(".pane-agent")).toBeHidden();
  await expect(target.locator(".pane-tui")).toBeVisible();
  await railButton(target, "desktop.rail.agent").click();
  await expect(target.locator(".pane-agent")).toBeVisible();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await expect(
    target.getByRole("region", { name: label("desktop.pane.agent") }),
  ).toBeFocused();
  await railButton(target, "desktop.rail.agent").click();
  await expect(target.locator(".pane-agent")).toBeHidden();
  await expect(target.locator(".pane-tui")).toBeVisible();
});

test("double-clicking the agent's bar maximizes and restores it, its buttons do not", async ({
  page: target,
}) => {
  await open(target);
  const title = target
    .locator(".pane-agent")
    .getByRole("heading", { name: label("desktop.agent.new_conversation") });
  await title.dblclick();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await title.dblclick();
  await expect(target.locator(".pane-tui")).toBeVisible();
  // A double click on one of its buttons is that button's, not the bar's,
  // even one that is not available yet and takes no click of its own.
  await target
    .locator(".pane-agent")
    .getByRole("button", { name: label("desktop.agent.new_conversation") })
    .dispatchEvent("dblclick");
  await expect(target.locator(".pane-tui")).toBeVisible();
});

test("the agent's message field holds a line even when the column opens after the window", async ({
  page: target,
}) => {
  await seedLayout(target, { layout: { agentShown: false } });
  await open(target);
  await railButton(target, "desktop.rail.agent").click();
  const field = target.getByRole("textbox", {
    name: label("desktop.agent.message_label"),
  });
  await expect(field).toBeVisible();
  // A line of text and the field's padding, at least: the placeholder shows.
  const { height, line } = await field.evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      height: element.clientHeight,
      line:
        parseFloat(style.lineHeight) +
        parseFloat(style.paddingTop) +
        parseFloat(style.paddingBottom),
    };
  });
  expect(height).toBeGreaterThanOrEqual(Math.floor(line));
});

const agentButton = (target: Page, key: string) =>
  target
    .locator(".pane-agent")
    .getByRole("button", { name: label(key), exact: false })
    .first();

test("the agent's history lists the host's conversations and opens one with its documents", async ({
  page: target,
}) => {
  await open(target);
  await agentButton(target, "desktop.agent.history").click();
  const body = target.locator(".agent-body");
  await expect(body.getByText("IVA del tercer trimestre")).toBeVisible();
  // Archived ones wait behind their own toggle.
  await expect(body.getByText("Alta como autónomo")).toHaveCount(0);
  await body.getByText("IVA del tercer trimestre").click();
  await expect(
    target.locator(".pane-agent").getByRole("heading", {
      name: "IVA del tercer trimestre",
    }),
  ).toBeVisible();
  // Its turns, as the host's history has them: the person's message with
  // the files sent with it, the operations the agent called, its reply.
  const log = body.getByRole("log");
  await expect(log).toContainText("¿Me preparas el 303?");
  await expect(log).toContainText("ticket-gasolinera.jpg");
  await expect(log).toContainText("Registrar la factura 2026-031");
  await expect(log).toContainText("He leído 42 apuntes del trimestre.");
  await agentButton(target, "desktop.agent.documents").click();
  await expect(body.getByText("factura-2026-031.pdf")).toBeVisible();
  await expect(body.getByText("facturas-proveedores.zip")).toBeVisible();
  // A new conversation leaves it, with nothing open.
  await agentButton(target, "desktop.agent.new_conversation").click();
  await expect(
    target.locator(".pane-agent").getByRole("heading", {
      name: label("desktop.agent.new_conversation"),
    }),
  ).toBeVisible();
  await expect(
    target.getByRole("textbox", {
      name: label("desktop.agent.message_label"),
    }),
  ).toBeVisible();
});

test("without agent views the column's doors say they are not available yet", async ({
  page: target,
}) => {
  await open(target, "no-views");
  for (const key of [
    "desktop.agent.history",
    "desktop.agent.documents",
    "desktop.agent.new_conversation",
  ])
    await expect(agentButton(target, key)).toHaveAttribute(
      "aria-disabled",
      "true",
    );
});

test("a refused read of the history says so, never that there are none", async ({
  page: target,
}) => {
  await open(target, "views-refused");
  await agentButton(target, "desktop.agent.history").click();
  const body = target.locator(".agent-body");
  await expect(body.getByRole("alert")).toBeVisible();
  await expect(body).not.toContainText(label("desktop.agent.history_empty"));
});
