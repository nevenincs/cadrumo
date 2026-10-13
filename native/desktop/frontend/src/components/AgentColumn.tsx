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
import { failureCode } from "../errors";
import { useAgentStatus, useLiveConversation } from "../shell/agentLive";
import type {
  AgentConsentRequest,
  AgentProviderRecord,
  AgentSendRequest,
  AgentServiceStatus,
  AgentSession,
} from "../shell/agentSession";
import {
  archivedCount,
  conversationDocument,
  transcriptItems,
  useAgentRead,
  useConversationGroups,
  type AgentRead,
  type AgentViews,
} from "../shell/agentViews";
import { useStrings, type Translate } from "../shell/strings";
import { AgentHeader } from "./agent/AgentHeader";
import { AgentWelcome } from "./agent/AgentWelcome";
import { Composer } from "./agent/Composer";
import { ConsentPrompt, type ConsentItem } from "./agent/ConsentPrompt";
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

/** A send waiting on the person's consent. */
type Asking = {
  request: AgentSendRequest;
  consent: AgentConsentRequest;
};

/** Why the agent service is not serving, in words; null when it is. */
function serviceWords(t: Translate, status: AgentServiceStatus): string | null {
  if (status.state === "ready") return null;
  if (status.state === "starting") return t("desktop.agent.service_starting");
  if (status.state === "stopped") return t("desktop.agent.service_stopped");
  return refusalWords(t, status.code);
}

/** A refusal code of the agent's, in words where it is one we know. */
function refusalWords(t: Translate, code: string): string {
  switch (code) {
    case "agent_service_absent":
      return t("desktop.agent.service_absent");
    case "agent_service_incompatible":
      return t("desktop.agent.service_incompatible");
    case "agent_signed_out":
      return t("desktop.agent.service_signed_out");
    case "agent_runtime_unavailable":
      return t("desktop.agent.service_runtime_unavailable");
    case "agent_provider_credential_missing":
      return t("desktop.agent.service_credential_missing");
    case "agent_service_failed":
      return t("desktop.agent.service_failed");
    default:
      return t("desktop.messages.failed", { code });
  }
}

/** The providers and models as the composer offers them. */
function choices(t: Translate, records: readonly AgentProviderRecord[]) {
  const providers: ProviderOption[] = records.map((record) => ({
    id: record.id,
    name: record.name,
    selectable: record.selectable,
    ...(record.unavailable_reason
      ? { unavailableReason: refusalWords(t, record.unavailable_reason) }
      : {}),
  }));
  const models: Record<string, ModelOption[]> = Object.fromEntries(
    records.map((record) => [
      record.id,
      record.models.map((model) => ({
        id: model.id,
        name: model.display_name,
        efforts: model.efforts,
        ...(model.default_effort
          ? { defaultEffort: model.default_effort }
          : {}),
      })),
    ]),
  );
  return { providers, models };
}

/** `selection` where the providers still offer it, else the first model
 * of the first provider that can be chosen; null when there is none. */
function offered(
  records: readonly AgentProviderRecord[],
  selection: AgentSelection | null,
): AgentSelection | null {
  if (selection) {
    const provider = records.find(
      (record) => record.id === selection.providerId && record.selectable,
    );
    const model = provider?.models.find(
      (option) => option.id === selection.modelId,
    );
    if (
      model &&
      (selection.effort === undefined ||
        model.efforts.includes(selection.effort))
    )
      return selection;
  }
  const provider = records.find(
    (record) => record.selectable && record.models.length > 0,
  );
  const model = provider?.models[0];
  if (!provider || !model) return null;
  return {
    providerId: provider.id,
    modelId: model.id,
    ...(model.default_effort ? { effort: model.default_effort } : {}),
  };
}

/**
 * The agent column's content: its header, the conversation or the history or
 * its documents, and the composer. What it shows comes from the host's agent
 * views, read as the signed-in profile's, and a conversation is kept up to
 * date from the host's agent session as replies are written. A host that
 * serves neither leaves every one of its doors saying it is not available
 * yet; nothing here is made up, and nothing is sent without the person's
 * consent.
 */
export function AgentColumn({
  agent,
  session,
  reader,
  shown,
  locale,
  body,
  trailing,
  onToggleMaximize,
}: {
  agent: AgentViews | undefined;
  /** Sending, consent and the live stream, where the host offers them. */
  session: AgentSession | undefined;
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
  // new reader starts on a new conversation with nothing open, and nothing
  // asked or chosen for the last one carries over.
  const [view, setView] = useState({
    reader,
    panel: "none" as Panel,
    archived: false,
    conversationId: null as string | null,
    chosen: null as AgentSelection | null,
    asking: null as Asking | null,
    sending: false,
    sendFailure: null as string | null,
    // The composer is drawn anew with this draft when a send is given back.
    draft: { key: 0, text: "" },
    // Counts the replies finished, each a reason to read the
    // conversations again.
    revision: 0,
  });
  if (view.reader !== reader)
    setView({
      reader,
      panel: "none",
      archived: false,
      conversationId: null,
      chosen: null,
      asking: null,
      sending: false,
      sendFailure: null,
      draft: { key: view.draft.key + 1, text: "" },
      revision: 0,
    });
  const { panel, archived, conversationId, asking, revision } = view;
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
  // Asked again once a reply has finished, for a title the agent gave.
  const conversations = useAgentRead(readConversations, revision);
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
  // The conversation shown, read whenever it is shown again and followed
  // while it is.
  const conversationShown = panel === "none" && conversationId !== null;
  const onSettled = useCallback(
    () => setView((held) => ({ ...held, revision: held.revision + 1 })),
    [],
  );
  const live = useLiveConversation({
    views: agent,
    session,
    conversationId,
    enabled: readable && conversationShown,
    onSettled,
  });
  const history = useMemo(
    (): AgentRead<ReturnType<typeof transcriptItems>> =>
      live.read.kind === "ready"
        ? { kind: "ready", value: transcriptItems(live.read.value, locale) }
        : live.read,
    [live.read, locale],
  );
  const groups = useConversationGroups(conversations, {
    locale,
    archived,
    currentId: conversationId,
  });

  // The service, and what it can run, while the column could send.
  const status = useAgentStatus(session, readable);
  const ready = status?.state === "ready";
  const readProviders = useMemo(
    () => (ready && session ? () => session.providers() : null),
    [ready, session],
  );
  const providers = useAgentRead(readProviders);
  const offer = useMemo(
    () => (providers.kind === "ready" ? choices(t, providers.value) : null),
    [providers, t],
  );
  const selection =
    providers.kind === "ready" ? offered(providers.value, view.chosen) : null;

  const current =
    conversations.kind === "ready" && conversationId !== null
      ? conversations.value.find((record) => record.id === conversationId)
      : undefined;
  const open = useCallback(
    (id: string) =>
      setView((held) => ({
        ...held,
        panel: "none",
        conversationId: id,
        asking: null,
        sendFailure: null,
      })),
    [],
  );
  const toggle = (next: Panel) =>
    change({ panel: panel === next ? "none" : next });

  // A send that did not go is given back to the composer to try again.
  const giveBack = (text: string, failure: string | null) =>
    setView((held) => ({
      ...held,
      asking: null,
      sending: false,
      sendFailure: failure,
      draft: { key: held.draft.key + 1, text },
    }));
  const deliver = async (request: AgentSendRequest) => {
    if (!session) return;
    try {
      live.sent(await session.send(request));
      change({ asking: null, sending: false });
    } catch (error) {
      giveBack(request.text, failureCode(error));
    }
  };
  const submit = async (text: string, chosen: AgentSelection) => {
    if (!session) return;
    let request: AgentSendRequest;
    try {
      // A new conversation begins with its first message, never on its own.
      let id = conversationId;
      if (id === null) {
        id = (await session.startConversation()).id;
        open(id);
      }
      // Watched before anything is sent, so the reply is followed from its
      // first word.
      await live.watch(id);
      request = {
        conversation_id: id,
        text,
        selection: {
          provider_id: chosen.providerId,
          model_id: chosen.modelId,
          ...(chosen.effort ? { effort: chosen.effort } : {}),
        },
      };
      const consent = await session.consentNeeded(request);
      if (consent) {
        change({ asking: { request, consent }, sending: false });
        return;
      }
    } catch (error) {
      giveBack(text, failureCode(error));
      return;
    }
    // A send that fails is given back by `deliver` itself.
    await deliver(request);
  };
  const send =
    session && ready && selection && !view.sending && !asking
      ? (text: string) => {
          change({ sending: true, sendFailure: null });
          void submit(text, selection);
        }
      : undefined;
  const allow = asking
    ? async () => {
        if (!session) return;
        change({ sending: true });
        try {
          await session.grantConsent(asking.consent);
        } catch (error) {
          giveBack(asking.request.text, failureCode(error));
          return;
        }
        await deliver(asking.request);
      }
    : undefined;
  const stop =
    session && live.open
      ? () => {
          const replyId = live.open;
          if (replyId)
            session
              .cancel(replyId)
              .catch((error: unknown) =>
                change({ sendFailure: failureCode(error) }),
              );
        }
      : undefined;

  const consentFor = (consent: AgentConsentRequest) => {
    const record =
      providers.kind === "ready"
        ? providers.value.find((option) => option.id === consent.provider_id)
        : undefined;
    const model = record?.models.find(
      (option) => option.id === consent.model_id,
    );
    const items = consent.items.map((item, index): ConsentItem => ({
      id: `${item.kind}-${item.kind === "document" ? item.id : index}`,
      label:
        item.kind === "messages"
          ? t("desktop.agent.consent_messages")
          : item.kind === "tool_results"
            ? t("desktop.agent.consent_tool_results")
            : item.name,
    }));
    return {
      providerName: record?.name ?? consent.provider_id,
      modelName: model?.display_name ?? consent.model_id,
      items,
    };
  };

  const notice = status ? serviceWords(t, status) : null;
  const asked = asking ? consentFor(asking.consent) : null;

  return (
    <>
      <AgentHeader
        // A conversation is untitled until the agent names it.
        title={current?.title || t("desktop.agent.new_conversation")}
        documentCount={current?.document_count ?? 0}
        historyOpen={historyOpen}
        documentsOpen={documentsOpen}
        // Each door opens only where a host serves the agent; elsewhere it
        // says it is not available yet.
        onNewConversation={
          agent
            ? () =>
                change({
                  panel: "none",
                  conversationId: null,
                  asking: null,
                  sendFailure: null,
                })
            : undefined
        }
        onToggleHistory={agent ? () => toggle("history") : undefined}
        onToggleDocuments={agent ? () => toggle("documents") : undefined}
        onToggleMaximize={onToggleMaximize}
        trailing={trailing}
      />
      {status?.lane === "development" && (
        // Said for as long as the lane is in use, whatever the agent's state.
        <p
          role="note"
          className="agent-lane flex shrink-0 items-start gap-2 border-b bg-accent px-3 py-2 text-xs text-foreground"
        >
          <Icon name="alert" size="xs" className="mt-0.5 shrink-0" />
          <span>{t("desktop.agent.lane_notice")}</span>
        </p>
      )}
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
        <div className="grid shrink-0 gap-2 p-3 pt-0">
          {asking && asked && (
            <ConsentPrompt
              providerName={asked.providerName}
              modelName={asked.modelName}
              contentItems={asked.items}
              onAllow={view.sending ? undefined : () => void allow?.()}
              onDecline={() => giveBack(asking.request.text, null)}
            />
          )}
          {view.sendFailure !== null ? (
            <p role="alert" className="flex items-start gap-2 text-sm">
              <Icon name="alert" className="mt-0.5 text-destructive" />
              <span>{refusalWords(t, view.sendFailure)}</span>
            </p>
          ) : (
            notice && (
              <p
                role="status"
                className="flex items-start gap-2 text-sm text-muted-foreground"
              >
                <Icon name="info" className="mt-0.5" />
                <span>{notice}</span>
              </p>
            )
          )}
          <Composer
            key={view.draft.key}
            defaultDraft={view.draft.text}
            locale={locale}
            attachments={NO_ATTACHMENTS}
            providers={offer?.providers ?? NO_PROVIDERS}
            models={offer?.models ?? NO_MODELS}
            selection={selection ?? NO_SELECTION}
            running={live.working || view.sending}
            onSend={send}
            onStop={stop}
            onSelectionChange={
              offer ? (chosen) => change({ chosen }) : undefined
            }
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
