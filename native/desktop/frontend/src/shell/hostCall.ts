import {
  invoke,
  type InvokeArgs,
  type InvokeOptions,
} from "@tauri-apps/api/core";
import {
  consoleSummary,
  errorEventSummary,
  isResizeObserverNotice,
  rejectionSummary,
} from "./diagnosticSummary";
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
  window.addEventListener("error", (event) => {
    // The browser's own notice that a ResizeObserver delivers the rest of a
    // frame's resizes in the next one: nothing failed.
    const notice = isResizeObserverNotice(event);
    reportDiagnostic(token, {
      event: "uncaught_error",
      level: notice ? "WARNING" : "ERROR",
      command: null,
      code: null,
      ...errorEventSummary(event),
    });
    if (!notice) notifyInternalFailure();
  });
  window.addEventListener("unhandledrejection", (event) => {
    reportDiagnostic(token, {
      event: "unhandled_rejection",
      level: "ERROR",
      command: null,
      code: null,
      ...rejectionSummary(event.reason),
    });
    notifyInternalFailure();
  });
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
      // The stack is taken here, so its first frame is this wrapper and its
      // second the caller.
      reportDiagnostic(token, {
        event: "console",
        level,
        command: null,
        code: null,
        ...consoleSummary(args, new Error().stack),
      });
      if (level === "ERROR") notifyInternalFailure();
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

/** What a caller knows of a call it has made. The level of a refusal's record
 * follows its retry class and whether the ask is actually coming, never the
 * command or the wording of the refusal. */
export type CallPlan = {
  /** Whether a refusal with this code is one that passes by waiting. */
  retryable?(code: string): boolean;
  /** Whether the caller will ask again after this refusal. */
  scheduled?(): boolean;
  /** Whether the window learned that the signed-in session ended after the
   * call was made. Nothing is left that wants its answer, so a refusal of any
   * kind is dropped without a record. */
  sessionEnded?(): boolean;
};

/** Refusals the host answers for what the person did or for where the
 * session stands, which the owning view words and offers a way on from. */
const REFUSAL_LEVEL: Readonly<Record<string, "WARNING">> = {
  // The runtime or host refused the request as asked; nothing failed. A
  // session that ended is not here: one the window did not see coming is an
  // error, and one it saw is dropped through `sessionEnded`.
  refused: "WARNING",
  review_changed: "WARNING",
  conflict: "WARNING",
  too_large: "WARNING",
};

function rejectionLevel(
  code: string | null,
  plan: CallPlan | undefined,
): "WARNING" | "ERROR" {
  if (code === null) return "ERROR";
  if (plan?.retryable?.(code) && plan.scheduled?.()) return "WARNING";
  return REFUSAL_LEVEL[code] ?? "ERROR";
}

export async function observedInvoke<T>(
  token: ShellToken | null,
  command: string,
  args?: InvokeArgs,
  options?: InvokeOptions,
  plan?: CallPlan,
): Promise<T> {
  try {
    return await invoke<T>(command, args, options);
  } catch (error) {
    const field = (name: "code" | "reason") =>
      error &&
      typeof error === "object" &&
      name in error &&
      typeof (error as Record<string, unknown>)[name] === "string"
        ? ((error as Record<string, unknown>)[name] as string)
        : null;
    const code = field("code");
    const reason = field("reason");
    // The session the call belonged to ended before it answered.
    if (plan?.sessionEnded?.()) throw error;
    // Backpressure and deliberate cancellation are expected control flow.
    if (code !== "queue_full" && code !== "installation_cancelled") {
      reportDiagnostic(token, {
        event: "command_rejected",
        level: rejectionLevel(code, plan),
        command,
        code,
        ...(reason !== null ? { reason } : {}),
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
  plan?: CallPlan,
) => Promise<HostResult<C>>;

/** Every JSON command goes through this call, which adds the launch token.
 * Typing the arguments by `HostCommands` makes a misnamed argument a compile
 * error instead of a refusal at run time. */
export function hostCall(token: ShellToken | null): HostCall {
  installDiagnostics(token);
  return (command, args, plan) =>
    token
      ? observedInvoke(token, command, { ...args, token }, undefined, plan)
      : Promise.reject(
          new Error("The desktop host did not provide a launch token."),
        );
}
