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
  | { kind: "refuse"; code: string; retryAfterSeconds: number | null };

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
  };
  /** The log subscription: fixture records, an available but empty source, a
   * missing or unreadable source, or a subscription that never answers. */
  logs: "records" | "empty" | "missing" | "unreadable" | "pending";
  /** Terminal sessions: fixture output, a session that starts and prints
   * nothing, a session that fails to start, or one that never starts. */
  terminals: "fixture" | "silent" | "failed" | "pending";
  /** How the documentation fixture answers a search. */
  docsSearch: "results" | "empty" | "slow" | "failed";
  /** Clipboard and external-link calls: served from memory, or refused. */
  services: "memory" | "refused";
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
      submit: { kind: "refuse", code: "timed_out", retryAfterSeconds: null },
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
