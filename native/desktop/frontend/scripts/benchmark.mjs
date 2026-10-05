// Measures the shell as it ships: bundle size, start-up, memory, and the
// interactions that can cost the most (a ten-thousand-record log, the
// palette, a splitter drag). It builds the product and a minified build of
// the development entry, serves the latter from memory-free static files,
// drives it in Chromium and writes the numbers under the build directory's
// test results. The numbers describe this machine; compare runs, not hosts.
import { chromium } from "@playwright/test";
import { spawnSync } from "node:child_process";
import {
  createReadStream,
  existsSync,
  mkdirSync,
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

/** The bytes of what one entry page loads, raw and gzipped, by kind. */
function bundle(directory, page) {
  const html = readFileSync(join(directory, page), "utf8");
  const loaded = [...html.matchAll(/(?:src|href)="\.\/([^"]+)"/g)].map(
    (match) => match[1],
  );
  const sizes = {};
  for (const name of loaded) {
    const bytes = readFileSync(join(directory, name));
    const kind = extname(name).slice(1);
    sizes[kind] ??= { raw: 0, gzip: 0 };
    sizes[kind].raw += bytes.length;
    sizes[kind].gzip += gzipSync(bytes).length;
  }
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
  bundle: { product: bundle(product, "index.html") },
};

try {
  // Start-up: a fresh context each run, so nothing is cached.
  const start = [];
  for (let run = 0; run < RUNS; run++) {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();
    await page.goto(`${origin}/scenarios.html?scenario=signed-in&bar=off`);
    await page.waitForSelector('[data-terminal="console"] .xterm-rows');
    start.push(
      await page.evaluate(() => {
        const [navigation] = performance.getEntriesByType("navigation");
        const paint = performance
          .getEntriesByType("paint")
          .find((entry) => entry.name === "first-contentful-paint");
        return {
          domContentLoaded: navigation.domContentLoadedEventEnd,
          firstContentfulPaint: paint?.startTime ?? 0,
          terminalsReady: performance.now(),
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
  report.afterPalette = await metrics(client);

  // A splitter drag across the main area.
  const handle = await page.locator(".split-separator").boundingBox();
  const drag = await frames(page, async () => {
    await page.mouse.move(handle.x, handle.y + 200);
    await page.mouse.down();
    for (let step = 0; step <= 60; step++)
      await page.mouse.move(handle.x - 300 + step * 10, handle.y + 200);
    await page.mouse.up();
  });
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
  const scroll = await frames(page, () =>
    page.evaluate(
      () =>
        new Promise((done) => {
          const list = document.querySelector(".logview-list");
          const started = performance.now();
          // From the newest record up toward the oldest, so every earlier
          // span is brought in on the way.
          const step = (now) => {
            const share = 1 - (now - started) / 2000;
            list.scrollTop = share * (list.scrollHeight - list.clientHeight);
            if (now - started < 2000) requestAnimationFrame(step);
            else done();
          };
          requestAnimationFrame(step);
        }),
    ),
  );
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
        requestAnimationFrame(() =>
          requestAnimationFrame(() => done(performance.now() - started)),
        );
      }),
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
  await context.close();
} finally {
  await browser.close();
  server.close();
}

const out = resolve(buildPath("desktop_results"), "benchmark");
mkdirSync(out, { recursive: true });
const file = resolve(out, "benchmark.json");
writeFileSync(file, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
console.log(`\nWritten to ${file}`);
