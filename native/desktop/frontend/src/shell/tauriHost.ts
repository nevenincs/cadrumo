import { Channel, invoke } from "@tauri-apps/api/core";
import type {
  HostCommand,
  HostCommands,
  ContextMenuItem,
  HostResult,
  LogBatch,
  ShellToken,
} from "../ipc/contract";
import type { Host } from "./host";
import { openTauriTerminal } from "./tauriTerminal";

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
    openTerminal: (kind, size, listener) =>
      token
        ? openTauriTerminal(token, kind, size, listener)
        : Promise.reject(
            new Error("The desktop host did not provide a launch token."),
          ),
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
    async showMenu(items: ContextMenuItem[], at?: { x: number; y: number }) {
      const { chosen } = await call(
        "shell_context_menu",
        at ? { items, x: at.x, y: at.y } : { items },
      );
      return chosen;
    },
    openExternal: (url) => call("open_external", { url }).then(() => undefined),
  };
}
