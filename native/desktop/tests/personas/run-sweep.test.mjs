import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import {
  BUDGET,
  caseBudgetMs,
  keepReason,
  lineProblem,
  recordedDurations,
  selectCases,
  unreachedRows,
} from "./run-sweep.mjs";

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

const world = { rows: [{ modelo: "200", year: 2025, period: "0A" }] };
const personaLine = {
  surface: "window",
  tree: "t",
  persona: "sociedad-limitada",
  modelo: null,
  year: null,
  period: null,
  loads: true,
  refusal_code: null,
  figures: null,
  reason: "",
  log: null,
};
const rowLine = {
  ...personaLine,
  modelo: "200",
  year: 2025,
  period: "0A",
  calculate: "pass",
  verify: "incomplete",
  export: "not-reached",
};

test("a row line may state export_served, as a boolean only", () => {
  assert.equal(
    lineProblem([personaLine, rowLine], world, "t", "sociedad-limitada"),
    null,
  );
  assert.equal(
    lineProblem(
      [personaLine, { ...rowLine, export_served: false }],
      world,
      "t",
      "sociedad-limitada",
    ),
    null,
  );
  assert.match(
    lineProblem(
      [personaLine, { ...rowLine, export_served: "no" }],
      world,
      "t",
      "sociedad-limitada",
    ),
    /export_served is not a boolean/,
  );
  assert.match(
    lineProblem(
      [{ ...personaLine, export_served: true }, rowLine],
      world,
      "t",
      "sociedad-limitada",
    ),
    /line keys differ/,
  );
  assert.match(
    lineProblem(
      [personaLine, { ...rowLine, surprise: 1 }],
      world,
      "t",
      "sociedad-limitada",
    ),
    /line keys differ/,
  );
});

test("a row line may state file, as a stage word only", () => {
  for (const file of ["pass", "not-shown", "refused", "not-reached", "error"])
    assert.equal(
      lineProblem(
        [personaLine, { ...rowLine, file }],
        world,
        "t",
        "sociedad-limitada",
      ),
      null,
      file,
    );
  assert.match(
    lineProblem(
      [personaLine, { ...rowLine, file: "shown" }],
      world,
      "t",
      "sociedad-limitada",
    ),
    /file shown is not a stage word/,
  );
  assert.match(
    lineProblem(
      [{ ...personaLine, file: "pass" }, rowLine],
      world,
      "t",
      "sociedad-limitada",
    ),
    /line keys differ/,
  );
});

test("a row line may state blocking_findings, as finding ids only", () => {
  assert.equal(
    lineProblem(
      [
        personaLine,
        {
          ...rowLine,
          blocking_findings: ["registry_authority_grade_insufficient"],
        },
      ],
      world,
      "t",
      "sociedad-limitada",
    ),
    null,
  );
  for (const blocking_findings of [
    [""],
    "registry_authority_grade_insufficient",
  ])
    assert.match(
      lineProblem(
        [personaLine, { ...rowLine, blocking_findings }],
        world,
        "t",
        "sociedad-limitada",
      ),
      /blocking_findings is not an array of non-empty finding ids/,
    );
  assert.match(
    lineProblem(
      [{ ...personaLine, blocking_findings: [] }, rowLine],
      world,
      "t",
      "sociedad-limitada",
    ),
    /line keys differ/,
  );
});

const at = (ms) => new Date(Date.UTC(2030, 0, 1) + ms).toISOString();
const event = (ms, name, extra = {}) =>
  JSON.stringify({ at: at(ms), event: name, ...extra });
const opened = (ms, modelo) =>
  event(ms, "workspace", { header: `Declaraciones${modelo}Some title` });

test("recorded durations are the longest start-up and per-modelo row times in the spec logs", () => {
  const dir = mkdtempSync(join(tmpdir(), "cadrumo-run-sweep-"));
  try {
    writeFileSync(
      join(dir, "sociedad-limitada-2030.log"),
      [
        event(0, "launched"),
        opened(60_000, "303"),
        opened(120_000, "200"),
        event(900_000, "form-tab"),
        '{"at":', // a killed spec's torn last line
      ].join("\n"),
    );
    writeFileSync(
      join(dir, "minorista-recargo-2030.log"),
      [
        event(0, "launched"),
        opened(90_000, "303"),
        opened(300_000, "390"),
      ].join("\n"),
    );
    writeFileSync(join(dir, "runner.log"), "not a spec log");
    const recorded = recordedDurations([dir, join(dir, "absent")]);
    assert.equal(recorded.startup, 90_000);
    assert.deepEqual([...recorded.rows].sort(), [
      ["200", 780_000],
      ["303", 210_000],
      ["390", 0],
    ]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("a case's budget grows with its own rows and recorded durations; the floor is only a minimum", () => {
  const recorded = {
    startup: 60_000,
    rows: new Map([
      ["200", 780_000],
      ["303", 60_000],
    ]),
  };
  const floor = 30 * 60_000;
  const quarters = [1, 2, 3, 4].map(() => ({ modelo: "303" }));
  assert.equal(caseBudgetMs(quarters, recorded, floor), floor);
  const heavy = [...quarters, { modelo: "200" }, { modelo: "200" }];
  assert.equal(
    caseBudgetMs(heavy, recorded, floor),
    Math.ceil((60_000 + 4 * 60_000 + 2 * 780_000) * BUDGET.margin),
  );
  const unknown = [{ modelo: "840" }];
  assert.equal(
    caseBudgetMs(unknown, { startup: 0, rows: new Map() }, 0),
    Math.ceil((BUDGET.defaultStartupMs + BUDGET.defaultRowMs) * BUDGET.margin),
  );
});

test("a timed-out case's unreached rows are the world rows its spec wrote no line for", () => {
  const rows = [
    { modelo: "303", year: "2030", period: "1T" },
    { modelo: "303", year: "2030", period: "2T" },
    { modelo: "200", year: "2030", period: "0A" },
  ];
  const lines = [
    personaLine,
    { ...rowLine, modelo: "303", year: 2030, period: "1T" },
  ];
  assert.deepEqual(unreachedRows(lines, { rows }), rows.slice(1));
  assert.equal(
    lineProblem(
      lines.map((line) => ({ ...line, tree: "t" })),
      { rows: rows.slice(0, 1).map((row) => ({ ...row, year: 2030 })) },
      "t",
      "sociedad-limitada",
    ),
    null,
  );
});

test("a run root is kept when its window refused the agent or logged an error", () => {
  const dir = mkdtempSync(join(tmpdir(), "cadrumo-sweep-keep-"));
  try {
    const logs = join(dir, "storage", "logs");
    mkdirSync(logs, { recursive: true });
    const host = join(logs, "cadrumo-native.jsonl");
    const runtime = join(logs, "cadrumo.log");
    const record = (service, failure = null) =>
      JSON.stringify({ kind: "service_event", service, failure });
    // A clean start, and a refusal the person acts on, leave nothing to keep.
    writeFileSync(
      host,
      [
        record({ event: "agent_starting", generation: 1 }),
        record({ event: "agent_refused", reason: "agent_signed_out" }),
        record({ event: "agent_ready", generation: 1, gatewayPort: 1 }),
      ].join("\n") + "\n",
    );
    writeFileSync(runtime, "2026-11-17T21:00:00.000Z [INFO] runtime: ready\n");
    assert.equal(keepReason(dir), null);
    // The operator's error: the agent refused because the runtime was not ready.
    writeFileSync(
      host,
      record({ event: "agent_refused", reason: "agent_runtime_unavailable" }) +
        "\n",
    );
    assert.match(keepReason(dir), /agent_runtime_unavailable/);
    writeFileSync(host, record(null, { code: "spawn_failed" }) + "\n");
    assert.match(keepReason(dir), /failure/);
    writeFileSync(host, "");
    writeFileSync(
      runtime,
      "2026-11-17T21:00:00.000Z [ERROR] sign_in: helper ended without result\n",
    );
    assert.match(keepReason(dir), /runtime logged an error/);
    // A root without logs has nothing that asks to keep it.
    assert.equal(keepReason(join(dir, "absent")), null);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
