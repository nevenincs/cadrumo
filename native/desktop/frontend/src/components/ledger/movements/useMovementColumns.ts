import { useEffect, useMemo, useState, type RefObject } from "react";
import type { LedgerView } from "../../../shell/layout";
import { draftedWidth } from "../editing/editingModel";
import {
  COLUMN_SPECS,
  columnLayout,
  dateWidth,
  presetOf,
  shownColumns,
  statusWidth,
  type ColumnId,
} from "./movementsModel";

/**
 * The movement columns as drawn: the person's layout and widths in rem, and
 * the order the grid draws. Where the review preset the page starts from
 * does not fit, it gives up Group before Category, and the columns menu
 * shows Group as hidden, so showing it there draws it. A layout the person
 * made is drawn as made.
 */
export function useMovementColumns({
  view,
  within,
  marks,
  withYear,
  drafting,
}: {
  view: LedgerView;
  /** The section's element, whose width is the room the columns have. */
  within: RefObject<HTMLDivElement | null>;
  /** The status column's marks, which set its natural width. */
  marks: number;
  /** Dates carry their year, the window spanning periods. */
  withYear: boolean;
  /** New movements are drawn, which widen the columns they edit. */
  drafting: boolean;
}) {
  const layout = useMemo(() => columnLayout(view.columns), [view.columns]);
  const remPx =
    typeof document === "undefined"
      ? 16
      : parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
  const widths = useMemo(() => {
    const out: Record<string, number> = {};
    for (const [column, px] of Object.entries(view.columns.widths))
      out[column] = px / remPx;
    return out;
  }, [view.columns.widths, remPx]);
  const [room, setRoom] = useState<number | null>(null);
  useEffect(() => {
    const element = within.current;
    if (!element) return;
    const observer = new ResizeObserver(() => setRoom(element.clientWidth));
    observer.observe(element);
    setRoom(element.clientWidth);
    return () => observer.disconnect();
  }, [within]);
  const untouched = view.columns.order.length === 0;
  const narrow = useMemo(() => {
    if (room === null || !untouched || presetOf(layout) !== "review")
      return false;
    const needed = shownColumns(layout).reduce((sum, column) => {
      const spec = COLUMN_SPECS[column];
      const natural =
        column === "status"
          ? statusWidth(view.density, marks)
          : column === "date"
            ? dateWidth(withYear)
            : Math.max(spec.width, spec.minWidth ?? 0);
      const rem =
        widths[column] ?? (drafting ? draftedWidth(column, natural) : natural);
      return sum + rem * remPx;
    }, 0);
    return needed > room;
  }, [
    layout,
    untouched,
    room,
    widths,
    view.density,
    marks,
    withYear,
    remPx,
    drafting,
  ]);
  const drawnLayout = useMemo(
    () =>
      narrow
        ? {
            ...layout,
            hidden: new Set<ColumnId>([...layout.hidden, "group_label"]),
          }
        : layout,
    [layout, narrow],
  );
  const order = useMemo(() => shownColumns(drawnLayout), [drawnLayout]);
  return { layout, remPx, widths, drawnLayout, order };
}
