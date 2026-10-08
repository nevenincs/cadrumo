// Starts or builds the component catalogue. The address comes from the same
// generated server definition the development server uses; the static build
// goes under the build directory and is never packaged.
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { buildPath } from "../../scripts/build-paths.mjs";
import { server } from "../../scripts/configuration.mjs";

const frontend = fileURLToPath(new URL("..", import.meta.url));
const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: { port: { type: "string", default: "6006" } },
});
const [command = "dev"] = positionals;

const args =
  command === "build"
    ? [
        "build",
        "--output-dir",
        resolve(buildPath("desktop_testing"), "storybook"),
      ]
    : command === "dev"
      ? ["dev", "--host", server().host, "--port", values.port, "--no-open"]
      : null;
if (!args) throw new Error(`Unknown catalogue command: ${command}`);

const result = spawnSync(
  process.execPath,
  [
    resolve(frontend, "node_modules/storybook/dist/bin/dispatcher.js"),
    ...args,
    "--disable-telemetry",
  ],
  {
    cwd: frontend,
    stdio: "inherit",
    env: { ...process.env, STORYBOOK_DISABLE_TELEMETRY: "1" },
  },
);
if (result.error) throw result.error;
process.exit(result.status ?? 1);
