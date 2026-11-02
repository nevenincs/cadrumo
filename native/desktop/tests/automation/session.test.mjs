import assert from "node:assert/strict";
import { test } from "node:test";
import {
  mkdtempSync,
  mkdirSync,
  symlinkSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { resolve } from "node:path";
import { buildPath } from "../../scripts/build-paths.mjs";
import { hostEnvironment, within } from "./session.mjs";

test("native exploration gets isolated storage and no inherited runtime authority", () => {
  const env = hostEnvironment(
    {
      PATH: "/tools",
      CADRUMO_STORAGE_ROOT: "/real",
      CADRUMO_PROFILE: "real",
      WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: "override",
      TAURI_WEBDRIVER_PORT: "1",
      HTTP_PROXY: "remote",
    },
    "/synthetic/run",
    "/test/package",
    4445,
  );
  assert.equal(env.CADRUMO_STORAGE_ROOT, "/synthetic/run/storage");
  assert.equal(env.CADRUMO_DESKTOP_PACKAGE_ROOT, "/test/package");
  assert.equal(env.TAURI_WEBDRIVER_PORT, "4445");
  assert.equal(env.CADRUMO_PROFILE, undefined);
  assert.equal(env.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS, undefined);
  assert.equal(env.HTTP_PROXY, undefined);
  assert.equal(env.PATH, "/tools");
});

test("session files cannot escape their run root through traversal or symlinks", () => {
  const root = mkdtempSync(
    resolve(buildPath("desktop_testing"), "automation-paths-"),
  );
  try {
    const runs = resolve(root, "runs");
    mkdirSync(runs);
    const inside = resolve(runs, "session.json");
    writeFileSync(inside, "{}");
    const outside = resolve(root, "outside.json");
    writeFileSync(outside, "{}");
    symlinkSync(outside, resolve(runs, "linked.json"));
    assert.equal(within(runs, inside), inside);
    assert.throws(() => within(runs, outside), /inside/);
    assert.throws(() => within(runs, resolve(runs, "linked.json")), /inside/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
