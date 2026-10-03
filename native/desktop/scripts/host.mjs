import { spawnSync } from "node:child_process";
import { cpSync, mkdirSync, readFileSync } from "node:fs";
import { delimiter, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const binaryDir = process.env.CADRUMO_CMAKE_BINARY_DIR;
if (!binaryDir || !isAbsolute(binaryDir))
  throw new Error("Select an absolute CMake build directory.");
const identity = JSON.parse(
  readFileSync(resolve(binaryDir, "generated/identity.json"), "utf8"),
);
const cli = resolve(desktop, "frontend/node_modules/@tauri-apps/cli/tauri.js");
const icons = resolve(binaryDir, "desktop/icons");
const snapshot = resolve(binaryDir, "desktop/host");
const contract = process.env.CADRUMO_NATIVE_CONTRACT;
if (!contract || !isAbsolute(contract))
  throw new Error(
    "Set CADRUMO_NATIVE_CONTRACT to the generated native contract.json.",
  );
const environment = {
  ...process.env,
  CARGO_TARGET_DIR: resolve(binaryDir, "cargo/desktop"),
  CADRUMO_NATIVE_CONTRACT: contract,
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
for (const entry of [
  "Cargo.toml",
  "Cargo.lock",
  "build.rs",
  "tauri.conf.json",
  "src",
]) {
  cpSync(
    resolve(desktop, "src-tauri", entry),
    resolve(snapshot, "src-tauri", entry),
    { recursive: true },
  );
}
run([
  "icon",
  resolve(desktop, "../../docs/_static/cadrumo-favicon.svg"),
  "--output",
  icons,
]);
const config = {
  productName: identity.name,
  identifier: identity.application_id,
  version: identity.version,
  build: { frontendDist: resolve(binaryDir, "desktop/frontend") },
  bundle: { icon: [resolve(icons, "icon.ico"), resolve(icons, "icon.png")] },
};
const action = process.argv[2] ?? "build";
if (action === "build") {
  run([
    "build",
    "--no-bundle",
    "--debug",
    "--config",
    JSON.stringify(config),
    "--",
    "--locked",
  ]);
} else if (action === "test" || action === "clippy") {
  const args =
    action === "test"
      ? [
          "test",
          "--locked",
          "--features",
          "live-package-tests",
          "--",
          "--nocapture",
          "--test-threads=1",
        ]
      : [
          "clippy",
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
