import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
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
import type {
  ProviderSignIn,
  ProviderSignInEvent,
  ProviderSignInMethod,
  ProviderSignInSnapshot,
} from "../../shell/providerSettings";
import type { ProviderStatus } from "./types";

const EVENTS: readonly ProviderSignInEvent[] = [
  "starting",
  "started",
  "browser_action",
  "succeeded",
  "cancelled",
  "failed",
];
const ACTIVE = new Set<ProviderSignInEvent>([
  "starting",
  "started",
  "browser_action",
]);
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const CODE = /^[a-z0-9_-]{1,64}$/i;
const LIFETIME_MS = 300_000;
const OBSERVE_MS = 1_000;

function safeFailureCode(error: unknown): string {
  const code = failureCode(error);
  return CODE.test(code) ? code : "unknown";
}

function hasControlCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const code = character.charCodeAt(0);
    return code <= 0x1f || code === 0x7f;
  });
}

type Props = {
  open: boolean;
  identity: string | null;
  provider: ProviderStatus;
  revision: string;
  signIn: ProviderSignIn;
  onOpenChange: (open: boolean) => void;
  onTerminal: () => void;
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
    event === "failed" &&
    typeof raw.reason === "string" &&
    CODE.test(raw.reason)
      ? raw.reason
      : undefined;
  if (terminal)
    return {
      attempt_id: raw.attempt_id,
      provider: providerId,
      event,
      ...(reason ? { reason } : {}),
    };

  // During cancellation the service may still report browser_action while it
  // finishes helper cleanup, but it has already removed the one-time URL.
  // Treat that as active progress with no browser action available.
  const url = event === "browser_action" ? safeUrl(raw.url) : undefined;
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
    ...(url ? { url } : {}),
    ...(userCode ? { user_code: userCode } : {}),
  };
}

function failureWords(t: Translate, code: string): string {
  switch (code) {
    case "not_signed_in":
      return t("desktop.providers.refused_not_signed_in");
    case "profile_locked":
      return t("desktop.providers.refused_profile_locked");
    case "person_act_required":
      return t("desktop.providers.refused_person_act_required");
    case "runtime_unavailable":
      return t("desktop.providers.refused_runtime_unavailable");
    case "catalog_unavailable":
      return t("desktop.providers.refused_catalog_unavailable");
    case "revision_conflict":
      return t("desktop.providers.refused_revision_conflict");
    case "timeout":
    case "expired":
      return t("desktop.providers.sign_in_timeout");
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
    case "succeeded":
    case "cancelled":
    case "failed":
      return "";
  }
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
  onOpenChange,
  onTerminal,
}: Props) {
  const t = useStrings();
  const [snapshot, setSnapshot] = useState<ProviderSignInSnapshot | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [method, setMethod] = useState<ProviderSignInMethod | null>(null);
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [opening, setOpening] = useState(false);
  const currentAttempt = useRef<string | null>(null);
  const generation = useRef(0);
  const deadline = useRef(0);
  const openedAttempt = useRef<string | null>(null);
  const clearedAttempt = useRef<string | null>(null);
  const api = useRef(signIn);
  const completed = useRef(onTerminal);
  const close = useRef(onOpenChange);
  api.current = signIn;
  completed.current = onTerminal;
  close.current = onOpenChange;

  const cancelQuietly = useCallback(
    (attemptId: string) => {
      void api.current
        .cancel({ attemptId })
        .then((answer) => {
          snapshotOf(answer, provider.id, attemptId);
        })
        .catch(() => undefined)
        .finally(() => completed.current());
    },
    [provider.id],
  );

  const activeAttemptId =
    snapshot && ACTIVE.has(snapshot.event) ? snapshot.attempt_id : null;

  useEffect(() => {
    if (!open || !activeAttemptId) return;
    let current = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
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
        setFailure("timeout");
        setCancelling(false);
        setOpening(false);
        cancelQuietly(attemptId);
        return;
      }
      try {
        const answer = await api.current.status({ attemptId });
        if (!current || currentAttempt.current !== attemptId) return;
        const next = snapshotOf(answer, provider.id, attemptId);
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
          setSnapshot(next);
          setFailure(
            next.event === "failed" ? (next.reason ?? "unknown") : null,
          );
          setCancelling(false);
          setOpening(false);
          completed.current();
        }
      } catch (error) {
        if (!current || currentAttempt.current !== attemptId) return;
        currentAttempt.current = null;
        setSnapshot(null);
        setFailure(safeFailureCode(error));
        setCancelling(false);
        setOpening(false);
        cancelQuietly(attemptId);
      }
      if (current && currentAttempt.current === attemptId) schedule();
    };
    schedule();
    return () => {
      current = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [activeAttemptId, cancelQuietly, identity, open, provider.id]);

  useEffect(
    () => () => {
      generation.current += 1;
      const attemptId = currentAttempt.current;
      currentAttempt.current = null;
      if (attemptId) cancelQuietly(attemptId);
    },
    [cancelQuietly],
  );

  const accept = (next: ProviderSignInSnapshot) => {
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
      setOpening(false);
      return;
    }
    currentAttempt.current = null;
    openedAttempt.current = null;
    clearedAttempt.current = null;
    setSnapshot(next);
    setFailure(next.event === "failed" ? (next.reason ?? "unknown") : null);
    setStarting(false);
    setCancelling(false);
    setOpening(false);
    deadline.current = 0;
    completed.current();
  };

  const start = async (nextMethod: ProviderSignInMethod) => {
    if (starting || currentAttempt.current) return;
    const mine = ++generation.current;
    openedAttempt.current = null;
    clearedAttempt.current = null;
    setMethod(nextMethod);
    setStarting(true);
    setFailure(null);
    setSnapshot(null);
    deadline.current = Date.now() + LIFETIME_MS;
    try {
      const answer = await signIn.start({
        provider: provider.id,
        revision,
        method: nextMethod,
      });
      const next = snapshotOf(answer, provider.id);
      if (mine !== generation.current) {
        if (ACTIVE.has(next.event)) cancelQuietly(next.attempt_id);
        else completed.current();
        return;
      }
      if (ACTIVE.has(next.event) && Date.now() >= deadline.current) {
        currentAttempt.current = next.attempt_id;
        setStarting(false);
        currentAttempt.current = null;
        setFailure("timeout");
        cancelQuietly(next.attempt_id);
        return;
      }
      setStarting(false);
      accept(next);
    } catch (error) {
      if (mine !== generation.current) return;
      currentAttempt.current = null;
      setSnapshot(null);
      setStarting(false);
      setFailure(safeFailureCode(error));
      deadline.current = 0;
      completed.current();
    }
  };

  const cancel = async () => {
    const attemptId = currentAttempt.current;
    if (!attemptId) {
      close.current(false);
      return;
    }
    setCancelling(true);
    setFailure(null);
    try {
      accept(
        snapshotOf(await signIn.cancel({ attemptId }), provider.id, attemptId),
      );
    } catch {
      clearedAttempt.current = attemptId;
      setSnapshot((current) =>
        current
          ? { ...current, url: undefined, user_code: undefined }
          : current,
      );
      setFailure("cancel_failed");
      setCancelling(false);
    }
  };

  const continueInBrowser = async () => {
    const current = snapshot;
    const url = current?.url;
    const openExternal = signIn.openExternal;
    if (!current || !url || !openExternal) return;
    openedAttempt.current = current.attempt_id;
    setSnapshot({ ...current, url: undefined });
    setOpening(true);
    setFailure(null);
    try {
      await openExternal(url);
    } catch {
      currentAttempt.current = null;
      setSnapshot(null);
      setOpening(false);
      setFailure("open_external_failed");
      cancelQuietly(current.attempt_id);
      return;
    }
    setOpening(false);
  };

  const active = snapshot !== null && ACTIVE.has(snapshot.event);
  const canContinue =
    snapshot?.event === "browser_action" &&
    Boolean(snapshot.url) &&
    Boolean(signIn.openExternal) &&
    openedAttempt.current !== snapshot.attempt_id;
  const terminalSuccess = snapshot?.event === "succeeded";
  const terminalCancelled = snapshot?.event === "cancelled";
  const terminalFailure = snapshot?.event === "failed";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        closeLabel={t("desktop.providers.sign_in_close")}
        aria-describedby="provider-sign-in-description"
      >
        <DialogHeader>
          <DialogTitle>
            {t("desktop.providers.sign_in_title", { provider: provider.name })}
          </DialogTitle>
          <DialogDescription id="provider-sign-in-description">
            {t("desktop.providers.sign_in_description", {
              provider: provider.name,
            })}
          </DialogDescription>
          <p className="text-sm text-muted-foreground">
            {t("desktop.providers.sign_in_security")}
          </p>
        </DialogHeader>

        {starting && (
          <p role="status" className="text-sm text-muted-foreground">
            {t("desktop.providers.sign_in_starting")}
          </p>
        )}
        {active && snapshot && (
          <div role="status" aria-live="polite" className="grid gap-2">
            <p className="text-sm text-muted-foreground">
              {activeWords(t, snapshot, method)}
            </p>
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
        {terminalSuccess && (
          <p role="status" className="text-sm text-foreground">
            {t("desktop.providers.sign_in_success", {
              provider: provider.name,
            })}
          </p>
        )}
        {terminalCancelled && (
          <p role="status" className="text-sm text-muted-foreground">
            {t("desktop.providers.sign_in_cancelled")}
          </p>
        )}
        {(failure || terminalFailure) && (
          <p role="alert" className="text-sm text-destructive">
            {failureWords(
              t,
              terminalFailure
                ? (snapshot?.reason ?? "unknown")
                : (failure ?? "unknown"),
            )}
          </p>
        )}

        <DialogFooter>
          {!snapshot && (
            <>
              <Button
                variant="primary"
                size="sm"
                disabled={starting}
                pending={starting}
                onClick={() => void start("browser")}
              >
                {t("desktop.providers.sign_in_start_browser")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={starting}
                onClick={() => void start("device")}
              >
                {t("desktop.providers.sign_in_start_device")}
              </Button>
            </>
          )}
          {canContinue && (
            <Button
              variant="primary"
              size="sm"
              disabled={opening}
              pending={opening}
              onClick={() => void continueInBrowser()}
            >
              {t("desktop.providers.sign_in_continue_browser")}
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
              variant="outline"
              size="sm"
              onClick={() => close.current(false)}
            >
              {t("desktop.providers.sign_in_close")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
