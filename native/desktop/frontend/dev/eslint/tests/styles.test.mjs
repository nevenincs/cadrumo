import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { styleViolations } from "../styles.mjs";

const root = fileURLToPath(new URL("../../../", import.meta.url));
function sheets(directory) {
  return readdirSync(join(root, directory), {
    withFileTypes: true,
  }).flatMap((entry) => {
    const path = `${directory}/${entry.name}`;
    return entry.isDirectory()
      ? sheets(path)
      : entry.name.endsWith(".css")
        ? [path]
        : [];
  });
}

test("all source styles obey placement and token ownership", () => {
  for (const path of sheets("src"))
    assert.deepEqual(
      styleViolations(path, readFileSync(join(root, path), "utf8")),
      [],
      path,
    );
});

test("rejects scattered sheets, renamed modules and independent scales", () => {
  for (const [path, source] of [
    ["src/components/calendar.css", ".item { color: var(--foreground) }"],
    ["src/styles/BadName.css", ""],
    ["src/styles/calendar.module.css", ""],
    ["src/styles/utilities.css", ".item { width: 8rem }"],
    ["src/styles/base.css", ".item { transition-duration: 150ms }"],
    ["src/styles/base.css", ".item { color: #abc123 }"],
    ["src/styles/theme.css", ":root { --shadow: 0 2px 4px rgb(0 0 0 / 8%) }"],
  ])
    assert.ok(styleViolations(path, source).length > 0, path);
});

test("allows canonical declarations, tokens and computational zeros", () => {
  for (const [path, source] of [
    [
      "src/styles/tokens.css",
      ":root { --motion-fast: 120ms; --hairline: 1px }",
    ],
    ["src/styles/theme.css", ":root { --scrim: rgb(0 0 0 / 22%) }"],
    ["src/styles/utilities.css", ".item { width: var(--spacing-field) }"],
    ["src/styles/base.css", ".item { width: 0px; height: 100% }"],
  ])
    assert.deepEqual(styleViolations(path, source), []);
});
