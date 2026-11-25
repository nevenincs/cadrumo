import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readSealed } from "../src/components/ledger/useSealedMovements";
import { useLedgerRead } from "../src/components/ledger/inspector/useInspectorReads";
import { isTransactionPrefix } from "../src/shell/ledgerGrammar";
import { fakePort, hexId } from "./support/ledger";

test("stored-movement reads reject virtual keys before IPC and ask the rest in one read", async () => {
  const { port, calls } = fakePort((call) => ({
    settle: {
      profile_id: "p",
      rows: (
        (call.kind === "submit" &&
          (call.payload as { transaction_ids: string[] }).transaction_ids) ||
        []
      ).map((id) => ({
        transaction_id: id,
        state: "open",
        seal_count: 0,
        seals: [],
      })),
    },
  }));
  const virtual = [
    "draft-123456abcdef",
    "",
    "A0",
    " f0",
    "f0\n",
    "f".repeat(65),
  ];
  for (const id of virtual) expect(isTransactionPrefix(id)).toBe(false);
  expect([...(await readSealed(port, virtual)).values()]).toEqual(
    virtual.map(() => null),
  );
  expect(calls).toEqual([]);
  const stored = ["a", "0f", hexId("created")];
  for (const id of stored) expect(isTransactionPrefix(id)).toBe(true);
  const answered = await readSealed(port, [...stored, "draft-1"]);
  expect(stored.map((id) => answered.get(id))).toEqual([false, false, false]);
  expect(answered.get("draft-1")).toBeNull();
  expect(calls.map((call) => call.kind === "submit" && call.payload)).toEqual([
    { transaction_ids: stored },
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
