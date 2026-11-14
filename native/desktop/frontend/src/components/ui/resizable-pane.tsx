import * as React from "react";
import { cn } from "@/components/ui/cn";
import { ResizeHandle } from "@/components/ui/resize-handle";

/** The edge of its row or column the pane is drawn against. */
type PaneEdge = "start" | "end" | "bottom";

type ResizablePaneProps = Omit<React.ComponentProps<"aside">, "children"> & {
  edge: PaneEdge;
  /** The person's size in CSS pixels, or null for `defaultSize`. */
  size: number | null;
  onSize: (size: number | null) => void;
  /** The size the pane opens at, and returns to on reset, in CSS pixels. */
  defaultSize: number;
  /** The least and the most the pane takes, in CSS pixels. */
  min: number;
  max: number;
  /** The most of its container the pane takes, 0 to 1, so the area beside
   * it keeps the rest at any window size. */
  maxShare: number;
  /** The least the rest of the container keeps, in CSS pixels; on a short
   * container the pane gives way to it. */
  keep?: number;
  /** Classes for the pane's frame, the box that holds the separator and the
   * pane, as its container places it. */
  boxClassName?: string;
  /** What the separator is called for assistive technology. */
  handleLabel: string;
  /** A keyboard nudge, in CSS pixels. */
  step?: number;
  children: React.ReactNode;
};

const DEFAULT_STEP = 24;

const clampTo = (value: number, low: number, high: number) =>
  Math.round(Math.max(low, Math.min(high, value)));

/** The size drawn for `wanted`, inside the pane's bounds and its share of a
 * container `room` long, or of no container while it is still unmeasured.
 * The share wins over the least, so a short window keeps the area beside the
 * pane. */
export function fittedPaneSize(
  wanted: number,
  bounds: { min: number; max: number; maxShare: number; keep?: number },
  room: number | null,
): number {
  const most =
    room === null
      ? bounds.max
      : Math.max(
          0,
          Math.min(
            bounds.max,
            room * bounds.maxShare,
            room - (bounds.keep ?? 0),
          ),
        );
  return clampTo(wanted, Math.min(bounds.min, most), most);
}

/**
 * A pane at one edge of a row or a column, drawn at a size the person sets
 * with its separator: dragged with a pointer, moved with the arrow keys,
 * Home and End for its least and most, Enter or a double click for its
 * default. The pane is held between its least and its most and never takes
 * more than its share of the container, which it measures as the window
 * changes. It reports a size; keeping it is the caller's.
 */
function ResizablePane({
  edge,
  size,
  onSize,
  defaultSize,
  min,
  max,
  maxShare,
  keep,
  boxClassName,
  handleLabel,
  step = DEFAULT_STEP,
  className,
  id,
  children,
  ...props
}: ResizablePaneProps) {
  const box = React.useRef<HTMLDivElement>(null);
  const generated = React.useId();
  const paneId = id ?? generated;
  const across = edge === "bottom";
  const [room, setRoom] = React.useState<number | null>(null);
  React.useLayoutEffect(() => {
    const container = box.current?.parentElement;
    if (!container) return;
    const measure = () =>
      setRoom(across ? container.clientHeight : container.clientWidth);
    const observer = new ResizeObserver(measure);
    observer.observe(container);
    measure();
    return () => observer.disconnect();
  }, [across]);

  const bounds = { min, max, maxShare, keep };
  const drawn = fittedPaneSize(size ?? defaultSize, bounds, room);
  const most = fittedPaneSize(Infinity, bounds, room);
  const least = fittedPaneSize(0, bounds, room);
  const set = (next: number) => onSize(fittedPaneSize(next, bounds, room));
  // Moving the line toward the start grows a pane drawn against the end.
  const grows = edge === "start" ? 1 : -1;
  const value = most > least ? ((drawn - least) / (most - least)) * 100 : 100;

  const handle = (
    <ResizeHandle
      orientation={across ? "horizontal" : "vertical"}
      aria-label={handleLabel}
      aria-controls={paneId}
      data-pane-edge={edge}
      value={value}
      onDrag={({ x, y }) => {
        const rect = box.current?.getBoundingClientRect();
        if (!rect) return;
        set(
          edge === "start"
            ? x - rect.left
            : edge === "end"
              ? rect.right - x
              : rect.bottom - y,
        );
      }}
      onStep={(direction) => set(drawn + grows * direction * step)}
      onLimit={(limit) => set(limit === "min" ? 0 : Infinity)}
      onReset={() => onSize(null)}
    />
  );

  return (
    <div
      ref={box}
      data-slot="resizable-pane"
      data-pane-edge={edge}
      className={cn(
        "flex min-h-0 min-w-0 shrink-0",
        across ? "flex-col" : "flex-row",
        boxClassName,
      )}
      style={across ? { height: drawn } : { width: drawn }}
    >
      {edge !== "start" && handle}
      <aside
        id={paneId}
        className={cn("flex min-h-0 min-w-0 flex-1 flex-col", className)}
        {...props}
      >
        {children}
      </aside>
      {edge === "start" && handle}
    </div>
  );
}

export { ResizablePane, type PaneEdge, type ResizablePaneProps };
