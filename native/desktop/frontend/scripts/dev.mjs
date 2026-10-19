// The development display, served from the CMake build directory under test.
// The build owns every generated input: its desktop-frontend-dev target (what
// just dev runs) and desktop-frontend-test build desktop-frontend-generated
// first. This script reads that directory and never configures or builds.
import { createServer } from "vite";
import { existsSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { buildPath } from "../../scripts/build-paths.mjs";

parseArgs({ options: {} });
const binaryDir = process.env.CADRUMO_CMAKE_BINARY_DIR;
if (!binaryDir || !isAbsolute(binaryDir))
  throw new Error(
    "Run just dev, or set CADRUMO_CMAKE_BINARY_DIR to the absolute build/<preset> directory of a configured repository build.",
  );
const generated = buildPath("desktop_frontend_generated");
for (const name of [
  "chrome-strings.json",
  "palette.css",
  "provider-icons.json",
])
  if (!existsSync(resolve(generated, name)))
    throw new Error(
      `${name} has not been generated in ${generated}. Build the desktop-frontend-generated target of ${binaryDir}, or run just dev.`,
    );

const frontend = fileURLToPath(new URL("..", import.meta.url));
const server = await createServer({ root: frontend });
try {
  await server.listen();
} catch (error) {
  await server.close();
  throw error;
}
server.printUrls();
console.log(`Build directory: ${binaryDir}`);
console.log("Development display: /scenarios.html");

let stopping = false;
async function stop() {
  if (stopping) return;
  stopping = true;
  await server.close();
  process.exit(0);
}
process.once("SIGINT", stop);
process.once("SIGTERM", stop);
