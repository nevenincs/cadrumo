import * as React from "react";
import { cn } from "@/components/ui/cn";
import { ResizeHandle } from "@/components/ui/resize-handle";
import { useScrolls } from "@/components/ui/useScrolls";

/** The edge of its row or column the pane is drawn against. */
type PaneEdge = "start" | "end" | "top" | "bottom";

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

/** How each edge lays out: across the container (a height) or along it (a
 * width), whether the pane is drawn before its line, and which way moving
 * the line toward the start grows it. */
type EdgeLayout = {
  across: boolean;
  leads: boolean;
  grows: 1 | -1;
  orientation: "horizontal" | "vertical";
  length: "height" | "width";
  flow: string;
};
const ALONG = {
  across: false,
  orientation: "vertical",
  length: "width",
  flow: "flex-row",
} as const;
const ACROSS = {
  across: true,
  orientation: "horizontal",
  length: "height",
  flow: "flex-col",
} as const;
const EDGES: Record<PaneEdge, EdgeLayout> = {
  start: { ...ALONG, leads: true, grows: 1 },
  end: { ...ALONG, leads: false, grows: -1 },
  top: { ...ACROSS, leads: true, grows: 1 },
  bottom: { ...ACROSS, leads: false, grows: -1 },
};

const LIMITS = { min: 0, max: Infinity } as const;

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

/** The length of the container `box` sits in, across or along, as the
 * window changes; null until it is measured. */
function useContainerRoom(
  box: React.RefObject<HTMLDivElement | null>,
  across: boolean,
): number | null {
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
  }, [box, across]);
  return room;
}

/** The size drawn for `wanted`, where it stands between the least and the
 * most as 0 to 100, and whether the line can move a whole `step`; a line
 * that cannot is not offered as a control. */
function paneTravel(
  wanted: number,
  bounds: Parameters<typeof fittedPaneSize>[1],
  room: number | null,
  step: number,
) {
  const drawn = fittedPaneSize(wanted, bounds, room);
  const most = fittedPaneSize(Infinity, bounds, room);
  const least = fittedPaneSize(0, bounds, room);
  return {
    drawn,
    value: most > least ? ((drawn - least) / (most - least)) * 100 : 100,
    movable: most - least >= step,
  };
}

/** The size a drag to `point` gives a pane drawn against `edge` of `rect`. */
function dragged(
  edge: PaneEdge,
  rect: DOMRect,
  point: { x: number; y: number },
): number {
  if (edge === "start") return point.x - rect.left;
  if (edge === "end") return rect.right - point.x;
  if (edge === "top") return point.y - rect.top;
  return rect.bottom - point.y;
}

/**
 * A pane at one edge of a row or a column, drawn at a size the person sets
 * with its separator: dragged with a pointer, moved with the arrow keys,
 * Home and End for its least and most, Enter or a double click for its
 * default. The pane is held between its least and its most and never takes
 * more than its share of the container, which it measures as the window
 * changes; where that leaves its line less than one step of travel, the line
 * is not drawn. It reports a size; keeping it is the caller's.
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
  const [pane, setPane] = React.useState<HTMLElement | null>(null);
  const scrolls = useScrolls(pane);
  const generated = React.useId();
  const paneId = id ?? generated;
  const { across, leads, grows, orientation, length, flow } = EDGES[edge];
  const room = useContainerRoom(box, across);
  const bounds = { min, max, maxShare, keep };
  const { drawn, value, movable } = paneTravel(
    size ?? defaultSize,
    bounds,
    room,
    step,
  );
  const set = (next: number) => onSize(fittedPaneSize(next, bounds, room));

  const handle = (
    <ResizeHandle
      orientation={orientation}
      aria-label={handleLabel}
      aria-controls={paneId}
      data-pane-edge={edge}
      value={value}
      onDrag={(point) => {
        const rect = box.current?.getBoundingClientRect();
        if (rect) set(dragged(edge, rect, point));
      }}
      onStep={(direction) => set(drawn + grows * direction * step)}
      onLimit={(limit) => set(LIMITS[limit])}
      onReset={() => onSize(null)}
    />
  );

  return (
    <div
      ref={box}
      data-slot="resizable-pane"
      data-pane-edge={edge}
      className={cn("flex min-h-0 min-w-0 shrink-0", flow, boxClassName)}
      style={{ [length]: drawn }}
    >
      {!leads && movable && handle}
      <aside
        ref={setPane}
        id={paneId}
        // A pane that scrolls is a Tab stop, so the arrows and the Page keys
        // move it without the pointer; it keeps the name it was given.
        tabIndex={scrolls ? 0 : undefined}
        className={cn(
          "flex min-h-0 min-w-0 flex-1 flex-col",
          scrolls &&
            "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
          className,
        )}
        {...props}
      >
        {children}
      </aside>
      {leads && movable && handle}
    </div>
  );
}

export { ResizablePane, type PaneEdge, type ResizablePaneProps };
