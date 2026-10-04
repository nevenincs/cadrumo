import {
  useRef,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";

// A keyboard nudge moves the ratio by a fixed share of the pane, not a pixel
// amount: there is no equivalent length token, since the split has no fixed
// size to derive pixels from.
const KEYBOARD_RESIZE_STEP = 0.03;

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

// Two panes and a separator. Pane DOM positions never change: swapping and
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
      : 1000;
    const low = Math.min(0.5, minA / size);
    const high = Math.max(0.5, 1 - minB / size);
    return Math.max(low, Math.min(high, value));
  };

  const drag = (event: ReactPointerEvent) => {
    if (!box.current) return;
    event.preventDefault();
    const rect = box.current.getBoundingClientRect();
    const dragging = horizontal ? "dragging-x" : "dragging-y";
    document.body.classList.add(dragging);
    const move = (e: PointerEvent) => {
      const at = horizontal
        ? (e.clientX - rect.left) / rect.width
        : (e.clientY - rect.top) / rect.height;
      onRatio(clamp(reversed ? 1 - at : at));
    };
    const up = () => {
      document.body.classList.remove(dragging);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const both = aShown && bShown;
  const shareA = !aShown ? 0 : bShown ? ratio : 1;
  const towardStart = horizontal ? "ArrowLeft" : "ArrowUp";
  const towardEnd = horizontal ? "ArrowRight" : "ArrowDown";
  const step = reversed ? -KEYBOARD_RESIZE_STEP : KEYBOARD_RESIZE_STEP;

  return (
    <div ref={box} className={`split split-${orientation}`}>
      <div
        className="split-pane"
        style={{ flexBasis: `${shareA * 100}%`, order: reversed ? 2 : 0 }}
        hidden={!aShown}
      >
        {a}
      </div>
      <div
        className="split-separator"
        style={{ order: 1 }}
        role="separator"
        aria-orientation={horizontal ? "vertical" : "horizontal"}
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(ratio * 100)}
        tabIndex={both ? 0 : -1}
        hidden={!both}
        onPointerDown={drag}
        onDoubleClick={() => onRatio(0.5)}
        onKeyDown={(e) => {
          if (e.key === towardStart) onRatio(clamp(ratio - step));
          else if (e.key === towardEnd) onRatio(clamp(ratio + step));
          else return;
          e.preventDefault();
        }}
      />
      <div
        className="split-pane"
        style={{ flexBasis: `${(1 - shareA) * 100}%`, order: reversed ? 0 : 2 }}
        hidden={!bShown}
      >
        {b}
      </div>
    </div>
  );
}
