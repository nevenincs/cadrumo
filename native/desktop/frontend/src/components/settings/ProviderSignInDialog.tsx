import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/ui/password-input";
import { Spinner } from "@/components/ui/spinner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { failureCode } from "../../errors";
import { useStrings, type Translate } from "../../shell/strings";
import type { ProviderSignIn } from "../../shell/providerSettings";
import type {
  ProviderSignInEvent,
  ProviderSignInMethod,
  ProviderSignInSnapshot,
} from "../../shell/providerSettingsContract";
import {
  cliStateCause,
  logRef,
  nextStep,
  signInCause,
  type CliStateCause,
  type NextStep,
  type SignInCause,
} from "../../shell/providerSignInWords";
import { SignInAdvice } from "./SignInAdvice";
import type { ProviderStatus } from "./types";

const EVENTS: readonly ProviderSignInEvent[] = [
  "starting",
  "started",
  "browser_action",
  "authorization_code_required",
  "succeeded",
  "cancelled",
  "failed",
];
const ACTIVE = new Set<ProviderSignInEvent>([
  "starting",
  "started",
  "browser_action",
  "authorization_code_required",
]);
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const REVISION = /^[0-9a-f]{64}$/;
const LIFETIME_MS = 300_000;
const OBSERVE_MS = 1_000;
/** Status reads in a row that may fail for a passing reason before the
 * attempt is given up and the failure is said, rather than waited out until
 * the attempt's lifetime ends. */
const STATUS_MISSES = 5;
/** How far apart, and for how long in all, a start refused while the agent
 * is being stopped for a terminal sign-in is tried again on its own: the
 * service retires the agent and refuses until it is gone, so the window asks
 * again with the freshly read revision, and after the bound it offers the
 * person's own retry. */
const AGENT_STOP_RETRY_MS = 3_000;
const AGENT_STOP_WAIT_MS = 60_000;
const TRANSIENT_STATUS_FAILURES = new Set([
  "read_failed",
  "timed_out",
  "timeout",
  "host_disconnected",
  "runtime_unavailable",
  "unknown",
]);

type ProviderSignInFailureCode =
  | "not_signed_in"
  | "signed_out"
  | "profile_required"
  | "profile_locked"
  | "person_act_required"
  | "runtime_unavailable"
  | "catalog_unavailable"
  | "revision_conflict"
  | "timeout"
  | "expired"
  | "open_external_failed"
  | "cancel_failed"
  | "provider_unavailable"
  | "busy"
  | "unsupported_flow"
  | "host_disconnected"
  | "cleanup_failed"
  | "invalid_request"
  | "provider_sign_in_protocol_error"
  | "provider_error"
  | "unknown";

const FAILURE_CODES: ReadonlySet<string> = new Set<ProviderSignInFailureCode>([
  "not_signed_in",
  "signed_out",
  "profile_required",
  "profile_locked",
  "person_act_required",
  "runtime_unavailable",
  "catalog_unavailable",
  "revision_conflict",
  "timeout",
  "expired",
  "open_external_failed",
  "cancel_failed",
  "provider_unavailable",
  "busy",
  "unsupported_flow",
  "host_disconnected",
  "cleanup_failed",
  "invalid_request",
  "provider_sign_in_protocol_error",
  "provider_error",
  "unknown",
]);

function isProviderSignInFailureCode(
  code: unknown,
): code is ProviderSignInFailureCode {
  return typeof code === "string" && FAILURE_CODES.has(code);
}

/** Why a failure happened and where the host logged it, in the closed words
 * a snapshot or a refusal carries; any other word is dropped. */
type FailureDetail = {
  cause?: SignInCause;
  next_step?: NextStep;
  status_cause?: CliStateCause;
  log_ref?: string;
};

type Failure = { code: ProviderSignInFailureCode; detail: FailureDetail };

function detailOf(value: object): FailureDetail {
  const raw = value as Record<string, unknown>;
  const cause = signInCause(raw.cause);
  const step = nextStep(raw.next_step);
  const statusCause = cliStateCause(raw.status_cause);
  const reference = logRef(raw.log_ref);
  return {
    ...(cause ? { cause } : {}),
    ...(step ? { next_step: step } : {}),
    ...(statusCause ? { status_cause: statusCause } : {}),
    ...(reference ? { log_ref: reference } : {}),
  };
}

/** A rejected call as the window words it: its code where the window names
 * it, else the closed reason it carries, with its cause and log reference. */
function rejectionOf(
  error: unknown,
  fallback: ProviderSignInFailureCode = "unknown",
): Failure {
  const raw: object = typeof error === "object" && error !== null ? error : {};
  const code = failureCode(error);
  const reason = (raw as { reason?: unknown }).reason;
  return {
    code:
      isProviderSignInFailureCode(code) && code !== "unknown"
        ? code
        : isProviderSignInFailureCode(reason) && reason !== "unknown"
          ? reason
          : fallback,
    detail: detailOf(raw),
  };
}

/** A missing status reply is not evidence that sign-in failed. Keep observing
 * this bounded attempt after transient bridge/runtime errors. */
function canRetryStatus(error: unknown): boolean {
  return TRANSIENT_STATUS_FAILURES.has(failureCode(error));
}

/** A start the service refused because it is stopping the agent for this
 * terminal sign-in: an expected step, not a fault. */
function agentStopping(failure: Failure | null): boolean {
  return (
    failure?.code === "busy" && failure.detail.cause === "agent_tree_running"
  );
}

function snapshotFailureCode(
  snapshot: ProviderSignInSnapshot | null,
): ProviderSignInFailureCode {
  return isProviderSignInFailureCode(snapshot?.reason)
    ? snapshot.reason
    : "unknown";
}

/** The last cause and log reference said of an attempt while it was live. */
type SeenDetail = { attemptId: string; detail: FailureDetail };

/** The window's own timeout of an attempt: it says what the service last said
 * of that attempt, and what the cancel answered, and nothing else. */
function timedOut(
  seen: SeenDetail | null,
  attemptId: string,
  answered: FailureDetail = {},
): Failure {
  return {
    code: "timeout",
    detail: {
      ...(seen?.attemptId === attemptId ? seen.detail : {}),
      ...answered,
    },
  };
}

function hasDetail(detail: FailureDetail): boolean {
  return Object.keys(detail).length > 0;
}

/** The failure a failed attempt's snapshot says, or none for another. */
function snapshotFailure(snapshot: ProviderSignInSnapshot): Failure | null {
  return snapshot.event === "failed"
    ? {
        code: snapshotFailureCode(snapshot),
        detail: detailOf(snapshot),
      }
    : null;
}

function hasControlCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const code = character.charCodeAt(0);
    return code <= 0x1f || code === 0x7f;
  });
}

function validAuthorizationCode(code: string): boolean {
  if (!/^[!-~]{1,2048}$/.test(code)) return false;
  let length =
    JSON.stringify({ version: 1, action: "auth_code", code: "" }).length + 1;
  for (const char of code) length += char === '"' || char === "\\" ? 2 : 1;
  return length <= 4096;
}

type Props = {
  open: boolean;
  identity: string | null;
  provider: ProviderStatus;
  revision: string;
  signIn: ProviderSignIn;
  methods: readonly ProviderSignInMethod[];
  /** The served console command template, for a failure whose next step is
   * to sign in from a console. */
  consoleSignInCommand?: string;
  onOpenChange: (open: boolean) => void;
  onTerminal: (providerId: string) => Promise<string | undefined>;
};

function safeUrl(value: unknown): string | undefined {
  if (
    typeof value !== "string" ||
    value.length > 8192 ||
    new TextEncoder().encode(value).byteLength > 8192
  )
    return undefined;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" && !parsed.username && !parsed.password
      ? value
      : undefined;
  } catch {
    return undefined;
  }
}

/** Reject malformed host answers and drop URL/code material from terminal states. */
function snapshotOf(
  value: unknown,
  providerId: string,
  expectedAttemptId?: string,
): ProviderSignInSnapshot {
  if (typeof value !== "object" || value === null)
    throw Object.assign(new Error("Invalid sign-in response."), {
      code: "provider_sign_in_protocol_error",
    });
  const raw = value as Partial<ProviderSignInSnapshot>;
  if (
    typeof raw.attempt_id !== "string" ||
    !UUID.test(raw.attempt_id) ||
    (expectedAttemptId !== undefined && raw.attempt_id !== expectedAttemptId) ||
    raw.provider !== providerId ||
    typeof raw.event !== "string" ||
    !EVENTS.includes(raw.event as ProviderSignInEvent)
  )
    throw Object.assign(new Error("Invalid sign-in response."), {
      code: "provider_sign_in_protocol_error",
    });

  const event = raw.event as ProviderSignInEvent;
  const terminal = !ACTIVE.has(event);
  const reason =
    (event === "failed" || event === "cancelled") &&
    isProviderSignInFailureCode(raw.reason)
      ? raw.reason
      : undefined;
  // Why and what next are the service's closed words, on a failed or
  // cancelled attempt only; any other word is dropped.
  const advised = event === "failed" || event === "cancelled";
  if (terminal)
    return {
      attempt_id: raw.attempt_id,
      provider: providerId,
      event,
      ...(reason ? { reason } : {}),
      ...(advised ? detailOf(raw) : {}),
    };

  // During cancellation the service may still report browser_action while it
  // finishes helper cleanup, but it has already removed the one-time URL.
  // Treat that as active progress with no browser action available.
  const url =
    event === "browser_action" || event === "authorization_code_required"
      ? safeUrl(raw.url)
      : undefined;
  const userCode =
    typeof raw.user_code === "string" &&
    raw.user_code.length <= 128 &&
    !hasControlCharacter(raw.user_code)
      ? raw.user_code
      : undefined;
  return {
    attempt_id: raw.attempt_id,
    provider: providerId,
    event,
    ...(reason ? { reason } : {}),
    ...detailOf(raw),
    ...(url ? { url } : {}),
    ...(userCode ? { user_code: userCode } : {}),
  };
}

function failureWords(
  t: Translate,
  failure: Failure,
  providerName: string,
  method: ProviderSignInMethod | null,
): string {
  if (agentStopping(failure))
    return t("desktop.providers.sign_in_agent_still_running", {
      provider: providerName,
    });
  switch (failure.code) {
    case "not_signed_in":
    case "signed_out":
    case "profile_required":
      return t("desktop.providers.sign_in_profile_required", {
        provider: providerName,
      });
    case "profile_locked":
      return t("desktop.providers.refused_profile_locked");
    case "person_act_required":
      return t("desktop.providers.refused_person_act_required");
    case "runtime_unavailable":
      return t("desktop.providers.refused_runtime_unavailable");
    case "catalog_unavailable":
      return t("desktop.providers.load_failed");
    case "revision_conflict":
      return t("desktop.providers.refused_revision_conflict");
    case "timeout":
    case "expired":
      return t("desktop.providers.sign_in_timeout");
    case "provider_unavailable":
      return t("desktop.providers.sign_in_provider_unavailable", {
        provider: providerName,
      });
    case "busy":
      return t("desktop.providers.sign_in_busy", { provider: providerName });
    case "unsupported_flow":
      return t(
        method === "device"
          ? "desktop.providers.sign_in_unsupported_device"
          : "desktop.providers.sign_in_unsupported_browser",
        { provider: providerName },
      );
    case "host_disconnected":
      return t("desktop.providers.sign_in_host_disconnected", {
        provider: providerName,
      });
    case "cleanup_failed":
      return t("desktop.providers.sign_in_cleanup_failed", {
        provider: providerName,
      });
    case "invalid_request":
    case "provider_sign_in_protocol_error":
      return t("desktop.providers.sign_in_invalid_request", {
        provider: providerName,
      });
    case "provider_error":
      return t("desktop.providers.sign_in_provider_error", {
        provider: providerName,
      });
    case "open_external_failed":
      return t("desktop.providers.sign_in_open_failed");
    case "cancel_failed":
      return t("desktop.providers.sign_in_cancel_failed");
    default:
      return t("desktop.providers.sign_in_failure");
  }
}

function activeWords(
  t: Translate,
  snapshot: ProviderSignInSnapshot,
  method: ProviderSignInMethod | null,
): string {
  switch (snapshot.event) {
    case "starting":
      return t("desktop.providers.sign_in_starting");
    case "started":
      return method === "device" && snapshot.user_code
        ? t("desktop.providers.sign_in_waiting_device")
        : t("desktop.providers.sign_in_waiting");
    case "browser_action":
      return method === "device" && snapshot.user_code
        ? t("desktop.providers.sign_in_waiting_device")
        : t("desktop.providers.sign_in_waiting");
    case "authorization_code_required":
      return t("desktop.providers.sign_in_code_prompt");
    case "succeeded":
    case "cancelled":
    case "failed":
      return "";
  }
}

/** The code is a secret: it stays hidden unless the person shows it, and it
 * is hidden again whenever the field is drawn anew. */
function AuthorizationCodeField({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const t = useStrings();
  const [revealed, setRevealed] = useState(false);
  return (
    <PasswordInput
      id="provider-authorization-code"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      revealed={revealed}
      onRevealedChange={setRevealed}
      showLabel={t("desktop.signin.show_code")}
      hideLabel={t("desktop.signin.hide_code")}
      autoComplete="one-time-code"
      maxLength={2048}
    />
  );
}

/**
 * A short-lived, attended sign-in. It observes only while this dialog is
 * mounted and open; closing or changing profile cancels the live attempt.
 */
export function ProviderSignInDialog({
  open,
  identity,
  provider,
  revision,
  signIn,
  methods,
  consoleSignInCommand,
  onOpenChange,
  onTerminal,
}: Props) {
  const t = useStrings();
  const [snapshot, setSnapshot] = useState<ProviderSignInSnapshot | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [method, setMethod] = useState<ProviderSignInMethod | null>(null);
  const [starting, setStarting] = useState(false);
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const submittedAttempt = useRef<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [retryRevision, setRetryRevision] = useState<string | null>(null);
  const [retryState, setRetryState] = useState<
    "idle" | "checking" | "ready" | "unavailable"
  >("idle");
  /** The window is trying a start again on its own while the agent stops. */
  const [awaitingStop, setAwaitingStop] = useState(false);
  /** When the first refusal of this run of retries came, for its bound. */
  const stopWaitSince = useRef<number | null>(null);
  const currentAttempt = useRef<string | null>(null);
  const generation = useRef(0);
  const deadline = useRef(0);
  const openedAttempt = useRef<string | null>(null);
  const seenDetail = useRef<SeenDetail | null>(null);
  const clearedAttempt = useRef<string | null>(null);
  const api = useRef(signIn);
  const completed = useRef(onTerminal);
  const close = useRef(onOpenChange);
  api.current = signIn;
  completed.current = onTerminal;
  close.current = onOpenChange;

  /** Keeps what the service said of a live attempt, for a timeout to say. */
  const noteSeen = useCallback((next: ProviderSignInSnapshot) => {
    const detail = detailOf(next);
    if (ACTIVE.has(next.event) && hasDetail(detail))
      seenDetail.current = { attemptId: next.attempt_id, detail };
  }, []);

  const refreshAfterTerminal = useCallback(
    (retryable: boolean, forGeneration: number) => {
      if (retryable) {
        setRetryRevision(null);
        setRetryState("checking");
      }
      void Promise.resolve()
        .then(() => completed.current(provider.id))
        .then((freshRevision) => {
          if (!retryable || generation.current !== forGeneration) return;
          if (
            typeof freshRevision === "string" &&
            REVISION.test(freshRevision)
          ) {
            setRetryRevision(freshRevision);
            setRetryState("ready");
          } else {
            setRetryRevision(null);
            setRetryState("unavailable");
          }
        })
        .catch(() => {
          if (!retryable || generation.current !== forGeneration) return;
          setRetryRevision(null);
          setRetryState("unavailable");
        });
    },
    [provider.id],
  );

  const cancelQuietly = useCallback(
    (
      attemptId: string,
      retryGeneration?: number,
      answered?: (detail: FailureDetail) => void,
    ) => {
      void api.current
        .cancel({ attemptId })
        .then((answer) => {
          const next = snapshotOf(answer, provider.id, attemptId);
          answered?.(detailOf(next));
        })
        .catch(() => undefined)
        .finally(() =>
          refreshAfterTerminal(
            retryGeneration !== undefined,
            retryGeneration ?? -1,
          ),
        );
    },
    [provider.id, refreshAfterTerminal],
  );

  /** The window gave up on the attempt: it says the timeout, with the cause
   * and log reference the cancel's answer adds to what was seen. */
  const cancelTimedOut = useCallback(
    (attemptId: string, forGeneration: number) =>
      cancelQuietly(attemptId, forGeneration, (detail) => {
        if (!hasDetail(detail)) return;
        setFailure((shown) =>
          shown?.code === "timeout" && generation.current === forGeneration
            ? { ...shown, detail: { ...shown.detail, ...detail } }
            : shown,
        );
      }),
    [cancelQuietly],
  );

  const activeAttemptId =
    snapshot && ACTIVE.has(snapshot.event) ? snapshot.attempt_id : null;

  useEffect(() => {
    if (!open || !activeAttemptId) return;
    let current = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let misses = 0;
    const attemptId = activeAttemptId;
    const schedule = () => {
      const remaining = deadline.current - Date.now();
      timer = setTimeout(
        () => void observe(),
        Math.max(0, Math.min(OBSERVE_MS, remaining)),
      );
    };
    const observe = async () => {
      if (!current || currentAttempt.current !== attemptId) return;
      if (Date.now() >= deadline.current) {
        currentAttempt.current = null;
        setSnapshot(null);
        setCode("");
        setFailure(timedOut(seenDetail.current, attemptId));
        setCancelling(false);
        cancelTimedOut(attemptId, generation.current);
        return;
      }
      try {
        const answer = await api.current.status({ attemptId });
        if (!current || currentAttempt.current !== attemptId) return;
        const next = snapshotOf(answer, provider.id, attemptId);
        misses = 0;
        noteSeen(next);
        if (ACTIVE.has(next.event)) {
          currentAttempt.current = attemptId;
          setSnapshot(
            clearedAttempt.current === attemptId
              ? { ...next, url: undefined, user_code: undefined }
              : openedAttempt.current === attemptId
                ? { ...next, url: undefined }
                : next,
          );
          setFailure(null);
        } else {
          currentAttempt.current = null;
          setCode("");
          setSnapshot(next);
          setFailure(snapshotFailure(next));
          setCancelling(false);
          refreshAfterTerminal(
            next.event === "failed" ||
              (next.event === "cancelled" && next.reason !== undefined),
            generation.current,
          );
        }
      } catch (error) {
        if (!current || currentAttempt.current !== attemptId) return;
        const passing = canRetryStatus(error);
        misses = passing ? misses + 1 : 0;
        if (
          passing &&
          misses < STATUS_MISSES &&
          Date.now() < deadline.current
        ) {
          // The host may be temporarily unable to read its status while it
          // starts or cleans up the helper. Preserve the active presentation
          // and let the next bounded poll determine the terminal result.
          if (current) schedule();
          return;
        }
        currentAttempt.current = null;
        setCode("");
        setSnapshot(null);
        // Reads that kept failing lost the attempt: said as lost contact,
        // with whatever cause and reference the last refusal carried.
        const lateTimeout = Date.now() >= deadline.current;
        setFailure(
          lateTimeout
            ? timedOut(seenDetail.current, attemptId, rejectionOf(error).detail)
            : rejectionOf(error, passing ? "host_disconnected" : "unknown"),
        );
        setCancelling(false);
        if (lateTimeout) cancelTimedOut(attemptId, generation.current);
        else cancelQuietly(attemptId, generation.current);
      }
      if (current && currentAttempt.current === attemptId) schedule();
    };
    schedule();
    return () => {
      current = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [
    activeAttemptId,
    cancelQuietly,
    cancelTimedOut,
    identity,
    noteSeen,
    open,
    provider.id,
    refreshAfterTerminal,
  ]);

  useEffect(
    () => () => {
      generation.current += 1;
      setCode("");
      const attemptId = currentAttempt.current;
      currentAttempt.current = null;
      if (attemptId) cancelQuietly(attemptId);
    },
    [cancelQuietly],
  );

  const accept = (
    next: ProviderSignInSnapshot,
    forGeneration = generation.current,
  ) => {
    noteSeen(next);
    if (ACTIVE.has(next.event)) {
      currentAttempt.current = next.attempt_id;
      setSnapshot(
        clearedAttempt.current === next.attempt_id
          ? { ...next, url: undefined, user_code: undefined }
          : openedAttempt.current === next.attempt_id
            ? { ...next, url: undefined }
            : next,
      );
      setFailure(null);
      setCancelling(false);
      return;
    }
    currentAttempt.current = null;
    setCode("");
    openedAttempt.current = null;
    clearedAttempt.current = null;
    setSnapshot(next);
    setFailure(snapshotFailure(next));
    setStarting(false);
    setCancelling(false);
    deadline.current = 0;
    refreshAfterTerminal(
      next.event === "failed" ||
        (next.event === "cancelled" && next.reason !== undefined),
      forGeneration,
    );
  };

  const start = async (
    nextMethod: ProviderSignInMethod,
    nextRevision = revision,
    /** The window's own retry while the agent stops: what is shown stays as
     * it is until the service answers. */
    afterStop = false,
  ) => {
    if (starting || currentAttempt.current) return;
    const mine = ++generation.current;
    if (!afterStop) stopWaitSince.current = null;
    openedAttempt.current = null;
    clearedAttempt.current = null;
    submittedAttempt.current = null;
    seenDetail.current = null;
    setCode("");
    setSubmitting(false);
    setMethod(nextMethod);
    setStarting(true);
    if (!afterStop) {
      setFailure(null);
      setAwaitingStop(false);
    }
    setSnapshot(null);
    setRetryRevision(null);
    setRetryState("idle");
    deadline.current = Date.now() + LIFETIME_MS;
    try {
      const answer = await signIn.start({
        provider: provider.id,
        revision: nextRevision,
        method: nextMethod,
      });
      const next = snapshotOf(answer, provider.id);
      if (mine !== generation.current) {
        if (ACTIVE.has(next.event)) cancelQuietly(next.attempt_id);
        else refreshAfterTerminal(false, -1);
        return;
      }
      if (ACTIVE.has(next.event) && Date.now() >= deadline.current) {
        currentAttempt.current = next.attempt_id;
        setStarting(false);
        currentAttempt.current = null;
        noteSeen(next);
        setFailure(timedOut(seenDetail.current, next.attempt_id));
        cancelTimedOut(next.attempt_id, mine);
        return;
      }
      setStarting(false);
      setAwaitingStop(false);
      stopWaitSince.current = null;
      accept(next, mine);
    } catch (error) {
      if (mine !== generation.current) return;
      currentAttempt.current = null;
      setSnapshot(null);
      setStarting(false);
      const refused = rejectionOf(error);
      setFailure(refused);
      if (agentStopping(refused)) {
        const now = Date.now();
        stopWaitSince.current ??= now;
        setAwaitingStop(now - stopWaitSince.current < AGENT_STOP_WAIT_MS);
      } else {
        stopWaitSince.current = null;
        setAwaitingStop(false);
      }
      deadline.current = 0;
      refreshAfterTerminal(true, mine);
    }
  };

  const startCurrent = useRef(start);
  const methodsCurrent = useRef(methods);
  methodsCurrent.current = methods;
  startCurrent.current = start;
  useEffect(() => {
    if (!open) return;
    // Deferring one task prevents StrictMode's setup/cleanup replay from
    // starting an abandoned authentication attempt.
    const timer = setTimeout(() => {
      const next = methodsCurrent.current.includes("browser")
        ? "browser"
        : methodsCurrent.current[0];
      if (next) void startCurrent.current(next);
    }, 0);
    return () => clearTimeout(timer);
  }, [open, identity]);

  useEffect(() => {
    if (snapshot?.event === "succeeded") close.current(false);
  }, [snapshot?.event]);

  // While the service stops the agent for this sign-in, the start is asked
  // again with the revision just read, a few seconds apart, until it is let
  // through or the bound set when the first refusal came is passed.
  useEffect(() => {
    if (
      !open ||
      !awaitingStop ||
      retryState !== "ready" ||
      !retryRevision ||
      method === null
    )
      return;
    const timer = setTimeout(
      () => void startCurrent.current(method, retryRevision, true),
      AGENT_STOP_RETRY_MS,
    );
    return () => clearTimeout(timer);
  }, [awaitingStop, method, open, retryRevision, retryState]);

  const cancel = async () => {
    setCode("");
    const attemptId = currentAttempt.current;
    if (!attemptId) {
      close.current(false);
      return;
    }
    const mine = generation.current;
    clearedAttempt.current = attemptId;
    setCancelling(true);
    setFailure(null);
    try {
      const next = snapshotOf(
        await signIn.cancel({ attemptId }),
        provider.id,
        attemptId,
      );
      if (generation.current !== mine || currentAttempt.current !== attemptId) {
        // The poller may have settled this attempt while cancellation was in
        // flight, and a later attempt may already be active. Keep the refresh
        // caused by cancellation, but never apply its old snapshot to that UI.
        refreshAfterTerminal(false, -1);
        return;
      }
      accept(next, mine);
      if (ACTIVE.has(next.event)) refreshAfterTerminal(false, -1);
    } catch {
      if (generation.current !== mine || currentAttempt.current !== attemptId) {
        refreshAfterTerminal(false, -1);
        return;
      }
      clearedAttempt.current = attemptId;
      setSnapshot((current) =>
        current
          ? { ...current, url: undefined, user_code: undefined }
          : current,
      );
      setFailure({ code: "cancel_failed", detail: {} });
      setCancelling(false);
      refreshAfterTerminal(false, -1);
    }
  };

  const continueInBrowser = useCallback(
    async (current: ProviderSignInSnapshot) => {
      const url = current.url;
      const openExternal = api.current.openExternal;
      if (!url || !openExternal) return;
      const attemptId = current.attempt_id;
      const mine = generation.current;
      if (
        currentAttempt.current !== attemptId ||
        openedAttempt.current === attemptId
      )
        return;
      openedAttempt.current = attemptId;
      setSnapshot({ ...current, url: undefined });
      setFailure(null);
      try {
        await openExternal(url);
      } catch {
        if (
          generation.current !== mine ||
          currentAttempt.current !== attemptId
        ) {
          // The failed browser handoff still belongs to its original attempt;
          // cleanup is keyed by that id and cannot touch a later attempt.
          cancelQuietly(attemptId);
          return;
        }
        currentAttempt.current = null;
        setSnapshot(null);
        setFailure({ code: "open_external_failed", detail: {} });
        cancelQuietly(attemptId, mine);
      }
    },
    [cancelQuietly],
  );

  // The browser action is a consequence of the person's explicit Start click.
  // Open it once as soon as the host supplies a validated address; the URL is
  // cleared from React state before the native browser handoff begins.
  useEffect(() => {
    if (
      (snapshot?.event === "browser_action" ||
        snapshot?.event === "authorization_code_required") &&
      snapshot.url
    ) {
      if (!api.current.openExternal) {
        const attemptId = snapshot.attempt_id;
        const mine = generation.current;
        if (currentAttempt.current === attemptId) {
          currentAttempt.current = null;
          setSnapshot(null);
          setFailure({ code: "open_external_failed", detail: {} });
          cancelQuietly(attemptId, mine);
        }
        return;
      }
      void continueInBrowser(snapshot);
    }
  }, [cancelQuietly, continueInBrowser, snapshot]);

  const submitCode = async () => {
    const attemptId = currentAttempt.current;
    if (
      !attemptId ||
      snapshot?.event !== "authorization_code_required" ||
      submittedAttempt.current === attemptId ||
      !validAuthorizationCode(code)
    )
      return;
    const mine = generation.current;
    const submitted = code;
    submittedAttempt.current = attemptId;
    setCode("");
    setSubmitting(true);
    setFailure(null);
    try {
      const next = snapshotOf(
        await signIn.submitCode({ attemptId, code: submitted }),
        provider.id,
        attemptId,
      );
      if (
        generation.current === mine &&
        currentAttempt.current === attemptId &&
        clearedAttempt.current !== attemptId
      )
        accept(next, mine);
    } catch (error) {
      if (
        generation.current === mine &&
        currentAttempt.current === attemptId &&
        clearedAttempt.current !== attemptId
      ) {
        currentAttempt.current = null;
        setSnapshot(null);
        setFailure(rejectionOf(error));
        cancelQuietly(attemptId, mine);
      }
    } finally {
      if (generation.current === mine) setSubmitting(false);
    }
  };

  const active = snapshot !== null && ACTIVE.has(snapshot.event);
  const checkingCode =
    active && submittedAttempt.current === snapshot.attempt_id;
  const terminalSuccess = snapshot?.event === "succeeded";
  const terminalCancelled = snapshot?.event === "cancelled";
  const terminalFailure = snapshot?.event === "failed";
  const terminalFailureReason =
    terminalFailure || (terminalCancelled && snapshot?.reason !== undefined);
  // What is said of a failure: an ended attempt's own snapshot first, else
  // the refusal or local failure that ended it.
  const shownFailure: Failure | null =
    terminalFailureReason && snapshot
      ? { code: snapshotFailureCode(snapshot), detail: detailOf(snapshot) }
      : failure;
  // The agent is being stopped and the window tries again on its own: said
  // as progress, not as a failure, unless a fresh revision cannot be read.
  const stopping =
    awaitingStop &&
    retryState !== "unavailable" &&
    shownFailure !== null &&
    agentStopping(shownFailure);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        closeLabel={t("desktop.providers.sign_in_close")}
        aria-describedby="provider-sign-in-description"
      >
        <DialogHeader>
          <DialogTitle>
            {terminalSuccess
              ? t("desktop.providers.sign_in_success_title", {
                  provider: provider.name,
                })
              : t("desktop.providers.sign_in_title", {
                  provider: provider.name,
                })}
          </DialogTitle>
          <DialogDescription
            id="provider-sign-in-description"
            role={terminalSuccess || active || starting ? "status" : undefined}
            aria-live={
              terminalSuccess || active || starting ? "polite" : undefined
            }
          >
            {terminalSuccess || stopping
              ? ""
              : starting
                ? t("desktop.providers.sign_in_starting")
                : checkingCode
                  ? t("desktop.providers.sign_in_code_checking")
                  : active && snapshot
                    ? activeWords(t, snapshot, method)
                    : failure || terminalCancelled || terminalFailure
                      ? ""
                      : t("desktop.providers.sign_in_starting")}
          </DialogDescription>
        </DialogHeader>

        {active && snapshot && (
          <div
            data-slot="sign-in-attempt"
            data-attempt-id={snapshot.attempt_id}
            className="grid gap-2"
          >
            {checkingCode && <Spinner className="size-4" />}
            {snapshot.event === "authorization_code_required" &&
              submittedAttempt.current !== snapshot.attempt_id &&
              clearedAttempt.current !== snapshot.attempt_id && (
                <div className="grid gap-2">
                  <label htmlFor="provider-authorization-code">
                    {t("desktop.providers.sign_in_code_label")}
                  </label>
                  <AuthorizationCodeField value={code} onChange={setCode} />
                  <Button
                    size="sm"
                    disabled={
                      submitting || cancelling || !validAuthorizationCode(code)
                    }
                    onClick={() => void submitCode()}
                  >
                    {t("desktop.providers.sign_in_code_submit")}
                  </Button>
                </div>
              )}
            {method === "device" && snapshot.user_code && (
              <p className="grid justify-items-start gap-1 text-sm">
                <span className="text-muted-foreground">
                  {t("desktop.providers.sign_in_user_code")}
                </span>
                <code className="rounded bg-muted px-2 py-1 font-mono text-base text-foreground">
                  {snapshot.user_code}
                </code>
              </p>
            )}
          </div>
        )}
        {terminalCancelled && !snapshot?.reason && (
          <p role="status" className="text-sm text-muted-foreground">
            {t("desktop.providers.sign_in_cancelled")}
          </p>
        )}
        {shownFailure && stopping && (
          <p
            role="status"
            aria-live="polite"
            data-slot="sign-in-agent-stopping"
            data-reason={shownFailure.code}
            data-cause={shownFailure.detail.cause}
            data-next-step={shownFailure.detail.next_step}
            data-status-cause={shownFailure.detail.status_cause}
            data-log-ref={shownFailure.detail.log_ref}
            className="flex items-center gap-2 text-sm text-muted-foreground"
          >
            <Spinner className="size-4" />
            {t("desktop.providers.sign_in_agent_stopping", {
              provider: provider.name,
            })}
          </p>
        )}
        {shownFailure && !stopping && (
          <p
            role="alert"
            data-reason={shownFailure.code}
            data-cause={shownFailure.detail.cause}
            data-next-step={shownFailure.detail.next_step}
            data-status-cause={shownFailure.detail.status_cause}
            data-log-ref={shownFailure.detail.log_ref}
            className="text-sm text-destructive"
          >
            {failureWords(t, shownFailure, provider.name, method)}
          </p>
        )}
        {shownFailure && !stopping && (
          <SignInAdvice
            causes={[
              shownFailure.detail.cause,
              shownFailure.detail.status_cause,
            ]}
            step={shownFailure.detail.next_step}
            command={consoleSignInCommand}
            provider={provider.provider}
          />
        )}
        {shownFailure?.detail.log_ref && (
          <p
            data-slot="sign-in-log-ref"
            className="text-sm text-muted-foreground"
          >
            {t("desktop.providers.sign_in_log_ref")}{" "}
            <code className="font-mono text-foreground select-all">
              {shownFailure.detail.log_ref}
            </code>
          </p>
        )}
        {retryState === "checking" && !stopping && (
          <p role="status" className="text-sm text-muted-foreground">
            {t("desktop.providers.sign_in_retry_checking")}
          </p>
        )}
        {retryState === "unavailable" && (
          <p role="alert" className="text-sm text-destructive">
            {t("desktop.providers.sign_in_retry_refresh_failed")}
          </p>
        )}

        <DialogFooter>
          {retryRevision &&
            retryState === "ready" &&
            !stopping &&
            !active &&
            method !== null &&
            methods.includes(method) && (
              <Button
                variant="primary"
                size="sm"
                disabled={starting}
                pending={starting}
                onClick={() => void start(method!, retryRevision)}
              >
                {t("desktop.providers.sign_in_retry")}
              </Button>
            )}
          {active || starting ? (
            <Button
              variant="outline"
              size="sm"
              disabled={cancelling}
              pending={cancelling}
              onClick={() => void cancel()}
            >
              {t("desktop.providers.sign_in_cancel")}
            </Button>
          ) : (
            <Button
              variant={terminalSuccess ? "primary" : "outline"}
              size="sm"
              onClick={() => close.current(false)}
            >
              {t(
                terminalSuccess
                  ? "desktop.providers.sign_in_done"
                  : "desktop.providers.sign_in_close",
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
