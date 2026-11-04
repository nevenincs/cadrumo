import assert from "node:assert/strict";
import {
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { describe, test } from "node:test";
import { fileURLToPath } from "node:url";

import {
  captureAgentLogs,
  resolvesInside,
  sanitizeEvidencePart,
} from "./agent-log-evidence.mjs";
import { Results } from "./results.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const fixture = resolve(here, "fixtures", "agent-logs", "storage");
const logNames = [
  "gateway.log",
  "worker.log",
  "conversation-worker-c1.stderr.log",
  "worker-autospawn-8123.stderr.log",
  "keychain.log",
];

// The repository ignores *.log, so the log files are written beside the
// committed non-log neighbours (config, token, env, rotation) for each test.
function storageIn(root) {
  const storage = join(root, "fixture-storage");
  cpSync(fixture, storage, { recursive: true });
  const runtime = join(storage, "agent", "0123456789abcdef", "home", "runtime");
  for (const name of logNames)
    writeFileSync(join(runtime, name), `log ${name}`);
  return storage;
}

function withResults(body) {
  const root = mkdtempSync(join(tmpdir(), "agent-log-evidence-"));
  try {
    const results = new Results(join(root, "results"));
    return body(results, root);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

describe("agent log evidence", () => {
  test("captures only the allow-listed log names", () => {
    withResults((results, root) => {
      const storage = storageIn(root);
      const captures = captureAgentLogs({ results, storage, prefix: "setup" });
      const names = captures.map((capture) => capture.name).sort();
      assert.deepEqual(names, [
        "setup-agent-01234567-conversation-worker-c1.stderr.log",
        "setup-agent-01234567-gateway.log",
        "setup-agent-01234567-worker-autospawn-8123.stderr.log",
        "setup-agent-01234567-worker.log",
      ]);
      assert.ok(captures.every((capture) => capture.status === "captured"));
      assert.deepEqual(readdirSync(results.evidenceDirectory).sort(), names);
      for (const file of readdirSync(results.evidenceDirectory))
        assert.ok(
          /^log /.test(
            readFileSync(join(results.evidenceDirectory, file), "utf8"),
          ),
        );
    });
  });

  test("a runtime link pointing outside the agent storage is refused", (t) => {
    withResults((results, root) => {
      const outside = join(root, "outside");
      mkdirSync(outside);
      writeFileSync(join(outside, "gateway.log"), "outside\n");
      const copy = join(root, "storage");
      const agent = join(copy, "agent", "ffffffff00000000", "home");
      mkdirSync(agent, { recursive: true });
      try {
        symlinkSync(outside, join(agent, "runtime"), "junction");
      } catch {
        t.skip("junction not creatable here");
        return;
      }
      const captures = captureAgentLogs({
        results,
        storage: copy,
        prefix: "setup",
      });
      assert.deepEqual(captures, [
        {
          name: "setup-agent-ffffffff-gateway.log",
          status: "refused_outside_agent_storage",
        },
      ]);
      assert.equal(readdirSync(results.evidenceDirectory).length, 0);
    });
  });

  test("the resolved-path check refuses outside, equal and missing paths", () => {
    withResults((_results, root) => {
      const parent = join(root, "agent");
      mkdirSync(parent);
      writeFileSync(join(parent, "a.log"), "x");
      writeFileSync(join(root, "b.log"), "x");
      assert.equal(resolvesInside(parent, join(parent, "a.log")), true);
      assert.equal(resolvesInside(parent, join(root, "b.log")), false);
      assert.equal(resolvesInside(parent, join(parent, "..", "agent")), false);
      assert.equal(resolvesInside(parent, join(parent, "missing.log")), false);
    });
  });

  test("an over-limit log keeps its last bytes and records the original size", () => {
    withResults((results, root) => {
      const source = join(root, "big.log");
      writeFileSync(source, "0123456789ABCDEF");
      const capture = results.logEvidence("big.log", source, 6);
      assert.deepEqual(capture, {
        name: "big.log",
        status: "truncated_head",
        bytes: 6,
        originalBytes: 16,
        limitBytes: 6,
      });
      assert.equal(
        readFileSync(join(results.evidenceDirectory, "big.log"), "utf8"),
        "ABCDEF",
      );
      const exact = results.logEvidence("exact.log", source, 16);
      assert.equal(exact.status, "captured");
      assert.equal(
        results.logEvidence("gone.log", join(root, "gone.log")).status,
        "unavailable",
      );
      assert.ok(!existsSync(join(results.evidenceDirectory, "gone.log")));
    });
  });

  test("evidence names cannot carry separators", () => {
    assert.equal(sanitizeEvidencePart("a/b\\c:d"), "a_b_c_d");
    assert.equal(sanitizeEvidencePart("..\\x"), "__x");
    assert.equal(sanitizeEvidencePart("ok-1.stderr.log"), "ok-1.stderr.log");
  });
});
