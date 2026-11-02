import type * as React from "react";
import type { ColumnLayout } from "./dataGridModel";
import type { GridColumn } from "./dataGridTypes";
import { cn } from "./cn";

// A cell that is the active one wears the ring inside its own edge: ink
// while the grid holds focus, the secondary text colour while it does not.
export const ACTIVE_RING =
  "outline-none data-[active]:outline-(length:--focus-ring) data-[active]:outline-offset-[calc(-1*var(--focus-ring))] data-[active]:outline-muted-foreground data-[active]:outline-solid data-[active]:focus-within:outline-ring";

// A sticky cell hides what scrolls under it, so it takes the grid's surface
// and lays the row's wash over it.
export const STICKY_CELL =
  "sticky z-(--layer-grid-sticky) bg-background group-hover/row:group-not-data-[selected]/row:[background-image:linear-gradient(var(--accent),var(--accent))] group-data-[selected]/row:[background-image:linear-gradient(var(--selected),var(--selected))]";

export const CELL = cn(
  "relative flex h-full shrink-0 items-center overflow-hidden px-2",
  ACTIVE_RING,
  "data-[in-range]:[&_.text-faint]:text-muted-foreground",
  "forced-colors:data-[in-range]:outline-(length:--hairline) forced-colors:data-[in-range]:outline-offset-[calc(-1*var(--hairline))] forced-colors:data-[in-range]:outline-[Highlight] forced-colors:data-[in-range]:outline-solid",
);

// The first cell carries the selected row's bar on its leading edge.
export const LEADING_EDGE =
  "before:absolute before:inset-y-0 before:start-0 before:w-(--selection-edge) before:bg-brand before:opacity-0 group-data-[selected]/row:before:opacity-100 forced-colors:before:bg-[Highlight] forced-colors:before:forced-color-adjust-none";

export const ROW = cn(
  "group/row absolute start-0 flex border-b border-border",
  "hover:not-data-[selected]:bg-accent data-[selected]:bg-selected",
  // Faint text has no contrast to spare on a wash.
  "hover:[&_.text-faint]:text-muted-foreground data-[selected]:[&_.text-faint]:text-muted-foreground",
  "forced-colors:data-[selected]:outline-(length:--selection-edge) forced-colors:data-[selected]:outline-offset-[calc(-1*var(--selection-edge))] forced-colors:data-[selected]:outline-[Highlight] forced-colors:data-[selected]:outline-solid",
);

// The edges of a range, drawn inside each cell that is on them.
export function rangeShadow(
  top: boolean,
  bottom: boolean,
  start: boolean,
  end: boolean,
) {
  const ink = "var(--foreground)";
  const edges = [
    top && `inset 0 var(--hairline) 0 0 ${ink}`,
    bottom && `inset 0 calc(-1 * var(--hairline)) 0 0 ${ink}`,
    start && `inset var(--hairline) 0 0 0 ${ink}`,
    end && `inset calc(-1 * var(--hairline)) 0 0 0 ${ink}`,
  ].filter(Boolean);
  return edges.length ? edges.join(", ") : undefined;
}

export function gridColumnPresentation<R>(
  ordered: readonly GridColumn<R>[],
  layout: ColumnLayout,
  view: { left: number; width: number },
) {
  // Where columns scroll under a pinned group, the group's inner edge shows,
  // so nothing seems to begin mid-word.
  const pinned = (id: string) => layout.byId.get(id)?.sticky;
  const lastStart = layout.boxes
    .filter((placed) => placed.sticky === "start")
    .at(-1)?.id;
  const firstEnd = layout.boxes.find((placed) => placed.sticky === "end")?.id;
  const pinnedEdge = (id: string) =>
    cn(
      id === lastStart && view.left > 0 && "border-e border-border",
      id === firstEnd &&
        view.left + view.width < layout.total - 1 &&
        "border-s border-border",
    );
  const stickyStyle = (id: string): React.CSSProperties => {
    const placed = layout.byId.get(id);
    if (!placed?.sticky) return {};
    return placed.sticky === "start"
      ? { insetInlineStart: placed.inset }
      : { insetInlineEnd: placed.inset };
  };
  // These depend on the column and layout, not the row. Build them once
  // rather than merging the same classes for every visible cell.
  const cellPresentation = ordered.map((column, position) => ({
    className: cn(
      CELL,
      position === 0 && LEADING_EDGE,
      column.align === "end" && "justify-end text-end tabular-nums",
      pinned(column.id) && STICKY_CELL,
      pinnedEdge(column.id),
    ),
    width: layout.byId.get(column.id)?.width,
    sticky: stickyStyle(column.id),
  }));

  return {
    pinned,
    lastStart,
    firstEnd,
    pinnedEdge,
    stickyStyle,
    cellPresentation,
  };
}
