import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import test from "node:test";
import { buildPath } from "../../../scripts/build-paths.mjs";
import { hostPreset, windowFixtures } from "../fixture-paths.mjs";
import { parseProject, typecheck } from "../typecheck.mjs";

const testing = buildPath("desktop_testing");
mkdirSync(testing, { recursive: true });

function json(file, value) {
  mkdirSync(resolve(file, ".."), { recursive: true });
  writeFileSync(file, JSON.stringify(value));
}

// A project whose own tsconfig points @fixtures at a decoy tree, as a static
// candidate list can point at another preset's build tree.
function plantedProject(t, { value, decoyValue }) {
  const root = mkdtempSync(resolve(testing, "typecheck-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const fixtures = resolve(root, "build", "host", "fixtures", "window");
  json(resolve(fixtures, "family", "projection.json"), { value });
  json(resolve(root, "decoy", "family", "projection.json"), {
    value: decoyValue,
  });
  mkdirSync(resolve(root, "src"));
  writeFileSync(
    resolve(root, "src", "reader.ts"),
    'import projection from "@fixtures/family/projection.json" with { type: "json" };\n' +
      "export const value: number = projection.value;\n",
  );
  json(resolve(root, "tsconfig.json"), {
    compilerOptions: {
      target: "ES2022",
      lib: ["ES2022"],
      module: "ESNext",
      moduleResolution: "Bundler",
      resolveJsonModule: true,
      strict: true,
      noEmit: true,
      types: [],
      paths: { "@fixtures/*": ["./decoy/*"] },
    },
    include: ["src"],
  });
  return { project: resolve(root, "tsconfig.json"), fixtures };
}

test("the frontend's alias is bound to the host preset's window projections alone", (t) => {
  const expected = join("build", hostPreset(), "fixtures", "window");
  assert.ok(windowFixtures().endsWith(expected), windowFixtures());
  // The real tsconfig.json, parsed by the pinned compiler, with a stand-in
  // directory for the host's projections, so this needs none seeded.
  const root = mkdtempSync(resolve(testing, "typecheck-alias-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const parsed = parseProject({ fixtures: root });
  assert.deepEqual(parsed.options.paths["@fixtures/*"], [
    resolve(root, "*").replaceAll("\\", "/"),
  ]);
  assert.deepEqual(parsed.options.paths["@/*"], ["./src/*"]);
});

test("the check reads the projections it is given, not the project's static candidates", (t) => {
  const planted = plantedProject(t, { value: 1, decoyValue: "decoy" });
  const { diagnostics } = typecheck(planted);
  assert.equal(diagnostics.length, 0);
});

test("a projection that no longer fits its reader fails the check", (t) => {
  const planted = plantedProject(t, { value: "changed", decoyValue: 1 });
  const { diagnostics } = typecheck(planted);
  assert.deepEqual(
    diagnostics.map((diagnostic) => diagnostic.code),
    [2322],
  );
});

test("missing projections are refused with the remedy before anything is checked", (t) => {
  const planted = plantedProject(t, { value: 1, decoyValue: 1 });
  rmSync(planted.fixtures, { recursive: true });
  assert.throws(
    () => typecheck(planted),
    (error) =>
      error.message.includes(planted.fixtures) &&
      error.message.includes("desktop-window-fixtures") &&
      error.message.includes("just fixtures-seed"),
  );
});
