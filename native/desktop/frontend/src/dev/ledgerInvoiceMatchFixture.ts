// `ledger.invoice.match` for the fixtures. Stories stage links and change
// movements freely over a generated ledger, so a recording cannot hold each
// question: this stand-in works the answer out. the generated `ledgerInvoiceMatch.json`
// holds what the real backend answered, a test in the owning Python package
// holds that recording to the live rule, and a test here holds this stand-in to it.

import {
  INVOICE_MATCH_TOLERANCE,
  SETTLING_DIRECTION,
  takesChanges,
  takesInvoice,
} from "../shell/ledgerContract";
import type {
  LedgerInvoiceMatchRequest,
  LedgerInvoiceMatchResult,
} from "../shell/ledgerInvoiceOperations";
import type {
  CatalogueInvoiceSnapshot,
  LedgerInvoiceMatchMismatch,
  LedgerInvoiceMatchPair,
  LedgerInvoiceMatchSuggestion,
} from "../shell/ledgerInvoiceContract";
import type { LedgerRow } from "../shell/ledger";

/** The movements the stand-in reads need nothing of a row but the movement. */
type HeldRow = Pick<LedgerRow, "transaction">;

const SCALE = 6;
const EARLY_DAYS = 3;
const LATE_RANK = 1000;
const WINDOW_DAYS = 10;
const DAY_MS = 86_400_000;

function units(text: string): bigint {
  const [whole = "0", fraction = ""] = text.trim().split(".");
  return (
    BigInt(whole) * 10n ** BigInt(SCALE) + BigInt(fraction.padEnd(SCALE, "0"))
  );
}
const distance = (left: bigint, right: bigint) =>
  left > right ? left - right : right - left;
const folded = (text: string) => text.toUpperCase().replace(/[^A-Z0-9]+/g, "");
const flowOf = (invoice: CatalogueInvoiceSnapshot) =>
  SETTLING_DIRECTION[invoice.kind];
const days = (from: string, to: string) =>
  Math.round(
    (Date.parse(`${to.slice(0, 10)}T12:00:00Z`) -
      Date.parse(`${from.slice(0, 10)}T12:00:00Z`)) /
      DAY_MS,
  );
const takesLink = (row: HeldRow) =>
  takesChanges(row.transaction.lifecycle_state) &&
  takesInvoice(row.transaction.direction);
// A name that is only a legal form tells no party; the recording holds this
// list to the backend's reading of "the same party".
const BARE_LEGAL_FORMS = new Set([
  "aie",
  "cb",
  "coop",
  "gmbh",
  "inc",
  "llc",
  "ltd",
  "sa",
  "sal",
  "sau",
  "sc",
  "scoop",
  "scp",
  "sl",
  "sll",
  "slne",
  "slp",
  "slu",
  "sociedadanonima",
  "sociedadlimitada",
]);
const namesNoParty = (name: string) =>
  BARE_LEGAL_FORMS.has(
    name
      .normalize("NFD")
      .replace(/\p{M}+/gu, "")
      .replace(/[^a-z0-9]+/g, ""),
  );
const overlap = (invoiceName: string, movementName: string) => {
  const a = invoiceName.trim().toLowerCase();
  const b = movementName.trim().toLowerCase();
  return (
    a !== "" &&
    b !== "" &&
    !namesNoParty(a) &&
    !namesNoParty(b) &&
    (a.includes(b) || b.includes(a))
  );
};

/** Digits after the point, as the stand-in's exact arithmetic needs them. */
const scaleOf = (text: string) => text.trim().split(".")[1]?.length ?? 0;

/** The magnitude of two decimals' difference, in the wider of their spellings. */
function spelledDistance(left: string, right: string): string {
  const scale = Math.max(scaleOf(left), scaleOf(right));
  const raw =
    distance(units(left), units(right)) / 10n ** BigInt(SCALE - scale);
  const digits = raw.toString().padStart(scale + 1, "0");
  return scale === 0
    ? digits
    : `${digits.slice(0, -scale)}.${digits.slice(-scale)}`;
}

/** Where a movement and an invoice to be linked do not agree. */
function mismatchesOf(
  row: HeldRow,
  invoice: CatalogueInvoiceSnapshot,
): LedgerInvoiceMatchMismatch[] {
  const found: LedgerInvoiceMatchMismatch[] = [];
  const none = { difference: null, movement: null, invoice: null, count: null };
  if (row.transaction.currency !== invoice.currency)
    found.push({
      ...none,
      kind: "currency",
      movement: row.transaction.currency,
      invoice: invoice.currency,
    });
  else if (
    distance(
      units(row.transaction.amount),
      units(invoice.settlement_amount.decimal),
    ) > units(INVOICE_MATCH_TOLERANCE)
  )
    found.push({
      ...none,
      kind: "amount",
      difference: {
        decimal: spelledDistance(
          row.transaction.amount,
          invoice.settlement_amount.decimal,
        ),
      },
    });
  const named = row.transaction.counterparty;
  if (
    named.trim() !== "" &&
    invoice.counterparty_name.trim() !== "" &&
    !overlap(invoice.counterparty_name, named)
  )
    found.push({ ...none, kind: "counterparty" });
  const elsewhere = invoice.linked_transaction_ids.filter(
    (id) => id !== row.transaction.transaction_id,
  ).length;
  if (elsewhere > 0)
    found.push({ ...none, kind: "linked_elsewhere", count: elsewhere });
  return found;
}

function settles(row: HeldRow, invoice: CatalogueInvoiceSnapshot): boolean {
  return (
    row.transaction.direction === flowOf(invoice) &&
    row.transaction.currency === invoice.currency &&
    distance(
      units(row.transaction.amount),
      units(invoice.settlement_amount.decimal),
    ) <= units(INVOICE_MATCH_TOLERANCE)
  );
}

type Candidate = {
  row: HeldRow;
  invoice: CatalogueInvoiceSnapshot;
  served: LedgerInvoiceMatchPair;
  rank: [number, number, number, bigint];
};

function candidate(
  row: HeldRow,
  invoice: CatalogueInvoiceSnapshot,
): Candidate | null {
  if (!settles(row, invoice)) return null;
  const number = folded(invoice.invoice_number);
  const named =
    number.length >= 4 && folded(row.transaction.description).includes(number);
  const gap = days(invoice.issued_at, row.transaction.date);
  const counterparty = overlap(
    invoice.counterparty_name,
    row.transaction.counterparty,
  );
  return {
    row,
    invoice,
    served: {
      transaction_id: row.transaction.transaction_id,
      invoice_id: invoice.invoice_id,
      number: named,
      gap,
      counterparty,
    },
    rank: [
      named ? 0 : 1,
      gap >= -EARLY_DAYS ? Math.abs(gap) : LATE_RANK - gap,
      counterparty ? 0 : 1,
      distance(
        units(row.transaction.amount),
        units(invoice.settlement_amount.decimal),
      ),
    ],
  };
}

const compare = (a: Candidate, b: Candidate) => {
  for (let at = 0; at < 3; at += 1)
    if (a.rank[at] !== b.rank[at])
      return (a.rank[at] as number) - (b.rank[at] as number);
  if (a.rank[3] !== b.rank[3]) return a.rank[3] < b.rank[3] ? -1 : 1;
  return 0;
};
const before = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
const order = (a: Candidate, b: Candidate) =>
  compare(a, b) ||
  before(a.invoice.invoice_id, b.invoice.invoice_id) ||
  before(a.row.transaction.transaction_id, b.row.transaction.transaction_id);

export function answerInvoiceMatch(
  request: LedgerInvoiceMatchRequest,
  rows: readonly HeldRow[],
  invoices: readonly CatalogueInvoiceSnapshot[],
  profileId: string,
): LedgerInvoiceMatchResult {
  const stagedRows = new Map(
    (request.staged ?? []).map((link) => [
      link.transaction_id,
      link.invoice_id,
    ]),
  );
  const stagedInvoices = new Map(
    [...stagedRows].map(([transactionId, invoiceId]) => [
      invoiceId,
      transactionId,
    ]),
  );
  const open = rows.filter(
    (row) =>
      takesLink(row) &&
      row.transaction.invoice_id === null &&
      !stagedRows.has(row.transaction.transaction_id),
  );
  const weighed = invoices.filter(
    (invoice) =>
      invoice.linked_transaction_ids.length === 0 &&
      !stagedInvoices.has(invoice.invoice_id) &&
      (request.invoice_id ?? invoice.invoice_id) === invoice.invoice_id,
  );
  const pairs = weighed
    .flatMap((invoice) => open.map((row) => candidate(row, invoice)))
    .filter((found): found is Candidate => found !== null)
    .sort(order);
  const usedRows = new Set<string>();
  const usedInvoices = new Set<string>();
  const best = new Map<string, LedgerInvoiceMatchSuggestion>();
  const rowOf = (pair: Candidate) => pair.row.transaction.transaction_id;
  for (const pair of pairs) {
    if (usedRows.has(rowOf(pair)) || usedInvoices.has(pair.invoice.invoice_id))
      continue;
    const ties = pairs.filter(
      (other) =>
        other !== pair &&
        (rowOf(other) === rowOf(pair) ||
          other.invoice.invoice_id === pair.invoice.invoice_id) &&
        !usedRows.has(rowOf(other)) &&
        !usedInvoices.has(other.invoice.invoice_id) &&
        compare(other, pair) === 0,
    );
    usedRows.add(rowOf(pair));
    usedInvoices.add(pair.invoice.invoice_id);
    best.set(rowOf(pair), {
      ...pair.served,
      ambiguous: ties.length > 0,
      ties: ties.map((tie) => tie.served),
      others: pairs
        .filter((other) => other !== pair && rowOf(other) === rowOf(pair))
        .map((other) => other.served),
    });
  }
  // A movement that ties for the invoice of another points at the same choice.
  for (const suggestion of [...best.values()])
    for (const tie of suggestion.ties) {
      if (best.has(tie.transaction_id)) continue;
      best.set(tie.transaction_id, {
        ...tie,
        ambiguous: true,
        ties: [
          {
            transaction_id: suggestion.transaction_id,
            invoice_id: suggestion.invoice_id,
            number: suggestion.number,
            gap: suggestion.gap,
            counterparty: suggestion.counterparty,
          },
        ],
        others: pairs
          .filter(
            (other) =>
              rowOf(other) === tie.transaction_id && other.served !== tie,
          )
          .map((other) => other.served),
      });
    }
  const dateOf = (id: string) =>
    rows.find((row) => row.transaction.transaction_id === id)!.transaction.date;
  const suggestions = [...best.values()]
    .sort(
      (left, right) =>
        dateOf(right.transaction_id).localeCompare(
          dateOf(left.transaction_id),
        ) || before(left.transaction_id, right.transaction_id),
    )
    .filter(
      (each) =>
        (request.transaction_id ?? each.transaction_id) === each.transaction_id,
    );
  const own = rows.find(
    (row) => row.transaction.transaction_id === request.transaction_id,
  );
  const target = invoices.find(
    (invoice) => invoice.invoice_id === request.invoice_id,
  );
  const judgements = (request.judge ?? []).map((link) => {
    const held = rows.find(
      (row) => row.transaction.transaction_id === link.transaction_id,
    );
    const asked = invoices.find(
      (invoice) => invoice.invoice_id === link.invoice_id,
    );
    return {
      transaction_id: link.transaction_id,
      invoice_id: link.invoice_id,
      found: held !== undefined && asked !== undefined,
      mismatches: held && asked ? mismatchesOf(held, asked) : [],
    };
  });
  return {
    profile_id: profileId,
    suggestions,
    judgements,
    window_days: WINDOW_DAYS,
    invoice_choices: own
      ? invoices
          .filter((invoice) => own.transaction.direction === flowOf(invoice))
          .sort(
            (left, right) =>
              right.issued_at.localeCompare(left.issued_at) ||
              before(left.invoice_id, right.invoice_id),
          )
          .map((invoice) => {
            const holder = stagedInvoices.get(invoice.invoice_id) ?? null;
            return {
              invoice_id: invoice.invoice_id,
              settles: settles(own, invoice),
              staged_for:
                holder === own.transaction.transaction_id ? null : holder,
              linked: invoice.linked_transaction_ids.filter(
                (linked) => linked !== own.transaction.transaction_id,
              ).length,
            };
          })
      : null,
    movement_choices: target
      ? rows
          .filter(
            (row) =>
              takesLink(row) &&
              row.transaction.invoice_id === null &&
              !stagedRows.has(row.transaction.transaction_id) &&
              row.transaction.direction === flowOf(target) &&
              row.transaction.currency === target.currency &&
              Math.abs(days(target.issued_at, row.transaction.date)) <=
                WINDOW_DAYS,
          )
          .map((row) => ({
            row,
            settles: settles(row, target),
            amount: distance(
              units(row.transaction.amount),
              units(target.settlement_amount.decimal),
            ),
            gap: Math.abs(days(target.issued_at, row.transaction.date)),
          }))
          .sort(
            (a, b) =>
              Number(b.settles) - Number(a.settles) ||
              (a.amount < b.amount ? -1 : a.amount > b.amount ? 1 : 0) ||
              a.gap - b.gap ||
              before(
                a.row.transaction.transaction_id,
                b.row.transaction.transaction_id,
              ),
          )
          .map((each) => ({
            transaction_id: each.row.transaction.transaction_id,
            settles: each.settles,
          }))
      : null,
  };
}
