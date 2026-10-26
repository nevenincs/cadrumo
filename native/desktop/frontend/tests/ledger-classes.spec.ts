import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { LEDGER_DEFINITIONS } from "../src/shell/ledger";
import { ledgerClassOf } from "../src/dev/ledgerClassesFixture";

// The scenario ledger classes each definition as the host does. The host's
// admitted list and the shipped manifest are the sources; the scenario's
// copy of the classes must equal both, definition by definition. No page is
// opened.

const ledgerModule = (name: string) =>
  readFileSync(
    fileURLToPath(
      new URL(`../../src-tauri/src/shell/ledger/${name}`, import.meta.url),
    ),
    "utf8",
  );

type Class = "read" | "write" | "review";

function admittedByHost(): Record<string, Class> {
  const list = ledgerModule("admitted.rs").match(
    /const ADMITTED: \[[^\]]*\] = \[([\s\S]*?)\n\];/,
  );
  expect(list).not.toBeNull();
  const found: Record<string, Class> = {};
  for (const entry of list![1]!.matchAll(/\("([^"]+)", (Read|Write|Review)\)/g))
    found[entry[1]!] = entry[2]!.toLowerCase() as Class;
  return found;
}

test("the scenario ledger classes every definition as the host's list does", () => {
  const host = admittedByHost();
  expect(Object.keys(host).sort()).toEqual([...LEDGER_DEFINITIONS].sort());
  for (const definition of LEDGER_DEFINITIONS)
    expect(ledgerClassOf(definition), definition).toBe(host[definition]);
});

test("the scenario ledger classes every definition as the shipped manifest does", () => {
  const shipped = JSON.parse(ledgerModule("relay_contracts.json")) as {
    operations: Record<string, { may_write: boolean; review: boolean }>;
    relay: { payload_text_limit: number };
  };
  expect(Object.keys(shipped.operations).sort()).toEqual(
    [...LEDGER_DEFINITIONS].sort(),
  );
  for (const definition of LEDGER_DEFINITIONS) {
    const facts = shipped.operations[definition]!;
    const expected: Class = facts.review
      ? "review"
      : facts.may_write
        ? "write"
        : "read";
    expect(ledgerClassOf(definition), definition).toBe(expected);
  }
});
