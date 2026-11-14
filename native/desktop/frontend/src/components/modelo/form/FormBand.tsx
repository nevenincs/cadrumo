import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { ResizablePane } from "@/components/ui/resizable-pane";
import { usePanePreference } from "../../../shell/panePreference";
import { useStrings } from "../../../shell/strings";

/** The name the band's height is kept under in the viewer's preferences. */
export const FORM_BAND_PANE = "modelo.workspace.band";

// Until the person sizes it, the band takes what it says up to this share
// of the form's column, and leaves the form this much more than its least
// room, in rem, so the boxes open as the working area.
const OPENING_SHARE = 1 / 3;
const FORM_OPENING_REM = 5;
// The least the band keeps of itself while the column has room, in rem:
// its first line stays in sight. On a window too short for that beside the
// form's least room the band gives way entirely, and has no line.
const BAND_LEAST_REM = 1.5;

const remPx = () =>
  parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;

type Measured = { content: number; room: number; keep: number };

/** What the band's frame sits in: the column's height, and what the
 * column's other parts keep, with the form's scroller at its least. */
function measureColumn(
  frame: HTMLElement,
  column: HTMLElement,
  content: HTMLElement,
): Measured {
  let keep = 0;
  for (const part of column.children)
    if (part !== frame && part instanceof HTMLElement) keep += partKept(part);
  return {
    content: Math.ceil(content.offsetHeight),
    room: column.clientHeight,
    keep: Math.ceil(keep),
  };
}

/** What a part of the column keeps beside the band: the form's scroller its
 * least height, anything else its height as drawn. */
function partKept(part: HTMLElement): number {
  return part.hasAttribute("data-modelo-form")
    ? parseFloat(getComputedStyle(part).minHeight) || 0
    : part.offsetHeight;
}

function useMeasured() {
  const content = useRef<HTMLDivElement>(null);
  const [measured, setMeasured] = useState<Measured | null>(null);
  useLayoutEffect(() => {
    const inner = content.current;
    const frame = inner?.closest<HTMLElement>("[data-slot=resizable-pane]");
    const column = frame?.parentElement;
    if (!inner || !frame || !column) return;
    const measure = () => setMeasured(measureColumn(frame, column, inner));
    const observer = new ResizeObserver(measure);
    observer.observe(inner);
    observer.observe(column);
    measure();
    return () => observer.disconnect();
  }, []);
  return [content, measured] as const;
}

/**
 * What is said about the whole form, above its pages: drawn at what it says
 * up to a third of the column, leaving the form room to work, until the
 * person sizes it with its line, then
 * at their height, never more than it says and never over the form's least
 * room. It gives way first on a short window and scrolls on its own. The
 * height is the viewer's, kept like the other panes' sizes.
 */
export function FormBand({ children }: { children: ReactNode }) {
  const t = useStrings();
  const kept = usePanePreference(FORM_BAND_PANE);
  const [content, measured] = useMeasured();
  const rem = remPx();
  const said = measured?.content ?? 0;
  const least = Math.min(said, BAND_LEAST_REM * rem);
  const room = measured?.room ?? 0;
  const opening = Math.min(
    said,
    room * OPENING_SHARE,
    room - (measured?.keep ?? 0) - FORM_OPENING_REM * rem,
  );
  return (
    <ResizablePane
      edge="top"
      aria-label={t("desktop.modelo.band.label")}
      handleLabel={t("desktop.modelo.band.resize")}
      size={kept.preference.bottom}
      onSize={(size) => kept.setSize("bottom", size)}
      defaultSize={opening}
      min={least}
      max={said}
      maxShare={1}
      keep={measured?.keep ?? 0}
      boxClassName="flex-none"
      className="overflow-y-auto"
      data-form-gives-way=""
    >
      <div ref={content} className="flex flex-none flex-col">
        {children}
      </div>
    </ResizablePane>
  );
}
