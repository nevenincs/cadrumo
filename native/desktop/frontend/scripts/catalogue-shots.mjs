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
let failures = 0;
for (const story of stories)
  for (const scheme of values.schemes.split(","))
    for (const locale of values.locales.split(",")) {
      const url = `${values.base}/iframe.html?id=${story.id}&viewMode=story&globals=scheme:${scheme};locale:${locale}`;
      const file = resolve(out, `${story.id}.${scheme}.${locale}.png`);
      try {
        await page.goto(url, { waitUntil: "networkidle" });
        await page.waitForSelector("#storybook-root > *", { timeout: 15000 });
        await page.evaluate(() => document.fonts.ready);
        await page.screenshot({ path: file, fullPage: true });
        console.log(file);
      } catch (error) {
        failures += 1;
        console.error(`failed: ${story.id} ${scheme} ${locale}: ${error}`);
      }
    }
await browser.close();
process.exit(failures ? 1 : 0);
