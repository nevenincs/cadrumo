import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { describe, test } from "node:test";
import { fileURLToPath } from "node:url";

import { overrideRefusalProblems } from "./override-refusal.mjs";

const fixtures = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "fixtures",
  "override-refusal",
);
const load = (name) => readFileSync(resolve(fixtures, name), "utf8");
const mentions = (result, text) =>
  assert(
    result.problems.some((problem) => problem.includes(text)),
    `${JSON.stringify(result.problems)} should mention ${text}`,
  );

describe("override refusal record", () => {
  test("the expected refusal sequence passes and names its pid", () => {
    const result = overrideRefusalProblems(load("expected.jsonl.fixture"));
    assert.deepEqual(result.problems, []);
    assert.equal(result.pid, 36636);
  });

  test("a gui_selected record fails", () => {
    const result = overrideRefusalProblems(load("gui-selected.jsonl.fixture"));
    mentions(result, "gui_selected");
  });

  test("a second failure fails", () => {
    const result = overrideRefusalProblems(load("extra-failure.jsonl.fixture"));
    mentions(result, "2 failure records");
  });

  test("the wrong code fails", () => {
    const result = overrideRefusalProblems(load("wrong-code.jsonl.fixture"));
    mentions(result, "other_failed");
  });

  test("a missing host_stopped fails", () => {
    const result = overrideRefusalProblems(load("no-stop.jsonl.fixture"));
    mentions(result, "host_stopped is not recorded once");
  });

  test("an exit code other than 1 fails", () => {
    const result = overrideRefusalProblems(load("exit-zero.jsonl.fixture"));
    mentions(result, "hostExitCode");
  });

  test("an empty or missing record fails", () => {
    mentions(overrideRefusalProblems(load("empty.jsonl.fixture")), "empty");
    mentions(overrideRefusalProblems(undefined), "missing");
  });

  test("a wrong operation, a foreign pid and a mixed-pid file fail", () => {
    const text = load("expected.jsonl.fixture");
    mentions(
      overrideRefusalProblems(text.replace('"webview"', '"window"')),
      "operation",
    );
    mentions(
      overrideRefusalProblems(text, { excludedPids: [36636] }),
      "another host",
    );
    mentions(
      overrideRefusalProblems(
        text.replace("36636", "7").replace(/\n.*$/s, "") + "\n" + text,
      ),
      "host pids",
    );
  });

  test("an unparsable line and a webview failure fail", () => {
    const text = load("expected.jsonl.fixture");
    mentions(overrideRefusalProblems(`${text}{nope\n`), "not a JSON object");
    mentions(
      overrideRefusalProblems(
        text.replace(
          '"status":null}\n{"sequence":5',
          '"status":null,"webviewFailure":{}}\n{"sequence":5',
        ),
      ),
      "webview failure",
    );
  });
});
