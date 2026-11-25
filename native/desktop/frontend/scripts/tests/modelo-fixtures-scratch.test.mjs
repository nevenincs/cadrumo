import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const driver = readFileSync(
  resolve(import.meta.dirname, "..", "modelo-fixtures.mjs"),
  "utf8",
);

// The body of every `try` block the driver closes with a `finally`.
function guardedBodies(source) {
  const bodies = [];
  for (const opening of source.matchAll(/\btry \{/g)) {
    const start = opening.index + opening[0].length;
    let depth = 1;
    let index = start;
    while (depth > 0 && index < source.length) {
      if (source[index] === "{") depth += 1;
      else if (source[index] === "}") depth -= 1;
      index += 1;
    }
    if (/^\s*finally\s*\{/.test(source.slice(index)))
      bodies.push(source.slice(start, index - 1));
  }
  return bodies;
}

test("the driver removes its envelope scratch in a finally block", () => {
  const bodies = guardedBodies(driver);
  assert.ok(
    bodies.some((body) => body.includes('python("envelopes", scratch)')),
    "the envelope read is not guarded by a finally block",
  );
  assert.match(
    driver,
    /\}\s*finally\s*\{\s*rmSync\(scratch, \{ recursive: true, force: true \}\);/,
  );
});

test("no guarded body exits the process, which would skip its finally block", () => {
  for (const body of guardedBodies(driver))
    assert.doesNotMatch(body, /process\.exit\(/);
});

test("a failed envelope read still fails the run when it has no status", () => {
  const [body] = guardedBodies(driver).filter((text) =>
    text.includes('python("envelopes", scratch)'),
  );
  assert.match(body, /process\.exitCode = read\.status \?\? 1;/);
});

test("the guarded-body reader finds an exit inside a try closed by finally", () => {
  const exiting = [
    "try {",
    "  if (failed) { process.exit(2); }",
    "} finally {",
    "  rmSync(scratch);",
    "}",
  ].join("\n");
  const unguarded = "try { process.exit(2); } catch {}";
  assert.equal(guardedBodies(exiting).length, 1);
  assert.match(guardedBodies(exiting)[0], /process\.exit\(/);
  assert.equal(guardedBodies(unguarded).length, 0);
});
