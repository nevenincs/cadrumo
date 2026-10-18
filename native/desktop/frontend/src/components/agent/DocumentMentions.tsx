import { Icon } from "@/components/ui/icon";
import { fileKindOf, type DocumentLister } from "../../shell/agentDocuments";
import type { AgentDocumentRecord } from "../../shell/agentViews";
import type { Translate } from "../../shell/strings";
import type { SuggestionSource } from "./ComposerSuggestions";
import { charTrigger } from "./composerTrigger";
import { KIND_GLYPH, formatSize } from "./files";

const atToken = charTrigger("@");

/**
 * What an `@` offers in the composer: the documents stored for the
 * conversation, every one whose name holds what follows the `@`. Choosing one
 * writes `@name` in place of the token and names the document for the next
 * message through `onPick`. A conversation not started yet has nothing
 * stored, and a host that serves no storage says so rather than showing none.
 */
export function documentSource({
  lister,
  conversationId,
  locale,
  t,
  onPick,
}: {
  /** Null where the host serves no stored documents. */
  lister: DocumentLister | null;
  conversationId: string | null;
  locale: string;
  t: Translate;
  onPick: (document: AgentDocumentRecord) => void;
}): SuggestionSource<AgentDocumentRecord> {
  return {
    id: "documents",
    match: atToken,
    items: (query, signal) => {
      if (!lister) throw new Error("agent_documents_unavailable");
      if (conversationId === null) return [];
      return lister.matching(conversationId, query, signal);
    },
    key: (document) => document.name,
    render: (document) => (
      <>
        <Icon
          name={KIND_GLYPH[fileKindOf(document.name, document.media_type)]}
          size="sm"
          className="shrink-0 text-muted-foreground"
        />
        <span className="min-w-0 flex-1 truncate" title={document.name}>
          {document.name}
        </span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {formatSize(locale, document.size_bytes)}
        </span>
      </>
    ),
    accept: (document) => {
      onPick(document);
      return `@${document.name} `;
    },
    label: t("desktop.agent.mention_label"),
    empty: t("desktop.agent.mention_empty"),
    loading: t("desktop.agent.mention_loading"),
    failed: lister
      ? t("desktop.agent.mention_failed")
      : t("desktop.agent.mention_unavailable"),
  };
}
