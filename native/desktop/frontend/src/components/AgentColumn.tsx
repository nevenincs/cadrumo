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
import { EmptyState } from "@/components/ui/empty";
import { Icon, type IconName } from "@/components/ui/icon";
import { failureCode } from "../errors";
import { useAgentAccess, type AgentAccess } from "../shell/agentAccess";
import {
  catalogChoices,
  ranSelection,
  restoredSelection,
  selectionRecord,
} from "../shell/agentCatalog";
import { useRememberedChoice } from "../shell/agentChoice";
import {
  DocumentLister,
  documentRefs,
  extensionOf,
  fileKindOf,
  MAX_REFERENCES,
} from "../shell/agentDocuments";
import { useDocumentInventory } from "../shell/agentDocumentInventory";
import { useStagedDocuments } from "../shell/agentStaging";
import { useAgentDrops } from "../shell/agentDrops";
import { DropOverlay } from "./agent/DropOverlay";
import { DocumentsPanel } from "./agent/DocumentsPanel";
import { StagedAttachmentsDialog } from "./agent/StagedAttachmentsDialog";
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
  AgentToolRefusal,
} from "../shell/agentSession";
import {
  archivedCount,
  createTranscriptProjection,
  newestRanWith,
  replyFacts,
  replyIdOf,
  transcriptItems,
  useAgentRead,
  useConversationGroups,
  type AgentRead,
  type AgentDocumentReference,
  type AgentViews,
} from "../shell/agentViews";
import { queuedWords, runStateWords } from "../shell/agentWords";
import {
  useProviderSettings,
  type ProviderSettings,
} from "../shell/providerSettings";
import { useStrings, type Translate } from "../shell/strings";
import type { OpenMenu } from "./ContextMenu";
import { AgentHeader } from "./agent/AgentHeader";
import { AgentWelcome } from "./agent/AgentWelcome";
import { ApprovalPrompt } from "./agent/ApprovalPrompt";
import { Composer, type ComposerReferences } from "./agent/Composer";
import { documentSource } from "./agent/DocumentMentions";
import { HistoryList } from "./agent/HistoryList";
import { QuestionsPrompt } from "./agent/QuestionsPrompt";
import { ModelRolesDialog } from "./agent/ModelRolesDialog";
import { SkillDialog } from "./agent/SkillDialog";
import { useSkillInventory } from "./agent/SlashSuggestions";
import { roleLanes } from "../shell/agentModelRoles";
import type { ModelRoleHost } from "../shell/modelRoles";
import type { SkillCommand } from "../shell/agentSkills";
import { AgentAccess as AgentAccessSection } from "./settings/AgentAccess";
import { LocalModels } from "./settings/LocalModels";
import { ProviderSettings as ProviderSettingsSection } from "./settings/ProviderSettings";
import { Transcript } from "./agent/Transcript";
import type {
  AgentSelection,
  ModelOption,
  ProviderOption,
} from "./agent/types";

// What the composer is given while nothing serves it: nothing. Sending,
// adding files and choosing a model each say they are not available yet.
const NO_PROVIDERS: ProviderOption[] = [];
/** How often, and after how long a first pause, a busy service is asked for its catalog again. */
const CATALOG_BUSY_RETRIES = 3;
const CATALOG_BUSY_PAUSE_MS = 2_000;
const NO_MODELS: Record<string, ModelOption[]> = {};
const NO_SELECTION: AgentSelection = {
  providerId: "",
  wayId: "",
  modelId: "",
};

type Panel = "none" | "history" | "settings" | "documents";

export type AgentColumnControl = {
  openLocalAi(): void;
  openModelRoles(): void;
};

type PendingSend = {
  id: string;
  conversationId: string | null;
  replyId: string | null;
  text: string;
  attachments: AgentDocumentReference[];
  skills: string[];
  previousReplies: string[];
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
    case "agent_service_busy":
      return t("desktop.agent.service_starting");
    case "agent_reply_in_progress":
      return t("desktop.agent.reply_in_progress");
    case "agent_conversation_delete_incomplete":
      return t("desktop.agent.delete_incomplete");
    case "agent_gateway_attachment_not_found":
      return t("desktop.agent.reference_missing");
    case "agent_gateway_attachment_changed":
      return t("desktop.agent.reference_changed");
    case "agent_gateway_attachment_refused":
    case "agent_gateway_attachments_invalid":
      return t("desktop.agent.reference_refused");
    case "agent_gateway_attachments_unavailable":
      return t("desktop.agent.references_unavailable");
    case "agent_gateway_conversation_deleting":
      return t("desktop.agent.conversation_deleting");
    case "agent_gateway_conversation_id_taken":
      return t("desktop.agent.conversation_id_taken");
    default:
      return t("desktop.agent.request_failed");
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
  onMenu,
  onToolRefused,
  onOpenLink,
  onOpenView,
  onSetUpLocalAi,
  onRemoveLocalModel,
  onOpenLocalAi,
  control,
  localAiSetup,
  onShowLocalAiSetup,
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
  /** Opens setup on the local AI, where this window offers setup. */
  onSetUpLocalAi?: () => void;
  /** Removes one local model no role selects, answering the refusal's code
   * or null, where this window offers setup. */
  onRemoveLocalModel?: (model: string) => Promise<string | null>;
  onOpenLocalAi?: () => void;
  /** The last setup that settled, by operation: what this computer holds may
   * have changed, so the catalog is read again. */
  setupSettled?: string | null;
  control?: Ref<AgentColumnControl>;
  /** The existing component status and recovery beside its local models. */
  localAiSetup?: ReactNode;
  onShowLocalAiSetup?: () => void;
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
  const [view, setView] = useState({
    reader,
    panel: "none" as Panel,
    localFocus: 0,
    archived: false,
    conversationId: null as string | null,
    chosen: null as AgentSelection | null,
    sending: false,
    pending: null as PendingSend | null,
    sendFailure: null as string | null,
    // Why the history's last action was refused.
    archiveFailure: null as string | null,
    historyBusy: false,
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
      localFocus: 0,
      archived: false,
      conversationId: null,
      chosen: null,
      sending: false,
      pending: null,
      sendFailure: null,
      archiveFailure: null,
      historyBusy: false,
      draft: { key: view.draft.key + 1, text: "" },
      revision: 0,
    });
  const { panel, archived, conversationId, revision } = view;
  const currentSend = useRef<string | null>(null);
  currentSend.current = view.pending?.id ?? null;
  const change = (next: Partial<typeof view>) =>
    setView((held) => ({ ...held, ...next }));

  const readable = agent !== undefined && reader !== null && shown;
  const status = useAgentStatus(session, readable);
  const ready = status?.state === "ready";
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
      serviceReadable && agent && (historyOpen || wanted)
        ? () => agent.conversations()
        : null,
    [serviceReadable, agent, historyOpen, wanted],
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
  const projectTranscript = useMemo(() => createTranscriptProjection(), []);
  const history = useMemo((): AgentRead<ReturnType<typeof transcriptItems>> => {
    if (live.read.kind !== "ready" && !pending) return live.read;
    const records = live.read.kind === "ready" ? [...live.read.value] : [];
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
  }, [live.read, pending, locale, t, projectTranscript]);
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
  // The person's model for each role that reads documents, where the host
  // offers reading and changing it.
  const [rolesShown, setRolesShown] = useState(false);
  const openLocalAi = useCallback(() => {
    setRolesShown(false);
    setView((held) => ({
      ...held,
      panel: "settings",
      localFocus: held.localFocus + 1,
    }));
  }, []);
  useImperativeHandle(
    control,
    () => ({
      openLocalAi,
      openModelRoles() {
        setRolesShown(true);
      },
    }),
    [openLocalAi],
  );
  const roleHost = useMemo((): ModelRoleHost | null => {
    if (
      !session?.modelRoles ||
      !session.setModelRole ||
      !session.clearModelRole
    )
      return null;
    return {
      read: session.modelRoles.bind(session),
      set: session.setModelRole.bind(session),
      clear: session.clearModelRole.bind(session),
      ...(session.modelLicence
        ? { licence: session.modelLicence.bind(session) }
        : {}),
    };
  }, [session]);
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
  // What it can run is the agent's own catalog, every lane of it. While the
  // agent starts, the service answers with the lanes the agent declares,
  // which are listed but cannot be chosen; the catalog is read again once the
  // agent is ready.
  const starting = status?.state === "starting";
  const readCatalog = useMemo(
    () =>
      (ready || starting) && session ? () => session.providerCatalog() : null,
    [ready, starting, session],
  );
  // Setup and provider settings invalidate the catalog independently.
  const [catalogAgain, setCatalogAgain] = useState(0);
  // Reads asked for while the service was busy.
  const [busyReads, setBusyReads] = useState(0);
  const catalog = useAgentRead(
    readCatalog,
    catalogAgain + settings.changes + busyReads + opened,
  );
  // A settled setup may have downloaded a model: what the catalog says this
  // computer holds is read again.
  useEffect(() => {
    if (setupSettled) setCatalogAgain((count) => count + 1);
  }, [setupSettled]);
  // The lanes whose models the person chooses, which a lane on this computer
  // lists in its provider settings.
  const localLanes = useMemo(
    () => (catalog.kind === "ready" ? roleLanes(catalog.value) : []),
    [catalog],
  );
  // A service still busy starting the agent answers the catalog late. The
  // column says the agent is still starting and asks again at the service's
  // next published status; a few reads, each after a longer pause, are the
  // bounded fallback when it publishes none.
  const catalogBusy =
    catalog.kind === "failed" && catalog.code === "agent_service_busy";
  const busyCatalogReads = useRef(0);
  const statusAtBusyRead = useRef(status);
  useEffect(() => {
    if (catalog.kind === "ready") busyCatalogReads.current = 0;
    if (!catalogBusy) return;
    if (statusAtBusyRead.current !== status) {
      statusAtBusyRead.current = status;
      setBusyReads((count) => count + 1);
      return;
    }
    if (busyCatalogReads.current >= CATALOG_BUSY_RETRIES) return;
    const pause = CATALOG_BUSY_PAUSE_MS * 2 ** busyCatalogReads.current;
    busyCatalogReads.current += 1;
    const again = window.setTimeout(
      () => setBusyReads((count) => count + 1),
      pause,
    );
    return () => window.clearTimeout(again);
  }, [catalog, catalogBusy, status]);
  const offer = useMemo(
    () => (catalog.kind === "ready" ? catalogChoices(t, catalog.value) : null),
    [catalog, t],
  );
  // What the next message runs with: what the person chose while this
  // conversation is shown, else what the conversation last ran with, else the
  // profile's last choice, each only where the catalog still offers it.
  const { remembered, remember } = useRememberedChoice(reader);
  const ranWith =
    conversationId !== null && live.read.kind === "ready"
      ? newestRanWith(live.read.value)
      : undefined;
  const selection = offer
    ? restoredSelection(offer, [
        view.chosen,
        ranWith && catalog.kind === "ready"
          ? ranSelection(catalog.value, ranWith)
          : null,
        remembered,
      ])
    : null;

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
  const open = useCallback(
    (id: string) =>
      setView((held) => ({
        ...held,
        panel: "none",
        conversationId: id,
        pending: null,
        sending: false,
        // A conversation opened runs with its own choice, not the last one's.
        chosen: held.conversationId === id ? held.chosen : null,
        sendFailure: null,
        archiveFailure: null,
      })),
    [],
  );
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
    change({ panel: panel === next ? "none" : next, localFocus: 0 });
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
      ? () => change({ panel: "settings" })
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
  const namedFor = staging.namedFor;
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

  // A send that did not go is given back to the composer to try again.
  const giveBack = (text: string, failure: string | null) =>
    setView((held) => ({
      ...held,
      sending: false,
      pending: null,
      sendFailure: failure,
      draft: { key: held.draft.key + 1, text },
    }));
  const deliver = async (
    request: AgentSendRequest,
    submission: PendingSend,
  ) => {
    if (!session) return;
    const current = () =>
      currentReader.current === reader && currentSend.current === submission.id;
    try {
      const { reply_id } = await session.send(request);
      if (!current()) return;
      // The agent returns no id for the message, so it is shown as sent until
      // the history has it.
      live.sent({
        reply_id,
        text: request.text,
        at: "start",
        attachments: submission.attachments,
        ...(request.skills ? { skills: request.skills } : {}),
      });
      // What the message named went with it.
      staging.sent(request.conversation_id);
      // A message sent may name the conversation, so it is read again.
      setView((held) => ({
        ...held,
        sending: false,
        pending:
          held.pending?.id === submission.id
            ? { ...held.pending, replyId: reply_id }
            : held.pending,
        revision: held.revision + 1,
      }));
    } catch (error) {
      if (current()) giveBack(request.text, failureCode(error));
    }
  };
  // Pressing Send is the person's decision: the message goes, and nothing
  // asks them again.
  const submit = async (
    text: string,
    chosen: AgentSelection,
    references: ComposerReferences,
  ) => {
    if (!session || catalog.kind !== "ready") return;
    const runs = selectionRecord(catalog.value, chosen);
    if (!runs) {
      giveBack(text, "agent_selection_unavailable");
      return;
    }
    const submission: PendingSend = {
      id: crypto.randomUUID(),
      conversationId,
      replyId: null,
      text,
      attachments: conversationId
        ? namedFor(conversationId).map(({ name, sha256, media_type }) => ({
            name,
            sha256,
            media_type,
          }))
        : [],
      skills: references.skills,
      previousReplies:
        live.read.kind === "ready" ? live.read.value.map(replyIdOf) : [],
    };
    currentSend.current = submission.id;
    change({ pending: submission });
    const current = () =>
      currentReader.current === reader && currentSend.current === submission.id;
    let request: AgentSendRequest;
    try {
      // A new conversation begins with its first message, never on its own.
      let id = conversationId;
      if (id === null) {
        id = (await session.startConversation()).id;
        if (!current()) return;
        setView((held) => ({
          ...held,
          conversationId: id,
          pending: held.pending
            ? { ...held.pending, conversationId: id }
            : null,
        }));
      }
      // Watched before anything is sent, so the reply is followed from its
      // first word.
      await live.watch(id);
      if (!current()) return;
      request = { conversation_id: id, text, selection: runs };
      if (references.skills.length > 0) request.skills = references.skills;
      const named = namedFor(id);
      if (named.length > 0) request.attachments = documentRefs(named);
    } catch (error) {
      if (current()) giveBack(text, failureCode(error));
      return;
    }
    // A send that fails is given back by `deliver` itself.
    await deliver(request, submission);
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
        ? (text: string, references: ComposerReferences) => {
            change({ sending: true, sendFailure: null });
            void submit(text, selection, references);
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
        offer.observed &&
        !offer.providers.some((provider) => provider.selectable)));
  const serviceNotice = status ? serviceWords(t, status) : null;
  const notice = incompatible
    ? t("desktop.agent.service_incompatible")
    : catalogBusy
      ? t("desktop.agent.service_starting")
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
            ? () =>
                change({
                  panel: "none",
                  conversationId: null,
                  pending: null,
                  sending: false,
                  chosen: null,
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
          settingsLoading ? (
            // One loader for the whole panel, and only until its sections
            // have first been read: after that the last answers stay on screen
            // while they are read again.
            <ReadState read={{ kind: "loading" }} icon="settings" />
          ) : (
            // Each section the host offers is shown, or says it failed, on its
            // own: provider settings and sign-in, plus keys for agents outside
            // Cadrumo.
            <div className="grid gap-6 p-3">
              {view.localFocus > 0 &&
                settings.read.kind === "ready" &&
                !localProvider && (
                  <div className="grid gap-2">
                    {localAiSetup}
                    <p className="text-sm text-muted-foreground">
                      {t("desktop.providers.local_models_none")}
                    </p>
                    {onShowLocalAiSetup && (
                      <Button variant="outline" onClick={onShowLocalAiSetup}>
                        {t("desktop.setup.open")}
                      </Button>
                    )}
                  </div>
                )}
              {providerSettings &&
                (settings.read.kind === "ready" ? (
                  <ProviderSettingsSection
                    key={view.localFocus}
                    focusLane={
                      view.localFocus > 0 ? localProvider?.id : undefined
                    }
                    providers={settings.read.value.providers}
                    signIn={providerSettings.signIn}
                    signInProviders={settings.read.value.signInProviders}
                    signInMethods={settings.read.value.signInMethods}
                    revisions={settings.read.value.revisions}
                    identity={reader}
                    busyId={settings.busyId}
                    outcomes={settings.outcomes}
                    onSave={settings.save}
                    onTurnOff={settings.turnOff}
                    onTurnOn={settings.turnOn}
                    onReset={settings.reset}
                    onRefresh={settings.refresh}
                    onSignInTerminal={refreshProviderAfterSignIn}
                    localModels={
                      roleHost
                        ? (lane) => (
                            <div className="grid gap-3">
                              {lane.id === localProvider?.id && localAiSetup}
                              <LocalModels
                                lane={
                                  localLanes.find(
                                    (held) => held.id === lane.id,
                                  ) ?? null
                                }
                                host={roleHost}
                                locale={locale}
                                onSetUp={onSetUpLocalAi}
                                onRemove={
                                  onRemoveLocalModel
                                    ? (model) =>
                                        onRemoveLocalModel(model).then(
                                          (code) => {
                                            if (code === null)
                                              setCatalogAgain(
                                                (count) => count + 1,
                                              );
                                            return code;
                                          },
                                        )
                                    : undefined
                                }
                              />
                            </div>
                          )
                        : undefined
                    }
                  />
                ) : settings.read.kind === "failed" ? (
                  <SectionFailure
                    words={t("desktop.providers.load_failed")}
                    onRetry={settings.refresh}
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
                ) : access.read.kind === "failed" ? (
                  <SectionFailure
                    words={t("desktop.agent.read_failed")}
                    onRetry={access.refresh}
                  />
                ) : (
                  <ReadState read={access.read} icon="settings" />
                ))}
            </div>
          )
        ) : documentsOpen ? (
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
                selectedIds={staging
                  .namedFor(conversationId)
                  .map((document) => document.name)}
                onClose={() => change({ panel: "none" })}
                onAddFiles={attach ? () => void attach() : undefined}
                onRefresh={documents.refresh}
                onUse={(name) => {
                  const document =
                    documents.read.kind === "ready"
                      ? documents.read.value.find(
                          (document) => document.name === name,
                        )
                      : undefined;
                  if (document) staging.name(document);
                }}
                onRemove={
                  documents.remove
                    ? (name) => void removeDocument(name)
                    : undefined
                }
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
              locale={locale}
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
          {live.approvals.map((approval) => (
            <ApprovalPrompt
              key={approval.request_id}
              source={approval.source}
              toolCall={approval.tool_call}
              toolServer={approval.tool_server}
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
                  {status?.state === "refused" && session?.retry && (
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => {
                        void session
                          .retry?.()
                          .catch((error: unknown) =>
                            change({ sendFailure: failureCode(error) }),
                          );
                      }}
                    >
                      {t("desktop.agent.retry")}
                    </Button>
                  )}
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
            onModelRoles={roleHost ? () => setRolesShown(true) : undefined}
          />
        </div>
      )}
      {rolesShown && roleHost && (
        <ModelRolesDialog
          host={roleHost}
          catalog={catalog.kind === "ready" ? catalog.value : null}
          locale={locale}
          onClose={() => setRolesShown(false)}
          onLocalAi={
            providerSettings ? (onOpenLocalAi ?? openLocalAi) : undefined
          }
        />
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

/** A settings section that could not be read, and the way to read it again. */
function SectionFailure({
  words,
  onRetry,
}: {
  words: string;
  onRetry: () => void;
}) {
  const t = useStrings();
  return (
    <div role="alert" className="grid justify-items-start gap-2">
      <p className="text-sm text-foreground">{words}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        {t("desktop.providers.refresh")}
      </Button>
    </div>
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
  if (read.kind === "loading") return <EmptyState role="status" busy />;
  return (
    <EmptyState
      role={read.kind === "failed" ? "alert" : "status"}
      icon={read.kind === "failed" ? "alert" : icon}
      heading={
        read.kind === "failed"
          ? t("desktop.agent.read_failed")
          : t("desktop.agent.unavailable")
      }
    />
  );
}
