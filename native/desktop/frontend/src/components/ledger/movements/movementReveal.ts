// What keeps a movement a link selects out of the grid: the person's own
// filters, search or a folded group. Each is named exactly, so showing the
// movement clears only what hides it and leaves the rest of the view alone.

import type { LedgerRow } from "../../../shell/ledger";
import {
  NO_FILTERS,
  groupRows,
  keepsRow,
  matchesSearch,
  type GroupingId,
  type MovementFilters,
  type ReadinessSets,
  type SearchContext,
} from "./movementsModel";

/** The filters only the product applies, read from the ledger. */
const SERVER_KEYS: readonly (keyof MovementFilters)[] = [
  "importBatches",
  "importIssue",
  "hideRejected",
];

export type MovementHiding = {
  /** The filters that each, on its own, leave the movement out. */
  readonly filters: readonly (keyof MovementFilters)[];
  /** Whether the search leaves it out. */
  readonly search: boolean;
  /** The folded group it is in, by the grid's group key. */
  readonly group: string | null;
};

const inForce = (filters: MovementFilters, key: keyof MovementFilters) =>
  JSON.stringify(filters[key]) !== JSON.stringify(NO_FILTERS[key]);

/** Why `row` is not drawn, or null when nothing the person chose hides it.
 * The filters are a conjunction, so one that alone drops the row is one
 * that has to go; the product's own filters drop it through `members`. */
export function movementHiding(
  row: LedgerRow,
  view: {
    readonly filters: MovementFilters;
    readonly sets: ReadinessSets;
    readonly members: ReadonlySet<string> | null;
    readonly terms: readonly string[];
    readonly search: SearchContext;
    readonly grouping: GroupingId | null;
    readonly collapsed: ReadonlySet<string>;
  },
): MovementHiding | null {
  const { filters } = view;
  const keys = (Object.keys(NO_FILTERS) as (keyof MovementFilters)[]).filter(
    (key) => inForce(filters, key),
  );
  const hiding = keys.filter(
    (key) =>
      !SERVER_KEYS.includes(key) &&
      !keepsRow(row, { ...NO_FILTERS, [key]: filters[key] }, view.sets, null),
  );
  if (view.members && !view.members.has(row.transaction.transaction_id))
    hiding.push(...keys.filter((key) => SERVER_KEYS.includes(key)));
  const search = !matchesSearch(row, view.terms, view.search);
  const group =
    view.grouping === null
      ? null
      : (groupRows([row], view.grouping, {
          label: () => "",
          pendingFirst: false,
          descending: false,
        })[0]?.key ?? null);
  const folded = group !== null && view.collapsed.has(group) ? group : null;
  return hiding.length > 0 || search || folded !== null
    ? { filters: hiding, search, group: folded }
    : null;
}

/** `filters` with those that hide a movement taken off, and no others. */
export function withoutHiding(
  filters: MovementFilters,
  hiding: MovementHiding,
): MovementFilters {
  const next = { ...filters };
  for (const key of hiding.filters)
    Object.assign(next, { [key]: NO_FILTERS[key] });
  return next;
}
