import { useEffect, useRef, useState } from "react";

export type CensoReadiness = {
  provider: string;
  route: string;
  ready: boolean;
  requirements: {
    field: string;
    satisfied: boolean;
    reason: string;
    secret: boolean;
  }[];
};
export type CensoSnapshot = {
  operation: string;
  state:
    | "reading"
    | "device"
    | "review"
    | "done"
    | "stopped"
    | "failed"
    | "unknown"
    | "unsupported";
  can_cancel: boolean;
  review_digest: string | null;
  /** On a pull that stopped for want of a component, the operator action
   * that sets it up; an identifier for routing, never shown. */
  recovery_action_id?: string;
  fields: {
    path: string;
    current: string | null;
    incoming: string | null;
    preserve: boolean;
  }[];
};
export type CensoDecision = "apply" | "reject" | "cancel";
export type CensoPort = {
  observe?(changed: () => void): Promise<() => void>;
  readiness(profile: string): Promise<CensoReadiness>;
  start(profile: string): Promise<CensoSnapshot>;
  status(profile: string, operation: string): Promise<CensoSnapshot>;
  answer(
    profile: string,
    operation: string,
    reviewDigest: string | null,
    decision: CensoDecision,
  ): Promise<CensoSnapshot>;
};

// Closed runtime reasons, never arbitrary keys or raw field paths as copy.
export const censoRequirementKeys = {
  profile_tax_id_required: "auth.sync.requirement.profile_tax_id_required",
  auth_method_required: "auth.sync.requirement.auth_method_required",
  certificate_file_required: "auth.sync.requirement.certificate_file_required",
  certificate_passphrase_required:
    "auth.sync.requirement.certificate_passphrase_required",
  clave_identity_required: "auth.sync.requirement.clave_identity_required",
  profile_identity_must_match:
    "auth.sync.requirement.profile_identity_must_match",
  nie_support_required: "auth.sync.requirement.nie_support_required",
  dni_validity_required: "auth.sync.requirement.dni_validity_required",
  clave_password_required: "auth.sync.requirement.clave_password_required",
  no_path_set: "auth.sync.requirement.certificate_file_required",
  file_missing: "auth.sync.requirement.file_missing",
  unreadable: "auth.sync.requirement.unreadable",
  corrupt: "auth.sync.requirement.corrupt",
  expired: "auth.sync.requirement.expired",
  expiring: "auth.sync.requirement.expiring",
  ok: "auth.sync.requirement.ok",
} as const;

/** Codes after which a Censo act is known not to have happened. */
const SETTLED_FAILURES = ["refused", "conflict", "not_signed_in"];
type CensoError =
  | "profile_mismatch"
  | "subject_busy"
  | "authentication_required"
  | "session_inactive"
  | "session_expired"
  | "refused"
  | "conflict"
  | "not_signed_in"
  | "unavailable"
  | "unknown";

/**
 * One profile's Censo synchronization: what it still needs, and the pull in
 * progress. Runtime pushes drive the pull; a slow check recovers a lost cue.
 * A failure whose outcome is not known is `uncertain`, and nothing is retried
 * or started again without an authoritative operation status.
 */
export function useCensoSync(
  port: CensoPort | undefined,
  profile: { profile_id: string; record_revision: number } | null,
  active: boolean,
  onSettled: () => void,
) {
  const [readiness, setReadiness] = useState<CensoReadiness | null>(null);
  const [snapshot, setSnapshot] = useState<CensoSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<CensoError | null>(null);
  const [readinessError, setReadinessError] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [reload, setReload] = useState(0);
  const settled = useRef(onSettled);
  settled.current = onSettled;
  const id = profile?.profile_id ?? null;
  const revision = profile?.record_revision ?? null;
  const operation = snapshot?.operation;
  const state = snapshot?.state;
  const finished =
    state === "done" || state === "stopped" || state === "failed";

  useEffect(() => {
    if (!active || !port || id === null || operation) return;
    let live = true;
    void port
      .readiness(id)
      .then((value) => {
        if (live) {
          setReadiness(value);
          setReadinessError(false);
        }
      })
      .catch(() => {
        if (live) setReadinessError(true);
      });
    return () => {
      live = false;
    };
  }, [active, port, id, revision, operation, reload]);

  useEffect(() => {
    if (!active || !port || id === null || !operation || finished || busy)
      return;
    let live = true,
      fetching = false,
      queued = false;
    let stop: (() => void) | undefined;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      if (!live) return;
      if (fetching) {
        queued = true;
        return;
      }
      fetching = true;
      clearTimeout(timer);
      try {
        const value = await port.status(id, operation);
        if (live) {
          setSnapshot(value);
          setActionError(null);
          setUncertain(false);
        }
      } catch {
        if (live) setActionError("unavailable");
      } finally {
        fetching = false;
      }
      if (live) {
        const delay = queued ? 0 : 30000;
        queued = false;
        // Runtime pushes drive updates; this is a recovery check for lost cues.
        timer = setTimeout(() => {
          void refresh();
        }, delay);
      }
    };
    timer = setTimeout(() => {
      void refresh();
    }, 0);
    if (port.observe)
      void port
        .observe(() => {
          void refresh();
        })
        .then((unsubscribe) => {
          if (!live) unsubscribe();
          else {
            stop = unsubscribe;
            void refresh();
          }
        })
        .catch(() => {
          if (live) setActionError("unavailable");
        });
    return () => {
      live = false;
      clearTimeout(timer);
      stop?.();
    };
  }, [active, port, id, operation, finished, busy, reload]);

  // A pull that ended may have changed the profile: it is read again once.
  useEffect(() => {
    if (finished) settled.current();
  }, [finished, operation]);

  const run = async (decision?: CensoDecision) => {
    if (!port || id === null || busy || (uncertain && !snapshot)) return;
    setBusy(true);
    setActionError(null);
    try {
      const value =
        decision && snapshot
          ? await port.answer(
              id,
              snapshot.operation,
              snapshot.review_digest,
              decision,
            )
          : await port.start(id);
      setSnapshot(value);
    } catch (failure) {
      const code =
        typeof failure === "object" && failure && "code" in failure
          ? String(failure.code)
          : "";
      const reason =
        typeof failure === "object" &&
        failure &&
        "reason" in failure &&
        typeof failure.reason === "string"
          ? failure.reason
          : "";
      if (
        code === "refused" &&
        (reason === "profile_mismatch" ||
          reason === "subject_busy" ||
          reason === "authentication_required" ||
          reason === "session_inactive" ||
          reason === "session_expired")
      ) {
        setActionError(reason);
      } else if (
        code === "refused" ||
        code === "conflict" ||
        code === "not_signed_in"
      ) {
        setActionError(code);
      } else {
        setActionError("unknown");
      }
      if (!SETTLED_FAILURES.includes(code)) setUncertain(true);
    } finally {
      setBusy(false);
    }
  };

  return {
    readiness,
    snapshot,
    busy,
    error: actionError ?? (readinessError ? "unavailable" : null),
    uncertain,
    start: () => run(),
    answer: (decision: CensoDecision) => run(decision),
    /** Puts a finished pull away, back to what the next one needs. */
    dismiss: () => {
      if (!finished) return;
      setSnapshot(null);
      setReadiness(null);
    },
    /** Checks again after a failure; an uncertain outcome stays uncertain
     * until a check answers. */
    retry: () => {
      if (!uncertain) setActionError(null);
      setReadinessError(false);
      setReload((value) => value + 1);
    },
  };
}
