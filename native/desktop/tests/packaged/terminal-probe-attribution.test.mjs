import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, describe, test } from "node:test";

import { productLogVerdict } from "./product-log.mjs";
import {
  attributeTerminalProbe,
  TERMINAL_PROBE_CHECK,
} from "./terminal-probe-attribution.mjs";
import { FAIL, PASS } from "./verdicts.mjs";

// Synthetic values throughout: one window host, one terminal session, a flood
// that delivered BYTES and the authored acknowledgement of BYTES + 1.
const HOST = 4100;
const SESSION = 7;
const BYTES = 9000;
const START = Date.parse("2026-11-05T10:00:00.000Z");

const checks = () => [
  {
    id: TERMINAL_PROBE_CHECK,
    verdict: PASS,
    startedAt: new Date(START).toISOString(),
    elapsedMs: 500,
  },
];

const ack = (seq, at, offset, ok, extra = {}) => ({
  seq,
  at,
  by: "harness",
  cmd: "terminal_ack",
  args: { session: SESSION, offset },
  bodyBytes: 40,
  session: SESSION,
  ok,
  code: ok ? null : "invalid_arguments",
  ms: 2,
  ...extra,
});

const trace = () => [
  ack(41, START + 100, BYTES, true),
  ack(42, START + 104, BYTES + 1, false),
];

const failure = (sequence, extra = {}) => ({
  sequence,
  source: "desktop",
  timestampMs: START + 105,
  hostPid: HOST,
  kind: "failure",
  process: 3,
  terminalSession: SESSION,
  failure: {
    code: "invalid_arguments",
    operation: "terminal",
    message: "The request arguments are invalid",
    causes: [],
  },
  status: { id: 3, pid: 4200, role: "repl", terminalBytes: BYTES },
  role: "repl",
  ...extra,
});

const attribute = (overrides = {}) =>
  attributeTerminalProbe({
    records: [failure(66)],
    trace: trace(),
    checks: checks(),
    windowHostPid: HOST,
    ...overrides,
  });

describe("terminal probe attribution", () => {
  test("accepts exactly the authored pair", () => {
    const records = [failure(66)];
    const attributed = attribute({ records });
    assert.equal(attributed.size, 1);
    assert.deepEqual(attributed.get(records[0]), {
      check: TERMINAL_PROBE_CHECK,
      call: 42,
      record: 66,
      hostPid: HOST,
      terminalSession: SESSION,
      offset: BYTES + 1,
    });
  });

  const refused = {
    "a record without terminalSession": () => {
      const record = failure(66);
      delete record.terminalSession;
      return { records: [record] };
    },
    "a non-numeric terminalSession": () => ({
      records: [failure(66, { terminalSession: String(SESSION) })],
    }),
    "a failure with no harness call": () => ({ trace: [trace()[0]] }),
    "the same code for another session": () => ({
      records: [failure(66, { terminalSession: SESSION + 1 })],
    }),
    "another host's record": () => ({
      records: [failure(66, { hostPid: HOST + 1 })],
    }),
    "no window host pid": () => ({ windowHostPid: null }),
    "a byte count other than offset - 1": () => ({
      records: [
        failure(66, {
          status: { id: 3, pid: 4200, role: "repl", terminalBytes: BYTES - 1 },
        }),
      ],
    }),
    "no accepted acknowledgement at the count": () => ({
      trace: [ack(41, START + 100, BYTES - 5, true), trace()[1]],
    }),
    "a refused prior acknowledgement": () => ({
      trace: [ack(41, START + 100, BYTES, false), trace()[1]],
    }),
    "the accepted acknowledgement after the probe": () => ({
      trace: [trace()[1], ack(43, START + 106, BYTES, true)],
    }),
    "a frontend-originated call": () => ({
      trace: trace().map((call) => ({ ...call, by: "shell" })),
    }),
    "a frontend refusal beside a harness accept": () => ({
      trace: [trace()[0], { ...trace()[1], by: "shell" }],
    }),
    "an accepted overshoot": () => ({
      trace: [trace()[0], { ...trace()[1], ok: true, code: null }],
    }),
    "another refusal code": () => ({
      trace: [trace()[0], { ...trace()[1], code: "not_found" }],
    }),
    "another command": () => ({
      trace: [trace()[0], { ...trace()[1], cmd: "terminal_write" }],
    }),
    "another failure code": () => ({
      records: [
        failure(66, {
          failure: { code: "not_found", operation: "terminal", causes: [] },
        }),
      ],
    }),
    "another failure operation": () => ({
      records: [
        failure(66, {
          failure: {
            code: "invalid_arguments",
            operation: "process",
            causes: [],
          },
        }),
      ],
    }),
    "a call outside the flood-every-byte window": () => ({
      trace: [
        ack(41, START + 600, BYTES, true),
        ack(42, START + 604, BYTES + 1, false),
      ],
      records: [failure(66, { timestampMs: START + 605 })],
    }),
    "a call that ends after the window": () => ({
      trace: [trace()[0], { ...trace()[1], at: START + 499 }],
      records: [failure(66, { timestampMs: START + 500 })],
    }),
    "no flood-every-byte check": () => ({ checks: [] }),
    "a record after the call window": () => ({
      records: [failure(66, { timestampMs: START + 104 + 2 + 2 })],
    }),
    "a record before the call window": () => ({
      records: [failure(66, { timestampMs: START + 104 - 2 })],
    }),
    "no trace": () => ({ trace: null }),
  };
  for (const [name, overrides] of Object.entries(refused))
    test(`refuses ${name}`, () => {
      assert.equal(attribute(overrides()).size, 0);
    });

  test("admits the record within one millisecond of the call window", () => {
    for (const timestampMs of [START + 103, START + 107])
      assert.equal(
        attribute({ records: [failure(66, { timestampMs })] }).size,
        1,
      );
  });

  test("one call excuses one record and the second stays", () => {
    const records = [failure(67), failure(66)];
    const attributed = attribute({ records });
    assert.equal(attributed.size, 1);
    assert(attributed.has(records[1]), "the earlier sequence is excused");
  });

  test("a second authored-looking pair is not excused", () => {
    const records = [failure(66), failure(68, { timestampMs: START + 205 })];
    const attributed = attribute({
      records,
      trace: [
        ...trace(),
        ack(50, START + 200, BYTES, true),
        ack(51, START + 204, BYTES + 1, false),
      ],
    });
    assert.equal(attributed.size, 1);
    assert(attributed.has(records[0]));
  });
});

describe("terminal probe attribution in the product-log gate", () => {
  const roots = [];
  after(() => {
    for (const root of roots) rmSync(root, { recursive: true, force: true });
  });
  const defaults = {
    logs: "logs",
    log_file: "logs/cadrumo.log",
    log_format:
      "%(asctime)s [%(levelname)s] %(name)s: %(message)s | %(diagnostic_context)s",
  };
  const gate = (records, overrides = {}) => {
    const root = mkdtempSync(join(tmpdir(), "terminal-attribution-"));
    roots.push(root);
    const logs = join(root, "storage", "logs");
    mkdirSync(logs, { recursive: true });
    writeFileSync(
      join(logs, "cadrumo.log"),
      `${new Date(START).toISOString()} [INFO] a.b: ok | {"process_id":1}\n`,
    );
    writeFileSync(
      join(logs, "cadrumo-native.jsonl"),
      records.map((record) => JSON.stringify(record)).join("\n") + "\n",
    );
    return productLogVerdict({
      storage: join(root, "storage"),
      defaults,
      checks: checks(),
      allowlist: [],
      run: "window",
      ipcTrace: trace(),
      windowHostPid: HOST,
      ...overrides,
    });
  };
  const disposition = (verdict, name) =>
    verdict.data.groups.filter((group) => group.disposition === name);

  test("the authored pair passes as one attributed record", () => {
    const verdict = gate([failure(66)]);
    assert.equal(verdict.verdict, PASS, verdict.detail);
    const [group, ...rest] = disposition(verdict, "attributed");
    assert.equal(rest.length, 0);
    assert.equal(group.count, 1);
    assert.equal(group.logger, "desktop.failure");
    assert.deepEqual(
      { call: group.attribution.call, record: group.attribution.record },
      { call: 42, record: 66 },
    );
    assert.equal(disposition(verdict, "allowed").length, 0);
  });

  test("a record without terminalSession fails the gate", () => {
    const record = failure(66);
    delete record.terminalSession;
    const verdict = gate([record]);
    assert.equal(verdict.verdict, FAIL);
    assert.equal(disposition(verdict, "attributed").length, 0);
  });

  test("an extra record for the one call stays unexpected", () => {
    const verdict = gate([failure(66), failure(67)]);
    assert.equal(verdict.verdict, FAIL);
    assert.equal(disposition(verdict, "attributed").length, 1);
    const [unexpected] = disposition(verdict, "unexpected");
    assert.equal(unexpected.count, 1);
  });

  test("a frontend-originated call fails the gate", () => {
    const verdict = gate([failure(66)], {
      ipcTrace: trace().map((call) => ({ ...call, by: "shell" })),
    });
    assert.equal(verdict.verdict, FAIL);
  });

  test("the setup run, with no trace or host pid, attributes nothing", () => {
    const verdict = gate([failure(66)], {
      run: "setup",
      ipcTrace: null,
      windowHostPid: null,
    });
    assert.equal(verdict.verdict, FAIL);
    assert.equal(disposition(verdict, "attributed").length, 0);
  });

  // The probe belongs to the window run alone: evidence that would excuse the
  // record there excuses nothing in any other run.
  for (const run of ["setup", "unknown"])
    test(`the ${run} run attributes nothing even with a valid trace, host and check`, () => {
      const verdict = gate([failure(66)], { run });
      assert.equal(verdict.verdict, FAIL);
      assert.equal(disposition(verdict, "attributed").length, 0);
      assert.equal(disposition(verdict, "unexpected").length, 1);
    });
});
