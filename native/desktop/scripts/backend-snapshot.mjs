// Keep Cargo's incremental inputs stable while removing renamed source files.
import {
  copyFileSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  realpathSync,
  rmSync,
} from "node:fs";
import { dirname, isAbsolute, relative, resolve } from "node:path";

export function syncBackendSource(source, destination, buildRoot) {
  const root = realpathSync(buildRoot);
  function owned(path) {
    const rel = relative(root, resolve(path));
    if (!rel || rel.startsWith("..") || isAbsolute(rel))
      throw new Error("Backend snapshot must stay inside the build directory.");
    for (let at = resolve(path); relative(root, at); at = dirname(at)) {
      if (dirname(at) === at)
        throw new Error(
          "Backend snapshot ancestor escaped the build directory.",
        );
      let stat;
      try {
        stat = lstatSync(at);
      } catch (error) {
        if (error.code === "ENOENT") continue;
        throw error;
      }
      if (stat.isSymbolicLink())
        throw new Error("Backend snapshot cannot contain linked paths.");
      const actual = relative(root, realpathSync(at));
      if (!actual || actual.startsWith("..") || isAbsolute(actual))
        throw new Error(
          "Backend snapshot resolves outside its build directory.",
        );
    }
  }
  function copy(from, to) {
    owned(to);
    const kind = lstatSync(from);
    if (kind.isSymbolicLink())
      throw new Error("Backend sources cannot contain linked paths.");
    if (kind.isDirectory()) {
      mkdirSync(to, { recursive: true });
      const names = readdirSync(from);
      for (const stale of readdirSync(to)) {
        if (names.includes(stale)) continue;
        const path = resolve(to, stale);
        owned(path);
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
