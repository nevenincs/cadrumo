import { expect, test, type Page } from "@playwright/test";
import type { SedeViewDialogKind, SedeViewInput } from "../../src/ipc/contract";
import {
  SEDE_VIEW_HOME,
  SEDE_VIEW_ORIGIN,
  SEDE_VIEW_TITLE,
} from "../../src/dev/sedeViewFixture";
import { label } from "../support/strings";
import { windowToast } from "../support/toast";

// The Browser page on the scenario host: the profile worker's browser is a
// made-up page drawn on a canvas, and the host's calls are the evidence of
// what the window asked for. The page is a browser the person drives freely,
// so these tests prove what the window sends, shows and keeps, never what a
// site does. Presentation evidence only: no host, runtime or Sede is behind
// them.

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() => {
    if (sessionStorage.getItem("layout-cleared")) return;
    localStorage.clear();
    sessionStorage.setItem("layout-cleared", "1");
  });
});

const rail = (target: Page) =>
  target.getByRole("navigation", { name: label("desktop.rail.label") });
const railButton = (target: Page, key: string) =>
  rail(target).getByRole("button", { name: label(key), exact: true });
const browserButton = (target: Page) =>
  railButton(target, "desktop.browser.title");

const browserPage = (target: Page) =>
  target.getByRole("region", {
    name: label("desktop.browser.title"),
    exact: true,
  });
const surface = (target: Page) =>
  browserPage(target).getByRole("group", {
    name: label("desktop.browser.surface"),
    exact: true,
  });
const toolbar = (target: Page) => target.locator("[data-browser-toolbar]");
const control = (target: Page, key: string) =>
  toolbar(target).getByRole("button", { name: label(key), exact: true });
const address = (target: Page) =>
  toolbar(target).getByRole("group", {
    name: label("desktop.browser.address"),
    exact: true,
  });
const prompts = (target: Page) =>
  browserPage(target).locator("[data-browser-prompts]");
/** The line over the page that says `text`. */
const line = (target: Page, text: string) =>
  prompts(target).getByRole("status").filter({ hasText: text });
const pageDialog = (target: Page) => target.getByRole("dialog");

const open = async (target: Page) => {
  await target.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await expect(railButton(target, "desktop.rail.agent")).not.toHaveAttribute(
    "aria-disabled",
    "true",
  );
};

/** Every host call of the run, in order. */
const calls = (target: Page) =>
  target.evaluate(() => window.__scenarioHostCalls ?? []);
/** Where the run's calls stand, so that a later read names only new ones. */
const mark = async (target: Page) => (await calls(target)).length;
const since = async (target: Page, at: number, call: string) =>
  (await calls(target)).slice(at).filter((made) => made === call);
const externalOpens = async (target: Page) =>
  (await calls(target)).filter((call) => call.startsWith("openExternal "));

const inputs = (target: Page) =>
  target.evaluate(() => window.__scenarioSedeView?.inputs() ?? []);
const received = (target: Page) =>
  target.evaluate(() => window.__scenarioSedeView?.received() ?? {});
const images = (target: Page) =>
  target.evaluate(() => window.__scenarioSedeView?.images() ?? 0);
const answers = (target: Page) =>
  target.evaluate(() => window.__scenarioSedeView?.answers() ?? []);
const credits = async (target: Page) =>
  (await calls(target)).filter((call) => call === "sedeViewCredit").length;

/** The made-up page is up: its address shows, the host is playing it and it
 * has drawn an image. */
async function live(target: Page) {
  await expect(address(target)).toContainText(
    `${SEDE_VIEW_ORIGIN}${SEDE_VIEW_HOME}`,
  );
  await expect
    .poll(() => target.evaluate(() => window.__scenarioSedeView !== undefined))
    .toBe(true);
  await expect.poll(() => images(target)).toBeGreaterThan(0);
}

/** Every image sent has been credited back, so the stream is idle. */
const idle = (target: Page) =>
  expect
    .poll(async () => {
      const sent = await images(target);
      return sent > 0 && (await credits(target)) === sent;
    })
    .toBe(true);

async function showBrowser(target: Page) {
  await open(target);
  await browserButton(target).click();
  await live(target);
  await idle(target);
}

async function bounds(target: Page) {
  const box = await surface(target).boundingBox();
  if (!box) throw new Error("The page has no surface to point at.");
  return box;
}

/** The events a key press or typed text became, as `down:a`, `text:a`. */
const brief = (event: SedeViewInput) =>
  event.type === "key"
    ? `${event.action}:${event.key}`
    : event.type === "text"
      ? `text:${event.text}`
      : event.type;

const near = (found: number, wanted: number) =>
  expect(Math.abs(found - wanted)).toBeLessThanOrEqual(2);

// ---------------------------------------------------------------------------
// The rail and the AEAT shortcut
// ---------------------------------------------------------------------------

test("the Browser rail button opens the page at the Sede, and a second click leaves it with the view running", async ({
  page: target,
}) => {
  await open(target);
  const button = browserButton(target);
  await expect(button).toHaveAttribute("aria-pressed", "false");
  await expect(browserPage(target)).toHaveCount(0);

  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "true");
  await expect(browserPage(target)).toBeFocused();
  await live(target);
  // The window names no address of its own, and opens nothing outside.
  expect(await externalOpens(target)).toEqual([]);

  const at = await mark(target);
  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "false");
  await expect(browserPage(target)).toHaveCount(0);
  // Coming back finds the same view, still at its page.
  await button.click();
  await expect(browserPage(target)).toBeVisible();
  await expect(address(target)).toContainText(
    `${SEDE_VIEW_ORIGIN}${SEDE_VIEW_HOME}`,
  );
  expect(await since(target, at, "sedeViewClose")).toEqual([]);
  expect(await since(target, at, "sedeViewOpen")).toEqual([]);
});

test("the AEAT click starts the view, and its menu opens the system browser while the view keeps running", async ({
  page: target,
}) => {
  await open(target);
  const aeat = railButton(target, "desktop.rail.aeat");
  const first = await mark(target);
  await aeat.click();
  await expect(browserButton(target)).toHaveAttribute("aria-pressed", "true");
  await live(target);
  expect(await since(target, first, "sedeViewOpen")).toHaveLength(1);
  expect(await externalOpens(target)).toEqual([]);

  const at = await mark(target);
  await aeat.click({ button: "right" });
  const menu = target.getByRole("menu");
  await expect(menu.getByRole("menuitem")).toHaveCount(1);
  await menu
    .getByRole("menuitem", { name: label("desktop.browser.external") })
    .click();
  await expect
    .poll(() => externalOpens(target))
    .toEqual(["openExternal https://sede.agenciatributaria.gob.es"]);
  // The menu is the person's own browser; the view is not touched.
  await expect(address(target)).toContainText(SEDE_VIEW_ORIGIN);
  expect(await since(target, at, "sedeViewClose")).toEqual([]);
  expect(await since(target, at, "sedeViewOpen")).toEqual([]);
});

test("the AEAT click brings an open view forward and sends it back to the Sede", async ({
  page: target,
}) => {
  await showBrowser(target);
  const aeat = railButton(target, "desktop.rail.aeat");

  // Shown already, the view still goes home.
  let at = await mark(target);
  await aeat.click();
  await expect
    .poll(() => since(target, at, "sedeViewNavigate home"))
    .toHaveLength(1);

  // Put aside behind another page, the click brings the same view forward.
  await railButton(target, "desktop.calendar.title").click();
  await expect(browserPage(target)).toHaveCount(0);
  at = await mark(target);
  await aeat.click();
  await expect(browserPage(target)).toBeVisible();
  await expect
    .poll(() => since(target, at, "sedeViewNavigate home"))
    .toHaveLength(1);
  expect(await since(target, at, "sedeViewOpen")).toEqual([]);
  expect(await since(target, at, "sedeViewClose")).toEqual([]);
});

// ---------------------------------------------------------------------------
// The toolbar
// ---------------------------------------------------------------------------

test("the toolbar's back, forward, reload and home reach the view, and its external button asks the host to open the page it holds", async ({
  page: target,
}) => {
  await showBrowser(target);
  const back = control(target, "desktop.browser.back");
  const forward = control(target, "desktop.browser.forward");
  const reload = control(target, "desktop.browser.reload");
  const home = control(target, "desktop.browser.home");
  const external = control(target, "desktop.browser.external");

  // At the start page there is nowhere to go back or forward to.
  await expect(back).toBeDisabled();
  await expect(forward).toBeDisabled();
  for (const each of [reload, home, external]) await expect(each).toBeEnabled();

  const at = await mark(target);
  await home.click();
  await expect
    .poll(() => since(target, at, "sedeViewNavigate home"))
    .toHaveLength(1);
  await expect(back).toBeEnabled();
  await expect(forward).toBeDisabled();

  await back.click();
  await expect
    .poll(() => since(target, at, "sedeViewNavigate back"))
    .toHaveLength(1);
  await expect(back).toBeDisabled();
  await expect(forward).toBeEnabled();

  await forward.click();
  await expect
    .poll(() => since(target, at, "sedeViewNavigate forward"))
    .toHaveLength(1);
  await expect(forward).toBeDisabled();
  await expect(back).toBeEnabled();

  await reload.click();
  await expect
    .poll(() => since(target, at, "sedeViewNavigate reload"))
    .toHaveLength(1);

  // The host holds the address: the window asks for "the page" and sends none.
  await external.click();
  await expect
    .poll(() => since(target, at, "sedeViewOpenExternal page"))
    .toHaveLength(1);
  expect(await externalOpens(target)).toEqual([]);
  // The address is shown, never typed.
  await expect(address(target).getByRole("textbox")).toHaveCount(0);
});

// ---------------------------------------------------------------------------
// Keys, pointer, wheel and text
// ---------------------------------------------------------------------------

test("a page off https shows its marker instead of the address it left, and has no page to open externally", async ({
  page: target,
}) => {
  await showBrowser(target);
  const external = control(target, "desktop.browser.external");
  await expect(external).toBeEnabled();
  for (const [security, words] of [
    ["insecure", "desktop.browser.page_insecure"],
    ["unknown", "desktop.browser.page_unknown"],
  ] as const) {
    await target.evaluate(
      (left) => window.__scenarioSedeView?.leave(left),
      security,
    );
    await expect(address(target)).toHaveAttribute(
      "data-browser-security",
      security,
    );
    await expect(address(target)).toContainText(label(words));
    await expect(address(target)).not.toContainText(SEDE_VIEW_ORIGIN);
    await expect(address(target)).not.toHaveAttribute("title");
    await expect(external).toBeDisabled();
  }
  // Back on the Sede, its address and its external open return.
  const at = await mark(target);
  await control(target, "desktop.browser.home").click();
  await live(target);
  await expect(external).toBeEnabled();
  await external.click();
  await expect
    .poll(() => since(target, at, "sedeViewOpenExternal page"))
    .toHaveLength(1);
});

test("the shell's chords stay out of the canvas while it has focus, and run again once focus leaves", async ({
  page: target,
}) => {
  await showBrowser(target);
  const palette = target.locator(".palette");
  // How many times the page was given this key, up or down.
  const heard = async (key: string) =>
    (await inputs(target)).filter(
      (each) => each.type === "key" && each.key === key,
    ).length;
  const box = await bounds(target);
  await target.mouse.click(box.x + 60, box.y + 60);
  await expect(surface(target)).toBeFocused();

  // Ctrl+K belongs to the page, as it does in a terminal.
  await target.keyboard.press("ControlOrMeta+KeyK");
  await expect.poll(() => heard("k")).toBe(2);
  await expect(palette).toHaveCount(0);
  expect(
    (await inputs(target)).find(
      (each) => each.type === "key" && each.key === "k",
    ),
  ).toMatchObject({ action: "down", modifiers: 2 });

  // Tab is the page's too: focus stays in the canvas.
  await target.keyboard.press("Tab");
  await expect.poll(() => heard("Tab")).toBe(2);
  await expect(surface(target)).toBeFocused();

  // The chords that fire everywhere still do, and the page does not get them.
  await target.keyboard.press("ControlOrMeta+Shift+KeyK");
  await expect(palette).toBeVisible();
  expect(await heard("K")).toBe(0);
  expect(await heard("k")).toBe(2);
  await target.keyboard.press("Escape");
  await expect(palette).toHaveCount(0);

  // Out of the canvas, Ctrl+K opens the palette and the page hears nothing.
  await browserPage(target).focus();
  await expect(surface(target)).not.toBeFocused();
  await target.keyboard.press("ControlOrMeta+KeyK");
  await expect(palette).toBeVisible();
  await target.keyboard.press("Escape");
  await expect(palette).toHaveCount(0);
  await browserPage(target).focus();
  await target.keyboard.press("KeyA");
  expect(await heard("k")).toBe(2);
  expect(await heard("a")).toBe(0);
});

test("the person's pointer, wheel and typing reach the page in its own pixels", async ({
  page: target,
}) => {
  await showBrowser(target);
  const box = await bounds(target);
  const events = async (from: number) => (await inputs(target)).slice(from);
  const next = async () => (await inputs(target)).length;

  // A click is a move, a press and a release at the point the person chose.
  let from = await next();
  await target.mouse.click(box.x + 120, box.y + 80);
  await expect
    .poll(async () =>
      (await events(from)).flatMap((each) =>
        each.type === "pointer" ? [each.action] : [],
      ),
    )
    .toEqual(["move", "down", "up"]);
  const down = (await events(from))[1];
  if (down?.type !== "pointer") throw new Error("The press was not sent.");
  expect(down).toMatchObject({ button: "left", click_count: 1, modifiers: 0 });
  near(down.x, 120);
  near(down.y, 80);

  // A second press in quick succession counts as a double click.
  from = await next();
  await target.mouse.dblclick(box.x + 120, box.y + 80);
  await expect
    .poll(async () =>
      (await events(from)).flatMap((each) =>
        each.type === "pointer" && each.action === "down"
          ? [each.click_count]
          : [],
      ),
    )
    .toEqual([1, 2]);

  // The right button goes to the page, and the shell draws no menu over it.
  from = await next();
  await target.mouse.click(box.x + 200, box.y + 100, { button: "right" });
  await expect
    .poll(async () =>
      (await events(from)).flatMap((each) =>
        each.type === "pointer" && each.action !== "move"
          ? [`${each.action}:${each.button}`]
          : [],
      ),
    )
    .toEqual(["down:right", "up:right"]);
  await expect(target.getByRole("menu")).toHaveCount(0);

  // The wheel turns the page, in the page's pixels, at the pointer.
  from = await next();
  await target.mouse.move(box.x + 300, box.y + 150);
  await target.mouse.wheel(0, 120);
  await expect
    .poll(async () =>
      (await events(from)).filter((each) => each.type === "wheel"),
    )
    .toHaveLength(1);
  const wheel = (await events(from)).find((each) => each.type === "wheel");
  if (wheel?.type !== "wheel") throw new Error("The wheel was not sent.");
  expect(wheel).toMatchObject({ delta_x: 0, delta_y: 120, modifiers: 0 });
  near(wheel.x, 300);
  near(wheel.y, 150);

  // Typing is each key and the text it types, in the order it was pressed.
  await target.mouse.click(box.x + 120, box.y + 80);
  await expect(surface(target)).toBeFocused();
  from = await next();
  await target.keyboard.type("hola 7");
  const typed = [..."hola 7"].flatMap((each) => [
    `down:${each}`,
    `text:${each}`,
    `up:${each}`,
  ]);
  await expect
    .poll(async () => (await events(from)).map((each) => brief(each)))
    .toEqual(typed);

  // A paste is its text, with Enter for each line break.
  from = await next();
  await surface(target).evaluate((element) => {
    const data = new DataTransfer();
    data.setData("text/plain", "primera linea\nsegunda linea");
    element.dispatchEvent(
      new ClipboardEvent("paste", {
        clipboardData: data,
        bubbles: true,
        cancelable: true,
      }),
    );
  });
  await expect
    .poll(async () => (await events(from)).map((each) => brief(each)))
    .toEqual([
      "text:primera linea",
      "down:Enter",
      "up:Enter",
      "text:segunda linea",
    ]);
});

// ---------------------------------------------------------------------------
// Credit
// ---------------------------------------------------------------------------

test("every image is credited once it is drawn, so the stream keeps flowing past the credit it started with", async ({
  page: target,
}) => {
  await showBrowser(target);
  const box = await bounds(target);
  await target.mouse.click(box.x + 40, box.y + 40);
  // The view starts with credit for two images. Each change after that is
  // drawn only because the window credited an earlier one.
  for (let round = 0; round < 6; round += 1) {
    const sent = await images(target);
    await target.keyboard.press("KeyA");
    await expect.poll(() => images(target)).toBeGreaterThan(sent);
    await idle(target);
  }
  expect(await images(target)).toBeGreaterThan(2);
  expect(await credits(target)).toBe(await images(target));
});

const PUTTING_ASIDE = {
  "another page of the rail": {
    away: (target: Page) =>
      railButton(target, "desktop.calendar.title").click(),
    back: (target: Page) => browserButton(target).click(),
  },
  "the agent pane maximized": {
    away: async (target: Page) => {
      const agent = railButton(target, "desktop.rail.agent");
      if ((await agent.getAttribute("aria-pressed")) !== "true")
        await agent.click();
      await target
        .locator(".pane-agent")
        .getByRole("button", { name: label("desktop.pane.maximize_agent") })
        .click();
    },
    back: (target: Page) =>
      target
        .locator(".pane-agent")
        .getByRole("button", { name: label("desktop.pane.restore") })
        .click(),
  },
} as const;

for (const [way, { away, back }] of Object.entries(PUTTING_ASIDE)) {
  test(`a page put aside by ${way} grants no credit, and shown again it credits what it owes so the newest image arrives at once`, async ({
    page: target,
  }) => {
    await showBrowser(target);
    await away(target);
    await expect(surface(target)).toBeHidden();

    const at = await mark(target);
    const sent = await images(target);
    // Three changes while out of sight: the view has credit for two of them,
    // and the third waits in the worker as the newest image.
    for (const phase of ["acquiring", "browsing", "acquiring"] as const)
      await target.evaluate(
        (next) => window.__scenarioSedeView?.phase(next),
        phase,
      );
    await expect.poll(() => images(target)).toBe(sent + 2);
    // Time for a credit to be sent if one were going to be.
    await target.waitForTimeout(300);
    expect(await images(target)).toBe(sent + 2);
    expect(await since(target, at, "sedeViewCredit")).toEqual([]);
    // The view was neither closed nor reopened for being out of sight.
    expect(await since(target, at, "sedeViewClose")).toEqual([]);

    await back(target);
    await expect(surface(target)).toBeVisible();
    await expect.poll(() => images(target)).toBe(sent + 3);
    await expect
      .poll(async () => (await since(target, at, "sedeViewCredit")).length)
      .toBe(3);
    await idle(target);
    expect(await since(target, at, "sedeViewClose")).toEqual([]);
    expect(await since(target, at, "sedeViewOpen")).toEqual([]);
  });
}

test("a download offered while the page is put aside is kept, and answerable once the page is shown again", async ({
  page: target,
}) => {
  await showBrowser(target);
  await railButton(target, "desktop.calendar.title").click();
  await expect(surface(target)).toBeHidden();

  const at = await mark(target);
  await target.evaluate(() =>
    window.__scenarioSedeView?.download("informe-aparte.pdf"),
  );
  await target.waitForTimeout(300);
  expect(await since(target, at, "sedeViewClose")).toEqual([]);

  await browserButton(target).click();
  const prompt = line(
    target,
    label("desktop.browser.download.prompt", { name: "informe-aparte.pdf" }),
  );
  await expect(prompt).toBeVisible();
  await prompt
    .getByRole("button", { name: label("desktop.browser.download.decline") })
    .click();
  await expect
    .poll(() => answers(target))
    .toEqual([{ kind: "download", id: 1, accepted: false }]);
});

// ---------------------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------------------

test("downloads wait for the person oldest first, and the native dialog opens only for the one answered", async ({
  page: target,
}) => {
  await showBrowser(target);
  const more = label("desktop.browser.notice.more", { count: 1 });
  await target.evaluate(() => {
    window.__scenarioSedeView?.download("informe-primero.pdf");
    window.__scenarioSedeView?.download("informe-segundo.pdf");
  });
  const first = line(
    target,
    label("desktop.browser.download.prompt", { name: "informe-primero.pdf" }),
  );
  await expect(first).toBeVisible();
  await expect(first).toContainText(more);
  await expect(prompts(target).getByText("informe-segundo.pdf")).toHaveCount(0);

  // Saving asks the host's dialog about the first; the second still waits.
  const at = await mark(target);
  await first
    .getByRole("button", { name: label("desktop.browser.download.save") })
    .click();
  const second = line(
    target,
    label("desktop.browser.download.prompt", { name: "informe-segundo.pdf" }),
  );
  await expect(second).toBeVisible();
  await expect(second).not.toContainText(more);
  await expect(
    line(target, label("desktop.browser.download.done")),
  ).toBeVisible();
  await second
    .getByRole("button", { name: label("desktop.browser.download.decline") })
    .click();
  await expect(second).toHaveCount(0);

  expect(await answers(target)).toEqual([
    { kind: "download", id: 1, accepted: true },
    { kind: "download", id: 2, accepted: false },
  ]);
  expect(await since(target, at, "sedeViewDownload save")).toHaveLength(1);
  expect(await since(target, at, "sedeViewDownload decline")).toHaveLength(1);
});

test("file choosers wait for the person oldest first, and a refusal says it was cancelled", async ({
  page: target,
}) => {
  await showBrowser(target);
  await target.evaluate(() => {
    window.__scenarioSedeView?.fileChooser(false);
    window.__scenarioSedeView?.fileChooser(true);
  });
  const one = line(target, label("desktop.browser.upload.prompt"));
  await expect(one).toBeVisible();
  await expect(one).toContainText(
    label("desktop.browser.notice.more", { count: 1 }),
  );
  await expect(
    line(target, label("desktop.browser.upload.prompt_many")),
  ).toHaveCount(0);

  const at = await mark(target);
  await one
    .getByRole("button", { name: label("desktop.browser.upload.choose") })
    .click();
  const many = line(target, label("desktop.browser.upload.prompt_many"));
  await expect(many).toBeVisible();
  await expect(
    line(target, label("desktop.browser.upload.done")),
  ).toBeVisible();
  await many
    .getByRole("button", { name: label("desktop.browser.upload.decline") })
    .click();
  await expect(many).toHaveCount(0);
  await expect(
    line(target, label("desktop.browser.upload.cancelled")),
  ).toBeVisible();

  expect(await answers(target)).toEqual([
    { kind: "file_chooser", id: 1, accepted: true },
    { kind: "file_chooser", id: 2, accepted: false },
  ]);
  expect(await since(target, at, "sedeViewUpload choose")).toHaveLength(1);
  expect(await since(target, at, "sedeViewUpload cancel")).toHaveLength(1);
});

test("a sign-in as another taxpayer is said in the person's words until it is dismissed", async ({
  page: target,
}) => {
  await showBrowser(target);
  await target.evaluate(() => window.__scenarioSedeView?.identityMismatch());
  const said = line(target, label("desktop.browser.notice.identity_mismatch"));
  await expect(said).toBeVisible();
  await said
    .getByRole("button", { name: label("desktop.browser.notice.dismiss") })
    .click();
  await expect(said).toHaveCount(0);
});

test("page dialogs are answered by the person, each in its own words", async ({
  page: target,
}) => {
  await showBrowser(target);
  const dialog = pageDialog(target);
  const play = (kind: SedeViewDialogKind, message: string, suggestion = "") =>
    target.evaluate(
      ([asked, text, suggested]) =>
        window.__scenarioSedeView?.dialog(
          asked,
          text,
          suggested === "" ? undefined : suggested,
        ),
      [kind, message, suggestion] as const,
    );
  const button = (key: string) =>
    dialog.getByRole("button", { name: label(key), exact: true });

  // An alert has one answer.
  await play("alert", "Aviso de la pagina");
  await expect(dialog).toContainText("Aviso de la pagina");
  await expect(button("desktop.browser.dialog.cancel")).toHaveCount(0);
  await button("desktop.browser.dialog.ok").click();
  await expect(dialog).toHaveCount(0);

  // A confirm can be declined.
  await play("confirm", "Seguro?");
  await expect(dialog).toContainText("Seguro?");
  await button("desktop.browser.dialog.cancel").click();
  await expect(dialog).toHaveCount(0);

  // A prompt starts from the page's suggestion and answers with the text.
  await play("prompt", "Tu nombre?", "Ana");
  const field = dialog.getByLabel(label("desktop.browser.dialog.prompt_label"));
  await expect(field).toHaveValue("Ana");
  await field.fill("Berta");
  await field.press("Enter");
  await expect(dialog).toHaveCount(0);

  // A page that asks before it is left is described in the window's words.
  await play("beforeunload", "Texto propio de la pagina");
  await expect(
    dialog.getByText(label("desktop.browser.dialog.leave_description")),
  ).toBeVisible();
  await expect(dialog).not.toContainText("Texto propio de la pagina");
  await button("desktop.browser.dialog.stay").click();
  await expect(dialog).toHaveCount(0);

  expect(await answers(target)).toEqual([
    { kind: "dialog", id: 1, accepted: true, text: null },
    { kind: "dialog", id: 2, accepted: false, text: null },
    { kind: "dialog", id: 3, accepted: true, text: "Berta" },
    { kind: "dialog", id: 4, accepted: false, text: null },
  ]);
});

test("dialogs queue oldest first, and closing one any other way declines it", async ({
  page: target,
}) => {
  await showBrowser(target);
  const dialog = pageDialog(target);
  await target.evaluate(() => {
    window.__scenarioSedeView?.dialog("confirm", "Primera pregunta", undefined);
    window.__scenarioSedeView?.dialog("confirm", "Segunda pregunta", undefined);
  });
  await expect(dialog).toContainText("Primera pregunta");
  await target.keyboard.press("Escape");
  await expect(dialog).toContainText("Segunda pregunta");
  await dialog
    .getByRole("button", {
      name: label("desktop.browser.dialog.ok"),
      exact: true,
    })
    .click();
  await expect(dialog).toHaveCount(0);
  expect(await answers(target)).toEqual([
    { kind: "dialog", id: 1, accepted: false, text: null },
    { kind: "dialog", id: 2, accepted: true, text: null },
  ]);
});

// ---------------------------------------------------------------------------
// A login that runs, and a session that is being saved
// ---------------------------------------------------------------------------

for (const way of ["key", "pointer"] as const)
  test(`the person's ${way} is not refused while a login runs, and takes it over`, async ({
    page: target,
  }) => {
    await showBrowser(target);
    await target.evaluate(() => window.__scenarioSedeView?.phase("acquiring"));
    const running = line(target, label("desktop.browser.acquiring"));
    await expect(running).toBeVisible();
    // The page and its controls stay usable, with nothing refused.
    for (const key of [
      "desktop.browser.reload",
      "desktop.browser.home",
      "desktop.browser.external",
    ])
      await expect(control(target, key)).toBeEnabled();

    await surface(target).focus();
    const box = await bounds(target);
    const before = (await received(target))[way] ?? 0;
    if (way === "key") await target.keyboard.press("KeyB");
    else await target.mouse.click(box.x + 50, box.y + 50);
    await expect
      .poll(async () => (await received(target))[way] ?? 0)
      .toBeGreaterThan(before);
    await expect(running).toHaveCount(0);
    await expect(browserPage(target).getByRole("alert")).toHaveCount(0);
    if (way === "key")
      expect(await inputs(target)).toContainEqual(
        expect.objectContaining({ type: "key", action: "down", key: "b" }),
      );
  });

test("a view that is saving its session shows it, holds every navigation and takes no input until it ends", async ({
  page: target,
}) => {
  await showBrowser(target);
  const box = await bounds(target);
  await target.mouse.click(box.x + 50, box.y + 50);
  await expect(surface(target)).toBeFocused();

  await target.evaluate(() => window.__scenarioSedeView?.phase("closing"));
  await expect(browserPage(target)).toHaveAttribute("aria-busy", "true");
  await expect(
    browserPage(target).getByText(label("desktop.browser.closing")),
  ).toBeVisible();
  for (const key of [
    "desktop.browser.back",
    "desktop.browser.forward",
    "desktop.browser.reload",
    "desktop.browser.home",
  ])
    await expect(control(target, key)).toBeDisabled();
  // Opening the person's own browser is not held by the saving.
  await expect(control(target, "desktop.browser.external")).toBeEnabled();

  // Neither the pointer nor the keyboard reaches the page now.
  const heard = await received(target);
  await target.mouse.click(box.x + 80, box.y + 80);
  await target.keyboard.press("KeyC");
  expect(await received(target)).toEqual(heard);

  // Leaving is refused, and the page stays where it is.
  await railButton(target, "desktop.calendar.title").click();
  await expect(windowToast(target)).toHaveText(
    label("desktop.navigation.busy"),
  );
  await expect(browserPage(target)).toBeVisible();
  await expect(target.locator(".calendar-page")).toHaveCount(0);

  // When it has ended, the page says how the session was kept and lets go.
  await target.evaluate(() =>
    window.__scenarioSedeView?.end("closed", "published"),
  );
  await expect(
    browserPage(target).getByText(label("desktop.browser.ended.closed")),
  ).toBeVisible();
  await expect(
    browserPage(target).getByText(
      label("desktop.browser.publication.published"),
    ),
  ).toBeVisible();
  await expect(browserPage(target)).not.toHaveAttribute("aria-busy", "true");

  // It can be opened again, and leaving is no longer refused.
  const at = await mark(target);
  await browserPage(target)
    .getByRole("button", { name: label("desktop.browser.reopen") })
    .click();
  await live(target);
  expect(await since(target, at, "sedeViewOpen")).toHaveLength(1);
  await railButton(target, "desktop.calendar.title").click();
  await expect(target.locator(".calendar-page")).toBeVisible();
});

// ---------------------------------------------------------------------------
// Leaving the page
// ---------------------------------------------------------------------------

const LEAVING = {
  "the Browser rail button": (target: Page) => browserButton(target).click(),
  "another page of the rail": (target: Page) =>
    railButton(target, "desktop.calendar.title").click(),
} as const;

for (const [way, leave] of Object.entries(LEAVING))
  test(`leaving the page by ${way} keeps the view running, and coming back finds it`, async ({
    page: target,
  }) => {
    await showBrowser(target);
    const at = await mark(target);
    await leave(target);
    await expect(browserPage(target)).toHaveCount(0);

    // Out of sight, the view goes on, and what it sends is not credited yet.
    const sent = await images(target);
    await target.evaluate(() => window.__scenarioSedeView?.phase("browsing"));
    await expect.poll(() => images(target)).toBe(sent + 1);
    await target.waitForTimeout(300);
    expect(await since(target, at, "sedeViewCredit")).toEqual([]);

    await browserButton(target).click();
    await expect(browserPage(target)).toBeVisible();
    await idle(target);
    await expect(address(target)).toContainText(
      `${SEDE_VIEW_ORIGIN}${SEDE_VIEW_HOME}`,
    );
    expect(await since(target, at, "sedeViewClose")).toEqual([]);
    expect(await since(target, at, "sedeViewOpen")).toEqual([]);
  });

test("closing the page with its close control closes the view once, and the next page waits for its session to be saved", async ({
  page: target,
}) => {
  await showBrowser(target);
  const at = await mark(target);
  await target
    .getByRole("button", {
      name: label("desktop.browser.close"),
      exact: true,
    })
    .click();
  await expect(browserPage(target)).toHaveCount(0);
  await expect.poll(() => since(target, at, "sedeViewClose")).toHaveLength(1);

  // The view is still saving its session: a new page says so, then opens.
  await browserButton(target).click();
  await expect(
    browserPage(target).getByText(label("desktop.browser.waiting")),
  ).toBeVisible();
  await live(target);
  expect(await since(target, at, "sedeViewOpen")).toHaveLength(1);
  // Closing is the only thing the window asked of the first view.
  expect(await since(target, at, "sedeViewClose")).toHaveLength(1);
});

test("signing out closes the view and leaves the page without a browser", async ({
  page: target,
}) => {
  await showBrowser(target);
  const at = await mark(target);
  await target
    .getByRole("button", { name: label("desktop.titlebar.profile_menu") })
    .click();
  await target
    .getByRole("menuitem", {
      name: label("desktop.account.sign_out"),
      exact: true,
    })
    .click();
  await expect(surface(target)).toHaveCount(0);
  await expect(
    browserPage(target).getByText(
      label("desktop.browser.failure.not_signed_in"),
    ),
  ).toBeVisible();
  await expect.poll(() => since(target, at, "sedeViewClose")).toHaveLength(1);
});

// ---------------------------------------------------------------------------
// What is kept
// ---------------------------------------------------------------------------

test("no frame, address or title of the page reaches storage, the window's address or its title", async ({
  page: target,
}) => {
  await showBrowser(target);
  const box = await bounds(target);
  await target.mouse.click(box.x + 90, box.y + 90);
  await target.keyboard.type("texto");
  await control(target, "desktop.browser.home").click();
  await target.evaluate(() => {
    window.__scenarioSedeView?.download("secreto.pdf");
  });
  await expect(
    line(
      target,
      label("desktop.browser.download.prompt", { name: "secreto.pdf" }),
    ),
  ).toBeVisible();
  await idle(target);

  // The page id may be saved; nothing the page drew or said is.
  await expect
    .poll(() =>
      target.evaluate(() => localStorage.getItem("cadrumo-shell-layout") ?? ""),
    )
    .toContain('"page":"browser"');
  const kept = await target.evaluate(() =>
    [...Object.entries(localStorage), ...Object.entries(sessionStorage)]
      .flat()
      .join("\n"),
  );
  const marks = [
    "sede.example",
    SEDE_VIEW_HOME,
    SEDE_VIEW_TITLE,
    "secreto.pdf",
    "texto",
    "data:image",
    "blob:",
    "/9j/",
  ];
  for (const found of marks) expect(kept, found).not.toContain(found);
  for (const found of [target.url(), await target.title()])
    for (const mine of [SEDE_VIEW_ORIGIN, SEDE_VIEW_TITLE])
      expect(found).not.toContain(mine);
});

test("a view refused for want of the browser says so and offers the browser's setup, not the generic refusal", async ({
  page: target,
}) => {
  await target.goto(
    "/scenarios.html?scenario=sede-browser-missing&latency=0&bar=off",
  );
  await target
    .getByRole("dialog", { name: label("desktop.setup.title") })
    .getByRole("button", { name: label("desktop.setup.not_now") })
    .click();
  await browserButton(target).click();
  const ended = browserPage(target)
    .getByRole("status")
    .filter({
      hasText: label("desktop.browser.ended.component_not_ready"),
    });
  await expect(ended).toBeVisible();
  await expect(browserPage(target)).not.toContainText(
    label("desktop.browser.failure.refused"),
  );
  await expect(browserPage(target)).not.toContainText(
    label("desktop.browser.ended.refused"),
  );
  // The offer comes from the setup the recorded verdict names.
  const offer = ended.locator('[data-setup-offer="browser"]');
  await expect(offer).toBeVisible();
  await offer.getByRole("button").click();
  await expect(
    target.getByRole("dialog", { name: label("desktop.setup.item.browser") }),
  ).toBeVisible();
  await expect(target.locator("body")).not.toContainText("operator.");
});

test("a view the host opens names no setup when it ends", async ({
  page: target,
}) => {
  await open(target);
  await browserButton(target).click();
  await expect(surface(target)).toBeVisible();
  await target.evaluate(() =>
    window.__scenarioSedeView?.end("operation_ended"),
  );
  const ended = browserPage(target)
    .getByRole("status")
    .filter({
      hasText: label("desktop.browser.ended.stopped"),
    });
  await expect(ended).toBeVisible();
  await expect(ended.locator("[data-setup-offer]")).toHaveCount(0);
});
