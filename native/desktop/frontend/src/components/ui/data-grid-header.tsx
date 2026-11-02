import type * as React from "react";
import { cn } from "./cn";
import { Icon } from "./icon";
import { Tooltip, TooltipTrigger, TooltipContent } from "./tooltip";
import { MIN_COLUMN_REM, type ColumnLayout } from "./dataGridModel";
import { HEADER_INDEX, type GridNavigation } from "./dataGridNavigation";
import {
  ACTIVE_RING,
  type gridColumnPresentation,
} from "./dataGridPresentation";
import type { DataGridProps, GridColumn } from "./dataGridTypes";

/** Column headers retain the grid's tab stop, pinned cues and pointer handles. */
export function DataGridHeader<R>({
  header,
  scroller,
  ordered,
  layout,
  view,
  remPx,
  navigation,
  presentation,
  earlierColumnsLabel,
  moreColumnsLabel,
  steerLeft,
  syncView,
  sort,
  onSort,
  drop,
  suppressClick,
  startReorder,
  startResize,
  fitColumn,
}: {
  header: React.RefObject<HTMLDivElement | null>;
  scroller: React.RefObject<HTMLDivElement | null>;
  ordered: readonly GridColumn<R>[];
  layout: ColumnLayout;
  view: { left: number; width: number };
  remPx: number;
  navigation: GridNavigation<R>;
  presentation: ReturnType<typeof gridColumnPresentation<R>>;
  earlierColumnsLabel: DataGridProps<R>["earlierColumnsLabel"];
  moreColumnsLabel: DataGridProps<R>["moreColumnsLabel"];
  steerLeft(element: HTMLElement, left: number): void;
  syncView(): void;
  sort: DataGridProps<R>["sort"];
  onSort: DataGridProps<R>["onSort"];
  drop: string | null;
  suppressClick: React.RefObject<boolean>;
  startReorder(
    event: React.PointerEvent<HTMLDivElement>,
    column: GridColumn<R>,
  ): void;
  startResize(
    event: React.PointerEvent<HTMLDivElement>,
    column: GridColumn<R>,
  ): void;
  fitColumn(column: GridColumn<R>): void;
}) {
  const { cellId, moveTo, resolvedIndex, resolved } = navigation;
  const isStop = (at: number, column: string) =>
    resolvedIndex === at && resolved?.column === column;
  const { pinned, pinnedEdge, stickyStyle, firstEnd, lastStart } = presentation;
  // Columns scrolled out of view under the pinned end group, which the
  // header names with a cue that scrolls to the first of them.
  const shownRight = view.left + view.width - layout.endCover;
  const beyond = layout.boxes.filter(
    (placed) => !placed.sticky && placed.left + placed.width > shownRight + 1,
  );
  const revealBeyond = () => {
    const element = scroller.current;
    const first = beyond[0];
    if (!element || !first) return;
    steerLeft(
      element,
      first.left + first.width - element.clientWidth + layout.endCover,
    );
    syncView();
  };
  // And those scrolled out of view under the pinned start group, which a
  // cue at its inner edge names and scrolls back to, the nearest first.
  const shownLeft = view.left + layout.startCover;
  const before = layout.boxes.filter(
    (placed) => !placed.sticky && placed.left < shownLeft - 1,
  );
  const revealBefore = () => {
    const element = scroller.current;
    const last = before.at(-1);
    if (!element || !last) return;
    steerLeft(element, last.left - layout.startCover);
    syncView();
  };
  const earlierCue =
    earlierColumnsLabel && before.length > 0 && view.width > 0 ? (
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            tabIndex={-1}
            data-slot="data-grid-earlier-columns"
            aria-label={earlierColumnsLabel(before.length)}
            className="absolute inset-y-0 start-full inline-flex items-center gap-0.5 border-e border-border bg-background px-1.5 text-xs font-medium text-muted-foreground tabular-nums hover:text-foreground"
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => {
              event.stopPropagation();
              revealBefore();
            }}
          >
            <Icon name="back" size="xs" />
            <span aria-hidden="true">+{before.length}</span>
          </button>
        </TooltipTrigger>
        <TooltipContent>{earlierColumnsLabel(before.length)}</TooltipContent>
      </Tooltip>
    ) : null;
  const moreCue =
    moreColumnsLabel && beyond.length > 0 && view.width > 0 ? (
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            tabIndex={-1}
            data-slot="data-grid-more-columns"
            aria-label={moreColumnsLabel(beyond.length)}
            className="absolute inset-y-0 end-full inline-flex items-center gap-0.5 border-s border-border bg-background px-1.5 text-xs font-medium text-muted-foreground tabular-nums hover:text-foreground"
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => {
              event.stopPropagation();
              revealBeyond();
            }}
          >
            <span aria-hidden="true">+{beyond.length}</span>
            <Icon name="forward" size="xs" />
          </button>
        </TooltipTrigger>
        <TooltipContent>{moreColumnsLabel(beyond.length)}</TooltipContent>
      </Tooltip>
    ) : null;

  const headerRow = (
    <div
      ref={header}
      role="rowgroup"
      className="sticky top-0 z-(--layer-grid-head) bg-background"
      style={{ width: layout.total }}
    >
      <div
        role="row"
        aria-rowindex={1}
        className="flex h-(--grid-row) border-b border-border-strong"
      >
        {ordered.map((column, at) => {
          const sorted = sort?.column === column.id ? sort.direction : null;
          const width = layout.byId.get(column.id)?.width ?? 0;
          const active = isStop(HEADER_INDEX, column.id);
          return (
            <div
              key={column.id}
              id={cellId(HEADER_INDEX, String(at))}
              role="columnheader"
              aria-colindex={at + 1}
              aria-sort={
                sorted === "asc"
                  ? "ascending"
                  : sorted === "desc"
                    ? "descending"
                    : column.sortable
                      ? "none"
                      : undefined
              }
              tabIndex={active ? 0 : -1}
              data-slot="data-grid-header-cell"
              data-header-column={column.id}
              data-active={active || undefined}
              data-drop={drop === column.id || undefined}
              className={cn(
                "relative flex h-full shrink-0 items-center gap-1 px-2 text-xs font-medium text-muted-foreground select-none",
                ACTIVE_RING,
                column.align === "end" && "justify-end text-end",
                column.sortable &&
                  onSort &&
                  "cursor-pointer hover:text-foreground",
                pinned(column.id) &&
                  "sticky z-(--layer-grid-head-sticky) bg-background",
                pinnedEdge(column.id),
                "data-[drop]:shadow-[inset_var(--selection-edge)_0_0_0_var(--ring)] forced-colors:data-[drop]:outline-[Highlight] forced-colors:data-[drop]:outline-solid",
              )}
              style={{ width, ...stickyStyle(column.id) }}
              onPointerDown={(event) => {
                moveTo({ key: null, column: column.id });
                if (!column.sticky) startReorder(event, column);
              }}
              onClick={() => {
                if (suppressClick.current) {
                  suppressClick.current = false;
                  return;
                }
                if (column.sortable) onSort?.(column.id);
              }}
            >
              {column.id === firstEnd && moreCue}
              {column.id === lastStart && earlierCue}
              <span className="min-w-0 truncate">
                {layout.byId.get(column.id)?.narrowed &&
                column.narrowHeader !== undefined
                  ? column.narrowHeader
                  : column.header}
              </span>
              {sorted && (
                <Icon
                  name={sorted === "asc" ? "sortAsc" : "sortDesc"}
                  size="xs"
                />
              )}
              {column.resizable !== false && (
                <div
                  role="separator"
                  aria-orientation="vertical"
                  aria-valuemin={column.minWidth ?? MIN_COLUMN_REM}
                  aria-valuemax={Math.max(100, Math.ceil(width / remPx))}
                  aria-valuenow={Math.round((width / remPx) * 4) / 4}
                  className="absolute inset-y-0 end-0 w-2 cursor-col-resize touch-none after:absolute after:inset-y-1 after:end-0 after:w-px after:bg-border hover:after:bg-ring"
                  onPointerDown={(event) => startResize(event, column)}
                  onClick={(event) => event.stopPropagation()}
                  onDoubleClick={(event) => {
                    event.stopPropagation();
                    fitColumn(column);
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );

  return headerRow;
}
