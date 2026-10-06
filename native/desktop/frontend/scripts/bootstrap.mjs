// Prepares a build directory for browser development of the shell.
//
// The development server reads three generated files (build paths, product
// identity, server address) and the shell reads two generated inputs (chrome
// strings, palette). Configuring the standalone desktop project writes the
// first three; its `desktop-frontend-generated` target runs the existing
// generators for the other two. Nothing is compiled: no Rust, no wheel and no
// documentation build.
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const desktop = fileURLToPath(new URL("../..", import.meta.url));

const hostTargets = {
  "win32-x64": "windows-x86-64",
  "linux-x64": "linux-x86-64",
  "linux-arm64": "linux-aarch64",
  "darwin-arm64": "macos-arm64",
};

// The standalone desktop project's presets own the default build directory:
// the preset that configures this host's target names it.
export function hostPreset() {
  const target = hostTargets[`${process.platform}-${process.arch}`];
  const { configurePresets } = JSON.parse(
    readFileSync(resolve(desktop, "CMakePresets.json"), "utf8"),
  );
  const preset = configurePresets.find(
    (candidate) => candidate.cacheVariables?.CADRUMO_TARGET === target,
  );
  if (!preset)
    throw new Error(
      "No desktop configure preset targets this host; pass --build-dir.",
    );
  return {
    name: preset.name,
    binaryDir: resolve(
      preset.binaryDir
        .replaceAll("${sourceDir}", desktop)
        .replaceAll("${presetName}", preset.name),
    ),
  };
}

function run(args) {
  const result = spawnSync("cmake", args, { stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function main() {
  const { values } = parseArgs({
    options: {
      "build-dir": { type: "string" },
      host: { type: "string", default: "127.0.0.1" },
      "dev-port": { type: "string", default: "15370" },
      "preview-port": { type: "string", default: "15371" },
    },
  });

  const preset = values["build-dir"] === undefined ? hostPreset() : undefined;
  const buildDir = preset?.binaryDir ?? resolve(values["build-dir"]);
  // An address that binds every interface is not one a browser can open.
  const open = ["0.0.0.0", "::"].includes(values.host)
    ? "127.0.0.1"
    : values.host;

  run([
    "-S",
    desktop,
    ...(preset ? ["--preset", preset.name] : ["-B", buildDir]),
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
      `Application  http://${open}:${values["dev-port"]}/`,
      `Scenarios    http://${open}:${values["dev-port"]}/scenarios.html`,
    ].join("\n"),
  );
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
)
  main();
