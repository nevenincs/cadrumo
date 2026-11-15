import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import type { TerminalApi, TerminalStatus } from "../components/TerminalPane";
import type { Host, TerminalKind } from "./host";

/**
 * Keeps the console on the environment the host starts it with. When the
 * host reports a new revision, a console with no running process is closed
 * and opened again at once; a running one is never stopped for it, and
 * `pending` asks the person to restart it. A console never opened needs
 * nothing: its first session starts with the current environment. The
 * Python and TUI sessions are not the console and are left alone.
 */
export function useConsoleEnvironment({
  host,
  status,
  terminals,
}: {
  host: Host;
  status: TerminalStatus;
  terminals: RefObject<Partial<Record<TerminalKind, TerminalApi>>>;
}) {
  const [pending, setPending] = useState(false);
  const live = useRef(status);
  live.current = status;
  const seen = useRef<string | null>(null);

  useEffect(() => {
    if (!host.observeConsoleEnvironment) return;
    let stop: (() => void) | null = null;
    let cancelled = false;
    host
      .observeConsoleEnvironment(({ revision }) => {
        if (cancelled || revision === seen.current) return;
        seen.current = revision;
        const pane = terminals.current.console;
        if (!pane) return;
        const phase = live.current.phase;
        if (phase === "exited" || phase === "failed") {
          setPending(false);
          pane.restart();
        } else if (phase === "running" || phase === "starting") {
          // A session still opening may already run its process.
          setPending(true);
        }
      })
      .then(
        (unsubscribe) => {
          if (cancelled) unsubscribe();
          else stop = unsubscribe;
        },
        // Without the subscription the console keeps the environment it was
        // started with, as it did before the host offered the event.
        () => undefined,
      );
    return () => {
      cancelled = true;
      stop?.();
    };
  }, [host, terminals]);

  // The process the notice was about has ended: the next session starts
  // with the current environment.
  const phase = status.phase;
  if (pending && (phase === "exited" || phase === "failed")) setPending(false);

  const restart = useCallback(() => {
    setPending(false);
    const pane = terminals.current.console;
    pane?.restart();
    // The door goes with the notice; the keyboard goes to the console.
    pane?.focus();
  }, [terminals]);

  return { pending, restart };
}
