// A clean install deletes node_modules before it writes it again, which breaks
// every process running from that tree. Every binary directory shares the one
// tree, so the evidence that it is current is the record npm leaves inside it,
// not a stamp in any build directory.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// npm records every package it placed here, with the lockfile's own entry.
const RECORD = "node_modules/.package-lock.json";
const IDENTITY = ["version", "resolved", "integrity"];
const DECLARED = [
  "dependencies",
  "devDependencies",
  "optionalDependencies",
  "peerDependencies",
];

// npm's rule for the os, cpu and libc lists: no negated value may match, and
// one plain value must when any is listed.
function admits(value, list) {
  if (list === undefined) return true;
  const entries = typeof list === "string" ? [list] : list;
  if (entries.length === 1 && entries[0] === "any") return true;
  let negated = 0;
  let match = false;
  for (const entry of entries) {
    if (entry.startsWith("!")) {
      negated++;
      if (value === entry.slice(1)) return false;
    } else match ||= value === entry;
  }
  return match || negated === entries.length;
}

function libc() {
  if (process.platform !== "linux") return undefined;
  try {
    const ldd = readFileSync("/usr/bin/ldd", "utf8");
    if (ldd.includes("musl")) return "musl";
    if (ldd.includes("GNU C Library")) return "glibc";
    return undefined;
  } catch {
    // The report otherwise resolves every network interface's name.
    const excluded = process.report.excludeNetwork;
    process.report.excludeNetwork = true;
    const report = process.report.getReport();
    process.report.excludeNetwork = excluded;
    if (report.header?.glibcVersionRuntime) return "glibc";
    const musl = (file) =>
      file.includes("libc.musl-") || file.includes("ld-musl-");
    return report.sharedObjects?.some(musl) ? "musl" : undefined;
  }
}

export function currentPlatform() {
  return { os: process.platform, cpu: process.arch, libc: libc() };
}

function packages(file) {
  try {
    const value = JSON.parse(readFileSync(file, "utf8")).packages;
    const entries = Object.values(value);
    return entries.every((entry) => entry && typeof entry === "object")
      ? value
      : undefined;
  } catch {
    return undefined;
  }
}

function dependency(locked, from, name) {
  for (let at = from; ;) {
    const candidate = `${at ? `${at}/` : ""}node_modules/${name}`;
    if (Object.hasOwn(locked, candidate)) return candidate;
    if (!at) return undefined;
    const parent = at.lastIndexOf("node_modules/");
    at = parent > 0 ? at.slice(0, parent - 1) : "";
  }
}

// An optional edge may go unresolved; a peer binds its dependent only when the
// lockfile placed it; any other edge must resolve.
function edges(entry, root) {
  const optional = entry.optionalDependencies ?? {};
  const meta = entry.peerDependenciesMeta ?? {};
  const found = new Map();
  for (const name of Object.keys(entry.peerDependencies ?? {}))
    found.set(name, meta[name]?.optional ? "optional" : "peer");
  for (const name of Object.keys(entry.dependencies ?? {}))
    found.set(name, "required");
  if (root)
    for (const name of Object.keys(entry.devDependencies ?? {}))
      found.set(name, "required");
  for (const name of Object.keys(optional)) found.set(name, "optional");
  return found;
}

// The packages npm installs from this lockfile on this platform. npm leaves out
// an optional package the platform excludes, each optional package that needs
// it, and whatever only those reach; the record lists none of them. npm also
// leaves out an optional package whose engines exclude this Node or whose
// install fails. Those are not modelled, so such a tree is installed each time.
function installable(locked, platform) {
  const verdicts = new Map();
  function admitted(location) {
    if (verdicts.has(location)) return verdicts.get(location);
    const entry = locked[location];
    if (!entry.optional) return true;
    // A cycle cannot exclude itself.
    verdicts.set(location, true);
    let verdict =
      admits(platform.os, entry.os) &&
      admits(platform.cpu, entry.cpu) &&
      (entry.libc === undefined ||
        (Boolean(platform.libc) && admits(platform.libc, entry.libc)));
    for (const [name, kind] of edges(entry, false)) {
      if (!verdict) break;
      if (kind === "optional") continue;
      const target = dependency(locked, location, name);
      if (target) verdict = admitted(target);
    }
    verdicts.set(location, verdict);
    return verdict;
  }
  const reached = new Set([""]);
  for (const location of reached) {
    for (const [name, kind] of edges(locked[location], location === "")) {
      const target = dependency(locked, location, name);
      if (!target) {
        if (kind === "required")
          return { unresolved: `${location || "the root package"}: ${name}` };
        continue;
      }
      if (admitted(target)) reached.add(target);
    }
  }
  reached.delete("");
  return { locations: reached };
}

function maps(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}

// The first dependency package.json and the lockfile's root entry declare
// differently. A clean install refuses such a pair, and only running it says
// so. npm records an empty map as absent, and a dependency that is also
// optional only as optional.
function undeclared(manifest, root) {
  const optional = maps(manifest.optionalDependencies);
  for (const kind of DECLARED) {
    const wanted = { ...maps(manifest[kind]) };
    if (kind === "dependencies")
      for (const name of Object.keys(optional)) delete wanted[name];
    const written = maps(root[kind]);
    for (const name of [...Object.keys(wanted), ...Object.keys(written)])
      if (wanted[name] !== written[name]) return `${kind}.${name}`;
  }
  return undefined;
}

/**
 * Whether the frontend's installed tree must be replaced to match its lockfile.
 * It reads the manifest and the two lockfiles and tests that each installed
 * package is present; it changes nothing.
 */
export function installDecision(frontend, platform = currentPlatform()) {
  const install = (reason) => ({ install: true, reason });
  const locked = packages(resolve(frontend, "package-lock.json"));
  if (!locked?.[""])
    return install("package-lock.json is missing or unreadable");
  let manifest;
  try {
    manifest = JSON.parse(
      readFileSync(resolve(frontend, "package.json"), "utf8"),
    );
  } catch {
    manifest = undefined;
  }
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest))
    return install("package.json is missing or unreadable");
  const drift = undeclared(manifest, locked[""]);
  if (drift)
    return install(
      `package.json and package-lock.json declare ${drift} differently`,
    );
  const recorded = packages(resolve(frontend, RECORD));
  if (!recorded) return install(`${RECORD} is missing or unreadable`);
  for (const [location, entry] of Object.entries(recorded)) {
    if (!Object.hasOwn(locked, location))
      return install(`${location} is installed but not locked`);
    for (const key of IDENTITY)
      if (entry[key] !== locked[location][key])
        return install(
          `${location} is installed with another ${key} than locked`,
        );
  }
  const { locations, unresolved } = installable(locked, platform);
  if (unresolved)
    return install(`package-lock.json does not place ${unresolved}`);
  for (const location of locations)
    if (!Object.hasOwn(recorded, location))
      return install(`${location} is locked but not installed`);
  for (const location of locations)
    if (!existsSync(resolve(frontend, location, "package.json")))
      return install(`${location} is recorded but absent`);
  return {
    install: false,
    reason: `${locations.size} installed packages match package-lock.json`,
  };
}

/**
 * Runs the clean install with this Node binary when the tree needs it, says in
 * one line which it did and why, and returns the exit status.
 */
export function ensureInstalled(frontend, npmCli, cleanInstall) {
  const decision = installDecision(frontend);
  if (!decision.install) {
    console.log(`Frontend dependencies: kept, ${decision.reason}.`);
    return 0;
  }
  console.log(`Frontend dependencies: reinstalling, ${decision.reason}.`);
  const result = spawnSync(process.execPath, [npmCli, ...cleanInstall], {
    cwd: frontend,
    stdio: "inherit",
    windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) return result.status ?? 1;
  const after = installDecision(frontend);
  // Without this the next build would delete the tree again and say nothing.
  if (after.install)
    console.warn(
      `Frontend dependencies still differ after the install: ${after.reason}.`,
    );
  return 0;
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const [npmCli, ...cleanInstall] = process.argv.slice(2);
  if (!npmCli || !isAbsolute(npmCli) || !cleanInstall.length)
    throw new Error(
      "Pass the absolute npm CLI and its clean-install arguments.",
    );
  process.exit(
    ensureInstalled(
      fileURLToPath(new URL("../frontend/", import.meta.url)),
      npmCli,
      cleanInstall,
    ),
  );
}
