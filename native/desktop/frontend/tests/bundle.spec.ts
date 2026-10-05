import { expect, test } from "@playwright/test";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { buildPath } from "../../scripts/build-paths.mjs";
import { SCENARIO_HOST_MARKER } from "../src/dev/marker";

const local = (path: string) => fileURLToPath(new URL(path, import.meta.url));

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
// absent from the product, not merely unused by it.
test("the search finds the scenario marker where the scenario host lives", () => {
  expect(carrying(local("../src/dev"), SCENARIO_HOST_MARKER)).toContain(
    "marker.ts",
  );
});

test("the production build contains no development scenario code", () => {
  const built = buildPath("desktop_frontend");
  expect(existsSync(join(built, "index.html"))).toBe(true);
  const names = files(built);
  expect(names.filter((name) => /scenario|docs-fixture/i.test(name))).toEqual(
    [],
  );
  expect(carrying(built, SCENARIO_HOST_MARKER)).toEqual([]);
  // Text the fixtures draw, in case the marker alone were tree-shaken away.
  for (const text of ["Simulated TUI session", "development fixture"])
    expect(carrying(built, text)).toEqual([]);
});
