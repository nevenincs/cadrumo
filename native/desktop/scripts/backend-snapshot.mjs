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
import { dirname, isAbsolute, relative, resolve } from "node:path";

// The host manifest names its sibling crates by relative path. The copies keep
// the source tree's layout beneath one root so those paths resolve unchanged
// and no copy lands beside the directory the build declares.
const HOST_CRATE = "desktop/src-tauri";
const HOST_CRATE_ENTRIES = ["Cargo.toml", "Cargo.lock", "build.rs", "src"];
const PATH_CRATES = ["application", "platform"];

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

export function syncBackendSource(source, destination, buildRoot) {
  const root = realpathSync(buildRoot);
  function copy(from, to) {
    owned(root, to);
    const kind = lstatSync(from);
    if (kind.isSymbolicLink())
      throw new Error("Backend sources cannot contain linked paths.");
    if (kind.isDirectory()) {
      mkdirSync(to, { recursive: true });
      const names = readdirSync(from);
      for (const stale of readdirSync(to)) {
        if (names.includes(stale)) continue;
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
  { incremental = false } = {},
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
    ...HOST_CRATE_ENTRIES.map((entry) => `${HOST_CRATE}/${entry}`),
  ]) {
    const source = resolve(native, member);
    const destination = resolve(layout.root, member);
    if (incremental) syncBackendSource(source, destination, layout.root);
    else {
      owned(layout.root, destination);
      cpSync(source, destination, { recursive: true });
    }
  }
  return layout;
}
