import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { resolve } from "node:path";
import { test } from "node:test";
import { buildPath } from "../../../scripts/build-paths.mjs";
import {
  releaseTestRunPorts,
  reserveTestRunPorts,
  testRunDirectory,
} from "../../scripts/test-run-directory.mjs";

const RUN = "CADRUMO_DESKTOP_TEST_RUN";
const keys = [
  "previewPort",
  "scenariosPort",
  "scenariosDocsPort",
  "hotPort",
] as const;
const stamp = new Date().toISOString().replace(/[-:]|\.\d+/g, "");
const results = buildPath("desktop_results");
const name = (number: number) => `${stamp}-${process.pid * 100 + number}`;

test("overlapping runs hold disjoint listeners until their own servers bind", async () => {
  const previous = process.env[RUN];
  const directories: string[] = [];
  try {
    process.env[RUN] = name(1);
    directories.push(testRunDirectory(results));
    const first = await reserveTestRunPorts(results);
    process.env[RUN] = name(2);
    directories.push(testRunDirectory(results));
    const second = await reserveTestRunPorts(results);
    assert.equal(
      new Set([
        ...keys.map((key) => first[key]),
        ...keys.map((key) => second[key]),
      ]).size,
      8,
    );
  } finally {
    for (const [index, directory] of directories.entries()) {
      process.env[RUN] = name(index + 1);
      await releaseTestRunPorts(results, [...keys]);
      await rm(directory, { recursive: true, force: true });
    }
    if (previous === undefined) delete process.env[RUN];
    else process.env[RUN] = previous;
  }
});

test(
  "a foreign HTTP listener cannot make a failed test server ready",
  { timeout: 60_000 },
  async () => {
    const previous = process.env[RUN];
    const foreign = createServer((_request, response) =>
      response.end("foreign"),
    );
    foreign.listen(0, "127.0.0.1");
    await once(foreign, "listening");
    const address = foreign.address();
    if (!address || typeof address === "string")
      throw new Error("No foreign port");
    process.env[RUN] = name(3);
    const directory = testRunDirectory(results);
    await reserveTestRunPorts(results);
    try {
      const file = resolve(directory, "ports.json");
      const ports = JSON.parse(await readFile(file, "utf8")) as Record<
        string,
        unknown
      >;
      ports.hotPort = address.port;
      await writeFile(file, JSON.stringify(ports));
      const child = spawn(
        process.execPath,
        ["scripts/test-server.mjs", "hot"],
        {
          cwd: process.cwd(),
          env: { ...process.env },
          stdio: ["ignore", "pipe", "pipe"],
        },
      );
      let output = "";
      child.stdout.on("data", (chunk: Buffer) => {
        output += chunk.toString();
      });
      child.stderr.on("data", (chunk: Buffer) => {
        output += chunk.toString();
      });
      const deadline = setTimeout(() => child.kill(), 45_000);
      const [code] = await once(child, "close");
      clearTimeout(deadline);
      assert.notEqual(code, 0);
      assert.match(output, /EADDRINUSE|already in use|ownership check failed/i);
      assert.doesNotMatch(output, /CADRUMO_TEST_READY/);
      assert.equal(
        await (await fetch(`http://127.0.0.1:${address.port}/`)).text(),
        "foreign",
      );
    } finally {
      await releaseTestRunPorts(results, [
        "previewPort",
        "scenariosPort",
        "scenariosDocsPort",
      ]);
      await new Promise<void>((done) => foreign.close(() => done()));
      await rm(directory, { recursive: true, force: true });
      if (previous === undefined) delete process.env[RUN];
      else process.env[RUN] = previous;
    }
  },
);
