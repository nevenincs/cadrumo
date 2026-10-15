import { isTauri } from "@tauri-apps/api/core";
import type { ShellToken } from "../ipc/contract";
import type { StartupHost } from "./host";
import { hostCall } from "./hostCall";

export function tauriStartup(): StartupHost | null {
  if (!isTauri()) return null;
  const token = window.__CADRUMO_SHELL__?.token;
  const call = hostCall(
    typeof token === "string" && /^[0-9a-f]{64}$/.test(token)
      ? (token as ShellToken)
      : null,
  );
  return {
    begin: () => call("startup_begin", {}),
    status: () => call("startup_status", {}),
  };
}
