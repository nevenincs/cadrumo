import { expect, test } from "@playwright/test";
import { fixtureLedger } from "../src/dev/fixtures/ledger";
import { LEDGER_PAYLOAD_LIMIT } from "../src/shell/ledger";

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

test("a payload is refused over the host's characters, and a request line over its bytes", () => {
  const request = (reason: string) => ({ transaction_id: "x", reason });
  const empty = JSON.stringify(request("")).length;
  // Exactly the payload limit passes; one character more does not.
  expect(
    tooLarge(ARCHIVE, request("a".repeat(LEDGER_PAYLOAD_LIMIT - empty))),
  ).toBe(false);
  expect(
    tooLarge(ARCHIVE, request("a".repeat(LEDGER_PAYLOAD_LIMIT - empty + 1))),
  ).toBe(true);
  // Few characters, but three bytes each: the line is over its bytes.
  expect(tooLarge(ARCHIVE, request("\u20ac".repeat(4_000)))).toBe(false);
  expect(tooLarge(ARCHIVE, request("\u20ac".repeat(6_000)))).toBe(true);
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
