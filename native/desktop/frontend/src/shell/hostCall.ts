import {
  invoke,
  type InvokeArgs,
  type InvokeOptions,
} from "@tauri-apps/api/core";
import { notifyInternalFailure } from "./internalFailures";
import type {
  HostCommand,
  HostCommands,
  HostResult,
  ShellToken,
} from "../ipc/contract";

type Diagnostic = Omit<
  HostCommands["desktop_frontend_diagnostic"]["args"]["report"],
  "dropped"
>;
let reporting = 0;
let dropped = 0;
let installed = false;
let diagnosticToken: ShellToken | null = null;

/** Only closed metadata leaves this document; exception text and console
 * arguments may contain passwords, tax data or terminal bytes. */
export function reportDiagnostic(
  token: ShellToken | null,
  report: Diagnostic,
): void {
  if (!token) return;
  if (reporting >= 16) {
    dropped = Math.min(4294967295, dropped + 1);
    return;
  }
  reporting++;
  const omitted = dropped;
  dropped = 0;
  void invoke("desktop_frontend_diagnostic", {
    report: { ...report, dropped: omitted },
    token,
  })
    .catch(() => {
      dropped = Math.min(4294967295, dropped + omitted + 1);
      notifyInternalFailure();
    })
    .finally(() => {
      reporting--;
    });
}

export function installDiagnostics(token: ShellToken | null): void {
  if (installed || !token) return;
  installed = true;
  diagnosticToken = token;
  const report = (event: Diagnostic["event"], level: Diagnostic["level"]) => {
    reportDiagnostic(token, { event, level, command: null, code: null });
    if (level === "ERROR" || level === "CRITICAL") notifyInternalFailure();
  };
  window.addEventListener("error", (error) => {
    reportDiagnostic(token, {
      event: "uncaught_error",
      level: "ERROR",
      command: null,
      code: null,
      line: error.lineno,
      column: error.colno,
    });
    notifyInternalFailure();
  });
  window.addEventListener("unhandledrejection", () =>
    report("unhandled_rejection", "ERROR"),
  );
  for (const [method, level] of [
    ["error", "ERROR"],
    ["warn", "WARNING"],
    ["info", "INFO"],
    ["debug", "DEBUG"],
    ["log", "INFO"],
  ] as const) {
    const original = console[method].bind(console);
    console[method] = (...args: unknown[]) => {
      original(...args);
      report("console", level);
    };
  }
}

export function reportReactError(): void {
  reportDiagnostic(diagnosticToken, {
    event: "react_error",
    level: "ERROR",
    command: null,
    code: null,
  });
  notifyInternalFailure();
}

export async function observedInvoke<T>(
  token: ShellToken | null,
  command: string,
  args?: InvokeArgs,
  options?: InvokeOptions,
): Promise<T> {
  try {
    return await invoke<T>(command, args, options);
  } catch (error) {
    const code =
      error &&
      typeof error === "object" &&
      "code" in error &&
      typeof error.code === "string"
        ? error.code
        : null;
    // Backpressure and deliberate cancellation are expected control flow.
    if (code !== "queue_full" && code !== "installation_cancelled") {
      reportDiagnostic(token, {
        event: "command_rejected",
        level: "ERROR",
        command,
        code,
      });
      // Typed refusals are worded by their owning view. Missing metadata and
      // native faults must also surface when a caller deliberately catches.
      if (
        code === null ||
        [
          "panic",
          "webview_failed",
          "lock_poisoned",
          "log_unavailable",
        ].includes(code)
      )
        notifyInternalFailure();
    }
    throw error;
  }
}

/** A JSON-argument host command, typed end to end by the published contract. */
export type HostCall = <C extends HostCommand>(
  command: C,
  args: Omit<HostCommands[C]["args"], "token">,
) => Promise<HostResult<C>>;

/** Every JSON command goes through this call, which adds the launch token.
 * Typing the arguments by `HostCommands` makes a misnamed argument a compile
 * error instead of a refusal at run time. */
export function hostCall(token: ShellToken | null): HostCall {
  installDiagnostics(token);
  return (command, args) =>
    token
      ? observedInvoke(token, command, { ...args, token })
      : Promise.reject(
          new Error("The desktop host did not provide a launch token."),
        );
}
