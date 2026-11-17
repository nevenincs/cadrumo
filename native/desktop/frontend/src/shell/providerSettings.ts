import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  ProviderOutcome,
  ProviderSecret,
  ProviderStatus,
} from "@/components/settings/types";
import { failureCode } from "../errors";
import type { CallPlan } from "./hostCall";
import { useCachedRead, type AgentRead } from "./agentViews";
import {
  CATALOG_BUSY_QUIET_MS,
  STATUS_BUSY_PAUSE_MS,
  catalogBusyPause,
} from "./catalogReadPolicy";
import {
  cliStateCause,
  consoleCommandTemplate,
  logRef,
  nextStep,
  signInCause,
} from "./providerSignInWords";
import type {
  ProviderSettingsAnswer,
  ProviderSettingsRecord,
  ProviderSignInMethod,
  ProviderSignInSnapshot,
} from "./providerSettingsContract";

// The model providers of the signed-in profile, as a host serves them: the
// masked status of each lane (a provider's API, or its command-line app),
// and the person's ways to set, disable or reset its key. A key goes to the host once, in the call that saves it, and comes
// back from nowhere: no answer here carries a key, and nothing keeps one.

export interface ProviderSignIn {
  start(change: {
    provider: string;
    revision: string;
    method: ProviderSignInMethod;
  }): Promise<ProviderSignInSnapshot>;
  status(change: { attemptId: string }): Promise<ProviderSignInSnapshot>;
  cancel(change: { attemptId: string }): Promise<ProviderSignInSnapshot>;
  submitCode(change: {
    attemptId: string;
    code: string;
  }): Promise<ProviderSignInSnapshot>;
  /** Same user-gesture-only operation as Host.openExternal. */
  openExternal?(url: string): Promise<void>;
}

/** Why a change was refused, as a stable code. `committed_readback_failed`
 * means the change was saved but its status could not be read back. */
export interface ProviderSettings {
  status(plan?: CallPlan): Promise<ProviderSettingsAnswer>;
  /** Attended GUI sign-in is absent unless this host implements it. */
  readonly signIn?: ProviderSignIn;
  /** Saves a key or token. The secret is handed on once and never kept.
   * Each change answers with the provider's new status. */
  set(change: {
    provider: string;
    revision: string;
    secret: string;
    base_url?: string;
  }): Promise<ProviderSettingsRecord>;
  /** Turns the lane off: the agent does not offer or use it, and what is
   * saved for it is kept. */
  turnOff(change: {
    provider: string;
    revision: string;
  }): Promise<ProviderSettingsRecord>;
  /** Turns a lane that is off back on, as it was saved. */
  turnOn(change: {
    provider: string;
    revision: string;
  }): Promise<ProviderSettingsRecord>;
  /** Back to unset. */
  reset(change: {
    provider: string;
    revision: string;
  }): Promise<ProviderSettingsRecord>;
  /** Signs a command-line lane out of its provider; it answers with the lane
   * signed out. Offered only where the lane serves `sign_out_available`. */
  signOut(change: {
    provider: string;
    revision: string;
  }): Promise<ProviderSettingsRecord>;
}

/** The console command the service serves, where it is a command template. */
const servedCommand = (value: unknown): { consoleSignInCommand?: string } => {
  const command = consoleCommandTemplate(value);
  return command ? { consoleSignInCommand: command } : {};
};

const providerStatus = (record: ProviderSettingsRecord): ProviderStatus => ({
  id: record.id,
  provider: record.provider,
  name: record.display_name,
  transport: record.transport,
  authKind: record.auth_kind,
  mode: record.mode,
  readiness: record.readiness,
  source: record.source,
  ...(record.cli_state ? { cliState: record.cli_state } : {}),
  // A cause is the service's closed word or nothing: another word is dropped.
  ...(cliStateCause(record.cli_state_cause)
    ? { cliStateCause: cliStateCause(record.cli_state_cause) }
    : {}),
  ...(nextStep(record.next_step)
    ? { nextStep: nextStep(record.next_step) }
    : {}),
  ...(record.credential_saved ? { credentialSaved: true } : {}),
  ...(record.reason ? { reason: record.reason } : {}),
  ...(record.base_url ? { baseUrl: record.base_url } : {}),
  ...(record.default_base_url
    ? { defaultBaseUrl: record.default_base_url }
    : {}),
  // Only the served value says it; nothing about the lane stands in for it.
  ...(typeof record.reads_off_host === "boolean"
    ? { readsOffHost: record.reads_off_host }
    : {}),
  ...(record.sign_out_available === true ? { signOutAvailable: true } : {}),
});

export type ProviderSettingsView = {
  read: AgentRead<{
    providers: ProviderStatus[];
    signInProviders: string[];
    signInMethods: Readonly<Record<string, readonly ProviderSignInMethod[]>>;
    consoleSignInCommand?: string;
    revisions: Readonly<Record<string, string>>;
    /** The service is still reading the sign-in routes and the apps' states
     * behind this answer, as it serves `reads_pending`. */
    readsPending: boolean;
  }>;
  busyId: string | null;
  outcomes: Readonly<Record<string, ProviderOutcome>>;
  save: (providerId: string, secret: ProviderSecret) => void;
  turnOff: (providerId: string) => void;
  turnOn: (providerId: string) => void;
  reset: (providerId: string) => void;
  signOut: (providerId: string) => void;
  refresh: () => void;
  /** Reads the settings again, as when the agent turns ready, without
   * invalidating the agent's provider list. */
  reread: () => void;
  /** Invalidations of the agent's provider list, including authentication
   * observed by a status refresh or a read made elsewhere. */
  changes: number;
  /** Shows a status read made elsewhere, in place of reading it again. */
  accept: (status: ProviderSettingsAnswer) => void;
};

/**
 * The providers of `reader`'s profile while `open`: read each time they open
 * (`opened` counts the openings), after each change of the person's and when
 * asked to refresh. The last answer stays on screen while it is read again,
 * so the settings load only the first time. A busy answer (the service still
 * starting the agent) is read again after a pause, growing to a ceiling,
 * for as long as they are open: the settings follow their own read, not the
 * agent's other reads or the ready it publishes, which can come much later.
 * That read is the service's own store read and waits on nothing, so its busy
 * answer (the host has not yet admitted the service) is asked again after a
 * short pause while the wait is the one expected, then on the catalog's.
 * An answer the service says it is still completing (`reads_pending`: the
 * sign-in routes and the apps' states are read behind it) is read again on
 * the same pauses while they are open, until an answer says it is complete.
 */
export function useProviderSettings(
  host: ProviderSettings | undefined,
  reader: string | null,
  open: boolean,
  opened: number,
): ProviderSettingsView {
  const owner = useMemo(() => ({ host, reader }), [host, reader]);
  const generation = useRef(0);
  useLayoutEffect(
    () => () => {
      generation.current += 1;
    },
    [owner],
  );
  const [state, setState] = useState({
    owner,
    again: 0,
    changes: 0,
    busyId: null as string | null,
    outcomes: {} as Record<string, ProviderOutcome>,
  });
  if (state.owner !== owner)
    setState({ owner, again: 0, changes: 0, busyId: null, outcomes: {} });
  // A busy answer is followed while the settings are open, and since when it
  // has been, so its refusals are recorded as the wait they are while it is
  // the one expected.
  const asking = useRef(open);
  useLayoutEffect(() => {
    asking.current = open;
  }, [open]);
  const following = useRef<{ since: number } | null>(null);
  const readStatus = useMemo(
    () =>
      host && reader !== null
        ? () =>
            host.status({
              retryable: (code) => code === "busy",
              scheduled: () => asking.current,
              expected: () =>
                following.current === null ||
                performance.now() - following.current.since <
                  CATALOG_BUSY_QUIET_MS,
            })
        : null,
    [host, reader],
  );
  const { read: answer, put } = useCachedRead(
    readStatus,
    reader,
    open,
    state.again + opened,
  );
  const busy =
    open &&
    readStatus !== null &&
    answer.kind === "failed" &&
    answer.code === "busy";
  const pending =
    open &&
    readStatus !== null &&
    answer.kind === "ready" &&
    answer.value.reads_pending;
  const pauses = useRef(0);
  useEffect(() => {
    if (!busy) following.current = null;
    if (!busy && !pending) {
      pauses.current = 0;
      return;
    }
    let pause: number;
    if (busy) {
      following.current ??= { since: performance.now() };
      const admitting =
        performance.now() - following.current.since < CATALOG_BUSY_QUIET_MS;
      pause = admitting
        ? STATUS_BUSY_PAUSE_MS
        : catalogBusyPause(pauses.current);
      if (!admitting) pauses.current += 1;
    } else {
      // The pending reads wait on the agent's own reads of its apps.
      pause = catalogBusyPause(pauses.current);
      pauses.current += 1;
    }
    const again = window.setTimeout(
      () => setState((held) => ({ ...held, again: held.again + 1 })),
      pause,
    );
    return () => window.clearTimeout(again);
  }, [answer, busy, pending]);
  const read = useMemo(
    (): ProviderSettingsView["read"] =>
      answer.kind === "ready"
        ? {
            kind: "ready",
            value: {
              providers: answer.value.providers.map(providerStatus),
              signInProviders: Array.isArray(answer.value.sign_in_providers)
                ? [...new Set<string>(answer.value.sign_in_providers)]
                : [],
              signInMethods: Object.fromEntries(
                Object.entries(answer.value.sign_in_methods ?? {}).flatMap(
                  ([provider, methods]) =>
                    Array.isArray(methods)
                      ? [
                          [
                            provider,
                            [
                              ...new Set(
                                methods.filter(
                                  (method): method is ProviderSignInMethod =>
                                    method === "browser" ||
                                    method === "device" ||
                                    method === "browser-code",
                                ),
                              ),
                            ],
                          ],
                        ]
                      : [],
                ),
              ),
              ...servedCommand(answer.value.console_sign_in_command),
              revisions: Object.fromEntries(
                answer.value.providers.map(
                  ({ id, revision }) => [id, revision] as const,
                ),
              ),
              readsPending: answer.value.reads_pending,
            },
          }
        : answer,
    [answer],
  );
  const revisionOf = (providerId: string) =>
    answer.kind === "ready"
      ? answer.value.providers.find((record) => record.id === providerId)
          ?.revision
      : undefined;

  const change = (
    providerId: string,
    act: (
      served: ProviderSettings,
      revision: string,
    ) => Promise<ProviderSettingsRecord>,
  ) => {
    const revision = revisionOf(providerId);
    if (!host || reader === null || revision === undefined) return;
    const mine = generation.current;
    setState((held) => ({
      ...held,
      busyId: providerId,
      outcomes: Object.fromEntries(
        Object.entries(held.outcomes).filter(([id]) => id !== providerId),
      ),
    }));
    act(host, revision).then(
      () =>
        setState((held) =>
          mine !== generation.current
            ? held
            : {
                ...held,
                busyId: null,
                again: held.again + 1,
                changes: held.changes + 1,
              },
        ),
      (error: unknown) => {
        const code = failureCode(error);
        const served =
          typeof error === "object" && error !== null
            ? (error as { cause?: unknown; log_ref?: unknown })
            : {};
        const cause = signInCause(served.cause);
        const ref = logRef(served.log_ref);
        const outcome: ProviderOutcome =
          code === "committed_readback_failed"
            ? { kind: "saved_unread" }
            : {
                kind: "refused",
                code,
                ...(cause ? { cause } : {}),
                ...(ref ? { logRef: ref } : {}),
              };
        setState((held) =>
          mine !== generation.current
            ? held
            : {
                ...held,
                busyId: null,
                outcomes: { ...held.outcomes, [providerId]: outcome },
                // Saved all the same, so what depends on it is read again.
                changes:
                  outcome.kind === "saved_unread"
                    ? held.changes + 1
                    : held.changes,
                // A record changed elsewhere is shown as it is now.
                again:
                  code === "revision_conflict" ? held.again + 1 : held.again,
              },
        );
      },
    );
  };

  const refresh = useCallback(
    () =>
      setState((held) => ({
        ...held,
        again: held.again + 1,
        changes: held.changes + 1,
        outcomes: {},
      })),
    [],
  );
  const reread = useCallback(
    () => setState((held) => ({ ...held, again: held.again + 1 })),
    [],
  );
  return {
    read,
    busyId: state.busyId,
    outcomes: state.outcomes,
    save: (providerId, secret) =>
      change(providerId, (served, revision) =>
        served.set({
          provider: providerId,
          revision,
          secret: secret.secret,
          ...(secret.baseUrl !== undefined ? { base_url: secret.baseUrl } : {}),
        }),
      ),
    turnOff: (providerId) =>
      change(providerId, (served, revision) =>
        served.turnOff({ provider: providerId, revision }),
      ),
    turnOn: (providerId) =>
      change(providerId, (served, revision) =>
        served.turnOn({ provider: providerId, revision }),
      ),
    reset: (providerId) =>
      change(providerId, (served, revision) =>
        served.reset({ provider: providerId, revision }),
      ),
    signOut: (providerId) =>
      change(providerId, (served, revision) =>
        served.signOut({ provider: providerId, revision }),
      ),
    refresh,
    reread,
    changes: state.changes,
    accept: (status) => {
      put(status);
      setState((held) => ({ ...held, changes: held.changes + 1 }));
    },
  };
}
