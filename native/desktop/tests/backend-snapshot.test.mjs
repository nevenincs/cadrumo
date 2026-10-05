import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  renameSync,
  rmSync,
  statSync,
  symlinkSync,
  utimesSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { syncBackendSource } from "../scripts/backend-snapshot.mjs";

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "cadrumo-backend-snapshot-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const source = join(root, "source");
  const build = join(root, "build");
  const target = join(build, "snapshot");
  mkdirSync(source);
  mkdirSync(build);
  return { source, build, target };
}

test("unchanged input keeps timestamps; edits and renames reach Cargo", (t) => {
  const { source, build, target } = fixture(t);
  writeFileSync(join(source, "old.rs"), "first");
  syncBackendSource(source, target, build);
  const old = join(target, "old.rs");
  utimesSync(old, 1000000000, 1000000000);
  const timestamp = statSync(old).mtimeMs;
  syncBackendSource(source, target, build);
  assert.equal(statSync(old).mtimeMs, timestamp);
  writeFileSync(join(source, "old.rs"), "changed");
  syncBackendSource(source, target, build);
  assert.equal(readFileSync(old, "utf8"), "changed");
  renameSync(join(source, "old.rs"), join(source, "new.rs"));
  syncBackendSource(source, target, build);
  assert.throws(() => statSync(old), { code: "ENOENT" });
  assert.equal(readFileSync(join(target, "new.rs"), "utf8"), "changed");
});

test("snapshot refuses outside destinations and linked ancestors before removal", (t) => {
  const { source, build, target } = fixture(t);
  writeFileSync(join(source, "keep"), "owned source");
  assert.throws(() => syncBackendSource(source, source, build), /inside/);
  assert.throws(() => syncBackendSource(source, build, build), /inside/);
  symlinkSync(
    source,
    target,
    process.platform === "win32" ? "junction" : "dir",
  );
  assert.throws(() => syncBackendSource(source, target, build), /linked/);
  assert.equal(readFileSync(join(source, "keep"), "utf8"), "owned source");
});
