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
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { ResizablePane } from "@/components/ui/resizable-pane";
import type { PanePreferenceControl } from "../../../shell/panePreference";
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

// Widths in rem at which the rail opens by default and the details move
// beside the form rather than under it.
const RAIL_ROOM_REM = 56;
const DETAILS_BESIDE_REM = 72;
// Each pane's default, least and most in rem, and the most of the form's
// area it takes, so the form keeps the rest at any window size.
const RAIL = { size: 15, min: 11, max: 28, share: 0.4 };
const DETAILS_SIDE = { size: 22, min: 16, max: 40, share: 0.45 };
// Under the form the details open at two fifths of the area and give way to
// the form's least room on a short window.
const DETAILS_BOTTOM = { share: 0.4, min: 6, max: 48, maxShare: 0.6 };
// The least the details under the form are drawn at however short the
// window, in rem, so they stay on screen and keep what they read.
const DETAILS_BOTTOM_FLOOR = 2;
// What a band that gives way keeps of itself before the details give way
// to it, in rem: its first lines stay readable and its controls reachable.
const BAND_KEEP_REM = 6;

const remPx = () =>
  parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;

type PaneDoor = { open: boolean; toggle(): void; controls: string };
const PaneDoors = createContext<{
  side: PaneDoor;
  details: PaneDoor | null;
} | null>(null);

/**
 * The controls that show and hide the panes beside the form, for the form's
 * toolbar. Outside a workspace there are no panes, and nothing is drawn.
 */
export function WorkspacePaneToggles() {
  const doors = useContext(PaneDoors);
  const t = useStrings();
  if (!doors) return null;
  const { side, details } = doors;
  return (
    <>
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
        <Icon name="splitRow" />
      </IconButton>
      {details && (
        <IconButton
          label={t(
            details.open
              ? "desktop.modelo.details.hide"
              : "desktop.modelo.details.show",
          )}
          size="sm"
          aria-pressed={details.open}
          aria-controls={details.open ? details.controls : undefined}
          data-pane-toggle="details"
          onClick={details.toggle}
        >
          <Icon name="splitColumn" />
        </IconButton>
      )}
    </>
  );
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
 * the first lines of a band that gives way (`data-form-gives-way`). */
type FormLeast = { fixed: number; band: number };

function formLeast(element: HTMLElement, bandKeep: number): FormLeast {
  const scroller = element.querySelector<HTMLElement>("[data-modelo-form]");
  if (!scroller) return { fixed: 0, band: 0 };
  let drawn = 0;
  let band = 0;
  for (const giving of element.querySelectorAll<HTMLElement>(
    "[data-form-gives-way]",
  )) {
    drawn += giving.offsetHeight;
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

/**
 * The form view's area: the rail at its start, the form, the details beside
 * it on a wide area or under it on a narrow one, and the staged-edit bar
 * under the form. Each pane is shown or hidden from the form's toolbar and
 * resized by its separator; both are the viewer's presentation, kept by the
 * caller, never a fact about the declaration. Under the form the details
 * give way first: the form keeps its bands and its scroller's least height.
 */
export function FormPanes({
  panes,
  panelId,
  rail,
  form,
  details,
  staged,
}: {
  panes: WorkspacePanes;
  /** The id of the tab panel this area is. */
  panelId: string;
  rail: ReactNode;
  form: ReactNode;
  /** Null where the declaration has no details to show. */
  details: ReactNode | null;
  staged: ReactNode;
}) {
  const t = useStrings();
  const [panel, room] = useBoxSize();
  const column = useRef<HTMLDivElement>(null);
  const below = useRef<HTMLDivElement>(null);
  const least = useFormLeast(column, below);
  const railId = useId();
  const detailsId = useId();
  const rem = remPx();
  const width = room?.width ?? window.innerWidth;
  const height = room?.height ?? window.innerHeight;
  const { side, details: detailsPane } = panes;
  const sideOpen = side.preference.open ?? width >= RAIL_ROOM_REM * rem;
  const beside = width >= DETAILS_BESIDE_REM * rem;
  // Under the form, the form's fixed bands and its scroller's least height
  // come first, then a sliver of the details, then the first lines of a
  // band that gives way, then the rest of the details. Too short for the
  // form and that sliver, the area keeps them and the workspace scrolls as
  // a whole. Opened where that leaves the details less than their least,
  // they start hidden; a window made shorter later keeps them shown.
  const floor = DETAILS_BOTTOM_FLOOR * rem;
  const roomy = useRoomAtOpening(
    least.fixed > 0 && room !== null
      ? height - least.fixed - least.band >= DETAILS_BOTTOM.min * rem
      : null,
  );
  const detailsOpen =
    details !== null &&
    (detailsPane.preference.open ?? (beside || roomy === true));
  const under = detailsOpen && !beside;
  const keep =
    least.fixed +
    Math.min(least.band, Math.max(0, height - least.fixed - floor));
  const areaLeast = least.fixed > 0 ? least.fixed + (under ? floor : 0) : 0;
  const doors = {
    side: {
      open: sideOpen,
      toggle: () => side.setOpen(!sideOpen),
      controls: railId,
    },
    details:
      details === null
        ? null
        : {
            open: detailsOpen,
            toggle: () => detailsPane.setOpen(!detailsOpen),
            controls: detailsId,
          },
  };

  // One grid with the panes always in the same places in the document, so
  // the details move between beside and under the form without being drawn
  // anew, and keep what they read. Too short for the form's least room, the
  // area keeps it and the workspace scrolls as a whole.
  return (
    <PaneDoors.Provider value={doors}>
      <div
        ref={panel}
        id={panelId}
        role="tabpanel"
        data-details={detailsOpen ? (beside ? "side" : "bottom") : "closed"}
        className="relative grid min-h-60 flex-1 grid-cols-[auto_minmax(0,1fr)_auto] grid-rows-[minmax(0,1fr)_auto_auto]"
        style={areaLeast > 0 ? { minHeight: areaLeast } : undefined}
      >
        {sideOpen && (
          <ResizablePane
            edge="start"
            id={railId}
            aria-label={t("desktop.modelo.side.label")}
            handleLabel={t("desktop.modelo.side.resize")}
            size={side.preference.side}
            onSize={(size) => side.setSize("side", size)}
            defaultSize={RAIL.size * rem}
            min={RAIL.min * rem}
            max={RAIL.max * rem}
            maxShare={RAIL.share}
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
        {detailsOpen && (
          <ResizablePane
            edge={beside ? "end" : "bottom"}
            id={detailsId}
            aria-label={t("desktop.modelo.details.label")}
            handleLabel={t("desktop.modelo.details.resize")}
            size={
              beside
                ? detailsPane.preference.side
                : detailsPane.preference.bottom
            }
            onSize={(size) =>
              detailsPane.setSize(beside ? "side" : "bottom", size)
            }
            defaultSize={
              beside ? DETAILS_SIDE.size * rem : height * DETAILS_BOTTOM.share
            }
            min={(beside ? DETAILS_SIDE.min : DETAILS_BOTTOM.min) * rem}
            max={(beside ? DETAILS_SIDE.max : DETAILS_BOTTOM.max) * rem}
            maxShare={beside ? DETAILS_SIDE.share : DETAILS_BOTTOM.maxShare}
            keep={beside ? undefined : keep}
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
