import { useMemo, type RefObject } from "react";
import type { TerminalApi } from "../components/TerminalPane";
import type { Action } from "./actions";
import { activeTerminal } from "./focusedArea";
import type { TerminalKind } from "./host";
import type { Translate } from "./strings";

/** The focused terminal's copy and paste. */
export function useTerminalActions({
  t,
  copy,
  terminals,
  paste,
}: {
  t: Translate;
  copy: (text: string) => void;
  terminals: RefObject<Partial<Record<TerminalKind, TerminalApi>>>;
  paste: (kind: TerminalKind | null) => void;
}): Action[] {
  return useMemo<Action[]>(
    () => [
      {
        id: "terminal.copy",
        label: t("desktop.menu.copy"),
        group: "terminal",
        icon: "copy",
        hidden: true,
        chords: [
          { mod: true, shift: true, code: "KeyC", key: "C", scope: "terminal" },
        ],
        // Only the focused terminal's selection; without one, nothing.
        run: () => {
          const kind = activeTerminal();
          if (kind) copy(terminals.current[kind]?.selection() ?? "");
        },
      },
      {
        id: "terminal.paste",
        label: t("desktop.menu.paste"),
        group: "terminal",
        icon: "paste",
        hidden: true,
        chords: [
          { mod: true, shift: true, code: "KeyV", key: "V", scope: "terminal" },
        ],
        run: () => paste(activeTerminal()),
      },
    ],
    [t, copy, terminals, paste],
  );
}
