// Whether the signed-in session this window was working for has ended, for
// every session-bound read in the window at once. The sign-in state sets it
// when the person signs out and when the session ends without being asked
// (an idle expiry), and clears it when a session starts again.

let ended = false;
let recorded = new Set<string>();

/** The window's session ended; reads bound to it have nothing to answer. */
export function sessionEnded(): boolean {
  return ended;
}

export function endSession(): void {
  ended = true;
}

/** A session started: a later end is a new one, recorded afresh. */
export function startSession(): void {
  ended = false;
  recorded = new Set();
}

/** Whether a refusal of `command` for the ended session is the first one,
 * which is the only one recorded. */
export function firstAfterEnd(command: string): boolean {
  if (recorded.has(command)) return false;
  recorded.add(command);
  return true;
}
