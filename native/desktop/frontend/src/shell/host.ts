// The shell's one port to the desktop host. Components depend on this
// interface only; the Tauri adapter implements it over the published IPC
// contract, and the browser host below stands in when there is no host at all
// (vite preview and browser-mode tests). The browser host fabricates nothing:
// every backend capability reports itself unavailable. Shapes the host
// publishes come from the IPC contract; the terminal shapes below stand until
// the contract's terminal block is published.

import type {
  AboutInfo,
  DesktopEnvironment,
  DesktopLanguage,
  DesktopSetup,
  LogBatch,
  ManagerStatus,
  ManagerSignal,
  SignInStatus,
  SignInSignal,
  SignInResult,
  SignOutResult,
  SetupCheckMode,
  SetupItemId,
  SetupModelDownload,
  SetupRemoval,
  WindowAction,
  WindowPresentation,
} from "../ipc/contract";
import type { ProfileAccounts } from "./profiles";
import type { AgentAccess } from "./agentAccess";
import type { AgentSession } from "./agentSession";
import type { AgentViews } from "./agentViews";
import type { ProviderSettings } from "./providerSettings";
import type { ProfileViews } from "./views";

export type TerminalKind = "console" | "python" | "tui";

export type AttendanceCandidate = {
  attendance_id: string;
  process_id: number | null;
  image_path: string | null;
  frontend: string;
  expires_at: string;
  scope: {
    operations: string[];
    actions: string[];
    periods: unknown[] | null;
    disclosures: unknown[];
    disclosure_categories: unknown[];
    allow_network: boolean;
    allow_changes_records: boolean;
    allow_delegation: boolean;
    allow_period_independent: boolean;
  };
};
export type Attendance = {
  inventory(): Promise<{ candidates: AttendanceCandidate[] }>;
  decide(id: string, approve: boolean): Promise<void>;
  /** Calls `changed` whenever the asks pending for the person may have
   * changed; the caller reads the inventory again. Resolves to unsubscribe. */
  observe(changed: () => void): Promise<() => void>;
};

export type TerminalEvent =
  /** `drawn` reports that the terminal has rendered these bytes; the host
   * withholds further output until rendered bytes are reported. */
  | { type: "data"; bytes: Uint8Array; drawn: () => void }
  | { type: "started" }
  | { type: "exited"; code: number | null }
  | { type: "failed"; message: string };

export type TerminalSession = {
  write(bytes: Uint8Array): Promise<void>;
  resize(cols: number, rows: number): Promise<void>;
  /** Stops pending writes and settles the session. */
  close(): Promise<void>;
};

/**
 * Component setup for the signed-in profile: the browser and the local AI.
 * The profile's Google account rides the same session and snapshot, but is
 * signed into and out of on its own, never as setup. Every method answers the
 * current `DesktopSetup`; a refusal rejects with `{ code: SetupRefusalCode }`.
 * A plan never downloads before `answer` approves it.
 */
export type Setup = {
  read(): Promise<DesktopSetup>;
  check(mode: SetupCheckMode): Promise<DesktopSetup>;
  /** A full check of `items`, or of every item when null. */
  verify(items: SetupItemId[] | null): Promise<DesktopSetup>;
  /** Plans setup of one `item`, beside any other item's setup. Resume after
   * an interruption is a new start with `resume`: the unchanged plan the
   * person approved before needs no second approval. */
  start(
    item: SetupItemId,
    options?: { resume?: boolean; download?: SetupModelDownload },
  ): Promise<DesktopSetup>;
  /** Answers the plan whose `plan_digest` the review showed. */
  answer(
    operationId: string,
    planDigest: string,
    decision: "apply" | "reject",
  ): Promise<DesktopSetup>;
  cancel(operationId: string): Promise<DesktopSetup>;
  /** Removes the local model `model`, which no role may still select: the
   * roles that name it are cleared first. */
  removeModel(model: string): Promise<DesktopSetup>;
  /** Removes the browser, or the local AI or its program alone, from this
   * computer. */
  remove(removal: SetupRemoval): Promise<DesktopSetup>;
  /** Opens Google's own sign-in page for the profile. */
  signInGoogle(): Promise<DesktopSetup>;
  /** Removes the profile's stored Google sign-in. */
  signOutGoogle(): Promise<DesktopSetup>;
  /** Calls `listener` with the current state, then on every change, until
   * the returned function unsubscribes. */
  observe(listener: (state: DesktopSetup) => void): Promise<() => void>;
};

export interface Host {
  readonly censo?: import("./profileCenso").CensoPort;
  readonly userProfile?: import("./userProfile").UserProfilePort;
  readonly aeatSync?: import("./aeatSync").AeatSyncPort;
  readonly aeatSyncResults?: import("./aeatSyncResults").AeatSyncResultsPort;
  readonly aeatSyncRun?: import("./aeatSyncRun").AeatSyncRunPort;
  readonly aeatSyncPrepare?: import("./aeatSyncPrepare").AeatSyncPreparePort;
  readonly attendance?: Attendance;
  /** Absent in a browser: native window behavior is never simulated as real. */
  readonly window?: {
    action(action: WindowAction): Promise<void>;
    observe(listener: (state: WindowPresentation) => void): Promise<() => void>;
    /** Asks the page before a close the system raised; the page answers
     * with "close_now" or "keep_open". */
    guardClose?(asked: () => void): Promise<() => void>;
  };
  /** False when no desktop host exists (browser preview). */
  readonly available: boolean;
  environment(): Promise<DesktopEnvironment>;
  /** What this installation is, where the host reads it from the package. */
  about?(): Promise<AboutInfo>;
  readonly language?: {
    read(): Promise<DesktopLanguage>;
    set(language: string): Promise<DesktopLanguage>;
    observe(listener: (state: DesktopLanguage) => void): Promise<() => void>;
  };
  signInStatus(): Promise<SignInStatus>;
  /** Reports a person gesture; background observations must never call it. */
  noteActivity?(): Promise<void>;
  /** Public observations only; cleanup cannot remove a newer subscriber. */
  observeSignIn?(listener: (signal: SignInSignal) => void): Promise<() => void>;
  managerStatus?(): Promise<ManagerStatus>;
  observeManager?(
    listener: (signal: ManagerSignal) => void,
  ): Promise<() => void>;
  /** Requests the independent manager, without authenticating or owning the runtime. */
  startManager?(): Promise<"dispatched" | "unsupported">;
  installManager?(
    scope: "user" | "machine",
  ): Promise<"dispatched" | "unsupported">;
  /** Signs in to `profile`, by its label, or to the profile the product
   * has selected where none is named. */
  signIn(password: Uint8Array, profile?: string): Promise<SignInResult>;
  signOut(): Promise<SignOutResult>;
  openTerminal(
    kind: TerminalKind,
    size: { cols: number; rows: number },
    listener: (event: TerminalEvent) => void,
  ): Promise<TerminalSession>;
  subscribeLogs(listener: (batch: LogBatch) => void): Promise<() => void>;
  readClipboard(): Promise<string>;
  writeClipboard(text: string): Promise<void>;
  /** Exports a selection to a new file in Downloads and returns its path. */
  exportLogs?(text: string): Promise<string>;
  /** Copies a log selection with the larger bounded log-transfer limit. */
  copyLogs?(text: string): Promise<void>;
  revealLogs?(): Promise<void>;
  openExternal(url: string): Promise<void>;
  /** The profiles on this computer, to choose from and to add to, where
   * this host offers them. Without them the shell signs in to the one
   * profile the status names. */
  readonly profiles?: ProfileAccounts;
  /** Read-only views of the signed-in profile, where this host offers any.
   * Without them the shell shows no way into a view. */
  readonly views?: ProfileViews;
  /** The signed-in profile's ledger: its registered operations, the files
   * the person picks for them and the reviews they pause for, where this
   * host offers them. Without it the shell shows no Ledger page. */
  readonly ledger?: import("./ledger").LedgerPort;
  /** The signed-in profile's declarations: the list, each one's form and
   * help, its registered modelo operations and the files they read and
   * write, where this host offers them. Without it the shell shows no
   * Declarations page. */
  readonly modelo?: import("./modelo").ModeloPort;
  /** The Sede in a browser page of the profile's own worker, streamed to the
   * window as images, where this host offers it. Without it the shell shows
   * no Browser page. */
  readonly sedeView?: import("./sedeView").SedeViewPort;
  /** What the agent column reads, where this host serves the agent.
   * Without it each of the column's views says it is not available yet. */
  readonly agent?: AgentViews;
  /** Working with the agent: its state, the catalog of what can run it,
   * sending, the live stream and what a reply waits on the person for.
   * Without it the column can read but not send, and says so. */
  readonly agentSession?: AgentSession;
  /** The signed-in profile's model providers and their keys, where this
   * host offers them. A key is handed to it once and never comes back. */
  readonly providerSettings?: ProviderSettings;
  /** The keys the signed-in profile issued to agents outside Cadrumo, which
   * reach it through its MCP server, where this host offers them. */
  readonly agentAccess?: AgentAccess;
  /** Component setup, where this host offers it. Without it the shell shows
   * no Components section and no setup actions. */
  readonly setup?: Setup;
}

export class HostUnavailable extends Error {
  constructor() {
    super("host-unavailable");
    this.name = "HostUnavailable";
  }
}

/** Browser stand-in. A test may supply a documentation entry with `?docs=`. */
export function browserHost(location: Location): Host {
  const unavailable = () => Promise.reject(new HostUnavailable());
  return {
    available: false,
    environment() {
      const docs = new URLSearchParams(location.search).get("docs");
      if (!docs) return unavailable();
      let entry: URL;
      try {
        entry = new URL(docs);
      } catch {
        return unavailable();
      }
      const lang = new URLSearchParams(location.search).get("lang") ?? "en";
      return Promise.resolve({
        outputLanguage: lang,
        logLevel: "INFO",
        docs: {
          state: "bundled",
          origin: entry.origin,
          languages: [{ code: lang, entry: entry.href }],
        },
      });
    },
    openTerminal: unavailable,
    signInStatus: unavailable,
    signIn: unavailable,
    signOut: unavailable,
    subscribeLogs: unavailable,
    readClipboard: () =>
      navigator.clipboard?.readText
        ? navigator.clipboard.readText()
        : unavailable(),
    writeClipboard: (text) =>
      navigator.clipboard?.writeText
        ? navigator.clipboard.writeText(text)
        : unavailable(),
    openExternal: unavailable,
  };
}

/** Available before the package and normal desktop services are assembled. */
export interface StartupHost {
  begin(): Promise<void>;
  status(): Promise<import("../ipc/contract").StartupProgress>;
}
