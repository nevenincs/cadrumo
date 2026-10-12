import {
  useCallback,
  useMemo,
  useState,
  type ReactNode,
  type Ref,
} from "react";
import { Empty, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Icon, type IconName } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import {
  archivedCount,
  conversationDocument,
  transcriptItems,
  useAgentRead,
  useConversationGroups,
  type AgentRead,
  type AgentViews,
} from "../shell/agentViews";
import { useStrings } from "../shell/strings";
import { AgentHeader } from "./agent/AgentHeader";
import { AgentWelcome } from "./agent/AgentWelcome";
import { Composer } from "./agent/Composer";
import { DocumentsPanel } from "./agent/DocumentsPanel";
import { HistoryList } from "./agent/HistoryList";
import { Transcript } from "./agent/Transcript";
import type {
  AgentSelection,
  ModelOption,
  ProviderOption,
  StagedAttachment,
} from "./agent/types";

// What the composer is given while nothing serves it: nothing. Sending,
// adding files and choosing a model each say they are not available yet.
const NO_ATTACHMENTS: StagedAttachment[] = [];
const NO_PROVIDERS: ProviderOption[] = [];
const NO_MODELS: Record<string, ModelOption[]> = {};
const NO_SELECTION: AgentSelection = { providerId: "", modelId: "" };

type Panel = "none" | "history" | "documents";

/**
 * The agent column's content: its header, the conversation or the history or
 * its documents, and the composer. What it shows comes from the host's agent
 * views, read as the signed-in profile's. A host that serves none leaves
 * every one of its doors saying it is not available yet; nothing here is
 * made up, and nothing is sent anywhere.
 */
export function AgentColumn({
  agent,
  reader,
  shown,
  locale,
  body,
  trailing,
  onToggleMaximize,
}: {
  agent: AgentViews | undefined;
  /** Whose the conversations are: the signed-in profile, or null while the
   * account withholds them. */
  reader: string | null;
  /** The column is on screen: only then is anything read. */
  shown: boolean;
  locale: string;
  /** The area the keyboard is given when the column is. */
  body: Ref<HTMLElement>;
  /** The column's own controls, after the conversation's. */
  trailing: ReactNode;
  onToggleMaximize: () => void;
}) {
  const t = useStrings();
  // What the column is showing belongs to the profile it was shown for: a
  // new reader starts on a new conversation with nothing open.
  const [view, setView] = useState({
    reader,
    panel: "none" as Panel,
    archived: false,
    conversationId: null as string | null,
  });
  if (view.reader !== reader)
    setView({ reader, panel: "none", archived: false, conversationId: null });
  const { panel, archived, conversationId } = view;
  const change = (next: Partial<typeof view>) =>
    setView((held) => ({ ...held, ...next }));

  const readable = agent !== undefined && reader !== null && shown;
  // The conversations are read while the history is open, and while one of
  // them is shown, for its title and its documents' count. Opening the
  // history asks again, so it is never the list from the last time.
  const historyOpen = panel === "history";
  const wanted = historyOpen || conversationId !== null;
  const readConversations = useMemo(
    () =>
      readable && agent && (historyOpen || wanted)
        ? () => agent.conversations()
        : null,
    [readable, agent, historyOpen, wanted],
  );
  const conversations = useAgentRead(readConversations);
  const documentsOpen = panel === "documents";
  const readDocuments = useMemo(
    () =>
      readable && agent && documentsOpen && conversationId !== null
        ? () =>
            agent
              .documents(conversationId)
              .then((records) => records.map(conversationDocument))
        : null,
    [readable, agent, documentsOpen, conversationId],
  );
  const documents = useAgentRead(readDocuments);
  // The conversation shown, read whenever it is shown again.
  const conversationShown = panel === "none" && conversationId !== null;
  const readHistory = useMemo(
    () =>
      readable && agent && conversationShown && conversationId !== null
        ? () =>
            agent
              .history(conversationId)
              .then((records) => transcriptItems(records, locale))
        : null,
    [readable, agent, conversationShown, conversationId, locale],
  );
  const history = useAgentRead(readHistory);
  const groups = useConversationGroups(conversations, {
    locale,
    archived,
    currentId: conversationId,
  });

  const current =
    conversations.kind === "ready" && conversationId !== null
      ? conversations.value.find((record) => record.id === conversationId)
      : undefined;
  const open = useCallback(
    (id: string) =>
      setView((held) => ({ ...held, panel: "none", conversationId: id })),
    [],
  );
  const toggle = (next: Panel) =>
    change({ panel: panel === next ? "none" : next });

  return (
    <>
      <AgentHeader
        title={current?.title ?? t("desktop.agent.new_conversation")}
        documentCount={current?.document_count ?? 0}
        historyOpen={historyOpen}
        documentsOpen={documentsOpen}
        // Each door opens only where a host serves the agent; elsewhere it
        // says it is not available yet.
        onNewConversation={
          agent
            ? () => change({ panel: "none", conversationId: null })
            : undefined
        }
        onToggleHistory={agent ? () => toggle("history") : undefined}
        onToggleDocuments={agent ? () => toggle("documents") : undefined}
        onToggleMaximize={onToggleMaximize}
        trailing={trailing}
      />
      <section
        ref={body}
        tabIndex={-1}
        aria-label={t("desktop.pane.agent")}
        className="agent-body flex min-h-0 flex-1 flex-col overflow-y-auto focus-visible:-outline-offset-2"
      >
        {historyOpen ? (
          groups ? (
            <HistoryList
              groups={groups}
              viewingArchived={archived}
              archivedCount={
                conversations.kind === "ready"
                  ? archivedCount(conversations.value)
                  : 0
              }
              onToggleArchived={() => change({ archived: !archived })}
              onOpen={open}
            />
          ) : (
            <ReadState read={conversations} icon="clock" />
          )
        ) : documentsOpen ? (
          conversationId === null ? (
            // A conversation not yet started has no documents to read.
            <DocumentsPanel
              documents={[]}
              locale={locale}
              onClose={() => change({ panel: "none" })}
            />
          ) : documents.kind === "ready" ? (
            <DocumentsPanel
              documents={documents.value}
              locale={locale}
              onClose={() => change({ panel: "none" })}
            />
          ) : (
            <ReadState read={documents} icon="page" />
          )
        ) : conversationId === null ? (
          <AgentWelcome />
        ) : history.kind === "ready" ? (
          // Replying again to a failed turn is the agent's to offer; until
          // a host can, Retry says it is not available.
          <Transcript items={history.value} locale={locale} />
        ) : (
          <ReadState read={history} icon="agent" />
        )}
      </section>
      {/* The history and the documents take the column's whole height, as
          the composer would sit under a list it does not write to. */}
      {!historyOpen && !documentsOpen && (
        <div className="shrink-0 p-3 pt-0">
          <Composer
            locale={locale}
            attachments={NO_ATTACHMENTS}
            providers={NO_PROVIDERS}
            models={NO_MODELS}
            selection={NO_SELECTION}
          />
        </div>
      )}
    </>
  );
}

/** A read that has no answer to show: not offered, on its way, or refused.
 * None of them is shown as empty. */
function ReadState({
  read,
  icon,
}: {
  read: AgentRead<unknown>;
  icon: IconName;
}) {
  const t = useStrings();
  if (read.kind === "loading")
    return (
      <Empty role="status">
        <Spinner />
      </Empty>
    );
  return (
    <Empty role={read.kind === "failed" ? "alert" : "status"}>
      <EmptyMedia>
        <Icon name={read.kind === "failed" ? "alert" : icon} />
      </EmptyMedia>
      <EmptyTitle>
        {read.kind === "failed"
          ? t("desktop.messages.failed", { code: read.code })
          : t("desktop.agent.unavailable")}
      </EmptyTitle>
    </Empty>
  );
}
