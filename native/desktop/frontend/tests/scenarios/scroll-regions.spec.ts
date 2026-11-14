import { expect, test, type Page } from "@playwright/test";

// Every area that scrolls can be scrolled with the mouse alone. The window's
// scrollbars are one rule (src/styles/base.css): a classic bar that takes
// layout room, so it is drawn without the pointer over it, with a thumb that
// never shrinks below a length that can be grabbed and that holds 3:1 against
// the surface. This guard measures that rule on the rendered pages, at the
// four window sizes the audits use, without trusting the rule's own words:
// it scans every element that really overflows with auto or scroll, and for
// each asserts the bar is drawn, the thumb has length, a wheel moves it and
// (once per run) that the thumb colour holds its contrast in light and dark.
//
// Chromium is launched with its scrollbars (the harness hides them by
// default), so the bars exist to be measured.

test.use({
  actionTimeout: 4000,
  launchOptions: { ignoreDefaultArgs: ["--hide-scrollbars"] },
});

const SIZES = [
  [1441, 923],
  [1280, 800],
  [1024, 640],
  [900, 600],
] as const;

/** The thickness the bar must at least have, in layout pixels. */
const MIN_BAR = 10;
/** The shortest thumb a person can grab, in pixels. */
const MIN_THUMB = 28;
/** WCAG 1.4.11: a user interface component against its surroundings. */
const MIN_CONTRAST = 3;

/**
 * Scrollers that still break a check, each with the file that owns the fix.
 * An entry is removed when its file is changed; the guard fails on a stale
 * entry (one that matched nothing), so this list cannot outlive its reason.
 */
const ALLOWED: {
  /** A part of the scroller's described selector. */
  selector: string;
  /** The check it is excused from. */
  check: "thumb" | "wheel" | "bar";
  reason: string;
}[] = [];

// ---------------------------------------------------------------------------
// The scan, as it runs in the page.
// ---------------------------------------------------------------------------

interface ScrollerRow {
  sel: string;
  clientH: number;
  scrollH: number;
  clientW: number;
  scrollW: number;
  overflowX: string;
  overflowY: string;
  /** Layout thickness of the vertical and horizontal bar, borders excluded. */
  barV: number;
  barH: number;
  /** The CSS minimum of the thumb, in pixels, as the browser resolves it. */
  thumbMinH: number;
  thumbMinW: number;
  /** Whether a wheel over the scroller moved it: null when no point of it
   * belongs to it alone (covered, or only its children scroll there). */
  wheelY: number | null;
  wheelX: number | null;
}

/** Every shown element that scrolls with auto or scroll and overflows. */
function scanScrollers(): Omit<ScrollerRow, "wheelY" | "wheelX">[] {
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
  const px = (v: string) => parseFloat(v) || 0;
  const one = (e: Element) => {
    const cls = typeof e.className === "string" ? e.className : "";
    const classes = cls.split(/\s+/).filter(Boolean).slice(0, 3).join(".");
    const role = e.getAttribute("role");
    return `${e.tagName.toLowerCase()}${e.id ? "#" + e.id : ""}${
      classes ? "." + classes : ""
    }${role ? `[role=${role}]` : ""}`;
  };
  const rows: Omit<ScrollerRow, "wheelY" | "wheelX">[] = [];
  let n = 0;
  for (const el of document.querySelectorAll<HTMLElement>("*")) {
    const cs = getComputedStyle(el);
    const scrollsX = cs.overflowX === "auto" || cs.overflowX === "scroll";
    const scrollsY = cs.overflowY === "auto" || cs.overflowY === "scroll";
    if (!scrollsX && !scrollsY) continue;
    if (!shown(el)) continue;
    const overY = el.scrollHeight - el.clientHeight;
    const overX = el.scrollWidth - el.clientWidth;
    if (!((scrollsY && overY > 1) || (scrollsX && overX > 1))) continue;
    const parent = el.parentElement;
    const label = parent ? `${one(parent)} > ${one(el)}` : one(el);
    const thumb = getComputedStyle(el, "::-webkit-scrollbar-thumb");
    el.setAttribute("data-scroll-guard", String(n));
    rows.push({
      sel: label,
      clientH: el.clientHeight,
      scrollH: el.scrollHeight,
      clientW: el.clientWidth,
      scrollW: el.scrollWidth,
      overflowX: cs.overflowX,
      overflowY: cs.overflowY,
      barV:
        el.offsetWidth -
        el.clientWidth -
        px(cs.borderLeftWidth) -
        px(cs.borderRightWidth),
      barH:
        el.offsetHeight -
        el.clientHeight -
        px(cs.borderTopWidth) -
        px(cs.borderBottomWidth),
      thumbMinH: px(thumb.minHeight),
      thumbMinW: px(thumb.minWidth),
    });
    n += 1;
  }
  return rows;
}

/** Roll a wheel over one tagged scroller, at a point only it owns. */
async function wheelOver(
  page: Page,
  index: number,
  vertical: boolean,
): Promise<number | null> {
  const point = await page.evaluate(
    ({ index, vertical }) => {
      const el = document.querySelector<HTMLElement>(
        `[data-scroll-guard="${index}"]`,
      );
      if (!el) return null;
      el.scrollTop = 0;
      el.scrollLeft = 0;
      const r = el.getBoundingClientRect();
      const x0 = Math.max(r.left, 0);
      const x1 = Math.min(r.left + el.clientWidth, innerWidth);
      const y0 = Math.max(r.top, 0);
      const y1 = Math.min(r.top + el.clientHeight, innerHeight);
      if (x1 - x0 < 4 || y1 - y0 < 4) return null;
      // The scroller a wheel at this point would move first.
      const owner = (from: Element | null) => {
        for (let p = from; p; p = p.parentElement) {
          const cs = getComputedStyle(p);
          const o = vertical ? cs.overflowY : cs.overflowX;
          const over = vertical
            ? p.scrollHeight - p.clientHeight
            : p.scrollWidth - p.clientWidth;
          if ((o === "auto" || o === "scroll") && over > 1) return p;
        }
        return null;
      };
      for (const fy of [0.5, 0.25, 0.75, 0.1, 0.9])
        for (const fx of [0.5, 0.2, 0.8, 0.35, 0.65, 0.05, 0.95]) {
          const x = x0 + (x1 - x0) * fx;
          const y = y0 + (y1 - y0) * fy;
          const top = document.elementFromPoint(x, y);
          if (top && el.contains(top) && owner(top) === el) return [x, y];
        }
      return null;
    },
    { index, vertical },
  );
  if (!point) return null;
  const [pointX = 0, pointY = 0] = point;
  await page.mouse.move(pointX, pointY);
  await page.mouse.wheel(vertical ? 0 : 240, vertical ? 240 : 0);
  await page.waitForTimeout(140);
  return page.evaluate(
    ({ index, vertical }) => {
      const el = document.querySelector<HTMLElement>(
        `[data-scroll-guard="${index}"]`,
      );
      if (!el) return null;
      const moved = vertical ? el.scrollTop : el.scrollLeft;
      el.scrollTop = 0;
      el.scrollLeft = 0;
      return moved;
    },
    { index, vertical },
  );
}

// ---------------------------------------------------------------------------
// The checker: pure, so the guard can be shown to catch a defect.
// ---------------------------------------------------------------------------

type Check = "bar" | "thumb" | "wheel";

/** What is wrong with one scroller, by check. */
function violations(row: ScrollerRow): { check: Check; why: string }[] {
  const out: { check: Check; why: string }[] = [];
  const scrollsY =
    (row.overflowY === "auto" || row.overflowY === "scroll") &&
    row.scrollH - row.clientH > 1;
  const scrollsX =
    (row.overflowX === "auto" || row.overflowX === "scroll") &&
    row.scrollW - row.clientW > 1;
  if (scrollsY) {
    if (row.barV < MIN_BAR)
      out.push({
        check: "bar",
        why: `vertical bar ${row.barV}px takes no layout room (needs ${MIN_BAR})`,
      });
    const drawn = Math.max(
      (row.clientH * row.clientH) / row.scrollH,
      row.thumbMinH,
    );
    if (drawn < MIN_THUMB)
      out.push({
        check: "thumb",
        why: `vertical thumb ${drawn.toFixed(1)}px in ${row.clientH}x${row.scrollH} (needs ${MIN_THUMB})`,
      });
    if (row.wheelY === 0)
      out.push({ check: "wheel", why: "a wheel does not move it down" });
  }
  if (scrollsX) {
    if (row.barH < MIN_BAR)
      out.push({
        check: "bar",
        why: `horizontal bar ${row.barH}px takes no layout room (needs ${MIN_BAR})`,
      });
    const drawn = Math.max(
      (row.clientW * row.clientW) / row.scrollW,
      row.thumbMinW,
    );
    if (drawn < MIN_THUMB)
      out.push({
        check: "thumb",
        why: `horizontal thumb ${drawn.toFixed(1)}px in ${row.clientW}x${row.scrollW} (needs ${MIN_THUMB})`,
      });
    if (row.wheelX === 0 && !scrollsY)
      out.push({ check: "wheel", why: "a wheel does not move it sideways" });
  }
  return out;
}

const used = new Set<number>();

/** Scan the page now and assert every scroller; `where` names the state. */
async function audit(page: Page, where: string) {
  const rows = await page.evaluate(scanScrollers);
  const seen = new Set<string>();
  for (const [index, found] of rows.entries()) {
    const key = `${found.sel}|${found.scrollH}|${found.scrollW}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const row: ScrollerRow = { ...found, wheelY: null, wheelX: null };
    if (found.scrollH - found.clientH > 1)
      row.wheelY = await wheelOver(page, index, true);
    if (found.scrollW - found.clientW > 1)
      row.wheelX = await wheelOver(page, index, false);
    for (const bad of violations(row)) {
      const excuse = ALLOWED.findIndex(
        (a) => a.check === bad.check && row.sel.includes(a.selector),
      );
      if (excuse >= 0) {
        used.add(excuse);
        continue;
      }
      expect.soft(false, `${where}: ${row.sel}: ${bad.why}`).toBe(true);
    }
  }
  return rows.length;
}

// ---------------------------------------------------------------------------
// Pages.
// ---------------------------------------------------------------------------

const settle = (page: Page, ms = 500) => page.waitForTimeout(ms);

async function open(
  page: Page,
  size: readonly [number, number],
  scenario: string,
  extra = "",
) {
  await page.setViewportSize({ width: size[0], height: size[1] });
  await page.goto(
    `/scenarios.html?scenario=${scenario}&latency=0&bar=off${extra}`,
  );
  await settle(page, 700);
}

/** A page the host offers: its rail button, else the test says why not. */
async function goTo(page: Page, rail: string) {
  const button = page.locator(`[data-rail=${rail}]`);
  expect(
    await button.count(),
    `not reachable: no rail button [data-rail=${rail}] in the scenario host`,
  ).toBeGreaterThan(0);
  await button.click();
  await settle(page, 800);
}

/** Audit the page, then once per tab of the tablists under `root`. */
async function auditTabs(page: Page, name: string, root: string) {
  let scanned = await audit(page, name);
  const tabs = page.locator(`${root} [role=tab]`);
  const count = await tabs.count();
  for (let i = 0; i < count; i += 1) {
    const tab = tabs.nth(i);
    if (!(await tab.isVisible())) continue;
    const tabName = ((await tab.innerText().catch(() => "")) || `tab ${i}`)
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 24);
    try {
      await tab.click({ timeout: 3000 });
    } catch {
      continue;
    }
    await settle(page, 450);
    scanned += await audit(page, `${name} / ${tabName}`);
  }
  return scanned;
}

test.describe.configure({ mode: "serial" });

for (const size of SIZES) {
  const tag = `${size[0]}x${size[1]}`;

  test(`profile and household scroll with the mouse at ${tag}`, async ({
    page,
  }) => {
    test.setTimeout(240000);
    await open(page, size, "user-profile", "&household=at_cap");
    await goTo(page, "profile");
    await page.locator("section.user-profile-page").first().waitFor();
    await settle(page, 700);
    let scanned = await audit(page, `profile ${tag}`);
    await page
      .locator("[data-household]")
      .evaluate((e) => e.scrollIntoView({ block: "end" }))
      .catch(() => {});
    await settle(page, 300);
    scanned += await audit(page, `profile household ${tag}`);
    expect(scanned, "the profile page has scrollers to guard").toBeGreaterThan(
      0,
    );

    // The worst case, measured in pixels rather than from the rule: the
    // profile's body is thousands of pixels long in a short pane, and its
    // thumb is drawn with the shortest length the rule allows.
    const body = page.locator(
      "section.user-profile-page [role=group][tabindex='0']",
    );
    await expect(body).toHaveCount(1);
    const drawn = await thumbLength(page, body);
    test.info().annotations.push({
      type: "measured",
      description: `${scanned} scrollers audited; profile body thumb ${drawn}px`,
    });
    expect(
      drawn,
      `profile body thumb drawn length at ${tag}`,
    ).toBeGreaterThanOrEqual(MIN_THUMB);
  });

  test(`declarations and the Modelo views scroll with the mouse at ${tag}`, async ({
    page,
  }) => {
    test.setTimeout(240000);
    await open(page, size, "ledger");
    await goTo(page, "declarations");
    let scanned = await audit(page, `declarations ${tag}`);
    const create = page.locator(".declarations-page .declarations-new");
    if (await create.count()) {
      await create.click();
      await settle(page, 500);
      scanned += await audit(page, `new declaration dialog ${tag}`);
      await page.keyboard.press("Escape");
      await settle(page, 300);
    }
    const grid = page
      .locator(".declarations-page")
      .getByRole("grid")
      .locator("[data-kind=data]")
      .filter({ hasText: "Modelo 130" })
      .first();
    expect(
      await grid.count(),
      "not reachable: no Modelo 130 row in the declarations list",
    ).toBeGreaterThan(0);
    await grid.dblclick();
    await page
      .locator("section.declarations-workspace")
      .getByRole("heading", { level: 1 })
      .waitFor();
    await settle(page, 800);
    scanned += await auditTabs(
      page,
      `modelo ${tag}`,
      "section.declarations-workspace",
    );
    expect(scanned).toBeGreaterThan(0);
  });

  test(`ledger sections scroll with the mouse at ${tag}`, async ({ page }) => {
    test.setTimeout(240000);
    await open(page, size, "ledger");
    await goTo(page, "ledger");
    await page.locator("section.ledger-page").first().waitFor();
    await settle(page, 700);
    const head = page.locator(".pane-docs .pane-head");
    const tabs = head.getByRole("tab");
    const count = await tabs.count();
    expect(count, "the ledger offers its sections").toBeGreaterThan(0);
    let scanned = await audit(page, `ledger ${tag}`);
    for (let i = 0; i < count; i += 1) {
      const name = (
        (await tabs
          .nth(i)
          .innerText()
          .catch(() => "")) || `tab ${i}`
      )
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 20);
      await tabs.nth(i).click({ timeout: 3000 });
      await settle(page, 600);
      scanned += await audit(page, `ledger ${name} ${tag}`);
      const row = page
        .locator("section.ledger-page [role=grid] [data-kind=data]")
        .first();
      if (await row.count()) {
        await row.click({ timeout: 2000 }).catch(() => {});
        await settle(page, 500);
        scanned += await audit(page, `ledger ${name} with a row ${tag}`);
      }
    }
    expect(scanned).toBeGreaterThan(0);
  });

  test(`calendar and AEAT sync scroll with the mouse at ${tag}`, async ({
    page,
  }) => {
    test.setTimeout(240000);
    await open(page, size, "ledger");
    await goTo(page, "calendar");
    await audit(page, `calendar ${tag}`);
    await open(page, size, "aeat-sync");
    await goTo(page, "aeat-sync");
    await page.locator("section.aeat-sync-page").first().waitFor();
    await auditTabs(page, `aeat sync ${tag}`, "section.aeat-sync-page");
  });
}

// ---------------------------------------------------------------------------
// The thumb, in pixels.
// ---------------------------------------------------------------------------

/**
 * The length of the drawn thumb of a vertical scroller: the run of pixels in
 * the middle of its bar that differ from the track. The page is photographed
 * and the bar's column read back in the page, so no decoder is needed.
 */
async function thumbLength(
  page: Page,
  scroller: ReturnType<Page["locator"]>,
): Promise<number> {
  const box = await scroller.evaluate((el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    const bar = el.offsetWidth - el.clientWidth;
    return { x: r.right - bar / 2, y: r.top, h: el.clientHeight, bar };
  });
  expect(box.bar, "the bar takes layout room").toBeGreaterThanOrEqual(MIN_BAR);
  const shot = await page.screenshot({
    clip: {
      x: Math.floor(box.x),
      y: Math.ceil(box.y),
      width: 1,
      height: box.h,
    },
  });
  return page.evaluate(async (base64) => {
    const image = new Image();
    image.src = `data:image/png;base64,${base64}`;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext("2d")!;
    context.drawImage(image, 0, 0);
    const data = context.getImageData(0, 0, image.width, image.height).data;
    const at = (y: number): [number, number, number] => [
      data[y * 4] ?? 0,
      data[y * 4 + 1] ?? 0,
      data[y * 4 + 2] ?? 0,
    ];
    // The thumb starts at the top at scroll 0; the track is read from the
    // pixel at the bottom of the bar, past the thumb.
    const track = at(image.height - 1);
    let length = 0;
    for (let y = 0; y < image.height; y += 1) {
      const p = at(y);
      const same =
        Math.abs(p[0] - track[0]) +
          Math.abs(p[1] - track[1]) +
          Math.abs(p[2] - track[2]) <
        12;
      if (same && length > 0) break;
      if (!same) length += 1;
    }
    return length;
  }, shot.toString("base64"));
}

// ---------------------------------------------------------------------------
// Contrast of the thumb, in light and dark.
// ---------------------------------------------------------------------------

type Rgb = [number, number, number];

function luminance([r, g, b]: Rgb) {
  const lin = (v: number) => {
    const s = v / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(a: Rgb, b: Rgb) {
  const [x, y] = [luminance(a), luminance(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

test("the thumb holds 3:1 against its track and surfaces in light and dark", async ({
  page,
}) => {
  await open(page, SIZES[1], "ledger");
  const colours = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const context = canvas.getContext("2d", { willReadFrequently: true })!;
    const rgb = (value: string): [number, number, number] => {
      context.clearRect(0, 0, 1, 1);
      context.fillStyle = "#000";
      context.fillStyle = value;
      context.fillRect(0, 0, 1, 1);
      const [r = 0, g = 0, b = 0] = context.getImageData(0, 0, 1, 1).data;
      return [r, g, b];
    };
    const out: Record<string, Record<string, [number, number, number]>> = {};
    for (const scheme of ["light", "dark"]) {
      const probe = document.createElement("div");
      probe.setAttribute("data-scheme", scheme);
      document.body.append(probe);
      const read = (token: string) => {
        probe.style.background = `var(${token})`;
        return rgb(getComputedStyle(probe).backgroundColor);
      };
      out[scheme] = {
        thumb: read("--scrollbar-thumb"),
        hover: read("--scrollbar-thumb-hover"),
        active: read("--scrollbar-thumb-active"),
        track: read("--scrollbar-track"),
        background: read("--background"),
        chrome: read("--chrome"),
        card: read("--card"),
      };
      probe.remove();
    }
    return out;
  });
  for (const scheme of ["light", "dark"]) {
    const c = colours[scheme];
    if (!c) throw new Error(`no colours for ${scheme}`);
    for (const against of ["track", "background", "chrome", "card"] as const) {
      for (const part of ["thumb", "hover", "active"] as const) {
        expect
          .soft(
            contrast(c[part]!, c[against]!),
            `${scheme}: ${part} against ${against}`,
          )
          .toBeGreaterThanOrEqual(MIN_CONTRAST);
      }
    }
  }
});

// ---------------------------------------------------------------------------
// The guard catches a defect.
// ---------------------------------------------------------------------------

test("the checker reports a scroller whose bar is hidden and passes a plain one", async ({
  page,
}) => {
  await open(page, SIZES[1], "ledger");
  const rows = await page.evaluate(() => {
    const make = (name: string, style: string) => {
      const box = document.createElement("div");
      box.id = name;
      box.style.cssText = `position:fixed;left:8px;top:8px;width:200px;height:120px;overflow:auto;z-index:2147483647;${style}`;
      const inner = document.createElement("div");
      inner.style.cssText = "height:900px;width:100px";
      box.append(inner);
      document.body.append(box);
      return box;
    };
    const plain = make("guard-plain", "");
    const rows: Record<string, unknown> = {};
    const read = (el: HTMLElement) =>
      ({
        clientH: el.clientHeight,
        scrollH: el.scrollHeight,
        clientW: el.clientWidth,
        scrollW: el.scrollWidth,
        overflowX: getComputedStyle(el).overflowX,
        overflowY: getComputedStyle(el).overflowY,
        barV: el.offsetWidth - el.clientWidth,
        barH: el.offsetHeight - el.clientHeight,
        thumbMinH: parseFloat(
          getComputedStyle(el, "::-webkit-scrollbar-thumb").minHeight,
        ),
        thumbMinW: 0,
      }) as const;
    rows.plain = read(plain);
    plain.remove();
    const hidden = make("guard-hidden", "scrollbar-width:none");
    rows.hidden = read(hidden);
    hidden.remove();
    // Its own thin bar: classic, but 4px wide.
    const style = document.createElement("style");
    style.textContent =
      "#guard-thin::-webkit-scrollbar{width:4px;height:4px}#guard-thin::-webkit-scrollbar-thumb{min-height:0}";
    document.head.append(style);
    const thin = make("guard-thin", "");
    rows.thin = read(thin);
    thin.remove();
    style.remove();
    return rows;
  });
  const row = (key: string): ScrollerRow => ({
    sel: `fixture ${key}`,
    wheelY: null,
    wheelX: null,
    ...(rows[key] as Omit<ScrollerRow, "sel" | "wheelY" | "wheelX">),
  });
  expect(
    violations(row("plain")),
    "a plain scroller takes the shared rule",
  ).toEqual([]);
  expect(
    violations(row("hidden")).map((v) => v.check),
    "scrollbar-width:none hides the bar",
  ).toContain("bar");
  expect(
    violations(row("thin")).map((v) => v.check),
    "a 4px bar is too thin",
  ).toContain("bar");
  expect(
    violations({ ...row("plain"), wheelY: 0 }).map((v) => v.check),
    "a wheel that moves nothing",
  ).toContain("wheel");
  expect(
    violations({
      ...row("plain"),
      clientH: 5,
      scrollH: 90000,
      thumbMinH: 0,
    }).map((v) => v.check),
    "a thumb with no minimum on a long page",
  ).toContain("thumb");
});

test("the allow-list holds nothing that no longer applies", () => {
  for (const [index, entry] of ALLOWED.entries())
    expect(used.has(index), `stale: ${entry.selector} (${entry.reason})`).toBe(
      true,
    );
});
