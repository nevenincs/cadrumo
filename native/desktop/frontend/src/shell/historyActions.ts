import { useMemo } from "react";
import { IS_MAC } from "@/shared/chords";
import type { Action } from "./actions";
import type { Translate } from "./strings";

/** The pointer buttons a mouse's back and forward side buttons report. */
export const POINTER_BACK = 3;
export const POINTER_FORWARD = 4;

/** Whether the element with focus keeps Alt+Left and Alt+Right for itself:
 * a grid's column header resizes its column with them, a page that marks
 * itself keeps them for its grids, and on macOS a text field moves by
 * word. */
function keepsAltArrows(element: Element | null): boolean {
  if (!element) return false;
  if (element.closest('[role="columnheader"], [data-keeps-alt-arrows]'))
    return true;
  return (
    IS_MAC &&
    (element.matches("input, textarea") ||
      (element as HTMLElement).isContentEditable)
  );
}

/** The window's back and forward over where the viewer has been, while a
 * page holds the first pane; the documentation keeps its own history on the
 * same chords. Shortcuts only: the palette offers the documentation's. */
export function useHistoryActions({
  t,
  pageOn,
  historyBack,
  historyForward,
}: {
  t: Translate;
  pageOn: boolean;
  historyBack: () => void;
  historyForward: () => void;
}): Action[] {
  return useMemo<Action[]>(() => {
    const buttonsEnabled = () => pageOn;
    const enabled = () => pageOn && !keepsAltArrows(document.activeElement);
    return [
      {
        id: "window.back",
        label: t("desktop.action.docs_back"),
        group: "general",
        icon: "back",
        hidden: true,
        chords: [{ alt: true, code: "ArrowLeft", key: "←", scope: "app" }],
        buttons: [POINTER_BACK],
        enabled,
        buttonsEnabled,
        run: historyBack,
      },
      {
        id: "window.forward",
        label: t("desktop.action.docs_forward"),
        group: "general",
        icon: "forward",
        hidden: true,
        chords: [{ alt: true, code: "ArrowRight", key: "→", scope: "app" }],
        buttons: [POINTER_FORWARD],
        enabled,
        buttonsEnabled,
        run: historyForward,
      },
    ];
  }, [t, pageOn, historyBack, historyForward]);
}
