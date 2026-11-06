import assert from "node:assert/strict";
import { test } from "node:test";
import { requireServed } from "../../src/dev/servedFixtures.ts";

test("a family with no generated projection refuses and names the seeding command", () => {
  assert.throws(
    () => requireServed("modelo/*.json", {}),
    (error: Error) =>
      error.message.includes("modelo/*.json") &&
      error.message.includes("just fixtures-seed"),
  );
});

test("a family with projections is returned unchanged", () => {
  const found = { "a.json": () => 1, "b.json": () => 2 };
  assert.equal(requireServed("modelo/*.json", found), found);
});
