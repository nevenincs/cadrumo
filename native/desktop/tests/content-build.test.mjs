import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  statSync,
  utimesSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { contentBuild, writeStable } from "../scripts/content-build.mjs";

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "cadrumo-content-build-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const source = join(root, "source");
  const output = join(root, "output");
  mkdirSync(source);
  writeFileSync(join(source, "input"), "first");
  return { root, source, output, record: join(root, "record.json") };
}

test("content fingerprints recover missing outputs and detect additions/deletions without timestamp rebuilds", (t) => {
  const { source, output, record } = fixture(t);
  const options = { inputs: [source], outputs: [output], record };
  let builds = 0;
  const build = () => {
    builds++;
    mkdirSync(output, { recursive: true });
    writeFileSync(join(output, "asset"), "unchanged bytes");
  };
  assert.equal(contentBuild(options, build), true);
  utimesSync(join(output, "asset"), 1000000000, 1000000000);
  const mtime = statSync(join(output, "asset")).mtimeMs;
  utimesSync(join(source, "input"), 1000000001, 1000000001);
  assert.equal(contentBuild(options, build), false);
  writeFileSync(join(source, "added"), "new");
  assert.equal(contentBuild(options, build), true);
  assert.equal(statSync(join(output, "asset")).mtimeMs, mtime);
  rmSync(join(source, "added"));
  assert.equal(contentBuild(options, build), true);
  rmSync(join(output, "asset"));
  assert.equal(contentBuild(options, build), true);
  writeFileSync(join(output, "asset"), "corrupted");
  assert.equal(contentBuild(options, build), true);
  assert.equal(builds, 5);
});

test("failed actions never publish fingerprints and stable writes preserve timestamps", (t) => {
  const { source, output, record } = fixture(t);
  writeStable(output, "same");
  utimesSync(output, 1000000000, 1000000000);
  writeStable(output, "same");
  assert.equal(statSync(output).mtimeMs, 1000000000000);
  const options = { inputs: [source], outputs: [output], record };
  assert.throws(
    () =>
      contentBuild(options, () => {
        throw new Error("failed");
      }),
    /failed/,
  );
  assert.equal(
    contentBuild(options, () => writeStable(output, "built")),
    true,
  );
  assert.equal(
    contentBuild(options, () => assert.fail("must not build")),
    false,
  );
});

test("identical regenerated assets retain their original file objects and precise times", (t) => {
  const { source, output, record } = fixture(t);
  const options = {
    inputs: [source],
    outputs: [output, join(output, "asset")],
    record,
  };
  const build = () => {
    mkdirSync(output, { recursive: true });
    writeFileSync(join(output, "asset"), "same bytes");
  };
  contentBuild(options, build);
  const before = statSync(join(output, "asset"), { bigint: true });
  const directoryBefore = statSync(output, { bigint: true });
  writeFileSync(join(source, "input"), "test-only edit");
  contentBuild(options, build);
  const after = statSync(join(output, "asset"), { bigint: true });
  assert.equal(after.ino, before.ino);
  assert.equal(after.mtimeNs, before.mtimeNs);
  assert.equal(
    statSync(output, { bigint: true }).mtimeNs,
    directoryBefore.mtimeNs,
  );
  writeFileSync(join(source, "input"), "failing edit");
  assert.throws(
    () =>
      contentBuild(options, () => {
        mkdirSync(output, { recursive: true });
        writeFileSync(join(output, "asset"), "partial output");
        throw new Error("failed build");
      }),
    /failed build/,
  );
  assert.equal(readFileSync(join(output, "asset"), "utf8"), "same bytes");
  assert.equal(
    statSync(join(output, "asset"), { bigint: true }).mtimeNs,
    before.mtimeNs,
  );
  assert.equal(contentBuild(options, build), true);
});

test("CMake independently invokes content-aware actions and recovers deleted products", (t) => {
  const { root, source, output, record } = fixture(t);
  const helper = fileURLToPath(
    new URL("../scripts/content-build.mjs", import.meta.url),
  );
  const producer = join(root, "producer.mjs");
  writeFileSync(
    producer,
    `import { appendFileSync, writeFileSync } from 'node:fs';
writeFileSync(process.argv[2], 'built'); appendFileSync(process.argv[3], 'build\\n');`,
  );
  const log = join(root, "build.log");
  const inputsFile = join(root, "inputs.json");
  // A real locale catalogue has enough paths to exceed cmd.exe's limit.
  writeFileSync(
    inputsFile,
    JSON.stringify([
      source,
      ...Array.from({ length: 400 }, (_, index) =>
        join(source, `catalogue-${index}.yml`),
      ),
    ]),
  );
  const quote = (value) => `"${value.replaceAll("\\", "/")}"`;
  writeFileSync(
    join(root, "CMakeLists.txt"),
    `cmake_minimum_required(VERSION 3.25)
project(ContentBuild NONE)
add_custom_target(product COMMAND ${quote(process.execPath)} ${quote(helper)} --inputs-file ${quote(inputsFile)} --record ${quote(record)} --output ${quote(output)} -- ${quote(process.execPath)} ${quote(producer)} ${quote(output)} ${quote(log)} VERBATIM)
add_custom_target(unrelated COMMAND ${quote(process.execPath)} -e "throw new Error('unrelated target ran')" VERBATIM)
`,
  );
  function cmake(args) {
    const result = spawnSync("cmake", args, {
      encoding: "utf8",
      windowsHide: true,
    });
    assert.equal(result.status, 0, result.stdout + result.stderr);
  }
  const binary = join(root, "build");
  cmake(["-S", root, "-B", binary, "-G", "Ninja"]);
  const build = () => cmake(["--build", binary, "--target", "product"]);
  build();
  build();
  utimesSync(join(source, "input"), 1000000000, 1000000000);
  build();
  assert.equal(readFileSync(log, "utf8"), "build\n");
  writeFileSync(join(source, "input"), "changed");
  build();
  rmSync(output);
  build();
  assert.equal(readFileSync(log, "utf8"), "build\nbuild\nbuild\n");
});
