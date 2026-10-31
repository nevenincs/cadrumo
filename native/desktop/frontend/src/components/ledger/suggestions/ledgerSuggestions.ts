// What the ledger's own records offer a field as it is typed in. Every list is
// drawn from rows the window already holds for the exact profile on screen,
// most recent first. A suggestion decides nothing: a pick is a draft edit the
// person sees, and the ledger still checks it on save. A pick never carries a
// classification, category, IVA category, operation type, rate or retention.

import type { Suggestion } from "@/components/ui/suggestions";
import type { CatalogueInvoice, LedgerRow } from "../../../shell/ledger";

/** The sibling fields a counterparty pick can fill. */
export type PartyFill = "name" | "tax_id" | "country";

const fold = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase()
    .replace(/\s+/g, " ")
    .trim();

const newestFirst = (invoices: readonly CatalogueInvoice[]) =>
  [...invoices].sort((left, right) =>
    right.issued_at.localeCompare(left.issued_at),
  );

/** The rows it is asked of, with one group first: same kind, same party. */
function firstThose<T>(rows: readonly T[], first: (row: T) => boolean): T[] {
  return [...rows.filter(first), ...rows.filter((row) => !first(row))];
}

/** Text once by its folded spelling, keeping the first (the newest) spelling. */
export function distinctText(texts: readonly (string | null)[]): string[] {
  const seen = new Map<string, string>();
  for (const text of texts) {
    const held = text?.trim();
    if (!held) continue;
    const key = fold(held);
    if (!seen.has(key)) seen.set(key, held);
  }
  return [...seen.values()];
}

const plainOptions = (texts: readonly string[]): Suggestion[] =>
  texts.map((text) => ({ value: text, label: text }));

type Party = {
  name: string;
  taxId: string | null;
  country: string | null;
};

/** The catalogue's parties, one per tax id, or per name where none is held. A
 * name under two tax ids stays two parties: they are never merged. */
function parties(invoices: readonly CatalogueInvoice[]): Party[] {
  const seen = new Map<string, Party>();
  for (const invoice of invoices) {
    const taxId = invoice.counterparty_tax_id?.trim().toUpperCase() || null;
    const name = invoice.counterparty_name.trim();
    if (!name && !taxId) continue;
    const key = taxId ?? `name:${fold(name)}`;
    if (!seen.has(key))
      seen.set(key, {
        name,
        taxId,
        country: invoice.counterparty_country.trim() || null,
      });
  }
  return [...seen.values()];
}

const partyFills = (party: Party): Record<string, string> => ({
  ...(party.name ? { name: party.name } : {}),
  ...(party.taxId ? { tax_id: party.taxId } : {}),
  ...(party.country ? { country: party.country } : {}),
});

const partyNote = (party: Party) =>
  [party.taxId, party.country].filter(Boolean).join(" · ") || undefined;

/** Counterparty names; the tax id finds one too, and tells two apart. */
export function partyNameOptions(
  invoices: readonly CatalogueInvoice[],
  scope: { kind?: CatalogueInvoice["kind"] | null } = {},
): Suggestion[] {
  const pool = firstThose(
    newestFirst(invoices),
    (invoice) => invoice.kind === scope.kind,
  );
  return parties(pool).flatMap((party) =>
    party.name
      ? [
          {
            value: party.name,
            label: party.name,
            note: partyNote(party),
            keywords: party.taxId ? [party.taxId] : undefined,
            fills: partyFills(party),
          },
        ]
      : [],
  );
}

/** Counterparty tax ids; the name finds one too. */
export function partyTaxIdOptions(
  invoices: readonly CatalogueInvoice[],
  scope: { kind?: CatalogueInvoice["kind"] | null } = {},
): Suggestion[] {
  const pool = firstThose(
    newestFirst(invoices),
    (invoice) => invoice.kind === scope.kind,
  );
  return parties(pool).flatMap((party) =>
    party.taxId
      ? [
          {
            value: party.taxId,
            label: party.taxId,
            note: party.name || undefined,
            keywords: party.name ? [party.name] : undefined,
            fills: partyFills(party),
          },
        ]
      : [],
  );
}

/** Invoice line descriptions, this party's first. */
export function lineDescriptionOptions(
  invoices: readonly CatalogueInvoice[],
  party = "",
): Suggestion[] {
  const wanted = fold(party);
  const pool = firstThose(
    newestFirst(invoices),
    (invoice) => wanted !== "" && fold(invoice.counterparty_name) === wanted,
  );
  return plainOptions(
    distinctText(
      pool.flatMap((invoice) => invoice.lines.map((line) => line.description)),
    ),
  );
}

/** Series in use, of the same kind and class first. */
export function seriesOptions(
  invoices: readonly CatalogueInvoice[],
  scope: { kind?: CatalogueInvoice["kind"] | null; invoiceClass?: string },
): Suggestion[] {
  const pool = firstThose(
    newestFirst(invoices),
    (invoice) =>
      invoice.kind === scope.kind &&
      invoice.invoice_class === scope.invoiceClass,
  );
  return plainOptions(distinctText(pool.map((invoice) => invoice.series)));
}

const invoiceNote = (invoice: CatalogueInvoice) =>
  [invoice.issued_at, invoice.counterparty_name].filter(Boolean).join(" · ") ||
  undefined;

/** Invoice numbers, of the same kind and then this party first. The fills name
 * the invoice's party; a rectificativa keeps its own series, so none is
 * offered. */
export function invoiceNumberOptions(
  invoices: readonly CatalogueInvoice[],
  scope: { kind?: CatalogueInvoice["kind"] | null; party?: string } = {},
): Suggestion[] {
  const wanted = fold(scope.party ?? "");
  const sameParty = (invoice: CatalogueInvoice) =>
    wanted !== "" && fold(invoice.counterparty_name) === wanted;
  const pool = firstThose(
    firstThose(newestFirst(invoices), (invoice) => invoice.kind === scope.kind),
    sameParty,
  );
  const seen = new Set<string>();
  return pool.flatMap((invoice) => {
    const number = invoice.invoice_number.trim();
    if (!number || seen.has(number)) return [];
    seen.add(number);
    return [
      {
        value: number,
        label: number,
        note: invoiceNote(invoice),
        fills: partyFills({
          name: invoice.counterparty_name.trim(),
          taxId: invoice.counterparty_tax_id?.trim() || null,
          country: invoice.counterparty_country.trim() || null,
        }),
      },
    ];
  });
}

/** Codes in use, the most used first. */
export function usedCodeOptions(
  codes: readonly (string | null)[],
  named?: (code: string) => string | undefined,
): Suggestion[] {
  const uses = new Map<string, number>();
  for (const code of codes) {
    const held = code?.trim().toUpperCase();
    if (held) uses.set(held, (uses.get(held) ?? 0) + 1);
  }
  return [...uses]
    .sort((left, right) => right[1] - left[1])
    .map(([code]) => ({ value: code, label: code, note: named?.(code) }));
}

const newestRowsFirst = (rows: readonly LedgerRow[]) =>
  [...rows].sort((left, right) =>
    right.transaction.date.localeCompare(left.transaction.date),
  );

/** Movement descriptions, each offering the counterparty it was last used
 * with. */
export function descriptionOptions(
  rows: readonly LedgerRow[],
  staged: readonly string[] = [],
): Suggestion[] {
  const seen = new Set<string>();
  const options: Suggestion[] = [];
  const add = (text: string, counterparty?: string) => {
    const held = text.trim();
    const key = fold(held);
    if (!held || seen.has(key)) return;
    seen.add(key);
    options.push({
      value: held,
      label: held,
      note: counterparty || undefined,
      fills: counterparty ? { counterparty } : undefined,
    });
  };
  for (const text of staged) add(text);
  for (const { transaction } of newestRowsFirst(rows))
    add(transaction.description, transaction.counterparty.trim());
  return options;
}

/** Movement counterparties: staged, then held rows, then the catalogue's
 * parties. A row's country and identification state come along as fills. */
export function counterpartyOptions(
  rows: readonly LedgerRow[],
  invoices: readonly CatalogueInvoice[] | null,
  staged: readonly string[] = [],
): Suggestion[] {
  const seen = new Set<string>();
  const options: Suggestion[] = [];
  const add = (name: string, fills?: Record<string, string>, note?: string) => {
    const held = name.trim();
    const key = fold(held);
    if (!held || seen.has(key)) return;
    seen.add(key);
    options.push({
      value: held,
      label: held,
      note,
      fills: fills && Object.keys(fills).length > 0 ? fills : undefined,
    });
  };
  for (const text of staged) add(text);
  for (const { transaction } of newestRowsFirst(rows))
    add(transaction.counterparty, {
      ...(transaction.counterparty_country
        ? { counterparty_country: transaction.counterparty_country }
        : {}),
      ...(transaction.counterparty_identification_state
        ? {
            counterparty_identification_state:
              transaction.counterparty_identification_state,
          }
        : {}),
    });
  for (const party of parties(newestFirst(invoices ?? [])))
    add(
      party.name,
      party.country ? { counterparty_country: party.country } : undefined,
      partyNote(party),
    );
  return options;
}

/** Group labels in use. */
export function groupOptions(rows: readonly LedgerRow[]): Suggestion[] {
  return plainOptions(
    distinctText(newestRowsFirst(rows).map((row) => row.group_label)),
  );
}

/** The fills that apply: only to what the person left empty. */
export function emptyFills<Field extends string>(
  fills: Readonly<Record<string, string>> | undefined,
  current: Readonly<Partial<Record<Field, string | null>>>,
  fields: Readonly<Partial<Record<string, Field>>>,
): [Field, string][] {
  if (!fills) return [];
  return Object.entries(fields).flatMap(([from, to]) => {
    const offered = fills[from];
    if (!to || !offered) return [];
    return (current[to] ?? "").trim() === "" ? [[to, offered]] : [];
  }) as [Field, string][];
}
