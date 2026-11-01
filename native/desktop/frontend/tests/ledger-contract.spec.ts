import { expect, test } from "@playwright/test";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import {
  CLASSIFICATIONS,
  DIRECTIONS,
  EVIDENCE_UPDATE_FIELDS,
  INVOICE_UPDATE_FIELDS,
  LEDGER_UPDATE_FIELDS,
  LIFECYCLE_STATES,
  OPERATION_TYPES,
  PAYMENT_STATUSES,
} from "../src/shell/ledgerContract";

// The ledger's fixed enums and correction masks are generated from the Python
// models that own them. The shipped module must be fresh, and the check must
// refuse a stale one, so a member added or dropped in Python cannot reach the
// window unseen.

const driver = resolve(import.meta.dirname, "../scripts/ledger-contract.mjs");
const shipped = resolve(import.meta.dirname, "../src/shell/ledgerContract.ts");

const check = (target: string) =>
  spawnSync("node", [driver, "--check", "--target", target], {
    encoding: "utf8",
    windowsHide: true,
  });

test("the shipped contract matches what the Python models generate", () => {
  const run = check(shipped);
  expect(run.stderr).toBe("");
  expect(run.status).toBe(0);
});

test("the check refuses a contract with a member dropped, added or reordered", () => {
  const scratch = mkdtempSync(join(tmpdir(), "ledger-contract-"));
  try {
    const original = readFileSync(shipped, "utf8");
    const target = join(scratch, "ledgerContract.ts");
    const defects = {
      dropped: original.replace('  "SPLIT",\n', ""),
      added: original.replace(
        '  "SPLIT",\n',
        '  "SPLIT",\n  "SOMETHING_NEW",\n',
      ),
      reordered: original.replace(
        '  "INCOMING",\n  "OUTGOING",\n',
        '  "OUTGOING",\n  "INCOMING",\n',
      ),
    };
    for (const [name, defective] of Object.entries(defects)) {
      expect(defective, name).not.toBe(original);
      writeFileSync(target, defective);
      const run = check(target);
      expect(run.status, name).toBe(1);
      expect(run.stderr, name).toContain("is stale");
    }
    writeFileSync(target, original);
    expect(check(target).status).toBe(0);
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
});

test("the generated lists carry the members the window reads", () => {
  expect(CLASSIFICATIONS.slice(0, 3)).toEqual([
    "BUSINESS",
    "PERSONAL",
    "MIXED",
  ]);
  expect(DIRECTIONS).toContain("INTERNAL_TRANSFER");
  expect(LIFECYCLE_STATES).toContain("ACTIVE");
  expect(PAYMENT_STATUSES).toContain("PARTIALLY_PAID");
  expect(OPERATION_TYPES).toContain("I");
  expect(LEDGER_UPDATE_FIELDS).toContain("own_account_id");
  expect(INVOICE_UPDATE_FIELDS).not.toContain("invoice_number");
  expect(EVIDENCE_UPDATE_FIELDS).toContain("invoice_date");
});
