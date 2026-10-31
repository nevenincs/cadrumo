// What the Ledger page holds to offer as text in its fields. The catalogue is
// read the first time a field wants it. All of it lives in this component's
// memory: the page is keyed by its reader, so everything held here goes with
// the profile, and nothing is written to browser storage.

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Suggestion } from "@/components/ui/suggestions";
import { countryName, currencyName } from "../../../shared/codeNames";
import type {
  CatalogueInvoice,
  LedgerPort,
  LedgerRow,
} from "../../../shell/ledger";
import { useStrings } from "../../../shell/strings";
import { useLedgerRead } from "../documents/useLedgerRead";
import {
  counterpartyOptions,
  descriptionOptions,
  distinctText,
  groupOptions,
  invoiceNumberOptions,
  lineDescriptionOptions,
  partyNameOptions,
  partyTaxIdOptions,
  usedCodeOptions,
} from "./ledgerSuggestions";

export type SuggestionKind =
  | "counterparty"
  | "description"
  | "group"
  | "party_name"
  | "party_tax_id"
  | "supplier"
  | "supplier_tax_id"
  | "invoice_number"
  | "line_description"
  | "country"
  | "state"
  | "currency"
  | "m210_payer"
  | "m210_asset";

export type SuggestionScope = {
  /** Same kind ranks first. */
  invoiceKind?: CatalogueInvoice["kind"] | null;
  /** This party's records rank first. */
  party?: string;
};

type Held = {
  rows: readonly LedgerRow[];
  /** Values staged but not saved, by field. */
  staged: (field: string) => string[];
  /** Null until read, or where the read failed. */
  invoices: readonly CatalogueInvoice[] | null;
  want(): void;
};

const HeldContext = createContext<Held | null>(null);

/** Holds the page's rows, stage and, once wanted, the catalogue. */
export function LedgerSuggestions({
  port,
  reader,
  rows,
  drafts,
  children,
}: {
  port: LedgerPort;
  reader: string | null;
  rows: readonly LedgerRow[] | null;
  /** New movements staged: what was typed in one suggests in the next. */
  drafts: readonly { fields: Partial<Record<string, string>> }[];
  children: ReactNode;
}) {
  const [wanted, setWanted] = useState(false);
  const { read } = useLedgerRead(
    port,
    reader,
    wanted,
    "ledger.invoice.list",
    {},
  );
  const invoices = read.value?.invoices ?? null;
  const want = useCallback(() => setWanted(true), []);
  const held = useMemo<Held>(
    () => ({
      rows: rows ?? [],
      invoices,
      want,
      staged: (field) =>
        drafts.flatMap((draft) => {
          const value = draft.fields[field];
          return value ? [value] : [];
        }),
    }),
    [rows, invoices, want, drafts],
  );
  return <HeldContext.Provider value={held}>{children}</HeldContext.Provider>;
}

function optionsOf(
  held: Held,
  kind: SuggestionKind,
  scope: SuggestionScope,
  locale: string,
): readonly Suggestion[] | null {
  const { rows, invoices } = held;
  const transactions = rows.map((row) => row.transaction);
  switch (kind) {
    case "counterparty":
      return counterpartyOptions(rows, invoices, held.staged("counterparty"));
    case "description":
      return descriptionOptions(rows, held.staged("description"));
    case "group":
      return groupOptions(rows);
    case "m210_payer":
      return distinctText(
        transactions.map(
          (row) => row.m210_income_classification?.payer_id ?? null,
        ),
      ).map((text) => ({ value: text, label: text }));
    case "m210_asset":
      return distinctText(
        transactions.map(
          (row) => row.m210_income_classification?.asset_or_right_id ?? null,
        ),
      ).map((text) => ({ value: text, label: text }));
    case "country":
      return usedCodeOptions(
        [
          ...transactions.map((row) => row.counterparty_country),
          ...(invoices ?? []).map((row) => row.counterparty_country),
        ],
        (code) => countryName(locale, code) ?? undefined,
      );
    case "state":
      return usedCodeOptions(
        transactions.map((row) => row.counterparty_identification_state),
        (code) => countryName(locale, code) ?? undefined,
      );
    case "currency":
      return usedCodeOptions(
        [
          ...transactions.map((row) => row.currency),
          ...(invoices ?? []).map((row) => row.currency),
        ],
        (code) => currencyName(locale, code) ?? undefined,
      );
  }
  if (invoices === null) return null;
  switch (kind) {
    case "party_name":
      return partyNameOptions(invoices, { kind: scope.invoiceKind });
    case "party_tax_id":
      return partyTaxIdOptions(invoices, { kind: scope.invoiceKind });
    case "supplier":
      return partyNameOptions(
        invoices.filter((row) => row.kind === "received"),
      );
    case "supplier_tax_id":
      return partyTaxIdOptions(
        invoices.filter((row) => row.kind === "received"),
      );
    case "invoice_number":
      return invoiceNumberOptions(invoices, {
        kind: scope.invoiceKind,
        party: scope.party,
      });
    case "line_description":
      return lineDescriptionOptions(invoices, scope.party);
  }
}

/** What a field of `kind` offers, as props for an editor. Outside the page, and
 * while nothing is held, it offers nothing and the field stays free. */
export function useFieldSuggestions(
  kind: SuggestionKind,
  scope: SuggestionScope = {},
): {
  suggestions: readonly Suggestion[] | null;
  onSuggestionsWanted(): void;
} {
  const held = useContext(HeldContext);
  const locale = useStrings().locale ?? "en";
  const { invoiceKind, party } = scope;
  const suggestions = useMemo(
    () => (held ? optionsOf(held, kind, { invoiceKind, party }, locale) : null),
    [held, kind, invoiceKind, party, locale],
  );
  const want = held?.want;
  const onSuggestionsWanted = useCallback(() => want?.(), [want]);
  return { suggestions, onSuggestionsWanted };
}
