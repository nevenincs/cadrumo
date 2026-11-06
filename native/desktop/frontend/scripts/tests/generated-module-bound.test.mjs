import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import {
  moduleBound,
  oversizedModules,
  physicalLines,
} from "../generated-module-bound.mjs";

// Any bound will do: the helper enforces the one it is handed.
const BOUND = 40;

const planted = (lines, newline = "\n", final = true) =>
  Array.from({ length: lines }, (_, index) => `export const l${index} = 0;`)
    .join(newline)
    .concat(final ? newline : "");

// Runs the refusal as a generator does, in a process of its own: the helper,
// then the write it guards, reported on standard output.
const generate = (text, bound = BOUND) =>
  spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "-e",
      `import { refuseOversizedModules } from ${JSON.stringify(
        new URL("../generated-module-bound.mjs", import.meta.url).href,
      )};
      refuseOversizedModules([["planted.ts", process.argv[1]]], JSON.parse(process.argv[2]), "split it");
      console.log("wrote planted.ts");`,
      text,
      JSON.stringify(bound),
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

test("a module at the bound passes and one line over is refused", () => {
  assert.deepEqual(oversizedModules([["edge.ts", planted(BOUND)]], BOUND), []);
  assert.deepEqual(oversizedModules([["big.ts", planted(BOUND + 1)]], BOUND), [
    `big.ts takes ${BOUND + 1} lines, more than ${BOUND}`,
  ]);
});

test("a missing final line break or CRLF does not hide a line", () => {
  for (const [newline, final] of [
    ["\n", false],
    ["\r\n", true],
    ["\r\n", false],
  ]) {
    const text = planted(BOUND + 1, newline, final);
    assert.equal(oversizedModules([["big.ts", text]], BOUND).length, 1);
  }
});

test("a producer that sends no usable bound is refused", () => {
  for (const bound of [undefined, null, 0, -1, 1.5, "40"]) {
    assert.throws(() => moduleBound(bound), /no positive integer module bound/);
  }
});

test("the refusal ends the run before the write it guards", () => {
  const over = generate(planted(BOUND + 1));
  assert.equal(over.status, 1);
  assert.match(over.stderr, /planted\.ts takes 41 lines, more than 40; split/);
  assert.equal(over.stdout, "");

  const edge = generate(planted(BOUND));
  assert.equal(edge.status, 0, edge.stderr);
  assert.equal(edge.stdout, "wrote planted.ts\n");

  const unbounded = generate(planted(1), null);
  assert.notEqual(unbounded.status, 0);
  assert.equal(unbounded.stdout, "");
});
