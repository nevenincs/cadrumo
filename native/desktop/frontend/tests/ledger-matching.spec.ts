import { expect, test } from "@playwright/test";
import {
  inconsistencies,
  remapInvoiceChoices,
  remapMatches,
  remapMovementChoices,
  tiedInvoices,
  tiedMovements,
} from "../src/components/ledger/matching/matchingModel";
import type { LedgerInvoiceMatchSuggestion } from "../src/shell/ledgerInvoiceOperations";
import { catalogueInvoice as invoice, hexId, movement } from "./support/ledger";

// The ledger says which invoice settles which movement and how they rank
// (`ledger.invoice.match`; the rule is the backend's and its parity tests are
// there). The window looks what it says up among the records it holds and
// shows each pair with the evidence it stands on. Every value is invented.

const served = (
  transactionId: string,
  invoiceId: string,
  facts: Partial<LedgerInvoiceMatchSuggestion> = {},
): LedgerInvoiceMatchSuggestion => ({
  transaction_id: transactionId,
  invoice_id: invoiceId,
  number: false,
  gap: 2,
  counterparty: false,
  ambiguous: false,
  ties: [],
  others: [],
  ...facts,
});

test("a served pair is shown with the invoice's own settlement and the evidence it stands on", () => {
  const row = movement("m");
  const withheld = invoice("F-1", {
    kind: "issued",
    grand_total: { decimal: "1815.00" },
    retention_amount: { decimal: "225.00" },
    settlement_amount: { decimal: "1590.00" },
  });
  const found = remapMatches(
    {
      suggestions: [
        served("m", withheld.invoice_id, { number: true, counterparty: true }),
      ],
    },
    [row],
    [withheld],
  );
  const best = found.best.get("m")!;
  expect(best.invoice).toBe(withheld);
  expect(best.settles).toBe("1590.00");
  expect(best.chips).toEqual([
    { kind: "number" },
    { kind: "gap", days: 2 },
    { kind: "counterparty" },
    { kind: "amount" },
  ]);
  expect(found.list).toEqual([best]);
});

test("a pair with a side the window does not hold is left out, whole or among the others", () => {
  const row = movement("m");
  const held = invoice("H-1");
  const unseen = invoice("U-1");
  const found = remapMatches(
    {
      suggestions: [
        served("gone", held.invoice_id),
        served("m", unseen.invoice_id),
        served("m", held.invoice_id, {
          others: [
            {
              transaction_id: "m",
              invoice_id: unseen.invoice_id,
              number: false,
              gap: 1,
              counterparty: false,
            },
            {
              transaction_id: "m",
              invoice_id: held.invoice_id,
              number: false,
              gap: 3,
              counterparty: false,
            },
          ],
        }),
      ],
    },
    [row],
    [held],
  );
  expect(found.list).toHaveLength(1);
  expect(found.list[0]!.others.map((pair) => pair.gap)).toEqual([3]);
});

test("tied invoices open a chooser and tied movements point at each other", () => {
  const left = invoice("AA-118");
  const right = invoice("AA-119");
  const row = movement("row");
  const tied = remapMatches(
    {
      suggestions: [
        served("row", left.invoice_id, {
          ambiguous: true,
          ties: [
            {
              transaction_id: "row",
              invoice_id: right.invoice_id,
              number: false,
              gap: 2,
              counterparty: false,
            },
          ],
        }),
      ],
    },
    [row],
    [left, right],
  ).best.get("row")!;
  expect(tied.ambiguous).toBe(true);
  expect(tiedInvoices(tied).map((pair) => pair.invoice.invoice_number)).toEqual(
    ["AA-118", "AA-119"],
  );
  expect(tiedMovements(tied)).toEqual([]);

  const a = movement("a");
  const b = movement("b");
  const issued = invoice("N-5", { kind: "issued" });
  const both = remapMatches(
    {
      suggestions: [
        served("a", issued.invoice_id, {
          ambiguous: true,
          ties: [
            {
              transaction_id: "b",
              invoice_id: issued.invoice_id,
              number: false,
              gap: 2,
              counterparty: false,
            },
          ],
        }),
      ],
    },
    [a, b],
    [issued],
  );
  const first = both.best.get("a")!;
  expect(tiedInvoices(first)).toEqual([]);
  expect(
    tiedMovements(first).map((pair) => pair.row.transaction.transaction_id),
  ).toEqual(["b"]);
});

test("the invoices offered for a link by hand keep the ledger's order and say what is staged or linked", () => {
  const settles = invoice("S-1");
  const elsewhere = invoice("S-2");
  const other = invoice("O-1");
  const picker = remapInvoiceChoices(
    [
      {
        invoice_id: other.invoice_id,
        settles: false,
        staged_for: null,
        linked: 0,
      },
      {
        invoice_id: settles.invoice_id,
        settles: true,
        staged_for: "rival",
        linked: 0,
      },
      {
        invoice_id: elsewhere.invoice_id,
        settles: true,
        staged_for: null,
        linked: 1,
      },
      {
        invoice_id: hexId("unseen"),
        settles: true,
        staged_for: null,
        linked: 0,
      },
    ],
    [settles, elsewhere, other],
  );
  expect(picker.settles.map((option) => option.invoice.invoice_number)).toEqual(
    ["S-1", "S-2"],
  );
  expect(picker.other.map((option) => option.invoice.invoice_number)).toEqual([
    "O-1",
  ]);
  expect(picker.settles[0]).toMatchObject({ stagedFor: "rival", linked: 0 });
  expect(picker.settles[1]).toMatchObject({ stagedFor: null, linked: 1 });
});

test("the movements offered for a link by hand keep the ledger's order and leave out those the window does not hold", () => {
  const first = movement("first");
  const second = movement("second");
  const offered = remapMovementChoices(
    [
      { transaction_id: "second", settles: true },
      { transaction_id: "unseen", settles: true },
      { transaction_id: "first", settles: false },
    ],
    [first, second],
  );
  expect(
    offered.map((option) => [
      option.row.transaction.transaction_id,
      option.settles,
    ]),
  ).toEqual([
    ["second", true],
    ["first", false],
  ]);
});

test("a one-sided link is repaired by a link only where both sides end up citing each other", () => {
  const lists = invoice("LISTS", { linked_transaction_ids: ["free"] });
  const cited = invoice("CITED");
  const free = movement("free");
  const citesOther = movement("cites", { invoice_id: hexId("inv-ELSEWHERE") });
  const listsCiting = invoice("LISTS-2", { linked_transaction_ids: ["cites"] });
  const citing = movement("citing", { invoice_id: cited.invoice_id });
  const found = inconsistencies(
    [
      {
        invoice_id: lists.invoice_id,
        transaction_id: "free",
        direction: "invoice-only",
      },
      {
        invoice_id: listsCiting.invoice_id,
        transaction_id: "cites",
        direction: "invoice-only",
      },
      {
        invoice_id: cited.invoice_id,
        transaction_id: "citing",
        direction: "transaction-only",
      },
      {
        invoice_id: hexId("inv-GONE"),
        transaction_id: "citing",
        direction: "transaction-only",
      },
      {
        invoice_id: lists.invoice_id,
        transaction_id: "unread",
        direction: "invoice-only",
      },
    ],
    [free, citesOther, citing],
    [lists, cited, listsCiting],
  );
  expect(found.map((item) => item.repair)).toEqual([
    { kind: "link" },
    { kind: "none", why: "cites_another" },
    { kind: "link" },
    { kind: "none", why: "invoice_missing" },
    { kind: "none", why: "not_loaded" },
  ]);
});
