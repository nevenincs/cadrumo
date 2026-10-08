// Screenshots of the running catalogue, one per story, scheme and language,
// for reviewing the design as it is actually drawn. Start the catalogue first
// (`npm run storybook`), then run this; the images go under the build
// directory's test results.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { buildPath } from "../../scripts/build-paths.mjs";

const { values } = parseArgs({
  options: {
    base: { type: "string", default: "http://127.0.0.1:6006" },
    out: { type: "string" },
    schemes: { type: "string", default: "light,dark" },
    locales: { type: "string", default: "en" },
    filter: { type: "string", default: "" },
    width: { type: "string", default: "1280" },
    height: { type: "string", default: "800" },
    scale: { type: "string", default: "1" },
  },
});

const out = resolve(
  values.out ?? resolve(buildPath("desktop_results"), "catalogue"),
);
mkdirSync(out, { recursive: true });

const index = await (await fetch(`${values.base}/index.json`)).json();
const filter = new RegExp(values.filter, "i");
const stories = Object.values(index.entries).filter(
  (entry) => entry.type === "story" && filter.test(entry.id),
);
if (!stories.length) throw new Error("No story matches the filter.");

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: Number(values.width), height: Number(values.height) },
  deviceScaleFactor: Number(values.scale),
});
const page = await context.newPage();
// A story that cannot load something is not the application as it is drawn.
const refused = [];
page.on("response", (response) => {
  if (response.status() >= 400 && !response.url().endsWith("/favicon.ico"))
    refused.push(`${response.status()} ${response.url()}`);
});
let failures = 0;
for (const story of stories)
  for (const scheme of values.schemes.split(","))
    for (const locale of values.locales.split(",")) {
      const url = `${values.base}/iframe.html?id=${story.id}&viewMode=story&globals=scheme:${scheme};locale:${locale}`;
      const file = resolve(out, `${story.id}.${scheme}.${locale}.png`);
      try {
        await page.goto(url, { waitUntil: "networkidle" });
        await page.waitForSelector("#storybook-root > *", { timeout: 15000 });
        // A story may act before it is ready to be looked at: typing a query,
        // moving the choice. Its render ends when that has finished.
        const phase = await page
          .waitForFunction(
            () => {
              const at = window.__STORYBOOK_PREVIEW__?.currentRender?.phase;
              return ["completed", "afterEach", "finished", "errored"].includes(
                at,
              )
                ? at
                : false;
            },
            null,
            { timeout: 15000 },
          )
          .then((handle) => handle.jsonValue());
        if (phase === "errored") throw new Error("the story failed to render");
        await page.evaluate(() => document.fonts.ready);
        const fonts = await page.evaluate(() =>
          [...document.fonts]
            .filter((font) => font.status === "error")
            .map((font) => font.family),
        );
        if (fonts.length) throw new Error(`fonts failed: ${fonts.join(", ")}`);
        if (refused.length) throw new Error(refused.splice(0).join("; "));
        // The story's frame scrolls inside the viewport, so a tall story is
        // photographed in a viewport grown to its whole height.
        const tall = await page.evaluate(() => {
          const frame = document.querySelector("#storybook-root > *");
          return frame ? frame.scrollHeight : 0;
        });
        const size = page.viewportSize();
        if (size && tall > size.height)
          await page.setViewportSize({ width: size.width, height: tall });
        await page.screenshot({ path: file });
        if (size) await page.setViewportSize(size);
        console.log(file);
      } catch (error) {
        failures += 1;
        console.error(`failed: ${story.id} ${scheme} ${locale}: ${error}`);
      }
    }
await browser.close();
process.exit(failures ? 1 : 0);
