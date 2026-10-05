import * as React from "react";
import { cn } from "@/components/ui/cn";

type ResizeHandleProps = Omit<
  React.ComponentProps<"div">,
  "onDrag" | "onDragEnd" | "onDragStart" | "role"
> & {
  /** The line's own direction: a `vertical` handle sits between columns. */
  orientation: "horizontal" | "vertical";
  /** Called with the pointer's viewport position while it drags. */
  onDrag: (point: { x: number; y: number }) => void;
  onDragStart?: () => void;
  onDragEnd?: () => void;
  /** Arrow keys: -1 toward the start, 1 toward the end. */
  onStep: (direction: -1 | 1) => void;
  /** Home and End: the smallest and the largest size. */
  onLimit?: (limit: "min" | "max") => void;
  /** Double click or double tap: back to the default. */
  onReset?: () => void;
  /** The current position, 0 to 100, for assistive technology. */
  value: number;
};

/**
 * The line between two resizable areas, as a window splitter: a focusable
 * separator that reports its position, dragged with a mouse, a pen or a
 * finger and moved with the arrow keys. The line is a hairline; the area that
 * takes the pointer is wider, and wider still for a coarse pointer.
 *
 * While it drags it captures the pointer, so the drag continues over a frame
 * or a terminal, and it marks the document so nothing underneath selects text
 * or shows another cursor.
 */
function ResizeHandle({
  orientation,
  onDrag,
  onDragStart,
  onDragEnd,
  onStep,
  onLimit,
  onReset,
  value,
  className,
  ...props
}: ResizeHandleProps) {
  const [dragging, setDragging] = React.useState(false);
  const vertical = orientation === "vertical";

  React.useEffect(() => {
    if (!dragging) return;
    document.body.dataset.resizing = orientation;
    return () => {
      delete document.body.dataset.resizing;
    };
  }, [dragging, orientation]);

  const finish = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    setDragging(false);
    onDragEnd?.();
  };

  return (
    <div
      data-slot="resize-handle"
      data-dragging={dragging || undefined}
      role="separator"
      aria-orientation={orientation}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(value)}
      tabIndex={0}
      className={cn(
        "relative z-(--layer-separator) shrink-0 touch-none bg-border-strong transition-colors",
        "hover:bg-ring focus-visible:bg-ring data-[dragging]:bg-ring",
        // The hairline is the visible line; this is what takes the pointer.
        "after:absolute after:content-['']",
        vertical
          ? "w-px cursor-col-resize after:inset-y-0 after:-inset-x-1 pointer-coarse:after:-inset-x-3"
          : "h-px cursor-row-resize after:inset-x-0 after:-inset-y-1 pointer-coarse:after:-inset-y-3",
        className,
      )}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
        event.currentTarget.focus();
        setDragging(true);
        onDragStart?.();
      }}
      onPointerMove={(event) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId))
          onDrag({ x: event.clientX, y: event.clientY });
      }}
      onPointerUp={finish}
      onPointerCancel={finish}
      onDoubleClick={onReset}
      onKeyDown={(event) => {
        const back = vertical ? "ArrowLeft" : "ArrowUp";
        const forward = vertical ? "ArrowRight" : "ArrowDown";
        if (event.key === back) onStep(-1);
        else if (event.key === forward) onStep(1);
        else if (event.key === "Home" && onLimit) onLimit("min");
        else if (event.key === "End" && onLimit) onLimit("max");
        else if (event.key === "Enter" && onReset) onReset();
        else return;
        event.preventDefault();
      }}
      {...props}
    />
  );
}

export { ResizeHandle, type ResizeHandleProps };
