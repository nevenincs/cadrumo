import { useEffect, useId, useRef, type ReactNode } from "react";
import { Field, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import type { AgentAccess, useAgentAccess } from "../../shell/agentAccess";
import type { CatalogLane } from "../../shell/localModelLanes";
import type { LocalModelHost } from "../../shell/localModels";
import type {
  ProviderSettings,
  useProviderSettings,
} from "../../shell/providerSettings";
import { useStrings } from "../../shell/strings";
import { AgentAccess as AgentAccessSection } from "../settings/AgentAccess";
import { LocalModels } from "../settings/LocalModels";
import { ProviderSettings as ProviderSettingsSection } from "../settings/ProviderSettings";
import { LocalAi } from "../setup/LocalAi";
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
  loading,
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
  localLanes,
  localProviderId,
  catalogStatus,
  onRetryCatalog,
  onLocalModelRemoved,
}: {
  /** Some section has not been read the first time yet. */
  loading: boolean;
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
  /** The catalog's lanes with their models. */
  localLanes: CatalogLane[];
  /** The provider lane on this computer, the local AI. */
  localProviderId: string | undefined;
  catalogStatus: "ready" | "loading" | "failed";
  onRetryCatalog: () => void;
  onLocalModelRemoved: () => void;
}) {
  const t = useStrings();
  const searchId = useId();
  const query = settingsQuery.trim().toLocaleLowerCase();
  const titleMatches = (title: string) =>
    Boolean(query) && title.toLocaleLowerCase().includes(query);
  const providerTitleMatches = titleMatches(t("desktop.providers.title"));
  const accessTitleMatches = titleMatches(t("desktop.automation_access.title"));
  const providerVisible =
    Boolean(providerSettings) &&
    (!query || providerTitleMatches || providerMatches);
  const accessVisible =
    Boolean(agentAccess) && (!query || accessTitleMatches || accessMatches);

  // One loader for the whole panel, and only until its sections have first
  // been read: after that the last answers stay on screen while they are read
  // again.
  if (loading) return <ReadState read={{ kind: "loading" }} icon="settings" />;
  return (
    <div className="grid gap-6 p-3">
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
                searching={Boolean(query)}
                embedded
                onMatch={onProviderMatch}
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
                onSignInTerminal={onSignInTerminal}
                localModels={
                  localModelHost
                    ? (lane) => {
                        const listed =
                          localLanes.find((held) => held.id === lane.id) ??
                          null;
                        // The lane on this computer is the local AI: its
                        // program and its model list together.
                        return lane.id === localProviderId ? (
                          <LocalAi
                            key={lane.id}
                            lanes={listed ? [listed] : []}
                            status={catalogStatus}
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
      {query && !providerVisible && !accessVisible && (
        <p role="status">{t("desktop.settings.agent_search_empty")}</p>
      )}
    </div>
  );
}
