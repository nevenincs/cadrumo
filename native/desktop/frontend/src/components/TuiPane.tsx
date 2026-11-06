import type { RefObject } from "react";
import { cn } from "@/components/ui/cn";
import { primaryChord, type Action } from "../shell/actions";
import type { AccountPhase } from "../shell/signIn";
import { DARK_TUI, LIGHT_TUI } from "../shell/terminalThemes";
import { PaneHeader, type PaneControl } from "./PaneHeader";
import { PANE_SURFACE } from "./paneSurface";
import { tuiStatus } from "./sessionStatus";
import { ShellTerminal, type TerminalWiring } from "./ShellTerminal";
import { SignedOut } from "./SignIn";
import type { TerminalStatus } from "./TerminalPane";

/** The TUI's pane: its header, and the TUI, or the way in while the account
 * withholds it. */
export function TuiPane({
  wiring,
  phase,
  status,
  scheme,
  shown,
  maximizeControl,
  splitControls,
  byId,
  toggleMaximize,
  close,
  askSignIn,
  signInButton,
}: {
  wiring: TerminalWiring;
  phase: AccountPhase;
  status: TerminalStatus;
  scheme: "light" | "dark";
  shown: boolean;
  maximizeControl: PaneControl;
  splitControls: PaneControl[];
  byId: (id: string) => Action | undefined;
  toggleMaximize: () => void;
  close: () => void;
  askSignIn: () => void;
  signInButton: RefObject<HTMLButtonElement | null>;
}) {
  const { t, account } = wiring;
  return (
    <div className={cn(PANE_SURFACE, "pane-tui")} data-scheme={scheme}>
      <PaneHeader
        title={t("desktop.pane.tui")}
        status={tuiStatus(t, account, phase, status)}
        onToggleMaximize={toggleMaximize}
        controls={[
          maximizeControl,
          ...splitControls,
          {
            id: "close",
            icon: "close",
            label: t("desktop.tui.hide"),
            shortcut: primaryChord(byId("tui.toggle")),
            run: close,
          },
        ]}
      />
      {account.gated ? (
        <SignedOut
          account={account}
          onSignIn={askSignIn}
          signInButton={signInButton}
        />
      ) : (
        <ShellTerminal
          kind="tui"
          shown={shown}
          theme={scheme === "dark" ? DARK_TUI : LIGHT_TUI}
          wiring={wiring}
        />
      )}
    </div>
  );
}
