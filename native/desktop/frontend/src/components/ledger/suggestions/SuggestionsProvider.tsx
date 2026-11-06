// What the Ledger page holds to offer as text in its fields. The catalogue and
// the known values of the whole history are each read the first time a field
// wants them, and what is staged and saved afterwards is added here rather than
// read again. All of it lives in this component's memory: the page is keyed by
// its reader, so everything held here goes with the profile, and nothing is
// written to browser storage.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Suggestion } from "@/components/ui/suggestions";
import { countryName, currencyName } from "../../../shared/codeNames";
import { formatPercent } from "../../../shared/numbers";
import { facts } from "../../../shell/compose";
import type { CatalogueInvoice } from "../../../shell/ledgerInvoiceOperations";
import type {
  LedgerKnownValueKind,
  LedgerKnownValuesResult,
  LedgerPort,
  LedgerRow,
} from "../../../shell/ledger";
import type { OutputLanguage } from "../../../shell/ledger";
import type {
  CapitalGood,
  ProrrataListedEntry,
} from "../../../shell/ledgerRegisterOperations";
import type { LedgerEntryOptionsResult } from "../../../shell/ledgerSetup";
import {
  NO_VOCABULARY,
  servedVocabulary,
  type ServedVocabulary,
  type VocabularyState,
} from "../../../shell/ledgerServedVocabulary";
import { holdLedgerClassifications } from "../../../shell/ledgerClassifications";
import { holdLedgerLanguage } from "../../../shell/ledgerLanguage";
import { holdLedgerLimits } from "../../../shell/ledgerLimits";
import {
  holdLedgerPeriods,
  holdLedgerPeriodsUnread,
} from "../../../shell/ledgerPeriods";
import type { StagedContent } from "../../../shell/ledgerStage";
import { useStrings, type Translate } from "../../../shell/strings";
import { useLedgerRead } from "../documents/useLedgerRead";
import { tokenText } from "../setup/setupWords";
import {
  capitalGoodOptions,
  counterpartyOptions,
  descriptionOptions,
  groupOptions,
  heldThenKnownOptions,
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
  | "m210_asset"
  | "asset_reference"
  | "investment_asset"
  | "prorrata_reference";

export type SuggestionScope = {
  /** Same kind ranks first. */
  invoiceKind?: CatalogueInvoice["kind"] | null;
  /** This party's records rank first. */
  party?: string;
  /** This year's register entries rank first. */
  year?: number;
};

type Held = {
  /** Every row drawn since the page opened, each as last drawn. */
  rows: readonly LedgerRow[];
  /** Values staged, and those saved since the page opened, by field. */
  staged: (field: string) => string[];
  /** Null until read, or where the read failed. */
  invoices: readonly CatalogueInvoice[] | null;
  /** The served entry vocabularies, by family; null likewise. */
  served: ReadonlyMap<string, ServedOptions> | null;
  /** Whether the entry vocabularies are being read, were read, or could not
   * be; the window holds no list to show meanwhile. */
  vocabulary: ServedVocabulary;
  /** The whole history's movement values; null likewise. */
  known: LedgerKnownValuesResult | null;
  /** The references the activity assets state; null likewise. */
  assetReferences: LedgerKnownValuesResult["asset_references"] | null;
  /** The capital goods register; null likewise. */
  capitalGoods: readonly CapitalGood[] | null;
  /** The prorrata register; null likewise. */
  prorrata: readonly ProrrataListedEntry[] | null;
  want(kind?: SuggestionKind): void;
};

const MOVEMENT_VALUES: { kinds: LedgerKnownValueKind[] } = {
  kinds: [
    "counterparty",
    "description",
    "group_label",
    "m210_payer",
    "m210_asset",
  ],
};
const ASSET_VALUES: { kinds: LedgerKnownValueKind[] } = {
  kinds: ["asset_reference"],
};
const NO_REQUEST = {};

/** The read each kind of field waits for; the rest wait for the catalogue. */
const READ_OF: Partial<Record<SuggestionKind, WantedRead>> = {
  counterparty: "movements",
  description: "movements",
  group: "movements",
  m210_payer: "movements",
  m210_asset: "movements",
  asset_reference: "assets",
  investment_asset: "capital",
  prorrata_reference: "prorrata",
};
type WantedRead = "invoices" | "movements" | "assets" | "capital" | "prorrata";

/** The text a stage states, by field: its new movements and its edits. */
function stagedTexts(stage: StagedContent): Map<string, string[]> {
  const texts = new Map<string, string[]>();
  const add = (field: string, value: string | undefined) => {
    if (value) texts.set(field, [...(texts.get(field) ?? []), value]);
  };
  for (const draft of stage.drafts)
    for (const [field, value] of Object.entries(draft.fields))
      add(field, value);
  for (const changes of Object.values(stage.rows))
    for (const [field, change] of Object.entries(changes))
      add(field, change.kind === "set" ? change.value : undefined);
  return texts;
}

/** What is staged now, then what an apply took off the stage since the page
 * opened: a saved value may lie outside anything drawn. */
function useStagedAndSaved(stage: StagedContent, applied: boolean) {
  const [saved, setSaved] = useState<ReadonlyMap<string, readonly string[]>>(
    () => new Map(),
  );
  const current = useMemo(() => stagedTexts(stage), [stage]);
  const before = useRef(current);
  useEffect(() => {
    const was = before.current;
    before.current = current;
    if (!applied || was === current) return;
    const left = [...was].flatMap(([field, values]) =>
      values
        .filter((value) => !current.get(field)?.includes(value))
        .map((value) => [field, value] as const),
    );
    if (left.length === 0) return;
    setSaved((held) => {
      const next = new Map(held);
      for (const [field, value] of left)
        next.set(field, [value, ...(next.get(field) ?? [])]);
      return next;
    });
  }, [current, applied]);
  return useCallback(
    (field: string) => [
      ...(current.get(field) ?? []),
      ...(saved.get(field) ?? []),
    ],
    [current, saved],
  );
}

/** Every row drawn since the page opened, the newest drawing of each. */
function useRowsSeen(rows: readonly LedgerRow[] | null) {
  const seen = useRef(new Map<string, LedgerRow>());
  return useMemo(() => {
    for (const row of rows ?? [])
      seen.current.set(row.transaction.transaction_id, row);
    return [...seen.current.values()];
  }, [rows]);
}

type ServedOptions = LedgerEntryOptionsResult["families"][number]["options"];

/** The families of words the entry vocabularies are served with; their words
 * ship with the window, so a key outside them has none. */
const ENTRY_WORD_FAMILIES = [
  "application.ledger.entry_options.deduction_fact_kind.",
  "application.ledger.entry_options.m210_payer_mode.",
  "application.ledger.entry_options.m210_income_concept.",
];

const HeldContext = createContext<Held | null>(null);

/** Holds the page's rows, stage and, once wanted, what each field reads. */
export function LedgerSuggestions({
  port,
  reader,
  rows,
  stage,
  applied,
  locale,
  children,
}: {
  port: LedgerPort;
  reader: string | null;
  rows: readonly LedgerRow[] | null;
  /** What is staged: what was typed in one movement suggests in the next. */
  stage: StagedContent;
  /** Whether the stage has been through an apply. */
  applied: boolean;
  /** The language the window shows, which the options' period names are
   * said in. */
  locale: string;
  children: ReactNode;
}) {
  const [wanted, setWanted] = useState<ReadonlySet<WantedRead>>(
    () => new Set(),
  );
  const { read } = useLedgerRead(
    port,
    reader,
    wanted.has("invoices"),
    "ledger.invoice.list",
    NO_REQUEST,
  );
  const invoices = read.value?.invoices ?? null;
  const { read: movementRead } = useLedgerRead(
    port,
    reader,
    wanted.has("movements"),
    "ledger.known-values",
    MOVEMENT_VALUES,
  );
  const { read: assetRead } = useLedgerRead(
    port,
    reader,
    wanted.has("assets"),
    "ledger.known-values",
    ASSET_VALUES,
  );
  const { read: capitalRead } = useLedgerRead(
    port,
    reader,
    wanted.has("capital"),
    "ledger.bienes_inversion.list",
    NO_REQUEST,
  );
  const { read: prorrataRead } = useLedgerRead(
    port,
    reader,
    wanted.has("prorrata"),
    "ledger.prorrata.list",
    NO_REQUEST,
  );
  const known = movementRead.value;
  const assetReferences = assetRead.value?.asset_references ?? null;
  const capitalGoods = capitalRead.value?.rows ?? null;
  const prorrata = prorrataRead.value?.entries ?? null;
  const want = useCallback((kind?: SuggestionKind) => {
    const needs = (kind && READ_OF[kind]) ?? "invoices";
    setWanted((held) => (held.has(needs) ? held : new Set([...held, needs])));
  }, []);
  const rowsSeen = useRowsSeen(rows);
  const staged = useStagedAndSaved(stage, applied);
  const { read: entryRead } = useLedgerRead(
    port,
    reader,
    true,
    "ledger.entry-options",
    { output_language: locale as OutputLanguage, periods: {} },
    locale,
  );
  const entryOptions = entryRead.value;
  // The read also serves the periods of the year and those that hold today,
  // which is where the page opens; the window keeps them as served.
  const servedPeriods = entryOptions?.periods ?? null;
  useEffect(() => {
    if (servedPeriods)
      holdLedgerPeriods(locale as OutputLanguage, servedPeriods);
  }, [servedPeriods, locale]);
  const unread = entryRead.phase === "failed";
  useEffect(() => {
    holdLedgerPeriodsUnread(unread);
    return () => holdLedgerPeriodsUnread(false);
  }, [unread]);
  const limits = entryOptions?.limits ?? null;
  useEffect(() => {
    holdLedgerLimits(limits);
    return () => holdLedgerLimits(null);
  }, [limits]);
  useEffect(() => {
    holdLedgerLanguage(locale as OutputLanguage);
    return () => holdLedgerLanguage(null);
  }, [locale]);
  const classifications = entryOptions?.classifications ?? null;
  useEffect(() => {
    holdLedgerClassifications(classifications);
    return () => holdLedgerClassifications(null);
  }, [classifications]);
  const served = useMemo(
    () =>
      entryOptions
        ? new Map(entryOptions.families.map((f) => [f.family, f.options]))
        : null,
    [entryOptions],
  );
  const vocabularyState: VocabularyState = entryOptions
    ? "ready"
    : entryRead.phase === "failed"
      ? "unavailable"
      : "loading";
  const vocabulary = useMemo(
    () => servedVocabulary(entryOptions ?? null, vocabularyState),
    [entryOptions, vocabularyState],
  );
  const held = useMemo<Held>(
    () => ({
      rows: rowsSeen,
      invoices,
      served,
      vocabulary,
      known,
      assetReferences,
      capitalGoods,
      prorrata,
      want,
      staged,
    }),
    [
      rowsSeen,
      invoices,
      served,
      vocabulary,
      known,
      assetReferences,
      capitalGoods,
      prorrata,
      want,
      staged,
    ],
  );
  return <HeldContext.Provider value={held}>{children}</HeldContext.Provider>;
}

/** A register entry by its year, kind, regime, sector and percentage: the
 * backend names what a movement cites, and an entry no reference can name is
 * not offered. Those of the movement's year come first. */
function prorrataOptions(
  entries: readonly ProrrataListedEntry[],
  year: number | undefined,
  t: Translate,
  locale: string,
): Suggestion[] {
  const named = entries.filter((entry) => entry.reference_id !== null);
  return [
    ...named.filter((entry) => entry.ejercicio === year),
    ...named.filter((entry) => entry.ejercicio !== year),
  ].map((entry) => {
    const percentage =
      entry.reference_kind === "provisional"
        ? entry.provisional_percentage
        : entry.definitive_percentage;
    return {
      value: entry.reference_id as string,
      label: facts(t, [
        entry.ejercicio,
        tokenText(t, "prorrata.kind", entry.reference_kind),
        tokenText(t, "prorrata.regime", entry.regime),
        entry.sector_id,
        percentage &&
          formatPercent(locale, percentage.decimal, { unit: "points" }),
      ]),
    };
  });
}

function optionsOf(
  held: Held,
  kind: SuggestionKind,
  scope: SuggestionScope,
  t: Translate,
  locale: string,
): readonly Suggestion[] | null {
  const { rows, invoices, known } = held;
  const transactions = rows.map((row) => row.transaction);
  const servedCodes = (family: string) => {
    const options = held.served?.get(family);
    return options
      ? { codes: options.map((option) => option.value), locale }
      : undefined;
  };
  switch (kind) {
    case "counterparty":
      return counterpartyOptions(
        rows,
        invoices,
        held.staged("counterparty"),
        known?.counterparties,
      );
    case "description":
      return descriptionOptions(
        rows,
        held.staged("description"),
        known?.descriptions,
      );
    case "group":
      return groupOptions(
        rows,
        held.staged("group_label"),
        known?.group_labels,
      );
    case "m210_payer":
      return heldThenKnownOptions(
        transactions.map(
          (row) => row.m210_income_classification?.payer_id ?? null,
        ),
        known?.m210_payers,
      );
    case "m210_asset":
      return heldThenKnownOptions(
        transactions.map(
          (row) => row.m210_income_classification?.asset_or_right_id ?? null,
        ),
        known?.m210_assets,
      );
    case "asset_reference":
      return held.assetReferences
        ? heldThenKnownOptions([], held.assetReferences)
        : null;
    case "investment_asset":
      return held.capitalGoods
        ? capitalGoodOptions(held.capitalGoods, scope.year)
        : null;
    case "prorrata_reference":
      return held.prorrata
        ? prorrataOptions(held.prorrata, scope.year, t, locale)
        : null;
    case "country":
      return usedCodeOptions(
        [
          ...transactions.map((row) => row.counterparty_country),
          ...(invoices ?? []).map((row) => row.counterparty_country),
        ],
        (code) => countryName(locale, code) ?? undefined,
        servedCodes("country"),
      );
    case "state":
      return usedCodeOptions(
        transactions.map((row) => row.counterparty_identification_state),
        (code) => countryName(locale, code) ?? undefined,
        servedCodes("country"),
      );
    case "currency":
      return usedCodeOptions(
        [
          ...transactions.map((row) => row.currency),
          ...(invoices ?? []).map((row) => row.currency),
        ],
        (code) => currencyName(locale, code) ?? undefined,
        servedCodes("currency"),
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
      return invoiceNumberOptions(
        invoices,
        { kind: scope.invoiceKind, party: scope.party },
        locale,
      );
    case "line_description":
      return lineDescriptionOptions(invoices, scope.party);
  }
}

/** What a field of `kind` offers, as props for an editor. Outside the page, and
 * while nothing is held, it offers nothing and the field stays free. */
export function useFieldSuggestions(
  kind: SuggestionKind | null,
  scope: SuggestionScope = {},
): {
  suggestions: readonly Suggestion[] | null;
  onSuggestionsWanted(): void;
} {
  const held = useContext(HeldContext);
  const t = useStrings();
  const locale = t.locale ?? "en";
  const { invoiceKind, party, year } = scope;
  const suggestions = useMemo(
    () =>
      held && kind
        ? optionsOf(held, kind, { invoiceKind, party, year }, t, locale)
        : null,
    [held, kind, invoiceKind, party, year, t, locale],
  );
  const want = held?.want;
  const onSuggestionsWanted = useCallback(() => {
    if (kind) want?.(kind);
  }, [want, kind]);
  return { suggestions, onSuggestionsWanted };
}

/** The codes a family serves, or null while unread, where the read failed and
 * outside the page: the field then stays free. */
export function useServedCodes(family: "country" | "currency") {
  const options = useContext(HeldContext)?.served?.get(family);
  return useMemo(
    () => (options ? options.map((option) => option.value) : null),
    [options],
  );
}

/** The registry's closed lists for an entry form, once served: while they
 * are being read or could not be, each is empty and `state` says which, so a
 * picker shows loading or unavailable and a stored id shows as itself. Outside
 * the page nothing is served and the state is unavailable. */
export function useVocabulary(): ServedVocabulary {
  return useContext(HeldContext)?.vocabulary ?? NO_VOCABULARY;
}

/** A served closed list as choices worded in the window's language, or null
 * while it cannot be offered. `withCode` shows the stored code before its word,
 * for a list the person knows by code. */
export function useServedChoices(
  family: "deduction_fact_kind" | "m210_payer_mode" | "m210_tipo_renta",
  { withCode = false }: { withCode?: boolean } = {},
): readonly { value: string; label: string }[] | null {
  const t = useStrings();
  const options = useContext(HeldContext)?.served?.get(family);
  return useMemo(
    () =>
      options
        ? options.map(({ value, label_key }) => {
            const word =
              label_key &&
              ENTRY_WORD_FAMILIES.some((prefix) => label_key.startsWith(prefix))
                ? t(label_key)
                : null;
            return {
              value,
              label: !word ? value : withCode ? `${value} · ${word}` : word,
            };
          })
        : null,
    [options, t, withCode],
  );
}

/** The catalogue as the page holds it: null while unread, where the read
 * failed, or outside the page. While `wanted`, using it asks for the read. */
export function useHeldInvoices(
  wanted = true,
): readonly CatalogueInvoice[] | null {
  const held = useContext(HeldContext);
  const want = held?.want;
  useEffect(() => {
    if (wanted) want?.();
  }, [wanted, want]);
  return held?.invoices ?? null;
}
