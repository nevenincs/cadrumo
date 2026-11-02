import { useCallback, useEffect, useMemo, useRef, type RefObject } from "react";
import {
  bridgeChords,
  findAction,
  type Action,
  type FocusArea,
} from "./actions";

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
      const focus: FocusArea = (event.target as HTMLElement | null)?.closest?.(
        ".xterm, [data-browser-surface]",
      )
        ? "terminal"
        : "chrome";
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
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, [actionsRef, chordAllowed]);

  return { isShellChord, chords, runShortcut };
}
