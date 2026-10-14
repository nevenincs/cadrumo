import { useCallback, useMemo, useState } from "react";
import type {
  ProviderOutcome,
  ProviderSecret,
  ProviderStatus,
} from "@/components/settings/types";
import { failureCode } from "../errors";
import { useAgentRead, type AgentRead } from "./agentViews";

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
};

export type ProviderSettingsAnswer = {
  /** A development build, where a provider with no key uses the
   * environment's. The host says which build it is. */
  development: boolean;
  providers: ProviderSettingsRecord[];
};

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
  status(): Promise<ProviderSettingsAnswer>;
  /** Saves a key or token. The secret is handed on once and never kept.
   * Each change answers with the provider's new status. */
  set(change: {
    provider: string;
    revision: string;
    secret: string;
    base_url?: string;
  }): Promise<ProviderSettingsRecord>;
  /** Disables the lane: nothing, not even the environment, is used. */
  turnOff(change: {
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
  ...(record.reason ? { reason: record.reason } : {}),
  ...(record.base_url ? { baseUrl: record.base_url } : {}),
  ...(record.default_base_url
    ? { defaultBaseUrl: record.default_base_url }
    : {}),
});

export type ProviderSettingsView = {
  read: AgentRead<{ development: boolean; providers: ProviderStatus[] }>;
  busyId: string | null;
  outcomes: Readonly<Record<string, ProviderOutcome>>;
  save: (providerId: string, secret: ProviderSecret) => void;
  turnOff: (providerId: string) => void;
  reset: (providerId: string) => void;
  refresh: () => void;
};

/**
 * The providers of `reader`'s profile while `open`, read when opened, after
 * each change of the person's and when asked to refresh; never on a timer.
 */
export function useProviderSettings(
  host: ProviderSettings | undefined,
  reader: string | null,
  open: boolean,
): ProviderSettingsView {
  const [state, setState] = useState({
    reader,
    again: 0,
    busyId: null as string | null,
    outcomes: {} as Record<string, ProviderOutcome>,
  });
  if (state.reader !== reader)
    setState({ reader, again: 0, busyId: null, outcomes: {} });
  const readStatus = useMemo(
    () => (host && reader !== null && open ? () => host.status() : null),
    [host, reader, open],
  );
  const answer = useAgentRead(readStatus, state.again);
  const read = useMemo(
    (): ProviderSettingsView["read"] =>
      answer.kind === "ready"
        ? {
            kind: "ready",
            value: {
              development: answer.value.development,
              providers: answer.value.providers.map(providerStatus),
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
    if (!host || revision === undefined) return;
    setState((held) => ({
      ...held,
      busyId: providerId,
      outcomes: Object.fromEntries(
        Object.entries(held.outcomes).filter(([id]) => id !== providerId),
      ),
    }));
    act(host, revision).then(
      () =>
        setState((held) => ({ ...held, busyId: null, again: held.again + 1 })),
      (error: unknown) => {
        const code = failureCode(error);
        const outcome: ProviderOutcome =
          code === "committed_readback_failed"
            ? { kind: "saved_unread" }
            : { kind: "refused", code };
        setState((held) => ({
          ...held,
          busyId: null,
          outcomes: { ...held.outcomes, [providerId]: outcome },
          // A record changed elsewhere is shown as it is now.
          again: code === "revision_conflict" ? held.again + 1 : held.again,
        }));
      },
    );
  };

  const refresh = useCallback(
    () =>
      setState((held) => ({ ...held, again: held.again + 1, outcomes: {} })),
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
    reset: (providerId) =>
      change(providerId, (served, revision) =>
        served.reset({ provider: providerId, revision }),
      ),
    refresh,
  };
}
