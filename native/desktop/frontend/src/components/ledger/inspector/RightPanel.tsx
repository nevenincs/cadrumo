import {
  useContext,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type Ref,
} from "react";
import { ResizeHandle } from "@/components/ui/resize-handle";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { useStrings } from "../../../shell/strings";
import { GridRoomContext } from "../gridRoom";

/** What the panel beside the grid shows: the pair queue of the To match
 * view, or the inspector of the selected movements. */
export type RightPanelMode = "match" | "movement";

/** A keyboard nudge, and the least the panel and the grid keep, in rem. */
const STEP_REM = 1.5;
const MIN_REM = 17.5;
/** The token's width, which a reset returns to. */
const DEFAULT_REM = 20;
const GRID_MIN_REM = 40;
/** The most of the window the panel takes. */
const MAX_SHARE = 0.6;

const remPx = () =>
  parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;

/** The least the grid's column keeps beside the panel, in CSS pixels: its
 * own, or more where the grid needs it to show a scrolling column whole. */
const columnLeast = (columnFloor: number | null, rem: number) =>
  Math.max(GRID_MIN_REM * rem, columnFloor ?? 0);

/** The least the row takes, in CSS pixels: the grid's column at its least,
 * and with the panel open, the panel at its least and the separator's line
 * between them. */
export const rowFloor = (columnFloor: number | null, withPanel: boolean) => {
  const rem = remPx();
  const column = columnLeast(columnFloor, rem);
  return Math.ceil(withPanel ? column + MIN_REM * rem + 1 : column);
};

/** The width the panel is drawn at, in CSS pixels: the person's, or the
 * token's, narrowed toward its least where the row would otherwise leave the
 * grid less than its own. Null keeps the token's width. */
export function fittedPanelWidth(
  width: number | null,
  room: number | null,
  rem: number,
  columnFloor: number | null = null,
  defaultRem: number = DEFAULT_REM,
): number | null {
  const wanted = width ?? defaultRem * rem;
  if (room === null) return width;
  const fitted = Math.max(
    MIN_REM * rem,
    Math.min(wanted, room - columnLeast(columnFloor, rem)),
  );
  return fitted === wanted ? width : Math.round(fitted);
}

/**
 * The one panel beside the ledger's grid, in two modes: "To match" and
 * "Movement", so only one side panel is ever open. It is resized by its
 * separator, with a pointer or the arrow keys, between its least width and
 * what leaves the grid its own; the width is the person's presentation,
 * kept with the layout. Where the row is short it opens narrower, down to
 * its least, so the grid keeps its own width as far as it can.
 */
export function RightPanel({
  mode,
  onMode,
  matchPanel,
  width,
  onWidth,
  panelRef,
  onKeyDown,
  defaultRem = DEFAULT_REM,
  children,
}: {
  mode: RightPanelMode;
  onMode: (mode: RightPanelMode) => void;
  /** The To match pair queue; without one the panel has one mode. */
  matchPanel?: ReactNode;
  /** In CSS pixels; null keeps the token's width. */
  width: number | null;
  onWidth: (width: number | null) => void;
  panelRef?: Ref<HTMLElement>;
  onKeyDown?: (event: KeyboardEvent<HTMLElement>) => void;
  /** The width, in rem, the panel opens at and a reset returns to, where
   * its content needs more than the token's; it is still held to the least
   * and the most the panel keeps. */
  defaultRem?: number;
  /** The movement inspector. */
  children: ReactNode;
}) {
  const t = useStrings();
  const { columnFloor } = useContext(GridRoomContext);
  const aside = useRef<HTMLElement | null>(null);
  // What the row leaves the grid and the panel: its width less the
  // separator's.
  const [room, setRoom] = useState<number | null>(null);
  useLayoutEffect(() => {
    const element = aside.current;
    const row = element?.parentElement;
    if (!element || !row) return;
    const measure = () => {
      const separator = element.previousElementSibling;
      setRoom(
        row.clientWidth -
          (separator instanceof HTMLElement ? separator.offsetWidth : 0),
      );
    };
    const observer = new ResizeObserver(measure);
    observer.observe(row);
    measure();
    return () => observer.disconnect();
  }, []);
  const limits = () => {
    const rem = remPx();
    const row = aside.current?.parentElement?.clientWidth ?? window.innerWidth;
    const min = MIN_REM * rem;
    const max = Math.max(
      min,
      Math.min(
        window.innerWidth * MAX_SHARE,
        row - columnLeast(columnFloor, rem),
      ),
    );
    return { min, max, rem };
  };
  const clamp = (next: number) => {
    const { min, max } = limits();
    return Math.round(Math.max(min, Math.min(max, next)));
  };
  const current = () => aside.current?.offsetWidth ?? limits().min;
  const shown =
    matchPanel !== undefined && mode === "match" ? "match" : "movement";
  // Where the line stands, for assistive technology: between the least
  // width and the most of the window the panel may take.
  const rem = remPx();
  const least = MIN_REM * rem;
  const most = Math.max(least, window.innerWidth * MAX_SHARE);
  const fitted = fittedPanelWidth(width, room, rem, columnFloor, defaultRem);
  const drawn = fitted ?? defaultRem * rem;
  const value = Math.max(
    0,
    Math.min(100, ((drawn - least) / (most - least || 1)) * 100),
  );

  return (
    <>
      <ResizeHandle
        orientation="vertical"
        className="ledger-panel-resize"
        aria-label={t("desktop.ledger.inspector.resize")}
        value={value}
        onDrag={({ x }) => {
          const right = aside.current?.getBoundingClientRect().right ?? x;
          onWidth(clamp(right - x));
        }}
        onStep={(direction) =>
          // The panel sits at the end: moving the line left widens it.
          onWidth(clamp(current() - direction * STEP_REM * limits().rem))
        }
        onLimit={(limit) =>
          onWidth(limit === "min" ? clamp(0) : clamp(Infinity))
        }
        onReset={() => onWidth(null)}
      />
      <aside
        ref={(element) => {
          aside.current = element;
          if (typeof panelRef === "function") panelRef(element);
          else if (panelRef) panelRef.current = element;
        }}
        aria-label={
          shown === "match"
            ? t("desktop.ledger.inspector.panel_match")
            : t("desktop.ledger.inspector.panel")
        }
        data-mode={shown}
        className="ledger-panel flex min-h-0 w-inspector min-w-inspector-min shrink-0 flex-col bg-background"
        style={
          fitted !== null
            ? { width: `${fitted}px` }
            : defaultRem !== DEFAULT_REM
              ? { width: `${defaultRem}rem` }
              : undefined
        }
        onKeyDown={onKeyDown}
      >
        {matchPanel !== undefined && (
          <div className="border-b px-3 py-2">
            <SegmentedControl
              aria-label={t("desktop.ledger.inspector.mode")}
              value={shown}
              onValueChange={(next) => onMode(next as RightPanelMode)}
            >
              <SegmentedControlItem value="match">
                {t("desktop.ledger.inspector.mode_match")}
              </SegmentedControlItem>
              <SegmentedControlItem value="movement">
                {t("desktop.ledger.inspector.mode_movement")}
              </SegmentedControlItem>
            </SegmentedControl>
          </div>
        )}
        {shown === "match" ? matchPanel : children}
      </aside>
    </>
  );
}
