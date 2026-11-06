import type {
  ComponentProps,
  Dispatch,
  RefObject,
  SetStateAction,
} from "react";
import type { Host, TerminalKind } from "../shell/host";
import type { SignInController } from "../shell/signIn";
import type { Translate } from "../shell/strings";
import type { useShellMenus } from "../shell/useShellMenus";
import type { useShellShortcuts } from "../shell/useShellShortcuts";
import {
  TerminalPane,
  type TerminalApi,
  type TerminalStatus,
} from "./TerminalPane";

/** What every terminal the window draws is wired to: the host, the
 * shell's chords and menu, where it reports its state and registers its
 * handle. */
export type TerminalWiring = {
  host: Host;
  t: Translate;
  account: SignInController;
  fontSize: ComponentProps<typeof TerminalPane>["fontSize"];
  isShellChord: ReturnType<typeof useShellShortcuts>["isShellChord"];
  setStatus: Dispatch<SetStateAction<Record<TerminalKind, TerminalStatus>>>;
  terminalMenu: ReturnType<typeof useShellMenus>["terminalMenu"];
  terminals: RefObject<Partial<Record<TerminalKind, TerminalApi>>>;
};

/** One terminal session as the window draws it: the TUI, the console or
 * Python. */
export function ShellTerminal({
  kind,
  shown,
  theme,
  wiring,
}: {
  kind: TerminalKind;
  shown: boolean;
  theme: ComponentProps<typeof TerminalPane>["theme"];
  wiring: TerminalWiring;
}) {
  const {
    host,
    t,
    account,
    fontSize,
    isShellChord,
    setStatus,
    terminalMenu,
    terminals,
  } = wiring;
  return (
    <TerminalPane
      host={host}
      kind={kind}
      shown={shown}
      theme={theme}
      fontSize={fontSize}
      label={
        kind === "tui"
          ? t("desktop.tui.label")
          : t(
              kind === "console"
                ? "desktop.rail.console"
                : "desktop.rail.python",
            )
      }
      isShellChord={isShellChord}
      onStatus={(k, s) => {
        setStatus((all) => ({ ...all, [k]: s }));
        if (k !== "tui") return;
        // The TUI's session has ended: what it did to the account is read
        // again.
        if (s.phase === "exited" || s.phase === "failed") account.tuiExited();
      }}
      onMenu={terminalMenu}
      register={(k, api) => {
        terminals.current[k] = api;
      }}
      tabPanel={kind !== "tui"}
    />
  );
}
