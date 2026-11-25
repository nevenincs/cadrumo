import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire, syncBuiltinESMExports } from "node:module";
import path from "node:path";
import { test } from "node:test";
import { ESLint } from "eslint";

const requireFrom = (name) =>
  createRequire(path.join(process.cwd(), "node_modules", name, "package.json"));

test("ESLint and TypeScript parser parents retain supported glob matching", () => {
  for (const name of [
    "eslint",
    "@eslint/config-array",
    "@typescript-eslint/typescript-estree",
  ]) {
    const { Minimatch, minimatch } = requireFrom(name)("minimatch");
    const sources = new Minimatch("src/**/*.{ts,tsx}", { dot: true });
    assert.equal(sources.match("src/components/Settings.tsx"), true, name);
    assert.equal(sources.match("src/.hidden/profile.ts"), true, name);
    assert.equal(sources.match("src/components/readme.md"), false, name);
    assert.equal(sources.match("src/components", true), true, name);
    assert.equal(
      minimatch("src/components/Profile.tsx", "src/**/*.{ts,tsx}"),
      true,
      name,
    );
    assert.equal(
      minimatch("src/components/profile.json", "src/**/*.{ts,tsx}"),
      false,
      name,
    );

    const extglob = new Minimatch("src/**/!(*.test).{ts,tsx}", { dot: true });
    assert.equal(extglob.match("src/components/Profile.tsx"), true, name);
    assert.equal(extglob.match("src/components/Profile.test.tsx"), false, name);

    const amplified = new Minimatch(Array(8).fill("**/../a/b").join("/"), {
      optimizationLevel: 2,
      braceExpandMax: 16,
    });
    assert.ok(amplified.set.length <= 16, `${name} exceeded the pattern cap`);
  }
});

test("ESLint discovers and parses the real TypeScript and TSX entrypoints", async () => {
  const lint = new ESLint();
  const results = await lint.lintFiles(["src/main.tsx", "src/startup.ts"]);
  assert.equal(results.length, 2);
  assert.ok(results.every((result) => result.fatalErrorCount === 0));
  assert.equal(await lint.isPathIgnored("node_modules/example.ts"), true);
});

test("aborted promise and stream globs stop issuing directory reads", async () => {
  const original = fs.readdir;
  let controller;
  let reads = 0;
  fs.readdir = function (...args) {
    reads += 1;
    const callback = args.at(-1);
    args[args.length - 1] = (...result) => {
      if (!controller.signal.aborted)
        controller.abort(new Error("probe abort"));
      callback(...result);
    };
    return original.apply(this, args);
  };
  syncBuiltinESMExports();
  try {
    const { glob, globStream } = await import("glob");
    for (const mode of ["promise", "stream"]) {
      controller = new AbortController();
      reads = 0;
      const options = { cwd: "src", signal: controller.signal };
      const walking =
        mode === "promise"
          ? glob("**/*", options)
          : new Promise((resolve, reject) => {
              const stream = globStream("**/*", options);
              stream.on("data", () => {});
              stream.on("end", resolve);
              stream.on("error", reject);
            });
      await assert.rejects(walking, /probe abort/);
      const atRejection = reads;
      assert.ok(atRejection > 0);
      await new Promise((resolve) => setTimeout(resolve, 200));
      assert.equal(reads, atRejection, mode);
    }
  } finally {
    fs.readdir = original;
    syncBuiltinESMExports();
  }
});

test("Storybook's docgen glob finds stories while respecting exclusions", () => {
  const { globSync } = requireFrom(
    "@joshwooding/vite-plugin-react-docgen-typescript",
  )("glob");
  const files = globSync("src/**/*.stories.tsx", {
    absolute: true,
    cwd: process.cwd(),
    ignore: ["src/dev/**"],
    nodir: true,
  }).map((file) => path.relative(process.cwd(), file).replaceAll("\\", "/"));
  assert.ok(files.includes("src/components/Settings.stories.tsx"));
  assert.ok(files.every((file) => !file.startsWith("src/dev/")));
});
