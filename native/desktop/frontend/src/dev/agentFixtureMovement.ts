import type { AgentDocumentRecord } from "../shell/agentViews";

declare global {
  interface Window {
    /** Why the host refuses the next movement handed to a conversation,
     * as it would reject: a code, and the words a ledger refusal served. */
    __fixtureMovementRefusal?: { code: string; refusal_words?: string };
  }
}

/** The scenario host's store of a Libro movement in a conversation, where
 * the profile's ledger serves movements: the movement read's answer, stored
 * unchanged as JSON from memory in `storage` and named from its own date and
 * id, as the desktop host does. `check` refuses as every agent call does
 * while the profile cannot read. */
export function fixtureMovementAttach(
  say: (call: string) => void,
  check: () => Promise<void>,
  storage: Map<string, AgentDocumentRecord[]>,
  readMovement: ((transactionId: string) => Promise<object>) | undefined,
): {
  attachLedgerMovement?: (
    conversationId: string,
    transactionId: string,
  ) => Promise<AgentDocumentRecord>;
} {
  if (!readMovement) return {};
  return {
    async attachLedgerMovement(conversationId, transactionId) {
      say(`agentAttachLedgerMovement ${conversationId} ${transactionId}`);
      await check();
      const refusal = window.__fixtureMovementRefusal;
      if (refusal) throw Object.assign(new Error(refusal.code), refusal);
      const served = await readMovement(transactionId);
      const transaction = (
        served as { transaction?: { date?: string; transaction_id?: string } }
      ).transaction;
      if (!transaction?.date || !transaction.transaction_id)
        throw Object.assign(new Error("agent_movement_unreadable"), {
          code: "agent_movement_unreadable",
        });
      const bytes = new TextEncoder().encode(JSON.stringify(served, null, 2));
      const digest = new Uint8Array(
        await crypto.subtle.digest("SHA-256", bytes),
      );
      const document: AgentDocumentRecord = {
        name: `movimiento-${transaction.date}-${transaction.transaction_id.slice(0, 8)}.json`,
        size_bytes: bytes.length,
        modified_at: new Date().toISOString(),
        sha256: Array.from(digest, (byte) =>
          byte.toString(16).padStart(2, "0"),
        ).join(""),
        media_type: "application/json",
      };
      storage.set(
        conversationId,
        [
          ...(storage.get(conversationId) ?? []).filter(
            (kept) => kept.name !== document.name,
          ),
          document,
        ].sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0)),
      );
      return document;
    },
  };
}
