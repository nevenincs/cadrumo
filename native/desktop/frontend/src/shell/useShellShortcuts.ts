import { useCallback, useEffect, useMemo, useRef, type RefObject } from "react";
import {
  bridgeChords,
  claimsButton,
  findAction,
  findButtonAction,
  type Action,
  type FocusArea,
} from "./actions";

/** What is drawn over the window and keeps a pointer's buttons. */
const LAYERS =
  '[role="dialog"], [role="alertdialog"], [role="menu"], [data-modal-layer]';

/** The area a key or button event came from: a terminal or the browser
 * keeps its own keys; everything else is the window's chrome. */
function areaOf(target: EventTarget | null): FocusArea {
  return (target as HTMLElement | null)?.closest?.(
    ".xterm, [data-browser-surface]",
  )
    ? "terminal"
    : "chrome";
}

/** Shares one action keymap and modal policy between native keys and docs. */
export function useShellShortcuts(
  actions: Action[],
  actionsRef: RefObject<Action[]>,
  paletteOpen: boolean,
  otherModal: boolean,
) {
  const isShellChord = useCallback(
    (event: KeyboardEvent) =>
      findAction(actionsRef.current, event, "terminal") !== null,
    [actionsRef],
  );

  // The bridge keymap changes only when chords do, not on every label change.
  const chordsKey = useMemo(
    () => JSON.stringify(bridgeChords(actions)),
    [actions],
  );
  const chords = useMemo(
    () => JSON.parse(chordsKey) as ReturnType<typeof bridgeChords>,
    [chordsKey],
  );

  // What holds the keyboard above the shell. A modal surface owns it: no
  // chord reaches the shell from under one, except the palette's own, which
  // closes the palette. The sign-in dialog is only on screen once the status
  // read has answered. Chords pressed in the documentation arrive by its
  // bridge and pass the same guard.
  const modal = useRef({ palette: false, other: false });
  modal.current = {
    palette: paletteOpen,
    other: otherModal,
  };
  const chordAllowed = useCallback(
    (id: string) =>
      !modal.current.other && (!modal.current.palette || id === "palette.open"),
    [],
  );
  const runShortcut = useCallback(
    (id: string) => {
      // A chord from the documentation asks for an action by name: one that
      // is not offered is not run, as a key pressed in the window is not.
      const action = actionsRef.current.find((known) => known.id === id);
      if (action && chordAllowed(id) && action.enabled?.() !== false)
        action.run();
    },
    [actionsRef, chordAllowed],
  );

  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      const focus = areaOf(event.target);
      const action = findAction(actionsRef.current, event, focus);
      if (!action) return;
      if (
        action.id === "window.leaveFullscreen" &&
        document.querySelector(
          '[role="dialog"], [role="menu"][data-state="open"]',
        )
      )
        return;
      if (event.repeat && action.id === "window.fullscreen") {
        event.preventDefault();
        return;
      }
      if (!chordAllowed(action.id)) return;
      event.preventDefault();
      event.stopPropagation();
      action.run();
    };
    // A pointer's side buttons run what their chords run. The document's
    // own history never moves: that would unload the window. A dialog,
    // sheet or menu drawn over the window keeps its buttons to itself.
    const button = (event: MouseEvent) => {
      if (!claimsButton(actionsRef.current, event.button)) return;
      event.preventDefault();
      const target = event.target as Element | null;
      if (target?.closest?.(LAYERS)) return;
      const action = findButtonAction(
        actionsRef.current,
        event.button,
        areaOf(target),
      );
      if (!action || !chordAllowed(action.id)) return;
      event.stopPropagation();
      action.run();
    };
    window.addEventListener("keydown", key, true);
    window.addEventListener("mouseup", button, true);
    return () => {
      window.removeEventListener("keydown", key, true);
      window.removeEventListener("mouseup", button, true);
    };
  }, [actionsRef, chordAllowed]);

  return { isShellChord, chords, runShortcut };
}
