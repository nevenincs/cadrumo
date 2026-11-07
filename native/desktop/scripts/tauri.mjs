import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  writeFileSync,
} from "node:fs";
import { delimiter, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { buildPath, readBuildPaths } from "./build-paths.mjs";
import { snapshotHostSources } from "./backend-snapshot.mjs";
import { contentBuild, writeStable } from "./content-build.mjs";
import {
  buildStamp,
  identity as readIdentity,
  profile,
  artifactFile,
  tauriConfig,
} from "./configuration.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const binaryDir = process.env.CADRUMO_CMAKE_BINARY_DIR;
if (!binaryDir || !isAbsolute(binaryDir))
  throw new Error("Select an absolute CMake build directory.");
readBuildPaths(binaryDir, resolve(desktop, "../.."));
const identity = readIdentity();
const selectedProfile = profile();
const action = process.argv[2] ?? "build";
const backendOnly = ["test-unit", "test-package", "clippy-backend"].includes(
  action,
);
const filter = process.argv[3] ?? process.env.CADRUMO_DESKTOP_HOST_TEST_FILTER;
if (
  (backendOnly || action === "test") &&
  (process.argv.length > 4 || filter?.startsWith("-"))
)
  throw new Error("Host tests accept one optional Rust test-name filter.");
const cli = resolve(desktop, "frontend/node_modules/@tauri-apps/cli/tauri.js");
const icons = buildPath("desktop_icons");
const contract = process.env.CADRUMO_NATIVE_CONTRACT;
if (!contract || !isAbsolute(contract))
  throw new Error(
    "Set CADRUMO_NATIVE_CONTRACT to the generated native contract.json.",
  );
const stamp = buildStamp(selectedProfile.debug, identity);
const environment = {
  ...process.env,
  ...selectedProfile.environment,
  // One source snapshot and one target directory for every host action:
  // Cargo keys a path dependency's units by its source path, so a second
  // snapshot or target would compile cadrumo-application and the whole
  // dependency graph again for the backend tests.
  CARGO_TARGET_DIR: buildPath("desktop_cargo"),
  CADRUMO_NATIVE_CONTRACT: contract,
  // The icon the desktop sets for itself where the platform takes none from a bundle.
  CADRUMO_DESKTOP_ICON: resolve(icons, "icon.icns"),
  CADRUMO_CONTRACT_RS: resolve(contract, "../contract.rs"),
  // The linked manager crate embeds the process manifest of this build kind on Windows.
  CADRUMO_PROCESS_MANIFEST: resolve(
    contract,
    `../process-${selectedProfile.debug ? "development" : "release"}.manifest`,
  ),
  CADRUMO_ID_NAME: identity.name,
  CADRUMO_ID_APPLICATION_ID: identity.application_id,
  CADRUMO_ID_VERSION: identity.version,
  CADRUMO_ID_MANAGER_ID: identity.manager_id,
  CADRUMO_ID_MANAGER_NAME: identity.manager_name,
  ...stamp.environment,
};
environment.CARGO_BUILD_BUILD_DIR = environment.CARGO_TARGET_DIR;
environment.CARGO_BUILD_TARGET_DIR = environment.CARGO_TARGET_DIR;
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
/** macOS draws an application icon at the size of its whole canvas, and its own
 * icons keep to Apple's grid: a rounded square 824 points wide, centred in 1024,
 * the rest clear. The tile fills its canvas edge to edge, so on macOS it would
 * stand larger than every icon beside it. The macOS icon sets the tile's artwork
 * in that square instead, over the tile's own ground where its corners differ. */
function macosIconSource(svg) {
  const root = svg.match(/<svg\b[^>]*>/);
  const ground = svg.match(/<path\b[^>]*\bfill="(#[0-9A-Fa-f]{6})"/);
  if (!root || !ground)
    throw new Error("The application icon lacks the tile the macOS icon sets.");
  const placed = root[0]
    .replace(/\s(?:width|height)="[^"]*"/g, "")
    .replace("<svg", '<svg x="100" y="100" width="824" height="824"');
  return [
    '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">',
    '<clipPath id="macos-shape"><rect x="100" y="100" width="824" height="824" rx="185.4"/></clipPath>',
    '<g clip-path="url(#macos-shape)">',
    `<rect x="100" y="100" width="824" height="824" fill="${ground[1]}"/>`,
    svg.replace(/^<\?xml[^>]*>\s*/, "").replace(root[0], placed),
    "</g></svg>",
  ].join("\n");
}
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
  { ...identity, version: stamp.displayVersion },
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
      resolve(desktop, "../../docs/_static/cadrumo-icon.svg"),
      ...readdirSync(resolve(desktop, "frontend/node_modules/@tauri-apps"))
        .filter((name) => name === "cli" || name.startsWith("cli-"))
        .map((name) =>
          resolve(desktop, "frontend/node_modules/@tauri-apps", name),
        ),
      fileURLToPath(new URL("content-build.mjs", import.meta.url)),
    ],
    outputs: [
      icons,
      resolve(icons, "icon.ico"),
      resolve(icons, "icon.png"),
      resolve(icons, "icon.icns"),
    ],
    record: resolve(buildPath("desktop_cache"), "icons-build.json"),
    identity: {
      node: process.version,
      platform: process.platform,
      arch: process.arch,
    },
  },
  () => {
    const source = resolve(desktop, "../../docs/_static/cadrumo-icon.svg");
    run(["icon", source, "--output", icons]);
    const macos = resolve(buildPath("desktop_cache"), "macos-icon");
    mkdirSync(macos, { recursive: true });
    const macosSource = resolve(macos, "icon.svg");
    writeFileSync(macosSource, macosIconSource(readFileSync(source, "utf8")));
    run(["icon", macosSource, "--output", macos]);
    copyFileSync(resolve(macos, "icon.icns"), resolve(icons, "icon.icns"));
  },
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
  if (testing && filter)
    console.error(
      `Only desktop host tests matching "${filter}" run: this is not the whole suite.`,
    );
  const args = testing
    ? [
        "test",
        ...(selectedProfile.debug ? [] : ["--release"]),
        "--locked",
        ...(live ? ["--features", "live-package-tests"] : []),
        ...(filter ? [filter] : []),
        "--",
        "--nocapture",
        "--test-threads=1",
        ...(environment.CADRUMO_PACKAGE_USER_DOCS === "0"
          ? [
              "--skip",
              "docs::tests::staged_documentation_serves_pages_search_and_worker_with_the_policy",
            ]
          : []),
      ]
    : null;
  // The test targets link cadrumo-platform's test-support feature, which that
  // crate refuses to compile in a release build. A release lint therefore
  // covers the binary alone, and every target, tests included, is linted under
  // the dev profile in either configuration.
  const lint = (scope) => [
    "clippy",
    ...scope,
    "--locked",
    ...(live ? ["--features", "live-package-tests"] : []),
    "--",
    "-D",
    "warnings",
  ];
  const invocations = args
    ? [args]
    : selectedProfile.debug
      ? [lint(["--all-targets"])]
      : [lint(["--release", "--bins"]), lint(["--all-targets"])];
  for (const invocation of invocations) {
    const result = spawnSync("cargo", invocation, {
      cwd: snapshot.crate,
      env: { ...environment, TAURI_CONFIG: JSON.stringify(config) },
      stdio: "inherit",
      windowsHide: true,
    });
    if (result.error) throw result.error;
    if (result.status !== 0) process.exit(result.status ?? 1);
  }
  process.exit(0);
} else {
  throw new Error(`Unknown host action: ${action}`);
}
