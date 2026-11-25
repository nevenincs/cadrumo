import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { ESLint } from "eslint";

// The bound as the Modelo generator wrote it, read here independently of the
// configuration under test.
const generated = JSON.parse(
  readFileSync(
    new URL("../../../src/shell/moduleBound.json", import.meta.url),
    "utf8",
  ),
).physicalLines;

const reported = async (text, filePath) => {
  const [result] = await new ESLint().lintText(text, { filePath });
  return result.messages.filter((message) => message.ruleId === "max-lines");
};

// Two lines in three are blank or a comment, so the rule only reports the
// planted module when it counts them.
const planted = (lines) =>
  Array.from({ length: lines }, (_, index) =>
    ["export const x = 0;", "", "// note"].at(index % 3),
  ).join("\n") + "\n";

test("the rule holds every TypeScript module to the generated bound", async () => {
  for (const filePath of ["src/planted.ts", "scripts/planted.mts"]) {
    const config = await new ESLint().calculateConfigForFile(filePath);
    const [severity, options] = config.rules["max-lines"];
    assert.equal(severity, 2, filePath);
    assert.deepEqual(
      options,
      { max: generated, skipBlankLines: false, skipComments: false },
      filePath,
    );
  }
});

test("a module one line over the bound is reported wherever it lives", async () => {
  const over = planted(generated + 1);
  for (const filePath of [
    "src/planted.ts",
    "src/components/Planted.tsx",
    "src/dev/planted.ts",
    "tests/planted.spec.ts",
    "scripts/planted.mts",
  ]) {
    assert.equal((await reported(over, filePath)).length, 1, filePath);
  }
});

test("a module at the bound passes, with or without a final newline", async () => {
  const edge = planted(generated);
  assert.deepEqual(await reported(edge, "src/edge.ts"), []);
  assert.deepEqual(await reported(edge.slice(0, -1), "src/edge.ts"), []);
});
