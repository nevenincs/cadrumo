// A Playwright server announces readiness only from the process that bound
// the run's own listener. A different process answering HTTP is never ready.
import { randomBytes } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { extname, relative, resolve, sep } from "node:path";
import { build, createServer, preview } from "vite";
import { buildPath } from "../../scripts/build-paths.mjs";
import { releaseTestRunPorts, testRunPorts } from "./test-run-directory.mjs";

const kind = process.argv[2];
const run = process.env.CADRUMO_DESKTOP_TEST_RUN;
if (!run || !/^[0-9]{8}T[0-9]{6}Z-[0-9]+$/.test(run))
  throw new Error("A browser test run is required");
if (!["product", "scenarios", "hot"].includes(kind))
  throw new Error(`Unknown browser test server: ${kind}`);

const results = buildPath("desktop_results");
const ports = testRunPorts(results);
if (!ports) throw new Error("Missing browser test ports");
const token = randomBytes(24).toString("hex");
const path = `/__cadrumo_test_owner/${token}`;
const middleware = (request, response, next) => {
  if (request.url !== path) return next();
  response.writeHead(200, { "Cache-Control": "no-store" }).end(token);
};
const TYPES = {
  ".css": "text/css",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".json": "application/json",
  ".woff2": "font/woff2",
};
// Vite's preview answers every request with a synchronous stat, on the one
// thread all the run's browsers wait on, and the volume it stats is the one
// those browsers write their traces to: a stall of seconds there stops every
// page. A run's bundle does not change once built, so it is read once and the
// server never touches the disk for it again.
function heldBundle(directory) {
  const files = new Map();
  for (const entry of readdirSync(directory, {
    recursive: true,
    withFileTypes: true,
  })) {
    if (!entry.isFile()) continue;
    const file = resolve(entry.parentPath, entry.name);
    const type = TYPES[extname(file)];
    if (!type) throw new Error(`No type for a bundled file: ${file}`);
    const url = `/${relative(directory, file).split(sep).join("/")}`;
    files.set(url, { type, body: readFileSync(file) });
  }
  return (request, response, next) => {
    const found = files.get(new URL(request.url, "http://preview").pathname);
    if (!found || !["GET", "HEAD"].includes(request.method)) return next();
    response.writeHead(200, {
      "Content-Type": found.type,
      "Content-Length": found.body.length,
      "Cache-Control": "no-cache",
    });
    response.end(request.method === "HEAD" ? undefined : found.body);
  };
}
const ownership = {
  name: "browser-test-server-ownership",
  configureServer: (server) => {
    server.middlewares.use(middleware);
  },
  configurePreviewServer: (server) => {
    server.middlewares.use(middleware);
    server.middlewares.use(heldBundle(server.config.build.outDir));
  },
};
const options = {
  configLoader: "runner",
  mode: kind === "product" ? "production" : "scenarios",
  plugins: [ownership],
};
if (kind === "hot") {
  await releaseTestRunPorts(results, ["hotPort"]);
  const server = await createServer(options);
  await server.listen();
  if (!server.httpServer?.listening)
    throw new Error("Test server did not listen");
} else {
  await build(options);
  await releaseTestRunPorts(
    results,
    kind === "product"
      ? ["previewPort"]
      : ["scenariosPort", "scenariosDocsPort"],
  );
  const server = await preview(options);
  if (!server.httpServer.listening)
    throw new Error("Test preview did not listen");
}
const port =
  kind === "product"
    ? ports.previewPort
    : kind === "scenarios"
      ? ports.scenariosPort
      : ports.hotPort;
const answer = await fetch(`http://127.0.0.1:${port}${path}`, {
  signal: AbortSignal.timeout(10_000),
});
if (!answer.ok || (await answer.text()) !== token)
  throw new Error("Browser test server ownership check failed");
if (kind === "scenarios") {
  const docs = await fetch(
    `http://127.0.0.1:${ports.scenariosDocsPort}/__cadrumo_test_owner`,
    { signal: AbortSignal.timeout(10_000) },
  );
  if (!docs.ok || (await docs.text()) !== ports.token)
    throw new Error("Browser test documentation ownership check failed");
}
process.stdout.write(`CADRUMO_TEST_READY ${run} ${kind}\n`);
