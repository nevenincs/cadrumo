import assert from "node:assert/strict";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { describe, test } from "node:test";
import { fileURLToPath } from "node:url";

import {
  allowlistProblems,
  compileLineFormat,
  loadAllowlist,
  normalizeMessage,
  parseDiagnosticLog,
  phaseWindowsOf,
  productLogVerdict,
  recordedChecks,
} from "./product-log.mjs";
import { FAIL, PASS } from "./verdicts.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const fixtures = resolve(here, "fixtures", "product-log");
const defaults = JSON.parse(
  readFileSync(resolve(fixtures, "defaults.json"), "utf8"),
);
const allowlist = loadAllowlist(resolve(here, "product-log-allowlist.json"));

function runCase(name, run = "setup") {
  const root = resolve(fixtures, name);
  const checksFile = resolve(root, "checks.json");
  return productLogVerdict({
    storage: resolve(root, "storage"),
    defaults,
    checks: existsSync(checksFile)
      ? JSON.parse(readFileSync(checksFile, "utf8"))
      : [],
    allowlist,
    run,
  });
}

const unexpected = (verdict) =>
  verdict.data.groups.filter((group) => group.disposition === "unexpected");

describe("line format", () => {
  const compiled = compileLineFormat(defaults.log_format);

  test("the fixture format is the one the application environment declares", () => {
    const declared = readFileSync(
      resolve(here, "..", "..", "..", "application-environment.toml"),
      "utf8",
    ).match(/^log_format\s*=\s*"(.*)"$/m);
    assert(declared, "the application environment declares log_format");
    assert.equal(defaults.log_format, declared[1]);
  });

  test("rejects a format it cannot compile", () => {
    assert.throws(
      () => compileLineFormat("%(message)s"),
      /unsupported log format/,
    );
  });

  test("parses header, message and the last parseable context", () => {
    const { records, orphans } = parseDiagnosticLog(
      '2026-11-04T18:50:00.000Z [INFO] a.b: shape x | {"not": json | {"process_id":7}\n',
      compiled,
    );
    assert.equal(orphans.length, 0);
    assert.equal(records.length, 1);
    assert.equal(records[0].message, 'shape x | {"not": json');
    assert.deepEqual(records[0].context, { process_id: 7 });
  });

  test("counts a traceback as continuation of its record and flags orphans", () => {
    const { records, orphans } = parseDiagnosticLog(
      [
        "Traceback (most recent call last):",
        '2026-11-04T18:50:00.000Z [ERROR] a.b: failed | {"process_id":7}',
        "Traceback (most recent call last):",
        "ValueError: x",
      ].join("\n"),
      compiled,
    );
    assert.equal(records.length, 1);
    assert.equal(records[0].continuation.length, 2);
    assert.deepEqual(orphans, [{ line: 1 }]);
  });
});

describe("normalization", () => {
  test("digits, hex, sha256 tokens and paths become placeholders", () => {
    assert.equal(
      normalizeMessage(
        "failed in 30 seconds from sha256:27f8dcfe-sha256:e7c3969b at <storage>\\agent\\x.log pid 61640",
      ),
      "failed in <n> seconds from <n> at <path> pid <n>",
    );
  });
});

describe("verdict over fixtures", () => {
  test("regression: the worker readiness defect fails even with every check listed over the whole timeline", () => {
    const verdict = runCase("regression");
    console.log(`regression verdict: ${verdict.verdict} - ${verdict.detail}`);
    assert.equal(verdict.verdict, FAIL);
    const groups = unexpected(verdict);
    const has = (level, text) =>
      groups.some(
        (group) =>
          group.level === level &&
          group.logger === "cadrumo_agent.control.worker_management" &&
          group.template.includes(text),
      );
    assert(
      has("ERROR", "Worker failed to become ready within <n> seconds"),
      "ready timeout",
    );
    assert(has("ERROR", "Failed to spawn worker"), "spawn failure");
    assert(
      groups.some(
        (group) =>
          group.level === "WARNING" &&
          group.template.includes("Withholding the worker credential") &&
          group.template.includes("(claim: free)"),
      ),
      "credential withheld warning",
    );
    assert.match(verdict.detail, /cadrumo_agent\.control\.worker_management/);
  });

  test("regression: the sanctioned KDF warning is allowed while the rest still fails", () => {
    const verdict = runCase("regression");
    const allowed = verdict.data.groups.filter(
      (group) => group.disposition === "allowed",
    );
    assert.deepEqual(
      allowed.map((group) => group.entry),
      ["kdf-refused-wrong-password"],
    );
  });

  test("regression: relayed agent twins are not counted twice", () => {
    const verdict = runCase("regression");
    const ready = unexpected(verdict).filter((group) =>
      group.template.includes("Worker failed to become ready"),
    );
    assert.equal(ready.length, 1);
    assert.equal(ready[0].count, 2);
    assert(!verdict.data.groups.some((group) => group.source === "agent"));
  });

  test("clean passes and reports no unexpected group", () => {
    const verdict = runCase("clean");
    assert.equal(verdict.verdict, PASS, verdict.detail);
    assert.equal(unexpected(verdict).length, 0);
  });

  test("the KDF warning passes only inside the wrong-password phase of a recorded check", () => {
    assert.equal(runCase("context-in").verdict, PASS);
    const out = runCase("context-out");
    assert.equal(out.verdict, FAIL);
    assert(
      unexpected(out).some((group) =>
        group.logger.includes("_kdf_worker_supervision"),
      ),
    );
    const missing = runCase("context-missing");
    assert.equal(missing.verdict, FAIL);
    assert(missing.data.inactiveEntries.includes("kdf-refused-wrong-password"));
  });

  test("the KDF entry does not apply in a run it does not list", () => {
    assert.equal(runCase("context-in", "other").verdict, FAIL);
  });

  test("a multi-line ERROR is one finding", () => {
    const verdict = runCase("multiline-error");
    assert.equal(verdict.verdict, FAIL);
    const groups = unexpected(verdict);
    assert.equal(groups.length, 1);
    assert.equal(groups[0].count, 1);
    assert.equal(groups[0].logger, "cadrumo.application.example");
  });

  test("a pipe and brace inside a message does not hide or invent a finding", () => {
    assert.equal(runCase("pipe-in-message").verdict, PASS);
  });

  test("an orphan traceback fails", () => {
    const verdict = runCase("orphan-traceback");
    assert.equal(verdict.verdict, FAIL);
    assert(
      unexpected(verdict).some(
        (group) => group.logger === "product-log.unparsed",
      ),
    );
  });

  test("an ERROR in a rotated file fails", () => {
    const verdict = runCase("rotated");
    assert.equal(verdict.verdict, FAIL);
    assert(verdict.data.sources.includes("cadrumo.log.1"));
  });

  test("a missing primary log fails", () => {
    const verdict = runCase("missing-log");
    assert.equal(verdict.verdict, FAIL);
    assert.match(verdict.detail, /missing cadrumo\.log/);
  });

  test("a traceback only in worker stderr fails", () => {
    const verdict = runCase("stderr-only");
    assert.equal(verdict.verdict, FAIL);
    assert(
      unexpected(verdict).some((group) => group.logger === "agent.stderr"),
    );
  });

  test("native ERROR records and the setup failure fail even when their fault test is recorded", () => {
    const verdict = runCase("native-errors");
    assert.equal(verdict.verdict, FAIL);
    const templates = unexpected(verdict)
      .filter((group) => group.source === "native")
      .map((group) => `${group.template} x${group.count}`);
    assert(
      templates.includes(
        "command_rejected command=agent_provider_catalog code=- x9",
      ),
      templates.join("\n"),
    );
    assert(
      templates.includes(
        "command_rejected command=agent_local_models code=- x2",
      ),
    );
    assert(
      templates.includes(
        "command_rejected command=sede_view_resize code=not_admitted x3",
      ),
    );
    assert(
      templates.some((text) =>
        text.startsWith(
          "failure code=setup_failed reason=setup_browser_failed causes=blocked_by_network",
        ),
      ),
    );
  });
});

describe("sanctioned native setup failure", () => {
  test("passes exactly once with its fault test recorded as passed", () => {
    const verdict = runCase("native-allowed");
    assert.equal(verdict.verdict, PASS, verdict.detail);
    assert.deepEqual(
      verdict.data.groups
        .filter((group) => group.disposition === "allowed")
        .map((group) => group.entry),
      ["setup-browser-blocked-by-proxy"],
    );
  });

  test("a second occurrence fails", () => {
    const verdict = runCase("native-twice");
    assert.equal(verdict.verdict, FAIL);
    assert.equal(unexpected(verdict).length, 1);
    assert.equal(unexpected(verdict)[0].count, 1);
  });

  test("a different cause fails", () => {
    assert.equal(runCase("native-other-cause").verdict, FAIL);
  });

  test("a run without the fault test fails", () => {
    const verdict = runCase("native-no-check");
    assert.equal(verdict.verdict, FAIL);
    assert(
      verdict.data.inactiveEntries.includes("setup-browser-blocked-by-proxy"),
    );
  });

  test("a fault test that did not pass fails", () => {
    assert.equal(runCase("native-check-failed").verdict, FAIL);
  });

  test("a record outside the fault test window fails", () => {
    const root = resolve(fixtures, "native-allowed");
    const verdict = productLogVerdict({
      storage: resolve(root, "storage"),
      defaults,
      checks: [
        {
          id: "provisioning-9-failure",
          verdict: "PASS",
          startedAt: "2026-11-04T18:00:00.000Z",
          elapsedMs: 20000,
        },
      ],
      allowlist,
      run: "setup",
    });
    assert.equal(verdict.verdict, FAIL);
  });

  test("is not available to the window run", () => {
    assert.equal(runCase("native-allowed", "window").verdict, FAIL);
  });
});

describe("other sources", () => {
  function scratch(files) {
    const root = mkdtempSync(join(tmpdir(), "product-log-"));
    for (const [name, text] of Object.entries(files)) {
      const path = resolve(root, "storage", name);
      mkdirSync(dirname(path), { recursive: true });
      writeFileSync(path, text);
    }
    return root;
  }
  const quiet = '2026-11-04T18:50:00.000Z [INFO] a.b: ok | {"process_id":1}\n';
  const verdictOf = (root) =>
    productLogVerdict({
      storage: resolve(root, "storage"),
      defaults,
      checks: [],
      allowlist,
    });

  test("a non-empty stall dump fails and an empty one does not", () => {
    const stalled = scratch({
      "logs/cadrumo.log": quiet,
      "logs/profile-worker-stall-7.txt": "thread dump",
    });
    const empty = scratch({
      "logs/cadrumo.log": quiet,
      "logs/profile-worker-stall-7.txt": "",
    });
    try {
      assert.equal(verdictOf(stalled).verdict, FAIL);
      assert.equal(verdictOf(empty).verdict, PASS);
    } finally {
      rmSync(stalled, { recursive: true, force: true });
      rmSync(empty, { recursive: true, force: true });
    }
  });

  test("a malformed structured agent line fails", () => {
    const root = scratch({
      "logs/cadrumo.log": quiet,
      "agent/h/home/runtime/gateway.log": "not json\n",
    });
    try {
      const verdict = verdictOf(root);
      assert.equal(verdict.verdict, FAIL);
      assert(
        unexpected(verdict).some(
          (group) => group.logger === "product-log.malformed",
        ),
      );
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  test("an ERROR found only in an agent log is reported by hash, not text", () => {
    const line = JSON.stringify({
      schema: "cadrumo-agent.log/1",
      timestamp: "2026-11-04T18:50:00.000+00:00",
      seq: 1,
      pid: 9,
      level: "ERROR",
      name: "cadrumo_agent.worker.app",
      message: "private-looking text",
      service: "worker",
    });
    const root = scratch({
      "logs/cadrumo.log": quiet,
      "agent/h/home/runtime/worker.log": `${line}\n`,
    });
    try {
      const verdict = verdictOf(root);
      assert.equal(verdict.verdict, FAIL);
      assert(!JSON.stringify(verdict).includes("private-looking text"));
      assert(
        unexpected(verdict).some((group) =>
          /^sha256:[0-9a-f]{16}$/.test(group.template),
        ),
      );
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  test("ungated WARNING records are observed without failing", () => {
    const root = scratch({
      "logs/cadrumo.log":
        '2026-11-04T18:50:00.000Z [WARNING] cadrumo.other.module: careful | {"process_id":1}\n',
    });
    try {
      const verdict = verdictOf(root);
      assert.equal(verdict.verdict, PASS);
      assert(
        verdict.data.groups.some((group) => group.disposition === "observed"),
      );
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});

describe("recorded checks", () => {
  test("phase windows are absolute and attach to their check", () => {
    const phases = phaseWindowsOf({
      originAt: "2026-11-04T18:00:00.000Z",
      phases: [{ phase: "ui-wrong-password", startedMs: 1500, elapsedMs: 751 }],
    });
    assert.deepEqual(phases, [
      {
        phase: "ui-wrong-password",
        startedAt: "2026-11-04T18:00:01.500Z",
        elapsedMs: 751,
      },
    ]);
    const checks = recordedChecks(
      [
        {
          id: "canonical-sign-in",
          startedAt: "2026-11-04T18:00:00.000Z",
          elapsedMs: 9,
        },
        { id: "unstamped" },
      ],
      { "canonical-sign-in": phases },
    );
    assert.deepEqual(
      checks.map((check) => check.id),
      ["canonical-sign-in"],
    );
    assert.equal(checks[0].phases.length, 1);
  });
});

describe("allow-list", () => {
  const harness = readFileSync(
    resolve(here, "..", "packaged.test.mjs"),
    "utf8",
  );
  const entry = allowlist[0];

  test("is valid and names only existing fault tests", () => {
    assert.deepEqual(allowlistProblems(allowlist), []);
    for (const item of allowlist) {
      assert(
        harness.includes(`"${item.fault_test.check}"`),
        `${item.id}: check literal`,
      );
      const source = resolve(here, "..", item.fault_test.source);
      assert(existsSync(source), `${item.id}: fault test source exists`);
      if (item.fault_test.phase)
        assert(
          readFileSync(source, "utf8").includes(`"${item.fault_test.phase}"`),
          `${item.id}: phase literal`,
        );
    }
  });

  test("refuses entries that would excuse errors, natives or broad messages", () => {
    const bad = (patch) => allowlistProblems([{ ...entry, ...patch }]);
    assert.notEqual(bad({ level: "ERROR" }).length, 0);
    assert.notEqual(bad({ source: "native" }).length, 0);
    const native = allowlist.find((item) => item.source === "native");
    const badNative = (patch) => allowlistProblems([{ ...native, ...patch }]);
    assert.deepEqual(badNative({}), []);
    assert.notEqual(
      badNative({ native: { ...native.native, cause_reason: "" } }).length,
      0,
    );
    assert.notEqual(badNative({ native: { kind: "failure" } }).length, 0);
    assert.notEqual(badNative({ runs: ["setup", "window"] }).length, 0);
    assert.notEqual(badNative({ max_count: 2 }).length, 0);
    assert.notEqual(
      badNative({
        fault_test: { ...native.fault_test, require_verdict: undefined },
      }).length,
      0,
    );
    assert.notEqual(badNative({ logger: "desktop.frontend" }).length, 0);
    assert.notEqual(bad({ message: "kdf" }).length, 0);
    assert.notEqual(bad({ message: "^kdf.*$" }).length, 0);
    assert.notEqual(bad({ logger: "cadrumo.*" }).length, 0);
    assert.notEqual(bad({ justification: "short" }).length, 0);
    assert.notEqual(bad({ fault_test: undefined }).length, 0);
    assert.notEqual(bad({ max_count: 0 }).length, 0);
    assert.notEqual(allowlistProblems([entry, entry]).length, 0);
  });

  test("holds only the two sanctioned entries, none for a rejected command", () => {
    assert.deepEqual(
      allowlist.map((item) => [item.id, item.source, item.fault_test.check]),
      [
        ["kdf-refused-wrong-password", "python", "canonical-sign-in"],
        ["setup-browser-blocked-by-proxy", "native", "provisioning-9-failure"],
      ],
    );
  });
});
