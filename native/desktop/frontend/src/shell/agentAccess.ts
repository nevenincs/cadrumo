import { useCallback, useMemo, useState } from "react";
import type {
  AgentCredential,
  AgentCredentialCategory,
  AgentCredentialOutcome,
  AgentCredentialStanding,
  AgentKeyChoice,
  IssuedKey,
} from "@/components/settings/AgentAccess";
import { failureCode } from "../errors";
import { useAgentRead, type AgentRead } from "./agentViews";

// The API keys the signed-in profile has issued to agents outside Cadrumo, as
// a host serves them: each key's standing and what it may do, and the person's
// ways to issue one and to revoke one. These are the person's own acts: the
// host takes them from the product's command line, which refuses them to an
// agent. Issuing is one act of the signed-in person's, with no password to
// repeat and no second approval. No answer here carries a key. A new key is put
// in this computer's secure store and comes back as a reference only, once, in
// the answer to the call that issued it.

/** Where a key's grant stands in the profile. Whether it has run out is a
 * matter of the time, which the shell tells for itself. */
export type AgentCredentialState =
  "pending" | "active" | "suspended" | "revoked";

export type AgentCredentialRecord = {
  /** The grant's id: what a revoke names, and what tells keys apart. */
  id: string;
  state: AgentCredentialState;
  /** When the grant became valid, as an ISO instant: when it was issued. */
  issued_at: string;
  expires_at: string;
  /** When one of its keys last let an agent in, as an ISO instant; null when
   * none has, or none is known to have. */
  last_used_at: string | null;
  /** The data categories the grant releases to the agent. */
  categories: AgentCredentialCategory[];
  /** The grant covers every operation an agent may run, not a chosen few. */
  all_operations: boolean;
};

export type AgentAccessAnswer = {
  credentials: AgentCredentialRecord[];
};

/** Why a change was refused, as a stable code. `outcome_unknown` means the
 * host did not hear how a change ended: the key may or may not exist. */
export type AgentAccessRefusal =
  | "not_signed_in"
  | "profile_locked"
  | "not_found"
  | "outcome_unknown"
  | "person_act_required"
  /** Issuing a key from here is not served yet. */
  | "issue_unavailable"
  | "unknown";

export interface AgentAccess {
  /** Every key of the signed-in profile, ended ones included. */
  list(): Promise<AgentAccessAnswer>;
  /**
   * Issues a key for an agent, as the signed-in person's own act, and answers
   * with the reference the key is named by. The key is not returned, it is put
   * in this computer's secure store.
   */
  issue(request: {
    tax_values: boolean;
  }): Promise<{ credential_reference: string }>;
  /** Revokes one grant, and so its keys. It answers once access is denied;
   * `cleanup_pending` says the stored key is still to be removed from this
   * computer. */
  revoke(request: { grant_id: string }): Promise<{ cleanup_pending: boolean }>;
}

/** Where a key stands at `now`: a grant that has run out is expired, whatever
 * else it was. */
export function credentialStanding(
  record: Pick<AgentCredentialRecord, "state" | "expires_at">,
  now: Date,
): AgentCredentialStanding {
  if (record.state === "revoked") return "revoked";
  const end = new Date(record.expires_at).getTime();
  // A date that cannot be read is not taken to be a key that still works.
  if (!Number.isFinite(end) || end <= now.getTime()) return "expired";
  return record.state;
}

/** A key as the section shows it, at the instant its list was read. */
export function agentCredential(
  record: AgentCredentialRecord,
  readAt: Date,
): AgentCredential {
  return {
    id: record.id,
    standing: credentialStanding(record, readAt),
    issuedAt: record.issued_at,
    expiresAt: record.expires_at,
    ...(record.last_used_at ? { lastUsedAt: record.last_used_at } : {}),
    categories: record.categories,
    allOperations: record.all_operations,
  };
}

export type AgentAccessView = {
  read: AgentRead<{ credentials: AgentCredential[] }>;
  /** The key whose revoke is on its way. */
  busyId: string | null;
  outcomes: Readonly<Record<string, AgentCredentialOutcome>>;
  issuing: boolean;
  issueRefusal: string | null;
  issued: IssuedKey | null;
  issue: (choice: AgentKeyChoice) => void;
  /** Forgets the key just issued and any refusal to issue one. */
  closeIssue: () => void;
  revoke: (id: string) => void;
  refresh: () => void;
};

const fresh = (reader: string | null) => ({
  reader,
  again: 0,
  busyId: null as string | null,
  outcomes: {} as Record<string, AgentCredentialOutcome>,
  issuing: false,
  issueRefusal: null as string | null,
  issued: null as IssuedKey | null,
});

/**
 * The keys of `reader`'s profile while `open`, read when opened, after each
 * change of the person's and when asked to refresh; never on a timer. With no
 * reader, nobody is signed in and the host is not asked anything. A key just
 * issued is shown until it is closed and is dropped with the profile or when
 * the section closes, so it is never seen twice.
 */
export function useAgentAccess(
  host: AgentAccess | undefined,
  reader: string | null,
  open: boolean,
): AgentAccessView {
  const [state, setState] = useState(() => fresh(reader));
  if (state.reader !== reader) setState(fresh(reader));
  else if (!open && (state.issued !== null || state.issueRefusal !== null))
    setState((held) => ({ ...held, issued: null, issueRefusal: null }));

  const readList = useMemo(
    () =>
      host && reader !== null && open
        ? () => host.list().then((answer) => ({ answer, readAt: new Date() }))
        : null,
    [host, reader, open],
  );
  const answer = useAgentRead(readList, state.again);
  const read = useMemo(
    (): AgentAccessView["read"] =>
      answer.kind === "ready"
        ? {
            kind: "ready",
            value: {
              credentials: answer.value.answer.credentials.map((record) =>
                agentCredential(record, answer.value.readAt),
              ),
            },
          }
        : answer,
    [answer],
  );

  // A change settles only for the profile that asked: an answer that comes
  // after the person has moved to another is dropped.
  const settle = (
    asked: string | null,
    change: (held: ReturnType<typeof fresh>) => ReturnType<typeof fresh>,
  ) => setState((held) => (held.reader === asked ? change(held) : held));

  const issue = (choice: AgentKeyChoice) => {
    if (!host || reader === null || state.issuing) return;
    const asked = reader;
    setState((held) => ({
      ...held,
      issuing: true,
      issueRefusal: null,
      issued: null,
    }));
    host.issue({ tax_values: choice.taxValues }).then(
      (key) =>
        settle(asked, (held) => ({
          ...held,
          issuing: false,
          issued: { reference: key.credential_reference },
          again: held.again + 1,
        })),
      (error: unknown) => {
        const code = failureCode(error);
        settle(asked, (held) => ({
          ...held,
          issuing: false,
          issueRefusal: code,
          // The key may exist all the same: the list is read again.
          again: code === "outcome_unknown" ? held.again + 1 : held.again,
        }));
      },
    );
  };

  const revoke = (id: string) => {
    if (!host || reader === null) return;
    const asked = reader;
    setState((held) => ({
      ...held,
      busyId: id,
      outcomes: Object.fromEntries(
        Object.entries(held.outcomes).filter(([key]) => key !== id),
      ),
    }));
    host.revoke({ grant_id: id }).then(
      (revoked) =>
        settle(asked, (held) => ({
          ...held,
          busyId: null,
          outcomes: revoked.cleanup_pending
            ? { ...held.outcomes, [id]: { kind: "revoked_cleanup_pending" } }
            : held.outcomes,
          again: held.again + 1,
        })),
      (error: unknown) => {
        const code = failureCode(error);
        settle(asked, (held) => ({
          ...held,
          busyId: null,
          outcomes: {
            ...held.outcomes,
            [id]: { kind: "refused", code },
          },
          // A key that is not there, or whose end is not known, is shown as it
          // is now.
          again:
            code === "not_found" || code === "outcome_unknown"
              ? held.again + 1
              : held.again,
        }));
      },
    );
  };

  const closeIssue = useCallback(
    () => setState((held) => ({ ...held, issued: null, issueRefusal: null })),
    [],
  );
  const refresh = useCallback(
    () =>
      setState((held) => ({ ...held, again: held.again + 1, outcomes: {} })),
    [],
  );
  return {
    read,
    busyId: state.busyId,
    outcomes: state.outcomes,
    issuing: state.issuing,
    issueRefusal: state.issueRefusal,
    issued: state.issued,
    issue,
    closeIssue,
    revoke,
    refresh,
  };
}
