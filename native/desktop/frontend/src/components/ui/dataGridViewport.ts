import * as React from "react";
import { lengthPx, prefixSums } from "./dataGridModel";
import type { DataGridProps, GridRow } from "./dataGridTypes";

function rootRemPx(): number {
  return parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
}

const ROW_HEIGHT = {
  compact: "--spacing-row-compact",
  comfortable: "--spacing-row-comfortable",
} as const;

/** Measures the grid and anchors variable rows while its viewport changes. */
export function useGridViewport<R>({
  scroller,
  header,
  rows,
  rowHeight,
  density,
  index,
}: {
  scroller: React.RefObject<HTMLDivElement | null>;
  header: React.RefObject<HTMLDivElement | null>;
  rows: readonly GridRow<R>[];
  rowHeight: DataGridProps<R>["rowHeight"];
  density: NonNullable<DataGridProps<R>["density"]>;
  index: ReadonlyMap<string, number>;
}) {
  const [view, setView] = React.useState({
    top: 0,
    left: 0,
    height: 0,
    width: 0,
  });
  const [remPx, setRemPx] = React.useState(16);
  const [rowPx, setRowPx] = React.useState(28);
  const [headerPx, setHeaderPx] = React.useState(28);
  const [measuredVersion, setMeasuredVersion] = React.useState(0);
  const measured = React.useRef(new Map<string, number>());
  // What the window needs in pixels: the rem, and the density's row height,
  // read from the tokens on the grid itself so a coarse pointer's taller
  // rows reach the arithmetic too.
  const readMetrics = React.useCallback(() => {
    const element = scroller.current;
    if (!element) return;
    const rem = rootRemPx();
    setRemPx(rem);
    const raw = getComputedStyle(element).getPropertyValue(ROW_HEIGHT[density]);
    const px = lengthPx(raw, rem);
    if (px) setRowPx(px);
    if (header.current) setHeaderPx(header.current.offsetHeight);
  }, [density, header, scroller]);

  const syncView = React.useCallback(() => {
    const element = scroller.current;
    if (!element) return;
    setView({
      top: element.scrollTop,
      left: element.scrollLeft,
      height: element.clientHeight,
      width: element.clientWidth,
    });
  }, [scroller]);

  React.useLayoutEffect(() => {
    const element = scroller.current;
    if (!element) return;
    readMetrics();
    syncView();
    const observer = new ResizeObserver(() => {
      readMetrics();
      syncView();
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [readMetrics, syncView, scroller]);

  const frame = React.useRef(0);
  // The tooltip for cut-short text is laid over its cell where it opened.
  const clearTip = React.useRef<(() => void) | null>(null);
  const onScroll = () => {
    clearTip.current?.();
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(syncView);
  };
  React.useEffect(() => () => cancelAnimationFrame(frame.current), []);

  const heights = React.useMemo(() => {
    void measuredVersion;
    return rows.map((row) => {
      const declared = rowHeight ? rowHeight(row) : undefined;
      if (declared !== undefined) return declared * remPx;
      if (!rowHeight && row.kind !== "custom") return rowPx;
      return measured.current.get(row.key) ?? rowPx;
    });
  }, [rows, rowHeight, remPx, rowPx, measuredVersion]);
  const tops = React.useMemo(() => prefixSums(heights), [heights]);
  const topsRef = React.useRef(tops);
  topsRef.current = tops;
  const indexRef = React.useRef(index);
  indexRef.current = index;

  const needsMeasure = (row: GridRow<R>) =>
    rowHeight ? rowHeight(row) === undefined : row.kind === "custom";

  // A row measured for the first time, or again after it changed, keeps
  // what is above the view where it was: the scroll moves by the change.
  const observer = React.useRef<ResizeObserver | null>(null);
  const measureRef = React.useCallback(
    (element: HTMLDivElement | null) => {
      if (!element) return;
      observer.current ??= new ResizeObserver((entries) => {
        let changed = false;
        for (const entry of entries) {
          const target = entry.target as HTMLElement;
          const key = target.dataset.key;
          if (key === undefined) continue;
          const height =
            entry.borderBoxSize[0]?.blockSize ?? target.offsetHeight;
          const before = measured.current.get(key);
          if (before === height) continue;
          measured.current.set(key, height);
          changed = true;
          const at = indexRef.current.get(key);
          const box = scroller.current;
          if (at !== undefined && box && before !== undefined) {
            const top = topsRef.current[at] ?? 0;
            if (top < box.scrollTop) box.scrollTop += height - before;
          }
        }
        if (changed) setMeasuredVersion((version) => version + 1);
      });
      const watcher = observer.current;
      watcher.observe(element);
      return () => watcher.unobserve(element);
    },
    [scroller],
  );
  React.useEffect(() => () => observer.current?.disconnect(), []);

  return {
    view,
    remPx,
    headerPx,
    heights,
    tops,
    needsMeasure,
    measureRef,
    syncView,
    clearTip,
    onScroll,
  };
}
