import { useEffect, useRef } from "react";
import { chordMatches, type ChordKeys } from "@/shared/chords";
import {
  CLASSIFY_KINDS,
  type ClassifyKind,
} from "../../../shell/ledgerCommands";

/** The chord each classify kind takes, which the page runs and its menus
 * show. */
export const CLASSIFY_CHORDS: Record<ClassifyKind, ChordKeys> = {
  business: { code: "KeyB", key: "B", alt: true },
  personal: { code: "KeyP", key: "P", alt: true },
  mixed: { code: "KeyM", key: "M", alt: true },
};
/** Whether `element` takes typed text, so a chord there is its own: a
 * checkbox or a radio does not. */
function takesText(element: HTMLElement): boolean {
  if (element.isContentEditable) return true;
  if (element instanceof HTMLTextAreaElement) return true;
  if (element instanceof HTMLSelectElement) return true;
  if (element instanceof HTMLInputElement)
    return !["checkbox", "radio", "button", "submit", "reset"].includes(
      element.type,
    );
  return false;
}

/**
 * Alt+B, Alt+P and Alt+M classify the selection wherever focus is on the
 * Ledger page, as Alt+I opens the inspector: the header's tabs, period and
 * buttons, a row checkbox, the toolbar and the inspector beside the grid
 * included. A text field keeps its keys, and a dialog over the page is not
 * the page. `classify` is the one of the latest render.
 */
export function useClassifyChords(classify: (kind: ClassifyKind) => void) {
  const chord = useRef<(kind: ClassifyKind) => void>(() => undefined);
  useEffect(() => {
    chord.current = (kind) => classify(kind);
  });
  useEffect(() => {
    const onChord = (event: globalThis.KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing) return;
      const kind = CLASSIFY_KINDS.find((each) =>
        chordMatches(CLASSIFY_CHORDS[each], event),
      );
      if (!kind) return;
      const target = event.target as HTMLElement | null;
      if (!target?.closest("[data-ledger-root]") || takesText(target)) return;
      event.preventDefault();
      chord.current(kind);
    };
    document.addEventListener("keydown", onChord);
    return () => document.removeEventListener("keydown", onChord);
  }, []);
}
