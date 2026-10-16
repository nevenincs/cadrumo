// Builds the host for the packaged end-to-end test: the shipped sources with
// the `webview2-remote-debugging` feature, which admits exactly one
// `--remote-debugging-port=<port>` in WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS.
// It has its own source snapshot and Cargo directory under the desktop testing
// directory, so it never replaces the image desktop-host-build declares for
// packaging, and it is never staged, packaged or distributed.
//
// `--served` builds a second such host whose shell is served by the desktop
// development server instead of embedded, for iterating on the shell against
// a real host. It has a directory of its own beside the first.
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { delimiter, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  hostSnapshot,
  snapshotHostSources,
} from "../../scripts/backend-snapshot.mjs";
import { buildPath } from "../../scripts/build-paths.mjs";
import {
  identity as readIdentity,
  profile,
  tauriConfig,
} from "../../scripts/configuration.mjs";
import { developmentServer } from "../../scripts/development-server.mjs";

export const FEATURE = "webview2-remote-debugging";
const BINARY = "cadrumo";

/** The two test hosts: the shell embedded, or served by the development server. */
export const VARIANTS = Object.freeze({
  embedded: "packaged",
  served: "served",
});

/** The directories this test host owns, all inside the desktop testing directory. */
export function packagedHostPaths(variant = VARIANTS.embedded) {
  if (!Object.values(VARIANTS).includes(variant))
    throw new Error(`Unknown packaged test host: ${variant}`);
  const root = resolve(buildPath("desktop_testing"), variant);
  const snapshot = resolve(root, "host");
  return {
    root,
    snapshot,
    configuration: resolve(hostSnapshot(snapshot).crate, "tauri.conf.json"),
    cargo: resolve(root, "cargo"),
    icons: resolve(root, "icons"),
    record: resolve(root, "host.json"),
  };
}

/** The test host recorded by the last build, refused when it no longer matches. */
export function packagedHost(variant = VARIANTS.embedded) {
  const { record, cargo } = packagedHostPaths(variant);
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

/** The development server's shell address, which a served host loads. */
export function servedShell() {
  const { devPort } = developmentServer();
  return `http://127.0.0.1:${devPort}/`;
}

function build(variant) {
  const desktop = fileURLToPath(new URL("../../", import.meta.url));
  const paths = packagedHostPaths(variant);
  const selected = profile();
  const identity = readIdentity();
  const contract = process.env.CADRUMO_NATIVE_CONTRACT;
  if (!contract || !isAbsolute(contract))
    throw new Error(
      "Set CADRUMO_NATIVE_CONTRACT to the generated native contract.json.",
    );
  // Preserve unchanged source timestamps so Cargo can reuse its compiled inputs.
  const snapshot = snapshotHostSources(resolve(desktop, ".."), paths.snapshot, {
    incremental: true,
  });
  const config = tauriConfig(
    JSON.parse(
      readFileSync(resolve(desktop, "src-tauri/tauri.conf.json.in"), "utf8"),
    ),
    identity,
    {
      configDirectory: snapshot.crate,
      frontend: buildPath("desktop_frontend"),
      icons: paths.icons,
    },
  );
  // Test windows must not activate or close an operator's running desktop.
  config.identifier += ".desktop-tests";
  // Tauri reads a URL frontend as a remote shell; the host then admits that
  // origin as its shell and loads nothing embedded.
  if (variant === VARIANTS.served) config.build.frontendDist = servedShell();
  const configuration = JSON.stringify(config, null, 2);
  if (
    !existsSync(paths.configuration) ||
    readFileSync(paths.configuration, "utf8") !== configuration
  )
    writeFileSync(paths.configuration, configuration);
  const environment = {
    ...process.env,
    ...selected.environment,
    CARGO_TARGET_DIR: paths.cargo,
    CADRUMO_NATIVE_CONTRACT: contract,
    CADRUMO_CONTRACT_RS: resolve(contract, "../contract.rs"),
    CADRUMO_ID_NAME: identity.name,
    CADRUMO_ID_APPLICATION_ID: identity.application_id,
    CADRUMO_ID_VERSION: identity.version,
    CADRUMO_ID_MANAGER_ID: identity.manager_id,
    CADRUMO_ID_MANAGER_NAME: identity.manager_name,
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
      cwd: snapshot.project,
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
    variant,
    shell: variant === VARIANTS.served ? servedShell() : null,
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
) {
  const options = process.argv.slice(2);
  if (options.some((option) => option !== "--served"))
    throw new Error("The packaged test host takes only --served.");
  build(options.includes("--served") ? VARIANTS.served : VARIANTS.embedded);
}
