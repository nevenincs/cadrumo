import {
  useCallback,
  useMemo,
  useState,
  type ReactNode,
  type Ref,
} from "react";
import { Button } from "@/components/ui/button";
import { Empty, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Icon, type IconName } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { failureCode } from "../errors";
import { useAgentAccess, type AgentAccess } from "../shell/agentAccess";
import {
  catalogChoices,
  offeredSelection,
  selectionRecord,
} from "../shell/agentCatalog";
import {
  newestReply,
  useAgentStatus,
  useLiveConversation,
} from "../shell/agentLive";
import type {
  AgentApproval,
  AgentQuestionnaire,
  AgentQuestionnaireAnswer,
  AgentSendRequest,
  AgentServiceStatus,
  AgentSession,
} from "../shell/agentSession";
import {
  archivedCount,
  replyFacts,
  transcriptItems,
  useAgentRead,
  useConversationGroups,
  type AgentRead,
  type AgentViews,
} from "../shell/agentViews";
import { queuedWords, runStateWords } from "../shell/agentWords";
import {
  useProviderSettings,
  type ProviderSettings,
} from "../shell/providerSettings";
import { useStrings, type Translate } from "../shell/strings";
import { AgentHeader } from "./agent/AgentHeader";
import { AgentWelcome } from "./agent/AgentWelcome";
import { ApprovalPrompt } from "./agent/ApprovalPrompt";
import { Composer } from "./agent/Composer";
import { HistoryList } from "./agent/HistoryList";
import { QuestionsPrompt } from "./agent/QuestionsPrompt";
import { AgentAccess as AgentAccessSection } from "./settings/AgentAccess";
import { ProviderSettings as ProviderSettingsSection } from "./settings/ProviderSettings";
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
const NO_SELECTION: AgentSelection = {
  providerId: "",
  wayId: "",
  modelId: "",
};

type Panel = "none" | "history" | "settings";

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
    case "agent_root_unmarked":
      return t("desktop.agent.service_root_unmarked");
    case "agent_service_failed":
      return t("desktop.agent.service_failed");
    case "agent_reply_in_progress":
      return t("desktop.agent.reply_in_progress");
    default:
      return t("desktop.messages.failed", { code });
  }
}

/**
 * The agent column's content: its header, the conversation or the history or
 * the settings, and the composer. What it shows comes from the host's agent
 * views, read as the signed-in profile's, and a conversation is kept up to
 * date from the host's agent session as replies are written. A host that
 * serves neither leaves every one of its doors saying it is not available
 * yet, and so does what the agent does not serve, such as a conversation's
 * documents. Nothing here is made up: the providers, models and what each can
 * do are the agent's own catalog, a conversation's records are what the agent
 * kept of its runs, and only what the person sends is sent.
 */
export function AgentColumn({
  agent,
  session,
  providerSettings,
  agentAccess,
  writeClipboard,
  reader,
  shown,
  locale,
  body,
  trailing,
  onToggleMaximize,
}: {
  agent: AgentViews | undefined;
  /** Sending and the live stream, where the host offers them. */
  session: AgentSession | undefined;
  /** The profile's model providers and their keys, where the host offers
   * them. */
  providerSettings: ProviderSettings | undefined;
  /** The keys the profile issued to agents outside Cadrumo, where the host
   * offers them. */
  agentAccess?: AgentAccess;
  /** Puts text on the clipboard, where the host offers it. */
  writeClipboard?: (text: string) => Promise<void>;
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
    sending: false,
    sendFailure: null as string | null,
    // Why the history's last archive was refused.
    archiveFailure: null as string | null,
    // The composer is drawn anew with this draft when a send is given back.
    draft: { key: 0, text: "" },
    // Counts the messages sent and the replies finished, each a reason to
    // read the conversations again.
    revision: 0,
  });
  if (view.reader !== reader)
    setView({
      reader,
      panel: "none",
      archived: false,
      conversationId: null,
      chosen: null,
      sending: false,
      sendFailure: null,
      archiveFailure: null,
      draft: { key: view.draft.key + 1, text: "" },
      revision: 0,
    });
  const { panel, archived, conversationId, revision } = view;
  const change = (next: Partial<typeof view>) =>
    setView((held) => ({ ...held, ...next }));

  const readable = agent !== undefined && reader !== null && shown;
  // The conversations are read while the history is open, and while one of
  // them is shown, for its title. Opening the history asks again, so it is
  // never the list from the last time.
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
  const history = useMemo((): AgentRead<ReturnType<typeof transcriptItems>> => {
    if (live.read.kind !== "ready") return live.read;
    return {
      kind: "ready",
      value: transcriptItems(live.read.value, locale, t),
    };
  }, [live.read, locale, t]);
  // What the agent served of the conversation's replies beside their words: the
  // state of the newest, what they ran with, and the tokens they used.
  const newest =
    live.read.kind === "ready" ? newestReply(live.read.value) : undefined;
  const facts = useMemo(
    () =>
      live.read.kind === "ready"
        ? replyFacts(live.read.value, locale, t)
        : { ranWith: null, usage: null },
    [live.read, locale, t],
  );
  const groups = useConversationGroups(conversations, {
    locale,
    archived,
    currentId: conversationId,
    untitled: t("desktop.agent.unavailable"),
  });

  // The service, and what it can run, while the column could send.
  const status = useAgentStatus(session, readable);
  const ready = status?.state === "ready";
  // What it can run is the agent's own catalog, every lane of it.
  const readCatalog = useMemo(
    () => (ready && session ? () => session.providerCatalog() : null),
    [ready, session],
  );
  const catalog = useAgentRead(readCatalog);
  const offer = useMemo(
    () => (catalog.kind === "ready" ? catalogChoices(t, catalog.value) : null),
    [catalog, t],
  );
  const selection = offer ? offeredSelection(offer, view.chosen) : null;

  const current =
    conversations.kind === "ready" && conversationId !== null
      ? conversations.value.find((record) => record.id === conversationId)
      : undefined;
  // Archiving is the agent's, one run at a time and for good: the history
  // offers it where the host does, and never an undo.
  const archiveHost = session?.archive ? session : undefined;
  const open = useCallback(
    (id: string) =>
      setView((held) => ({
        ...held,
        panel: "none",
        conversationId: id,
        sendFailure: null,
        archiveFailure: null,
      })),
    [],
  );
  const toggle = (next: Panel) =>
    change({ panel: panel === next ? "none" : next });
  // The agent's settings belong to the signed-in profile, and are read
  // only while they are open.
  const settingsOpen = panel === "settings";
  const settings = useProviderSettings(
    providerSettings,
    reader,
    settingsOpen && shown,
  );
  const access = useAgentAccess(agentAccess, reader, settingsOpen && shown);
  const openSettings =
    (providerSettings || agentAccess) && reader !== null
      ? () => change({ panel: "settings" })
      : undefined;

  // A send that did not go is given back to the composer to try again.
  const giveBack = (text: string, failure: string | null) =>
    setView((held) => ({
      ...held,
      sending: false,
      sendFailure: failure,
      draft: { key: held.draft.key + 1, text },
    }));
  const deliver = async (request: AgentSendRequest) => {
    if (!session) return;
    try {
      const { reply_id } = await session.send(request);
      // The agent returns no id for the message, so it is shown as sent until
      // the history has it.
      live.sent({ reply_id, text: request.text, at: "start" });
      // A message sent may name the conversation, so it is read again.
      setView((held) => ({
        ...held,
        sending: false,
        revision: held.revision + 1,
      }));
    } catch (error) {
      giveBack(request.text, failureCode(error));
    }
  };
  // Pressing Send is the person's decision: the message goes, and nothing
  // asks them again.
  const submit = async (text: string, chosen: AgentSelection) => {
    if (!session || catalog.kind !== "ready") return;
    const runs = selectionRecord(catalog.value, chosen);
    if (!runs) {
      giveBack(text, "agent_selection_unavailable");
      return;
    }
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
      request = { conversation_id: id, text, selection: runs };
    } catch (error) {
      giveBack(text, failureCode(error));
      return;
    }
    // A send that fails is given back by `deliver` itself.
    await deliver(request);
  };
  // What the reply waits on. While it asks questions, a message written
  // below answers them in the person's own words, and goes on with the
  // same reply.
  const questionnaire = live.questionnaires[0];
  const answer = async (
    asked: AgentQuestionnaire,
    reply: AgentQuestionnaireAnswer,
  ) => {
    if (!session) return;
    change({ sending: true, sendFailure: null });
    try {
      await session.answerQuestions(asked, reply);
      // An answer in words continues the run in place: shown as sent, as a
      // message is.
      if (reply.kind === "message")
        live.sent({ reply_id: asked.reply_id, text: reply.text, at: "end" });
      live.resolved(asked.request_id);
      change({ sending: false });
    } catch (error) {
      if (reply.kind === "message") giveBack(reply.text, failureCode(error));
      else change({ sending: false, sendFailure: failureCode(error) });
    }
  };
  const decide = async (approval: AgentApproval, optionId: string) => {
    if (!session) return;
    change({ sending: true, sendFailure: null });
    try {
      await session.decideApproval(approval, optionId);
      live.resolved(approval.request_id);
      change({ sending: false });
    } catch (error) {
      change({ sending: false, sendFailure: failureCode(error) });
    }
  };
  const answering = session && ready && !view.sending;
  // The agent takes no message while a run needs repair or is being
  // reconciled.
  const heldByRun =
    newest?.status === "repair_needed" ||
    newest?.status === "reconciling" ||
    newest?.status === "deleting";
  // A selection the catalog names in full: a model not yet chosen or written
  // cannot be run.
  const runnable =
    catalog.kind === "ready" &&
    selection !== null &&
    selectionRecord(catalog.value, selection) !== null;
  const send =
    answering && questionnaire
      ? (text: string) => void answer(questionnaire, { kind: "message", text })
      : answering && selection && runnable && !heldByRun
        ? (text: string) => {
            change({ sending: true, sendFailure: null });
            void submit(text, selection);
          }
        : undefined;
  const stop =
    session && live.open
      ? () => {
          const replyId = live.open;
          if (replyId)
            session.cancel(replyId).then(
              () => live.stopping(replyId),
              (error: unknown) => change({ sendFailure: failureCode(error) }),
            );
        }
      : undefined;

  // No provider the agent can run: a key is missing, or every lane is held
  // back. That is not a failure, and the way to a key is offered.
  const incompatible = offer?.incompatible === true;
  const noProvider =
    !incompatible &&
    ((status?.state === "refused" &&
      status.code === "agent_provider_credential_missing") ||
      (offer !== null &&
        !offer.providers.some((provider) => provider.selectable)));
  const notice = incompatible
    ? t("desktop.agent.service_incompatible")
    : noProvider
      ? t("desktop.agent.no_provider")
      : status
        ? serviceWords(t, status)
        : null;

  return (
    <>
      <AgentHeader
        // A conversation not yet started has no title; one the agent was
        // given none for says so.
        title={
          current
            ? current.title || t("desktop.agent.unavailable")
            : t("desktop.agent.new_conversation")
        }
        historyOpen={historyOpen}
        // Each door opens only where a host serves the agent; elsewhere it
        // says it is not available yet. The documents door is never open:
        // Cadrumo's custody serves the agent none yet.
        onNewConversation={
          agent
            ? () =>
                change({
                  panel: "none",
                  conversationId: null,
                  sendFailure: null,
                })
            : undefined
        }
        onToggleHistory={agent ? () => toggle("history") : undefined}
        settingsOpen={settingsOpen}
        onToggleSettings={openSettings ? () => toggle("settings") : undefined}
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
        {settingsOpen ? (
          // Each section the host offers is read, and shown or said, on its
          // own: the providers' keys and the keys of agents outside Cadrumo.
          <div className="grid gap-6 p-3">
            {providerSettings &&
              (settings.read.kind === "ready" ? (
                <ProviderSettingsSection
                  providers={settings.read.value.providers}
                  development={settings.read.value.development}
                  busyId={settings.busyId}
                  outcomes={settings.outcomes}
                  onSave={settings.save}
                  onTurnOff={settings.turnOff}
                  onReset={settings.reset}
                  onRefresh={settings.refresh}
                />
              ) : (
                <ReadState read={settings.read} icon="settings" />
              ))}
            {agentAccess &&
              (access.read.kind === "ready" ? (
                <AgentAccessSection
                  credentials={access.read.value.credentials}
                  locale={locale}
                  busyId={access.busyId}
                  outcomes={access.outcomes}
                  issuing={access.issuing}
                  issueRefusal={access.issueRefusal}
                  issued={access.issued}
                  onIssue={access.issue}
                  onCloseIssue={access.closeIssue}
                  onRevoke={access.revoke}
                  onRefresh={access.refresh}
                  onCopy={writeClipboard}
                />
              ) : (
                <ReadState read={access.read} icon="settings" />
              ))}
          </div>
        ) : historyOpen ? (
          groups ? (
            <div className="flex min-h-0 flex-1 flex-col">
              {view.archiveFailure !== null && (
                <p
                  role="alert"
                  className="flex shrink-0 items-start gap-2 px-3 pt-3 text-sm"
                >
                  <Icon name="alert" className="mt-0.5 text-destructive" />
                  <span>{refusalWords(t, view.archiveFailure)}</span>
                </p>
              )}
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
                onArchive={
                  archiveHost
                    ? (id) => {
                        change({ archiveFailure: null });
                        archiveHost.archive?.(id).then(
                          () =>
                            setView((held) => ({
                              ...held,
                              revision: held.revision + 1,
                            })),
                          (error: unknown) =>
                            change({ archiveFailure: failureCode(error) }),
                        );
                      }
                    : undefined
                }
              />
            </div>
          ) : (
            <ReadState read={conversations} icon="clock" />
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
      {/* The history and the settings take the column's whole height, as the
          composer would sit under a list it does not write to. */}
      {!historyOpen && !settingsOpen && (
        <div className="grid shrink-0 gap-2 p-3 pt-0">
          {live.approvals.map((approval) => (
            <ApprovalPrompt
              key={approval.request_id}
              source={approval.source}
              toolCall={approval.tool_call}
              toolKind={approval.tool_kind}
              description={approval.description}
              options={approval.options}
              onDecide={
                answering
                  ? (optionId) => void decide(approval, optionId)
                  : undefined
              }
            />
          ))}
          {questionnaire && (
            <QuestionsPrompt
              key={questionnaire.request_id}
              questions={questionnaire.questions}
              onAnswer={
                answering
                  ? (answers) =>
                      void answer(questionnaire, { kind: "answers", answers })
                  : undefined
              }
              onDecline={
                answering
                  ? () => void answer(questionnaire, { kind: "decline" })
                  : undefined
              }
            />
          )}
          {conversationId !== null && (
            <ReplyFacts
              state={newest ? runStateWords(t, newest.status) : null}
              queued={
                newest?.queued_messages
                  ? queuedWords(t, newest.queued_messages)
                  : null
              }
              ranWith={facts.ranWith}
              usage={facts.usage}
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
                <span className="grid justify-items-start gap-1.5">
                  {notice}
                  {noProvider && openSettings && (
                    <Button variant="outline" size="xs" onClick={openSettings}>
                      {t("desktop.agent.set_up_providers")}
                    </Button>
                  )}
                </span>
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
            // Questions are answered by a message too, so Send stays.
            running={!questionnaire && (live.working || view.sending)}
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

/** What the agent served of the conversation's newest reply beside its words:
 * a run state the transcript draws no indicator for, the messages queued behind
 * it, what the replies ran with and the tokens they used. Each is said only
 * where the agent served it. */
function ReplyFacts({
  state,
  queued,
  ranWith,
  usage,
}: {
  state: string | null;
  queued: string | null;
  ranWith: string | null;
  usage: string | null;
}) {
  return (
    <>
      {[state, queued].map(
        (words) =>
          words && (
            <p
              key={words}
              role="status"
              className="agent-reply-state flex items-start gap-2 text-sm text-muted-foreground"
            >
              <Icon name="info" className="mt-0.5" />
              <span>{words}</span>
            </p>
          ),
      )}
      {[ranWith, usage].map(
        (words) =>
          words && (
            <p
              key={words}
              className="agent-reply-facts text-xs text-muted-foreground"
            >
              {words}
            </p>
          ),
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
