import { Channel, invoke } from "@tauri-apps/api/core";
import type { ContextMenuItem, LogBatch, ShellToken } from "../ipc/contract";
import type { Host } from "./host";
import { hostCall } from "./hostCall";
import { openTauriTerminal } from "./tauriTerminal";

const TOKEN_PATTERN = /^[0-9a-f]{64}$/;
const PROFILE_HEADER = "x-cadrumo-profile";

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
  const call = hostCall(token);
  // A command whose body is a password and nothing else. The token travels
  // as a header, and so does the label of the profile it names,
  // percent-encoded, since a header carries no other text.
  const submit = <Result>(
    command: "sign_in_submit" | "profile_create",
    password: Uint8Array,
    profile?: string,
  ): Promise<Result> =>
    token
      ? invoke<Result>(command, password, {
          headers: {
            "x-cadrumo-token": token,
            ...(profile === undefined
              ? {}
              : { [PROFILE_HEADER]: encodeURIComponent(profile) }),
          },
        })
      : Promise.reject(new Error("Missing desktop launch token."));

  return {
    available: true,
    nativeMenus: true,
    environment: () => call("desktop_environment", {}),
    signInStatus: () => call("sign_in_status", {}),
    signOut: () => call("sign_out", {}),
    signIn: (password, profile) => submit("sign_in_submit", password, profile),
    profiles: {
      list: () => call("profile_list", {}),
      create: (name, password) => submit("profile_create", password, name),
    },
    openTerminal: (kind, size, listener) =>
      token
        ? openTauriTerminal(token, call, kind, size, listener)
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
