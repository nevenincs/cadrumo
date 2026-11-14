import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { selectCases } from "./run-sweep.mjs";

const planned = [
  { persona: "sociedad-limitada", horizon: 2025, rows: 4 },
  { persona: "sociedad-limitada", horizon: 2026, rows: 4 },
  { persona: "minorista-recargo", horizon: 2026, rows: 6 },
];

test("without --persona every case is selected", () => {
  assert.deepEqual(selectCases(planned, undefined), planned);
});

test("a persona or persona@horizon selects its cases", () => {
  assert.deepEqual(
    selectCases(planned, "minorista-recargo,sociedad-limitada@2025"),
    [planned[0], planned[2]],
  );
});

test("a name matching no case is refused and named, never skipped", () => {
  assert.throws(
    () => selectCases(planned, "sociedad-limitada,comercio-minorista"),
    /--persona names no case of the rows file: comercio-minorista$/,
  );
  assert.throws(
    () => selectCases(planned, "sociedad-limitada@2019"),
    /sociedad-limitada@2019/,
  );
});

test("the command exits non-zero naming an unknown persona", () => {
  const dir = mkdtempSync(join(tmpdir(), "cadrumo-run-sweep-"));
  try {
    const rows = join(dir, "rows-test.jsonl");
    writeFileSync(
      rows,
      `${JSON.stringify({ persona: "sociedad-limitada", horizon: 2026, modelo: "200", period: "0A" })}\n`,
    );
    const run = spawnSync(
      process.execPath,
      [
        fileURLToPath(new URL("./run-sweep.mjs", import.meta.url)),
        "--rows",
        rows,
        "--persona",
        "comercio-minorista",
        "--dry-run",
      ],
      { encoding: "utf8" },
    );
    assert.notEqual(run.status, 0);
    assert.match(run.stderr + run.stdout, /comercio-minorista/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
