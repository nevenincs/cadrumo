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
import {
  createReadStream,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { gzipSync } from "node:zlib";
import { buildPath } from "../../scripts/build-paths.mjs";

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
    [resolve(frontend, "node_modules/vite/bin/vite.js"), ...args],
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

const TYPES = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
};

function serve(directory) {
  const server = createServer((request, response) => {
    const path = normalize(
      join(directory, new URL(request.url, "http://x").pathname),
    );
    if (!path.startsWith(directory + sep) || !existsSync(path)) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, {
      "Content-Type": TYPES[extname(path)] ?? "application/octet-stream",
    });
    createReadStream(path).pipe(response);
  });
  return new Promise((ready) =>
    server.listen(0, "127.0.0.1", () =>
      ready({ server, origin: `http://127.0.0.1:${server.address().port}` }),
    ),
  );
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
const built = resolve(buildPath("desktop_testing"), "scenarios");
const { server, origin } = await serve(built);
const browser = await chromium.launch();
const report = {
  at: new Date().toISOString(),
  bundle: { product: bundle(product) },
};

/** One frame in the page, so what was just done has been drawn. */
const nextFrame = (page) =>
  page.evaluate(() => new Promise((done) => requestAnimationFrame(done)));

try {
  // Start-up: a fresh context each run, so nothing is cached.
  const start = [];
  for (let run = 0; run < RUNS; run++) {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();
    // The page notes for itself when its terminals have drawn, so the time
    // carries none of this script's own polling.
    await page.addInitScript(() => {
      const seen = new MutationObserver(() => {
        if (!document.querySelector('[data-terminal="console"] .xterm-rows'))
          return;
        seen.disconnect();
        window.__terminalsReady = performance.now();
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

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  const client = await context.newCDPSession(page);
  await client.send("Performance.enable");

  // Idle shell: three terminals, the fixture log, nothing open.
  await page.goto(`${origin}/scenarios.html?scenario=signed-in&bar=off`);
  await page.waitForSelector('[data-terminal="console"] .xterm-rows');
  await page.waitForTimeout(500);
  report.idle = await metrics(client);

  // The palette: from the chord to the dialog being on screen.
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
  const separator = page.locator(".split-separator");
  const handle = await separator.boundingBox();
  const before = await separator.getAttribute("aria-valuenow");
  const drag = await frames(page, async () => {
    await page.mouse.move(handle.x, handle.y + 200);
    await page.mouse.down();
    for (let step = 0; step <= 60; step++) {
      await page.mouse.move(handle.x - 300 + step * 10, handle.y + 200);
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
  await page.goto(
    `${origin}/scenarios.html?scenario=signed-in&bar=off&records=${RECORDS}`,
  );
  await page.waitForSelector('[data-terminal="console"] .xterm-rows');
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
  await page.selectOption(".logview select", "0");
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
  // The log's tab is still the open one, so the console is not on screen.
  await page.waitForSelector('[data-terminal="console"] .xterm-rows', {
    state: "attached",
  });
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
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();
    const client = await context.newCDPSession(page);
    await client.send("Performance.enable");
    await page.goto(
      `${origin}/scenarios.html?scenario=signed-in&bar=off&latency=0&calendar=busy`,
    );
    await page.locator('[data-terminal="console"] .xterm-rows').waitFor();
    const months = page.locator(".calendar-months");
    const show = () => page.keyboard.press("Control+Shift+KeyD");
    const shown = [];
    for (let run = 0; run < RUNS; run++) {
      // Timed in the page, from the key to the frame after the months are
      // in the document.
      const drawn = page.evaluate(
        () =>
          new Promise((done) => {
            let from = 0;
            window.addEventListener(
              "keydown",
              () => (from = performance.now()),
              { once: true, capture: true },
            );
            const seen = new MutationObserver(() => {
              if (!document.querySelector(".calendar-month")) return;
              seen.disconnect();
              requestAnimationFrame(() => done(performance.now() - from));
            });
            seen.observe(document.body, { childList: true, subtree: true });
          }),
      );
      await show();
      shown.push(await drawn);
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
    const separator = page.locator(".split-separator").first();
    const handle = await separator.boundingBox();
    const drag = await frames(page, async () => {
      await page.mouse.move(handle.x, handle.y + 200);
      await page.mouse.down();
      // Out to where both faces fit and back: every step lays the months
      // out anew, and two of them change the face.
      for (let step = 0; step <= 60; step++) {
        await page.mouse.move(
          handle.x + (step <= 30 ? step : 60 - step) * 12,
          handle.y + 200,
        );
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
} finally {
  await browser.close();
  server.close();
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
