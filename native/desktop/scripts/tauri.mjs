import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  writeFileSync,
} from "node:fs";
import { delimiter, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { buildPath } from "./build-paths.mjs";
import { snapshotHostSources } from "./backend-snapshot.mjs";
import { contentBuild, writeStable } from "./content-build.mjs";
import {
  identity as readIdentity,
  profile,
  artifactFile,
  executable,
  tauriConfig,
} from "./configuration.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const binaryDir = process.env.CADRUMO_CMAKE_BINARY_DIR;
if (!binaryDir || !isAbsolute(binaryDir))
  throw new Error("Select an absolute CMake build directory.");
const identity = readIdentity();
const selectedProfile = profile();
const action = process.argv[2] ?? "build";
const backendOnly = ["test-unit", "test-package", "clippy-backend"].includes(
  action,
);
const filter = process.argv[3];
if (backendOnly && (process.argv.length > 4 || filter?.startsWith("-")))
  throw new Error("Backend tests accept one optional Rust test-name filter.");
if (action === "run") {
  const result = spawnSync(executable(), process.argv.slice(3), {
    stdio: "inherit",
    windowsHide: true,
  });
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
}
const cli = resolve(desktop, "frontend/node_modules/@tauri-apps/cli/tauri.js");
const icons = buildPath("desktop_icons");
const contract = process.env.CADRUMO_NATIVE_CONTRACT;
if (!contract || !isAbsolute(contract))
  throw new Error(
    "Set CADRUMO_NATIVE_CONTRACT to the generated native contract.json.",
  );
const environment = {
  ...process.env,
  ...selectedProfile.environment,
  CARGO_TARGET_DIR:
    backendOnly && process.env.CARGO_TARGET_DIR
      ? process.env.CARGO_TARGET_DIR
      : buildPath("desktop_cargo"),
  CADRUMO_NATIVE_CONTRACT: contract,
  CADRUMO_CONTRACT_RS: resolve(contract, "../contract.rs"),
};
if (process.env.CADRUMO_DESKTOP_RUST_BIN) {
  const pathKey =
    Object.keys(environment).find((key) => key.toUpperCase() === "PATH") ??
    "PATH";
  environment[pathKey] =
    process.env.CADRUMO_DESKTOP_RUST_BIN +
    delimiter +
    (environment[pathKey] ?? "");
}
// Preserve Cargo's input timestamps while synchronizing additions and removals.
const snapshot = snapshotHostSources(
  resolve(desktop, ".."),
  buildPath("desktop_host"),
  { incremental: true },
);
function run(args) {
  const result = spawnSync(process.execPath, [cli, ...args], {
    cwd: snapshot.project,
    stdio: "inherit",
    windowsHide: true,
    env: environment,
  });
  if (result.error) throw result.error;
  if (result.status !== 0)
    throw new Error(`Tauri ${args[0]} failed: ${result.status}`);
}
const configDirectory = snapshot.crate;
// tauri-build watches this directory even when no capabilities are declared.
// A missing watched path makes Cargo rerun the build script on every test.
mkdirSync(resolve(configDirectory, "capabilities"), { recursive: true });
// Rust host tests exercise the real modules, not a compiled frontend. The
// inert asset exists only in this test snapshot and is never staged.
const frontend = backendOnly
  ? resolve(buildPath("desktop_testing"), "backend-assets")
  : buildPath("desktop_frontend");
if (backendOnly) {
  mkdirSync(frontend, { recursive: true });
  if (!existsSync(resolve(frontend, "index.html")))
    writeFileSync(
      resolve(frontend, "index.html"),
      "<!doctype html><title>Backend test fixture</title>",
    );
}
const config = tauriConfig(
  JSON.parse(
    readFileSync(resolve(desktop, "src-tauri/tauri.conf.json.in"), "utf8"),
  ),
  identity,
  { configDirectory, frontend, icons },
);
const configFile = resolve(configDirectory, "tauri.conf.json");
const configText = JSON.stringify(config, null, 2);
writeStable(configFile, configText);
contentBuild(
  {
    inputs: [
      process.execPath,
      fileURLToPath(import.meta.url),
      resolve(desktop, "../../docs/_static/cadrumo-favicon.svg"),
      ...readdirSync(resolve(desktop, "frontend/node_modules/@tauri-apps"))
        .filter((name) => name === "cli" || name.startsWith("cli-"))
        .map((name) =>
          resolve(desktop, "frontend/node_modules/@tauri-apps", name),
        ),
      fileURLToPath(new URL("content-build.mjs", import.meta.url)),
    ],
    outputs: [icons, resolve(icons, "icon.ico"), resolve(icons, "icon.png")],
    record: resolve(buildPath("desktop_cache"), "icons-build.json"),
    identity: {
      node: process.version,
      platform: process.platform,
      arch: process.arch,
    },
  },
  () =>
    run([
      "icon",
      resolve(desktop, "../../docs/_static/cadrumo-favicon.svg"),
      "--output",
      icons,
    ]),
);
if (action === "prepare") process.exit(0);
if (action === "build") {
  run([
    "build",
    "--no-bundle",
    ...(selectedProfile.debug ? ["--debug"] : []),
    "--",
    "--locked",
  ]);
  const metadata = spawnSync(
    "cargo",
    ["metadata", "--no-deps", "--locked", "--format-version", "1"],
    {
      cwd: snapshot.crate,
      env: environment,
      encoding: "utf8",
      windowsHide: true,
    },
  );
  if (metadata.error) throw metadata.error;
  if (metadata.status !== 0) throw new Error(metadata.stderr);
  const manifest = resolve(snapshot.crate, "Cargo.toml");
  const owner = JSON.parse(metadata.stdout).packages.find(
    (pkg) => resolve(pkg.manifest_path) === manifest,
  );
  const binaries = owner?.targets.filter((target) =>
    target.kind.includes("bin"),
  );
  if (binaries?.length !== 1)
    throw new Error("Desktop manifest must declare exactly one executable");
  const built = resolve(
    buildPath("desktop_cargo"),
    selectedProfile.directory,
    binaries[0].name + (process.platform === "win32" ? ".exe" : ""),
  );
  // CMake declares this image for package staging; a renamed Cargo binary must not stage a stale file.
  const declared = process.env.CADRUMO_DESKTOP_HOST_EXECUTABLE;
  if (!declared || !isAbsolute(declared))
    throw new Error(
      "Set CADRUMO_DESKTOP_HOST_EXECUTABLE to the host image CMake declares.",
    );
  const same =
    process.platform === "win32"
      ? resolve(declared).toLowerCase() === built.toLowerCase()
      : resolve(declared) === built;
  if (!same)
    throw new Error(
      `The Cargo host image ${built} differs from the CMake declaration ${declared}.`,
    );
  writeStable(artifactFile(), JSON.stringify({ executable: built }));
} else if (action === "test" || action === "clippy" || backendOnly) {
  const testing = ["test", "test-unit", "test-package"].includes(action);
  const live = ["test", "test-package", "clippy"].includes(action);
  const args = testing
    ? [
        "test",
        ...(selectedProfile.debug ? [] : ["--release"]),
        "--locked",
        ...(live ? ["--features", "live-package-tests"] : []),
        ...(backendOnly && filter ? [filter] : []),
        "--",
        "--nocapture",
        "--test-threads=1",
      ]
    : [
        "clippy",
        ...(selectedProfile.debug ? [] : ["--release"]),
        "--locked",
        "--all-targets",
        ...(live ? ["--features", "live-package-tests"] : []),
        "--",
        "-D",
        "warnings",
      ];
  const result = spawnSync("cargo", args, {
    cwd: snapshot.crate,
    env: { ...environment, TAURI_CONFIG: JSON.stringify(config) },
    stdio: "inherit",
    windowsHide: true,
  });
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
} else {
  throw new Error(`Unknown host action: ${action}`);
}
