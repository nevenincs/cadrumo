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
import type { AgentServiceStatus } from "./agentSession";
import { useCachedRead, type AgentRead } from "./agentViews";
import { CATALOG_BUSY_QUIET_MS } from "./catalogReadPolicy";
import { useWindowReturn } from "./modelListState";
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
  /** A console login completed. Its provider state must be read under the current profile. */
  observeConsoleLogin?(changed: () => void): Promise<() => void>;
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
    /** The same lanes as served, record by record. */
    records: readonly ProviderSettingsRecord[];
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
 * so the settings load only the first time. A busy answer (the host has not
 * yet admitted the service) and an answer the service says it is still
 * completing (`reads_pending`: the sign-in routes and the apps' states are
 * read behind it) wait on a cue, never on a timer: a status the service
 * publishes after the read was asked (`published`, which the service also
 * sends again once a read it answered busy or pending for has settled), the
 * person coming back to the window, or the person's own action. A cue that
 * comes while a read is out is taken as soon as that read ends.
 */
export function useProviderSettings(
  host: ProviderSettings | undefined,
  reader: string | null,
  open: boolean,
  opened: number,
  published: AgentServiceStatus | null,
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
  // The status last published, the one the newest read was asked under, and
  // whether that read is still out, so a publication causes one read, and
  // one that came while a read was out causes it once that read ends.
  const latest = useRef(published);
  useLayoutEffect(() => {
    latest.current = published;
  }, [published]);
  const askedUnder = useRef(published);
  const out = useRef(false);
  const readStatus = useMemo(
    () =>
      host && reader !== null
        ? () => {
            askedUnder.current = latest.current;
            out.current = true;
            const promise = host.status({
              retryable: (code) => code === "busy",
              scheduled: () => asking.current,
              expected: () =>
                following.current === null ||
                performance.now() - following.current.since <
                  CATALOG_BUSY_QUIET_MS,
            });
            const settled = () => {
              out.current = false;
            };
            promise.then(settled, settled);
            return promise;
          }
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
  // The last complete answer, kept while the service says a later one is
  // still being completed: such an answer carries only part of what the apps
  // and sign-in routes behind it will say, so it does not unsay a lane's
  // standing. A complete answer, or a change the person made to a lane,
  // replaces it.
  const [complete, setComplete] = useState<{
    owner: typeof owner;
    from: ProviderSettingsAnswer;
    providers: ReadonlyMap<string, ProviderSettingsRecord>;
  } | null>(null);
  if (answer.kind === "ready" && !answer.value.reads_pending) {
    if (complete?.from !== answer.value || complete.owner !== owner)
      setComplete({
        owner,
        from: answer.value,
        providers: new Map(
          answer.value.providers.map((lane) => [lane.id, lane]),
        ),
      });
  }
  // Since when the settings have answered busy, so its refusals are recorded
  // as the wait they are while it is the one expected.
  useEffect(() => {
    if (busy) following.current ??= { since: performance.now() };
    else following.current = null;
  }, [busy]);
  const waits = busy || pending;
  useEffect(() => {
    if (waits && !out.current && askedUnder.current !== published)
      setState((held) => ({ ...held, again: held.again + 1 }));
  }, [answer, waits, published]);
  useWindowReturn(
    waits
      ? () => setState((held) => ({ ...held, again: held.again + 1 }))
      : null,
  );
  const read = useMemo((): ProviderSettingsView["read"] => {
    if (answer.kind !== "ready") return answer;
    const earlier =
      answer.value.reads_pending && complete?.owner === owner ? complete : null;
    const served = earlier
      ? {
          ...answer.value,
          providers: answer.value.providers.map((lane) => {
            const before = earlier.providers.get(lane.id);
            // Only a lane the store left as it was keeps its earlier standing.
            return before &&
              before.mode === lane.mode &&
              before.credential_saved === lane.credential_saved
              ? { ...before, revision: lane.revision }
              : lane;
          }),
          sign_in_providers: earlier.from.sign_in_providers,
          sign_in_methods: earlier.from.sign_in_methods,
        }
      : answer.value;
    return {
      kind: "ready",
      value: {
        providers: served.providers.map(providerStatus),
        records: served.providers,
        signInProviders: Array.isArray(served.sign_in_providers)
          ? [...new Set<string>(served.sign_in_providers)]
          : [],
        signInMethods: Object.fromEntries(
          Object.entries(served.sign_in_methods ?? {}).flatMap(
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
        ...servedCommand(served.console_sign_in_command),
        revisions: Object.fromEntries(
          served.providers.map(({ id, revision }) => [id, revision] as const),
        ),
        readsPending: answer.value.reads_pending,
      },
    };
  }, [answer, complete, owner]);
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
      () => {
        // What the lane stands on is the change's to say, not the earlier answer's.
        setComplete((held) =>
          held
            ? {
                ...held,
                providers: new Map(
                  [...held.providers].filter(([id]) => id !== providerId),
                ),
              }
            : held,
        );
        setState((held) =>
          mine !== generation.current
            ? held
            : {
                ...held,
                busyId: null,
                again: held.again + 1,
                changes: held.changes + 1,
              },
        );
      },
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
  useEffect(() => {
    if (!host?.observeConsoleLogin || reader === null) return;
    let current = true;
    let stop: (() => void) | undefined;
    void host
      .observeConsoleLogin(() => {
        if (current) refresh();
      })
      .then((release) => {
        if (current) {
          stop = release;
          // Include a login completed between the initial read and registration.
          reread();
        } else release();
      })
      .catch(() => {
        if (current) {
          window.addEventListener("focus", refresh);
          stop = () => window.removeEventListener("focus", refresh);
        }
      });
    return () => {
      current = false;
      stop?.();
    };
  }, [host, reader, refresh, reread]);
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
