// The development scenarios: named, deterministic host behaviours for
// designing and testing the shell in a browser. Each one is data; the
// scenario host (./scenarioHost.ts) turns it into a `Host`. Titles and
// summaries are tool text for developers, not product chrome, so they are not
// in the locale catalogues.

import type { HostErrorCode, SignInStatus } from "../ipc/contract";

/** What a submitted password meets. */
export type SubmitOutcome =
  | { kind: "accept" }
  /** The host never answers, so the pending presentation stays up. */
  | { kind: "pending" }
  | { kind: "refuse"; code: string; retryAfterSeconds: number | null }
  /** The command itself fails: the call rejects with a host failure. */
  | { kind: "fail"; code: HostErrorCode };

export type Scenario = {
  id: string;
  title: string;
  summary: string;
  /** `desktop_environment`: answered, never answered, or refused. */
  environment: "ready" | "pending" | "failed";
  signIn: {
    /** The status every read reports until a submission or sign-out changes it. */
    status: Omit<SignInStatus, "active_profile">;
    /** Status reads never answer. */
    statusPending?: boolean;
    /** Status reads reject with this host failure. */
    statusFailure?: HostErrorCode;
    submit: SubmitOutcome;
    /** Sign-out answers, or rejects with this host failure. */
    signOutFailure?: HostErrorCode;
    /** The active profile's name; null when the host knows none. */
    profile?: string | null;
  };
  /** The log subscription: fixture records, an available but empty source, a
   * missing or unreadable source, or a subscription that never answers. */
  logs: "records" | "empty" | "missing" | "unreadable" | "pending";
  /** Terminal sessions: fixture output, a session that starts and prints
   * nothing, one that starts and then fails, one that fails to start, or one
   * that never starts. */
  terminals: "fixture" | "silent" | "failing" | "failed" | "pending";
  /** How the documentation fixture answers a search. */
  docsSearch: "results" | "empty" | "slow" | "failed";
  /** Clipboard and external-link calls: served from memory, or refused. */
  services: "memory" | "refused";
  /** The profile views: the fixture calendar and notification counts, a
   * calendar with nothing due and notifications never captured, reads that
   * are refused, or a host that offers no views at all, as the desktop host
   * does today. */
  views: "fixture" | "empty" | "refused" | "none";
};

const signedOut: Scenario["signIn"]["status"] = {
  supported: true,
  state: "absent",
  runtimeAvailable: true,
  refusal: null,
};

const base = {
  environment: "ready",
  logs: "records",
  terminals: "fixture",
  docsSearch: "results",
  services: "memory",
  views: "fixture",
} as const satisfies Partial<Scenario>;

export const SCENARIOS: readonly Scenario[] = [
  {
    ...base,
    id: "signed-out",
    title: "Signed out",
    summary:
      "No live sign-in. Any password is accepted after a short, fixed delay.",
    signIn: { status: signedOut, submit: { kind: "accept" } },
  },
  {
    ...base,
    id: "signing-in",
    title: "Signing in",
    summary:
      "Submit any password: the host never answers, so the pending state stays up.",
    signIn: { status: signedOut, submit: { kind: "pending" } },
  },
  {
    ...base,
    id: "signed-in",
    title: "Signed in",
    summary:
      "A live sign-in is present; the TUI pane runs its fixture session.",
    signIn: {
      status: { ...signedOut, state: "present" },
      submit: { kind: "accept" },
    },
  },
  {
    ...base,
    id: "wrong-password",
    title: "Wrong password",
    summary: "Every submission is refused with CREDENTIAL_REJECTED.",
    signIn: {
      status: signedOut,
      submit: {
        kind: "refuse",
        code: "CREDENTIAL_REJECTED",
        retryAfterSeconds: null,
      },
    },
  },
  {
    ...base,
    id: "throttled",
    title: "Throttled",
    summary: "Every submission is refused with THROTTLED and a 30 second wait.",
    signIn: {
      status: signedOut,
      submit: { kind: "refuse", code: "THROTTLED", retryAfterSeconds: 30 },
    },
  },
  {
    ...base,
    id: "profile-locked",
    title: "Profile locked",
    summary:
      "Status carries PROFILE_LOCKED: the view hands over to the TUI's own resume.",
    signIn: {
      status: {
        ...signedOut,
        refusal: { code: "PROFILE_LOCKED", retryAfterSeconds: null },
      },
      submit: {
        kind: "refuse",
        code: "PROFILE_LOCKED",
        retryAfterSeconds: null,
      },
    },
  },
  {
    ...base,
    id: "no-profile",
    title: "No active profile",
    summary:
      "Nothing to sign in to: no profile was created, or none is chosen. The way on is the TUI.",
    signIn: { status: signedOut, submit: { kind: "accept" }, profile: null },
  },
  {
    ...base,
    id: "runtime-unavailable",
    title: "Runtime unavailable",
    summary:
      "Status reports unknown presence with no runtime to ask; submission is disabled.",
    signIn: {
      status: { ...signedOut, state: "unknown", runtimeAvailable: false },
      submit: {
        kind: "refuse",
        code: "RUNTIME_UNAVAILABLE",
        retryAfterSeconds: null,
      },
      profile: null,
    },
    terminals: "silent",
  },
  {
    ...base,
    id: "unsupported",
    title: "Sign-in unsupported",
    summary:
      "The platform has no lock observer: no sign-in view and no Account section.",
    signIn: {
      status: { ...signedOut, supported: false, state: "unknown" },
      submit: { kind: "accept" },
    },
  },
  {
    ...base,
    id: "loading",
    title: "Loading",
    summary:
      "The environment, sign-in status, log subscription and sessions never answer.",
    environment: "pending",
    signIn: {
      status: signedOut,
      statusPending: true,
      submit: { kind: "pending" },
    },
    logs: "pending",
    terminals: "pending",
    docsSearch: "slow",
  },
  {
    ...base,
    id: "empty",
    title: "Empty",
    summary:
      "Signed in with nothing to show: no log records, silent sessions, no search results.",
    signIn: {
      status: { ...signedOut, state: "present" },
      submit: { kind: "accept" },
    },
    logs: "empty",
    terminals: "silent",
    docsSearch: "empty",
    views: "empty",
  },
  {
    ...base,
    id: "error",
    title: "Error",
    summary:
      "The environment and status reads are refused, the log source is unreadable, sessions fail to start and shell services refuse.",
    environment: "failed",
    signIn: {
      status: { ...signedOut, state: "unknown" },
      statusFailure: "timed_out",
      submit: { kind: "fail", code: "timed_out" },
    },
    logs: "unreadable",
    terminals: "failed",
    docsSearch: "failed",
    services: "refused",
  },
  {
    ...base,
    id: "logs-missing",
    title: "Log file missing",
    summary:
      "Signed in; the log source reports missing, which is not an empty log.",
    signIn: {
      status: { ...signedOut, state: "present" },
      submit: { kind: "accept" },
    },
    logs: "missing",
  },
  {
    ...base,
    id: "sign-out-refused",
    title: "Sign-out refused",
    summary:
      "Signed in; the sign-out command fails, so the sign-in stays and the failure shows.",
    signIn: {
      status: { ...signedOut, state: "present" },
      submit: { kind: "accept" },
      signOutFailure: "timed_out",
    },
  },
  {
    ...base,
    id: "session-failure",
    title: "Session failure",
    summary:
      "Signed in; each session starts, prints a line, then fails and exits.",
    signIn: {
      status: { ...signedOut, state: "present" },
      submit: { kind: "accept" },
    },
    terminals: "failing",
  },
  {
    ...base,
    id: "tui-unavailable",
    title: "TUI cannot start",
    summary:
      "Signed out, and every session fails to start: carrying on in the TUI comes back to the gate.",
    signIn: { status: signedOut, submit: { kind: "accept" } },
    terminals: "failed",
  },
  {
    ...base,
    id: "views-refused",
    title: "Profile views refused",
    summary:
      "Signed in; every read of a profile view fails, which is not an empty calendar.",
    signIn: {
      status: { ...signedOut, state: "present" },
      submit: { kind: "accept" },
    },
    views: "refused",
  },
  {
    ...base,
    id: "no-views",
    title: "No profile views",
    summary:
      "Signed in on a host that offers no profile views, as the desktop host does today: nothing leads to one.",
    signIn: {
      status: { ...signedOut, state: "present" },
      submit: { kind: "accept" },
    },
    views: "none",
  },
];

export const DEFAULT_SCENARIO = "signed-out";

export function findScenario(id: string | null): Scenario {
  const found = SCENARIOS.find((scenario) => scenario.id === id);
  if (found) return found;
  const fallback = SCENARIOS.find(
    (scenario) => scenario.id === DEFAULT_SCENARIO,
  );
  if (!fallback) throw new Error("The default scenario is not declared.");
  return fallback;
}
