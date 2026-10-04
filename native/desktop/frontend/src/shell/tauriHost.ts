import { Channel, invoke } from "@tauri-apps/api/core";
import type {
  HostCommand,
  HostCommands,
  HostResult,
  LogBatch,
  ShellToken,
} from "../ipc/contract";
import type { Host, MenuItem } from "./host";

const TOKEN_PATTERN = /^[0-9a-f]{64}$/;

// The host defines the token getter only on the shell's top frame, and it
// answers once. Read it here, at module load, and keep it in this closure: it
// never reaches the documentation frame, a URL, storage or a log.
function takeToken(): ShellToken | null {
  const token = window.__CADRUMO_SHELL__?.token;
  return typeof token === "string" && TOKEN_PATTERN.test(token)
    ? (token as ShellToken)
    : null;
}

export class TerminalContractPending extends Error {
  constructor() {
    super("terminal-contract-pending");
    this.name = "TerminalContractPending";
  }
}

/** The desktop host, reached only through the published command contract. */
export function tauriHost(): Host {
  const token = takeToken();
  const call = <C extends HostCommand>(
    command: C,
    args: Omit<HostCommands[C]["args"], "token">,
  ): Promise<HostResult<C>> =>
    token
      ? invoke<HostResult<C>>(command, { ...args, token })
      : Promise.reject(
          new Error("The desktop host did not provide a launch token."),
        );

  return {
    available: true,
    nativeMenus: true,
    environment: () => call("desktop_environment", {}),
    // Terminal commands are published with the terminal frame encoding.
    openTerminal: () => Promise.reject(new TerminalContractPending()),
    async subscribeLogs(listener: (batch: LogBatch) => void) {
      const records = new Channel<LogBatch>();
      records.onmessage = listener;
      const { subscription } = await call("logs_subscribe", { records });
      return () => {
        void call("logs_unsubscribe", { subscription }).catch(() => undefined);
      };
    },
    readClipboard: () =>
      call("shell_clipboard_read", {}).then(({ text }) => text),
    writeClipboard: (text) =>
      call("shell_clipboard_write", { text }).then(() => undefined),
    async showMenu(items: MenuItem[], at?: { x: number; y: number }) {
      const entries = items.flatMap((item) =>
        "separator" in item
          ? []
          : [{ id: item.id, label: item.label, enabled: item.enabled }],
      );
      const { chosen } = await call(
        "shell_context_menu",
        at ? { items: entries, x: at.x, y: at.y } : { items: entries },
      );
      return chosen;
    },
    openExternal: (url) => call("open_external", { url }).then(() => undefined),
  };
}
