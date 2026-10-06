import { expect, test } from "@playwright/test";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../scripts/build-paths.mjs";
import { developmentModules } from "../dev/product-boundary";
import { SCENARIO_HOST_MARKER } from "../src/dev/marker";
import { AEAT_SEDE } from "../src/shell/links";

const local = (path: string) => fileURLToPath(new URL(path, import.meta.url));
const root = local("..");

/** Every file under `directory`, as paths relative to it. */
function files(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory()
      ? files(path).map((inner) => join(entry.name, inner))
      : [relative(directory, path)];
  });
}

/** The files under `directory` whose bytes contain `text`. */
function carrying(directory: string, text: string): string[] {
  return files(directory).filter((file) =>
    readFileSync(join(directory, file)).includes(text),
  );
}

// The scenario host fabricates host answers, sign-in included, so it must be
// absent from the product, not merely unused by it. The build refuses any
// development module (dev/product-boundary.ts); these tests hold that refusal
// to representative inputs and then look at what was actually built.

test("the build boundary names every kind of development module", () => {
  const at = (path: string) => resolve(root, path);
  expect(
    developmentModules(
      [
        at("src/dev/scenarioHost.ts"),
        at("src/dev/scenarios.ts"),
        at("src/dev/fixtures/logs.ts"),
        at("src/dev/ScenarioBar.tsx"),
        at("dev/docs-fixture/plugin.ts"),
        at("src/components/ui/button.stories.tsx"),
        `${at("src/dev/dev.css")}?direct`,
      ],
      root,
    ),
  ).toEqual([
    "src/dev/scenarioHost.ts",
    "src/dev/scenarios.ts",
    "src/dev/fixtures/logs.ts",
    "src/dev/ScenarioBar.tsx",
    "dev/docs-fixture/plugin.ts",
    "src/components/ui/button.stories.tsx",
    "src/dev/dev.css",
  ]);
});

test("the build boundary leaves product and dependency modules alone", () => {
  const at = (path: string) => resolve(root, path);
  expect(
    developmentModules(
      [
        at("src/App.tsx"),
        at("src/shell/host.ts"),
        at("src/components/ui/button.tsx"),
        at("node_modules/react/index.js"),
        resolve(root, "../../../docs/_static/hanken-grotesk-var-latin.woff2"),
        "\0desktop-content",
      ],
      root,
    ),
  ).toEqual([]);
});

test("the search finds the scenario marker where the scenario host lives", () => {
  expect(carrying(local("../src/dev"), SCENARIO_HOST_MARKER)).toContain(
    "marker.ts",
  );
});

test("the addresses the shell opens are the product's own constants", () => {
  const constants = readFileSync(
    local("../../../../src/cadrumo/core/external_constants.toml"),
    "utf8",
  );
  expect(/^sede = "([^"]+)"$/m.exec(constants)?.[1]).toBe(AEAT_SEDE);
});

test("the production build contains no development scenario code", () => {
  const built = buildPath("desktop_frontend");
  expect(existsSync(join(built, "index.html"))).toBe(true);
  expect(
    files(built).filter((name) => /scenario|docs-fixture|stories/i.test(name)),
  ).toEqual([]);
  // Every file in the directory: the desktop package embeds all of it, and
  // a build leaves nothing of an earlier one behind.
  const page = readFileSync(join(built, "index.html"), "utf8");
  const entry = [...page.matchAll(/(?:src|href)="\.\/([^"]+)"/g)].map(
    (match) => match[1] ?? "",
  );
  expect(entry.length).toBeGreaterThan(0);
  const loaded = files(built);
  expect(loaded.filter((name) => /\.js$/.test(name)).length).toBeLessThan(8);
  for (const text of [
    SCENARIO_HOST_MARKER,
    "Simulated TUI session",
    "development fixture",
    "Simulated host",
  ])
    for (const file of loaded)
      expect(
        readFileSync(join(built, file)).includes(text),
        `${file} carries "${text}"`,
      ).toBe(false);
});
