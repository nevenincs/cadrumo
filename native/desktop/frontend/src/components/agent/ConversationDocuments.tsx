import {
  extensionOf,
  fileKindOf,
  MAX_REFERENCES,
} from "../../shell/agentDocuments";
import type { useDocumentInventory } from "../../shell/agentDocumentInventory";
import type { AgentSession } from "../../shell/agentSession";
import { useStrings } from "../../shell/strings";
import { AttachmentGrants } from "./AttachmentGrants";
import { DocumentsPanel } from "./DocumentsPanel";
import { ReadState, SectionFailure } from "./ReadState";

/** The documents stored in the conversation shown, which the next message
 * can name, with the files each grant lets the agent read. */
export function ConversationDocuments({
  documents,
  reader,
  conversationId,
  session,
  locale,
  named,
  onClose,
  onAddFiles,
  onName,
  onRemove,
}: {
  documents: ReturnType<typeof useDocumentInventory>;
  reader: string | null;
  conversationId: string | null;
  session: AgentSession | undefined;
  locale: string;
  /** The names of the documents the next message names. */
  named: string[];
  onClose: () => void;
  onAddFiles?: () => void;
  /** Names a stored document in the next message. */
  onName: (name: string) => void;
  /** Removes a stored document, or every one where `name` is null. */
  onRemove?: (name: string | null) => void;
}) {
  const t = useStrings();
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {documents.failed && (
        <p role="alert" className="px-3 py-2 text-sm text-destructive">
          {t("desktop.agent.document_remove_failed")}
        </p>
      )}
      {documents.read.kind === "ready" ? (
        <DocumentsPanel
          key={`${reader}:${conversationId}`}
          documents={documents.read.value.map((document) => ({
            id: document.name,
            name: document.name,
            extension: extensionOf(document.name),
            sizeBytes: document.size_bytes,
            kind: fileKindOf(document.name, document.media_type),
          }))}
          locale={locale}
          busy={documents.busy}
          selectionLimit={MAX_REFERENCES}
          selectedIds={named}
          footer={session ? <AttachmentGrants session={session} /> : undefined}
          onClose={onClose}
          onAddFiles={onAddFiles}
          onRefresh={documents.refresh}
          onUse={onName}
          onRemove={onRemove}
        />
      ) : documents.read.kind === "failed" ? (
        <SectionFailure
          words={t("desktop.agent.mention_failed")}
          onRetry={documents.refresh}
        />
      ) : (
        <ReadState read={documents.read} icon="page" />
      )}
    </div>
  );
}
