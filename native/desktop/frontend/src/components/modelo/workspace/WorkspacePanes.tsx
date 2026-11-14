import {
  createContext,
  useContext,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { fittedPaneSize, ResizablePane } from "@/components/ui/resizable-pane";
import type {
  PanePlacement,
  PanePreferenceControl,
} from "../../../shell/panePreference";
import { useStrings } from "../../../shell/strings";

/** The panes around a declaration's form whose presentation the viewer
 * keeps: the To do and Outline rail, and the chosen box's details. */
export type WorkspacePanes = {
  side: PanePreferenceControl;
  details: PanePreferenceControl;
};

/** The names the panes are kept under in the viewer's preferences. */
export const WORKSPACE_PANE_IDS = {
  side: "modelo.workspace.side",
  details: "modelo.workspace.details",
} as const;

// Width in rem at which the rail opens by default.
const RAIL_ROOM_REM = 56;
// Width in rem from which, until the person chooses, the details are drawn
// beside the form rather than under it. It only picks the default: the
// person's choice of arrangement always wins over it.
const DETAILS_BESIDE_REM = 72;
// Each pane's default, least and most in rem, and the most of the form's
// area it takes, so the form keeps the rest at any window size.
const RAIL = { size: 15, min: 10, max: 28, share: 0.4 };
const DETAILS_SIDE = { size: 22, min: 8, max: 40, share: 0.45 };
// Under the form the details open at two fifths of the area and give way to
// the form's least room on a short window.
const DETAILS_BOTTOM = { share: 0.4, min: 6, max: 48, maxShare: 0.6 };
// The room under the form kept for the details however short the window,
// in rem: more than their least, so their line always has room to move.
// Where the window cannot hold it beside the form's least room, the
// workspace scrolls as a whole rather than clipping either.
const DETAILS_BOTTOM_ROOM = 10;
// The least width in rem the form keeps beside the details, so a box's
// label stays readable once its value goes under it. Where the window
// cannot hold it beside the details' least, the details give way to it.
const FORM_BESIDE_LEAST = 15;
// The two separators' hairlines, in CSS pixels.
const HANDLES = 2;
// What a band that gives way keeps of itself before the details give way
// to it, in rem: its first lines stay readable and its controls reachable.
const BAND_KEEP_REM = 6;

const remPx = () =>
  parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;

type PaneDoor = { open: boolean; toggle(): void; controls: string };
const PaneDoors = createContext<{
  side: PaneDoor;
  /** Null where the declaration has no details. */
  details: PaneDoor | null;
  /** Whether the details go beside the form, shown or hidden; null where
   * the declaration has no details. */
  placement: PaneDoor | null;
} | null>(null);

/**
 * The controls that show and hide the panes beside the form and set where
 * the details go, each with its own icon: the rail at the start, the details
 * at the end or under the form, and the line between the form and the
 * details. They stay together and are drawn whatever is shown, so none
 * comes and goes with another's state.
 */
function WorkspacePaneToggles() {
  const doors = useContext(PaneDoors);
  const t = useStrings();
  if (!doors) return null;
  const { side, details, placement } = doors;
  return (
    <div
      role="group"
      aria-label={t("desktop.modelo.panes.label")}
      data-pane-toggles=""
      className="flex flex-none items-center gap-1"
    >
      {/* The rail's control keeps the rail's own name; whether it is shown
          is its pressed state. */}
      <IconButton
        label={t("desktop.modelo.side.label")}
        size="sm"
        aria-pressed={side.open}
        aria-controls={side.open ? side.controls : undefined}
        data-pane-toggle="side"
        onClick={side.toggle}
      >
        <Icon name="panelLeft" />
      </IconButton>
      {details && placement && (
        <DetailsToggles details={details} placement={placement} />
      )}
    </div>
  );
}

/** The details' control, with the icon of where they go, and beside it the
 * control that sets where: beside the form when pressed, under it when not,
 * whether or not the details are shown, so a choice made while they are
 * hidden holds when they are shown. Its icon draws the line as it is. */
function DetailsToggles({
  details,
  placement,
}: {
  details: PaneDoor;
  placement: PaneDoor;
}) {
  const t = useStrings();
  const beside = placement.open;
  const controls = details.open ? details.controls : undefined;
  return (
    <>
      <IconButton
        label={t(
          details.open
            ? "desktop.modelo.details.hide"
            : "desktop.modelo.details.show",
        )}
        size="sm"
        aria-pressed={details.open}
        aria-controls={controls}
        data-pane-toggle="details"
        onClick={details.toggle}
      >
        <Icon name={beside ? "panelRight" : "panelBottom"} />
      </IconButton>
      <IconButton
        label={t("desktop.modelo.details.beside")}
        size="sm"
        aria-pressed={beside}
        aria-controls={controls}
        data-pane-toggle="placement"
        onClick={placement.toggle}
      >
        <Icon name={beside ? "splitBeside" : "splitUnder"} />
      </IconButton>
    </>
  );
}

/** The pane controls, drawn in `place` once the workspace has drawn it. */
function PaneControls({ place }: { place: HTMLElement | null }) {
  return place ? createPortal(<WorkspacePaneToggles />, place) : null;
}

function useBoxSize() {
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ width: number; height: number } | null>(
    null,
  );
  useLayoutEffect(() => {
    const element = box.current;
    if (!element) return;
    const measure = () =>
      setSize({ width: element.clientWidth, height: element.clientHeight });
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    measure();
    return () => observer.disconnect();
  }, []);
  return [box, size] as const;
}

/** What the form column holds against the details under it: its fixed bands
 * and its scroller's least height (`data-modelo-form`), and apart from them
 * the first lines of a band that gives way (`data-form-gives-way`). A band
 * drawn as a resizable pane counts with its frame, so its line coming and
 * going as its room changes moves nothing else. */
type FormLeast = { fixed: number; band: number };

function formLeast(element: HTMLElement, bandKeep: number): FormLeast {
  const scroller = element.querySelector<HTMLElement>("[data-modelo-form]");
  if (!scroller) return { fixed: 0, band: 0 };
  let drawn = 0;
  let band = 0;
  for (const giving of element.querySelectorAll<HTMLElement>(
    "[data-form-gives-way]",
  )) {
    const frame = giving.parentElement;
    drawn += (frame?.dataset.slot === "resizable-pane" ? frame : giving)
      .offsetHeight;
    band += Math.min(giving.scrollHeight, bandKeep);
  }
  const least = parseFloat(getComputedStyle(scroller).minHeight) || 0;
  return {
    fixed: element.scrollHeight - scroller.offsetHeight - drawn + least,
    band,
  };
}

/** The form column's least room, with what is drawn under the details
 * counted as fixed, as the window, the form and the staged bar change. */
function useFormLeast(
  column: RefObject<HTMLDivElement | null>,
  below: RefObject<HTMLDivElement | null>,
): FormLeast {
  const [fixed, setFixed] = useState(0);
  const [band, setBand] = useState(0);
  useLayoutEffect(() => {
    const form = column.current;
    const under = below.current;
    if (!form || !under) return;
    let watched: Element | null = null;
    const measure = () => {
      const scroller = form.querySelector("[data-modelo-form]");
      if (scroller !== watched) {
        if (watched) observer.unobserve(watched);
        if (scroller) observer.observe(scroller);
        watched = scroller;
      }
      const least = formLeast(form, BAND_KEEP_REM * remPx());
      setFixed(Math.ceil(least.fixed + under.offsetHeight));
      setBand(Math.ceil(least.band));
    };
    const observer = new ResizeObserver(measure);
    observer.observe(form);
    observer.observe(under);
    measure();
    return () => observer.disconnect();
  }, [column, below]);
  return { fixed, band };
}

/** `roomy` as first measured, kept while the area stays drawn; null until
 * it is measured. */
function useRoomAtOpening(roomy: boolean | null): boolean | null {
  const [kept, setKept] = useState<boolean | null>(null);
  if (kept === null && roomy !== null) setKept(roomy);
  return kept ?? roomy;
}

type Bounds = { min: number; max: number; maxShare: number; keep?: number };

/** Where the details go for whoever has not chosen: beside the form on a
 * wide area, under it otherwise. */
function automaticPlacement(width: number, rem: number): PanePlacement {
  return width >= DETAILS_BESIDE_REM * rem ? "side" : "bottom";
}

/** What is kept when the person asks for `next`: choosing the arrangement
 * the area would pick anyway hands the choice back to the area. */
function chosenPlacement(
  next: PanePlacement,
  automatic: PanePlacement,
): PanePlacement | null {
  return next === automatic ? null : next;
}

/** The rail's bounds. Beside the details it leaves them their least and the
 * form its least, and takes half of what is left over, so both lines keep
 * room to move on a narrow area. */
function railBounds(rem: number, width: number, beside: boolean): Bounds {
  const bounds = {
    min: RAIL.min * rem,
    max: RAIL.max * rem,
    maxShare: RAIL.share,
  };
  if (!beside) return bounds;
  const others = (DETAILS_SIDE.min + FORM_BESIDE_LEAST) * rem + HANDLES;
  const spare = Math.max(0, width - bounds.min - others);
  return { ...bounds, keep: others + spare / 2 };
}

/** The details' bounds and default in `placement`. Beside the form they
 * leave the rail as drawn and the form its least width; under it, the form
 * keeps `keep`. Where an area cannot hold both, the form's least wins and
 * the details are drawn smaller than their own least, never over the form. */
function detailsBounds(
  placement: PanePlacement,
  rem: number,
  area: { height: number; rail: number; keep: number },
): Bounds & { size: number } {
  if (placement === "side")
    return {
      size: DETAILS_SIDE.size * rem,
      min: DETAILS_SIDE.min * rem,
      max: DETAILS_SIDE.max * rem,
      maxShare: DETAILS_SIDE.share,
      keep: area.rail + FORM_BESIDE_LEAST * rem + HANDLES,
    };
  return {
    size: area.height * DETAILS_BOTTOM.share,
    min: DETAILS_BOTTOM.min * rem,
    max: DETAILS_BOTTOM.max * rem,
    maxShare: DETAILS_BOTTOM.maxShare,
    keep: area.keep,
  };
}

/** The rail's width as drawn in an area `width` wide, or 0 while hidden. */
function railDrawn(
  side: PanePreferenceControl,
  bounds: Bounds,
  open: boolean,
  rem: number,
  width: number,
) {
  return open
    ? fittedPaneSize(side.preference.side ?? RAIL.size * rem, bounds, width)
    : 0;
}

/** Whether the details under the form get their least when the area is
 * first measured; null until it is. */
function roomyUnder(
  least: FormLeast,
  room: { height: number } | null,
  rem: number,
): boolean | null {
  if (least.fixed <= 0 || room === null) return null;
  return room.height - least.fixed - least.band >= DETAILS_BOTTOM.min * rem;
}

/** What the form keeps above the details under it: its fixed bands and
 * least height, then as much of a band that gives way as leaves the
 * details their kept room. */
function keptAbove(least: FormLeast, height: number, kept: number): number {
  return (
    least.fixed + Math.min(least.band, Math.max(0, height - least.fixed - kept))
  );
}

/** Whether the rail is shown and where the details go: as the person chose,
 * or as the area's width suggests. */
function chosenOrAutomatic(panes: WorkspacePanes, width: number, rem: number) {
  const automatic = automaticPlacement(width, rem);
  return {
    sideOpen: panes.side.preference.open ?? width >= RAIL_ROOM_REM * rem,
    automatic,
    placement: panes.details.preference.placement ?? automatic,
  };
}

/** How the form's area is laid out: whether each pane is shown, where the
 * details go and what bounds each pane keeps. */
function useArrangement(
  panes: WorkspacePanes,
  room: { width: number; height: number } | null,
  least: FormLeast,
  hasDetails: boolean,
) {
  const rem = remPx();
  const { width, height } = room ?? {
    width: window.innerWidth,
    height: window.innerHeight,
  };
  const { side, details } = panes;
  const { sideOpen, automatic, placement } = chosenOrAutomatic(
    panes,
    width,
    rem,
  );
  const beside = placement === "side";
  // Under the form, the form's fixed bands and its scroller's least height
  // come first, then the room kept for the details, then the first lines of
  // a band that gives way, then the rest of the details. Too short for the
  // form and that room, the area keeps them and the workspace scrolls as a
  // whole. Opened where the details would get less than their least, they
  // start hidden; a window made shorter later keeps them shown.
  const kept = DETAILS_BOTTOM_ROOM * rem;
  const roomy = useRoomAtOpening(roomyUnder(least, room, rem));
  const detailsOpen =
    hasDetails && (details.preference.open ?? (beside || roomy === true));
  const rail = railBounds(rem, width, detailsOpen && beside);
  const under = detailsOpen && !beside ? kept : 0;
  return {
    rem,
    sideOpen,
    detailsOpen,
    placement,
    automatic,
    rail,
    details: detailsBounds(placement, rem, {
      height,
      rail: railDrawn(side, rail, sideOpen, rem, width),
      keep: keptAbove(least, height, kept),
    }),
    areaLeast: least.fixed > 0 ? least.fixed + under : 0,
  };
}

/**
 * The form view's area: the rail at its start, the form, the details beside
 * it or under it, and the staged-edit bar under the form. Each pane is shown
 * or hidden from the form's toolbar and resized by its separator, in either
 * arrangement of the details.
 *
 * Where the details go is the person's: the toolbar's arrangement control
 * puts them beside the form (a vertical line) or under it (a horizontal
 * line). Whoever has not chosen gets the arrangement the area's width
 * suggests; choosing the one the area would pick anyway hands the choice
 * back to the area, so a second press returns to the automatic arrangement.
 * Each arrangement keeps its own size. All of this is the viewer's
 * presentation, kept by the caller, never a fact about the declaration.
 *
 * The form's least room wins over any arrangement: under the form, the form
 * keeps its bands and its scroller's least height and the details their
 * kept room, and a short window scrolls the workspace as a whole; beside it,
 * the form keeps its least width and the details give way to it. Nothing is
 * clipped.
 */
export function FormPanes({
  panes,
  panelId,
  rail,
  form,
  details,
  staged,
  controls,
}: {
  panes: WorkspacePanes;
  /** The id of the tab panel this area is. */
  panelId: string;
  rail: ReactNode;
  form: ReactNode;
  /** Null where the declaration has no details to show. */
  details: ReactNode | null;
  staged: ReactNode;
  /** Where the pane controls are drawn: a place in the workspace's view
   * bar, so they stay put whatever the panes do to the form's width. */
  controls: HTMLElement | null;
}) {
  const t = useStrings();
  const [panel, room] = useBoxSize();
  const column = useRef<HTMLDivElement>(null);
  const below = useRef<HTMLDivElement>(null);
  const least = useFormLeast(column, below);
  const railId = useId();
  const detailsId = useId();
  const layout = useArrangement(panes, room, least, details !== null);
  const { side, details: detailsPane } = panes;
  const beside = layout.placement === "side";
  const doors = {
    side: {
      open: layout.sideOpen,
      toggle: () => side.setOpen(!layout.sideOpen),
      controls: railId,
    },
    details:
      details === null
        ? null
        : {
            open: layout.detailsOpen,
            toggle: () => detailsPane.setOpen(!layout.detailsOpen),
            controls: detailsId,
          },
    placement:
      details === null
        ? null
        : {
            open: beside,
            toggle: () => {
              // Where the details go never shows or hides them: until the
              // person chose, whether they are shown follows the arrangement,
              // so it is held as drawn.
              if (detailsPane.preference.open === null)
                detailsPane.setOpen(layout.detailsOpen);
              detailsPane.setPlacement(
                chosenPlacement(beside ? "bottom" : "side", layout.automatic),
              );
            },
            controls: detailsId,
          },
  };

  // One grid with the panes always in the same places in the document, so
  // the details move between beside and under the form without being drawn
  // anew, and keep what they read.
  return (
    <PaneDoors.Provider value={doors}>
      <PaneControls place={controls} />
      <div
        ref={panel}
        id={panelId}
        role="tabpanel"
        data-details={layout.detailsOpen ? layout.placement : "closed"}
        className="relative grid min-h-60 flex-1 grid-cols-[auto_minmax(0,1fr)_auto] grid-rows-[minmax(0,1fr)_auto_auto]"
        style={
          layout.areaLeast > 0 ? { minHeight: layout.areaLeast } : undefined
        }
      >
        {layout.sideOpen && (
          <ResizablePane
            edge="start"
            id={railId}
            aria-label={t("desktop.modelo.side.label")}
            handleLabel={t("desktop.modelo.side.resize")}
            size={side.preference.side}
            onSize={(size) => side.setSize("side", size)}
            defaultSize={RAIL.size * layout.rem}
            {...layout.rail}
            boxClassName="col-start-1 row-span-3 row-start-1"
            className="bg-chrome"
          >
            {rail}
          </ResizablePane>
        )}
        <div
          ref={column}
          className="col-start-2 row-start-1 flex min-h-0 min-w-0 flex-col"
        >
          {form}
        </div>
        {layout.detailsOpen && (
          <ResizablePane
            edge={beside ? "end" : "bottom"}
            id={detailsId}
            aria-label={t("desktop.modelo.details.label")}
            handleLabel={t("desktop.modelo.details.resize")}
            size={detailsPane.preference[layout.placement]}
            onSize={(size) => detailsPane.setSize(layout.placement, size)}
            defaultSize={layout.details.size}
            min={layout.details.min}
            max={layout.details.max}
            maxShare={layout.details.maxShare}
            keep={layout.details.keep}
            boxClassName={
              beside
                ? "col-start-3 row-span-3 row-start-1"
                : "col-start-2 row-start-2"
            }
            className="overflow-y-auto bg-card"
          >
            {details}
          </ResizablePane>
        )}
        <div ref={below} className="col-start-2 row-start-3 min-w-0">
          {staged}
        </div>
      </div>
    </PaneDoors.Provider>
  );
}
