import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { buildPath } from "../scripts/build-paths.mjs";

const testing = buildPath("desktop_testing");
mkdirSync(testing, { recursive: true });

test("desktop tools require declared, contained CMake paths", () => {
  const original = process.env.CADRUMO_CMAKE_BINARY_DIR;
  const root = mkdtempSync(resolve(testing, "paths-"));
  try {
    process.env.CADRUMO_CMAKE_BINARY_DIR = root;
    assert.throws(() => buildPath("frontend"), /ENOENT/);
    writeFileSync(
      resolve(root, "build-paths.json"),
      JSON.stringify({
        paths: { frontend: "assets/web", escape: "../outside" },
      }),
    );
    assert.equal(buildPath("frontend"), resolve(root, "assets/web"));
    assert.throws(() => buildPath("escape"), /Invalid CMake output directory/);
    assert.throws(() => buildPath("missing"), /Invalid CMake output directory/);
  } finally {
    process.env.CADRUMO_CMAKE_BINARY_DIR = original;
    rmSync(root, { recursive: true });
  }
});
