import { useEffect, useId, useRef, type ReactNode } from "react";
import { Field, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import type { AgentAccess, useAgentAccess } from "../../shell/agentAccess";
import { offerMatches } from "../../shell/agentOffer";
import { useAgentOffer } from "../../shell/agentOfferContext";
import type { AgentServiceStatus } from "../../shell/agentSession";
import type { LocalModelHost } from "../../shell/localModels";
import {
  settingsAwaitStart,
  type ProviderSettings,
  type useProviderSettings,
} from "../../shell/providerSettings";
import { useStrings } from "../../shell/strings";
import { AgentAccess as AgentAccessSection } from "../settings/AgentAccess";
import { LocalModels } from "../settings/LocalModels";
import {
  ProviderSettings as ProviderSettingsSection,
  ProviderSettingsWaiting,
  type ProviderServiceWait,
} from "../settings/ProviderSettings";
import { TaskAssignments } from "../settings/TaskAssignments";
import { LocalAi } from "../setup/LocalAi";
import { serviceWords } from "./agentRefusalWords";
import { ReadState, SectionFailure } from "./ReadState";

function SettingsDisclosure({
  title,
  visible,
  searching,
  children,
}: {
  title: string;
  visible: boolean;
  searching: boolean;
  children: ReactNode;
}) {
  const details = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (searching && visible && details.current) details.current.open = true;
  }, [searching, visible]);
  return (
    <details
      ref={details}
      open
      hidden={!visible}
      className="group/settings rounded-lg bg-card p-3"
    >
      <summary className="flex min-h-control-lg cursor-pointer items-center justify-between gap-2 rounded-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring">
        {title}
        <Icon
          name="chevronDown"
          className="shrink-0 transition-transform group-open/settings:rotate-180"
        />
      </summary>
      <div className="pt-3">{children}</div>
    </details>
  );
}

/**
 * The agent's settings: a search over them, then each section the host
 * offers, shown or saying it failed on its own: provider settings and
 * sign-in, with the local AI and the local model lists, plus keys for agents
 * outside Cadrumo.
 */
export function AgentSettingsPanel({
  query: settingsQuery,
  onQuery,
  providerMatches,
  onProviderMatch,
  accessMatches,
  onAccessMatch,
  providerSettings,
  settings,
  agentAccess,
  access,
  reader,
  locale,
  writeClipboard,
  onSignInTerminal,
  localModelHost,
  localProviderId,
  catalogStatus,
  catalogFailure = null,
  onRetryCatalog,
  onLocalModelRemoved,
  service = null,
  onRetryService,
}: {
  query: string;
  onQuery: (query: string) => void;
  providerMatches: boolean;
  onProviderMatch: (matches: boolean) => void;
  accessMatches: boolean;
  onAccessMatch: (matches: boolean) => void;
  providerSettings: ProviderSettings | undefined;
  settings: ReturnType<typeof useProviderSettings>;
  agentAccess: AgentAccess | undefined;
  access: ReturnType<typeof useAgentAccess>;
  reader: string | null;
  locale: string;
  writeClipboard?: (text: string) => Promise<void>;
  /** A provider sign-in finished: the revision it left, where read. */
  onSignInTerminal: (
    providerId: string,
    identity: string | null,
  ) => Promise<string | undefined>;
  /** The local model lists, where the agent runs and the host offers them. */
  localModelHost: LocalModelHost | null;
  /** The provider lane on this computer, the local AI. */
  localProviderId: string | undefined;
  catalogStatus: "ready" | "loading" | "failed";
  /** The refusal the catalogue read answered, while it is failed. */
  catalogFailure?: string | null;
  onRetryCatalog: () => void;
  onLocalModelRemoved: () => void;
  /** Where the agent service is, as it last published; null before its
   * first status. */
  service?: AgentServiceStatus | null;
  /** Starts the service again after it published a refusal a new start can
   * move on. */
  onRetryService?: () => void;
}) {
  const t = useStrings();
  const offer = useAgentOffer();
  const searchId = useId();
  const panel = useRef<HTMLDivElement>(null);
  // The way on for a lane a task cannot run on yet is in that provider's
  // own settings above: they are opened and brought into view.
  const showProvider = (provider: string) => {
    const group = [
      ...(panel.current?.querySelectorAll<HTMLElement>("li[data-provider]") ??
        []),
    ].find((held) => held.dataset.provider === provider);
    if (!group) return;
    for (
      let open = group.closest("details");
      open;
      open = open.parentElement?.closest("details") ?? null
    )
      open.open = true;
    // The provider's first connection row, with its details opened.
    const expander = group.querySelector<HTMLElement>(
      "[data-slot=lane-expander]",
    );
    if (expander?.getAttribute("aria-expanded") === "false") expander.click();
    group.scrollIntoView({ block: "nearest" });
    expander?.focus();
  };
  const query = settingsQuery.trim().toLocaleLowerCase();
  const titleMatches = (title: string) =>
    Boolean(query) && offerMatches([title], query);
  const providerTitleMatches = titleMatches(t("desktop.providers.title"));
  const accessTitleMatches = titleMatches(t("desktop.automation_access.title"));
  const tasksTitleMatches = titleMatches(
    t("desktop.providers.task_models_title"),
  );
  const tasksOffered = Boolean(localModelHost?.chooseTask);
  const tasksVisible = tasksOffered && (!query || tasksTitleMatches);
  // Each section is drawn as soon as its own read answers, and says on its
  // own while it is read; one that has not answered yet cannot be said not to
  // match a search, so it stays shown.
  const providerVisible =
    Boolean(providerSettings) &&
    (!query ||
      providerTitleMatches ||
      providerMatches ||
      settings.read.kind === "loading");
  // While the settings are unread, where the service stands says why: the host
  // answers busy until it admits the service, the admitted service answers
  // not signed in until it takes up the person's session, and a service that
  // stopped (or never starts) published its reason, which a read then fails
  // on. Only a read that failed otherwise is the section's own failure.
  const stopped =
    service?.state === "refused" || service?.state === "stopped"
      ? service
      : null;
  const read = settings.read;
  const wait: ProviderServiceWait | null =
    read.kind === "ready" || read.kind === "unavailable"
      ? null
      : read.kind === "loading"
        ? service?.state === "ready"
          ? null
          : { state: "starting" }
        : read.code === "busy"
          ? { state: "starting" }
          : stopped
            ? {
                state: "stopped",
                words: serviceWords(t, stopped) ?? "",
                ...(stopped.state === "refused" && onRetryService
                  ? { onRetry: onRetryService }
                  : {}),
              }
            : settingsAwaitStart(read.code)
              ? { state: "starting" }
              : null;
  const accessVisible =
    Boolean(agentAccess) &&
    (!query ||
      accessTitleMatches ||
      accessMatches ||
      access.read.kind === "loading");
  return (
    <div ref={panel} className="grid gap-6 p-3">
      <Field>
        <FieldLabel htmlFor={searchId}>
          {t("desktop.settings.agent_search")}
        </FieldLabel>
        <Input
          id={searchId}
          type="search"
          value={settingsQuery}
          onChange={(event) => onQuery(event.currentTarget.value)}
        />
      </Field>
      {providerSettings && (
        <SettingsDisclosure
          title={t("desktop.providers.title")}
          visible={providerVisible}
          searching={Boolean(query)}
        >
          {providerSettings &&
            (settings.read.kind === "ready" ? (
              <ProviderSettingsSection
                query={providerTitleMatches ? "" : query}
                embedded
                onMatch={onProviderMatch}
                providers={settings.read.value.providers}
                signIn={providerSettings.signIn}
                signInProviders={settings.read.value.signInProviders}
                signInMethods={settings.read.value.signInMethods}
                consoleSignInCommand={settings.read.value.consoleSignInCommand}
                revisions={settings.read.value.revisions}
                readsPending={settings.read.value.readsPending}
                identity={reader}
                busyId={settings.busyId}
                outcomes={settings.outcomes}
                onSave={settings.save}
                onTurnOff={settings.turnOff}
                onTurnOn={settings.turnOn}
                onReset={settings.reset}
                onSignOut={settings.signOut}
                onRefresh={settings.refresh}
                onSignInTerminal={onSignInTerminal}
                lanes={offer?.lanes}
                localModels={
                  localModelHost
                    ? (lane) => {
                        const listed =
                          offer?.modelLanes.find(
                            (held) => held.id === lane.id,
                          ) ?? null;
                        // The lane on this computer is the local AI: its
                        // program and its model list together.
                        return lane.id === localProviderId ? (
                          <LocalAi
                            key={lane.id}
                            lanes={listed ? [listed] : []}
                            status={catalogStatus}
                            failure={catalogFailure}
                            onRetry={onRetryCatalog}
                            host={localModelHost}
                            locale={locale}
                            onRemoved={onLocalModelRemoved}
                          />
                        ) : (
                          <LocalModels
                            key={lane.id}
                            lane={listed}
                            laneStatus={catalogStatus}
                            laneFailure={catalogFailure}
                            onRetryLane={onRetryCatalog}
                            host={localModelHost}
                            locale={locale}
                            onRemoved={onLocalModelRemoved}
                          />
                        );
                      }
                    : undefined
                }
              />
            ) : wait ? (
              // The settings are read again on the status the service
              // publishes next: a wait, not a failure to retry.
              <ProviderSettingsWaiting
                embedded
                wait={wait}
                lanes={offer ? [...offer.lanes.values()] : []}
              />
            ) : settings.read.kind === "failed" ? (
              <SectionFailure
                words={t("desktop.providers.load_failed")}
                onRetry={settings.refresh}
              />
            ) : (
              <ReadState read={settings.read} icon="settings" />
            ))}
        </SettingsDisclosure>
      )}
      {agentAccess && (
        <SettingsDisclosure
          title={t("desktop.automation_access.title")}
          visible={accessVisible}
          searching={Boolean(query)}
        >
          {agentAccess &&
            (access.read.kind === "ready" ? (
              <AgentAccessSection
                query={accessTitleMatches ? "" : query}
                embedded
                onMatch={onAccessMatch}
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
        </SettingsDisclosure>
      )}
      {localModelHost && tasksOffered && (
        <SettingsDisclosure
          title={t("desktop.providers.task_models_title")}
          visible={tasksVisible}
          searching={Boolean(query)}
        >
          <TaskAssignments
            host={localModelHost}
            catalogStatus={catalogStatus}
            catalogFailure={catalogFailure}
            onRetryCatalog={onRetryCatalog}
            onShowProvider={providerSettings ? showProvider : undefined}
          />
        </SettingsDisclosure>
      )}
      {query && !providerVisible && !accessVisible && !tasksVisible && (
        <p role="status">{t("desktop.settings.agent_search_empty")}</p>
      )}
    </div>
  );
}
