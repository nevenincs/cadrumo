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
} from "../ipc/contract";

export type TerminalKind = "console" | "python" | "tui";

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
  /** False when no desktop host exists (browser preview). */
  readonly available: boolean;
  /** Whether menus are drawn by the operating system. */
  readonly nativeMenus: boolean;
  environment(): Promise<DesktopEnvironment>;
  openTerminal(
    kind: TerminalKind,
    size: { cols: number; rows: number },
    listener: (event: TerminalEvent) => void,
  ): Promise<TerminalSession>;
  subscribeLogs(listener: (batch: LogBatch) => void): Promise<() => void>;
  readClipboard(): Promise<string>;
  writeClipboard(text: string): Promise<void>;
  /** Resolves to the chosen item id, or null when dismissed. Omit `at` for a
   * pointer-opened menu so the host places it at the cursor. */
  showMenu(
    items: ContextMenuItem[],
    at?: { x: number; y: number },
  ): Promise<string | null>;
  openExternal(url: string): Promise<void>;
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
        docs: {
          origin: entry.origin,
          languages: [{ code: lang, entry: entry.href }],
        },
      });
    },
    openTerminal: unavailable,
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
