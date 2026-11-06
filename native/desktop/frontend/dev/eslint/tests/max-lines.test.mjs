import assert from "node:assert/strict";
import { test } from "node:test";
import { ESLint } from "eslint";
import { MODULE_LINE_LIMIT } from "../../../scripts/module-line-limit.mjs";

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

test("a module one line over the limit is reported wherever it lives", async () => {
  const over = planted(MODULE_LINE_LIMIT + 1);
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

test("a module at the limit passes, with or without a final newline", async () => {
  const edge = planted(MODULE_LINE_LIMIT);
  assert.deepEqual(await reported(edge, "src/edge.ts"), []);
  assert.deepEqual(await reported(edge.slice(0, -1), "src/edge.ts"), []);
});
