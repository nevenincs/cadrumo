// Explicit, process-local selection of an immutable prepared image. No staging.
import { createHash } from "node:crypto";
import { lstatSync, readFileSync, readdirSync, realpathSync } from "node:fs";
import { isAbsolute, relative, resolve, sep, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { readBuildPaths } from "../../scripts/build-paths.mjs";

const repository = realpathSync(
  fileURLToPath(new URL("../../../../", import.meta.url)),
);
let active;
export const digest = (bytes) =>
  createHash("sha256").update(bytes).digest("hex");
export const fileDigest = (file) => digest(readFileSync(file));
export function physicalMember(root, path) {
  if (!isAbsolute(path) || path.split(/[\\/]/).includes(".."))
    throw new Error("Invalid frozen member path");
  const member = relative(root, path);
  if (member === ".." || member.startsWith(`..${sep}`) || isAbsolute(member))
    throw new Error("Frozen member escapes root");
  let current = root;
  for (const part of ["", ...member.split(sep)]) {
    current = resolve(current, part);
    if (
      lstatSync(current).isSymbolicLink() ||
      realpathSync(current).toLowerCase() !== current.toLowerCase()
    )
      throw new Error(`Linked frozen member: ${current}`);
  }
  return path;
}
/** Complete sorted inventories include directories and refuse every link. */
export function inventory(root) {
  physicalMember(dirname(root), root);
  const result = [];
  function visit(path, name) {
    const stat = lstatSync(path, { bigint: true });
    if (stat.isSymbolicLink()) throw new Error(`Linked frozen member: ${path}`);
    if (stat.isDirectory()) {
      result.push([name, "directory"]);
      for (const child of readdirSync(path).sort())
        visit(resolve(path, child), name ? `${name}/${child}` : child);
    } else if (stat.isFile()) {
      // A multiply linked image could let a later source edit mutate this image.
      if (stat.nlink !== 1n)
        throw new Error(`Hardlinked frozen member: ${path}`);
      result.push([name, "file", String(stat.size), fileDigest(path)]);
    } else throw new Error(`Unsupported frozen member: ${path}`);
  }
  visit(root, "");
  return result;
}
function keys(value, names) {
  if (
    !value ||
    JSON.stringify(Object.keys(value).sort()) !==
      JSON.stringify([...names].sort())
  )
    throw new Error("Malformed or extra frozen record members");
}
export function frozenRoots(build, source = repository) {
  const paths = readBuildPaths(build, source);
  return {
    stage: resolve(paths.stage, "Debug/app"),
    mirror: resolve(paths.desktop_testing, "agent-live-package/Debug/app"),
    hostRecord: resolve(paths.desktop_testing, "packaged/host.json"),
    configuration: resolve(
      paths.desktop_testing,
      "packaged/host/desktop/src-tauri/tauri.conf.json",
    ),
  };
}
/** Conservative source/helper and built-record closure; Src is deliberately absent. */
export function protectedFiles(build, source = repository) {
  const paths = readBuildPaths(build, source);
  const files = new Set();
  function walk(root, accept = () => true) {
    physicalMember(source, root);
    if (lstatSync(root).isSymbolicLink())
      throw new Error(`Linked protected input: ${root}`);
    for (const name of readdirSync(root).sort()) {
      const path = resolve(root, name);
      const stat = lstatSync(path);
      if (stat.isSymbolicLink())
        throw new Error(`Linked protected input: ${path}`);
      if (stat.isDirectory()) walk(path, accept);
      else if (accept(path)) files.add(path);
    }
  }
  physicalMember(source, build);
  walk(resolve(source, "native/desktop/scripts"), (p) => p.endsWith(".mjs"));
  walk(resolve(source, "native/desktop/tests/packaged"), (p) =>
    /\.(mjs|py)$/.test(p),
  );
  walk(paths.generated);
  walk(paths.desktop_frontend_generated);
  walk(resolve(paths.desktop_testing, "packaged/host"));
  walk(resolve(paths.desktop_testing, "packaged/cargo/debug/.fingerprint"));
  walk(resolve(source, "native/desktop/frontend/node_modules/playwright-core"));
  walk(resolve(source, "native/desktop/frontend/node_modules/@xterm/xterm"));
  for (const member of [
    "CMakePresets.json",
    "native/desktop/tests/packaged.test.mjs",
    "native/desktop/frontend/package.json",
    "native/desktop/frontend/package-lock.json",
    ".tmp/2026-11-03-checks/frozen-image-record.mjs",
    ".tmp/2026-11-03-checks/frozen-image-runner.mjs",
    ".tmp/2026-11-03-checks/frozen-image-run.ps1",
  ])
    files.add(resolve(source, member));
  for (const member of [
    "CMakeCache.txt",
    "build-paths.json",
    "desktop/testing/packaged/host.json",
    "desktop/testing/packaged/cargo/debug/cadrumo.exe",
  ])
    files.add(resolve(build, member));
  return [...files].sort();
}
/** Validate bytes before interpreting JSON; canonical encoding also rejects duplicate keys. */
export function validateFrozenRecord(
  path,
  expectedHash,
  { source = repository } = {},
) {
  if (!/^[a-f0-9]{64}$/.test(expectedHash))
    throw new Error("Missing frozen record hash");
  const bytes = readFileSync(path);
  if (digest(bytes) !== expectedHash)
    throw new Error("Frozen record hash mismatch");
  const record = JSON.parse(bytes);
  if (JSON.stringify(record) !== bytes.toString())
    throw new Error("Noncanonical or duplicate frozen record members");
  keys(record, [
    "schema",
    "build",
    "roots",
    "trees",
    "files",
    "applicationCohort",
    "inputHelper",
  ]);
  if (record.schema !== 1) throw new Error("Unknown frozen record schema");
  const paths = readBuildPaths(record.build, source);
  physicalMember(resolve(paths.desktop_testing, "frozen-image-runner"), path);
  if (
    JSON.stringify(record.roots) !==
    JSON.stringify(frozenRoots(record.build, source))
  )
    throw new Error("Wrong frozen roots");
  keys(record.trees, [record.roots.stage, record.roots.mirror]);
  for (const [root, wanted] of Object.entries(record.trees)) {
    if (JSON.stringify(inventory(root)) !== JSON.stringify(wanted))
      throw new Error(`Frozen inventory changed: ${root}`);
  }
  if (!Array.isArray(record.files) || !record.files.length)
    throw new Error("Missing protected harness inputs");
  if (
    JSON.stringify(record.files.map((pair) => pair[0])) !==
    JSON.stringify(protectedFiles(record.build, source))
  )
    throw new Error("Protected input closure changed");
  const seen = new Set();
  for (const pair of record.files) {
    if (!Array.isArray(pair) || pair.length !== 2 || seen.has(pair[0]))
      throw new Error("Duplicate or malformed protected input");
    seen.add(pair[0]);
    physicalMember(source, pair[0]);
    if (fileDigest(pair[0]) !== pair[1])
      throw new Error(`Protected input changed: ${pair[0]}`);
  }
  const host = JSON.parse(readFileSync(record.roots.hostRecord, "utf8"));
  if (
    host.variant !== "packaged" ||
    host.shell !== null ||
    host.configuration !== "Debug" ||
    JSON.stringify([...host.features].sort()) !==
      JSON.stringify(["native-automation", "webview2-remote-debugging"])
  )
    throw new Error("Wrong frozen host features/configuration");
  physicalMember(
    resolve(paths.desktop_testing, "packaged/cargo"),
    host.executable,
  );
  if (
    fileDigest(host.executable) !== host.sha256 ||
    fileDigest(resolve(record.roots.mirror, "cadrumo.exe")) !== host.sha256
  )
    throw new Error("Wrong frozen automation host hash");
  for (const file of [
    record.roots.hostRecord,
    record.roots.configuration,
    host.executable,
    resolve(record.build, "build-paths.json"),
    resolve(paths.generated, "contract.json"),
    resolve(paths.desktop_frontend_generated, "chrome-strings.json"),
  ])
    if (!seen.has(file)) throw new Error(`Unpinned required input: ${file}`);
  return {
    record,
    host: Object.freeze({
      ...host,
      features: Object.freeze([...host.features]),
      executable: resolve(record.roots.mirror, "cadrumo.exe"),
      package: record.roots.mirror,
    }),
  };
}
export function activateFrozenHost(path, hash) {
  if (active) throw new Error("Frozen host activation is immutable");
  validateFrozenRecord(path, hash);
  active = Object.freeze({ path, hash });
}
export function frozenHostSelection(variant) {
  if (!active) return null;
  if (variant !== "packaged")
    throw new Error("Frozen host refuses served variant");
  const { record, host } = validateFrozenRecord(active.path, active.hash);
  if (
    process.env.CADRUMO_CMAKE_BINARY_DIR !== record.build ||
    process.env.CADRUMO_BUILD_CONFIG !== "Debug" ||
    process.env.CADRUMO_DESKTOP_PACKAGE_ROOT !== record.roots.stage
  )
    throw new Error("Frozen host environment mismatch");
  return host;
}
