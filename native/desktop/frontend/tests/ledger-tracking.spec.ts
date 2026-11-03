import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readSealed } from "../src/components/ledger/useSealedMovements";
import { useLedgerRead } from "../src/components/ledger/inspector/useInspectorReads";
import { isTransactionPrefix } from "../src/shell/ledgerGrammar";
import { fakePort, hexId } from "./support/ledger";

test("stored-movement reads reject virtual keys before IPC and preserve canonical prefixes", async () => {
  const { port, calls } = fakePort(() => ({ settle: { participated_in: [] } }));
  for (const id of [
    "draft-123456abcdef",
    "",
    "A0",
    " f0",
    "f0\n",
    "f".repeat(65),
  ]) {
    expect(isTransactionPrefix(id)).toBe(false);
    expect(await readSealed(port, id)).toBeNull();
  }
  expect(calls).toEqual([]);
  for (const id of ["a", "0f", hexId("created")]) {
    expect(isTransactionPrefix(id)).toBe(true);
    expect(await readSealed(port, id)).toBe(false);
  }
  expect(calls.map((call) => call.kind === "submit" && call.payload)).toEqual([
    { transaction_prefix: "a" },
    { transaction_prefix: "0f" },
    { transaction_prefix: hexId("created") },
  ]);
});

test("an inspector read without a request is idle rather than an unfinishable spinner", () => {
  const { port } = fakePort(() => {
    throw new Error("no request may be sent");
  });
  function Probe() {
    const read = useLedgerRead(
      port,
      "ledger.track",
      null,
      "removed-draft",
      true,
    );
    return createElement("span", null, read?.kind ?? "idle");
  }
  expect(renderToStaticMarkup(createElement(Probe))).toBe("<span>idle</span>");
});
