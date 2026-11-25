import * as React from "react";
import {
  headerSelection,
  selectRange,
  selectionExtent,
  selectOnly,
  toggleKey,
  type SelectionCause,
} from "./dataGridModel";
import type { GridRow, DataGridProps } from "./dataGridTypes";

export const GridSelectionContext = React.createContext<{
  isSelected: (key: string) => boolean;
  toggle: (key: string, range: boolean) => void;
  /** The visible rows become the selection, or with `add` join it. */
  toggleAll: (add: boolean) => void;
  extent: "none" | "some" | "all";
} | null>(null);

/** Row selection shared by grid gestures and its checkbox controls. */
export function useGridSelection<R>({
  rows,
  index,
  dataKeys,
  selection,
  onSelectionChange,
}: {
  rows: readonly GridRow<R>[];
  index: ReadonlyMap<string, number>;
  dataKeys: readonly string[];
  selection: DataGridProps<R>["selection"];
  onSelectionChange: DataGridProps<R>["onSelectionChange"];
}) {
  const selectionAnchor = React.useRef<string | null>(null);
  // After Shift+Space, Shift with a vertical move extends the row
  // selection as well as the range, as a spreadsheet does in row mode.
  const rowMode = React.useRef(false);
  const changeSelection = (next: Set<string>, cause: SelectionCause) => {
    if (!selection || !onSelectionChange) return;
    onSelectionChange(next, cause);
  };
  const pickRow = (key: string, how: { toggle?: boolean; range?: boolean }) => {
    if (!selection) return;
    if (how.range) {
      changeSelection(
        selectRange(
          dataKeys,
          selectionAnchor.current,
          key,
          how.toggle ? selection : new Set(),
        ),
        "range",
      );
      return;
    }
    selectionAnchor.current = key;
    rowMode.current = false;
    if (how.toggle) changeSelection(toggleKey(selection, key), "toggle");
    else changeSelection(selectOnly(key), "select");
  };
  /** In row mode, the rows from the selection anchor to `key` become the
   * selection. */
  const extendRows = (key: string) => {
    if (!rowMode.current || !selection) return;
    const target = rows[index.get(key) ?? -1];
    if (target?.kind !== "data") return;
    changeSelection(
      selectRange(dataKeys, selectionAnchor.current, key),
      "range",
    );
  };

  const selectionContext = React.useMemo(
    () =>
      selection
        ? {
            isSelected: (key: string) => selection.has(key),
            toggle: (key: string, range: boolean) => {
              if (!onSelectionChange) return;
              if (range)
                onSelectionChange(
                  selectRange(
                    dataKeys,
                    selectionAnchor.current,
                    key,
                    selection,
                  ),
                  "range",
                );
              else {
                selectionAnchor.current = key;
                onSelectionChange(toggleKey(selection, key), "toggle");
              }
            },
            toggleAll: (add: boolean) =>
              onSelectionChange?.(
                headerSelection(dataKeys, selection, add),
                "all",
              ),
            extent: selectionExtent(dataKeys, selection),
          }
        : null,
    [selection, onSelectionChange, dataKeys],
  );

  return {
    selectionAnchor,
    rowMode,
    changeSelection,
    pickRow,
    extendRows,
    selectionContext,
  };
}
