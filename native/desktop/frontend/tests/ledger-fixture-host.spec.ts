import { expect, test } from "@playwright/test";
import { fixtureLedger } from "../src/dev/fixtures/ledger";
import type { FileToken } from "../src/shell/ledger";
import {
  RELAY_PAYLOAD_LIMIT,
  RELAY_REQUEST_LIMIT,
} from "../src/shell/relayBounds";

// The scenario ledger holds to the host's bounds and to its handling of a
// write whose settlement was not seen. The scenario ledger needs a window; a
// bare one stands in for it here. No page is opened.

const stand = globalThis as unknown as { window?: unknown };
stand.window = {
  location: { search: "" },
  setTimeout: globalThis.setTimeout,
};
const { ledgerFixture, replyTooLarge, tooLarge } =
  await import("../src/dev/ledgerFixture");

const ARCHIVE = "ledger.archive";

test("a payload is refused over the host's bytes, not its characters", () => {
  const request = (reason: string) => ({ transaction_id: "x", reason });
  const empty = JSON.stringify(request("")).length;
  // Exactly the payload limit passes; one byte more does not.
  expect(
    tooLarge(ARCHIVE, request("a".repeat(RELAY_PAYLOAD_LIMIT - empty))),
  ).toBe(false);
  expect(
    tooLarge(ARCHIVE, request("a".repeat(RELAY_PAYLOAD_LIMIT - empty + 1))),
  ).toBe(true);
  // Characters of three bytes: a third of the bound in characters fits,
  // and one more character is over its bytes.
  const euros = Math.floor((RELAY_PAYLOAD_LIMIT - empty) / 3);
  expect(tooLarge(ARCHIVE, request("\u20ac".repeat(euros)))).toBe(false);
  expect(tooLarge(ARCHIVE, request("\u20ac".repeat(euros + 1)))).toBe(true);
  // The relay's whole request has room for the frame around a full payload.
  expect(RELAY_REQUEST_LIMIT).toBeGreaterThan(RELAY_PAYLOAD_LIMIT);
});

test("a reply is lost over sixteen mebibytes of bytes, not of characters", () => {
  const mebibyte = 1024 * 1024;
  expect(replyTooLarge("a".repeat(15 * mebibyte))).toBe(false);
  expect(replyTooLarge("a".repeat(17 * mebibyte))).toBe(true);
  // Characters of three bytes: 5 MiB of them are 15 MiB, 6 MiB are 18 MiB.
  expect(replyTooLarge("\u20ac".repeat(5 * mebibyte))).toBe(false);
  expect(replyTooLarge("\u20ac".repeat(6 * mebibyte))).toBe(true);
});

test("a write whose settlement was not seen can be observed, and a read is never unknown", async () => {
  const movement = fixtureLedger().movements.find(
    (found) => !found.sealed && found.transaction.lifecycle_state === "ACTIVE",
  )!;
  const port = ledgerFixture({
    say: () => undefined,
    wait: async () => undefined,
    signedIn: () => true,
    shape: "unknown",
  });
  const failure = await port
    .submit(ARCHIVE, {
      transaction_id: movement.transaction.transaction_id,
      reason: "Duplicado",
    })
    .then(
      () => null,
      (error: { code: string; operation_id: string | null }) => error,
    );
  expect(failure?.code).toBe("unknown");
  expect(failure?.operation_id).toMatch(/^[0-9a-f]{64}$/);
  // The write landed: observing it answers how it settled.
  const observed = await port.observe(failure!.operation_id!);
  expect(observed.kind).toBe("settled");
  // A definition the host classes as a read settles whatever the shape.
  const read = await port.submit("ledger.rule.list", {});
  expect(read.kind).toBe("settled");
});

test("the scenario's readiness check asks what the product's does: a usage ratio of Mixed, and a category of a refund", async () => {
  const port = ledgerFixture({
    say: () => undefined,
    wait: async () => undefined,
    signedIn: () => true,
    shape: "fixture",
  });
  // A quarter of its own, which no seeded movement reaches.
  const period = { filing_year: 2031, code: "1T" };
  const added = async (key: string, facts: Record<string, string>) => {
    const outcome = await port.submit("ledger.add", {
      booked_date: "2031-02-03",
      amount: "36.30",
      currency: "EUR",
      description: `MOVEMENT ${key}`,
      idempotency_key: key.padEnd(32, "0"),
      direction: "OUTGOING",
      ...facts,
    });
    if (outcome.kind !== "settled") throw new Error("not added");
    return outcome.result.transaction!.transaction_id;
  };
  const mixed = await added("mixed", {
    business_classification: "MIXED",
    business_pct: "0.3",
    category_id: "telefonia_movil",
  });
  const refund = await added("refund", {
    direction: "INCOMING",
    business_classification: "BUSINESS",
    purchase_invoice_evidence_id: "e".repeat(64),
  });
  const income = await added("income", {
    direction: "INCOMING",
    business_classification: "BUSINESS",
  });
  const reasons = async () => {
    const outcome = await port.submit("ledger.preflight", { period });
    if (outcome.kind !== "settled") throw new Error("not checked");
    return outcome.result.issues.map(
      (issue) => `${issue.transaction_id}:${issue.reason}`,
    );
  };
  expect((await reasons()).sort()).toEqual(
    [
      `${mixed}:missing_proportionality_reference`,
      `${refund}:missing_category`,
    ].sort(),
  );
  expect((await reasons()).some((found) => found.startsWith(income))).toBe(
    false,
  );
  // Mixed naming its configured ratio is ready.
  const bulk = await port.submit("ledger.classify.bulk", {
    csv_text: `transaction_id,classification,business_pct,usage_ratio_id\n${mixed},MIXED,0.3,telefonia_movil\n`,
  });
  expect(bulk.kind).toBe("settled");
  expect(await reasons()).toEqual([`${refund}:missing_category`]);
});

test("a model review names its movement by the full id, as the registered request decodes it", async () => {
  const movement = fixtureLedger().movements.find(
    (found) => !found.sealed && found.transaction.lifecycle_state === "ACTIVE",
  )!;
  const id = movement.transaction.transaction_id;
  const port = ledgerFixture({
    say: () => undefined,
    wait: async () => undefined,
    signedIn: () => true,
    shape: "fixture",
  });
  const ask = (transaction_id: string) =>
    port
      .submit("ledger.classify.review", {
        transaction_id,
        mode: "classification",
        origin: "classify_llm_apply",
      })
      .then(
        () => null,
        (error: { code: string }) => error.code,
      );
  // A short handle, another spelling of the id, or a longer one is refused.
  expect(await ask(id.slice(0, 8))).toBe("invalid");
  expect(await ask(id.toUpperCase())).toBe("invalid");
  expect(await ask(`${id}0`)).toBe("invalid");
  // The full id is asked.
  expect(await ask(id)).toBeNull();
});

test("an export is shown in the file manager only once its file was written", async () => {
  const port = ledgerFixture({
    say: () => undefined,
    wait: async () => undefined,
    signedIn: () => true,
    shape: "fixture",
  });
  const reveal = (token: FileToken) =>
    port.revealFile(token).then(
      () => null,
      (error: { code: string }) => error.code,
    );
  const saveTo = async () =>
    (await port.saveFile("csv", "CSV", "movimientos-2026.csv")).files[0]!.token;
  const exportTo = (output_path: FileToken) =>
    port.submit("ledger.export", { output_path, export_format: "csv" }).then(
      () => null,
      (error: { code: string }) => error.code,
    );
  // Saved to, but nothing written there yet.
  const first = await saveTo();
  expect(await reveal(first)).toBe("file_unavailable");
  expect(await exportTo(first)).toBeNull();
  expect(await reveal(first)).toBeNull();
  // An export whose outcome is unknown, and which never ran, wrote nothing.
  const second = await saveTo();
  (
    stand.window as {
      __scenarioLedger?: { nextWrites(outcomes: string[]): void };
    }
  ).__scenarioLedger!.nextWrites(["lost"]);
  expect(await exportTo(second)).toBe("unknown");
  expect(await reveal(second)).toBe("file_unavailable");
  // A file picked to be read is never shown through this door.
  const picked = (await port.pickFiles("bank_statements", "file", "CSV"))
    .files[0]!.token;
  expect(await reveal(picked)).toBe("invalid");
});
