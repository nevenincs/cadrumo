import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { TextEditor } from "@/components/editors/TextEditor";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import iconArtwork from "virtual:desktop-provider-icons";
import type { AgentEngineHealth } from "../../shell/agentSession";
import {
  groupedByProvider,
  laneStatus,
  offerMatches,
  type LaneReason,
  type LaneStatus,
  type OfferedLane,
} from "../../shell/agentOffer";
import type { SetupRow } from "../../ipc/componentSetup";
import { engineNotRunningWords } from "../../shell/engineHealth";
import { connectionWords } from "../../shell/providerConnection";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings, type Translate } from "../../shell/strings";
import { ProviderMark } from "../agent/ProviderMark";
import { EngineDoor } from "../setup/EngineDoor";
import { rowSentence } from "../setup/setupWords";
import { ProviderSignInDialog } from "./ProviderSignInDialog";
import { SignInAdvice } from "./SignInAdvice";
import type { ProviderSignIn } from "../../shell/providerSettings";
import type { ProviderSignInMethod } from "../../shell/providerSettingsContract";
import type { ProviderOutcome, ProviderSecret, ProviderStatus } from "./types";

const STATUS_WORDS = {
  ready: "desktop.providers.status_ready",
  saved: "desktop.providers.status_saved",
  signed_in: "desktop.providers.status_signed_in",
  not_checked: "desktop.providers.status_not_checked",
  setup_needed: "desktop.providers.status_setup_needed",
  sign_in_needed: "desktop.providers.status_sign_in_needed",
  unconfirmed: "desktop.providers.status_unconfirmed",
  engine_not_running: "desktop.agent.engine_not_running",
  off: "desktop.providers.status_off",
} as const satisfies Record<LaneStatus, string>;

/** A lane's status in one word; a lane turned off with its key stored says
 * that the key is kept, as the service serves `credential_saved`. */
function statusWords(
  t: Translate,
  status: LaneStatus,
  provider: ProviderStatus,
): string {
  if (status === "off" && provider.credentialSaved)
    return t("desktop.providers.status_off_kept");
  return t(STATUS_WORDS[status]);
}

/** The statuses that wait on the person, drawn in the warning tone; one in
 * use reads in the body text, and one with nothing to do (off, not checked)
 * in secondary text. */
const STATUS_TONE: Record<LaneStatus, string> = {
  ready: "text-foreground",
  saved: "text-foreground",
  signed_in: "text-foreground",
  not_checked: "text-muted-foreground",
  off: "text-muted-foreground",
  setup_needed: "text-warning",
  sign_in_needed: "text-warning",
  unconfirmed: "text-warning",
  engine_not_running: "text-warning",
};

/** Why a lane stands where it does and what moves it on, in words. A lane
 * whose app could not be confirmed says it through its served cause and
 * step instead, so it has none here. */
function reasonWords(
  t: Translate,
  reason: LaneReason,
  provider: ProviderStatus,
  engine: AgentEngineHealth | null,
  setup: SetupRow | null,
): string | null {
  switch (reason) {
    case "turned_off":
      return t("desktop.providers.reason_turned_off");
    case "record_unreadable":
      return t("desktop.providers.reason_record_unreadable");
    case "app_missing":
      return t("desktop.providers.detail_app_missing", {
        provider: provider.name,
      });
    case "add_key":
      return t("desktop.providers.reason_add_key", { provider: provider.name });
    case "check_settings":
      return t("desktop.providers.reason_check_settings");
    case "key_saved":
      return t("desktop.providers.reason_key_saved");
    case "sign_in":
      return t("desktop.providers.detail_sign_in", { provider: provider.name });
    case "app_unconfirmed":
      return null;
    case "signed_in":
      return t("desktop.providers.reason_signed_in", {
        provider: provider.name,
      });
    case "not_checked":
      return t("desktop.providers.reason_not_checked");
    case "engine_not_running":
      return engine ? engineNotRunningWords(t, engine) : null;
    case "local_setup":
    case "local_ready":
      return setup
        ? rowSentence(t, setup)
        : t("desktop.providers.reason_local_ready");
  }
}

/** The refusal of a change while the agent is starting, which passes by
 * waiting: a key being saved keeps its form and what was typed in it. */
const agentStarting = (outcome: ProviderOutcome | undefined) =>
  outcome?.kind === "refused" && outcome.code === "busy";

/** Why a change was not made, in words where it is a refusal we know. */
function refusalWords(
  t: Translate,
  outcome: Extract<ProviderOutcome, { kind: "refused" }>,
): string {
  switch (outcome.code) {
    case "not_signed_in":
      return t("desktop.providers.refused_not_signed_in");
    case "profile_locked":
      return t("desktop.providers.refused_profile_locked");
    case "invalid_key_format":
      return t("desktop.providers.refused_invalid_key_format");
    case "base_url_rejected":
      return t("desktop.providers.refused_base_url_rejected");
    case "revision_conflict":
      return t("desktop.providers.refused_revision_conflict");
    case "catalog_unavailable":
      return t("desktop.providers.load_failed");
    case "runtime_unavailable":
      return t("desktop.providers.refused_runtime_unavailable");
    case "person_act_required":
      return t("desktop.providers.refused_person_act_required");
    case "model_list_full":
      return t("desktop.providers.refused_model_list_full");
    case "busy":
      return outcome.cause === "agent_tree_running"
        ? t("desktop.providers.refused_agent_starting")
        : t("desktop.providers.refused_busy");
    case "service_failed":
      return t("desktop.providers.refused_service_failed");
    case "timed_out":
      return t("desktop.providers.refused_timed_out");
    default:
      return t("desktop.providers.change_failed");
  }
}

/** A refused change: why, the served cause where the refusal words do not
 * already say it, and the log line's reference. */
function Refusal({
  outcome,
  provider,
  children,
}: {
  outcome: Extract<ProviderOutcome, { kind: "refused" }>;
  provider: string;
  children?: ReactNode;
}) {
  const t = useStrings();
  const said =
    outcome.code === "busy" && outcome.cause === "agent_tree_running";
  return (
    <div role="alert" className="flex items-start gap-2 text-sm">
      <Icon name="alert" className="mt-0.5 text-destructive" />
      <div className="grid flex-1 gap-1">
        <span>{refusalWords(t, outcome)}</span>
        {!said && <SignInAdvice causes={[outcome.cause]} provider={provider} />}
        {outcome.logRef && (
          <p data-slot="change-log-ref" className="text-muted-foreground">
            {t("desktop.providers.sign_in_log_ref")}{" "}
            <code className="font-mono text-foreground select-all">
              {outcome.logRef}
            </code>
          </p>
        )}
        {children}
      </div>
    </div>
  );
}

/**
 * Where a key or token is written to be saved. The field is the only place
 * the secret ever is: nothing keeps it as the field changes, only whether it
 * holds anything. Saving reads it and hands the secret on; the field keeps
 * what was typed until the save is answered, so a save refused while the
 * agent starts can be tried again as it was, and the form is gone, with the
 * field, once the save is done. Nothing here can show a stored key, and the
 * field has no placeholder that could be taken for one.
 */
function SecretForm({
  provider,
  saving,
  refused,
  onSave,
  onCancel,
}: {
  provider: ProviderStatus;
  saving: boolean;
  /** The last save was refused while the agent starts. */
  refused?: Extract<ProviderOutcome, { kind: "refused" }>;
  onSave: (secret: ProviderSecret) => void;
  onCancel: () => void;
}) {
  const t = useStrings();
  const secretId = useId();
  const addressId = useId();
  const secret = useRef<HTMLInputElement>(null);
  const [filled, setFilled] = useState(false);
  const gateway = provider.authKind === "api_key_with_base_url";
  // A gateway without a default address needs one written.
  const needsAddress = gateway && !provider.defaultBaseUrl;
  const [address, setAddress] = useState(provider.baseUrl ?? "");
  const held = !filled || (needsAddress && address.trim() === "") || saving;
  const defaults = provider.defaultBaseUrl
    ? [{ value: provider.defaultBaseUrl, label: provider.defaultBaseUrl }]
    : null;

  const save = (event: FormEvent) => {
    event.preventDefault();
    const value = secret.current?.value.trim() ?? "";
    if (held || value === "") return;
    onSave({
      secret: value,
      ...(gateway ? { baseUrl: address.trim() } : {}),
    });
  };

  return (
    <form className="grid gap-3" onSubmit={save}>
      <Field>
        <FieldLabel htmlFor={secretId}>
          {t("desktop.providers.key_label", { provider: provider.name })}
        </FieldLabel>
        <Input
          ref={secret}
          id={secretId}
          type="password"
          autoComplete="new-password"
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          onInput={(event) =>
            setFilled(event.currentTarget.value.trim() !== "")
          }
        />
        <FieldDescription>{t("desktop.providers.key_note")}</FieldDescription>
      </Field>
      {gateway && (
        <Field>
          <FieldLabel htmlFor={addressId}>
            {t("desktop.providers.base_url_label")}
          </FieldLabel>
          <TextEditor
            id={addressId}
            type="url"
            inputMode="url"
            value={address}
            onChange={setAddress}
            required={needsAddress}
            suggestions={defaults}
            opensEmpty
          />
          <FieldDescription>
            {provider.defaultBaseUrl
              ? t("desktop.providers.base_url_default", {
                  url: provider.defaultBaseUrl,
                })
              : t("desktop.providers.base_url_required")}
          </FieldDescription>
        </Field>
      )}
      {refused && <Refusal outcome={refused} provider={provider.provider} />}
      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>
          {t("desktop.providers.cancel")}
        </Button>
        <Button type="submit" variant="primary" size="sm" disabled={held}>
          {saving
            ? t("desktop.providers.saving")
            : refused
              ? t("desktop.providers.save_retry")
              : t("desktop.providers.save")}
        </Button>
      </div>
    </form>
  );
}

/**
 * One connection of a provider, on one row: its provider's mark and name
 * with the way it connects, one status word, whether a conversation on it
 * leaves this computer, the one thing to do about it where there is one, and
 * the switch that turns it on or off for the agent. The reason for its
 * status, its key, address, sign-in and models are behind its expander.
 */
function LaneRow({
  provider,
  hidden = false,
  busy,
  outcome,
  onSave,
  onTurnOff,
  onTurnOn,
  onReset,
  onRefresh,
  signInSupported,
  readsPending,
  onSignIn,
  onSignOut,
  consoleSignInCommand,
  models,
  engine,
  setup,
}: {
  provider: ProviderStatus;
  hidden?: boolean;
  busy: boolean;
  outcome?: ProviderOutcome;
  onSave: (secret: ProviderSecret) => void;
  onTurnOff: () => void;
  onTurnOn: () => void;
  onReset: () => void;
  onRefresh: () => void;
  signInSupported: boolean;
  /** The service is still reading the sign-in methods behind its answer. */
  readsPending: boolean;
  onSignIn: () => void;
  /** Signs the lane out, where the host offers it. */
  onSignOut?: () => void;
  /** The served console command template, with its `{provider}` slot. */
  consoleSignInCommand?: string;
  /** The models of a keyless lane on this computer, shown while it is on. */
  models?: ReactNode;
  /** What the service measured of the lane's local engine, where it did. */
  engine: AgentEngineHealth | null;
  /** The setup row of the local AI that runs this lane's engine, where it has one. */
  setup: SetupRow | null;
}) {
  const t = useStrings();
  const headingId = useId();
  const bodyId = useId();
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  // A save the form handed on: once its answer comes, the form closes,
  // unless the agent was starting, when it stays open with what was typed.
  const [saving, setSaving] = useState(false);
  const [wasBusy, setWasBusy] = useState(busy);
  if (wasBusy !== busy) {
    setWasBusy(busy);
    if (wasBusy && saving) {
      setSaving(false);
      if (!agentStarting(outcome)) setEditing(false);
    }
  }
  const signInOnly = provider.authKind === "provider_sign_in_only";
  const keyless = provider.authKind === "none";
  const keyed = !signInOnly && !keyless;
  const hasKey = provider.mode === "key" || provider.mode === "oauth_token";
  const off = provider.mode === "disabled";
  // Where a sign-in-only lane's sign-in stands: offered, still being read, or
  // unavailable by a complete answer.
  const signInState = !signInOnly
    ? undefined
    : signInSupported
      ? "offered"
      : readsPending
        ? "pending"
        : "unavailable";
  const { status, reason } = laneStatus(
    provider,
    engine,
    setup ? setup.state === "ready" : null,
  );
  const reasonLine = reasonWords(t, reason, provider, engine, setup);
  const connection = connectionWords(t, provider);
  // A keyless lane runs against the server on this computer that Cadrumo
  // launches the agent with, not the address the agent declares by default,
  // so no address is shown for it.
  const address =
    provider.authKind === "api_key_with_base_url"
      ? (provider.baseUrl ?? provider.defaultBaseUrl)
      : undefined;
  const addKey = () => {
    setExpanded(true);
    setEditing(true);
  };
  const formRefusal =
    editing && outcome?.kind === "refused" && agentStarting(outcome)
      ? outcome
      : undefined;
  const leaves = provider.readsOffHost;
  // The one thing to do about the lane, where there is one.
  const action =
    off || busy ? null : status === "sign_in_needed" &&
      signInState === "offered" ? (
      <Button variant="outline" size="xs" onClick={onSignIn}>
        {t("desktop.providers.sign_in_action")}
      </Button>
    ) : status === "signed_in" && provider.signOutAvailable && onSignOut ? (
      <Button
        variant="outline"
        size="xs"
        aria-label={t("desktop.providers.sign_out_label", {
          provider: provider.name,
        })}
        onClick={onSignOut}
      >
        {t("desktop.providers.sign_out_action")}
      </Button>
    ) : keyed && !hasKey && !editing ? (
      <Button variant="outline" size="xs" onClick={addKey}>
        {t("desktop.providers.add_key")}
      </Button>
    ) : status === "engine_not_running" && engine?.state === "not_running" ? (
      <EngineDoor door={engine.door} />
    ) : null;
  return (
    <li
      data-provider={provider.provider}
      data-lane={provider.id}
      data-transport={provider.transport}
      data-auth-kind={provider.authKind}
      data-sign-in={signInState}
      data-reads-off-host={leaves === undefined ? undefined : String(leaves)}
      hidden={hidden}
      aria-labelledby={headingId}
      className={cn("rounded-lg bg-card", hidden ? "hidden" : "grid")}
    >
      <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-2 gap-y-1 px-3 py-2">
        <ProviderMark provider={provider.provider} size="md" />
        <div className="grid min-w-0 gap-0.5">
          <h4
            id={headingId}
            className="min-w-0 font-medium wrap-anywhere text-foreground"
          >
            {provider.name}
            <span className="font-normal text-muted-foreground">
              {" · "}
              {connection}
            </span>
          </h4>
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <span
              data-slot="provider-status"
              data-status={status}
              data-reason={reason}
              className={STATUS_TONE[status]}
            >
              {statusWords(t, status, provider)}
            </span>
            {leaves !== undefined && (
              <span
                data-slot="reads-off-host"
                title={t(
                  leaves
                    ? "desktop.providers.reads_off_host"
                    : "desktop.providers.reads_on_host",
                )}
                className="inline-flex text-muted-foreground"
              >
                <Icon name={leaves ? "globe" : "home"} />
                <span className="sr-only">
                  {t(
                    leaves
                      ? "desktop.providers.reads_off_host"
                      : "desktop.providers.reads_on_host",
                  )}
                </span>
              </span>
            )}
            {busy && (
              <span className="text-muted-foreground">
                {t("desktop.providers.saving")}
              </span>
            )}
            {action}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Switch
            checked={!off}
            disabled={busy}
            aria-label={t("desktop.providers.use_in_agent", {
              provider: provider.name,
              connection,
            })}
            onCheckedChange={(on) => (on ? onTurnOn() : onTurnOff())}
          />
          <Button
            variant="ghost"
            size="icon-sm"
            data-slot="lane-expander"
            aria-expanded={expanded}
            aria-controls={bodyId}
            aria-label={t("desktop.providers.lane_details", {
              provider: provider.name,
              connection,
            })}
            onClick={() => setExpanded((open) => !open)}
          >
            <Icon
              name="chevronDown"
              className={cn("transition-transform", expanded && "rotate-180")}
            />
          </Button>
        </div>
      </div>
      {outcome?.kind === "saved_unread" && (
        <p
          role="status"
          className="flex flex-wrap items-center gap-2 px-3 pb-2 text-sm text-foreground"
        >
          <Icon name="info" className="text-muted-foreground" />
          <span className="flex-1">{t("desktop.providers.saved_unread")}</span>
          <Button variant="outline" size="xs" onClick={onRefresh}>
            {t("desktop.providers.refresh")}
          </Button>
        </p>
      )}
      {outcome?.kind === "refused" && !formRefusal && (
        <div className="px-3 pb-2">
          <Refusal outcome={outcome} provider={provider.provider} />
        </div>
      )}
      {/* A collapsed row lays out nothing of its details; the row keeps
          whether its key form is open. */}
      {expanded && (
        <div
          id={bodyId}
          data-slot="lane-details"
          className="grid gap-3 border-t border-border px-3 py-3"
        >
          {reasonLine && (
            <p data-slot="lane-reason" className="text-sm text-foreground">
              {reasonLine}
            </p>
          )}
          {(reason === "app_unconfirmed" || reason === "app_missing") && (
            <SignInAdvice
              causes={[provider.cliStateCause]}
              step={provider.nextStep}
              command={consoleSignInCommand}
              provider={provider.provider}
            />
          )}
          {address && !off && (
            <p className="text-sm text-muted-foreground wrap-anywhere">
              {t("desktop.providers.address", { url: address })}
            </p>
          )}
          {!off && signInOnly && status !== "signed_in" && (
            <>
              {signInState === "pending" && (
                <p role="status" className="text-sm text-muted-foreground">
                  {t("desktop.providers.sign_in_checking")}
                </p>
              )}
              {signInState === "unavailable" && (
                <p role="note" className="text-sm text-muted-foreground">
                  {t("desktop.providers.sign_in_unavailable", {
                    provider: provider.name,
                  })}
                </p>
              )}
            </>
          )}
          {!off &&
            keyed &&
            (editing ? (
              <SecretForm
                provider={provider}
                saving={busy}
                {...(formRefusal ? { refused: formRefusal } : {})}
                onSave={(secret) => {
                  setSaving(true);
                  onSave(secret);
                }}
                onCancel={() => {
                  setSaving(false);
                  setEditing(false);
                }}
              />
            ) : (
              hasKey && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={addKey}
                  >
                    {t("desktop.providers.replace_key")}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={busy}
                    onClick={onReset}
                  >
                    {t("desktop.providers.remove_key")}
                  </Button>
                </div>
              )
            ))}
          {!off && keyless && models}
        </div>
      )}
    </li>
  );
}

/**
 * The AI providers of the signed-in profile, one row for each connection the
 * agent has, in the agent's order with each provider's API before its app:
 * named and drawn as the agent's provider list names and draws it, with one
 * status, the one thing to do about it, and the person's way to set an API
 * key or sign in. A stored key is never shown, and only these controls,
 * pressed by the person, change one.
 */
export function ProviderSettings({
  providers,
  busyId = null,
  outcomes = {},
  onSave,
  onTurnOff,
  onTurnOn,
  onReset,
  onSignOut,
  onRefresh,
  onSignInTerminal,
  signIn,
  signInProviders = [],
  signInMethods = {},
  revisions = {},
  readsPending = false,
  consoleSignInCommand,
  identity = null,
  localModels,
  lanes,
  query = "",
  embedded = false,
  onMatch,
}: {
  providers: readonly ProviderStatus[];
  /** The way whose change is on its way. */
  busyId?: string | null;
  /** How the last change to each way ended, by way id. */
  outcomes?: Readonly<Record<string, ProviderOutcome>>;
  onSave: (providerId: string, secret: ProviderSecret) => void;
  onTurnOff: (providerId: string) => void;
  onTurnOn: (providerId: string) => void;
  onReset: (providerId: string) => void;
  /** Signs a lane out, where the host offers it. */
  onSignOut?: (providerId: string) => void;
  onRefresh: () => void;
  /** Refreshes the lane after sign-in and returns its freshly read revision. */
  onSignInTerminal?: (
    providerId: string,
    identity: string | null,
  ) => Promise<string | undefined>;
  signIn?: ProviderSignIn;
  /** Canonical provider slugs declared by the agent as GUI sign-in capable. */
  signInProviders?: readonly string[];
  /** GUI sign-in methods the agent declares for each canonical provider. */
  signInMethods?: Readonly<
    Record<string, readonly ProviderSignInMethod[] | undefined>
  >;
  /** Current lane revisions from the same provider status read. */
  revisions?: Readonly<Record<string, string>>;
  /** The same read's `reads_pending`: the service still reads the sign-in
   * methods behind it. */
  readsPending?: boolean;
  /** The console command that signs a provider in by hand, with a
   * `{provider}` slot, as the service serves it. */
  consoleSignInCommand?: string;
  /** Signed-in profile identity, used to discard an open attempt on switch. */
  identity?: string | null;
  /** The model controls of a keyless lane, where the host offers them: a
   * lane on this computer has no key or sign-in, only its models. */
  localModels?: (lane: ProviderStatus) => ReactNode;
  /** What the agent offers of each lane, by lane id: what the service
   * measured of a local engine's lane among it. */
  lanes?: ReadonlyMap<string, OfferedLane>;
  query?: string;
  embedded?: boolean;
  onMatch?: (matches: boolean) => void;
}) {
  const t = useStrings();
  const titleId = useId();
  const [selection, setSelection] = useState<{
    laneId: string;
    identity: string | null;
  } | null>(null);
  const currentIdentity = useRef(identity);
  currentIdentity.current = identity;
  const refreshCurrent = useRef(onSignInTerminal);
  refreshCurrent.current = onSignInTerminal;
  const fallbackRefresh = useRef(onRefresh);
  fallbackRefresh.current = onRefresh;
  const selectedProvider =
    selection?.identity === identity
      ? providers.find((provider) => provider.id === selection.laneId)
      : undefined;
  const selectedIdentity = selection?.identity ?? null;
  const selectedRevision = selectedProvider
    ? revisions[selectedProvider.id]
    : undefined;
  const selectedMethods = selectedProvider
    ? (signInMethods[selectedProvider.provider] ?? [])
    : [];
  const engineOf = (lane: ProviderStatus) =>
    lane.authKind === "none" ? (lanes?.get(lane.id)?.engine ?? null) : null;
  // A lane whose engine runs on this computer is as ready as the local AI set
  // up to run it, which the setup row serves.
  const localAi = useProvisioning().localAiRow;
  const setupOf = (lane: ProviderStatus) => (engineOf(lane) ? localAi : null);
  const ordered = groupedByProvider(
    providers,
    (lane) => lane.provider,
    (lane) => lane.transport,
  ).flat();
  const laneMatches = (lane: ProviderStatus) =>
    offerMatches(
      [
        lane.name,
        connectionWords(t, lane),
        statusWords(
          t,
          laneStatus(
            lane,
            engineOf(lane),
            setupOf(lane) ? setupOf(lane)?.state === "ready" : null,
          ).status,
          lane,
        ),
      ],
      query,
    );
  const matches = ordered.some(laneMatches);
  useEffect(() => onMatch?.(matches), [matches, onMatch]);
  return (
    <section aria-labelledby={titleId} className="provider-settings grid gap-2">
      <h3
        id={titleId}
        className={embedded ? "sr-only" : "font-medium text-foreground"}
      >
        {t("desktop.providers.title")}
      </h3>
      <ul className="grid gap-2">
        {ordered.map((lane) => (
          <LaneRow
            // The local engine's lane is one row whichever engine serves it:
            // choosing the other engine, from inside its details, keeps the
            // row and its details open.
            key={engineOf(lane) ? "local-engine" : lane.id}
            provider={lane}
            engine={engineOf(lane)}
            setup={setupOf(lane)}
            hidden={!laneMatches(lane)}
            busy={busyId === lane.id}
            outcome={outcomes[lane.id]}
            signInSupported={Boolean(
              signIn?.openExternal &&
              revisions[lane.id] &&
              signInProviders.includes(lane.provider) &&
              (signInMethods[lane.provider]?.length ?? 0) > 0,
            )}
            readsPending={readsPending}
            onSignIn={() => setSelection({ laneId: lane.id, identity })}
            consoleSignInCommand={consoleSignInCommand}
            onSave={(secret) => onSave(lane.id, secret)}
            onTurnOff={() => onTurnOff(lane.id)}
            onTurnOn={() => onTurnOn(lane.id)}
            onReset={() => onReset(lane.id)}
            {...(onSignOut ? { onSignOut: () => onSignOut(lane.id) } : {})}
            onRefresh={onRefresh}
            models={lane.authKind === "none" ? localModels?.(lane) : undefined}
          />
        ))}
      </ul>
      <details className="text-sm text-muted-foreground">
        <summary className="w-fit cursor-pointer rounded-sm py-1 outline-none focus-visible:ring-2 focus-visible:ring-ring">
          {t("desktop.providers.icon_credits")}
        </summary>
        <div className="grid gap-1 pt-1">
          <p>{iconArtwork.attribution.title}</p>
          <p>{iconArtwork.attribution.licence}</p>
          <p>{iconArtwork.attribution.notice}</p>
          <p>{iconArtwork.attribution.trademarks}</p>
        </div>
      </details>
      {selectedProvider && selectedRevision && signIn?.openExternal && (
        <ProviderSignInDialog
          open
          identity={identity}
          provider={selectedProvider}
          revision={selectedRevision}
          signIn={signIn}
          methods={selectedMethods}
          consoleSignInCommand={consoleSignInCommand}
          onOpenChange={(open) => {
            if (!open) setSelection(null);
          }}
          onTerminal={(providerId) => {
            if (
              currentIdentity.current !== selectedIdentity ||
              providerId !== selectedProvider.id
            )
              return Promise.resolve(undefined);
            const refresh = refreshCurrent.current;
            if (!refresh) {
              fallbackRefresh.current();
              return Promise.resolve(undefined);
            }
            return Promise.resolve()
              .then(() => refresh(providerId, selectedIdentity))
              .then((freshRevision) =>
                currentIdentity.current === selectedIdentity
                  ? freshRevision
                  : undefined,
              );
          }}
        />
      )}
    </section>
  );
}
