import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { seedLayout } from "./support/layout";
import { openPanelTab, panelToggle } from "./support/panel";
import { identity } from "../../scripts/configuration.mjs";
import { label } from "./support/strings";
import { ABOUT_FIXTURE } from "../src/dev/fixtures/about";
import {
  arrangement,
  DOCS,
  docsFrame,
  local,
  openWithDocs,
  page,
  revealTui,
  signInHost,
} from "./support/desktopShell";

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
  // The TUI and documentation wait to be asked for. The agent
  // works only for a signed-in profile, and with no host nobody is: its
  // column is not shown, and its button stays in the rail, held, saying why.
  await expect(target.locator(".pane-agent")).toBeHidden();
  const agent = rail.getByRole("button", {
    name: `${label("desktop.rail.agent")}, ${label("desktop.agent.sign_in_first")}`,
    exact: true,
  });
  await expect(agent).toHaveAttribute("aria-disabled", "true");
  await agent.click({ force: true });
  await expect(target.locator(".pane-agent")).toBeHidden();
  await expect(target.locator(".pane-docs")).toBeHidden();
  await expect(target.locator(".pane-docs")).toContainText(
    label("desktop.host.unavailable"),
  );
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(0);
  await revealTui(target);
  await expect(target.locator(".pane-tui .xterm")).toHaveCount(1);
  for (const rows of await target.locator(".xterm-rows").all())
    await expect(rows).toHaveText("");
  // Only the note shows: an idle terminal would draw its cursor over it.
  await expect(target.locator(".pane-tui .terminal-note")).toHaveText(
    label("desktop.host.unavailable"),
  );
  await expect(target.locator(".pane-tui .terminal-host")).toBeHidden();
  await openPanelTab(target, "logs");
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.logs") }),
  ).toHaveAttribute("aria-selected", "true");
  // The banner says the host is missing, and offers its one way back.
  const banner = target.locator(".source-banner");
  await expect(
    banner.getByText(label("desktop.host.unavailable"), { exact: true }),
  ).toBeVisible();
  await expect(
    banner.getByRole("button", {
      name: label("desktop.logs.reconnect"),
      exact: true,
    }),
  ).toBeVisible();
  await expect(banner).toHaveText(
    label("desktop.host.unavailable") + label("desktop.logs.reconnect"),
  );
  await expect(target.locator(".record")).toHaveCount(0);
});

test("the single rail toggle opens and closes the panel and preserves its tab", async ({
  page: target,
}) => {
  await target.goto("/");
  const rail = target.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  const panel = target.locator("section.panel");
  await expect(panel).toBeHidden();
  await openPanelTab(target, "python");
  await expect(panel).toBeVisible();
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.python") }),
  ).toHaveAttribute("aria-selected", "true");
  await panelToggle(target).click();
  await expect(panel).toBeHidden();
  await target.keyboard.press("Control+Backquote");
  await expect(panel).toBeVisible();
  await rail.getByRole("button", { name: label("desktop.rail.tui") }).click();
  await expect(target.locator(".pane-tui")).toBeVisible();
  await rail.getByRole("button", { name: label("desktop.rail.tui") }).click();
  await expect(target.locator(".pane-tui")).toBeHidden();
});

test("maximize, swap, orientation and hide never reload the documentation", async ({
  page: target,
}) => {
  await openWithDocs(target);
  await revealTui(target);
  // A marker in the page's own window survives only if the frame never
  // remounts or reloads.
  const docs = docsFrame(target);
  await docs.evaluate(() => {
    (window as unknown as { kept: boolean }).kept = true;
  });
  const docsHead = target.locator('[data-dock-header="docs"]');
  await docsHead
    .getByRole("button", { name: label("desktop.dock.expand"), exact: true })
    .click();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await expect(target.locator("section.panel")).toBeHidden();
  await docsHead
    .getByRole("button", { name: label("desktop.dock.restore"), exact: true })
    .click();
  await expect(target.locator(".pane-tui")).toBeVisible();
  // Swapped from the pane's arrangement menu, stacked from the palette.
  await docsHead
    .getByRole("button", { name: label("desktop.dock.arrange"), exact: true })
    .click();
  await target
    .getByRole("menuitem", { name: label("desktop.split.swap"), exact: true })
    .click();
  await expect.poll(() => arrangement(target)).toBe("row");
  await target.keyboard.press("ControlOrMeta+Shift+KeyK");
  await target
    .locator(".palette")
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.split.stack"));
  await target.keyboard.press("Enter");
  await expect.poll(() => arrangement(target)).toBe("column");
  const rail = target.getByRole("navigation", {
    name: label("desktop.rail.label"),
  });
  await rail.getByRole("button", { name: label("desktop.rail.tui") }).click();
  await expect(target.locator(".pane-tui")).toBeHidden();
  await rail.getByRole("button", { name: label("desktop.rail.tui") }).click();
  const kept = await docs.evaluate(
    () => (window as unknown as { kept?: boolean }).kept === true,
  );
  expect(kept).toBe(true);
});

test("a window too narrow for side by side stacks without changing the choice", async ({
  page: target,
}) => {
  await seedLayout(target);
  await target.goto("/");
  await revealTui(target);
  await expect.poll(() => arrangement(target)).toBe("row");
  const stackOffers = async () => {
    await target.keyboard.press("ControlOrMeta+Shift+KeyK");
    const palette = target.locator(".palette");
    await palette
      .getByRole("combobox", { name: label("desktop.palette.label") })
      .fill(label("desktop.split.stack"));
    const offers = await palette
      .getByRole("option")
      .filter({ hasText: label("desktop.split.stack") })
      .count();
    await target.keyboard.press("Escape");
    await expect(palette).toBeHidden();
    return offers;
  };
  expect(await stackOffers()).toBe(1);
  await target.setViewportSize({ width: 520, height: 600 });
  await expect.poll(() => arrangement(target)).toBe("column");
  // The choice cannot take effect here, so it is not offered.
  expect(await stackOffers()).toBe(0);
  // The window stacks them without changing the choice: given the room
  // again, they stand side by side as they were left.
  await target.setViewportSize({ width: 1280, height: 720 });
  await expect.poll(() => arrangement(target)).toBe("row");
  expect(await stackOffers()).toBe(1);
});

test("the documentation can relay only the chords the shell published to it", async ({
  page: target,
}) => {
  await openWithDocs(target);
  const docs = docsFrame(target);
  const post = (id: string) =>
    docs.evaluate((shortcut) => {
      parent.postMessage(
        {
          channel: "cadrumo-desktop",
          version: 1,
          type: "shortcut",
          id: shortcut,
        },
        "*",
      );
    }, id);
  // An action the shell never published to the frame is refused.
  await post("view.maximizeTui");
  await post("terminal.paste");
  await target.waitForTimeout(300);
  await expect(target.locator(".pane-docs")).toBeVisible();
  // A published chord is honoured, so the refusal above is not silence.
  await expect(async () => {
    await post("panel.logs");
    await expect(
      target.getByRole("tab", { name: label("desktop.rail.logs") }),
    ).toHaveAttribute("aria-selected", "true", { timeout: 500 });
  }).toPass();
});

test("bridge messages from any window but the documentation frame are ignored", async ({
  page: target,
}) => {
  await openWithDocs(target);
  await openPanelTab(target, "console");
  const logs = target.locator('[data-dock-pane="logs"]');
  await expect(logs).toBeHidden();
  await target.evaluate(() => {
    window.postMessage(
      {
        channel: "cadrumo-desktop",
        version: 1,
        type: "shortcut",
        id: "panel.logs",
      },
      "*",
    );
  });
  await target.waitForTimeout(300);
  await expect(logs).toBeHidden();
});

test("the remembered layout survives a reload", async ({ page: target }) => {
  await target.goto("/");
  await revealTui(target);
  await target
    .getByRole("button", { name: label("desktop.rail.settings"), exact: true })
    .click();
  const settings = target.getByRole("dialog", {
    name: label("desktop.settings.title"),
  });
  await settings
    .getByRole("radiogroup", { name: label("desktop.settings.docs_and_tui") })
    .getByRole("radio", { name: label("desktop.settings.stacked") })
    .click();
  await expect.poll(() => arrangement(target)).toBe("column");
  await target.keyboard.press("Escape");
  await openPanelTab(target, "python");
  await expect
    .poll(() =>
      target.evaluate(
        () =>
          JSON.parse(localStorage.getItem("cadrumo-shell-layout") ?? "null")
            ?.layout?.tab,
      ),
    )
    .toBe("python");
  await target.reload();
  // The TUI left shown is shown again, without being asked for.
  await expect(target.locator(".pane-tui")).toBeVisible();
  await expect.poll(() => arrangement(target)).toBe("column");
  await expect(target.locator("section.panel")).toBeVisible();
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.python") }),
  ).toHaveAttribute("aria-selected", "true");
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
  // Each item leads with its icon; the history items show the chord the
  // registry binds for them, in the platform's notation, and the others none:
  // Ctrl+C in the frame is the browser's own, which neither the shell binds
  // nor the bridge relays.
  const alt = process.platform === "darwin" ? "⌥" : "Alt";
  const items: [string, string, string[]][] = [
    ["desktop.menu.copy", "copy", []],
    ["desktop.menu.copy_link", "link", []],
    ["desktop.action.docs_back", "back", [alt, "←"]],
    ["desktop.action.docs_forward", "forward", [alt, "→"]],
    ["desktop.rail.docs_home", "book", [alt, "Home"]],
  ];
  for (const [key, icon, chord] of items) {
    const item = menu.getByRole("menuitem", { name: label(key), exact: true });
    await expect(item.locator(`[data-icon=${icon}]`)).toHaveCount(1);
    await expect(item.locator("kbd")).toHaveText(chord);
  }
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
  await expect(
    palette.getByRole("listbox").getByRole("option").first(),
  ).toBeVisible();
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill(label("desktop.pane.maximize_tui"));
  await target.keyboard.press("Enter");
  await expect(palette).toBeHidden();
  await expect(target.locator(".pane-docs")).toBeHidden();
  await expect(target.locator(".pane-tui")).toBeVisible();
});

test("a live documentation search survives more than four seconds of Pagefind work", async ({
  page: target,
}) => {
  const delayed = page(
    "Slow documentation",
    "<h1>Stand-in documentation</h1>",
  ).replace(
    "</head>",
    `<script>
      window.CadrumoDocs = {
        search: () => new Promise((resolve) => setTimeout(() => resolve([{
          kind: "concept", title: "modelo", href: "/second.html",
          excerpt: "Official form", crumb: "Documentation"
        }]), 4700))
      };
    </script></head>`,
  );
  await openWithDocs(target, delayed);
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  const palette = target.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  await palette
    .getByRole("combobox", { name: label("desktop.palette.label") })
    .fill("modelo");
  const result = palette.getByRole("option", { name: /modelo/i });
  await expect(result).toBeVisible({ timeout: 10000 });
  await expect(palette.locator(".palette-note")).toHaveCount(0);
  await result.click();
  await expect(target.frameLocator(".docs-frame").locator("h1")).toHaveText(
    "Second page",
  );
});

test("a forced appearance reaches the documentation through the bridge", async ({
  page: target,
}) => {
  await openWithDocs(target);
  await target
    .getByRole("button", { name: label("desktop.rail.settings"), exact: true })
    .click();
  await target
    .getByRole("radiogroup", { name: label("desktop.settings.appearance") })
    .getByRole("radio", { name: label("desktop.settings.dark") })
    .click();
  await expect
    .poll(() =>
      docsFrame(target).evaluate(() => document.body.dataset.theme ?? ""),
    )
    .toBe("dark");
  await expect(target.locator("html")).toHaveAttribute("data-scheme", "dark");
});

// The window's own content security policy, read from the Tauri configuration
// template, with the documentation origin framed as the build frames it. The
// component foundation positions overlays with inline styles and injects a
// few style elements; this proves the policy admits all of it as it stands.
test("the shell runs under the window's content security policy without a violation", async ({
  page: target,
}) => {
  const pageErrors: string[] = [];
  target.on("pageerror", (error) => pageErrors.push(error.message));
  const template = JSON.parse(
    readFileSync(local("../../src-tauri/tauri.conf.json.in"), "utf8"),
  ) as { app: { security: { csp: string } } };
  const policy = template.app.security.csp.replace(
    "frame-src 'none'",
    `frame-src ${DOCS}`,
  );
  expect(policy).toContain(`frame-src ${DOCS}`);
  await target.route(
    (url) => url.pathname === "/" || url.pathname.endsWith("/index.html"),
    async (route) => {
      if (route.request().url().startsWith(DOCS)) return route.fallback();
      const response = await route.fetch();
      await route.fulfill({
        response,
        headers: {
          ...response.headers(),
          "content-security-policy": policy,
        },
      });
    },
  );
  await target.addInitScript(() => {
    const seen: string[] = [];
    (window as unknown as { __violations: string[] }).__violations = seen;
    document.addEventListener("securitypolicyviolation", (event) =>
      seen.push(`${event.violatedDirective} ${event.blockedURI}`),
    );
  });
  await signInHost(target);
  // The sign-in dialog, its tooltip and its refusal.
  const password = target.getByLabel(label("desktop.signin.password"), {
    exact: true,
  });
  await expect(password).toBeVisible();
  await target
    .getByRole("button", { name: label("desktop.signin.show_password") })
    .focus();
  await expect(target.getByRole("tooltip")).toBeVisible();
  await password.fill("secret á漢");
  await target.keyboard.press("Enter");
  await expect(
    target.getByText(label("desktop.signin.refused.invalid")),
  ).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  // The palette and settings: every overlay the shell opens by itself.
  await target
    .getByRole("button", { name: label("desktop.rail.search") })
    .click();
  await expect(
    target.getByRole("dialog", { name: label("desktop.palette.label") }),
  ).toBeVisible();
  await target.keyboard.press("Escape");
  await target
    .getByRole("button", { name: label("desktop.rail.settings"), exact: true })
    .click();
  await expect(target.locator(".settings")).toBeVisible();
  await expect(target.locator(".settings [data-about-open]")).toContainText(
    ABOUT_FIXTURE.display_version!,
  );
  await target.keyboard.press("Escape");
  await expect(target.frameLocator(".docs-frame").locator("h1")).toHaveText(
    "Stand-in documentation",
  );
  await openPanelTab(target, "console");
  await expect(target.locator(".xterm").first()).toBeVisible();
  expect(
    await target.evaluate(
      () => (window as unknown as { __violations: string[] }).__violations,
    ),
  ).toEqual([]);
  expect(pageErrors).toEqual([]);
});
