import { useEffect, useRef } from "react";
import type { AccountPhase } from "./signIn";
import type { TerminalKind } from "./host";

/** Where focus goes when the account gate opens or closes with the sign-in
 * dialog put aside: the TUI takes it when what held it went with the gate. */
export function useGateFocus({
  gated,
  phase,
  signInDismissed,
  focusView,
}: {
  gated: boolean;
  phase: AccountPhase;
  signInDismissed: boolean;
  focusView: (view: TerminalKind | "logs") => void;
}) {
  // Whether the last render showed a gate the person could act on, with
  // the dialog put aside. The first status read is a gate too, but not one
  // anybody was standing at: being let through it at startup moves no
  // focus. And with the dialog still up, its own close decides where focus
  // goes: this must not get there first.
  const stoodAtGate = useRef(false);
  useEffect(() => {
    // Admitted after the dialog was put aside: the way in that held focus
    // went with the gate, and the TUI that has started takes it.
    if (
      stoodAtGate.current &&
      !gated &&
      document.activeElement === document.body
    )
      focusView("tui");
    stoodAtGate.current =
      gated && phase !== "checking" && phase !== "starting" && signInDismissed;
  }, [gated, phase, signInDismissed, focusView]);
  useEffect(() => {
    // Signed out from here, no dialog follows. If the terminal that held
    // focus went with the session, the pane's way back in takes it.
    if (gated && signInDismissed && document.activeElement === document.body)
      focusView("tui");
  }, [gated, signInDismissed, focusView]);
}
