// How the person is looking at the movements: filters, search, sort, the
// groups folded and the selection, held in the page's memory for the
// profile while the section is put away; and the saved view and grouping,
// which the window keeps as presentation. Nothing here holds a value the
// person typed in storage: the search and the filters' values stay in
// memory, and a saved view is kept by its id only.

import { useCallback, useState, type RefObject } from "react";
import type { LedgerView } from "../../../shell/layout";
import type { LedgerWindowScope } from "../../../shell/ledgerWindow";
import {
  DEFAULT_SORT,
  NO_FILTERS,
  SAVED_VIEWS,
  SERVER_GROUPING,
  isGrouping,
  isSavedView,
  serverFilters,
  serverSortField,
  viewFilters,
  type GroupingId,
  type MovementFilters,
  type MovementSort,
  type SavedViewId,
} from "./movementsModel";

/** What the movements section keeps of itself in the page's memory. */
export type MovementsMemory = {
  filters: MovementFilters;
  search: string;
  sort: MovementSort;
  collapsed: string[];
  selection: string[];
};

export type MovementsView = {
  filters: MovementFilters;
  /** Replaces the filters; a saved view no longer describes them. */
  setFilters: (filters: MovementFilters) => void;
  search: string;
  setSearch: (search: string) => void;
  sort: MovementSort;
  setSort: (sort: MovementSort) => void;
  collapsed: ReadonlySet<string>;
  setCollapsed: (collapsed: ReadonlySet<string>) => void;
  selection: ReadonlySet<string>;
  setSelection: (selection: ReadonlySet<string>) => void;
  savedView: SavedViewId | null;
  chooseView: (view: SavedViewId) => void;
  groupBy: GroupingId | null;
  setGroupBy: (groupBy: GroupingId | null) => void;
};

export function useMovementsView(
  memory: RefObject<{ movements?: MovementsMemory }>,
  view: LedgerView,
  onViewChange: (update: (current: LedgerView) => LedgerView) => void,
): MovementsView {
  const savedView = isSavedView(view.savedView) ? view.savedView : null;
  const groupBy = isGrouping(view.groupBy) ? view.groupBy : null;
  const [state, setState] = useState<MovementsMemory>(
    () =>
      memory.current.movements ?? {
        filters: savedView ? viewFilters(savedView) : NO_FILTERS,
        search: "",
        sort: DEFAULT_SORT,
        collapsed: [],
        selection: [],
      },
  );
  const update = useCallback(
    (patch: Partial<MovementsMemory>) =>
      setState((current) => {
        const next = { ...current, ...patch };
        memory.current.movements = next;
        return next;
      }),
    [memory],
  );
  return {
    filters: state.filters,
    setFilters: (filters) => {
      update({ filters });
      if (savedView !== null)
        onViewChange((current) => ({ ...current, savedView: null }));
    },
    search: state.search,
    setSearch: (search) => update({ search }),
    sort: state.sort,
    setSort: (sort) => update({ sort }),
    collapsed: new Set(state.collapsed),
    setCollapsed: (collapsed) => update({ collapsed: [...collapsed] }),
    selection: new Set(state.selection),
    setSelection: (selection) => update({ selection: [...selection] }),
    savedView,
    chooseView: (next) => {
      update({ filters: viewFilters(next), collapsed: [] });
      // A view that groups brings its grouping; leaving one takes it away.
      const own = SAVED_VIEWS[next].groupBy;
      const left = savedView ? SAVED_VIEWS[savedView].groupBy : undefined;
      onViewChange((current) => ({
        ...current,
        savedView: next,
        groupBy:
          own ?? (left && current.groupBy === left ? null : current.groupBy),
      }));
    },
    groupBy,
    setGroupBy: (next) => {
      update({ collapsed: [] });
      onViewChange((current) => ({ ...current, groupBy: next }));
    },
  };
}

/**
 * What the period window reads beside its period. "All periods" is read in
 * part, so the product sorts and partitions it, and applies its own filters
 * where one read can say them. A period is read whole and refined here.
 */
export function windowScope(
  allPeriods: boolean,
  movements: Pick<MovementsView, "filters" | "sort" | "groupBy">,
): LedgerWindowScope {
  if (!allPeriods) return {};
  const field = serverSortField(movements.sort.key);
  const scopes = serverFilters(movements.filters);
  return {
    ...(scopes.length === 1 ? scopes[0] : {}),
    ...(field ? { sort_by: field, sort_order: movements.sort.direction } : {}),
    ...(movements.groupBy === SERVER_GROUPING ? { by_group: true } : {}),
  };
}
