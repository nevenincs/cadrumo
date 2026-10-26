import { useMemo, useRef, useState } from "react";
import { failureCode } from "../errors";
import { readAllDocuments } from "./agentDocuments";
import type { AgentSession } from "./agentSession";
import { useAgentRead, type AgentViews } from "./agentViews";

/** Authoritative stored files for the visible conversation. A mutation never
 * updates another conversation, and an uncertain removal is read back. */
export function useDocumentInventory({
  agent,
  session,
  reader,
  conversationId,
  enabled,
  version,
}: {
  agent: AgentViews | undefined;
  session: AgentSession | undefined;
  reader: string | null;
  conversationId: string | null;
  enabled: boolean;
  version: number;
}) {
  const [again, setAgain] = useState(0);
  const owner = useMemo(
    () => ({ reader, conversationId, session }),
    [reader, conversationId, session],
  );
  const [mutation, setMutation] = useState<{
    source: unknown;
    busy: boolean;
    failed: boolean;
  }>({ source: null, busy: false, failed: false });
  const source = useMemo(
    () =>
      enabled && owner.reader !== null && agent?.documents
        ? () =>
            owner.conversationId === null
              ? Promise.resolve([])
              : readAllDocuments(
                  agent.documents!.bind(agent),
                  owner.conversationId,
                )
        : null,
    [agent, owner, enabled],
  );
  const current = useRef(source);
  current.current = source;
  const read = useAgentRead(source, again + version);
  const [counts, setCounts] = useState<{
    reader: string | null;
    values: Readonly<Record<string, number>>;
  }>({ reader, values: {} });
  if (counts.reader !== reader) setCounts({ reader, values: {} });
  else if (
    conversationId !== null &&
    read.kind === "ready" &&
    counts.values[conversationId] !== read.value.length
  )
    setCounts({
      reader,
      values: { ...counts.values, [conversationId]: read.value.length },
    });
  const refresh = () => setAgain((held) => held + 1);
  const remove =
    session?.removeDocuments && conversationId !== null && source
      ? async (name: string | null) => {
          setMutation({ source, busy: true, failed: false });
          let succeeded = false;
          try {
            await session.removeDocuments!(conversationId, name ?? undefined);
            succeeded = true;
          } catch (error) {
            // Unknown outcomes are reconciled by the listing, never retried here.
            if (failureCode(error) === "agent_gateway_attachment_not_found")
              succeeded = true;
          }
          if (current.current !== source) return false;
          setMutation({ source, busy: false, failed: !succeeded });
          refresh();
          return succeeded;
        }
      : undefined;
  return {
    read,
    refresh,
    remove,
    busy: mutation.source === source && mutation.busy,
    failed: mutation.source === source && mutation.failed,
    counts: counts.reader === reader ? counts.values : {},
  };
}
