import type * as React from "react";
import { cn } from "./cn";
import { Icon } from "./icon";
import { inBox, type ColumnLayout } from "./dataGridModel";
import { cellCount, type GridNavigation } from "./dataGridNavigation";
import {
  CELL,
  ROW,
  rangeShadow,
  type gridColumnPresentation,
} from "./dataGridPresentation";
import { CellStateContext, FOCUSED, UNFOCUSED } from "./dataGridCellState";
import type {
  DataGridProps,
  Editing,
  GridColumn,
  GridRow,
  RowContext,
} from "./dataGridTypes";
import type { useGridViewport } from "./dataGridViewport";
import { listOf } from "@/shared/lists";

/** One measured data, section or custom row, including its accessibility notes. */
export function DataGridRow<R>({
  at,
  rows,
  ordered,
  layout,
  viewport,
  navigation,
  presentation,
  selection,
  focused,
  editing,
  editable,
  describeRow,
  describeCell,
  rowState,
  editorFor,
  pointerCell,
  clickCell,
  menuCell,
  doubleCell,
  onToggleSection,
}: {
  at: number;
  rows: readonly GridRow<R>[];
  ordered: readonly GridColumn<R>[];
  layout: ColumnLayout;
  viewport: ReturnType<typeof useGridViewport<R>>;
  navigation: GridNavigation<R>;
  presentation: ReturnType<typeof gridColumnPresentation<R>>;
  selection: DataGridProps<R>["selection"];
  focused: boolean;
  editing: Editing | null;
  editable: boolean;
  describeRow: DataGridProps<R>["describeRow"];
  describeCell: DataGridProps<R>["describeCell"];
  rowState: DataGridProps<R>["rowState"];
  editorFor(
    key: string,
    column: string,
    initial?: string,
  ): React.ReactNode | null;
  pointerCell(event: React.PointerEvent, row: GridRow<R>, column: string): void;
  clickCell(event: React.MouseEvent, row: GridRow<R>): void;
  menuCell(
    event: React.MouseEvent,
    row: GridRow<R>,
    column: string | null,
  ): void;
  doubleCell(row: GridRow<R>, column: string): void;
  onToggleSection: DataGridProps<R>["onToggleSection"];
}) {
  const { view, tops, heights, needsMeasure, measureRef } = viewport;
  const { resolvedIndex, resolved, cellId, box } = navigation;
  const { cellPresentation } = presentation;
  const isStop = (at: number, column: string) =>
    resolvedIndex === at && resolved?.column === column;
  const statusId = (at: number) => cellId(at, "status");

  const drawRow = (at: number) => {
    const row = rows[at];
    if (!row) return null;
    const top = tops[at] ?? 0;
    const measure = needsMeasure(row);
    const height = measure ? undefined : heights[at];
    const status = describeRow?.(row.key);
    const state = rowState?.(row.key);
    const tokens = state
      ? (["changed", "refused", "locked"] as const).filter(
          (name) => state[name],
        )
      : [];
    const selected = row.kind === "data" && !!selection?.has(row.key);
    const common = {
      role: "row" as const,
      "aria-rowindex": at + 2,
      "aria-selected": row.kind === "data" && selection ? selected : undefined,
      "aria-current": state?.current || undefined,
      "data-slot": "data-grid-row",
      "data-key": row.key,
      "data-kind": row.kind,
      "data-selected": selected || undefined,
      "data-state": tokens.length ? tokens.join(" ") : undefined,
      ref: measure ? measureRef : undefined,
      className: ROW,
      style: { top, height, width: layout.total },
    };
    const statusNode = status ? (
      <span hidden id={statusId(at)}>
        {status}
      </span>
    ) : null;
    const described = (extra?: string) =>
      [status ? statusId(at) : null, extra].filter(Boolean).join(" ") ||
      undefined;

    if (row.kind === "data") {
      return (
        <div key={row.key} {...common}>
          {ordered.map((column, position) => {
            const id = cellId(at, String(position));
            const activeHere = isStop(at, column.id);
            const note = describeCell?.(row.key, column.id);
            const reason =
              note?.readOnlyReason ?? column.readOnlyReason?.(row.data);
            const readOnly = editable && (!!reason || !column.editor);
            const ranged = box ? inBox(box, at, position) : false;
            const isEditing =
              editing?.key === row.key && editing.column === column.id;
            const editor = isEditing
              ? editorFor(row.key, column.id, editing.initial)
              : null;
            const noteId = `${id}-note`;
            const noteText = listOf(
              document.documentElement.lang || undefined,
              [note?.text, reason].filter((part): part is string => !!part),
              "plain",
            );
            return (
              <div
                key={column.id}
                id={id}
                role="gridcell"
                aria-colindex={position + 1}
                aria-describedby={described(noteText ? noteId : undefined)}
                aria-invalid={note?.invalid || undefined}
                aria-readonly={readOnly || undefined}
                tabIndex={activeHere ? 0 : -1}
                data-slot="data-grid-cell"
                data-column={column.id}
                data-active={activeHere || undefined}
                data-in-range={ranged || undefined}
                className={cellPresentation[position]!.className}
                style={{
                  width: cellPresentation[position]!.width,
                  boxShadow:
                    ranged && box
                      ? rangeShadow(
                          at === box.top,
                          at === box.bottom,
                          position === box.start,
                          position === box.end,
                        )
                      : undefined,
                  ...cellPresentation[position]!.sticky,
                }}
                onPointerDown={(event) => pointerCell(event, row, column.id)}
                onClick={(event) => clickCell(event, row)}
                onDoubleClick={() => doubleCell(row, column.id)}
                onContextMenu={(event) => menuCell(event, row, column.id)}
              >
                {editor !== null ? (
                  <div className="absolute inset-0 z-(--layer-grid-editor) flex">
                    {editor}
                  </div>
                ) : (
                  <CellStateContext.Provider
                    value={activeHere && focused ? FOCUSED : UNFOCUSED}
                  >
                    {column.cell(row.data, {
                      key: row.key,
                      active: activeHere,
                      selected,
                      narrowed: layout.byId.get(column.id)?.narrowed === true,
                    })}
                  </CellStateContext.Provider>
                )}
                {noteText && (
                  <span hidden id={noteId}>
                    {noteText}
                  </span>
                )}
              </div>
            );
          })}
          {statusNode}
        </div>
      );
    }

    // A section or a one-cell custom row is one cell across the grid, kept
    // in view while the grid scrolls sideways.
    const count = cellCount(row, ordered.length);
    if (row.kind === "section" || count <= 1) {
      const id = cellId(at, "s");
      const activeHere = isStop(at, "");
      const isEditing = editing?.key === row.key && editing.column === "";
      const editor =
        isEditing && row.kind === "custom"
          ? editorFor(row.key, "0", editing.initial)
          : null;
      return (
        <div key={row.key} {...common}>
          <div
            id={id}
            role="gridcell"
            aria-colindex={1}
            aria-colspan={ordered.length || 1}
            aria-expanded={row.kind === "section" ? !row.collapsed : undefined}
            aria-describedby={described()}
            tabIndex={count > 0 ? (activeHere ? 0 : -1) : undefined}
            data-slot="data-grid-cell"
            data-active={activeHere || undefined}
            className={cn(
              CELL,
              "sticky start-0 z-(--layer-grid-sticky)",
              row.kind === "section" && "gap-2 font-medium",
            )}
            style={{ width: view.width || layout.total }}
            onPointerDown={
              count > 0 ? (event) => pointerCell(event, row, "") : undefined
            }
            onClick={
              row.kind === "section"
                ? () => onToggleSection?.(row.key)
                : undefined
            }
            onDoubleClick={
              row.kind === "custom" ? () => doubleCell(row, "") : undefined
            }
            onContextMenu={(event) => menuCell(event, row, null)}
          >
            {row.kind === "section" ? (
              <>
                <span
                  className="flex min-w-0 flex-1 items-center gap-2"
                  style={{
                    paddingInlineStart: `calc(var(--spacing) * ${4 * (row.depth ?? 0)})`,
                  }}
                >
                  <Icon
                    name={row.collapsed ? "forward" : "chevronDown"}
                    size="xs"
                  />
                  <span className="min-w-0 truncate">{row.label}</span>
                  {row.hint && (
                    <span className="min-w-0 truncate font-normal text-muted-foreground">
                      {row.hint}
                    </span>
                  )}
                </span>
                {row.summary && (
                  <span className="shrink-0 text-muted-foreground">
                    {row.summary}
                  </span>
                )}
              </>
            ) : editor !== null ? (
              <div className="absolute inset-0 z-(--layer-grid-editor) flex">
                {editor}
              </div>
            ) : (
              row.render(customContext(at, row, count))
            )}
          </div>
          {statusNode}
        </div>
      );
    }
    return (
      <div key={row.key} {...common}>
        {row.render(customContext(at, row, count))}
        {statusNode}
      </div>
    );
  };

  function customContext(
    at: number,
    row: Extract<GridRow<R>, { kind: "custom" }>,
    count: number,
  ): RowContext {
    const activeHere = resolvedIndex === at;
    const status = describeRow?.(row.key) ? statusId(at) : undefined;
    const editingCell =
      editing?.key === row.key && count > 1
        ? Number(editing.column) || 0
        : null;
    return {
      key: row.key,
      active: activeHere,
      activeCell:
        activeHere && count > 1 ? Number(resolved?.column) || 0 : null,
      editingCell,
      editor:
        editingCell !== null && editing
          ? editorFor(row.key, editing.column, editing.initial)
          : null,
      cellProps: (cell) => {
        const column = String(cell);
        const here = isStop(at, column);
        return {
          id: cellId(at, `x${column}`),
          role: "gridcell",
          tabIndex: here ? 0 : -1,
          "aria-colindex": cell + 1,
          "aria-describedby": status,
          "data-slot": "data-grid-cell",
          "data-active": here || undefined,
          className: CELL,
          onPointerDown: (event) => pointerCell(event, row, column),
          onDoubleClick: () => doubleCell(row, column),
          onContextMenu: (event) => menuCell(event, row, null),
        };
      },
    };
  }

  return drawRow(at);
}
