import { spawnSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { delimiter, isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { buildPath } from "./build-paths.mjs";
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
const snapshot = buildPath("desktop_host");
// Remove only generated source copies so renamed Rust modules cannot survive a rebuild.
for (const directory of [
  resolve(snapshot, "src-tauri/src"),
  resolve(snapshot, "../application/src"),
  resolve(snapshot, "../platform/src"),
]) {
  if (!existsSync(directory)) continue;
  const ownedPath = relative(realpathSync(binaryDir), realpathSync(directory));
  if (!ownedPath || ownedPath.startsWith("..") || isAbsolute(ownedPath))
    throw new Error(
      "Generated sources must remain inside the selected build directory.",
    );
  rmSync(directory, { recursive: true });
}
const contract = process.env.CADRUMO_NATIVE_CONTRACT;
if (!contract || !isAbsolute(contract))
  throw new Error(
    "Set CADRUMO_NATIVE_CONTRACT to the generated native contract.json.",
  );
const environment = {
  ...process.env,
  ...selectedProfile.environment,
  CARGO_TARGET_DIR: buildPath("desktop_cargo"),
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
cpSync(
  resolve(desktop, "../application"),
  resolve(snapshot, "../application"),
  {
    recursive: true,
  },
);
cpSync(resolve(desktop, "../platform"), resolve(snapshot, "../platform"), {
  recursive: true,
});
function run(args) {
  const result = spawnSync(process.execPath, [cli, ...args], {
    cwd: snapshot,
    stdio: "inherit",
    windowsHide: true,
    env: environment,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
mkdirSync(resolve(snapshot, "src-tauri"), { recursive: true });
for (const entry of ["Cargo.toml", "Cargo.lock", "build.rs", "src"]) {
  cpSync(
    resolve(desktop, "src-tauri", entry),
    resolve(snapshot, "src-tauri", entry),
    { recursive: true },
  );
}
const config = tauriConfig(
  JSON.parse(
    readFileSync(resolve(desktop, "src-tauri/tauri.conf.json.in"), "utf8"),
  ),
  identity,
  buildPath("desktop_frontend"),
  icons,
);
writeFileSync(
  resolve(snapshot, "src-tauri/tauri.conf.json"),
  JSON.stringify(config, null, 2),
);
run([
  "icon",
  resolve(desktop, "../../docs/_static/cadrumo-favicon.svg"),
  "--output",
  icons,
]);
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
      cwd: resolve(snapshot, "src-tauri"),
      env: environment,
      encoding: "utf8",
      windowsHide: true,
    },
  );
  if (metadata.error) throw metadata.error;
  if (metadata.status !== 0) throw new Error(metadata.stderr);
  const manifest = resolve(snapshot, "src-tauri/Cargo.toml");
  const owner = JSON.parse(metadata.stdout).packages.find(
    (pkg) => resolve(pkg.manifest_path) === manifest,
  );
  const binaries = owner?.targets.filter((target) =>
    target.kind.includes("bin"),
  );
  if (binaries?.length !== 1)
    throw new Error("Desktop manifest must declare exactly one executable");
  writeFileSync(
    artifactFile(),
    JSON.stringify({
      executable: resolve(
        buildPath("desktop_cargo"),
        selectedProfile.directory,
        binaries[0].name + (process.platform === "win32" ? ".exe" : ""),
      ),
    }),
  );
} else if (action === "test" || action === "clippy") {
  const args =
    action === "test"
      ? [
          "test",
          ...(selectedProfile.debug ? [] : ["--release"]),
          "--locked",
          "--features",
          "live-package-tests",
          "--",
          "--nocapture",
          "--test-threads=1",
        ]
      : [
          "clippy",
          ...(selectedProfile.debug ? [] : ["--release"]),
          "--locked",
          "--all-targets",
          "--features",
          "live-package-tests",
          "--",
          "-D",
          "warnings",
        ];
  const result = spawnSync("cargo", args, {
    cwd: resolve(snapshot, "src-tauri"),
    env: { ...environment, TAURI_CONFIG: JSON.stringify(config) },
    stdio: "inherit",
    windowsHide: true,
  });
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
} else {
  throw new Error(`Unknown host action: ${action}`);
}
