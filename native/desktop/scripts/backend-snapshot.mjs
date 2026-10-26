// Keep Cargo's incremental inputs stable while removing renamed source files.
import {
  copyFileSync,
  cpSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  realpathSync,
  rmSync,
} from "node:fs";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";

// The host manifest names its sibling crates by relative path. The copies keep
// the source tree's layout beneath one root so those paths resolve unchanged
// and no copy lands beside the directory the build declares.
const HOST_CRATE = "desktop/src-tauri";
const HOST_CRATE_ENTRIES = ["Cargo.toml", "Cargo.lock", "build.rs", "src"];
const PATH_CRATES = [
  "application",
  "platform",
  "installer",
  "manager",
  "launch_guard",
  "interpreter_host",
];
// The interpreter host crate compiles these C host sources into the Cadrumo binary.
const INTERPRETER_SOURCES = [
  "interpreter/windows/host.manifest",
  "interpreter/windows/host.c",
  "interpreter/launch_guard.h",
  "interpreter/launch_profile.h",
];
// The host's tests carry real Modelo forms' admitted edit baselines through
// the bridge and the relay, and check the committed write envelopes against
// the host's own reduction: envelopes the product's own producers wrote. Only
// a snapshot for the host's tests copies them.
export const HOST_TEST_INPUTS = [
  "desktop/frontend/src/dev/fixtures/modelo/modelo-303-1T-en.json",
  "desktop/frontend/src/dev/fixtures/modelo/modelo-347-0A-en.json",
  "desktop/frontend/src/dev/fixtures/modelo/export-130.json",
  "desktop/frontend/src/dev/fixtures/modelo/export-165-unverified.json",
  "desktop/frontend/src/dev/fixtures/modelo/reconcile-130.json",
];

export function hostSnapshot(root) {
  return {
    root,
    // The Tauri CLI runs where src-tauri is a child.
    project: resolve(root, dirname(HOST_CRATE)),
    crate: resolve(root, HOST_CRATE),
    crates: PATH_CRATES.map((crate) => resolve(root, crate)),
  };
}

function owned(root, path) {
  const rel = relative(root, resolve(path));
  if (!rel || rel.startsWith("..") || isAbsolute(rel))
    throw new Error(
      "Generated sources must stay inside their declared directory.",
    );
  for (let at = resolve(path); relative(root, at); at = dirname(at)) {
    if (dirname(at) === at)
      throw new Error(
        "Generated source ancestor escaped its declared directory.",
      );
    let stat;
    try {
      stat = lstatSync(at);
    } catch (error) {
      if (error.code === "ENOENT") continue;
      throw error;
    }
    if (stat.isSymbolicLink())
      throw new Error("Generated sources cannot contain linked paths.");
    const actual = relative(root, realpathSync(at));
    if (!actual || actual.startsWith("..") || isAbsolute(actual))
      throw new Error(
        "Generated sources resolve outside their declared directory.",
      );
  }
}

export function syncBackendSource(
  source,
  destination,
  buildRoot,
  excluded = [],
) {
  const root = realpathSync(buildRoot);
  function copy(from, to) {
    owned(root, to);
    const kind = lstatSync(from);
    if (kind.isSymbolicLink())
      throw new Error("Backend sources cannot contain linked paths.");
    if (kind.isDirectory()) {
      mkdirSync(to, { recursive: true });
      const ignored = resolve(from) === resolve(source) ? excluded : [];
      const names = readdirSync(from).filter((name) => !ignored.includes(name));
      for (const stale of readdirSync(to)) {
        if (names.includes(stale) || ignored.includes(stale)) continue;
        const path = resolve(to, stale);
        owned(root, path);
        rmSync(path, { recursive: true });
      }
      for (const name of names) copy(resolve(from, name), resolve(to, name));
    } else if (kind.isFile()) {
      if (existsSync(to) && readFileSync(from).equals(readFileSync(to))) return;
      mkdirSync(dirname(to), { recursive: true });
      copyFileSync(from, to);
    } else {
      throw new Error("Backend sources must be regular files or directories.");
    }
  }
  copy(resolve(source), resolve(destination));
}

/**
 * Copies the host crate and the crates it names by path from the `native`
 * source directory into `root`, and returns where they are. An incremental
 * snapshot rewrites only changed files; a full one replaces each source
 * directory.
 */
export function snapshotHostSources(
  native,
  root,
  { incremental = false, tests = false } = {},
) {
  mkdirSync(root, { recursive: true });
  if (lstatSync(root).isSymbolicLink())
    throw new Error("Generated sources cannot contain linked paths.");
  const layout = hostSnapshot(realpathSync(root));
  // Remove only generated source copies so renamed Rust modules cannot survive a rebuild.
  for (const crate of incremental ? [] : [layout.crate, ...layout.crates]) {
    const sources = resolve(crate, "src");
    if (!existsSync(sources)) continue;
    owned(layout.root, sources);
    rmSync(sources, { recursive: true });
  }
  owned(layout.root, layout.crate);
  mkdirSync(layout.crate, { recursive: true });
  for (const member of [
    ...PATH_CRATES,
    ...INTERPRETER_SOURCES,
    ...(tests ? HOST_TEST_INPUTS : []),
    ...HOST_CRATE_ENTRIES.map((entry) => `${HOST_CRATE}/${entry}`),
  ]) {
    const source = resolve(native, member);
    const destination = resolve(layout.root, member);
    // Local compiler output is not a source dependency. In particular a
    // leftover Cargo target tree can contain gigabytes and thousands of files.
    const excluded = PATH_CRATES.includes(member) ? ["target", ".exe"] : [];
    if (incremental)
      syncBackendSource(source, destination, layout.root, excluded);
    else {
      owned(layout.root, destination);
      cpSync(source, destination, {
        recursive: true,
        filter: (path) =>
          !excluded.includes(relative(source, path).split(sep)[0]),
      });
    }
  }
  return layout;
}
