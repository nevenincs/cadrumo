// Builds the host for the packaged end-to-end test: the shipped sources with
// the `webview2-remote-debugging` feature, which admits exactly one
// `--remote-debugging-port=<port>` in WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS.
// It has its own source snapshot and Cargo directory under the desktop testing
// directory, so it never replaces the image desktop-host-build declares for
// packaging, and it is never staged, packaged or distributed.
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { delimiter, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { buildPath } from "../../scripts/build-paths.mjs";
import {
  identity as readIdentity,
  profile,
  tauriConfig,
} from "../../scripts/configuration.mjs";

export const FEATURE = "webview2-remote-debugging";
const BINARY = "cadrumo";

/** The directories this test host owns, all inside the desktop testing directory. */
export function packagedHostPaths() {
  const root = resolve(buildPath("desktop_testing"), "packaged");
  return {
    root,
    snapshot: resolve(root, "host"),
    cargo: resolve(root, "cargo"),
    icons: resolve(root, "icons"),
    record: resolve(root, "host.json"),
  };
}

/** The test host recorded by the last build, refused when it no longer matches. */
export function packagedHost() {
  const { record, cargo } = packagedHostPaths();
  const value = JSON.parse(readFileSync(record, "utf8"));
  if (
    typeof value.executable !== "string" ||
    !isAbsolute(value.executable) ||
    !resolve(value.executable).startsWith(cargo) ||
    !value.features?.includes(FEATURE)
  )
    throw new Error(`The packaged test host record is invalid: ${record}`);
  if (sha256(value.executable) !== value.sha256)
    throw new Error("The packaged test host changed after it was recorded.");
  return value;
}

function sha256(file) {
  return createHash("sha256").update(readFileSync(file)).digest("hex");
}

/** The features Cargo compiled the desktop binary with, from its fingerprint. */
function compiledFeatures(cargo, directory) {
  const fingerprints = resolve(cargo, directory, ".fingerprint");
  const found = new Set();
  for (const entry of readdirSync(fingerprints)) {
    if (!entry.startsWith("cadrumo-desktop-")) continue;
    const file = resolve(fingerprints, entry, `bin-${BINARY}.json`);
    if (!existsSync(file)) continue;
    const features = JSON.parse(
      JSON.parse(readFileSync(file, "utf8")).features,
    );
    found.add(JSON.stringify([...features].sort()));
  }
  return [...found].map((text) => JSON.parse(text));
}

function build() {
  const desktop = fileURLToPath(new URL("../../", import.meta.url));
  const paths = packagedHostPaths();
  const selected = profile();
  const contract = process.env.CADRUMO_NATIVE_CONTRACT;
  if (!contract || !isAbsolute(contract))
    throw new Error(
      "Set CADRUMO_NATIVE_CONTRACT to the generated native contract.json.",
    );
  // Remove only the generated source copies, as the shipped build does.
  for (const directory of [
    resolve(paths.snapshot, "src-tauri/src"),
    resolve(paths.snapshot, "../application/src"),
    resolve(paths.snapshot, "../platform/src"),
  ])
    if (existsSync(directory)) rmSync(directory, { recursive: true });
  mkdirSync(resolve(paths.snapshot, "src-tauri"), { recursive: true });
  for (const crate of ["application", "platform"])
    cpSync(
      resolve(desktop, "..", crate),
      resolve(paths.snapshot, "..", crate),
      {
        recursive: true,
      },
    );
  for (const entry of ["Cargo.toml", "Cargo.lock", "build.rs", "src"])
    cpSync(
      resolve(desktop, "src-tauri", entry),
      resolve(paths.snapshot, "src-tauri", entry),
      { recursive: true },
    );
  const configDirectory = resolve(paths.snapshot, "src-tauri");
  const config = tauriConfig(
    JSON.parse(
      readFileSync(resolve(desktop, "src-tauri/tauri.conf.json.in"), "utf8"),
    ),
    readIdentity(),
    {
      configDirectory,
      frontend: buildPath("desktop_frontend"),
      icons: paths.icons,
    },
  );
  writeFileSync(
    resolve(configDirectory, "tauri.conf.json"),
    JSON.stringify(config, null, 2),
  );
  const environment = {
    ...process.env,
    ...selected.environment,
    CARGO_TARGET_DIR: paths.cargo,
    CADRUMO_NATIVE_CONTRACT: contract,
    CADRUMO_CONTRACT_RS: resolve(contract, "../contract.rs"),
  };
  if (process.env.CADRUMO_DESKTOP_RUST_BIN) {
    const key =
      Object.keys(environment).find((name) => name.toUpperCase() === "PATH") ??
      "PATH";
    environment[key] =
      process.env.CADRUMO_DESKTOP_RUST_BIN +
      delimiter +
      (environment[key] ?? "");
  }
  const cli = resolve(
    desktop,
    "frontend/node_modules/@tauri-apps/cli/tauri.js",
  );
  const run = (args) => {
    const result = spawnSync(process.execPath, [cli, ...args], {
      cwd: paths.snapshot,
      env: environment,
      stdio: "inherit",
      windowsHide: true,
    });
    if (result.error) throw result.error;
    if (result.status !== 0) process.exit(result.status ?? 1);
  };
  run([
    "icon",
    resolve(desktop, "../../docs/_static/cadrumo-favicon.svg"),
    "--output",
    paths.icons,
  ]);
  // `tauri build`, unlike a plain Cargo build, enables custom-protocol, so the
  // host is a packaged build: it serves the documentation from the package
  // and enforces the WebView2 environment check.
  run([
    "build",
    "--no-bundle",
    ...(selected.debug ? ["--debug"] : []),
    "--features",
    FEATURE,
    "--",
    "--locked",
  ]);
  const executable = resolve(
    paths.cargo,
    selected.directory,
    BINARY + (process.platform === "win32" ? ".exe" : ""),
  );
  const compiled = compiledFeatures(paths.cargo, selected.directory);
  if (compiled.length !== 1 || !compiled[0].includes(FEATURE))
    throw new Error(
      `The test host was not compiled with ${FEATURE}: ${JSON.stringify(compiled)}`,
    );
  const record = {
    executable,
    features: compiled[0],
    configuration: process.env.CADRUMO_BUILD_CONFIG,
    sha256: sha256(executable),
  };
  writeFileSync(paths.record, JSON.stringify(record, null, 2));
  console.log(
    `Packaged test host: ${executable}\n  features: ${record.features.join(", ")}\n  sha256: ${record.sha256}`,
  );
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
)
  build();
