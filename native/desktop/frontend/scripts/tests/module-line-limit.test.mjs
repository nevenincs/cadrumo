import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import {
  MODULE_LINE_LIMIT,
  oversizedModules,
  physicalLines,
} from "../module-line-limit.mjs";

const planted = (lines, newline = "\n", final = true) =>
  Array.from({ length: lines }, (_, index) => `export const l${index} = 0;`)
    .join(newline)
    .concat(final ? newline : "");

// Runs the refusal the wire-type driver runs, in a process of its own, so the
// exit status is the one a generator run would end with.
const refusal = (text) =>
  spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "-e",
      `import { refuseOversizedModules } from ${JSON.stringify(
        new URL("../module-line-limit.mjs", import.meta.url).href,
      )};
      refuseOversizedModules([["planted.ts", process.argv[1]]], "split it");`,
      text,
    ],
    { encoding: "utf8", windowsHide: true },
  );

test("a physical line is counted under every line ending", () => {
  assert.equal(physicalLines(""), 0);
  assert.equal(physicalLines("a"), 1);
  assert.equal(physicalLines("a\n"), 1);
  assert.equal(physicalLines("a\nb"), 2);
  assert.equal(physicalLines("a\r\nb\r\n"), 2);
  assert.equal(physicalLines("a\rb"), 2);
  assert.equal(physicalLines("\n\n"), 2);
});

test("a module at the limit passes and one line over is refused", () => {
  assert.deepEqual(
    oversizedModules([["edge.ts", planted(MODULE_LINE_LIMIT)]]),
    [],
  );
  assert.deepEqual(
    oversizedModules([["big.ts", planted(MODULE_LINE_LIMIT + 1)]]),
    [`big.ts takes ${MODULE_LINE_LIMIT + 1} lines, more than 1500`],
  );
});

test("a missing final line break or CRLF does not hide a line", () => {
  for (const [newline, final] of [
    ["\n", false],
    ["\r\n", true],
    ["\r\n", false],
  ]) {
    assert.equal(
      oversizedModules([
        ["big.ts", planted(MODULE_LINE_LIMIT + 1, newline, final)],
      ]).length,
      1,
    );
  }
});

test("the driver's refusal ends the run with a failure before writing", () => {
  const over = refusal(planted(MODULE_LINE_LIMIT + 1));
  assert.equal(over.status, 1);
  assert.match(
    over.stderr,
    /planted\.ts takes 1501 lines, more than 1500; split it/,
  );

  const edge = refusal(planted(MODULE_LINE_LIMIT));
  assert.equal(edge.status, 0, edge.stderr);
  assert.equal(edge.stderr, "");
});
