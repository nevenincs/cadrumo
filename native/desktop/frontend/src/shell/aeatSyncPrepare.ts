// What must be in place before an update from AEAT can run, and the sign-in
// the host makes when the session needs one. The host judges both; the window
// only words the answer. Nothing here starts an update.

/** the browser the update reads AEAT with, as the setup engine's
 * browser row reads: `missing` is something setup can install (with its
 * served download size), `attention` is a row that needs its own recovery. */
export type AeatBrowserReadiness =
  | { state: "ready" }
  | { state: "missing"; bytes: number | null }
  | { state: "attention" };

/** Whether the profile has what AEAT asks for: a certificate, or Cl@ve
 * with its facts. */
export type AeatAccessReadiness = "ready" | "needs_access";

export type AeatSyncPrepared = {
  browser: AeatBrowserReadiness;
  access: AeatAccessReadiness;
};

/** What the sign-in is waiting on, while it is. */
export type AeatSignInStage = "waiting_for_phone";

export type AeatSyncPreparePort = {
  /** Reads the setup engine's browser row and the profile's AEAT access.
   * It reaches no network. */
  prepare(): Promise<AeatSyncPrepared>;
  /** Signs in to AEAT with the profile's configured way, reusing a session
   * that is still valid, including one made in the in-app browser. Calls
   * `stage` when it waits on the person; resolves once signed in. A
   * rejection is read by `aeatSignInFailure`. */
  signIn(stage: (stage: AeatSignInStage) => void): Promise<void>;
  /** Stops a sign-in that waits on the person's phone. */
  cancelSignIn(): Promise<void>;
};

export type AeatSignInFailure =
  "needs_access" | "cancelled" | "refused" | "unavailable";

/** A rejected sign-in's `{ code }` as the failure the window words. */
export function aeatSignInFailure(error: unknown): AeatSignInFailure {
  const code = (error as { code?: unknown } | null)?.code;
  return code === "needs_access" || code === "cancelled" || code === "refused"
    ? code
    : "unavailable";
}
