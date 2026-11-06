import { useRef, useState } from "react";
import type { TerminalApi, TerminalStatus } from "../components/TerminalPane";
import type { TerminalKind } from "./host";

/** The terminal sessions the window draws: each one's state as its pane
 * reports it, and the handle each pane registers. */
export function useTerminalSessions() {
  const [status, setStatus] = useState<Record<TerminalKind, TerminalStatus>>({
    console: { phase: "starting" },
    python: { phase: "starting" },
    tui: { phase: "starting" },
  });
  const terminals = useRef<Partial<Record<TerminalKind, TerminalApi>>>({});
  return { status, setStatus, terminals };
}
