import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";
import type {
  ProviderOutcome,
  ProviderSecret,
  ProviderStatus,
} from "@/components/settings/types";
import { failureCode } from "../errors";
import type { CallPlan } from "./hostCall";
import { useCachedRead, type AgentRead } from "./agentViews";
import {
  cliStateCause,
  consoleCommandTemplate,
  nextStep,
  type CliStateCause,
  type NextStep,
  type SignInCause,
} from "./providerSignInWords";

// The model providers of the signed-in profile, as a host serves them: the
// masked status of each lane (a provider's API, or its command-line app),
// and the person's ways to set, disable or reset its key. A key goes to the host once, in the call that saves it, and comes
// back from nowhere: no answer here carries a key, and nothing keeps one.

export type ProviderSettingsRecord = {
  /** The lane's id, `<provider>_<transport>`, which each change names. One
   * provider has a lane for its API and one for its command-line app. */
  id: string;
  /** The provider the lane reaches, as cadrumo-agent names it: shared by
   * every lane of that provider. */
  provider: string;
  /** The provider's product name, the same in every language and on each of
   * its lanes. */
  display_name: string;
  /** Its web API, or its command-line app. */
  transport: ProviderStatus["transport"];
  auth_kind: ProviderStatus["authKind"];
  mode: ProviderStatus["mode"];
  available: boolean;
  source: ProviderStatus["source"];
  readiness: ProviderStatus["readiness"];
  /** Null when ready, else a closed code: a refusal code, or
   * `not_configured`, `turned_off`, `sign_in_with_provider_tool` or
   * `record_unreadable`. */
  reason?: string | null;
  base_url?: string | null;
  default_base_url?: string | null;
  /** Sent back with a change, so a record changed elsewhere is not
   * overwritten: 64 lowercase hex digits, all zeros for a lane that has no
   * record. */
  revision: string;
  /** Where the lane's command-line app stands on this computer; only a
   * command-line lane has one. */
  cli_state?: ProviderStatus["cliState"] | null;
  /** Why the app's state is not established, as a closed word; a word this
   * window does not know is dropped. */
  cli_state_cause?: CliStateCause | null;
  /** What to do about `cli_state_cause`, as a closed word. */
  next_step?: NextStep | null;
  /** Whether a key is stored for the lane, whatever its mode: one that is
   * turned off keeps it for when it is turned on again. */
  credential_saved?: boolean;
};

export type ProviderSettingsAnswer = {
  providers: ProviderSettingsRecord[];
  /** Canonical providers the agent declares usable from the GUI sign-in flow.
   * Missing means no provider supports it. */
  sign_in_providers?: string[];
  /** GUI sign-in methods supported per canonical provider slug. */
  sign_in_methods?: Record<string, ProviderSignInMethod[]>;
  /** The console command that signs a provider in by hand, with a
   * `{provider}` slot for the provider's id. Absent when not served. */
  console_sign_in_command?: string;
};

export type ProviderSignInMethod = "browser" | "device" | "browser-code";
export type ProviderSignInEvent =
  | "starting"
  | "started"
  | "browser_action"
  | "authorization_code_required"
  | "succeeded"
  | "cancelled"
  | "failed";

/** Transient progress for a person-started provider sign-in attempt. */
export type ProviderSignInSnapshot = {
  attempt_id: string;
  /** Lane id, such as `codex_cli`. */
  provider: string;
  event: ProviderSignInEvent;
  reason?: string;
  /** Why the attempt did not succeed, as a closed word, on a failed or
   * cancelled attempt. */
  cause?: SignInCause;
  /** What to do about `cause`, as a closed word. */
  next_step?: NextStep;
  /** Why the status read after the attempt did not establish a sign-in. */
  status_cause?: CliStateCause;
  /** Present only while the person can open the provider's sign-in page. */
  url?: string;
  /** Device-flow code; shown only while this attempt is active. */
  user_code?: string;
};

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
export type ProviderSettingsRefusal =
  | "not_signed_in"
  | "profile_locked"
  | "invalid_key_format"
  | "base_url_rejected"
  | "revision_conflict"
  | "committed_readback_failed"
  | "catalog_unavailable"
  | "runtime_unavailable"
  | "person_act_required"
  | "unknown";

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
}

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
});

export type ProviderSettingsView = {
  read: AgentRead<{
    providers: ProviderStatus[];
    signInProviders: string[];
    signInMethods: Readonly<Record<string, readonly ProviderSignInMethod[]>>;
    consoleSignInCommand?: string;
    revisions: Readonly<Record<string, string>>;
  }>;
  busyId: string | null;
  outcomes: Readonly<Record<string, ProviderOutcome>>;
  save: (providerId: string, secret: ProviderSecret) => void;
  turnOff: (providerId: string) => void;
  turnOn: (providerId: string) => void;
  reset: (providerId: string) => void;
  refresh: () => void;
  /** Invalidations of the agent's provider list, including authentication
   * observed by a status refresh or a read made elsewhere. */
  changes: number;
  /** Shows a status read made elsewhere, in place of reading it again. */
  accept: (status: ProviderSettingsAnswer) => void;
};

/**
 * The providers of `reader`'s profile while `open`: read each time they open
 * (`opened` counts the openings), after each change of the person's and when
 * asked to refresh; never on a timer. The last answer stays on screen while
 * it is read again, so the settings load only the first time.
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
  const readStatus = useMemo(
    () => (host && reader !== null ? () => host.status() : null),
    [host, reader],
  );
  const { read: answer, put } = useCachedRead(
    readStatus,
    reader,
    open,
    state.again + opened,
  );
  const read = useMemo(
    (): ProviderSettingsView["read"] =>
      answer.kind === "ready"
        ? {
            kind: "ready",
            value: {
              providers: answer.value.providers.map(providerStatus),
              signInProviders: Array.isArray(answer.value.sign_in_providers)
                ? [...new Set(answer.value.sign_in_providers)]
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
              ...(consoleCommandTemplate(answer.value.console_sign_in_command)
                ? {
                    consoleSignInCommand: answer.value.console_sign_in_command,
                  }
                : {}),
              revisions: Object.fromEntries(
                answer.value.providers.map(
                  ({ id, revision }) => [id, revision] as const,
                ),
              ),
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
        const outcome: ProviderOutcome =
          code === "committed_readback_failed"
            ? { kind: "saved_unread" }
            : { kind: "refused", code };
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
    refresh,
    changes: state.changes,
    accept: (status) => {
      put(status);
      setState((held) => ({ ...held, changes: held.changes + 1 }));
    },
  };
}
