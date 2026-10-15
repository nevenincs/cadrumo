// The shell's one port to the desktop host. Components depend on this
// interface only; the Tauri adapter implements it over the published IPC
// contract, and the browser host below stands in when there is no host at all
// (vite preview and browser-mode tests). The browser host fabricates nothing:
// every backend capability reports itself unavailable. Shapes the host
// publishes come from the IPC contract; the terminal shapes below stand until
// the contract's terminal block is published.

import type {
  ContextMenuItem,
  DesktopEnvironment,
  LogBatch,
  ManagerStatus,
  ManagerSignal,
  SignInStatus,
  SignInSignal,
  SignInResult,
  SignOutResult,
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

export interface Host {
  readonly attendance?: Attendance;
  /** Absent in a browser: native window behavior is never simulated as real. */
  readonly window?: {
    action(action: WindowAction): Promise<void>;
    observe(listener: (state: WindowPresentation) => void): Promise<() => void>;
  };
  /** False when no desktop host exists (browser preview). */
  readonly available: boolean;
  /** Whether menus are drawn by the operating system. */
  readonly nativeMenus: boolean;
  environment(): Promise<DesktopEnvironment>;
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
  /** Resolves to the chosen item id, or null when dismissed. Omit `at` for a
   * pointer-opened menu so the host places it at the cursor. */
  showMenu(
    items: ContextMenuItem[],
    at?: { x: number; y: number },
  ): Promise<string | null>;
  openExternal(url: string): Promise<void>;
  /** The profiles on this computer, to choose from and to add to, where
   * this host offers them. Without them the shell signs in to the one
   * profile the status names. */
  readonly profiles?: ProfileAccounts;
  /** Read-only views of the signed-in profile, where this host offers any.
   * Without them the shell shows no way into a view. */
  readonly views?: ProfileViews;
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
    nativeMenus: false,
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
    showMenu: unavailable,
    openExternal: unavailable,
  };
}

/** Available before the package and normal desktop services are assembled. */
export interface StartupHost {
  begin(): Promise<void>;
  status(): Promise<import("../ipc/contract").StartupProgress>;
}
