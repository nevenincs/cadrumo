// Measures the shell: bundle size, start-up, memory, and the interactions
// that can cost the most (a ten-thousand-record log, the palette, a splitter
// drag, overlays opened and closed many times).
//
// Bundle size is the product build's. Everything timed runs on a minified
// build of the scenario page, which is the product's own code over the
// scenario host: no desktop host, runtime or real terminal is in it. It is
// served as static files and driven in Chromium, and the numbers go under
// the build directory's test results.
//
// Times are taken to the next frame, so they come in steps of a frame. The
// numbers describe this machine: compare runs, not hosts. `--check` fails
// the run when a number is over its budget; the budgets are loose on purpose
// and catch a regression of kind, not of degree.
import { chromium } from "@playwright/test";
import { spawnSync } from "node:child_process";
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { gzipSync } from "node:zlib";
import { preview } from "vite";
import { buildPath } from "../../scripts/build-paths.mjs";
import { label } from "../tests/support/strings.ts";

const frontend = fileURLToPath(new URL("..", import.meta.url));
const { values } = parseArgs({
  options: {
    records: { type: "string", default: "10000" },
    runs: { type: "string", default: "5" },
    check: { type: "boolean", default: false },
  },
});
const RECORDS = Number(values.records);
const RUNS = Number(values.runs);

function vite(...args) {
  const result = spawnSync(
    process.execPath,
    [
      resolve(frontend, "node_modules/vite/bin/vite.js"),
      ...args,
      "--configLoader",
      "runner",
    ],
    { cwd: frontend, stdio: ["ignore", "ignore", "inherit"] },
  );
  if (result.status !== 0) throw new Error(`vite ${args.join(" ")} failed`);
}

/** The bytes of everything a build emitted, raw and gzipped, by kind: the
 * entry's own files and every chunk and font it can go on to load. */
function bundle(directory) {
  const sizes = {};
  for (const name of readdirSync(directory, { recursive: true })) {
    const kind = extname(name).slice(1);
    if (!kind) continue;
    const bytes = readFileSync(join(directory, name));
    sizes[kind] ??= { raw: 0, gzip: 0 };
    sizes[kind].raw += bytes.length;
    sizes[kind].gzip += gzipSync(bytes).length;
  }
  if (!sizes.js || !sizes.css)
    throw new Error(`No script or stylesheet was built into ${directory}.`);
  return sizes;
}

const median = (list) => {
  const sorted = [...list].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
};
const percentile = (list, p) => {
  const sorted = [...list].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))];
};
const round = (value, places = 1) => Number(value.toFixed(places));

async function metrics(client) {
  // Twice, with a pause between: what the first collection frees can hold
  // the last references to nodes, which the second then lets go.
  await client.send("HeapProfiler.collectGarbage");
  await new Promise((done) => setTimeout(done, 250));
  await client.send("HeapProfiler.collectGarbage");
  const { metrics: list } = await client.send("Performance.getMetrics");
  const of = (name) => list.find((metric) => metric.name === name)?.value ?? 0;
  return {
    heapMB: round(of("JSHeapUsedSize") / 1048576),
    nodes: of("Nodes"),
    listeners: of("JSEventListeners"),
  };
}

/** Frame intervals, in milliseconds, while `action` runs in the page. */
async function frames(page, action) {
  await page.evaluate(() => {
    window.__frames = [];
    let last = performance.now();
    const tick = (now) => {
      window.__frames.push(now - last);
      last = now;
      window.__framing = requestAnimationFrame(tick);
    };
    window.__framing = requestAnimationFrame(tick);
  });
  await action();
  return page.evaluate(() => {
    cancelAnimationFrame(window.__framing);
    return window.__frames;
  });
}

vite("build");
vite("build", "--mode", "scenarios");
const product = buildPath("desktop_frontend");
let server;
let browser;
const report = {
  at: new Date().toISOString(),
  setup: "Docs beside TUI, console panel open; isolated scenario context",
  bundle: { product: bundle(product) },
};
const stage = (name) => {
  report.stage = name;
  console.log(`Measuring ${name}`);
};

async function measuredShellContext() {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  context.on("page", (page) => {
    page.on("pageerror", (error) =>
      console.error(`Benchmark page error: ${error}`),
    );
    page.on("console", (message) => {
      if (message.type() === "error")
        console.error(`Benchmark console error: ${message.text()}`);
    });
  });
  await context.addInitScript(() => {
    if (window !== window.top) return;
    if (!["http:", "https:"].includes(location.protocol)) return;
    if (sessionStorage.getItem("benchmark-layout-seeded")) return;
    localStorage.setItem(
      "cadrumo-shell-layout",
      JSON.stringify({
        prefs: { order: "docs" },
        layout: {
          agentShown: false,
          docsShown: true,
          tuiShown: true,
          page: "docs",
          panelOpen: true,
          tab: "console",
        },
      }),
    );
    sessionStorage.setItem("benchmark-layout-seeded", "1");
  });
  return context;
}

async function dockDivider(page) {
  const separator = page.locator(
    '[data-dock-divider][aria-orientation="vertical"]:visible',
  );
  await separator.first().waitFor();
  if ((await separator.count()) !== 1)
    throw new Error("Expected the single Docs/TUI divider.");
  const handle = await separator.boundingBox();
  if (!handle) throw new Error("The dock divider has no visible bounds.");
  return {
    separator,
    x: handle.x + handle.width / 2,
    y: handle.y + handle.height / 2,
    horizontalMotion:
      (await separator.getAttribute("aria-orientation")) === "vertical",
  };
}

/** One frame in the page, so what was just done has been drawn. */
const nextFrame = (page) =>
  page.evaluate(() => new Promise((done) => requestAnimationFrame(done)));

try {
  // The scenario preview owns the documentation fixture and injects its port.
  // A plain static server would measure a failed Docs pane instead.
  server = await preview({
    root: frontend,
    configLoader: "runner",
    mode: "scenarios",
  });
  const address = server.httpServer.address();
  if (!address || typeof address === "string")
    throw new Error("The benchmark preview has no TCP address.");
  const origin = `http://127.0.0.1:${address.port}`;
  browser = await chromium.launch();
  stage("startup");
  // Start-up of the explicitly opened shell surfaces, with a fresh context.
  const start = [];
  for (let run = 0; run < RUNS; run++) {
    const context = await measuredShellContext();
    const page = await context.newPage();
    // The page notes for itself when its terminals have drawn, so the time
    // carries none of this script's own polling.
    await page.addInitScript(() => {
      const seen = new MutationObserver(() => {
        if (!document.querySelector('[data-terminal="console"] .xterm-screen'))
          return;
        seen.disconnect();
        requestAnimationFrame(() => {
          window.__terminalsReady = performance.now();
        });
      });
      seen.observe(document, { childList: true, subtree: true });
    });
    await page.goto(`${origin}/scenarios.html?scenario=signed-in&bar=off`);
    await page.waitForFunction(() => window.__terminalsReady !== undefined);
    start.push(
      await page.evaluate(() => {
        const [navigation] = performance.getEntriesByType("navigation");
        const paint = performance
          .getEntriesByType("paint")
          .find((entry) => entry.name === "first-contentful-paint");
        return {
          domContentLoaded: navigation.domContentLoadedEventEnd,
          firstContentfulPaint: paint?.startTime ?? 0,
          terminalsReady: window.__terminalsReady,
        };
      }),
    );
    await context.close();
  }
  report.startMs = {
    domContentLoaded: round(median(start.map((s) => s.domContentLoaded))),
    firstContentfulPaint: round(
      median(start.map((s) => s.firstContentfulPaint)),
    ),
    terminalsReady: round(median(start.map((s) => s.terminalsReady))),
  };

  const context = await measuredShellContext();
  const page = await context.newPage();
  const client = await context.newCDPSession(page);
  await client.send("Performance.enable");

  // Idle shell with Docs, TUI and the console explicitly open.
  await page.goto(`${origin}/scenarios.html?scenario=signed-in&bar=off`);
  await page.waitForSelector('[data-terminal="console"] .xterm-screen');
  await page.frameLocator(".docs-frame").locator("body").waitFor();
  await page.waitForTimeout(500);
  report.idle = await metrics(client);

  // The palette: from the chord to the dialog being on screen.
  stage("palette");
  const palette = [];
  for (let run = 0; run < RUNS * 2; run++) {
    const opened = await page.evaluate(
      () =>
        new Promise((done) => {
          const started = performance.now();
          const seen = new MutationObserver(() => {
            if (!document.querySelector(".palette")) return;
            seen.disconnect();
            requestAnimationFrame(() => done(performance.now() - started));
          });
          seen.observe(document.body, { childList: true, subtree: true });
          window.dispatchEvent(
            new KeyboardEvent("keydown", {
              code: "KeyK",
              key: "K",
              ctrlKey: true,
              shiftKey: true,
              bubbles: true,
            }),
          );
        }),
    );
    palette.push(opened);
    await page.keyboard.press("Escape");
    await page.waitForSelector(".palette", { state: "detached" });
  }
  report.paletteOpenMs = {
    median: round(median(palette)),
    p95: round(percentile(palette, 0.95)),
  };

  // Overlays opened and closed many times: what is left behind after the
  // first rounds must not keep growing. Locators, not element handles, so
  // this script holds on to nothing in the page.
  stage("overlay retention");
  const churn = async (count) => {
    for (let run = 0; run < count; run++) {
      await page.keyboard.press("Control+Shift+KeyK");
      await page.locator(".palette").waitFor();
      await page.keyboard.press("Escape");
      await page.locator(".palette").waitFor({ state: "detached" });
      await page.keyboard.press("Control+Comma");
      await page.locator(".settings").waitFor();
      // Settings takes focus a moment after it is in the document; a key
      // pressed before that is not pressed in it.
      await page.waitForFunction(
        () => document.activeElement?.closest(".settings") != null,
      );
      await page.keyboard.press("Escape");
      await page.locator(".settings").waitFor({ state: "detached" });
    }
    return metrics(client);
  };
  await page.locator(".rail button").first().focus();
  const settled = await churn(10);
  const later = await churn(40);
  report.overlayChurn = {
    cycles: 40,
    settled,
    later,
    nodesGrown: later.nodes - settled.nodes,
    listenersGrown: later.listeners - settled.listeners,
  };

  // A splitter drag across the main area, one pointer move to a frame, as a
  // hand moves it.
  stage("dock resizing");
  const { separator, x, y, horizontalMotion } = await dockDivider(page);
  const before = await separator.getAttribute("aria-valuenow");
  const drag = await frames(page, async () => {
    await page.mouse.move(x, y);
    await page.mouse.down();
    for (let step = 0; step <= 60; step++) {
      const offset = -300 + step * 10;
      await page.mouse.move(
        x + (horizontalMotion ? offset : 0),
        y + (horizontalMotion ? 0 : offset),
      );
      await nextFrame(page);
    }
    await page.mouse.up();
  });
  if ((await separator.getAttribute("aria-valuenow")) === before)
    throw new Error("The splitter drag did not move the split.");
  report.splitDragFrameMs = {
    median: round(median(drag)),
    p95: round(percentile(drag, 0.95)),
    worst: round(Math.max(...drag)),
  };

  // The log view under the largest log the host keeps.
  stage("logs");
  await page.goto(
    `${origin}/scenarios.html?scenario=signed-in&bar=off&records=${RECORDS}`,
  );
  await page.waitForSelector('[data-terminal="console"] .xterm-screen');
  const shown = await page.evaluate(
    () =>
      new Promise((done) => {
        const started = performance.now();
        document.getElementById("tab-logs").click();
        const wait = () =>
          document.querySelector(".logview-list .record")
            ? requestAnimationFrame(() => done(performance.now() - started))
            : requestAnimationFrame(wait);
        wait();
      }),
  );
  await page
    .getByRole("button", { name: label("desktop.logs.filters"), exact: true })
    .click();
  await page
    .getByLabel(label("desktop.logs.minimum_level"), { exact: true })
    .selectOption("0");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  const drawn = await page.locator(".logview-list .record").count();
  // The filter is timed from the newest span, before any scrolling has
  // brought earlier ones in.
  const filter = await page.evaluate(
    () =>
      new Promise((done) => {
        const input = document.querySelector(".filter-text");
        const started = performance.now();
        const setter = Object.getOwnPropertyDescriptor(
          HTMLInputElement.prototype,
          "value",
        ).set;
        setter.call(input, "record 99");
        input.dispatchEvent(new Event("input", { bubbles: true }));
        requestAnimationFrame(() => done(performance.now() - started));
      }),
  );
  await page.fill(".filter-text", "");
  await page.waitForTimeout(300);
  const scroll = await frames(page, () =>
    page.evaluate(
      () =>
        new Promise((done) => {
          const list = document.querySelector(".logview-list");
          const started = performance.now();
          // Upward a screen at a time for two seconds, as a held Page Up
          // scrolls, so earlier spans are brought in on the way.
          const step = (now) => {
            list.scrollTop -= list.clientHeight;
            if (now - started < 2000) requestAnimationFrame(step);
            else done();
          };
          requestAnimationFrame(step);
        }),
    ),
  );
  report.log = {
    records: RECORDS,
    drawnAtFirst: drawn,
    drawnAfterScroll: await page.locator(".logview-list .record").count(),
    firstRowsMs: round(shown),
    scrollFrameMs: {
      median: round(median(scroll)),
      p95: round(percentile(scroll, 0.95)),
      worst: round(Math.max(...scroll)),
    },
    filterMs: round(filter),
    ...(await metrics(client)),
  };
  // A reader who has scrolled up in a full log while records stream in at
  // the most the host sends: the drawn span grows to its limit and every
  // batch is a commit over it.
  await page.goto(
    `${origin}/scenarios.html?scenario=signed-in&bar=off&records=${RECORDS}&feed=100`,
  );
  // The log is restored as the active tab. A fresh page has never activated
  // its console, so no terminal renderer needs to exist for this measurement.
  await page.locator("#tab-logs").click();
  await page.locator(".logview-list .record").first().waitFor();
  const reading = await page.locator(".logview-list").boundingBox();
  await page.mouse.move(
    reading.x + reading.width / 2,
    reading.y + reading.height / 2,
  );
  await page.mouse.wheel(0, -900);
  await page.waitForTimeout(12000);
  const streamed = await frames(page, () => page.waitForTimeout(3000));
  report.logWhileReading = {
    drawn: await page.locator(".logview-list .record").count(),
    frameMs: {
      median: round(median(streamed)),
      p95: round(percentile(streamed, 0.95)),
      worst: round(Math.max(...streamed)),
    },
  };
  await context.close();

  // The filing calendar at the turn of a year, nine windows open at once:
  // how long it takes to be drawn, what its faces and a month drawn whole
  // leave behind when gone over many times, and what a drag of the split
  // costs while its months are laid out anew at every step.
  {
    stage("calendar");
    const context = await measuredShellContext();
    // Observe the shortcut before the shell can synchronously draw its page.
    await context.addInitScript(() => {
      window.addEventListener(
        "keydown",
        (event) => {
          if (
            event.code === "KeyD" &&
            event.ctrlKey &&
            event.shiftKey &&
            window.__calendarTiming
          )
            window.__calendarTiming.from = performance.now();
        },
        true,
      );
    });
    const page = await context.newPage();
    const client = await context.newCDPSession(page);
    await client.send("Performance.enable");
    await page.goto(
      `${origin}/scenarios.html?scenario=signed-in&bar=off&latency=0&calendar=busy`,
    );
    await page.locator('[data-terminal="console"] .xterm-screen').waitFor();
    const months = page.locator(".calendar-months");
    const show = () => page.keyboard.press("Control+Shift+KeyD");
    const shown = [];
    for (let run = 0; run < RUNS; run++) {
      // Closing the calendar can restore focus inside Docs. A key relayed
      // from that iframe never reaches this window's timing listener.
      await page.locator(".rail button").first().focus();
      // Timed in the page, from the key to the frame after the months are
      // in the document.
      await page.evaluate(() => {
        if (document.activeElement !== document.querySelector(".rail button"))
          throw new Error(
            "Calendar timing requires focus in the parent window",
          );
        if (document.querySelector(".calendar-months"))
          throw new Error(
            "Calendar timing requires the calendar to start closed",
          );
        const timing = (window.__calendarTiming = { from: null });
        window.__calendarDraw = new Promise((done, reject) => {
          const stop = () => {
            delete window.__calendarTiming;
            seen.disconnect();
            clearTimeout(timeout);
          };
          const seen = new MutationObserver(() => {
            if (!document.querySelector(".calendar-month")) return;
            stop();
            if (timing.from === null) {
              reject(
                new Error("Calendar appeared without the measured key event"),
              );
              return;
            }
            requestAnimationFrame(() => done(performance.now() - timing.from));
          });
          const timeout = setTimeout(() => {
            stop();
            reject(new Error("Calendar did not appear after the measured key"));
          }, 10000);
          seen.observe(document.body, { childList: true, subtree: true });
        });
      });
      const drawn = page.evaluate(() => window.__calendarDraw);
      const [elapsed] = await Promise.all([drawn, show()]);
      shown.push(elapsed);
      await page.evaluate(() => delete window.__calendarDraw);
      await show();
      await months.waitFor({ state: "detached" });
    }
    const face = (index) =>
      page.locator(".calendar-view [role=radio]").nth(index).click();
    const whole = page.locator(".calendar-whole").first();
    const churn = async (count) => {
      for (let run = 0; run < count; run++) {
        await show();
        await months.waitFor();
        await face(1);
        await page.locator(".calendar-list").waitFor();
        await face(0);
        await months.waitFor();
        await whole.click();
        await page.locator('.calendar-whole[aria-expanded="true"]').waitFor();
        await whole.click();
        await page.locator(".calendar-bar").first().click();
        await show();
        await months.waitFor({ state: "detached" });
      }
      return metrics(client);
    };
    const settled = await churn(10);
    const later = await churn(40);
    await show();
    await months.waitFor();
    const held = await metrics(client);
    const { x, y, horizontalMotion } = await dockDivider(page);
    if (!horizontalMotion)
      throw new Error("The calendar measurement requires side-by-side panes.");
    const drag = await frames(page, async () => {
      await page.mouse.move(x, y);
      await page.mouse.down();
      // Out to where both faces fit and back: every step lays the months
      // out anew, and two of them change the face.
      for (let step = 0; step <= 60; step++) {
        await page.mouse.move(x + (step <= 30 ? step : 60 - step) * 12, y);
        await nextFrame(page);
        // At its widest the page has both faces: a drag that never got
        // there measured nothing that was asked.
        if (
          step === 30 &&
          (await page.locator(".calendar-aside").count()) === 0
        )
          throw new Error("The drag did not widen the calendar to both faces.");
      }
      await page.mouse.up();
    });
    if ((await page.locator(".calendar-aside").count()) !== 0)
      throw new Error("The drag did not bring the calendar back to one face.");
    report.calendar = {
      windows: await page.locator("li[data-entry], .calendar-bar").count(),
      shownMs: {
        first: round(shown[0]),
        median: round(median(shown)),
      },
      heapMB: held.heapMB,
      churn: {
        cycles: 40,
        nodesGrown: later.nodes - settled.nodes,
        listenersGrown: later.listeners - settled.listeners,
      },
      splitDragFrameMs: {
        median: round(median(drag)),
        p95: round(percentile(drag, 0.95)),
        worst: round(Math.max(...drag)),
      },
    };
    await context.close();
  }

  // The sign-in dialog, signed out with several profiles: put aside and
  // opened again, turned into the form that creates a profile and back,
  // and another profile chosen. What it leaves behind must not keep growing.
  {
    stage("sign-in retention");
    const context = await measuredShellContext();
    const page = await context.newPage();
    const client = await context.newCDPSession(page);
    await client.send("Performance.enable");
    await page.goto(
      `${origin}/scenarios.html?scenario=signed-out&bar=off&latency=0`,
    );
    const dialog = page.locator(".sign-in");
    const choice = page.locator("#profile-choice");
    await choice.waitFor();
    const churn = async (count) => {
      for (let run = 0; run < count; run++) {
        await page.locator(".new-profile").click();
        await page.locator(".create-profile").waitFor();
        await page.locator(".create-profile button").last().click();
        await choice.waitFor();
        await choice.selectOption({ index: 2 });
        await choice.selectOption({ index: 0 });
        await page.keyboard.press("Escape");
        await dialog.waitFor({ state: "detached" });
        await page
          .locator(".pane-tui [data-slot=empty] button")
          .first()
          .click();
        await choice.waitFor();
      }
      return metrics(client);
    };
    const settled = await churn(10);
    const later = await churn(40);
    report.signIn = {
      heapMB: later.heapMB,
      churn: {
        cycles: 40,
        nodesGrown: later.nodes - settled.nodes,
        listenersGrown: later.listeners - settled.listeners,
      },
    };
    await context.close();
  }

  // The Ledger page over a period of five thousand movements: how long the
  // period takes to be read in pages and drawn, a scroll through it, every
  // shown movement selected, and a sort of the whole window.
  {
    stage("ledger");
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();
    const client = await context.newCDPSession(page);
    await client.send("Performance.enable");
    await page.addInitScript(() =>
      localStorage.setItem(
        "cadrumo-shell-layout",
        JSON.stringify({ layout: { page: "ledger" } }),
      ),
    );
    await page.goto(
      `${origin}/scenarios.html?scenario=ledger&bar=off&latency=0&ledger=large`,
    );
    const trigger = page.locator(".ledger-period");
    await trigger.waitFor();
    const grid = page.locator(".ledger-movements [role=grid]");
    const head = page.locator(".pane-docs .pane-head");
    // The large period is the fixture's last quarter, wherever today is.
    for (let guard = 0; guard < 400; guard++) {
      const shown = (await trigger.textContent()) ?? "";
      const [year, code] = shown.split(" · ");
      if (year === "2026" && code === "4T") break;
      const later =
        Number(year) > 2026 || (Number(year) === 2026 && code > "4T");
      await head
        .locator(".ledger-period")
        .locator("xpath=..")
        .getByRole("button")
        .nth(later ? 0 : 2)
        .click();
    }
    await grid.waitFor();
    const read = [];
    for (let run = 0; run < RUNS; run++) {
      // Timed in the page, from asking for the period again to the frame
      // that draws it whole.
      read.push(
        await page.evaluate(
          () =>
            new Promise((done) => {
              const status = () =>
                document.querySelector(".ledger-movements .ledger-count")
                  ?.textContent ?? "";
              const before = status();
              const buttons = document
                .querySelector(".pane-docs .pane-head .ledger-period")
                .parentElement.querySelectorAll("button");
              buttons[0].click();
              // Once the quarter before is drawn, the large one is asked
              // for again and timed until it is drawn whole.
              const back = () => {
                const now = status();
                if (now === "" || now === before)
                  return requestAnimationFrame(back);
                const started = performance.now();
                buttons[2].click();
                const whole = () =>
                  status() === before
                    ? requestAnimationFrame(() =>
                        done(performance.now() - started),
                      )
                    : requestAnimationFrame(whole);
                requestAnimationFrame(whole);
              };
              requestAnimationFrame(back);
            }),
        ),
      );
    }
    const rows = Number(await grid.getAttribute("aria-rowcount")) - 1;
    if (rows < 5000)
      throw new Error(`The large period read ${rows} movements, not 5000.`);
    const scroll = await frames(page, () =>
      page.evaluate(
        () =>
          new Promise((done) => {
            const box = document.querySelector(".ledger-movements [role=grid]");
            const started = performance.now();
            const step = (now) => {
              box.scrollTop += box.clientHeight;
              if (now - started < 2000) requestAnimationFrame(step);
              else done();
            };
            requestAnimationFrame(step);
          }),
      ),
    );
    await grid.locator("[data-kind=data] [role=gridcell]").first().click();
    const select = await page.evaluate(
      () =>
        new Promise((done) => {
          const cell = document.activeElement;
          const started = performance.now();
          cell.dispatchEvent(
            new KeyboardEvent("keydown", {
              key: "a",
              code: "KeyA",
              ctrlKey: true,
              bubbles: true,
              cancelable: true,
            }),
          );
          requestAnimationFrame(() => done(performance.now() - started));
        }),
    );
    const sort = await page.evaluate(
      () =>
        new Promise((done) => {
          const header = [
            ...document.querySelectorAll(
              ".ledger-movements [role=columnheader]",
            ),
          ].find((cell) => cell.getAttribute("aria-sort") === "none");
          const started = performance.now();
          header.click();
          requestAnimationFrame(() => done(performance.now() - started));
        }),
    );
    report.ledger = {
      movements: rows,
      drawnRows: await grid.locator("[data-kind=data]").count(),
      readMs: { median: round(median(read)), worst: round(Math.max(...read)) },
      scrollFrameMs: {
        median: round(median(scroll)),
        p95: round(percentile(scroll, 0.95)),
        worst: round(Math.max(...scroll)),
      },
      selectAllMs: round(select),
      sortMs: round(sort),
      ...(await metrics(client)),
    };
    await context.close();
  }
} catch (error) {
  const pages = [];
  for (const context of browser?.contexts() ?? []) {
    for (const page of context.pages()) {
      pages.push({
        url: page.url(),
        state: await page
          .evaluate(() => ({
            layout: localStorage.getItem("cadrumo-shell-layout"),
            text: document.body.innerText.slice(0, 4000),
            panes: Array.from(
              document.querySelectorAll("[data-dock-pane]"),
            ).map((pane) => pane.getAttribute("data-dock-pane")),
            terminals: Array.from(
              document.querySelectorAll("[data-terminal]"),
            ).map((terminal) => ({
              name: terminal.getAttribute("data-terminal"),
              text: terminal.textContent,
              rows: terminal.querySelectorAll(".xterm-rows").length,
            })),
          }))
          .catch((captureError) => ({ captureError: String(captureError) })),
      });
    }
  }
  const out = resolve(buildPath("desktop_results"), "benchmark");
  mkdirSync(out, { recursive: true });
  const file = resolve(out, "benchmark-failure.json");
  writeFileSync(
    file,
    `${JSON.stringify({ error: String(error), report, pages }, null, 2)}\n`,
  );
  console.error(`Benchmark failure state written to ${file}`);
  throw error;
} finally {
  try {
    await browser?.close();
  } finally {
    await server?.close();
  }
}

// What each number may be at most. Sizes are of the product build; a frame
// budget of two frames allows one dropped frame, never a run of them.
const BUDGETS = [
  ["product script, gzip kB", report.bundle.product.js.gzip / 1024, 320],
  ["product stylesheet, gzip kB", report.bundle.product.css.gzip / 1024, 20],
  ["first contentful paint ms", report.startMs.firstContentfulPaint, 1000],
  ["terminals ready ms", report.startMs.terminalsReady, 1500],
  ["idle heap MB", report.idle.heapMB, 24],
  ["palette open, median ms", report.paletteOpenMs.median, 100],
  // What stays after an overlay closes is the last one or two, kept until the
  // next render replaces them, so the count wanders by a few overlays' worth.
  // A leak keeps one for every cycle: several thousand nodes over forty.
  ["nodes grown over 40 overlay cycles", report.overlayChurn.nodesGrown, 1500],
  [
    "listeners grown over 40 overlay cycles",
    report.overlayChurn.listenersGrown,
    300,
  ],
  ["splitter drag frame, p95 ms", report.splitDragFrameMs.p95, 34],
  ["log first rows ms", report.log.firstRowsMs, 150],
  ["log scroll frame, p95 ms", report.log.scrollFrameMs.p95, 34],
  ["log filter ms", report.log.filterMs, 100],
  [
    "frame while reading a streaming log, p95 ms",
    report.logWhileReading.frameMs.p95,
    50,
  ],
  ["heap with the largest log MB", report.log.heapMB, 48],
  ["calendar shown, median ms", report.calendar.shownMs.median, 150],
  [
    "nodes grown over 40 calendar cycles",
    report.calendar.churn.nodesGrown,
    1500,
  ],
  [
    "listeners grown over 40 calendar cycles",
    report.calendar.churn.listenersGrown,
    300,
  ],
  [
    "splitter drag frame with the calendar, p95 ms",
    report.calendar.splitDragFrameMs.p95,
    34,
  ],
  ["heap with the calendar MB", report.calendar.heapMB, 24],
  [
    "nodes grown over 40 sign-in dialog cycles",
    report.signIn.churn.nodesGrown,
    1500,
  ],
  [
    "listeners grown over 40 sign-in dialog cycles",
    report.signIn.churn.listenersGrown,
    300,
  ],
  [
    "ledger period of 5,000 read and drawn, median ms",
    report.ledger.readMs.median,
    3000,
  ],
  ["ledger scroll frame, p95 ms", report.ledger.scrollFrameMs.p95, 34],
  ["ledger select every shown movement ms", report.ledger.selectAllMs, 150],
  ["ledger sort of 5,000 ms", report.ledger.sortMs, 300],
  ["ledger rows in the document", report.ledger.drawnRows, 80],
  ["heap with 5,000 movements MB", report.ledger.heapMB, 64],
];
report.budgets = BUDGETS.map(([name, value, most]) => ({
  name,
  value: round(value),
  most,
  within: value <= most,
}));

const out = resolve(buildPath("desktop_results"), "benchmark");
mkdirSync(out, { recursive: true });
const file = resolve(out, "benchmark.json");
writeFileSync(file, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
console.log(`\nWritten to ${file}`);
const over = report.budgets.filter((budget) => !budget.within);
for (const budget of over)
  console.error(
    `over budget: ${budget.name}: ${budget.value} > ${budget.most}`,
  );
if (values.check && over.length) process.exit(1);
