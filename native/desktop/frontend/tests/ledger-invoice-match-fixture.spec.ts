import { expect, test } from "@playwright/test";
import { answerInvoiceMatch } from "../src/dev/ledgerInvoiceMatchFixture";
import { settlementOf } from "../src/dev/ledgerSettlement";
import type {
  CatalogueInvoice,
  LedgerInvoiceMatchPair,
} from "../src/shell/ledgerInvoiceOperations";
import type { LedgerRow } from "../src/shell/ledger";
import recorded from "@fixtures/ledger-recordings/ledgerInvoiceMatch.json" with { type: "json" };
import { catalogueInvoice, hexId, movement } from "./support/ledger";

// The stand-in stories use for `ledger.invoice.match`, held to what the real
// backend answered. A test in the owning Python package holds the recording to
// the live rule, so the stand-in cannot drift from it unseen. The recording
// speaks of movements and invoices by name; the stand-in is given records.

type Scenario = (typeof recorded.scenarios)[number];
type Entry = Record<string, string | boolean | null | undefined>;

// The backend breaks a tie between equal candidates by invoice id, and its ids
// come from the invoice's own content. The recording keeps no ids, only the
// order it answered in, so each invoice is given an id that sorts where the
// recorded answer put its number: a tied pair is then offered in the order the
// backend offered it, whatever ids the backend's content now yields.
function answeredOrder(scenario: Scenario): Map<string, number> {
  type Named = { invoice: string; ties?: Named[]; others?: Named[] };
  const named: string[] = [];
  for (const found of scenario.answer.suggestions as Named[])
    for (const each of [found, ...(found.ties ?? []), ...(found.others ?? [])])
      if (!named.includes(each.invoice)) named.push(each.invoice);
  return new Map(named.map((number, at) => [number, at]));
}

function recordsOf(scenario: Scenario): {
  rows: LedgerRow[];
  invoices: CatalogueInvoice[];
  numberOf: Map<string, string>;
} {
  const answered = answeredOrder(scenario);
  const invoices = scenario.invoices.map((entry: Entry) => {
    const number = entry.number as string;
    const retention = (entry.retention as string | undefined) ?? null;
    return catalogueInvoice(number, {
      invoice_id: hexId(
        `${String(answered.get(number) ?? answered.size).padStart(3, "0")}-${number}`,
      ),
      kind: entry.kind as CatalogueInvoice["kind"],
      issued_at: entry.issued as string,
      counterparty_name: entry.party as string,
      currency: (entry.currency as string | undefined) ?? "EUR",
      grand_total: {
        decimal: (scenario.totals as Record<string, string>)[number]!,
      },
      retention_amount: retention ? { decimal: retention } : null,
      settlement_amount: {
        decimal: (scenario.settlements as Record<string, string>)[number]!,
      },
      linked_transaction_ids: entry.linked ? [hexId("elsewhere")] : [],
    });
  });
  const rows = scenario.movements.map((entry: Entry) =>
    movement(entry.name as string, {
      amount: entry.amount as string,
      direction: entry.direction as LedgerRow["transaction"]["direction"],
      date: entry.on as string,
      description: entry.description as string,
      counterparty: (entry.counterparty as string | null) ?? "",
      currency: entry.currency as string,
      lifecycle_state: (entry.state as string | undefined) ?? "ACTIVE",
      invoice_id: entry.cited ? hexId("elsewhere") : null,
    }),
  );
  return {
    rows,
    invoices,
    numberOf: new Map(
      invoices.map((invoice) => [invoice.invoice_id, invoice.invoice_number]),
    ),
  };
}

for (const scenario of recorded.scenarios) {
  test(`the stand-in answers as the backend did: ${scenario.name}`, () => {
    const { rows, invoices, numberOf } = recordsOf(scenario);
    const byNumber = new Map(
      invoices.map((invoice) => [invoice.invoice_number, invoice]),
    );
    const focus = (scenario.focus ?? {}) as {
      invoice?: string;
      movement?: string;
    };
    const answer = answerInvoiceMatch(
      {
        staged: (scenario.staged as string[][]).map(
          ([movementName, number]) => ({
            transaction_id: movementName!,
            invoice_id: byNumber.get(number!)!.invoice_id,
          }),
        ),
        invoice_id: focus.invoice
          ? byNumber.get(focus.invoice)!.invoice_id
          : null,
        transaction_id: focus.movement ?? null,
        judge: ((scenario as { judge?: string[][] }).judge ?? []).map(
          ([movementName, number]) => ({
            transaction_id: movementName!,
            invoice_id: byNumber.get(number!)!.invoice_id,
          }),
        ),
      },
      rows,
      invoices,
      "profile",
    );
    const named = (pair: LedgerInvoiceMatchPair) => ({
      movement: pair.transaction_id,
      invoice: numberOf.get(pair.invoice_id),
      number: pair.number,
      gap: pair.gap,
      counterparty: pair.counterparty,
    });
    expect({
      suggestions: answer.suggestions.map((found) => ({
        ...named(found),
        ambiguous: found.ambiguous,
        ties: found.ties.map(named),
        others: found.others.map(named),
      })),
      invoice_choices:
        answer.invoice_choices?.map((choice) => ({
          invoice: numberOf.get(choice.invoice_id),
          settles: choice.settles,
          staged_for: choice.staged_for,
          linked: choice.linked,
        })) ?? null,
      movement_choices:
        answer.movement_choices?.map((choice) => ({
          movement: choice.transaction_id,
          settles: choice.settles,
        })) ?? null,
      ...((scenario as { judge?: string[][] }).judge
        ? {
            judgements: answer.judgements.map((judgement) => ({
              movement: judgement.transaction_id,
              invoice: numberOf.get(judgement.invoice_id),
              found: judgement.found,
              mismatches: judgement.mismatches.map((each) => ({
                ...each,
                difference: each.difference?.decimal ?? null,
              })),
            })),
          }
        : {}),
    }).toEqual(scenario.answer);
    expect(answer.window_days).toBe(10);
  });

  test(`the fixtures state what an invoice settles as the backend did: ${scenario.name}`, () => {
    for (const entry of scenario.invoices as Entry[]) {
      const number = entry.number as string;
      expect(
        settlementOf(
          (scenario.totals as Record<string, string>)[number]!,
          (entry.retention as string | undefined) ?? null,
        ),
      ).toEqual({
        decimal: (scenario.settlements as Record<string, string>)[number],
      });
    }
  });
}
