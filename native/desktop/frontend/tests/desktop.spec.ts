import { expect, test, type Page } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { identity } from "../../scripts/configuration.mjs";

const local = (path: string) => fileURLToPath(new URL(path, import.meta.url));

// Expected labels come from the generated catalogue once it exists; before
// that the shell shows each key, and so do these expectations.
const catalogue = local("../src/generated/chrome-strings.json");
const english: Record<string, string> = existsSync(catalogue)
  ? ((
      JSON.parse(readFileSync(catalogue, "utf8")) as Record<
        string,
        Record<string, string>
      >
    ).en ?? {})
  : {};
const label = (key: string) => english[key] ?? key;

// A stand-in documentation origin. It is a different origin from the shell,
// and its pages load the real desktop bridge script.
const DOCS = "http://docs.cadrumo.test";
const bridge = readFileSync(
  local("../../../../docs/_static/cadrumo-desktop-bridge.js"),
  "utf8",
);
const page = (title: string, body: string) =>
  `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${title}</title>` +
  `<script src="/bridge.js"></script></head><body data-theme="light">${body}</body></html>`;
const PAGES: Record<string, string> = {
  "/index.html": page(
    "Stand-in documentation",
    '<h1>Stand-in documentation</h1><p id="text">Casilla 01 total</p>' +
      '<a id="internal" href="/second.html">Second page</a> <a id="external" href="https://example.org/">External</a>',
  ),
  "/second.html": page("Second page", "<h1>Second page</h1>"),
};

async function serveDocs(target: Page) {
  await target.route(`${DOCS}/**`, (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/bridge.js")
      return route.fulfill({ contentType: "text/javascript", body: bridge });
    const html = PAGES[path];
    return html
      ? route.fulfill({ contentType: "text/html", body: html })
      : route.fulfill({ status: 404, body: "" });
  });
}

async function openWithDocs(target: Page) {
  await serveDocs(target);
  await target.goto(`/?docs=${encodeURIComponent(`${DOCS}/index.html`)}`);
  await expect(target.frameLocator(".docs-frame").locator("h1")).toHaveText(
    "Stand-in documentation",
  );
}

test.beforeEach(async ({ page: target }) => {
  // Start each test from the default layout, once: a reload inside a test must
  // still see what that test stored.
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("without a host the shell lays out every area and invents nothing", async ({
  page: target,
}) => {
  await target.goto("/");
  await expect(target).toHaveTitle(identity().name);
  const rail = target.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  await expect(rail.getByRole("button")).toHaveCount(7);
  await expect(target.locator(".pane-docs")).toContainText(
    label("desktop.host.unavailable"),
  );
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  for (const rows of await target.locator(".xterm-rows").all())
    await expect(rows).toHaveText("");
  await rail.getByRole("button", { name: label("desktop.rail.logs") }).click();
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.logs") }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(target.locator(".source-banner")).toHaveText(
    label("desktop.host.unavailable"),
  );
  await expect(target.locator(".record")).toHaveCount(0);
});

test("the rail opens and closes the panel tabs and the TUI pane", async ({
  page: target,
}) => {
  await target.goto("/");
  const rail = target.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  const panel = target.locator("section.panel");
  await rail
    .getByRole("button", { name: label("desktop.rail.python") })
    .click();
  await expect(panel).toBeVisible();
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.python") }),
  ).toHaveAttribute("aria-selected", "true");
  await rail
    .getByRole("button", { name: label("desktop.rail.python") })
    .click();
  await expect(panel).toBeHidden();
  await target.keyboard.press("Control+Backquote");
  await expect(panel).toBeVisible();
  await rail.getByRole("button", { name: label("desktop.rail.tui") }).click();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await rail.getByRole("button", { name: label("desktop.rail.tui") }).click();
  await expect(target.locator(".pane-tui")).toBeVisible();
});

test("maximizing and restoring keeps the documentation frame mounted", async ({
  page: target,
}) => {
  await openWithDocs(target);
  await target.evaluate(() => {
    (window as unknown as { frameBefore: Element | null }).frameBefore =
      document.querySelector(".docs-frame");
  });
  await target.locator(".pane-docs .pane-head button").first().click();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await expect(target.locator("section.panel")).toBeHidden();
  await target.locator(".pane-docs .pane-head button").first().click();
  await expect(target.locator(".pane-tui")).toBeVisible();
  await expect(target.locator("section.panel")).toBeVisible();
  const same = await target.evaluate(
    () =>
      (window as unknown as { frameBefore: Element | null }).frameBefore ===
      document.querySelector(".docs-frame"),
  );
  expect(same).toBe(true);
  await expect(target.frameLocator(".docs-frame").locator("h1")).toHaveText(
    "Stand-in documentation",
  );
});

test("the remembered layout survives a reload", async ({ page: target }) => {
  await target.goto("/");
  await target
    .getByRole("button", { name: label("desktop.rail.settings") })
    .click();
  const settings = target.getByRole("dialog", {
    name: label("desktop.settings.title"),
  });
  await settings
    .getByRole("radiogroup", { name: label("desktop.settings.docs_and_tui") })
    .getByRole("radio", { name: label("desktop.settings.stacked") })
    .click();
  await expect(target.locator(".split")).toHaveClass(/split-column/);
  await target.reload();
  await expect(target.locator(".split")).toHaveClass(/split-column/);
});

test("shell chords pressed inside the documentation reach the shell", async ({
  page: target,
}) => {
  await openWithDocs(target);
  const docs = target.frameLocator(".docs-frame");
  await docs.locator("#text").click();
  const palette = target.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  await expect(async () => {
    await target.keyboard.press("Control+KeyK");
    await expect(palette).toBeVisible({ timeout: 500 });
  }).toPass();
  await target.keyboard.press("Escape");
  await expect(palette).toBeHidden();
});

test("a context menu in the documentation offers copy, link and history", async ({
  page: target,
}) => {
  await openWithDocs(target);
  await target
    .frameLocator(".docs-frame")
    .locator("#external")
    .click({ button: "right" });
  const menu = target.getByRole("menu");
  await expect(menu).toBeVisible();
  await expect(
    menu.getByRole("menuitem", {
      name: label("desktop.menu.copy"),
      exact: true,
    }),
  ).toBeDisabled();
  await expect(
    menu.getByRole("menuitem", { name: label("desktop.menu.copy_link") }),
  ).toBeEnabled();
  await expect(
    menu.getByRole("menuitem", { name: label("desktop.action.docs_back") }),
  ).toBeEnabled();
  await expect(
    menu.getByRole("menuitem", { name: label("desktop.rail.docs_home") }),
  ).toBeEnabled();
  await target.keyboard.press("Escape");
  await expect(menu).toBeHidden();
});

test("external links never navigate the documentation frame", async ({
  page: target,
}) => {
  await openWithDocs(target);
  const docs = target.frameLocator(".docs-frame");
  await docs.locator("#external").click();
  await expect(docs.locator("h1")).toHaveText("Stand-in documentation");
  await docs.locator("#internal").click();
  await expect(docs.locator("h1")).toHaveText("Second page");
});

test("the palette lists actions and runs the chosen one", async ({
  page: target,
}) => {
  await target.goto("/");
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  await expect(palette.getByRole("option").first()).toBeVisible();
  await palette.getByRole("combobox").fill(label("desktop.pane.maximize_tui"));
  await target.keyboard.press("Enter");
  await expect(palette).toBeHidden();
  await expect(target.locator(".pane-docs")).toBeHidden();
  await expect(target.locator(".pane-tui")).toBeVisible();
});
