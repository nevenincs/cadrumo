// Which invoice settles which movement, as the Ledger page suggests it. A
// suggestion is a proposal the person links, and a link is permanent, so
// each movement shows one best invoice and each invoice is offered to one
// movement. A candidate follows the product's own rule: an invoice no
// movement is linked to and a movement linked to no invoice, an issued
// invoice against money in and a received one against money out, in the
// same currency, and a movement amount that settles the invoice's total less
// its retención to the cent. Candidates rank by the invoice number found in
// the description, then the shortest issue-to-payment gap, then the
// counterparty, then the amount. Equal candidates are ambiguous: the person
// chooses. Nothing here reads or writes the ledger.

import type {
  CatalogueInvoice,
  LedgerCheckResult,
  LedgerRow,
} from "../../../shell/ledger";
import type { StageEvent, StagedAction } from "../../../shell/ledgerStage";

/** How far apart, in cents, a movement and an invoice may be and still
 * settle: the product's own tolerance. */
const TOLERANCE_UNITS = 10_000n; // one cent at six decimals
const SCALE = 6;
/** Paid this many days before the invoice's date still ranks by the gap;
 * earlier than that ranks after every payment made after issue. */
const EARLY_DAYS = 3;
const LATE_RANK = 1000;

/** A decimal text as units of a millionth, or null for anything else. */
function units(text: string): bigint | null {
  const found = /^(\d+)(?:\.(\d{1,6}))?$/.exec(text.trim());
  if (!found) return null;
  const fraction = (found[2] ?? "").padEnd(SCALE, "0");
  return BigInt(found[1]!) * 10n ** BigInt(SCALE) + BigInt(fraction);
}
/** Units back to decimal text, to the cent. */
function centsText(value: bigint): string {
  const negative = value < 0n;
  const magnitude = negative ? -value : value;
  const cents = (magnitude + 5_000n) / 10_000n;
  const whole = cents / 100n;
  const fraction = (cents % 100n).toString().padStart(2, "0");
  return `${negative ? "-" : ""}${whole}.${fraction}`;
}

/** What an invoice settles in money: its total less what was withheld. */
export function settlement(invoice: CatalogueInvoice): string | null {
  const total = units(invoice.grand_total.decimal);
  if (total === null) return null;
  const withheld = invoice.retention_amount
    ? units(invoice.retention_amount.decimal)
    : 0n;
  if (withheld === null) return null;
  return centsText(total - withheld);
}

/** The movement direction an invoice of `kind` is paid in. */
export const flowOf = (invoice: CatalogueInvoice) =>
  invoice.kind === "issued" ? "INCOMING" : "OUTGOING";

const DAY_MS = 86_400_000;
/** Whole days from `from` to `to`, both calendar days. */
export function daysBetween(from: string, to: string): number {
  return Math.round(
    (Date.parse(`${to.slice(0, 10)}T12:00:00Z`) -
      Date.parse(`${from.slice(0, 10)}T12:00:00Z`)) /
      DAY_MS,
  );
}

const LEGAL_FORMS = /\b(s\.?l\.?u?|s\.?a\.?u?|s\.?coop|sll|slp|cb|scp)\b\.?/g;
/** A party's name folded for comparison: no accents, case, punctuation or
 * legal form. */
export function partyName(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(LEGAL_FORMS, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}
/** Whether two names overlap, one inside the other, as the product
 * compares counterparties. */
export function sameParty(left: string, right: string): boolean {
  const a = partyName(left);
  const b = partyName(right);
  return a !== "" && b !== "" && (a.includes(b) || b.includes(a));
}

const reference = (text: string) =>
  text.toUpperCase().replace(/[^A-Z0-9]+/g, "");
/** Whether a movement's description names the invoice's number. A number
 * too short to tell apart from other digits never counts. */
export function numberInDescription(
  row: LedgerRow,
  invoice: CatalogueInvoice,
): boolean {
  const number = reference(invoice.invoice_number);
  return (
    number.length >= 4 &&
    reference(row.transaction.description).includes(number)
  );
}

/** The evidence a pair stands on, shown as chips. */
export type MatchChip =
  | { kind: "number" }
  | { kind: "gap"; days: number }
  | { kind: "counterparty" }
  | { kind: "amount" };

/** One movement and one invoice that settle each other. */
export type MatchPair = {
  row: LedgerRow;
  invoice: CatalogueInvoice;
  /** What the invoice settles, to the cent. */
  settles: string;
  number: boolean;
  /** Days from the invoice's date to the movement's. */
  gap: number;
  counterparty: boolean;
  chips: MatchChip[];
  /** The ranking key: lower ranks first. */
  rank: readonly [number, number, number, bigint];
};

/** A movement's best invoice, with what competes with it. */
export type MatchSuggestion = MatchPair & {
  /** Another candidate ranks exactly as well: the person chooses. */
  ambiguous: boolean;
  /** The pairs that rank exactly as well and share this movement or this
   * invoice. */
  ties: MatchPair[];
  /** The movement's other candidates. */
  others: MatchPair[];
};

export type Reconciliation = {
  /** The best suggestion of each movement that has one, by movement id. */
  best: Map<string, MatchSuggestion>;
  /** Every candidate pair, best first. */
  pairs: MatchPair[];
  /** The suggestions, newest movement first. */
  list: MatchSuggestion[];
};

function compareRank(left: MatchPair, right: MatchPair): number {
  for (let at = 0; at < 3; at += 1) {
    const a = left.rank[at] as number;
    const b = right.rank[at] as number;
    if (a !== b) return a - b;
  }
  return left.rank[3] === right.rank[3]
    ? 0
    : left.rank[3] < right.rank[3]
      ? -1
      : 1;
}
const sameRank = (left: MatchPair, right: MatchPair) =>
  compareRank(left, right) === 0;

/** The movements and invoices staged links already take. */
export function stagedLinks(actions: readonly StagedAction[]): {
  rows: Map<string, string>;
  invoices: Map<string, string>;
} {
  const rows = new Map<string, string>();
  const invoices = new Map<string, string>();
  for (const action of actions)
    if (action.kind === "link") {
      rows.set(action.transactionId, action.invoiceId);
      invoices.set(action.invoiceId, action.transactionId);
    }
  return { rows, invoices };
}

/** Whether a movement can take a link at all. */
export const linkable = (row: LedgerRow) =>
  row.transaction.lifecycle_state === "ACTIVE" &&
  (row.transaction.direction === "INCOMING" ||
    row.transaction.direction === "OUTGOING");

/** Whether `row` settles `invoice` by flow, currency and amount. */
export function settles(row: LedgerRow, invoice: CatalogueInvoice): boolean {
  if (row.transaction.direction !== flowOf(invoice)) return false;
  if (row.transaction.currency !== invoice.currency) return false;
  const owed = settlement(invoice);
  const paid = units(row.transaction.amount);
  const due = owed === null ? null : units(owed);
  if (paid === null || due === null) return false;
  const distance = paid > due ? paid - due : due - paid;
  return distance <= TOLERANCE_UNITS;
}

function pairOf(row: LedgerRow, invoice: CatalogueInvoice): MatchPair | null {
  if (!settles(row, invoice)) return null;
  const owed = settlement(invoice)!;
  const distance = units(row.transaction.amount)! - units(owed)!;
  const number = numberInDescription(row, invoice);
  const gap = daysBetween(invoice.issued_at, row.transaction.date);
  const counterparty = sameParty(
    row.transaction.counterparty,
    invoice.counterparty_name,
  );
  const chips: MatchChip[] = [];
  if (number) chips.push({ kind: "number" });
  chips.push({ kind: "gap", days: gap });
  if (counterparty) chips.push({ kind: "counterparty" });
  chips.push({ kind: "amount" });
  return {
    row,
    invoice,
    settles: owed,
    number,
    gap,
    counterparty,
    chips,
    rank: [
      number ? 0 : 1,
      gap >= -EARLY_DAYS ? Math.abs(gap) : LATE_RANK - gap,
      counterparty ? 0 : 1,
      distance < 0n ? -distance : distance,
    ],
  };
}

/**
 * The suggestions for `rows` against `invoices`, one best invoice per
 * movement and one movement per invoice. A movement or an invoice a staged
 * link already takes is offered to nothing else.
 */
export function reconcile(
  rows: readonly LedgerRow[],
  invoices: readonly CatalogueInvoice[],
  actions: readonly StagedAction[] = [],
): Reconciliation {
  const staged = stagedLinks(actions);
  const open = rows.filter(
    (row) =>
      linkable(row) &&
      row.transaction.invoice_id === null &&
      !staged.rows.has(row.transaction.transaction_id),
  );
  const unmatched = invoices.filter(
    (invoice) =>
      invoice.linked_transaction_ids.length === 0 &&
      !staged.invoices.has(invoice.invoice_id),
  );
  const pairs: MatchPair[] = [];
  for (const invoice of unmatched)
    for (const row of open) {
      const pair = pairOf(row, invoice);
      if (pair) pairs.push(pair);
    }
  pairs.sort(
    (left, right) =>
      compareRank(left, right) ||
      (left.invoice.invoice_id < right.invoice.invoice_id ? -1 : 1) ||
      (left.row.transaction.transaction_id <
      right.row.transaction.transaction_id
        ? -1
        : 1),
  );
  const usedRows = new Set<string>();
  const usedInvoices = new Set<string>();
  const best = new Map<string, MatchSuggestion>();
  const rowId = (pair: MatchPair) => pair.row.transaction.transaction_id;
  const invoiceId = (pair: MatchPair) => pair.invoice.invoice_id;
  for (const pair of pairs) {
    if (usedRows.has(rowId(pair)) || usedInvoices.has(invoiceId(pair)))
      continue;
    const ties = pairs.filter(
      (other) =>
        other !== pair &&
        (rowId(other) === rowId(pair) ||
          invoiceId(other) === invoiceId(pair)) &&
        !usedRows.has(rowId(other)) &&
        !usedInvoices.has(invoiceId(other)) &&
        sameRank(other, pair),
    );
    usedRows.add(rowId(pair));
    usedInvoices.add(invoiceId(pair));
    best.set(rowId(pair), {
      ...pair,
      ambiguous: ties.length > 0,
      ties,
      others: pairs.filter(
        (other) => other !== pair && rowId(other) === rowId(pair),
      ),
    });
  }
  // A movement that ties for another's invoice points at the same choice.
  for (const suggestion of [...best.values()])
    for (const tie of suggestion.ties) {
      if (best.has(rowId(tie))) continue;
      best.set(rowId(tie), {
        ...tie,
        ambiguous: true,
        ties: [suggestion],
        others: pairs.filter(
          (other) => other !== tie && rowId(other) === rowId(tie),
        ),
      });
    }
  const list = [...best.values()].sort(
    (left, right) =>
      right.row.transaction.date.localeCompare(left.row.transaction.date) ||
      (rowId(left) < rowId(right) ? -1 : 1),
  );
  return { best, pairs, list };
}

/** The invoices tied for a movement's choice: its own candidates that rank
 * as well as its best, best first. Empty when the choice is not its own. */
export function tiedInvoices(suggestion: MatchSuggestion): MatchPair[] {
  const id = suggestion.row.transaction.transaction_id;
  const own = suggestion.ties.filter(
    (tie) => tie.row.transaction.transaction_id === id,
  );
  return own.length ? [suggestion, ...own] : [];
}
/** The other movements tied for this movement's best invoice. */
export function tiedMovements(suggestion: MatchSuggestion): MatchPair[] {
  const id = suggestion.row.transaction.transaction_id;
  return suggestion.ties.filter(
    (tie) => tie.row.transaction.transaction_id !== id,
  );
}

/** The staged action that links `row` to `invoice`: one link per
 * movement, so staging another replaces it. */
export function linkAction(
  transactionId: string,
  invoiceId: string,
): StagedAction {
  return {
    id: `link:${transactionId}`,
    kind: "link",
    transactionId,
    invoiceId,
  };
}
export const stageLink = (
  transactionId: string,
  invoiceId: string,
): StageEvent => ({
  type: "stage_action",
  action: linkAction(transactionId, invoiceId),
});

/** One invoice the manual picker offers a movement. */
export type PickerOption = {
  invoice: CatalogueInvoice;
  /** The movement a staged link already gives this invoice to: the option
   * is shown disabled. */
  stagedFor: string | null;
  /** How many movements are already linked to it. An invoice may settle
   * several movements, as partial payments do. */
  linked: number;
};
/** The invoices a movement may be linked to by hand, by whether they
 * settle its amount, newest first. */
export function linkPicker(
  row: LedgerRow,
  invoices: readonly CatalogueInvoice[],
  actions: readonly StagedAction[] = [],
): { settles: PickerOption[]; other: PickerOption[] } {
  const staged = stagedLinks(actions);
  const id = row.transaction.transaction_id;
  const options = invoices
    .filter((invoice) => row.transaction.direction === flowOf(invoice))
    .map((invoice): PickerOption => ({
      invoice,
      stagedFor:
        staged.invoices.get(invoice.invoice_id) !== id
          ? (staged.invoices.get(invoice.invoice_id) ?? null)
          : null,
      linked: invoice.linked_transaction_ids.filter((linked) => linked !== id)
        .length,
    }))
    .sort((left, right) =>
      right.invoice.issued_at.localeCompare(left.invoice.issued_at),
    );
  return {
    settles: options.filter((option) => settles(row, option.invoice)),
    other: options.filter((option) => !settles(row, option.invoice)),
  };
}

// ---- Links the two catalogues disagree about ---------------------------------

/** One one-sided link, and the repair the page can stage for it. */
export type LinkInconsistency = {
  invoiceId: string;
  transactionId: string;
  direction: "invoice-only" | "transaction-only";
  invoice: CatalogueInvoice | null;
  row: LedgerRow | null;
  /** The link that makes both sides cite each other, or why there is
   * none here. */
  repair:
    | { kind: "link" }
    | {
        kind: "none";
        /** `not_loaded`: the movement is outside the rows read, so whether it
         * cites another invoice is not known here. */
        why: "invoice_missing" | "cites_another" | "not_loaded";
      };
};

/**
 * The one-sided links `ledger.check` found, with a repair where a link
 * mends both sides: a movement that cites an invoice which does not list
 * it, or an invoice that lists a movement which cites nothing. A movement
 * that cites another invoice is left for the person: a link would leave
 * that other invoice one-sided.
 */
export function inconsistencies(
  found: LedgerCheckResult["link_inconsistencies"],
  rows: readonly LedgerRow[] | null,
  invoices: readonly CatalogueInvoice[],
): LinkInconsistency[] {
  const byRow = new Map(
    (rows ?? []).map((row) => [row.transaction.transaction_id, row]),
  );
  const byInvoice = new Map(
    invoices.map((invoice) => [invoice.invoice_id, invoice]),
  );
  return found.map((item) => {
    const invoice = byInvoice.get(item.invoice_id) ?? null;
    const row = byRow.get(item.transaction_id) ?? null;
    let repair: LinkInconsistency["repair"];
    if (item.direction === "transaction-only")
      repair = invoice
        ? { kind: "link" }
        : { kind: "none", why: "invoice_missing" };
    else if (!invoice) repair = { kind: "none", why: "invoice_missing" };
    else if (!row) repair = { kind: "none", why: "not_loaded" };
    else if (row.transaction.invoice_id !== null)
      repair = { kind: "none", why: "cites_another" };
    else repair = { kind: "link" };
    return {
      invoiceId: item.invoice_id,
      transactionId: item.transaction_id,
      direction: item.direction,
      invoice,
      row,
      repair,
    };
  });
}
