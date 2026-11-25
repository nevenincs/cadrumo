import type { HostCall } from "./hostCall";

// Whether the signed-in session this window was working for has ended, for
// every session-bound command in the window at once. The sign-in state sets
// it as soon as it learns of an end, whichever way the end came: the person
// signing out, an idle expiry, a lapsed or locked session, or a runtime that
// went away. It clears when a session starts again.

let ended = false;
let recorded = new Set<string>();
let confirm: (() => Promise<void>) | null = null;

/** How long a refusal's record waits for the sign-in state to say whether
 * the session is still there, before it is recorded as the window saw it. */
const CONFIRM_MS = 5000;

/** The window's session ended; commands bound to it have nothing to answer. */
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

/** The sign-in state's own read of whether the session is still there. It
 * ends the session through `endSession` when it finds it gone. */
export function confirmSessionWith(check: () => Promise<void>): () => void {
  confirm = check;
  return () => {
    if (confirm === check) confirm = null;
  };
}

/**
 * Whether the session has ended, once the sign-in state has read it again.
 * The host can announce an end to a view before it tells the sign-in state,
 * so a refusal for a missing session may arrive first; it was foreseen only
 * if the session turns out to be gone.
 */
export async function sessionEndConfirmed(): Promise<boolean> {
  if (ended || !confirm) return ended;
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([
      confirm().catch(() => undefined),
      new Promise<void>((resolve) => (timer = setTimeout(resolve, CONFIRM_MS))),
    ]);
  } finally {
    clearTimeout(timer);
  }
  return ended;
}

/** The refusal the host answers a session-bound command with when nobody is
 * signed in; the window answers it itself once it knows the session ended. */
export type SessionEndedRefusal = { code: "not_signed_in" };

export function refuseIfEnded(): void {
  if (ended) throw { code: "not_signed_in" } satisfies SessionEndedRefusal;
}

/** `call`, for commands that only a signed-in session can ask. After the
 * session ended they are not sent: the window answers the refusal the host
 * would, so nothing reaches the host or its log. */
export function sessionBound(call: HostCall): HostCall {
  return (command, args, plan) =>
    ended
      ? Promise.reject({ code: "not_signed_in" } satisfies SessionEndedRefusal)
      : call(command, args, plan);
}
