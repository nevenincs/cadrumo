import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type Ref,
} from "react";
import { Button } from "@/components/ui/button";
import { isCadrumoLink } from "../shell/navigation/links";
import { Icon } from "@/components/ui/icon";
import { failureCode } from "../errors";
import { useAgentAccess, type AgentAccess } from "../shell/agentAccess";
import { DocumentLister } from "../shell/agentDocuments";
import { useDocumentInventory } from "../shell/agentDocumentInventory";
import { useStagedDocuments } from "../shell/agentStaging";
import { useAgentDrops } from "../shell/agentDrops";
import { DropOverlay } from "./agent/DropOverlay";
import { StagedAttachmentsDialog } from "./agent/StagedAttachmentsDialog";
import {
  newestReply,
  useAgentStatus,
  useLiveConversation,
} from "../shell/agentLive";
import type { AgentSession, AgentToolRefusal } from "../shell/agentSession";
import {
  archivedCount,
  newestRanWith,
  replyFacts,
  useAgentRead,
  useConversationGroups,
  type AgentViews,
} from "../shell/agentViews";
import { queuedWords, runStateWords } from "../shell/agentWords";
import { labelled } from "../shell/compose";
import {
  useProviderSettings,
  type ProviderSettings,
} from "../shell/providerSettings";
import { useStrings } from "../shell/strings";
import type { OpenMenu } from "./ContextMenu";
import { AgentHeader } from "./agent/AgentHeader";
import type { AgentColumnView, Panel } from "./agent/agentColumnView";
import { refusalWords, serviceWords } from "./agent/agentRefusalWords";
import { agentSending } from "./agent/agentSending";
import { AgentSettingsPanel } from "./agent/AgentSettingsPanel";
import { AgentWelcome } from "./agent/AgentWelcome";
import { Composer } from "./agent/Composer";
import { documentSource } from "./agent/DocumentMentions";
import { HistoryList } from "./agent/HistoryList";
import { ReadState } from "./agent/ReadState";
import { ReplyFacts } from "./agent/ReplyFacts";
import { RunPrompts } from "./agent/RunPrompts";
import { useShownTranscript } from "./agent/useShownTranscript";
import { ColumnNotice, type EngineNotice } from "./agent/ColumnNotice";
import { ConversationDocuments } from "./agent/ConversationDocuments";
import { SkillDialog } from "./agent/SkillDialog";
import { useSkillInventory } from "./agent/SlashSuggestions";
import { useAgentCatalog } from "./agent/useAgentCatalog";
import { useLocalModelHosts } from "./agent/useLocalModelHosts";
import type { SkillCommand } from "../shell/agentSkills";
import { Transcript } from "./agent/Transcript";
import type {
  AgentSelection,
  ModelOption,
  ProviderOption,
} from "./agent/types";

// What the composer is given while nothing serves it: nothing. Sending,
// adding files and choosing a model each say they are not available yet.
const NO_PROVIDERS: ProviderOption[] = [];
const NO_MODELS: Record<string, ModelOption[]> = {};
const NO_SELECTION: AgentSelection = {
  providerId: "",
  wayId: "",
  modelId: "",
};

export type AgentColumnControl = {
  /** Shows the conversation with the model picker open. */
  openModelPicker(): void;
};

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
  onMenu,
  onToolRefused,
  onOpenLink,
  onOpenView,
  control,
  setupSettled = null,
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
  /** Opens a context menu, drawn by the shell. */
  onMenu?: OpenMenu;
  /** Told when the conversation shown has a tool call the product refused,
   * keyed by its reply and call. */
  onToolRefused?: (key: string, refusal: AgentToolRefusal) => void;
  /** Opens an address a reply links to, in the system browser. */
  onOpenLink?: (url: string) => void;
  /** Opens a `cadrumo:` link a reply carries, or says why it cannot.
   * `opened` is told the register view that opened, once it is shown. */
  onOpenView?: (url: string, opened?: (view: string) => void) => void;
  /** The last setup that settled, by operation: what this computer holds may
   * have changed, so the catalog is read again. */
  setupSettled?: string | null;
  control?: Ref<AgentColumnControl>;
}) {
  const t = useStrings();
  const [setupCheck, setSetupCheck] = useState<{
    reader: string;
    conversation: string | null;
  } | null>(null);
  const currentReader = useRef(reader);
  currentReader.current = reader;
  // What the column is showing belongs to the profile it was shown for: a
  // new reader starts on a new conversation with nothing open, and nothing
  // asked or chosen for the last one carries over.
  const [view, setView] = useState<AgentColumnView>({
    reader,
    panel: "none",
    archived: false,
    conversationId: null,
    chosen: null,
    sending: false,
    interactionId: null,
    pending: null,
    sendFailure: null,
    sendFit: null,
    archiveFailure: null,
    historyBusy: false,
    draft: { key: 0, text: "" },
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
      interactionId: null,
      pending: null,
      sendFailure: null,
      sendFit: null,
      archiveFailure: null,
      historyBusy: false,
      draft: { key: view.draft.key + 1, text: "" },
      revision: 0,
    });
  const { panel, archived, conversationId, revision } = view;
  const promptOwner = useMemo(
    () => ({ reader, conversationId, session }),
    [reader, conversationId, session],
  );
  const currentPromptOwner = useRef(promptOwner);
  currentPromptOwner.current = promptOwner;
  const pendingPrompt = useRef<{
    owner: typeof promptOwner;
    id: string;
  } | null>(null);
  useEffect(
    () => () => {
      const retired = pendingPrompt.current;
      if (retired?.owner !== promptOwner) return;
      pendingPrompt.current = null;
      setView((held) =>
        held.interactionId === retired.id
          ? { ...held, interactionId: null, sending: false }
          : held,
      );
    },
    [promptOwner],
  );
  const currentSend = useRef<string | null>(null);
  currentSend.current = view.pending?.id ?? null;
  const change = (next: Partial<typeof view>) =>
    setView((held) => ({ ...held, ...next }));

  const readable = agent !== undefined && reader !== null && shown;
  const status = useAgentStatus(session, reader, readable);
  const ready = status?.state === "ready";
  const unsupported =
    status?.state === "refused" && status.code === "agent_platform_unsupported";
  // A signed-in profile can precede its agent service. Reopening this gate
  // also refreshes reads after the service has recovered.
  const serviceReadable = readable && (!session || ready);
  // The conversations are read while the history is open, and while one of
  // them is shown, for its title. Opening the history asks again, so it is
  // never the list from the last time.
  const historyOpen = panel === "history";
  const documentsOpen = panel === "documents";
  const wanted = historyOpen || conversationId !== null;
  const readConversations = useMemo(
    () =>
      reader !== null && serviceReadable && agent && (historyOpen || wanted)
        ? () => agent.conversations()
        : null,
    [reader, serviceReadable, agent, historyOpen, wanted],
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
    enabled: serviceReadable && conversationShown,
    onSettled,
    onToolRefused,
  });
  const pending =
    view.reader === reader && view.pending?.conversationId === conversationId
      ? view.pending
      : null;
  const history = useShownTranscript(live.read, pending, locale, t);
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
  // cadrumo-agent's skills, which `/` lists, and the skill command shown.
  const skills = useSkillInventory(session);
  const reviewSkill = useMemo(() => session?.skill?.bind(session), [session]);
  const verifySkill = useMemo(
    () => session?.verifySkill?.bind(session),
    [session],
  );
  const [skillShown, setSkillShown] = useState<SkillCommand | null>(null);
  const [settingsQuery, setSettingsQuery] = useState("");
  const [providerMatches, setProviderMatches] = useState(true);
  const [accessMatches, setAccessMatches] = useState(true);
  const [pickerRequests, setPickerRequests] = useState(0);
  const openModelPicker = useCallback(() => {
    setView((held) => ({ ...held, panel: "none" }));
    setPickerRequests((count) => count + 1);
  }, []);
  useImperativeHandle(
    control,
    () => ({
      openModelPicker,
    }),
    [openModelPicker],
  );
  const { localModelHost, readingHost, listChanges } = useLocalModelHosts(
    session,
    ready,
  );
  // The agent's settings belong to the signed-in profile, and are read only
  // while they are open: the first time behind one loader, and after that
  // again behind what was read last, each time they open.
  const settingsOpen = panel === "settings";
  const [opens, setOpens] = useState({ open: false, count: 0 });
  if (opens.open !== settingsOpen)
    setOpens({
      open: settingsOpen,
      count: settingsOpen ? opens.count + 1 : opens.count,
    });
  const opened =
    opens.open !== settingsOpen && settingsOpen ? opens.count + 1 : opens.count;
  const settings = useProviderSettings(
    providerSettings,
    reader,
    settingsOpen && shown,
    opened,
  );
  const ranWith =
    conversationId !== null && live.read.kind === "ready"
      ? newestRanWith(live.read.value)
      : undefined;
  const agentCatalog = useAgentCatalog({
    t,
    reader,
    session,
    status,
    readingHost,
    setupSettled,
    settingsChanges: settings.changes,
    opened,
    listChanges,
    chosen: view.chosen,
    ranWith,
  });
  const {
    catalog,
    catalogBusy,
    localLanes,
    engines,
    offer,
    selection,
    remember,
  } = agentCatalog;

  const current =
    conversations.kind === "ready" && conversationId !== null
      ? conversations.value.find((record) => record.id === conversationId)
      : undefined;
  // Archiving is the agent's, for the whole chain and for good: the history
  // offers it where the host does, and never an undo.
  const archiveHost = session?.archive ? session : undefined;
  const historyAction = useRef(false);
  const mutateHistory = async (id: string, action: "archive" | "delete") => {
    const perform = session?.[action];
    if (!perform || historyAction.current) return;
    historyAction.current = true;
    change({ archiveFailure: null, historyBusy: true });
    let failure: string | null = null;
    try {
      await perform(id);
    } catch (error: unknown) {
      failure = failureCode(error);
    } finally {
      historyAction.current = false;
    }
    if (currentReader.current !== reader) return;
    setView((held) => {
      const removed =
        action === "delete" &&
        (failure === null ||
          failure === "agent_conversation_delete_incomplete") &&
        held.conversationId === id;
      return {
        ...held,
        historyBusy: false,
        archiveFailure: failure,
        revision: held.revision + 1,
        ...(removed
          ? {
              conversationId: null,
              pending: null,
              sending: false,
              chosen: null,
              draft: { key: held.draft.key + 1, text: "" },
            }
          : {}),
      };
    });
  };
  // Renaming is offered where the host renames. A refusal is said where the
  // rename was asked: in the history, or over the composer for the header.
  const renameHost = session?.rename ? session : undefined;
  const rename = (id: string, title: string, where: "history" | "header") => {
    const said = (code: string | null) =>
      change(
        where === "history" ? { archiveFailure: code } : { sendFailure: code },
      );
    said(null);
    renameHost?.rename?.(id, title).then(
      () => setView((held) => ({ ...held, revision: held.revision + 1 })),
      (error: unknown) => said(failureCode(error)),
    );
  };
  const open = useCallback((id: string) => {
    pendingPrompt.current = null;
    setView((held) => ({
      ...held,
      panel: "none",
      conversationId: id,
      pending: null,
      sending: false,
      interactionId: null,
      // A conversation opened runs with its own choice, not the last one's.
      chosen: held.conversationId === id ? held.chosen : null,
      sendFailure: null,
      archiveFailure: null,
    }));
  }, []);
  // The conversation a first message starts keeps the choice it was sent
  // with.
  const started = useCallback(
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
  const localProvider =
    settings.read.kind === "ready"
      ? settings.read.value.providers.find((lane) => lane.authKind === "none")
      : undefined;
  const access = useAgentAccess(
    agentAccess,
    reader,
    settingsOpen && shown,
    opened,
  );
  const refreshProviderAfterSignIn = async (
    providerId: string,
    identity: string | null,
  ) => {
    if (
      identity === null ||
      identity !== reader ||
      currentReader.current !== reader ||
      !providerSettings
    )
      return undefined;
    let revision: string | undefined;
    try {
      const answer = await providerSettings.status();
      if (currentReader.current !== reader || identity !== reader)
        return undefined;
      revision = answer.providers.find(
        (record) => record.id === providerId,
      )?.revision;
      // The settings show this read rather than asking for another.
      settings.accept(answer);
    } catch {
      // A failed direct read must never make retry available with the old
      // revision; the settings are read again instead.
      if (currentReader.current === reader && identity === reader)
        settings.refresh();
    }
    if (currentReader.current !== reader || identity !== reader)
      return undefined;
    return typeof revision === "string" && /^[0-9a-f]{64}$/.test(revision)
      ? revision
      : undefined;
  };
  const settingsLoading =
    (providerSettings !== undefined && settings.read.kind === "loading") ||
    (agentAccess !== undefined && access.read.kind === "loading");
  const openSettings =
    (providerSettings || agentAccess) && reader !== null
      ? () => {
          change({ panel: "settings" });
        }
      : undefined;

  // The stored documents the next message names: chosen with `@`, or
  // attached and stored first. A send that does not go keeps them.
  const [documentsVersion, setDocumentsVersion] = useState(0);
  const [attachmentsShown, setAttachmentsShown] = useState<{
    reader: string | null;
    conversation: string | null;
  } | null>(null);
  const staging = useStagedDocuments({
    reader,
    conversationId,
    session,
    filterLabel: t("desktop.agent.attach_filter"),
    t,
    onStored: () => setDocumentsVersion((held) => held + 1),
  });
  const documents = useDocumentInventory({
    agent,
    session,
    reader,
    conversationId,
    enabled: serviceReadable,
    version: documentsVersion,
  });
  const readAttachmentPolicy = useMemo(
    () =>
      serviceReadable && session?.attachmentPolicy
        ? session.attachmentPolicy.bind(session)
        : null,
    [serviceReadable, session],
  );
  const attachmentPolicy = useAgentRead(readAttachmentPolicy);
  const removeDocument = async (name: string | null) => {
    if (await documents.remove?.(name))
      staging.remove(name === null ? null : `stored:${name}`);
  };
  const groups = useConversationGroups(conversations, {
    locale,
    archived,
    currentId: conversationId,
    untitled: t("desktop.agent.unavailable"),
    documentCounts: documents.counts,
  });
  useEffect(() => {
    if (!pending?.conversationId || live.read.kind !== "ready") return;
    const delivered = live.read.value.some(
      (record) =>
        record.kind === "person" &&
        record.text === pending.text &&
        (pending.replyId
          ? record.reply_id === pending.replyId
          : !pending.previousReplies.includes(record.reply_id)),
    );
    if (!delivered) return;
    // Durable history can confirm delivery before its command returns, or
    // after the service recovered from a lost acknowledgement. Never resend
    // it or leave the composer waiting for an answer that may never arrive.
    staging.sent(pending.conversationId);
    setView((held) =>
      held.reader === reader && held.pending?.id === pending.id
        ? { ...held, sending: false, pending: null, sendFailure: null }
        : held,
    );
  }, [pending, live.read, staging, reader]);
  const lister = useMemo(
    () => (agent?.documents ? new DocumentLister(agent.documents) : null),
    [agent],
  );
  const nameDocument = staging.name;
  const mentionSources = useMemo(
    () => [
      documentSource({
        lister: reader !== null ? lister : null,
        conversationId,
        locale,
        t,
        onPick: nameDocument,
      }),
    ],
    [lister, reader, conversationId, locale, t, nameDocument],
  );
  // Files are stored in the conversation's own storage, so a conversation
  // not started yet is reserved first, as its first message would.
  const attach =
    staging.attach && session && reader !== null
      ? async (dropId?: string) => {
          let id = conversationId;
          try {
            if (id === null) {
              id = (await session.startConversation()).id;
              started(id);
              if (documentsOpen) change({ panel: "documents" });
            }
          } catch (error) {
            change({ sendFailure: failureCode(error) });
            return;
          }
          const failure = await staging.attach?.(id, dropId);
          if (failure) change({ sendFailure: failure });
        }
      : undefined;

  const dropping = useAgentDrops({
    session,
    enabled:
      shown &&
      reader !== null &&
      !!attach &&
      !historyOpen &&
      !settingsOpen &&
      status?.state === "ready",
    reader,
    conversationId,
    onDrop: (id) => {
      void attach?.(id);
    },
  });

  const { questionnaire, answering, answer, decide, send, stop } = agentSending(
    {
      session,
      reader,
      conversationId,
      catalog,
      selection,
      newest,
      ready,
      sending: view.sending,
      live,
      staging,
      setView,
      currentReader,
      currentSend,
      promptOwner,
      currentPromptOwner,
      pendingPrompt,
      refreshCatalog: agentCatalog.refresh,
    },
  );

  // No provider the agent can run: a key is missing, or every lane is held
  // back. That is not a failure, and the way to a key is offered.
  const incompatible = offer?.incompatible === true;
  const noProvider =
    !incompatible &&
    ((status?.state === "refused" &&
      status.code === "agent_provider_credential_missing") ||
      (offer !== null &&
        offer.observed &&
        !offer.providers.some((provider) => provider.selectable)));
  // Where no lane can run and some lane only lacks a downloaded model, the
  // way on is downloading one rather than setting up a provider.
  // Where no lane can run and a local engine is the one that does not, the
  // way on is the engine's door rather than setting up a provider or
  // downloading a model.
  const engineNotices: EngineNotice[] = noProvider
    ? (offer?.providers ?? []).flatMap((provider) =>
        provider.ways.flatMap((way) =>
          way.engineNotRunning
            ? [
                {
                  id: way.id,
                  words: labelled(t, provider.name, way.engineNotRunning.words),
                  door: way.engineNotRunning.door,
                },
              ]
            : [],
        ),
      )
    : [];
  const engineHeld = engineNotices.length > 0 && !catalogBusy;
  const noModelHeld =
    noProvider && !engineHeld && offer?.modelsToDownload === true;
  const serviceNotice = status ? serviceWords(t, status) : null;
  const notice = incompatible
    ? t("desktop.agent.service_incompatible")
    : catalogBusy
      ? t("desktop.agent.service_starting")
      : engineHeld
        ? null
        : noModelHeld
          ? t("desktop.agent.no_installed_model")
          : noProvider
            ? t("desktop.agent.no_provider")
            : offer !== null && !offer.observed
              ? (serviceNotice ?? t("desktop.agent.lane_not_observed"))
              : serviceNotice;

  return (
    <div
      ref={dropping.target}
      className="relative flex min-h-0 flex-1 flex-col"
    >
      <AgentHeader
        // A conversation not yet started has no title; one the agent was
        // given none for says so.
        title={
          current
            ? current.title || t("desktop.agent.unavailable")
            : t("desktop.agent.new_conversation")
        }
        onRename={
          renameHost && current
            ? (title) => rename(current.id, title, "header")
            : undefined
        }
        onMenu={onMenu}
        historyOpen={historyOpen}
        documentsOpen={documentsOpen}
        documentCount={
          documents.read.kind === "ready" ? documents.read.value.length : 0
        }
        onToggleDocuments={
          serviceReadable && agent?.documents
            ? () => {
                documents.refresh();
                toggle("documents");
              }
            : undefined
        }
        onNewConversation={
          agent
            ? () => {
                pendingPrompt.current = null;
                change({
                  panel: "none",
                  conversationId: null,
                  pending: null,
                  sending: false,
                  interactionId: null,
                  chosen: null,
                  sendFailure: null,
                });
              }
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
          className="agent-lane flex shrink-0 items-start gap-2 bg-accent px-3 py-2 text-xs text-foreground"
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
          <AgentSettingsPanel
            loading={settingsLoading}
            query={settingsQuery}
            onQuery={setSettingsQuery}
            providerMatches={providerMatches}
            onProviderMatch={setProviderMatches}
            accessMatches={accessMatches}
            onAccessMatch={setAccessMatches}
            providerSettings={providerSettings}
            settings={settings}
            agentAccess={agentAccess}
            access={access}
            reader={reader}
            locale={locale}
            writeClipboard={writeClipboard}
            onSignInTerminal={refreshProviderAfterSignIn}
            localModelHost={localModelHost}
            localLanes={localLanes}
            engines={engines}
            localProviderId={localProvider?.id}
            catalogStatus={
              catalog.kind === "ready"
                ? "ready"
                : catalog.kind === "loading"
                  ? "loading"
                  : "failed"
            }
            onRetryCatalog={agentCatalog.retry}
            onLocalModelRemoved={agentCatalog.refresh}
          />
        ) : documentsOpen ? (
          <ConversationDocuments
            documents={documents}
            reader={reader}
            conversationId={conversationId}
            session={session}
            locale={locale}
            named={staging
              .namedFor(conversationId)
              .map((document) => document.name)}
            onClose={() => change({ panel: "none" })}
            onAddFiles={attach ? () => void attach() : undefined}
            onName={(name) => {
              const document =
                documents.read.kind === "ready"
                  ? documents.read.value.find(
                      (document) => document.name === name,
                    )
                  : undefined;
              if (document) staging.name(document);
            }}
            onRemove={
              documents.remove ? (name) => void removeDocument(name) : undefined
            }
          />
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
                busy={view.historyBusy}
                onArchive={
                  archiveHost
                    ? (id) => void mutateHistory(id, "archive")
                    : undefined
                }
                onDelete={
                  session?.delete
                    ? (id) => void mutateHistory(id, "delete")
                    : undefined
                }
                onRename={
                  renameHost
                    ? (id, title) => rename(id, title, "history")
                    : undefined
                }
                onMenu={onMenu}
              />
            </div>
          ) : (
            <ReadState read={conversations} icon="clock" />
          )
        ) : conversationId === null && !pending ? (
          <AgentWelcome />
        ) : history.kind === "ready" ? (
          // Replying again to a failed turn is the agent's to offer; until
          // a host can, Retry says it is not available.
          <>
            {live.read.kind === "failed" && (
              <p role="alert" className="px-3 py-2 text-sm text-destructive">
                {t("desktop.agent.read_failed")}
              </p>
            )}
            <Transcript
              items={history.value}
              onOpenProviderSettings={openSettings}
              onOpenLink={(url) => {
                // Cadrumo's own addresses never reach the browser.
                if (!isCadrumoLink(url)) {
                  onOpenLink?.(url);
                  return;
                }
                const origin =
                  reader === null
                    ? null
                    : { reader, conversation: conversationId };
                onOpenView?.(url, (opened) => {
                  // Back from setting up AEAT access, the person can have
                  // the agent check it again.
                  if (origin && opened === "profile/aeat-access")
                    setSetupCheck(origin);
                });
              }}
            />
          </>
        ) : (
          <ReadState read={history} icon="agent" />
        )}
      </section>
      {/* The history and the settings take the column's whole height, as the
          composer would sit under a list it does not write to. */}
      {!historyOpen && !settingsOpen && (
        <div className="grid shrink-0 gap-2 p-3 pt-0">
          {setupCheck?.reader === reader &&
            setupCheck?.conversation === conversationId && (
              <Button
                disabled={!send || !!live.open}
                onClick={() => {
                  if (!send) return;
                  send(t("desktop.agent.aeat_setup_resume_message"), {
                    skills: [],
                  });
                  setSetupCheck(null);
                }}
              >
                {t("desktop.agent.aeat_setup_check")}
              </Button>
            )}
          <RunPrompts
            session={session}
            approvals={live.approvals}
            questionnaire={questionnaire}
            answering={!!answering}
            onDecide={(approval, optionId) => void decide(approval, optionId)}
            onAnswer={(asked, reply) => void answer(asked, reply)}
            onResolved={live.resolved}
          />
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
          <ColumnNotice
            failure={view.sendFailure}
            fit={view.sendFit}
            notice={notice}
            engines={engineHeld ? engineNotices : undefined}
            onRetry={
              status?.state === "refused" && !unsupported && session?.retry
                ? () => {
                    void session
                      .retry?.()
                      .catch((error: unknown) =>
                        change({ sendFailure: failureCode(error) }),
                      );
                  }
                : undefined
            }
            onSetUpProviders={
              noProvider && !noModelHeld && !engineHeld
                ? openSettings
                : undefined
            }
            onDownloadModels={noModelHeld ? openSettings : undefined}
            onOpenModelSettings={openSettings}
          />
          <Composer
            key={view.draft.key}
            defaultDraft={view.draft.text}
            locale={locale}
            attachments={staging.staged}
            suggestionSources={mentionSources}
            onAddFiles={attach ? () => void attach() : undefined}
            onRemoveAttachment={staging.remove}
            onRemoveAllAttachments={() => staging.remove(null)}
            onShowAllAttachments={() =>
              setAttachmentsShown({ reader, conversation: conversationId })
            }
            providers={offer?.providers ?? NO_PROVIDERS}
            models={offer?.models ?? NO_MODELS}
            selection={selection ?? NO_SELECTION}
            // Questions are answered by a message too, so Send stays.
            running={!questionnaire && (live.working || view.sending)}
            onSend={send}
            onStop={stop}
            skills={skills}
            onSkillCommand={
              reviewSkill || verifySkill ? setSkillShown : undefined
            }
            onSelectionChange={
              offer
                ? (chosen) => {
                    change({ chosen });
                    remember(chosen);
                  }
                : undefined
            }
            pickerRequests={pickerRequests}
            onPickerClosed={() => setPickerRequests(0)}
            onDownloadModels={openSettings}
          />
        </div>
      )}
      {skillShown && (
        <SkillDialog
          command={skillShown}
          locale={locale}
          review={reviewSkill}
          verify={verifySkill}
          onClose={() => setSkillShown(null)}
        />
      )}
      {shown &&
        attachmentsShown !== null &&
        attachmentsShown.reader === reader &&
        attachmentsShown.conversation === conversationId && (
          <StagedAttachmentsDialog
            attachments={staging.staged}
            locale={locale}
            onRemove={staging.remove}
            onRemoveAll={() => staging.remove(null)}
            onAddFiles={attach ? () => void attach() : undefined}
            onClose={() => setAttachmentsShown(null)}
            onAfterClose={() =>
              dropping.target.current
                ?.querySelector<HTMLElement>("textarea")
                ?.focus()
            }
          />
        )}
      <DropOverlay
        visible={dropping.drag !== null}
        armed={dropping.drag?.armed}
        fileCount={dropping.drag?.count}
        acceptedTypes={
          attachmentPolicy.kind === "ready"
            ? attachmentPolicy.value.extensions.map((extension) =>
                extension.toUpperCase(),
              )
            : undefined
        }
        locale={locale}
      />
    </div>
  );
}
