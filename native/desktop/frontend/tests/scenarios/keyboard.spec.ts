import { expect, test, type Locator, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The shell by keyboard alone: tab stops, arrow-key patterns, shortcuts, and
// where focus goes when a surface opens and closes.

const open = (target: Page, scenario = "signed-in") =>
  target.goto(`/scenarios.html?scenario=${scenario}&latency=0&bar=off`);

const rail = (target: Page) =>
  target.getByRole("navigation", { name: label("desktop.rail.label") });

const focusedWithin = (area: Locator) => area.locator(":focus");

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

test("the rail is one tab stop and the arrow keys move within it", async ({
  page: target,
}) => {
  await open(target);
  const buttons = rail(target).getByRole("button");
  await buttons.first().focus();
  await target.keyboard.press("ArrowDown");
  await expect(buttons.nth(1)).toBeFocused();
  await target.keyboard.press("End");
  await expect(buttons.last()).toBeFocused();
  await target.keyboard.press("Home");
  await expect(buttons.first()).toBeFocused();
  // One stop: Tab leaves the rail instead of walking its buttons.
  await target.keyboard.press("Tab");
  await expect(focusedWithin(rail(target))).toHaveCount(0);
});

test("a rail button names itself to a keyboard user", async ({
  page: target,
}) => {
  await open(target);
  await rail(target).getByRole("button").first().focus();
  await expect(target.getByRole("tooltip")).toContainText(
    label("desktop.rail.search"),
  );
});

test("the panel tabs follow the arrow keys and keep focus in the row", async ({
  page: target,
}) => {
  await open(target);
  const tab = (key: string) => target.getByRole("tab", { name: label(key) });
  await tab("desktop.rail.console").focus();
  await target.keyboard.press("ArrowRight");
  await expect(tab("desktop.rail.python")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(tab("desktop.rail.python")).toBeFocused();
  await expect(target.locator('[data-terminal="python"]')).toBeVisible();
  await target.keyboard.press("ArrowRight");
  await expect(tab("desktop.rail.logs")).toBeFocused();
  await expect(target.locator("#panel-logs")).toBeVisible();
  // Enter hands the keyboard to the chosen view.
  await target.keyboard.press("ArrowLeft");
  await expect(tab("desktop.rail.python")).toBeFocused();
  await target.keyboard.press("Enter");
  await expect(
    target.locator('[data-terminal="python"] textarea'),
  ).toBeFocused();
});

test("both splitters move by the arrow keys and report their position", async ({
  page: target,
}) => {
  await open(target);
  // Each reports the share of the area it sizes: the documentation pane for
  // the split, which the left arrow narrows, and the bottom panel for its
  // own handle, which the down arrow lowers.
  for (const [name, back] of [
    [label("desktop.split.resize"), "ArrowLeft"],
    [label("desktop.panel.resize"), "ArrowDown"],
  ] as const) {
    const handle = target.getByRole("separator", { name });
    await handle.focus();
    const before = Number(await handle.getAttribute("aria-valuenow"));
    await target.keyboard.press(back);
    await expect
      .poll(async () => Number(await handle.getAttribute("aria-valuenow")))
      .toBeLessThan(before);
    await expect(handle).toBeFocused();
    const smaller = Number(await handle.getAttribute("aria-valuenow"));
    await target.keyboard.press(
      back === "ArrowLeft" ? "ArrowRight" : "ArrowUp",
    );
    await expect
      .poll(async () => Number(await handle.getAttribute("aria-valuenow")))
      .toBeGreaterThan(smaller);
  }
});

test("the rail is as wide as its token and marks its chosen item on screen", async ({
  page: target,
}) => {
  await open(target);
  const measured = await rail(target).evaluate((nav) => ({
    width: nav.getBoundingClientRect().width,
    token: parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue(
        "--spacing-rail",
      ),
    ),
    rem: parseFloat(getComputedStyle(document.documentElement).fontSize),
  }));
  expect(measured.width).toBe(measured.token * measured.rem);
  // The bar beside the chosen item is drawn inside the window.
  const bar = await rail(target)
    .locator('button[aria-pressed="true"]')
    .first()
    .evaluate((button) => {
      const style = getComputedStyle(button, "::before");
      return {
        left: button.getBoundingClientRect().left + parseFloat(style.left),
        opacity: style.opacity,
      };
    });
  expect(bar.left).toBeGreaterThanOrEqual(0);
  expect(bar.opacity).toBe("1");
});

test("the palette opens by chord, runs by Enter and returns focus", async ({
  page: target,
}) => {
  await open(target);
  const opener = rail(target).getByRole("button").nth(1);
  await opener.focus();
  await target.keyboard.press("Control+KeyK");
  const palette = target.getByRole("dialog", {
    name: label("desktop.palette.label"),
  });
  await expect(palette.getByRole("combobox")).toBeFocused();
  // The arrow keys move the choice while focus stays in the input.
  const options = palette.getByRole("option");
  await expect(options.first()).toHaveAttribute("aria-selected", "true");
  await target.keyboard.press("ArrowDown");
  await expect(options.nth(1)).toHaveAttribute("aria-selected", "true");
  await expect(palette.getByRole("combobox")).toBeFocused();
  await target.keyboard.press("Escape");
  await expect(palette).toBeHidden();
  await expect(opener).toBeFocused();
});

test("an action run from the palette keeps the focus it takes", async ({
  page: target,
}) => {
  await open(target);
  await rail(target).getByRole("button").nth(1).focus();
  await target.keyboard.press("Control+KeyK");
  const palette = target.locator(".palette");
  await palette.getByRole("combobox").fill(label("desktop.rail.python"));
  await expect(palette.getByRole("option").first()).toContainText(
    label("desktop.rail.python"),
  );
  await target.keyboard.press("Enter");
  await expect(palette).toHaveCount(0);
  await expect(
    target.locator('[data-terminal="python"] textarea'),
  ).toBeFocused();
  // Chosen by name, a view is shown, not toggled: choosing it again keeps it.
  await target.keyboard.press("Control+Shift+KeyK");
  await palette.getByRole("combobox").fill(label("desktop.rail.python"));
  await target.keyboard.press("Enter");
  await expect(target.locator('[data-terminal="python"]')).toBeVisible();
  await expect(
    target.locator('[data-terminal="python"] textarea'),
  ).toBeFocused();
});

test("settings opened from the palette inside a terminal stays open", async ({
  page: target,
}) => {
  await open(target);
  await target.locator('[data-terminal="console"] .xterm-screen').click();
  await target.keyboard.press("Control+Shift+KeyK");
  const palette = target.locator(".palette");
  await palette.getByRole("combobox").fill(label("desktop.settings.title"));
  await expect(palette.getByRole("option").first()).toContainText(
    label("desktop.settings.title"),
  );
  await target.keyboard.press("Enter");
  const settings = target.locator(".settings");
  await expect(settings).toBeVisible();
  await expect(focusedWithin(settings)).toHaveCount(1);
  // It is still there once every focus hand-over has settled.
  await target.waitForTimeout(300);
  await expect(settings).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(settings).toHaveCount(0);
  await expect(
    target.locator('[data-terminal="console"] textarea'),
  ).toBeFocused();
});

test("no chord reaches the shell from under the sign-in dialog", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  const dialog = target.locator(".sign-in");
  await expect(target.locator("#profile-password")).toBeFocused();
  await target.keyboard.press("Control+Comma");
  await target.keyboard.press("Control+KeyK");
  await target.keyboard.press("Control+Shift+KeyT");
  await target.keyboard.press("F6");
  await expect(target.locator(".settings")).toHaveCount(0);
  await expect(target.locator(".palette")).toHaveCount(0);
  await expect(target.locator(".pane-tui")).toBeVisible();
  await expect(focusedWithin(dialog)).toHaveCount(1);
});

test("F6 reaches the calendar where the documentation would be", async ({
  page: target,
}) => {
  // Short enough that the calendar has more than it can show at once.
  await target.setViewportSize({ width: 1280, height: 520 });
  await open(target);
  await rail(target)
    .getByRole("button", { name: label("desktop.calendar.title") })
    .click();
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page).toBeFocused();
  // The focused page is what scrolls: the keyboard moves through it.
  const scrolled = () => page.evaluate((element) => element.scrollTop);
  expect(await scrolled()).toBe(0);
  await target.keyboard.press("PageDown");
  await expect.poll(scrolled).toBeGreaterThan(0);
  // The scroll is eased: the next key waits for it to come to rest, or the
  // first would carry on over it.
  const resting = async () => {
    const at = await scrolled();
    await target.waitForTimeout(120);
    return at === (await scrolled());
  };
  await expect.poll(resting).toBe(true);
  await target.keyboard.press("Home");
  await expect.poll(scrolled).toBe(0);
  await target.keyboard.press("F6");
  await expect(target.locator('[data-terminal="tui"] textarea')).toBeFocused();
  await target.keyboard.press("Shift+F6");
  await expect(page).toBeFocused();
  // Inside the page the keyboard reaches its controls in order.
  await target.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: label("desktop.calendar.refresh") }),
  ).toBeFocused();
});

test("the calendar's chord shows it from a terminal and puts it away again", async ({
  page: target,
}) => {
  await open(target);
  await target.locator('[data-terminal="tui"] .xterm-screen').click();
  await expect(target.locator('[data-terminal="tui"] textarea')).toBeFocused();
  await target.keyboard.press("ControlOrMeta+Shift+D");
  const page = target.getByRole("region", {
    name: label("desktop.calendar.title"),
  });
  await expect(page).toBeFocused();
  // The chord is on the button that does the same.
  const button = rail(target).getByRole("button", {
    name: label("desktop.calendar.title"),
  });
  await expect(button).toHaveAttribute("aria-pressed", "true");
  await button.hover();
  await expect(target.getByRole("tooltip")).toContainText("D");
  await target.keyboard.press("ControlOrMeta+Shift+D");
  await expect(page).toHaveCount(0);
  await expect(target.locator(".docs-frame")).toBeVisible();
});

test("the calendar's chord does nothing on a host without profile views", async ({
  page: target,
}) => {
  await open(target, "no-views");
  await expect(target.locator(".docs-frame")).toBeVisible();
  await rail(target).getByRole("button").first().focus();
  await target.keyboard.press("ControlOrMeta+Shift+D");
  await expect(target.locator(".calendar-page")).toHaveCount(0);
  await expect(target.locator(".docs-frame")).toBeVisible();
});

test("F6 moves focus from area to area and back", async ({ page: target }) => {
  await open(target);
  await expect(target.locator(".docs-frame")).toBeVisible();
  await rail(target).getByRole("button").first().focus();
  await target.keyboard.press("F6");
  await expect(target.locator(".docs-frame")).toBeFocused();
  // Inside the frame the documentation's own bridge would send the chord;
  // from the frame element the shell hears it directly.
  await target.keyboard.press("F6");
  await expect(target.locator('[data-terminal="tui"] textarea')).toBeFocused();
  await target.keyboard.press("F6");
  await expect(
    target.locator('[data-terminal="console"] textarea'),
  ).toBeFocused();
  await target.keyboard.press("F6");
  await expect(focusedWithin(rail(target))).toHaveCount(1);
  await target.keyboard.press("Shift+F6");
  await expect(
    target.locator('[data-terminal="console"] textarea'),
  ).toBeFocused();
});

test("settings opens on the current choice, moves by arrows and returns focus", async ({
  page: target,
}) => {
  await open(target);
  const opener = rail(target).getByRole("button", {
    name: label("desktop.rail.settings"),
  });
  await opener.focus();
  await target.keyboard.press("Enter");
  const appearance = target.getByRole("radiogroup", {
    name: label("desktop.settings.appearance"),
  });
  await expect(
    appearance.getByRole("radio", {
      name: label("desktop.settings.follow_docs"),
    }),
  ).toBeFocused();
  await target.keyboard.press("ArrowRight");
  await expect(
    appearance.getByRole("radio", { name: label("desktop.settings.light") }),
  ).toHaveAttribute("aria-checked", "true");
  await target.keyboard.press("Escape");
  await expect(target.locator(".settings")).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("the shell's chords reach their actions from the chrome", async ({
  page: target,
}) => {
  await open(target);
  await rail(target).getByRole("button").first().focus();
  await target.keyboard.press("Control+Shift+KeyT");
  await expect(target.locator(".pane-tui")).toBeHidden();
  await target.keyboard.press("Control+Shift+KeyT");
  await expect(target.locator(".pane-tui")).toBeVisible();
  await rail(target).getByRole("button").first().focus();
  await target.keyboard.press("Control+Backquote");
  await expect(target.locator("section.panel")).toBeHidden();
  await target.keyboard.press("Control+Shift+Digit3");
  await expect(
    target.getByRole("tab", { name: label("desktop.rail.logs") }),
  ).toHaveAttribute("aria-selected", "true");
  await target.keyboard.press("Control+Shift+KeyM");
  await expect(target.locator(".main-area")).toBeHidden();
  await target.keyboard.press("Control+Shift+KeyM");
  await expect(target.locator(".main-area")).toBeVisible();
  await rail(target).getByRole("button").first().focus();
  await target.keyboard.press("Control+Comma");
  await expect(target.locator(".settings")).toBeVisible();
});

test("a focused terminal keeps its own keys and yields only the global chords", async ({
  page: target,
}) => {
  await open(target);
  await target.locator('[data-terminal="console"] .xterm-screen').click();
  // Ctrl+K belongs to the terminal: the palette stays closed.
  await target.keyboard.press("Control+KeyK");
  await expect(target.locator(".palette")).toHaveCount(0);
  await target.keyboard.press("Control+Shift+KeyK");
  await expect(target.locator(".palette")).toBeVisible();
});

test("the sign-in dialog keeps Tab inside it and Escape hands focus on", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  const dialog = target.locator(".sign-in");
  await expect(target.locator("#profile-password")).toBeFocused();
  for (let press = 0; press < 8; press++) {
    await target.keyboard.press("Tab");
    await expect(focusedWithin(dialog)).toHaveCount(1);
  }
  for (let press = 0; press < 8; press++) {
    await target.keyboard.press("Shift+Tab");
    await expect(focusedWithin(dialog)).toHaveCount(1);
  }
  await target.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(
    target.locator(".pane-tui").getByRole("button", {
      name: label("desktop.signin.submit"),
      exact: true,
    }),
  ).toBeFocused();
});

test("the reveal control shows and hides the password by keyboard", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  const field = target.locator("#profile-password");
  await field.fill("a secret");
  await expect(field).toHaveAttribute("type", "password");
  await target
    .getByRole("button", { name: label("desktop.signin.show_password") })
    .press("Enter");
  await expect(field).toHaveAttribute("type", "text");
  await target
    .getByRole("button", { name: label("desktop.signin.hide_password") })
    .press("Space");
  await expect(field).toHaveAttribute("type", "password");
  await expect(field).toHaveValue("a secret");
});

test("a log record's detail opens and closes by keyboard", async ({
  page: target,
}) => {
  await open(target);
  await rail(target)
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  const toggle = target.getByRole("button", {
    name: label("desktop.logs.details"),
  });
  await toggle.focus();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await target.keyboard.press("Enter");
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(target.locator(".record pre")).toContainText("Traceback");
  // And closes by the same key, with the keyboard still on it.
  await target.keyboard.press("Enter");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(target.locator(".record pre")).toHaveCount(0);
  await expect(toggle).toBeFocused();
});

test("log records are reached, marked and given their menu by keyboard", async ({
  page: target,
}) => {
  await open(target);
  await rail(target)
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  const rows = target.locator(".logview-list .record");
  const count = await rows.count();
  expect(count).toBeGreaterThan(3);
  // One tab stop: from the filter, Tab passes the bar's controls and lands
  // on the newest record.
  await target.locator(".logview .filter-text").focus();
  for (let press = 0; press < 12; press++) {
    await target.keyboard.press("Tab");
    if (await target.locator(".logview-list .record:focus").count()) break;
  }
  await expect(rows.last()).toBeFocused();
  await expect(rows.last()).toHaveAttribute("aria-current", "true");
  await target.keyboard.press("ArrowUp");
  await expect(rows.nth(count - 2)).toBeFocused();
  await expect(rows.nth(count - 2)).toHaveAttribute("aria-current", "true");
  await expect(rows.last()).not.toHaveAttribute("aria-current", "true");
  await target.keyboard.press("Home");
  await expect(rows.first()).toBeFocused();
  await target.keyboard.press("End");
  await expect(rows.last()).toBeFocused();
  expect(
    await rows.evaluateAll(
      (all) => all.filter((row) => row.tabIndex === 0).length,
    ),
  ).toBe(1);
  // The menu key opens the menu a right-click opens, beside its row and
  // never across it: at the end of the list, in the middle and at the top.
  const menu = target.getByRole("menu", {
    name: label("desktop.palette.actions"),
  });
  for (const at of [count - 1, Math.floor(count / 2), 0]) {
    const row = rows.nth(at);
    await row.focus();
    await target.keyboard.press("ContextMenu");
    await expect(menu).toBeVisible();
    await expect(row).toHaveAttribute("aria-current", "true");
    const [rowBox, menuBox] = [
      await row.boundingBox(),
      await menu.boundingBox(),
    ];
    if (!rowBox || !menuBox) throw new Error("The menu or its row is gone.");
    const across =
      menuBox.y < rowBox.y + rowBox.height - 1 &&
      menuBox.y + menuBox.height > rowBox.y + 1;
    expect(across, `row ${at}`).toBe(false);
    await target.keyboard.press("Escape");
    await expect(menu).toBeHidden();
    await expect(row).toBeFocused();
  }
  // Shift+F10 is the same key by another name.
  await target.keyboard.press("Shift+F10");
  await expect(menu).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  // The log has a name of its own for a screen reader's list of regions.
  await expect(
    target.getByRole("log", { name: label("desktop.rail.logs") }),
  ).toBeVisible();
});

test("Enter on a record opens its detail", async ({ page: target }) => {
  await open(target);
  await rail(target)
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  const row = target
    .locator(".logview-list .record")
    .filter({ has: target.locator("[aria-expanded]") })
    .first();
  await row.focus();
  await target.keyboard.press("Enter");
  await expect(row.locator("pre")).toContainText("Traceback");
  await target.keyboard.press("Enter");
  await expect(row.locator("pre")).toHaveCount(0);
});

test("the menu stand-in follows the arrow keys and closes on Escape", async ({
  page: target,
}) => {
  await open(target);
  await rail(target)
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  await target.locator(".record").first().click({ button: "right" });
  const menu = target.getByRole("menu");
  await expect(menu).toBeVisible();
  await target.keyboard.press("ArrowDown");
  await expect(menu.getByRole("menuitem").first()).toBeFocused();
  await target.keyboard.press("Escape");
  await expect(menu).toBeHidden();
});

test("a view chosen in the palette from inside a terminal takes focus every time", async ({
  page: target,
}) => {
  await open(target);
  const palette = target.locator(".palette");
  const choose = async (key: string) => {
    await target.keyboard.press("Control+Shift+KeyK");
    await palette.getByRole("combobox").fill(label(key));
    await expect(palette.getByRole("option").first()).toContainText(label(key));
    await target.keyboard.press("Enter");
    await expect(palette).toHaveCount(0);
  };
  await target.locator('[data-terminal="console"] .xterm-screen').click();
  // The view is shown by a state change that commits after the choice; focus
  // has to wait for it. Repeated, because losing that race is intermittent.
  for (let round = 0; round < 4; round++) {
    await choose("desktop.rail.python");
    await expect(
      target.locator('[data-terminal="python"] textarea'),
    ).toBeFocused();
    await choose("desktop.rail.logs");
    await expect(target.locator(".logview .filter-text")).toBeFocused();
    await choose("desktop.rail.console");
    await expect(
      target.locator('[data-terminal="console"] textarea'),
    ).toBeFocused();
  }
});

test("chords work while the sign-in state is still being read", async ({
  page: target,
}) => {
  // No dialog is on screen until the read answers, so nothing owns the
  // keyboard above the shell.
  await open(target, "loading");
  await expect(target.locator(".sign-in")).toHaveCount(0);
  await rail(target).getByRole("button").first().focus();
  await target.keyboard.press("Control+KeyK");
  await expect(target.locator(".palette")).toBeVisible();
  await target.keyboard.press("Control+KeyK");
  await expect(target.locator(".palette")).toHaveCount(0);
  await target.keyboard.press("Control+Backquote");
  await expect(target.locator("section.panel")).toBeHidden();
});

test("a chord sent from the documentation does not act under the sign-in dialog", async ({
  page: target,
}) => {
  await open(target, "signed-out");
  await expect(target.locator("#profile-password")).toBeFocused();
  const page = target.frameLocator(".docs-frame").locator("body");
  await expect(page).toContainText("Stand-in documentation");
  // The documentation's bridge forwards the shell's chords; a page that has
  // taken focus by itself can send one while the dialog is open.
  await page.press("Control+Comma");
  await page.press("Control+Shift+KeyT");
  await target.waitForTimeout(300);
  await expect(target.locator(".settings")).toHaveCount(0);
  await expect(target.locator(".pane-tui")).toBeVisible();
});

test("a press outside a record's menu keeps what it pressed", async ({
  page: target,
}) => {
  await open(target);
  await rail(target)
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  const rows = target.locator(".logview-list .record");
  const menu = target.getByRole("menu");
  await rows.nth(1).click({ button: "right" });
  await expect(menu).toBeVisible();
  const filter = target.locator(".logview .filter-text");
  await filter.click();
  await expect(menu).toBeHidden();
  await target.keyboard.type("Idle");
  await expect(filter).toHaveValue("Idle");
  await filter.fill("");
  // A right-click on another record closes this menu and opens that one.
  await rows.nth(1).click({ button: "right" });
  await expect(menu).toBeVisible();
  await rows.nth(3).click({ button: "right" });
  await target.waitForTimeout(400);
  await expect(menu).toBeVisible();
  await expect(rows.nth(3)).toHaveAttribute("aria-current", "true");
});

test("the log is one tab stop however many records have a detail", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=2000",
  );
  await rail(target)
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  const list = target.locator(".logview-list");
  await expect(list.locator(".record").first()).toBeAttached();
  const stops = await list.evaluate(
    (element) =>
      [...element.querySelectorAll<HTMLElement>("*")].filter(
        (node) => node.tabIndex >= 0,
      ).length,
  );
  expect(stops).toBe(1);
});

test("bringing in earlier records leaves the view on the record it was on", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=signed-in&latency=0&bar=off&records=3000",
  );
  await rail(target)
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  const list = target.locator(".logview-list");
  const rows = list.locator(".record");
  await expect(rows).toHaveCount(400);
  // Near the top of the drawn span, which asks for the span before it.
  const before = await list.evaluate((element) => {
    element.scrollTop = 40;
    const edge = element.getBoundingClientRect().top;
    const row = [...element.querySelectorAll<HTMLElement>(".record")].find(
      (candidate) => candidate.getBoundingClientRect().bottom > edge,
    );
    return {
      seq: row?.dataset.seq ?? "",
      top: (row?.getBoundingClientRect().top ?? 0) - edge,
    };
  });
  await expect(rows).toHaveCount(800);
  const after = await list.evaluate((element, seq) => {
    const edge = element.getBoundingClientRect().top;
    const row = element.querySelector(`[data-seq="${seq}"]`);
    return (row?.getBoundingClientRect().top ?? Number.NaN) - edge;
  }, before.seq);
  expect(Math.abs(after - before.top)).toBeLessThanOrEqual(2);
});

test("a chord pressed in the documentation focuses the view it shows", async ({
  page: target,
}) => {
  await open(target);
  const page = target.frameLocator(".docs-frame").locator("body");
  await expect(page).toContainText("Stand-in documentation");
  // The chord crosses the documentation's bridge, so the view it shows is
  // not on screen yet when the shell hears of it.
  for (let round = 0; round < 3; round++) {
    await page.press("Control+Shift+Digit2");
    await expect(
      target.locator('[data-terminal="python"] textarea'),
    ).toBeFocused();
    await page.press("Control+Shift+Digit3");
    await expect(target.locator(".logview .filter-text")).toBeFocused();
  }
});

test("the arrow keys move on from a record's detail toggle", async ({
  page: target,
}) => {
  await open(target);
  await rail(target)
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  const rows = target.locator(".logview-list .record");
  const withDetail = rows.filter({ has: target.locator("[aria-expanded]") });
  // A click leaves focus on the toggle; the keyboard carries on from there.
  await withDetail.first().locator("[aria-expanded]").click();
  await expect(withDetail.first().locator("pre")).toBeVisible();
  await target.keyboard.press("ArrowDown");
  await expect(target.locator(".logview-list .record:focus")).toHaveCount(1);
  await expect(withDetail.first()).not.toBeFocused();
});

test("a press in the documentation while a menu is open keeps focus there", async ({
  page: target,
}) => {
  await open(target);
  await rail(target)
    .getByRole("button", { name: label("desktop.rail.logs") })
    .click();
  await target
    .locator(".logview-list .record")
    .nth(1)
    .click({ button: "right" });
  const menu = target.getByRole("menu");
  await expect(menu).toBeVisible();
  await target.frameLocator(".docs-frame").locator("h1").click();
  await expect(menu).toBeHidden();
  await target.waitForTimeout(200);
  await expect(target.locator(".docs-frame")).toBeFocused();
});
