import assert from "node:assert/strict";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  realpathSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  ensureInstalled,
  installDecision,
} from "../scripts/frontend-install.mjs";

const PLATFORM = { os: "testos", cpu: "testcpu", libc: undefined };
const RECORD = "node_modules/.package-lock.json";

function entry(version, extra = {}) {
  return {
    version,
    resolved: `https://registry.example/package-${version}.tgz`,
    integrity: `sha512-${version}`,
    ...extra,
  };
}

// One runtime and one development dependency. The tool has a binding for this
// platform, one for another, a WebAssembly fallback with a dependency of its
// own, and an optional wrapper that cannot work without the foreign binding.
function locked() {
  const optional = { dev: true, optional: true };
  return {
    "": {
      name: "fixture",
      dependencies: { runtime: "1.0.0" },
      devDependencies: { tool: "2.0.0" },
    },
    "node_modules/runtime": entry("1.0.0", {
      dependencies: { shared: "^1.0.0" },
    }),
    "node_modules/shared": entry("1.4.0"),
    "node_modules/tool": entry("2.0.0", {
      dev: true,
      dependencies: { shared: "^2.0.0" },
      optionalDependencies: {
        "tool-here": "2.0.0",
        "tool-elsewhere": "2.0.0",
        "tool-wasm": "2.0.0",
        "tool-wrapper": "2.0.0",
      },
    }),
    "node_modules/tool/node_modules/shared": entry("2.1.0", { dev: true }),
    "node_modules/tool-here": entry("2.0.0", {
      ...optional,
      os: ["testos"],
      cpu: ["testcpu"],
    }),
    "node_modules/tool-elsewhere": entry("2.0.0", {
      ...optional,
      os: ["otheros"],
      cpu: ["testcpu"],
    }),
    "node_modules/tool-wasm": entry("2.0.0", {
      ...optional,
      cpu: ["wasm32"],
      dependencies: { "wasm-runtime": "1.0.0" },
    }),
    "node_modules/wasm-runtime": entry("1.0.0", optional),
    "node_modules/tool-wrapper": entry("2.0.0", {
      ...optional,
      dependencies: { "tool-elsewhere": "2.0.0" },
    }),
  };
}

const INSTALLED = [
  "node_modules/runtime",
  "node_modules/shared",
  "node_modules/tool",
  "node_modules/tool/node_modules/shared",
  "node_modules/tool-here",
];

function frontend(t, packages = locked(), installed = INSTALLED) {
  const root = mkdtempSync(join(tmpdir(), "cadrumo-frontend-install-"));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  writeFileSync(
    join(root, "package-lock.json"),
    JSON.stringify({ lockfileVersion: 3, packages }),
  );
  const { dependencies, devDependencies } = packages[""];
  writeFileSync(
    join(root, "package.json"),
    JSON.stringify({ name: "fixture", dependencies, devDependencies }),
  );
  const recorded = {};
  for (const location of installed) {
    recorded[location] = packages[location];
    mkdirSync(join(root, location), { recursive: true });
    writeFileSync(join(root, location, "package.json"), "{}");
  }
  mkdirSync(join(root, "node_modules"), { recursive: true });
  writeFileSync(
    join(root, RECORD),
    JSON.stringify({ lockfileVersion: 3, packages: recorded }),
  );
  return root;
}

function record(root, change) {
  const file = join(root, RECORD);
  const value = JSON.parse(readFileSync(file, "utf8"));
  change(value.packages);
  writeFileSync(file, JSON.stringify(value));
}

function manifest(root, change) {
  const file = join(root, "package.json");
  const value = JSON.parse(readFileSync(file, "utf8"));
  writeFileSync(file, JSON.stringify(change(value) ?? value));
}

test("a manifest the lockfile no longer matches is left to npm", (t) => {
  const root = frontend(t);
  const kept = { install: false };
  assert.partialDeepStrictEqual(installDecision(root, PLATFORM), kept);

  manifest(root, (value) => {
    value.dependencies.added = "1.0.0";
  });
  assert.deepEqual(installDecision(root, PLATFORM), {
    install: true,
    reason:
      "package.json and package-lock.json declare dependencies.added differently",
  });

  for (const kind of ["optionalDependencies", "peerDependencies"]) {
    const added = frontend(t);
    manifest(added, (value) => {
      value[kind] = { added: "1.0.0" };
    });
    assert.equal(
      installDecision(added, PLATFORM).reason,
      `package.json and package-lock.json declare ${kind}.added differently`,
    );
  }

  const changed = frontend(t);
  manifest(changed, (value) => {
    value.devDependencies.tool = "^2.0.0";
  });
  assert.equal(
    installDecision(changed, PLATFORM).reason,
    "package.json and package-lock.json declare devDependencies.tool differently",
  );

  const removed = frontend(t);
  manifest(removed, (value) => {
    delete value.devDependencies;
  });
  assert.equal(
    installDecision(removed, PLATFORM).reason,
    "package.json and package-lock.json declare devDependencies.tool differently",
  );

  for (const text of ["{", "[]", "null"]) {
    const unreadable = frontend(t);
    writeFileSync(join(unreadable, "package.json"), text);
    assert.equal(
      installDecision(unreadable, PLATFORM).reason,
      "package.json is missing or unreadable",
    );
  }
  const missing = frontend(t);
  rmSync(join(missing, "package.json"));
  assert.equal(
    installDecision(missing, PLATFORM).reason,
    "package.json is missing or unreadable",
  );
});

test("a manifest npm would write the same root entry for is in sync", (t) => {
  // npm omits an empty map and does not keep the manifest's key order.
  const reordered = frontend(t);
  manifest(reordered, (value) => ({
    peerDependencies: {},
    optionalDependencies: {},
    devDependencies: value.devDependencies,
    dependencies: value.dependencies,
  }));
  assert.equal(installDecision(reordered, PLATFORM).install, false);

  // npm records a dependency that is also optional only as optional.
  const packages = locked();
  packages[""].optionalDependencies = { "tool-here": "2.0.0" };
  const optional = frontend(t, packages);
  manifest(optional, (value) => {
    value.dependencies["tool-here"] = "2.0.0";
    value.optionalDependencies = { "tool-here": "2.0.0" };
  });
  assert.equal(installDecision(optional, PLATFORM).install, false);
});

test("a tree holding what npm installs on this platform is kept", (t) => {
  const decision = installDecision(frontend(t), PLATFORM);
  assert.deepEqual(decision, {
    install: false,
    reason: "5 installed packages match package-lock.json",
  });
});

test("a tree without a readable record is installed", (t) => {
  const root = frontend(t);
  writeFileSync(join(root, RECORD), "{");
  assert.match(installDecision(root, PLATFORM).reason, /unreadable/);
  rmSync(join(root, RECORD));
  assert.equal(installDecision(root, PLATFORM).install, true);
  rmSync(join(root, "node_modules"), { recursive: true });
  assert.equal(installDecision(root, PLATFORM).install, true);
  rmSync(join(root, "package-lock.json"));
  assert.match(installDecision(root, PLATFORM).reason, /^package-lock\.json/);
});

test("a recorded package that differs from its locked entry is installed", (t) => {
  for (const key of ["version", "resolved", "integrity"]) {
    const root = frontend(t);
    record(root, (packages) => {
      packages["node_modules/tool/node_modules/shared"][key] = "another";
    });
    const decision = installDecision(root, PLATFORM);
    assert.equal(decision.install, true);
    assert.match(
      decision.reason,
      new RegExp(`^node_modules/tool/node_modules/shared .* ${key} `),
    );
  }
});

test("a package the lockfile dropped or added is installed", (t) => {
  const root = frontend(t);
  record(root, (packages) => {
    packages["node_modules/removed"] = entry("1.0.0");
  });
  assert.match(
    installDecision(root, PLATFORM).reason,
    /^node_modules\/removed is installed but not locked/,
  );
  for (const location of INSTALLED) {
    const partial = frontend(
      t,
      locked(),
      INSTALLED.filter((installed) => installed !== location),
    );
    assert.equal(
      installDecision(partial, PLATFORM).reason,
      `${location} is locked but not installed`,
    );
  }
});

test("a recorded package whose directory is gone is installed", (t) => {
  for (const location of INSTALLED) {
    const root = frontend(t);
    rmSync(join(root, location), { recursive: true });
    const decision = installDecision(root, PLATFORM);
    assert.equal(decision.install, true);
    assert.match(decision.reason, /is recorded but absent$/);
  }
});

test("a tree installed for another platform is installed again", (t) => {
  const root = frontend(t);
  assert.equal(
    installDecision(root, { ...PLATFORM, os: "otheros" }).reason,
    "node_modules/tool-elsewhere is locked but not installed",
  );
  // The WebAssembly fallback brings its own dependency with it.
  assert.equal(
    installDecision(root, { ...PLATFORM, cpu: "wasm32" }).reason,
    "node_modules/tool-wasm is locked but not installed",
  );
  const everything = frontend(
    t,
    locked(),
    Object.keys(locked()).filter((location) => location),
  );
  assert.equal(installDecision(everything, PLATFORM).install, false);
});

test("a package bound to a C library follows npm's platform rule", (t) => {
  const packages = locked();
  packages["node_modules/tool"].optionalDependencies["tool-musl"] = "2.0.0";
  packages["node_modules/tool-musl"] = entry("2.0.0", {
    dev: true,
    optional: true,
    os: ["!otheros"],
    libc: ["musl"],
  });
  const root = frontend(t, packages);
  for (const libc of ["glibc", undefined])
    assert.equal(installDecision(root, { ...PLATFORM, libc }).install, false);
  assert.equal(
    installDecision(root, { ...PLATFORM, libc: "musl" }).reason,
    "node_modules/tool-musl is locked but not installed",
  );
});

test("a lockfile that cannot place a required package is left to npm", (t) => {
  const packages = locked();
  packages["node_modules/runtime"].dependencies.unplaced = "1.0.0";
  assert.equal(
    installDecision(frontend(t, packages), PLATFORM).reason,
    "package-lock.json does not place node_modules/runtime: unplaced",
  );
});

test("the clean install runs only for a tree that needs it", (t) => {
  const root = frontend(t);
  const calls = join(root, "calls.json");
  const npmCli = join(root, "npm-cli.mjs");
  // Stands in for npm: it records its invocation and writes the tree's record.
  writeFileSync(
    npmCli,
    `import { cpSync, mkdirSync, writeFileSync } from "node:fs";
writeFileSync(${JSON.stringify(calls)}, JSON.stringify({ arguments: process.argv.slice(2), cwd: process.cwd() }));
if (process.argv.includes("--fail")) process.exit(3);
mkdirSync("node_modules/shared", { recursive: true });
writeFileSync("node_modules/shared/package.json", "{}");
cpSync("record.json", ${JSON.stringify(RECORD)});
`,
  );
  writeFileSync(join(root, "record.json"), readFileSync(join(root, RECORD)));

  assert.equal(ensureInstalled(root, npmCli, ["ci"]), 0);
  assert.equal(existsSync(calls), false);

  rmSync(join(root, "node_modules/shared"), { recursive: true });
  rmSync(join(root, RECORD));
  assert.equal(ensureInstalled(root, npmCli, ["ci", "--fail"]), 3);
  assert.equal(ensureInstalled(root, npmCli, ["ci", "--include=dev"]), 0);
  const call = JSON.parse(readFileSync(calls, "utf8"));
  assert.deepEqual(call.arguments, ["ci", "--include=dev"]);
  assert.equal(realpathSync(call.cwd), realpathSync(root));
  assert.equal(installDecision(root).install, false);
});
