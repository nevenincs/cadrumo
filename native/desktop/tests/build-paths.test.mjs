import assert from "node:assert/strict";
import {
  mkdirSync,
  mkdtempSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { buildPath, readBuildPaths } from "../scripts/build-paths.mjs";

const testing = buildPath("desktop_testing");
mkdirSync(testing, { recursive: true });

function configuredBuild(presetName = "desktop-test", project = "desktop") {
  const repository = mkdtempSync(resolve(testing, "path-admission-"));
  const desktopSource = resolve(repository, "native/desktop");
  const source = project === "root" ? repository : desktopSource;
  const build = resolve(repository, "build", presetName);
  mkdirSync(source, { recursive: true });
  mkdirSync(desktopSource, { recursive: true });
  mkdirSync(build, { recursive: true });
  writeFileSync(
    resolve(repository, "CMakePresets.json"),
    JSON.stringify({ configurePresets: [{ name: "root-test" }] }),
  );
  writeFileSync(
    resolve(desktopSource, "CMakePresets.json"),
    JSON.stringify({ configurePresets: [{ name: "desktop-test" }] }),
  );
  writeFileSync(
    resolve(build, "build-paths.json"),
    JSON.stringify({
      source,
      paths: { desktop_cargo: "cargo/desktop", desktop_testing: "desktop/testing" },
    }),
  );
  writeFileSync(
    resolve(build, "CMakeCache.txt"),
    [
      `CMAKE_HOME_DIRECTORY:INTERNAL=${source}`,
      `CMAKE_CACHEFILE_DIR:INTERNAL=${build}`,
      "",
    ].join("\n"),
  );
  return { repository, source, build };
}

test("desktop paths require an enrolled configured physical build directory", () => {
  const fixture = configuredBuild();
  try {
    assert.deepEqual(readBuildPaths(fixture.build, fixture.repository), {
      desktop_cargo: resolve(fixture.build, "cargo/desktop"),
      desktop_testing: resolve(fixture.build, "desktop/testing"),
    });
    assert.throws(
      () => readBuildPaths(`${fixture.build}/../desktop-test`, fixture.repository),
      /traversal|enrolled|preset/i,
    );
    assert.throws(
      () => readBuildPaths(resolve(fixture.repository, "build/unlisted"), fixture.repository),
      /visible configure preset/,
    );
  } finally {
    rmSync(fixture.repository, { recursive: true, force: true });
  }
});

test("desktop paths bind the manifest and cache to the preset source and build", () => {
  const fixture = configuredBuild();
  try {
    const manifest = resolve(fixture.build, "build-paths.json");
    writeFileSync(
      manifest,
      JSON.stringify({ source: fixture.repository, paths: { desktop: "desktop" } }),
    );
    assert.throws(
      () => readBuildPaths(fixture.build, fixture.repository),
      /another source tree/,
    );
    writeFileSync(
      manifest,
      JSON.stringify({ source: fixture.source, paths: { desktop: "desktop" } }),
    );
    writeFileSync(
      resolve(fixture.build, "CMakeCache.txt"),
      `CMAKE_HOME_DIRECTORY:INTERNAL=${fixture.source}\nCMAKE_CACHEFILE_DIR:INTERNAL=${fixture.repository}\n`,
    );
    assert.throws(
      () => readBuildPaths(fixture.build, fixture.repository),
      /another binary directory/,
    );
  } finally {
    rmSync(fixture.repository, { recursive: true, force: true });
  }
});

test("desktop paths admit the root preset when its manifest and cache name the repository source", () => {
  const fixture = configuredBuild("root-test", "root");
  try {
    assert.deepEqual(readBuildPaths(fixture.build, fixture.repository), {
      desktop_cargo: resolve(fixture.build, "cargo/desktop"),
      desktop_testing: resolve(fixture.build, "desktop/testing"),
    });
  } finally {
    rmSync(fixture.repository, { recursive: true, force: true });
  }
});

test("desktop paths reject a linked enrolled build directory", (t) => {
  const fixture = configuredBuild();
  try {
    const presets = resolve(fixture.source, "CMakePresets.json");
    writeFileSync(
      presets,
      JSON.stringify({
        configurePresets: [
          { name: "desktop-test" },
          { name: "desktop-linked" },
        ],
      }),
    );
    const linked = resolve(fixture.repository, "build/desktop-linked");
    try {
      symlinkSync(fixture.build, linked, "junction");
    } catch (error) {
      if (["EACCES", "EPERM", "ENOTSUP"].includes(error.code)) {
        t.skip("This host does not permit creating a directory junction");
        return;
      }
      throw error;
    }
    assert.throws(() => readBuildPaths(linked, fixture.repository), /Linked CMake output path/);
  } finally {
    rmSync(fixture.repository, { recursive: true, force: true });
  }
});

test("desktop output declarations reject traversal and linked children", (t) => {
  const fixture = configuredBuild();
  try {
    const manifest = resolve(fixture.build, "build-paths.json");
    writeFileSync(
      manifest,
      JSON.stringify({ source: fixture.source, paths: { escape: "../outside" } }),
    );
    assert.throws(() => readBuildPaths(fixture.build, fixture.repository), /Invalid CMake output/);

    const outside = resolve(fixture.repository, "outside");
    const linked = resolve(fixture.build, "linked");
    mkdirSync(outside);
    try {
      symlinkSync(outside, linked, "junction");
    } catch (error) {
      if (["EACCES", "EPERM", "ENOTSUP"].includes(error.code)) {
        t.skip("This host does not permit creating a directory junction");
        return;
      }
      throw error;
    }
    writeFileSync(
      manifest,
      JSON.stringify({ source: fixture.source, paths: { escape: "linked/output" } }),
    );
    assert.throws(() => readBuildPaths(fixture.build, fixture.repository), /Linked CMake output/);
  } finally {
    rmSync(fixture.repository, { recursive: true, force: true });
  }
});

test("production buildPath uses the selected CMake binary directory", () => {
  const target = buildPath("desktop_testing");
  assert.equal(
    target,
    resolve(process.env.CADRUMO_CMAKE_BINARY_DIR, "desktop/testing"),
  );
});
