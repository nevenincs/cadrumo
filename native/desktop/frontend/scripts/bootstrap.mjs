// Prepares a build directory for browser development of the shell.
//
// The development server reads three generated files (build paths, product
// identity, server address) and the shell reads two generated inputs (chrome
// strings, palette). Configuring the standalone desktop project writes the
// first three; its `desktop-frontend-generated` target runs the existing
// generators for the other two. Nothing is compiled: no Rust, no wheel and no
// documentation build.
import { spawnSync } from "node:child_process";
import { isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const desktop = fileURLToPath(new URL("../..", import.meta.url));
const repository = resolve(desktop, "../..");

const { values } = parseArgs({
  options: {
    "build-dir": { type: "string" },
    host: { type: "string", default: "127.0.0.1" },
    "dev-port": { type: "string", default: "15370" },
    "preview-port": { type: "string", default: "15371" },
  },
});

const buildDir = resolve(
  values["build-dir"] ?? resolve(repository, "build", "desktop-frontend"),
);
if (!isAbsolute(buildDir)) throw new Error("The build directory must resolve.");

function run(args) {
  const result = spawnSync("cmake", args, { stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

run([
  "-S",
  desktop,
  "-B",
  buildDir,
  `-DCADRUMO_DESKTOP_BIND_ADDRESS=${values.host}`,
  `-DCADRUMO_DESKTOP_DEV_PORT=${values["dev-port"]}`,
  `-DCADRUMO_DESKTOP_PREVIEW_PORT=${values["preview-port"]}`,
]);
run(["--build", buildDir, "--target", "desktop-frontend-generated"]);

console.log(
  [
    "",
    "The build directory is ready. Select it for this shell, then start the server:",
    "",
    `  PowerShell   $env:CADRUMO_CMAKE_BINARY_DIR = '${buildDir}'`,
    `  POSIX shell  export CADRUMO_CMAKE_BINARY_DIR='${buildDir}'`,
    "",
    "  npm run dev",
    "",
    `Application  http://${values.host}:${values["dev-port"]}/`,
    `Scenarios    http://${values.host}:${values["dev-port"]}/scenarios.html`,
  ].join("\n"),
);
