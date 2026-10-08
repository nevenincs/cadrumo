import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";

import { Results } from "./results.mjs";

test("failed-run evidence is bounded, scrubbed and retains check duration", (t) => {
  const parent = resolve(tmpdir());
  const directory = mkdtempSync(join(parent, "cadrumo-result-evidence-"));
  t.after(() => {
    assert.equal(dirname(resolve(directory)), parent);
    rmSync(directory, { recursive: true });
  });
  const results = new Results(join(directory, "results"));
  const source = join(directory, "source.log");
  const secret = "fixture-secret-not-for-artifacts";
  results.secret(secret);
  writeFileSync(source, `safe failure ${secret}\n`);
  assert.equal(results.logEvidence("failure.log", source).status, "captured");
  const captured = readFileSync(
    join(results.evidenceDirectory, "failure.log"),
    "utf8",
  );
  assert.equal(captured, "safe failure <redacted>\n");

  results.record({
    id: "failed",
    title: "failure timing",
    verdict: "FAIL",
    detail: "fixture failure",
    startedAt: "2026-10-07T00:00:00.000Z",
    elapsedMs: 123.25,
  });
  results.finish({ startedAt: "2026-10-07T00:00:00.000Z" });
  const document = JSON.parse(
    readFileSync(join(results.directory, "results.json"), "utf8"),
  );
  assert.equal(document.checks[0].elapsedMs, 123.25);
  assert.equal(document.checks[0].startedAt, "2026-10-07T00:00:00.000Z");
  assert.match(
    readFileSync(join(results.directory, "summary.txt"), "utf8"),
    /123\.3 ms/,
  );

  writeFileSync(source, Buffer.alloc(4 * 1024 * 1024 + 1, 120));
  assert.equal(
    results.logEvidence("oversized.log", source).status,
    "over_limit",
  );
  assert.equal(
    results.logEvidence("absent.log", join(directory, "missing")).status,
    "unavailable",
  );
  // A closed descriptor allows the fixture log to be removed immediately on Windows.
  rmSync(source);
});
