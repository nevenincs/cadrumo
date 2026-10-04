import assert from "node:assert/strict";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { buildPath } from "../scripts/build-paths.mjs";
import {
  docsOrigin,
  identity,
  profile,
  server,
  tauriConfig,
  executable,
} from "../scripts/configuration.mjs";

test("CMake build configurations select Cargo optimization and debug information", () => {
  assert.equal(profile("Debug").debug, true);
  assert.equal(profile("Release").debug, false);
  assert.equal(
    profile("RelWithDebInfo").environment.CARGO_PROFILE_RELEASE_DEBUG,
    "2",
  );
  assert.equal(
    profile("MinSizeRel").environment.CARGO_PROFILE_RELEASE_OPT_LEVEL,
    "s",
  );
  assert.throws(() => profile(""), /supported CMake configuration/);
  assert.throws(() => profile("misspelled"), /supported CMake configuration/);
});

test("generated identity, server settings and artifact paths have no product fallback", () => {
  const original = process.env.CADRUMO_CMAKE_BINARY_DIR;
  const originalConfig = process.env.CADRUMO_BUILD_CONFIG;
  const testing = buildPath("desktop_testing");
  mkdirSync(testing, { recursive: true });
  const root = mkdtempSync(resolve(testing, "configuration-"));
  try {
    mkdirSync(resolve(root, "generated"));
    process.env.CADRUMO_CMAKE_BINARY_DIR = root;
    process.env.CADRUMO_BUILD_CONFIG = "Release";
    writeFileSync(
      resolve(root, "build-paths.json"),
      JSON.stringify({
        paths: { generated: "generated", desktop_cargo: "compiler" },
      }),
    );
    assert.throws(identity, /ENOENT/);
    const product = {
      name: "Configured application",
      application_id: "org.example.configured",
      version: "3.2.1",
    };
    writeFileSync(
      resolve(root, "generated/identity.json"),
      JSON.stringify(product),
    );
    assert.deepEqual(identity(), product);
    const template = JSON.parse(
      readFileSync(
        new URL("../src-tauri/tauri.conf.json.in", import.meta.url),
        "utf8",
      ),
    );
    const config = tauriConfig(
      template,
      identity(),
      resolve(root, "assets"),
      resolve(root, "icons"),
    );
    assert.equal(config.productName, product.name);
    assert.equal(config.identifier, product.application_id);
    assert.equal(config.version, product.version);
    assert.equal(config.app.windows[0].title, product.name);
    assert.equal(config.app.windows[0].create, false);
    const ports = { host: "0.0.0.0", devPort: 25420, previewPort: 25421 };
    writeFileSync(
      resolve(root, "generated/desktop-server.json"),
      JSON.stringify(ports),
    );
    assert.deepEqual(server(), ports);
    writeFileSync(
      resolve(root, "generated/desktop-server.json"),
      JSON.stringify({ ...ports, previewPort: 0 }),
    );
    assert.throws(server, /Invalid frontend/);
    const artifact = resolve(root, "compiler/release/from-cargo-metadata.exe");
    writeFileSync(
      resolve(root, "generated/desktop-Release.json"),
      JSON.stringify({ executable: artifact }),
    );
    assert.equal(executable(), artifact);
    writeFileSync(
      resolve(root, "generated/desktop-Release.json"),
      JSON.stringify({ executable: resolve(root, "elsewhere.exe") }),
    );
    assert.throws(executable, /selected Cargo profile/);
    writeFileSync(resolve(root, "generated/identity.json"), "{}");
    assert.throws(identity, /missing name/);
  } finally {
    process.env.CADRUMO_CMAKE_BINARY_DIR = original;
    if (originalConfig === undefined) delete process.env.CADRUMO_BUILD_CONFIG;
    else process.env.CADRUMO_BUILD_CONFIG = originalConfig;
    rmSync(root, { recursive: true });
  }
});

test("the shell policy frames only the documentation origin of the target platform", () => {
  const template = JSON.parse(
    readFileSync(
      new URL("../src-tauri/tauri.conf.json.in", import.meta.url),
      "utf8",
    ),
  );
  const product = {
    name: "Configured application",
    application_id: "org.example.configured",
    version: "3.2.1",
  };
  const frames = (config) =>
    config.app.security.csp
      .split(";")
      .map((directive) => directive.trim())
      .filter((directive) => directive.startsWith("frame-src"));
  assert.deepEqual(frames({ app: template.app }), ["frame-src 'none'"]);
  for (const [platform, https, origin] of [
    ["win32", false, "http://cadrumo-docs.localhost"],
    ["win32", true, "https://cadrumo-docs.localhost"],
    ["linux", false, "cadrumo-docs://localhost"],
    ["linux", true, "cadrumo-docs://localhost"],
  ]) {
    const configured = {
      ...template,
      app: {
        ...template.app,
        windows: [{ ...template.app.windows[0], useHttpsScheme: https }],
      },
    };
    assert.equal(docsOrigin(configured.app.windows[0], platform), origin);
    const config = tauriConfig(
      configured,
      product,
      "assets",
      "icons",
      platform,
    );
    assert.deepEqual(frames(config), [`frame-src ${origin}`]);
    const rest = (policy) =>
      policy
        .split(";")
        .map((d) => d.trim())
        .filter((d) => !d.startsWith("frame-src"));
    assert.deepEqual(
      rest(config.app.security.csp),
      rest(template.app.security.csp),
    );
  }
  for (const csp of [
    "default-src 'self'",
    "default-src 'self'; frame-src *",
    "frame-src 'none'; frame-src 'none'",
  ]) {
    const broken = {
      ...template,
      app: { ...template.app, security: { ...template.app.security, csp } },
    };
    assert.throws(
      () => tauriConfig(broken, product, "assets", "icons", "win32"),
      /must frame nothing/,
    );
  }
});
