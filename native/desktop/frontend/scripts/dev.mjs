// just dev and npm run dev share this entry, including configuration generation.
import { createServer } from "vite";
import { fileURLToPath } from "node:url";
import { bootstrap } from "./bootstrap.mjs";

const frontend = fileURLToPath(new URL("..", import.meta.url));
process.env.CADRUMO_CMAKE_BINARY_DIR = bootstrap();
const server = await createServer({ root: frontend });
try {
  await server.listen();
} catch (error) {
  await server.close();
  throw error;
}
server.printUrls();
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
