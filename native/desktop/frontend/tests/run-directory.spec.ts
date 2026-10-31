import { expect, test } from "@playwright/test";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { build, preview, resolveConfig } from "vite";
import { buildPath } from "../../scripts/build-paths.mjs";
import { testRunProductBuild } from "../scripts/test-run-directory.mjs";

test("a product preview keeps its own build when another output is rebuilt", async ({
  request,
}, info) => {
  const runVariable = "CADRUMO_DESKTOP_TEST_RUN";
  const previous = process.env[runVariable];
  const stamp = new Date().toISOString().replace(/[-:]|\.\d+/g, "");
  process.env[runVariable] = `${stamp}-${process.pid}`;
  const results = buildPath("desktop_results");
  const product = testRunProductBuild(results);
  if (!product) throw new Error("The test run has no product output");
  const run = resolve(product, "..");
  const source = info.outputPath("source");
  const ordinary = info.outputPath("ordinary");
  let server: Awaited<ReturnType<typeof preview>> | undefined;
  try {
    const config = await resolveConfig({ configLoader: "runner" }, "build");
    expect(resolve(config.build.outDir)).toBe(product);
    expect(product).not.toBe(buildPath("desktop_frontend"));

    await mkdir(source, { recursive: true });
    await writeFile(resolve(source, "index.html"), "<h1>first build</h1>");
    const fixture = {
      configFile: false as const,
      root: source,
      logLevel: "silent" as const,
    };
    await build({ ...fixture, build: { outDir: product, emptyOutDir: true } });
    server = await preview({
      ...fixture,
      build: { outDir: product },
      preview: { host: "127.0.0.1", port: 0, strictPort: true },
    });
    const address = server.httpServer.address();
    if (!address || typeof address === "string")
      throw new Error("No preview port");
    const url = `http://127.0.0.1:${address.port}/`;
    expect(await (await request.get(url)).text()).toContain("first build");

    await writeFile(resolve(source, "index.html"), "<h1>second build</h1>");
    await build({ ...fixture, build: { outDir: ordinary, emptyOutDir: true } });
    expect(await readFile(resolve(ordinary, "index.html"), "utf8")).toContain(
      "second build",
    );
    expect(await (await request.get(url)).text()).toContain("first build");
  } finally {
    if (server)
      await new Promise<void>((done) => server!.httpServer.close(() => done()));
    await rm(run, { recursive: true, force: true });
    if (previous === undefined) delete process.env[runVariable];
    else process.env[runVariable] = previous;
  }
});
