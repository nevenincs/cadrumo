import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { relative, resolve, sep } from "node:path";
import test from "node:test";
import { buildPath, readBuildPaths } from "../../../scripts/build-paths.mjs";
import {
  parseProject,
  WINDOW_INDEX,
  writeAliasProject,
} from "../fixture-alias.mjs";
import { typecheck } from "../typecheck.mjs";

const testing = buildPath("desktop_testing");
mkdirSync(testing, { recursive: true });

function json(file, value) {
  mkdirSync(resolve(file, ".."), { recursive: true });
  writeFileSync(file, JSON.stringify(value));
}

// Write `files` into `fixtures` and record them as the seed does.
function seeded(fixtures, files) {
  const outputs = {};
  for (const [name, value] of Object.entries(files)) {
    const path = resolve(fixtures, ...name.split("/"));
    json(path, value);
    outputs[name] = createHash("sha256")
      .update(readFileSync(path))
      .digest("hex");
  }
  json(resolve(fixtures, WINDOW_INDEX), {
    format: "cadrumo-window-projections-v1",
    families: { family: outputs },
  });
  return fixtures;
}

function scratch(t, prefix) {
  const root = mkdtempSync(resolve(testing, prefix));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return root;
}

// A project whose own tsconfig points @fixtures at a decoy tree, as a static
// candidate list can point at another preset's build tree.
function plantedProject(t, { value, decoyValue }) {
  const root = scratch(t, "typecheck-");
  const fixtures = seeded(resolve(root, "build", "selected", "fixtures"), {
    "family/projection.json": { value },
  });
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

test("the frontend's alias is bound to the projections it is given alone", (t) => {
  // The real tsconfig.json, parsed by the pinned compiler, with a stand-in
  // directory for the build's projections, so this needs none seeded.
  const root = seeded(scratch(t, "typecheck-alias-"), {
    "family/projection.json": { value: 1 },
  });
  const parsed = parseProject({ fixtures: root });
  assert.deepEqual(parsed.options.paths["@fixtures/*"], [
    resolve(root, "*").replaceAll("\\", "/"),
  ]);
  assert.deepEqual(parsed.options.paths["@/*"], ["./src/*"]);
});

test("a build of another preset reads its own projections, never the host preset's", (t) => {
  const repository = scratch(t, "typecheck-presets-");
  writeFileSync(
    resolve(repository, "CMakePresets.json"),
    JSON.stringify({
      configurePresets: [
        { name: "windows-x64" },
        { name: "windows-installers-x64" },
      ],
    }),
  );
  for (const preset of ["windows-x64", "windows-installers-x64"]) {
    const build = resolve(repository, "build", preset);
    mkdirSync(build, { recursive: true });
    writeFileSync(
      resolve(build, "build-paths.json"),
      JSON.stringify({
        source: repository,
        paths: { window_fixtures: "fixtures/window" },
      }),
    );
    writeFileSync(
      resolve(build, "CMakeCache.txt"),
      `CMAKE_HOME_DIRECTORY:INTERNAL=${repository}\nCMAKE_CACHEFILE_DIR:INTERNAL=${build}\n`,
    );
  }
  const selected = resolve(repository, "build", "windows-installers-x64");
  const fixtures = readBuildPaths(selected, repository).window_fixtures;
  assert.equal(fixtures, resolve(selected, "fixtures", "window"));
  const host = relative(resolve(repository, "build", "windows-x64"), fixtures);
  assert.ok(host.startsWith(`..${sep}`), fixtures);
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

function refusedWithRemedy(fixtures, reason) {
  return (error) =>
    error.message.includes(fixtures) &&
    error.message.includes(reason) &&
    error.message.includes("desktop-window-fixtures") &&
    error.message.includes("just fixtures-seed");
}

test("missing projections are refused with the remedy before anything is checked", (t) => {
  const planted = plantedProject(t, { value: 1, decoyValue: 1 });
  rmSync(planted.fixtures, { recursive: true });
  assert.throws(
    () => typecheck(planted),
    refusedWithRemedy(planted.fixtures, "missing"),
  );
});

test("projections no seed recorded are refused with the remedy", (t) => {
  const planted = plantedProject(t, { value: 1, decoyValue: 1 });
  rmSync(resolve(planted.fixtures, WINDOW_INDEX));
  assert.throws(
    () => typecheck(planted),
    refusedWithRemedy(planted.fixtures, WINDOW_INDEX),
  );
});

test("a partial seed is refused naming the missing output", (t) => {
  const planted = plantedProject(t, { value: 1, decoyValue: 1 });
  rmSync(resolve(planted.fixtures, "family", "projection.json"));
  assert.throws(
    () => typecheck(planted),
    refusedWithRemedy(planted.fixtures, "family/projection.json is missing"),
  );
});

test("an output edited after its seed is refused", (t) => {
  const planted = plantedProject(t, { value: 1, decoyValue: 1 });
  json(resolve(planted.fixtures, "family", "projection.json"), { value: 2 });
  assert.throws(
    () => typecheck(planted),
    refusedWithRemedy(
      planted.fixtures,
      "family/projection.json differs from its seed",
    ),
  );
});

test("Playwright's project binds every alias absolutely, @fixtures to the given projections", (t) => {
  const root = scratch(t, "typecheck-playwright-");
  const fixtures = seeded(resolve(root, "fixtures"), {
    "family/projection.json": { value: 1 },
  });
  const destination = resolve(root, "testing", "playwright-tsconfig.json");
  assert.equal(writeAliasProject(destination, { fixtures }), destination);
  const written = JSON.parse(readFileSync(destination, "utf8"));
  const frontend = resolve(import.meta.dirname, "..", "..");
  assert.equal(
    written.extends,
    resolve(frontend, "tsconfig.json").replaceAll("\\", "/"),
  );
  assert.deepEqual(written.compilerOptions.paths["@fixtures/*"], [
    resolve(fixtures, "*").replaceAll("\\", "/"),
  ]);
  assert.deepEqual(written.compilerOptions.paths["@/*"], [
    resolve(frontend, "src", "*").replaceAll("\\", "/"),
  ]);
  const before = statSync(destination).mtimeMs;
  writeAliasProject(destination, { fixtures });
  assert.equal(statSync(destination).mtimeMs, before);
});

test("Playwright's project is refused for an unseeded build", (t) => {
  const root = scratch(t, "typecheck-playwright-");
  const fixtures = resolve(root, "fixtures");
  assert.throws(
    () =>
      writeAliasProject(resolve(root, "playwright-tsconfig.json"), {
        fixtures,
      }),
    refusedWithRemedy(fixtures, "missing"),
  );
});
