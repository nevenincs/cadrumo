import { useRef, type ReactNode } from "react";
import { cn } from "@/components/ui/cn";
import { ResizeHandle } from "@/components/ui/resize-handle";

// A keyboard nudge moves the ratio by a fixed share of the pane, not a length:
// the split has no fixed size to derive one from.
const KEYBOARD_RESIZE_STEP = 0.03;
const DEFAULT_RATIO = 0.5;

type Props = {
  orientation: "row" | "column";
  /** Show pane B first. */
  reversed: boolean;
  /** Pane A's share, 0..1, so a remembered split survives window resizes. */
  ratio: number;
  onRatio: (ratio: number) => void;
  minA: number;
  minB: number;
  a: ReactNode;
  b: ReactNode;
  aShown: boolean;
  bShown: boolean;
  label: string;
};

// Two panes and a handle. Pane DOM positions never change: swapping and
// hiding use CSS `order` and `hidden`, so neither the docs frame nor a live
// terminal is ever remounted.
export function Split({
  orientation,
  reversed,
  ratio,
  onRatio,
  minA,
  minB,
  a,
  b,
  aShown,
  bShown,
  label,
}: Props) {
  const box = useRef<HTMLDivElement>(null);
  const horizontal = orientation === "row";

  const clamp = (value: number) => {
    const size = box.current
      ? horizontal
        ? box.current.clientWidth
        : box.current.clientHeight
      : 0;
    if (size <= 0) return value;
    const low = Math.min(DEFAULT_RATIO, minA / size);
    const high = Math.max(DEFAULT_RATIO, 1 - minB / size);
    return Math.max(low, Math.min(high, value));
  };

  const both = aShown && bShown;
  const shareA = !aShown ? 0 : bShown ? ratio : 1;
  const step = reversed ? -KEYBOARD_RESIZE_STEP : KEYBOARD_RESIZE_STEP;
  const pane =
    "split-pane relative flex min-h-0 min-w-0 shrink grow-0 overflow-hidden";

  return (
    <div
      ref={box}
      className={cn(
        "split flex min-h-0 min-w-0 flex-1",
        horizontal ? "split-row flex-row" : "split-column flex-col",
      )}
    >
      <div
        className={pane}
        style={{ flexBasis: `${shareA * 100}%`, order: reversed ? 2 : 0 }}
        hidden={!aShown}
      >
        {a}
      </div>
      <ResizeHandle
        className="split-separator"
        style={{ order: 1 }}
        orientation={horizontal ? "vertical" : "horizontal"}
        aria-label={label}
        value={ratio * 100}
        tabIndex={both ? 0 : -1}
        hidden={!both}
        onDrag={({ x, y }) => {
          if (!box.current) return;
          const rect = box.current.getBoundingClientRect();
          const at = horizontal
            ? (x - rect.left) / rect.width
            : (y - rect.top) / rect.height;
          onRatio(clamp(reversed ? 1 - at : at));
        }}
        onStep={(direction) => onRatio(clamp(ratio + direction * step))}
        onLimit={(limit) => onRatio(clamp(limit === "min" ? 0 : 1))}
        onReset={() => onRatio(clamp(DEFAULT_RATIO))}
      />
      <div
        className={pane}
        style={{ flexBasis: `${(1 - shareA) * 100}%`, order: reversed ? 0 : 2 }}
        hidden={!bShown}
      >
        {b}
      </div>
    </div>
  );
}
