import type { AgentAccess, AgentCredentialRecord } from "../shell/agentAccess";

// The scenario host's API keys for agents outside Cadrumo: a profile that has
// issued a few, one in each standing. A change is checked as the product
// checks it and then forgotten: issuing is the signed-in person's one act, and
// the one thing it hands back is a reference, never a key.

/** A key whose revoke is taken, while the key stored on the computer is still
 * to be removed. */
export const CLEANUP_PENDING_ID = "e5b1d0c2-4a7f-4c63-9b3e-0d1f2a3b4c5d";

/** The id of the key that has been used most recently. */
export const USED_ID = "3f9a1c2e-71b4-4d58-a9c0-6e2d8b14f7a3";

const DAY = 24 * 60 * 60 * 1000;

const coded = (code: string) => Object.assign(new Error(code), { code });

export function agentAccessFixture({
  say,
  wait,
  readable,
  now = () => new Date(),
}: {
  say: (call: string) => void;
  wait: () => Promise<void>;
  /** A profile is signed in whose keys these are. */
  readable: () => boolean;
  now?: () => Date;
}): AgentAccess {
  const at = (days: number) => new Date(now().getTime() + days * DAY);
  const iso = (days: number) => at(days).toISOString();
  const agent = ["profile_values", "operation_metadata"] as const;
  const records = new Map<string, AgentCredentialRecord>(
    (
      [
        {
          id: USED_ID,
          state: "active",
          issued_at: iso(-90),
          expires_at: iso(275),
          last_used_at: iso(-1),
          categories: [...agent, "tax_values"],
          all_operations: true,
        },
        {
          id: "b7c4e2d9-0a13-4f6b-8e75-1c9d3a5f2b60",
          state: "active",
          issued_at: iso(-12),
          expires_at: iso(353),
          last_used_at: null,
          categories: [...agent],
          all_operations: true,
        },
        {
          id: CLEANUP_PENDING_ID,
          state: "active",
          issued_at: iso(-30),
          expires_at: iso(335),
          last_used_at: iso(-8),
          categories: [...agent],
          all_operations: true,
        },
        {
          id: "9d2f6a41-c8e3-4b07-a5d1-7f0e4c8b3a29",
          state: "suspended",
          issued_at: iso(-60),
          expires_at: iso(305),
          last_used_at: iso(-20),
          categories: [...agent],
          all_operations: true,
        },
        {
          id: "2a8e5c70-d4b9-4136-8f2a-5e7c1b9d0f44",
          state: "active",
          issued_at: iso(-400),
          expires_at: iso(-35),
          last_used_at: iso(-60),
          categories: [...agent],
          all_operations: true,
        },
        {
          id: "6c0b9e83-f1a5-47d2-b8c4-3a6e9d2f7015",
          state: "revoked",
          issued_at: iso(-120),
          expires_at: iso(245),
          last_used_at: iso(-100),
          categories: [...agent, "tax_values"],
          all_operations: true,
        },
      ] satisfies AgentCredentialRecord[]
    ).map((record) => [record.id, record]),
  );

  return {
    async list() {
      say("agentAccessList");
      await wait();
      if (!readable()) throw coded("not_signed_in");
      return { credentials: [...records.values()].map((r) => ({ ...r })) };
    },
    async issue({ tax_values }) {
      say("agentAccessIssue");
      await wait();
      if (!readable()) throw coded("not_signed_in");
      const id = crypto.randomUUID();
      records.set(id, {
        id,
        state: "active",
        issued_at: iso(0),
        expires_at: iso(365),
        last_used_at: null,
        categories: [
          ...agent,
          ...(tax_values ? (["tax_values"] as const) : []),
        ],
        all_operations: true,
      });
      return { credential_reference: crypto.randomUUID() };
    },
    async revoke({ grant_id }) {
      say(`agentAccessRevoke ${grant_id.slice(0, 8)}`);
      await wait();
      if (!readable()) throw coded("not_signed_in");
      const record = records.get(grant_id);
      if (!record) throw coded("not_found");
      records.set(grant_id, { ...record, state: "revoked" });
      return { cleanup_pending: grant_id === CLEANUP_PENDING_ID };
    },
  };
}
