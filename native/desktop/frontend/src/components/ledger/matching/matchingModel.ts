// How the Ledger page shows the ledger's proposals of which invoice settles
// which movement. The ledger weighs flow, currency and amount, ranks the
// candidates and says which tie (`ledger.invoice.match`); the window looks
// the movements and invoices it holds up by id and shows each pair with the
// evidence it stands on. A suggestion is a proposal the person links, and a
// link is permanent. Nothing here decides which pair is best.

import type {
  LedgerCheckResult,
  LedgerInvoiceMatchResult,
} from "../../../shell/ledgerInvoiceOperations";
import type {
  CatalogueInvoiceSnapshot,
  LedgerInvoiceMatchPair,
} from "../../../shell/ledgerInvoiceContract";
import type { LedgerRow } from "../../../shell/ledger";
import type { StageEvent, StagedAction } from "../../../shell/ledgerStage";

/** The evidence a pair stands on, shown as chips. */
export type MatchChip =
  | { kind: "number" }
  | { kind: "gap"; days: number }
  | { kind: "counterparty" }
  | { kind: "amount" };

/** One movement and one invoice that settle each other. */
export type MatchPair = {
  row: LedgerRow;
  invoice: CatalogueInvoiceSnapshot;
  /** What the invoice settles, as the ledger states it. */
  settles: string;
  number: boolean;
  /** Days from the invoice's date to the movement's. */
  gap: number;
  counterparty: boolean;
  chips: MatchChip[];
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
  /** The suggestions, newest movement first. */
  list: MatchSuggestion[];
};

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

/** The pairs of a served answer, as the window shows them: each side looked
 * up among the records the window holds, a pair with a side it does not hold
 * left out. */
export function remapMatches(
  result: Pick<LedgerInvoiceMatchResult, "suggestions">,
  rows: readonly LedgerRow[],
  invoices: readonly CatalogueInvoiceSnapshot[],
): Reconciliation {
  const rowById = new Map(
    rows.map((row) => [row.transaction.transaction_id, row]),
  );
  const invoiceById = new Map(
    invoices.map((invoice) => [invoice.invoice_id, invoice]),
  );
  const pairOf = (served: LedgerInvoiceMatchPair): MatchPair | null => {
    const row = rowById.get(served.transaction_id);
    const invoice = invoiceById.get(served.invoice_id);
    if (!row || !invoice) return null;
    const chips: MatchChip[] = [];
    if (served.number) chips.push({ kind: "number" });
    chips.push({ kind: "gap", days: served.gap });
    if (served.counterparty) chips.push({ kind: "counterparty" });
    chips.push({ kind: "amount" });
    return {
      row,
      invoice,
      settles: invoice.settlement_amount.decimal,
      number: served.number,
      gap: served.gap,
      counterparty: served.counterparty,
      chips,
    };
  };
  const known = (served: readonly LedgerInvoiceMatchPair[]) =>
    served.flatMap((each) => pairOf(each) ?? []);
  const list = result.suggestions.flatMap((served): MatchSuggestion[] => {
    const pair = pairOf(served);
    return pair
      ? [
          {
            ...pair,
            ambiguous: served.ambiguous,
            ties: known(served.ties),
            others: known(served.others),
          },
        ]
      : [];
  });
  return {
    best: new Map(
      list.map((each) => [each.row.transaction.transaction_id, each]),
    ),
    list,
  };
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
  invoice: CatalogueInvoiceSnapshot;
  /** The movement a staged link already gives this invoice to: the option
   * is shown disabled. */
  stagedFor: string | null;
  /** How many movements are already linked to it. An invoice may settle
   * several movements, as partial payments do. */
  linked: number;
};
/** The invoices the ledger offers a movement for a link by hand, as the
 * window holds them: those that settle its amount, and the rest. */
export function remapInvoiceChoices(
  choices: NonNullable<LedgerInvoiceMatchResult["invoice_choices"]>,
  invoices: readonly CatalogueInvoiceSnapshot[],
): { settles: PickerOption[]; other: PickerOption[] } {
  const invoiceById = new Map(
    invoices.map((invoice) => [invoice.invoice_id, invoice]),
  );
  const options = choices.flatMap((choice) => {
    const invoice = invoiceById.get(choice.invoice_id);
    return invoice
      ? [
          {
            settles: choice.settles,
            option: {
              invoice,
              stagedFor: choice.staged_for,
              linked: choice.linked,
            } satisfies PickerOption,
          },
        ]
      : [];
  });
  return {
    settles: options.filter((each) => each.settles).map((each) => each.option),
    other: options.filter((each) => !each.settles).map((each) => each.option),
  };
}

/** One movement the picker offers an invoice. */
export type MovementOption = {
  row: LedgerRow;
  /** The movement settles the invoice by flow, currency and amount. */
  settles: boolean;
};
/** The movements the ledger offers an invoice for a link by hand, as the
 * window holds them. */
export function remapMovementChoices(
  choices: NonNullable<LedgerInvoiceMatchResult["movement_choices"]>,
  rows: readonly LedgerRow[],
): MovementOption[] {
  const rowById = new Map(
    rows.map((row) => [row.transaction.transaction_id, row]),
  );
  return choices.flatMap((choice) => {
    const row = rowById.get(choice.transaction_id);
    return row ? [{ row, settles: choice.settles }] : [];
  });
}

// ---- Links the two catalogues disagree about ---------------------------------

/** One one-sided link, and the repair the page can stage for it. */
export type LinkInconsistency = {
  invoiceId: string;
  transactionId: string;
  direction: "invoice-only" | "transaction-only";
  invoice: CatalogueInvoiceSnapshot | null;
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
  invoices: readonly CatalogueInvoiceSnapshot[],
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
