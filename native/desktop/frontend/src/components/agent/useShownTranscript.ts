import { useMemo } from "react";
import type { useLiveConversation } from "../../shell/agentLive";
import {
  createTranscriptProjection,
  replyIdOf,
  type AgentRead,
  type transcriptItems,
} from "../../shell/agentViews";
import type { Translate } from "../../shell/strings";
import type { PendingSend } from "./agentColumnView";

/**
 * The conversation as the transcript draws it: what the agent kept of its
 * runs, with a message sent and not yet kept shown in its place, as sending
 * until the agent acknowledges it.
 */
export function useShownTranscript(
  read: ReturnType<typeof useLiveConversation>["read"],
  pending: PendingSend | null,
  locale: string,
  t: Translate,
): AgentRead<ReturnType<typeof transcriptItems>> {
  const projectTranscript = useMemo(() => createTranscriptProjection(), []);
  return useMemo((): AgentRead<ReturnType<typeof transcriptItems>> => {
    if (read.kind !== "ready" && !pending) return read;
    const records = read.kind === "ready" ? [...read.value] : [];
    // Keep the person's words ahead of any events that beat the send
    // acknowledgement, and through an initial history read still in flight.
    const echoed =
      pending &&
      records.some(
        (record) =>
          record.kind === "person" &&
          record.text === pending.text &&
          (pending.replyId
            ? record.reply_id === pending.replyId
            : !pending.previousReplies.includes(record.reply_id)),
      );
    if (pending && !echoed) {
      const nextReply = records.findIndex((record) =>
        pending.replyId
          ? replyIdOf(record) === pending.replyId
          : !pending.previousReplies.includes(replyIdOf(record)),
      );
      records.splice(nextReply < 0 ? records.length : nextReply, 0, {
        kind: "person",
        id: pending.id,
        reply_id: pending.replyId ?? pending.id,
        text: pending.text,
        sent_at: null,
        attachments: pending.attachments,
        skills: pending.skills,
      });
    }
    const items = projectTranscript(records, locale, t);
    return {
      kind: "ready",
      value: items.map((item) =>
        pending &&
        pending.replyId === null &&
        item.kind === "person" &&
        item.id === `person:${pending.id}:${pending.id}`
          ? { ...item, sending: true }
          : item,
      ),
    };
  }, [read, pending, locale, t, projectTranscript]);
}
