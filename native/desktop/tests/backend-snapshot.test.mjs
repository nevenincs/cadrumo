import assert from "node:assert/strict";
import {
  existsSync,
  mkdtempSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  realpathSync,
  renameSync,
  rmSync,
  statSync,
  symlinkSync,
  utimesSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { isAbsolute, join, relative, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import {
  hostSnapshot,
  snapshotHostSources,
  syncBackendSource,
} from "../scripts/backend-snapshot.mjs";

const NATIVE = fileURLToPath(new URL("../../", import.meta.url));

function inside(root, path) {
  const rel = relative(root, path);
  return Boolean(rel) && !rel.startsWith("..") && !isAbsolute(rel);
}

// Every file beneath a directory, as paths relative to it.
function files(directory) {
  return readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => relative(directory, join(entry.parentPath, entry.name)));
}

// The directories a manifest names by a relative path that leaves its crate.
function pathDependencies(crate) {
  const manifest = readFileSync(join(crate, "Cargo.toml"), "utf8");
  return [...manifest.matchAll(/\bpath\s*=\s*"([^"]+)"/g)]
    .map((match) => resolve(crate, match[1]))
    .filter((target) => !inside(crate, target));
}

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

test("the host snapshot keeps every crate the manifests name inside its root", (t) => {
  const build = realpathSync(
    mkdtempSync(join(tmpdir(), "cadrumo-host-snapshot-")),
  );
  t.after(() => rmSync(build, { recursive: true, force: true }));
  for (const incremental of [false, true]) {
    const declared = join(build, String(incremental), "desktop/host");
    const snapshot = snapshotHostSources(NATIVE, declared, { incremental });
    assert.deepEqual(snapshot, hostSnapshot(declared));
    const crates = [snapshot.crate, ...snapshot.crates];
    for (const path of [snapshot.project, ...crates])
      assert.ok(inside(declared, path), path);
    // A sibling of the declared directory is an output no cleanup group owns.
    assert.deepEqual(readdirSync(join(declared, "..")), ["host"]);
    assert.equal(
      realpathSync(join(snapshot.project, "src-tauri")),
      snapshot.crate,
    );
    const named = crates.flatMap(pathDependencies);
    assert.ok(named.length >= 2, "the host manifest names its sibling crates");
    for (const target of named) {
      assert.ok(crates.includes(target), `${target} is not a snapshot crate`);
      assert.ok(existsSync(join(target, "Cargo.toml")), target);
    }
    // The copy has the source tree's own relative layout.
    for (const crate of crates) {
      const source = resolve(NATIVE, relative(declared, crate));
      assert.deepEqual(files(join(crate, "src")), files(join(source, "src")));
      assert.deepEqual(
        readFileSync(join(crate, "Cargo.toml")),
        readFileSync(join(source, "Cargo.toml")),
      );
    }
  }
});

function crates(t) {
  const root = realpathSync(
    mkdtempSync(join(tmpdir(), "cadrumo-host-snapshot-")),
  );
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const native = join(root, "native");
  for (const crate of ["application", "platform", "desktop/src-tauri"]) {
    mkdirSync(join(native, crate, "src"), { recursive: true });
    writeFileSync(join(native, crate, "Cargo.toml"), crate);
    writeFileSync(join(native, crate, "src/old.rs"), crate);
  }
  for (const entry of ["Cargo.lock", "build.rs"])
    writeFileSync(join(native, "desktop/src-tauri", entry), entry);
  return { root, native, declared: join(root, "build/desktop/host") };
}

test("a full host snapshot drops renamed sources and keeps generated files", (t) => {
  const { native, declared } = crates(t);
  const snapshot = snapshotHostSources(native, declared);
  writeFileSync(join(snapshot.crate, "tauri.conf.json"), "generated");
  for (const crate of ["application", "platform", "desktop/src-tauri"])
    renameSync(
      join(native, crate, "src/old.rs"),
      join(native, crate, "src/new.rs"),
    );
  snapshotHostSources(native, declared);
  for (const crate of [snapshot.crate, ...snapshot.crates])
    assert.deepEqual(readdirSync(join(crate, "src")), ["new.rs"]);
  assert.equal(
    readFileSync(join(snapshot.crate, "tauri.conf.json"), "utf8"),
    "generated",
  );
  assert.deepEqual(readdirSync(join(declared, "..")), ["host"]);
});

test("a host snapshot refuses a linked root or a linked crate", (t) => {
  const { root, native, declared } = crates(t);
  const outside = join(root, "outside");
  mkdirSync(join(outside, "src"), { recursive: true });
  writeFileSync(join(outside, "src/keep.rs"), "not generated");
  const kind = process.platform === "win32" ? "junction" : "dir";
  mkdirSync(declared, { recursive: true });
  symlinkSync(outside, join(declared, "application"), kind);
  for (const incremental of [false, true])
    assert.throws(
      () => snapshotHostSources(native, declared, { incremental }),
      /linked|outside their declared directory/,
    );
  rmSync(declared, { recursive: true });
  symlinkSync(outside, declared, kind);
  for (const incremental of [false, true])
    assert.throws(
      () => snapshotHostSources(native, declared, { incremental }),
      /linked|outside their declared directory/,
    );
  assert.deepEqual(files(outside), [join("src", "keep.rs")]);
});
