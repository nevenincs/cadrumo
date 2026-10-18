import { useCallback, useMemo, useRef, useState } from "react";
import type { StagedAttachment } from "@/components/agent/types";
import { failureCode } from "../errors";
import {
  MAX_REFERENCES,
  extensionOf,
  fileKindOf,
  stagedReference,
} from "./agentDocuments";
import type {
  AgentSession,
  AgentUploadEvent,
  AgentUploadPick,
} from "./agentSession";
import type { AgentDocumentRecord } from "./agentViews";
import type { Translate } from "./strings";

// What the next message of a conversation names of its stored documents: the
// ones chosen with `@`, and the files the person attaches, which are stored
// first and then named like any other. All of it belongs to the reader and
// the conversation it was staged in, whose storage holds the documents; any
// other conversation shows none of it.

/** The id a stored document is staged under; never an upload's. */
const storedId = (name: string) => `stored:${name}`;

/** Why a file was not stored, in words. */
export function uploadRefusalWords(t: Translate, code: string): string {
  switch (code) {
    case "agent_attachment_too_large":
    case "agent_gateway_attachment_too_large":
      return t("desktop.agent.upload_too_large");
    case "agent_attachment_format_refused":
    case "agent_gateway_attachment_format_refused":
      return t("desktop.agent.upload_format_refused");
    case "agent_gateway_attachment_quota_exceeded":
      return t("desktop.agent.upload_quota_exceeded");
    case "agent_attachment_unreadable":
      return t("desktop.agent.upload_unreadable");
    case "agent_attachment_name_refused":
      return t("desktop.agent.upload_name_refused");
    default:
      return t("desktop.agent.upload_failed");
  }
}

type Upload = StagedAttachment & { code?: string };

type Staging = {
  reader: string | null;
  conversation: string | null;
  documents: AgentDocumentRecord[];
  uploads: Upload[];
};

const fromPick = (pick: AgentUploadPick): Upload => ({
  id: pick.id,
  name: pick.name,
  extension: extensionOf(pick.name),
  sizeBytes: pick.size_bytes,
  kind: fileKindOf(pick.name, null),
  state: pick.state,
  ...(pick.code ? { code: pick.code } : {}),
});

/** `documents` with `document` named once more, unless it already is or the
 * message names all it can. */
const withNamed = (
  documents: AgentDocumentRecord[],
  document: AgentDocumentRecord,
) =>
  documents.some((kept) => kept.name === document.name) ||
  documents.length >= MAX_REFERENCES
    ? documents
    : [...documents, document];

export type StagedDocuments = {
  /** What the composer's well shows: the uploads still on their way or
   * refused, then the stored documents the message names. */
  staged: StagedAttachment[];
  /** The stored documents the next message of `conversationId` names. */
  namedFor: (conversationId: string | null) => AgentDocumentRecord[];
  /** Names a stored document for the next message. */
  name: (document: AgentDocumentRecord) => void;
  /** Takes a staged file away, or all of them. An upload taken away is not
   * named when it is stored. */
  remove: (id: string | null) => void;
  /** Forgets what a message of `conversationId` named once it went. */
  sent: (conversationId: string) => void;
  /** Picks files and stores them for `conversationId`, where the host can;
   * a refusal of the pick itself is given back as its code. */
  attach?: (conversationId: string) => Promise<string | null>;
};

export function useStagedDocuments({
  reader,
  conversationId,
  session,
  filterLabel,
  t,
}: {
  reader: string | null;
  conversationId: string | null;
  session: AgentSession | undefined;
  filterLabel: string;
  t: Translate;
}): StagedDocuments {
  const [staging, setStaging] = useState<Staging>({
    reader,
    conversation: conversationId,
    documents: [],
    uploads: [],
  });
  const own = (held: Staging, id: string | null) =>
    held.reader === reader && held.conversation === id;
  const current = own(staging, conversationId) ? staging : null;
  // What a change is made to: this reader and conversation's staging, a new
  // one where the last belonged to another.
  const update = useRef<
    (id: string | null, change: (held: Staging) => Staging) => void
  >(() => {});
  update.current = (id, change) =>
    setStaging((held) =>
      change(
        held.reader === reader && held.conversation === id
          ? held
          : { reader, conversation: id, documents: [], uploads: [] },
      ),
    );

  const name = useCallback(
    (document: AgentDocumentRecord) =>
      update.current(conversationId, (held) => ({
        ...held,
        documents: withNamed(held.documents, document),
      })),
    [conversationId],
  );
  const remove = (id: string | null) =>
    update.current(conversationId, (held) =>
      id === null
        ? { ...held, documents: [], uploads: [] }
        : {
            ...held,
            documents: held.documents.filter(
              (kept) => storedId(kept.name) !== id,
            ),
            uploads: held.uploads.filter((upload) => upload.id !== id),
          },
    );
  const sent = (id: string) =>
    setStaging((held) =>
      held.conversation === id ? { ...held, documents: [] } : held,
    );

  const attachHost = session?.attach?.bind(session);
  const attach = attachHost
    ? async (id: string) => {
        // An event for an upload no longer staged, or staged elsewhere, is
        // left alone; an upload stored is named for the next message.
        const onEvent = (event: AgentUploadEvent) =>
          setStaging((held) => {
            if (held.reader !== reader || held.conversation !== id) return held;
            const at = held.uploads.findIndex(
              (upload) => upload.id === event.id,
            );
            const upload = held.uploads[at];
            if (!upload) return held;
            const uploads = [...held.uploads];
            switch (event.kind) {
              case "progress":
                uploads[at] = {
                  ...upload,
                  state: "uploading",
                  progress:
                    upload.sizeBytes > 0 ? event.sent / upload.sizeBytes : 1,
                };
                return { ...held, uploads };
              case "refused":
                uploads[at] = {
                  ...upload,
                  state: "refused",
                  code: event.code,
                };
                return { ...held, uploads };
              case "stored":
                uploads.splice(at, 1);
                return {
                  ...held,
                  uploads,
                  documents: withNamed(held.documents, event.document),
                };
            }
          });
        try {
          const picked = await attachHost(id, filterLabel, onEvent);
          if (picked.length > 0)
            update.current(id, (held) => ({
              ...held,
              uploads: [
                ...held.uploads,
                ...picked
                  .map(fromPick)
                  .filter(
                    (pick) => !held.uploads.some((kept) => kept.id === pick.id),
                  ),
              ],
            }));
          return null;
        } catch (error) {
          return failureCode(error);
        }
      }
    : undefined;

  const documents = current?.documents;
  const uploads = current?.uploads;
  const staged = useMemo(
    (): StagedAttachment[] => [
      ...(uploads ?? []).map(({ code, ...upload }) =>
        code
          ? { ...upload, refusalReason: uploadRefusalWords(t, code) }
          : upload,
      ),
      ...(documents ?? []).map((document) => ({
        ...stagedReference(document),
        id: storedId(document.name),
      })),
    ],
    [documents, uploads, t],
  );

  return {
    staged,
    namedFor: (id) => (own(staging, id) ? staging.documents : []),
    name,
    remove,
    sent,
    ...(attach ? { attach } : {}),
  };
}
