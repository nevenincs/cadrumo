import assert from "node:assert/strict";
import {
  existsSync,
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  cleanInstalled,
  withInstallLock,
} from "../scripts/frontend-install.mjs";

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "cadrumo-frontend-clean-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const frontend = join(root, "frontend");
  mkdirSync(join(frontend, "node_modules"), { recursive: true });
  writeFileSync(join(frontend, "package.json"), "source manifest");
  writeFileSync(join(frontend, "node_modules", "installed"), "generated");
  return { root, frontend };
}

test("explicit install cleanup removes only shared npm outputs and is idempotent", (t) => {
  const { frontend } = fixture(t);
  assert.equal(cleanInstalled(frontend), 0);
  assert.equal(existsSync(join(frontend, "node_modules")), false);
  assert.equal(
    readFileSync(join(frontend, "package.json"), "utf8"),
    "source manifest",
  );
  assert.equal(cleanInstalled(frontend), 0);
  assert.equal(existsSync(join(frontend, ".cadrumo-npm.lock")), false);
});

test("install and clean share exclusive ownership", (t) => {
  const { frontend } = fixture(t);
  withInstallLock(frontend, () => {
    assert.throws(
      () => cleanInstalled(frontend),
      /Another frontend install or clean/,
    );
    assert.equal(existsSync(join(frontend, "node_modules", "installed")), true);
  });
  assert.throws(
    () =>
      withInstallLock(frontend, () => {
        throw new Error("install failed");
      }),
    /install failed/,
  );
  assert.equal(cleanInstalled(frontend), 0);
});

test("cleanup rejects linked owners and does not follow nested package links", (t) => {
  const { root, frontend } = fixture(t);
  const outside = join(root, "outside");
  mkdirSync(outside);
  writeFileSync(join(outside, "keep"), "outside");
  const kind = process.platform === "win32" ? "junction" : "dir";
  symlinkSync(outside, join(frontend, "node_modules", "linked-package"), kind);
  cleanInstalled(frontend);
  assert.equal(readFileSync(join(outside, "keep"), "utf8"), "outside");
  symlinkSync(outside, join(frontend, "node_modules"), kind);
  assert.throws(() => cleanInstalled(frontend), /linked paths/);
  assert.equal(readFileSync(join(outside, "keep"), "utf8"), "outside");
  const linkedFrontend = join(root, "linked-frontend");
  symlinkSync(frontend, linkedFrontend, kind);
  assert.throws(() => cleanInstalled(linkedFrontend), /linked paths/);
});
