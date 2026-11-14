import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The packaged window's audit of the rail pages, measured the same way in the
// scenario host: the same probes (the pane audit and the page geometry of
// window-ux-audit.test.mjs), the same names and the same sizes, read from the
// page. UX-08 the Ledger sections, UX-09 the profile, UX-10 the profile's
// household, UX-11 the settings popover, UX-12 the AEAT data page and UX-13
// back and forward between the pages visited. Each page at each size is its
// own test, and each check inside is soft, so every failure is reported.
// A page the host does not offer fails as "not reachable" with its reason.

/** The audit's window sizes: its default and the three it found short. */
const SIZES = [
  [1441, 923],
  [1280, 800],
  [1024, 640],
  [900, 600],
] as const;

/** The least height the scrolling region of a page keeps (as the Modelo form
 * does, see modelo-window-ux.spec.ts). */
const SCROLLER_FLOOR = 150;

// ---------------------------------------------------------------------------
// The probes, as they run in the page. Each is self-contained: Playwright
// serialises it.
// ---------------------------------------------------------------------------

interface Box extends Array<number> {
  0: number;
  1: number;
  2: number;
  3: number;
}

interface PaneAudit {
  found: boolean;
  viewport?: [number, number];
  root?: string;
  rootBox?: Box;
  paneBox?: Box;
  header?: { box: Box; inPane: boolean; titleShown: boolean } | null;
  scroller?: {
    el: string;
    clientHeight: number;
    scrollHeight: number;
    box: Box;
  } | null;
  clipped?: { el: string; clientHeight: number; scrollHeight: number }[];
  clippedCount?: number;
  boundary?: boolean;
}

/** Report the place of a page's header, its main scrolling region and every
 * overflow-hidden box that clips visible content vertically. */
function paneAudit(args: {
  rootSel: string;
  options?: { pane?: string; header?: string };
}): PaneAudit {
  const { rootSel, options } = args;
  const shown = (el: Element) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return (
      r.width > 0 &&
      r.height > 0 &&
      cs.visibility !== "hidden" &&
      cs.display !== "none"
    );
  };
  const describe = (el: Element) =>
    `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${
      typeof el.className === "string" && el.className
        ? "." + el.className.split(/\s+/).filter(Boolean).slice(0, 2).join(".")
        : ""
    }`;
  const box = (el: Element) => {
    const r = el.getBoundingClientRect();
    return [r.left, r.top, r.right, r.bottom].map(Math.round) as Box;
  };
  const scrolls = (el: Element) =>
    /auto|scroll/.test(getComputedStyle(el).overflowY);
  const root = [...document.querySelectorAll(rootSel)].find(shown);
  if (!root) return { found: false };
  const pane =
    (options?.pane ? root.closest(options.pane) : null) ??
    root.closest(".main-area");
  const paneBox: Box = pane
    ? box(pane)
    : ([0, 0, window.innerWidth, window.innerHeight] as Box);
  // The pane header; a page that draws its own <header> (the profile) is
  // measured by that.
  const header = options?.header
    ? [...document.querySelectorAll(options.header)].find(shown)
    : ((pane ?? document).querySelector('[data-slot="pane-header"]') ??
      root.querySelector("header"));
  const headerBox = header && shown(header) ? box(header) : null;
  // The header may itself be the heading (the settings popover's is).
  const title = header?.matches("h1, h2, h3")
    ? header
    : header?.querySelector("h1, h2, h3");
  const titleBox = title && shown(title) ? box(title) : null;
  // The nearest scrolling ancestor-or-self, else the tallest scrolling
  // descendant.
  let scroller: Element | null = null;
  for (
    let p: Element | null = root;
    p && p !== document.body;
    p = p.parentElement
  ) {
    if (scrolls(p) && shown(p)) {
      scroller = p;
      break;
    }
  }
  if (!scroller) {
    for (const el of root.querySelectorAll("*")) {
      if (
        scrolls(el) &&
        shown(el) &&
        (!scroller || el.clientHeight > scroller.clientHeight)
      )
        scroller = el;
    }
  }
  const clipped: { el: string; clientHeight: number; scrollHeight: number }[] =
    [];
  const scan: Element[] = [...root.querySelectorAll("*"), root];
  for (
    let p: Element | null = root.parentElement;
    p && p !== document.body;
    p = p.parentElement
  )
    scan.push(p);
  for (const el of scan) {
    if (getComputedStyle(el).overflowY !== "hidden") continue;
    if (
      !shown(el) ||
      el.clientHeight <= 0 ||
      el.scrollHeight <= el.clientHeight + 2
    )
      continue;
    if (![...el.children].some(shown)) continue;
    clipped.push({
      el: describe(el),
      clientHeight: el.clientHeight,
      scrollHeight: el.scrollHeight,
    });
  }
  const boundary = document.querySelector(
    '[data-error-boundary], [data-slot="error-boundary"], .error-boundary',
  );
  return {
    found: true,
    viewport: [window.innerWidth, window.innerHeight],
    root: describe(root),
    rootBox: box(root),
    paneBox,
    header: headerBox && {
      box: headerBox,
      inPane:
        headerBox[1] >= paneBox[1] - 1 &&
        headerBox[3] <= paneBox[3] + 1 &&
        headerBox[0] >= paneBox[0] - 1 &&
        headerBox[2] <= paneBox[2] + 1,
      titleShown: !!titleBox && titleBox[2] - titleBox[0] > 1,
    },
    scroller: scroller && {
      el: describe(scroller),
      clientHeight: scroller.clientHeight,
      scrollHeight: scroller.scrollHeight,
      box: box(scroller),
    },
    clipped: clipped.slice(0, 10),
    clippedCount: clipped.length,
    boundary: !!boundary,
  };
}

interface Geometry {
  viewport: [number, number];
  docScroll: [number, number];
  unreachable: {
    el: string;
    name: string;
    rect: number[];
    outOfWindow: boolean;
  }[];
  overflowHidden: number;
}

/** The viewport, the document's scroll size and every shown interactive
 * element or heading that lies outside the viewport with no scrolling
 * ancestor to bring it in, or outside an ancestor that clips it without
 * scrolling. */
function pageGeometry(): Geometry {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const shown = (el: Element) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return (
      r.width > 0 &&
      r.height > 0 &&
      cs.visibility !== "hidden" &&
      cs.display !== "none" &&
      cs.opacity !== "0"
    );
  };
  const name = (el: Element) =>
    (el.getAttribute("aria-label") || el.textContent || el.id || "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 50);
  const describe = (el: Element) =>
    `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${
      typeof el.className === "string" && el.className
        ? "." + el.className.split(/\s+/).filter(Boolean).slice(0, 2).join(".")
        : ""
    }`;
  const clippedBy = (el: Element) => {
    // The nearest ancestor that clips `el` on an axis without scrolling to it.
    const r = el.getBoundingClientRect();
    for (
      let p = el.parentElement;
      p && p !== document.body;
      p = p.parentElement
    ) {
      const cs = getComputedStyle(p);
      const clipX = cs.overflowX !== "visible";
      const clipY = cs.overflowY !== "visible";
      if (!clipX && !clipY) continue;
      const pr = p.getBoundingClientRect();
      const outY = clipY && (r.bottom > pr.bottom + 1 || r.top < pr.top - 1);
      const outX = clipX && (r.right > pr.right + 1 || r.left < pr.left - 1);
      if (outY || outX) {
        const scrolls =
          (outY && /auto|scroll/.test(cs.overflowY)) ||
          (outX && /auto|scroll/.test(cs.overflowX));
        return { scrolls };
      }
    }
    return null;
  };
  // A shown control scrolled out of view inside a scrolling ancestor is
  // reachable by scrolling; one outside the window with no such ancestor is not.
  const scrollable = (el: Element) => {
    for (
      let p = el.parentElement;
      p && p !== document.body;
      p = p.parentElement
    ) {
      const cs = getComputedStyle(p);
      if (
        (/auto|scroll/.test(cs.overflowY) &&
          p.scrollHeight > p.clientHeight + 1) ||
        (/auto|scroll/.test(cs.overflowX) && p.scrollWidth > p.clientWidth + 1)
      )
        return true;
    }
    return false;
  };
  const unreachable: Geometry["unreachable"] = [];
  const interesting = document.querySelectorAll(
    'button, a[href], input, select, textarea, [role="tab"], [role="button"], h1, h2, [role="grid"]',
  );
  for (const el of interesting) {
    if (!shown(el)) continue;
    const r = el.getBoundingClientRect();
    const clip = clippedBy(el);
    const outOfWindow =
      r.bottom > vh + 1 || r.right > vw + 1 || r.top < -1 || r.left < -1;
    if ((outOfWindow && !scrollable(el)) || (clip && !clip.scrolls)) {
      unreachable.push({
        el: describe(el),
        name: name(el),
        rect: [r.left, r.top, r.right, r.bottom].map(Math.round),
        outOfWindow,
      });
    }
  }
  let overflowHidden = 0;
  for (const el of document.querySelectorAll("*")) {
    const cs = getComputedStyle(el);
    if (
      (cs.overflowY === "hidden" &&
        el.scrollHeight > el.clientHeight + 2 &&
        el.clientHeight > 0) ||
      (cs.overflowX === "hidden" &&
        el.scrollWidth > el.clientWidth + 2 &&
        el.clientWidth > 0)
    ) {
      if (shown(el)) overflowHidden += 1;
    }
  }
  return {
    viewport: [vw, vh],
    docScroll: [
      document.documentElement.scrollWidth,
      document.documentElement.scrollHeight,
    ],
    unreachable: unreachable.slice(0, 25),
    overflowHidden,
  };
}

/** An error boundary or crash message on the page. */
function pageErrors() {
  const text = document.body.innerText || "";
  return {
    boundary: !!document.querySelector(
      '[data-error-boundary], [data-slot="error-boundary"], .error-boundary',
    ),
    crash:
      /something went wrong|unexpected error|internal error|Uncaught|TypeError|is not a function/i.test(
        text,
      ),
    empty: text.trim().length === 0,
  };
}

/** Which page the window shows now: the roots drawn and the rail buttons
 * pressed. */
function pageNow() {
  const drawn = (sel: string) =>
    [...document.querySelectorAll(sel)].some(
      (e) => e.getClientRects().length > 0,
    );
  return {
    ledger: drawn("section.ledger-page"),
    profile: drawn("section.user-profile-page"),
    aeatSync: drawn("section.aeat-sync-page"),
    declarations: drawn("section.declarations-workspace"),
  };
}

// ---------------------------------------------------------------------------
// The judgement of one measured page.
// ---------------------------------------------------------------------------

const json = (value: unknown) => JSON.stringify(value);

interface Measure {
  page: string;
  size: readonly [number, number];
  root: string;
  options?: { pane?: string; header?: string };
  /** The popover's whole box must lie inside the window. */
  fitsWindow?: boolean;
}

/** Measure the page now drawn and assert what a person expects of it. */
async function measureAndJudge(target: Page, m: Measure) {
  const audit = await target.evaluate(paneAudit, {
    rootSel: m.root,
    options: m.options,
  });
  const errors = await target.evaluate(pageErrors);
  const geometry = await target.evaluate(pageGeometry);
  const at = `${m.page} at ${m.size[0]}x${m.size[1]}`;
  await test.info().attach(`measure ${at}`, {
    body: json({ audit, errors, geometry }),
    contentType: "application/json",
  });

  expect
    .soft(audit.found, `${at}: the page root ${m.root} is drawn`)
    .toBe(true);
  if (!audit.found) return;
  const [vw, vh] = audit.viewport!;
  expect
    .soft(
      errors.boundary || errors.crash || errors.empty,
      `${at}: an error boundary, crash text or an empty page is shown: ${json(errors)}`,
    )
    .toBe(false);

  // The header is drawn, inside its pane and the window. (Whether it holds a
  // heading is recorded in the measure, not judged: the Ledger's header is its
  // sections and period, not a title.)
  const header = audit.header;
  expect.soft(header, `${at}: the page header is drawn`).toBeTruthy();
  if (header) {
    expect
      .soft(
        header.inPane,
        `${at}: header box ${json(header.box)} lies inside the pane ${json(audit.paneBox)}`,
      )
      .toBe(true);
    expect
      .soft(
        header.box[0] >= -1 &&
          header.box[1] >= -1 &&
          header.box[2] <= vw + 1 &&
          header.box[3] <= vh + 1,
        `${at}: header box ${json(header.box)} lies inside the ${vw}x${vh} window`,
      )
      .toBe(true);
  }

  // The scrolling region keeps room to work.
  const scroller = audit.scroller;
  if (scroller) {
    expect
      .soft(
        scroller.clientHeight,
        `${at}: scroller ${scroller.el} is ${scroller.clientHeight}px high (scrollHeight ${scroller.scrollHeight}) in a ${audit.paneBox![3] - audit.paneBox![1]}px pane`,
      )
      .toBeGreaterThanOrEqual(SCROLLER_FLOOR);
  }

  // No overflow-hidden box cuts visible content off vertically.
  expect
    .soft(
      audit.clippedCount,
      `${at}: boxes that clip visible content: ${json(audit.clipped)}`,
    )
    .toBe(0);

  // The content stays inside its pane: its sides always, its bottom as well
  // (a tall root is scrolled to its end by the caller).
  const [rl, , rr, rb] = audit.rootBox!;
  const [pl, , pr, pb] = audit.paneBox!;
  expect
    .soft(
      rl >= pl - 1 && rr <= pr + 1 && rb <= pb + 1,
      `${at}: ${audit.root} box ${json(audit.rootBox)} overflows the pane ${json(audit.paneBox)}`,
    )
    .toBe(true);

  // The page fits the window: no scroll of the document, nothing shown that
  // lies outside the window or is cut off without a way to scroll to it.
  expect
    .soft(
      geometry.docScroll[0] <= vw + 1 && geometry.docScroll[1] <= vh + 1,
      `${at}: the document scrolls ${json(geometry.docScroll)} in a ${vw}x${vh} window`,
    )
    .toBe(true);
  expect
    .soft(
      geometry.unreachable,
      `${at}: controls or headings outside the window or cut off: ${json(geometry.unreachable.slice(0, 5))}`,
    )
    .toEqual([]);
  if (m.fitsWindow) {
    const [l, t, r, b] = audit.rootBox!;
    expect
      .soft(
        l >= -1 && t >= -1 && r <= vw + 1 && b <= vh + 1,
        `${at}: ${audit.root} box ${json(audit.rootBox)} does not fit the ${vw}x${vh} window`,
      )
      .toBe(true);
  }
}

// ---------------------------------------------------------------------------
// Reaching the pages in the scenario host.
// ---------------------------------------------------------------------------

test.beforeEach(async ({ page: target }) => {
  await target.addInitScript(() =>
    localStorage.removeItem("cadrumo-shell-layout"),
  );
});

const open = async (
  target: Page,
  size: readonly [number, number],
  scenario: string,
  extra = "",
) => {
  await target.setViewportSize({ width: size[0], height: size[1] });
  await target.goto(
    `/scenarios.html?scenario=${scenario}&latency=0&bar=off${extra}`,
  );
};

/** Press the rail button `id` and wait for the page root; a page the host
 * does not offer fails, naming why. */
async function openRailPage(target: Page, id: string, root: string) {
  const button = target.locator(`[data-rail=${id}]`);
  expect(
    await button.count(),
    `not reachable: no rail button [data-rail=${id}] in the scenario host`,
  ).toBeGreaterThan(0);
  expect(
    await button.getAttribute("aria-disabled"),
    `not reachable: rail button ${id} is held (aria-disabled)`,
  ).not.toBe("true");
  await button.click();
  await expect(
    target.locator(root).first(),
    `not reachable: ${root} not shown after pressing rail ${id}`,
  ).toBeVisible();
  // The page settles (its read, its first layout) before it is measured.
  await target.waitForTimeout(700);
}

const sizeName = (size: readonly [number, number]) => `${size[0]}x${size[1]}`;

// UX-08 ------------------------------------------------------------------

// The ids are the section tokens of the ledger's locale keys
// (desktop.ledger.section.<id>).
const LEDGER_TABS = ["movements", "invoices", "documents", "assets"];
const LEDGER_SETUP = ["rules", "registers", "health"];

for (const size of SIZES) {
  for (const id of [...LEDGER_TABS, ...LEDGER_SETUP]) {
    test(`UX-08 ledger/${id} keeps its header and scroller at ${sizeName(size)}`, async ({
      page: target,
    }) => {
      await open(target, size, "ledger");
      await openRailPage(target, "ledger", "section.ledger-page");
      const head = target.locator(".pane-docs .pane-head");
      if (LEDGER_SETUP.includes(id)) {
        await head
          .getByRole("button", {
            name: label("desktop.ledger.setup"),
            exact: true,
          })
          .click();
        await target
          .getByRole("menuitem", {
            name: label(`desktop.ledger.section.${id}`),
          })
          .click();
        await expect(
          head.getByRole("button", {
            name: label("desktop.ledger.setup_current", {
              section: label(`desktop.ledger.section.${id}`),
            }),
            exact: true,
          }),
          `not reachable: the setup button does not show ${id}`,
        ).toBeVisible();
      } else {
        const tab = head.getByRole("tab", {
          name: label(`desktop.ledger.section.${id}`),
        });
        expect(
          await tab.count(),
          `not reachable: no tab for the ${id} section`,
        ).toBeGreaterThan(0);
        await tab.click();
        await expect(
          tab,
          `not reachable: the ${id} tab is not selected`,
        ).toHaveAttribute("aria-selected", "true");
      }
      await target.waitForTimeout(700);
      await measureAndJudge(target, {
        page: `ledger/${id}`,
        size,
        root: "section.ledger-page",
      });
    });
  }
}

// UX-09 ------------------------------------------------------------------

for (const size of SIZES) {
  test(`UX-09 profile keeps its header and scroller at ${sizeName(size)}`, async ({
    page: target,
  }) => {
    await open(target, size, "user-profile");
    await openRailPage(target, "profile", "section.user-profile-page");
    await measureAndJudge(target, {
      page: "profile",
      size,
      root: "section.user-profile-page",
    });
  });
}

// UX-10 ------------------------------------------------------------------

for (const size of SIZES) {
  test(`UX-10 profile household stays inside the profile pane at ${sizeName(size)}`, async ({
    page: target,
  }) => {
    // The household the host serves at its cap shows the most it can.
    await open(target, size, "user-profile", "&household=at_cap");
    await openRailPage(target, "profile", "section.user-profile-page");
    await expect(
      target.locator("[data-household]"),
      "not reachable: no [data-household]: the profile has not loaded it, or a detail search is active",
    ).toBeVisible();
    await target
      .locator("[data-household]")
      .evaluate((element) => element.scrollIntoView({ block: "end" }));
    await target.waitForTimeout(700);
    await measureAndJudge(target, {
      page: "profile/household",
      size,
      root: "[data-household]",
      // The household sits under the profile's own header.
      options: { header: ".user-profile-page header" },
    });
  });
}

// UX-11 ------------------------------------------------------------------

for (const size of SIZES) {
  test(`UX-11 settings popover keeps its header and fits the window at ${sizeName(size)}`, async ({
    page: target,
  }) => {
    await open(target, size, "ledger");
    const button = target.locator("[data-rail=settings]");
    expect(
      await button.count(),
      "not reachable: no rail button [data-rail=settings]",
    ).toBeGreaterThan(0);
    await button.click();
    await expect(
      target.locator(".settings").first(),
      "not reachable: .settings not shown after pressing rail settings",
    ).toBeVisible();
    await target.waitForTimeout(700);
    await measureAndJudge(target, {
      page: "settings",
      size,
      root: ".settings",
      options: { header: ".settings h2" },
      fitsWindow: true,
    });
  });
}

// UX-12 ------------------------------------------------------------------

for (const size of SIZES) {
  test(`UX-12 AEAT sync keeps its header and scroller at ${sizeName(size)}`, async ({
    page: target,
  }) => {
    await open(target, size, "aeat-sync");
    await openRailPage(target, "aeat-sync", "section.aeat-sync-page");
    await measureAndJudge(target, {
      page: "aeat-sync",
      size,
      root: "section.aeat-sync-page",
    });
  });
}

// UX-13 ------------------------------------------------------------------

const PAGES = [
  ["ledger", "section.ledger-page", "ledger"],
  ["profile", "section.user-profile-page", "profile"],
  ["aeat-sync", "section.aeat-sync-page", "aeatSync"],
] as const;

type Shown = ReturnType<typeof pageNow>;

/** The one of the visited pages drawn now, or what is drawn instead. */
const shownPage = (now: Shown) =>
  PAGES.filter(([, , key]) => now[key]).map(([id]) => id);

for (const size of SIZES) {
  test(`UX-13 back and forward move between the pages visited at ${sizeName(size)}`, async ({
    page: target,
  }) => {
    await open(target, size, "ledger");
    for (const [id, root] of PAGES) await openRailPage(target, id, root);
    const at = sizeName(size);
    const now = async () => shownPage(await target.evaluate(pageNow));
    expect
      .soft(await now(), `${at}: after visiting the three pages`)
      .toEqual(["aeat-sync"]);

    // The window binds Alt+Left and Alt+Right off a field.
    const chord = async (key: string) => {
      await target.evaluate(() =>
        (document.activeElement as HTMLElement | null)?.blur?.(),
      );
      await target.keyboard.press(`Alt+${key}`);
    };
    // The shell binds the pointer's side buttons on the window's mouseup.
    const side = (button: number) =>
      target.evaluate((which) => {
        document.body.dispatchEvent(
          new MouseEvent("mouseup", {
            button: which,
            bubbles: true,
            cancelable: true,
          }),
        );
      }, button);
    const step = async (
      how: string,
      act: () => Promise<unknown>,
      expected: string[],
    ) => {
      await act();
      await target.waitForTimeout(1000);
      const after = await now();
      expect
        .soft(after, `${at}: after ${how}, the page shown`)
        .toEqual(expected);
    };
    await step("Alt+ArrowLeft", () => chord("ArrowLeft"), ["profile"]);
    await step("Alt+ArrowLeft again", () => chord("ArrowLeft"), ["ledger"]);
    await step("Alt+ArrowRight", () => chord("ArrowRight"), ["profile"]);
    await step("pointer back button", () => side(3), ["ledger"]);
    await step("pointer forward button", () => side(4), ["profile"]);
  });
}
