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
    /** What creating a profile meets. Accepted where it is left out. */
    create?: SubmitOutcome;
    /** The creation is made although its answer fails to arrive. */
    createLands?: boolean;
  };
  /** The profiles the host can list: none, the one fixture profile, several,
   * or a list that cannot be read; or a host with no profile commands at
   * all, as the desktop host is today, where the shell knows only the one
   * profile the status names. */
  profiles:
    | "none"
    | "one"
    | "several"
    /** Several, one of them under a name the host will not pass on. */
    | "odd"
    /** Read once, and unreadable from then on. */
    | "once"
    | "unreadable"
    | "absent";
  /** The log subscription: fixture records, an available but empty source, a
   * missing or unreadable source, or a subscription that never answers. */
  logs: "records" | "empty" | "missing" | "unreadable" | "pending";
  managerLog?: "missing" | "unreadable" | "rejected";
  /** Terminal sessions: fixture output, a session that starts and prints
   * nothing, one that starts and then fails, one that fails to start, or one
   * that never starts. */
  terminals: "fixture" | "silent" | "failing" | "failed" | "pending";
  /** How the documentation fixture answers a search. */
  docsSearch: "results" | "empty" | "slow" | "failed";
  /** Clipboard and external-link calls: served from memory, or refused. */
  services: "memory" | "refused";
  /** Explicit manager-start scenarios only; older hosts offer no command. */
  manager?: {
    /** Simulate the native host's automatic dispatch before React mounts. */
    autoDispatched?: boolean;
    result:
      | "dispatched"
      | "pending"
      | "unmanaged"
      | "unsupported"
      | { code: HostErrorCode };
    /** Fixed dispatch-answer delay, independent of profile/sign-in latency. */
    delayMs?: number;
    /** Status reads after dispatch before the runtime becomes available. */
    readyAfterReads?: number;
    /** Hold a ready status answer so navigation can happen before it lands. */
    readyReadDelayMs?: number;
    /** Status reads fail after dispatch, following the initial unavailable read. */
    statusFailureAfterDispatch?: HostErrorCode;
  };
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

const servicesDown: Scenario["signIn"] = {
  status: { ...signedOut, state: "unknown", runtimeAvailable: false },
  submit: {
    kind: "refuse",
    code: "RUNTIME_UNAVAILABLE",
    retryAfterSeconds: null,
  },
};

const base = {
  environment: "ready",
  logs: "records",
  terminals: "fixture",
  docsSearch: "results",
  services: "memory",
  views: "fixture",
  profiles: "several",
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
    title: "No active profile, no profile commands",
    summary:
      "A host that cannot list or create profiles, as the desktop host is today, and names none: the way on is the TUI.",
    signIn: { status: signedOut, submit: { kind: "accept" }, profile: null },
    profiles: "absent",
  },
  {
    ...base,
    id: "first-run",
    title: "First run",
    summary:
      "No profile exists on this computer: the dialog is the form that creates one. Any name and password are accepted.",
    signIn: { status: signedOut, submit: { kind: "accept" }, profile: null },
    profiles: "none",
  },
  {
    ...base,
    id: "create-refused",
    title: "Profile creation refused",
    summary:
      "No profile exists, and every attempt to create one is refused by the product.",
    signIn: {
      status: signedOut,
      submit: { kind: "accept" },
      profile: null,
      create: {
        kind: "refuse",
        code: "profile_already_exists",
        retryAfterSeconds: null,
      },
    },
    profiles: "none",
  },
  {
    ...base,
    id: "creating-profile",
    title: "Creating a profile",
    summary:
      "No profile exists; submit the form and the host never answers, so the wait stays up.",
    signIn: {
      status: signedOut,
      submit: { kind: "accept" },
      profile: null,
      create: { kind: "pending" },
    },
    profiles: "none",
  },
  {
    ...base,
    id: "create-unanswered",
    title: "Profile creation unanswered",
    summary:
      "No profile exists, and a creation gets no answer and makes nothing: its outcome is not known.",
    signIn: {
      status: signedOut,
      submit: { kind: "accept" },
      profile: null,
      create: { kind: "fail", code: "timed_out" },
    },
    profiles: "none",
  },
  {
    ...base,
    id: "create-lands-unanswered",
    title: "Profile created, answer lost",
    summary:
      "No profile exists; a creation gets no answer, and the profile is there all the same.",
    signIn: {
      status: signedOut,
      submit: { kind: "accept" },
      profile: null,
      create: { kind: "fail", code: "timed_out" },
      createLands: true,
    },
    profiles: "none",
  },
  {
    ...base,
    id: "create-refused-other",
    title: "Profile creation refused for another reason",
    summary:
      "No profile exists, and every creation is refused with a code the shell does not name.",
    signIn: {
      status: signedOut,
      submit: { kind: "accept" },
      profile: null,
      create: {
        kind: "refuse",
        code: "REFUSED_PROFILE_REGISTRATION",
        retryAfterSeconds: null,
      },
    },
    profiles: "none",
  },
  {
    ...base,
    id: "profiles-read-once",
    title: "Profiles readable once",
    summary:
      "Several profiles, listed by the first read and unreadable afterwards.",
    signIn: { status: signedOut, submit: { kind: "accept" } },
    profiles: "once",
  },
  {
    ...base,
    id: "odd-names",
    title: "A profile the host will not name",
    summary:
      "Several profiles, one under a name the product's command line would rewrite: it is listed, and opened only in the TUI.",
    signIn: { status: signedOut, submit: { kind: "accept" } },
    profiles: "odd",
  },
  {
    ...base,
    id: "choose-profile",
    title: "Several profiles, none selected",
    summary:
      "Profiles exist and the product has none selected: the person chooses one before a password can be sent.",
    signIn: { status: signedOut, submit: { kind: "accept" }, profile: null },
  },
  {
    ...base,
    id: "one-profile",
    title: "One profile",
    summary:
      "The only profile on this computer: it is named, with nothing to choose.",
    signIn: { status: signedOut, submit: { kind: "accept" } },
    profiles: "one",
  },
  {
    ...base,
    id: "profiles-unreadable",
    title: "Profiles unreadable",
    summary:
      "The status names a profile but the list of profiles cannot be read: sign-in goes to the named one.",
    signIn: { status: signedOut, submit: { kind: "accept" } },
    profiles: "unreadable",
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
    id: "runtime-starting",
    title: "Runtime starting in background",
    summary:
      "The desktop stays usable while the automatically launched runtime prepares services.",
    signIn: servicesDown,
    profiles: "one",
    terminals: "silent",
    manager: { result: "dispatched", autoDispatched: true, readyAfterReads: 5 },
  },
  {
    ...base,
    id: "runtime-startup-failed",
    title: "Runtime startup status failed",
    summary:
      "The native readiness read fails rather than confirming a ready runtime.",
    signIn: { ...servicesDown, statusFailure: "timed_out" },
    profiles: "one",
    terminals: "silent",
    manager: { result: "dispatched", autoDispatched: true },
  },
  {
    ...base,
    id: "runtime-startup-stalled",
    title: "Runtime startup status stalled",
    summary:
      "The initial availability read never answers; the startup deadline exposes recovery.",
    signIn: { ...servicesDown, statusPending: true },
    profiles: "one",
    terminals: "silent",
    manager: { result: "dispatched", autoDispatched: true },
  },
  {
    ...base,
    id: "manager-recovers",
    title: "Manager restores services",
    summary:
      "Services are down. Starting the manager waits four seconds; later status reads restore the sign-in form.",
    signIn: servicesDown,
    profiles: "one",
    terminals: "silent",
    manager: { result: "dispatched", delayMs: 4_000, readyAfterReads: 3 },
  },
  {
    ...base,
    id: "manager-pending",
    title: "Manager dispatch pending",
    summary:
      "The manager-start request never answers; its pending button stays up while availability reads continue.",
    signIn: servicesDown,
    profiles: "one",
    terminals: "silent",
    manager: { result: "pending" },
  },
  {
    ...base,
    id: "manager-failed",
    title: "Manager dispatch failed",
    summary:
      "The manager-start request fails with the host's typed spawn_failed refusal.",
    signIn: servicesDown,
    profiles: "one",
    terminals: "silent",
    manager: { result: { code: "spawn_failed" } },
  },
  {
    ...base,
    id: "manager-unmanaged",
    title: "Manager unavailable in an unmanaged package",
    summary:
      "The manager-start request reports an unmanaged package; services remain down.",
    signIn: servicesDown,
    profiles: "one",
    terminals: "silent",
    manager: { result: "unmanaged" },
  },
  {
    ...base,
    id: "manager-unsupported",
    title: "Manager dispatch unsupported",
    summary:
      "The manager-start request reports an unsupported platform; services remain down.",
    signIn: servicesDown,
    profiles: "one",
    terminals: "silent",
    manager: { result: "unsupported" },
  },
  {
    ...base,
    id: "manager-still-down",
    title: "Manager dispatched, services remain down",
    summary:
      "The manager-start request is dispatched but availability reads keep reporting services down through the bounded wait.",
    signIn: servicesDown,
    profiles: "one",
    terminals: "silent",
    manager: { result: "dispatched" },
  },
  {
    ...base,
    id: "manager-readiness-delayed",
    title: "Manager readiness answer delayed",
    summary:
      "Services are down. Dispatch succeeds, but the ready status answer arrives five seconds later.",
    signIn: servicesDown,
    profiles: "one",
    terminals: "silent",
    manager: {
      result: "dispatched",
      readyAfterReads: 1,
      readyReadDelayMs: 5_000,
    },
  },
  {
    ...base,
    id: "manager-retry-delayed",
    title: "Manager retry answer delayed",
    summary:
      "Each dispatch fails after four seconds, so a repeated retry can be exercised while its answer is pending.",
    signIn: servicesDown,
    profiles: "one",
    terminals: "silent",
    manager: { result: { code: "spawn_failed" }, delayMs: 4_000 },
  },
  {
    ...base,
    id: "manager-status-rejected",
    title: "Manager status read rejected",
    summary:
      "Services are initially down. Dispatch succeeds, but subsequent availability reads fail with timed_out.",
    signIn: servicesDown,
    profiles: "one",
    terminals: "silent",
    manager: {
      result: "dispatched",
      statusFailureAfterDispatch: "timed_out",
    },
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
    id: "manager-log-missing",
    title: "Manager log missing",
    summary:
      "Python records remain available while the manager log is missing.",
    managerLog: "missing",
    signIn: {
      status: { ...signedOut, state: "present" },
      submit: { kind: "accept" },
    },
  },
  {
    ...base,
    id: "manager-log-unreadable",
    title: "Manager log unreadable",
    summary:
      "Python records remain available while the manager log cannot be read.",
    managerLog: "unreadable",
    signIn: {
      status: { ...signedOut, state: "present" },
      submit: { kind: "accept" },
    },
  },
  {
    ...base,
    id: "manager-log-rejected",
    title: "Manager log rows rejected",
    summary:
      "The manager log reports refused diagnostic rows without revealing their content.",
    managerLog: "rejected",
    signIn: {
      status: { ...signedOut, state: "present" },
      submit: { kind: "accept" },
    },
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
