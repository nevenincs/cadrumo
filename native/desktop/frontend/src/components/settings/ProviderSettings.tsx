import { useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import iconArtwork from "virtual:desktop-provider-icons";
import { useStrings, type Translate } from "../../shell/strings";
import { ProviderMark } from "../agent/ProviderMark";
import { ProviderSignInDialog } from "./ProviderSignInDialog";
import type {
  ProviderSignIn,
  ProviderSignInMethod,
} from "../../shell/providerSettings";
import type { ProviderOutcome, ProviderSecret, ProviderStatus } from "./types";

/** One status for a connection, in the same words wherever it is shown. */
type ConnectionStatus =
  "ready" | "saved" | "not_checked" | "setup_needed" | "sign_in_needed" | "off";

/** Describe what is set, without claiming more than the reading says. */
function connectionStatus(provider: ProviderStatus): ConnectionStatus {
  if (provider.reason === "record_unreadable") return "setup_needed";
  if (provider.mode === "disabled") return "off";
  if (provider.readiness === "unusable") return "setup_needed";
  // An app connection needs its app, whatever it signs in with.
  if (provider.cliState === "not_installed") return "setup_needed";
  if (provider.authKind === "provider_sign_in_only") {
    if (
      provider.cliState === "installed_signed_in" ||
      provider.readiness === "ready"
    )
      return "ready";
    if (
      provider.cliState === "installed_signed_out" ||
      provider.readiness === "sign_in_required"
    )
      return "sign_in_needed";
    return "not_checked";
  }
  if (provider.readiness === "ready") return "ready";
  if (provider.readiness === "sign_in_required") return "sign_in_needed";
  if (
    provider.mode === "key" ||
    provider.mode === "oauth_token" ||
    provider.source !== "none"
  )
    return "saved";
  return "setup_needed";
}

const STATUS_WORDS = {
  ready: "desktop.providers.status_ready",
  saved: "desktop.providers.status_saved",
  not_checked: "desktop.providers.status_not_checked",
  setup_needed: "desktop.providers.status_setup_needed",
  sign_in_needed: "desktop.providers.status_sign_in_needed",
  off: "desktop.providers.status_off",
} as const satisfies Record<ConnectionStatus, string>;

function statusWords(t: Translate, status: ConnectionStatus): string {
  return t(STATUS_WORDS[status]);
}

/** Only a connection the agent can use stands out; one that is not set up,
 * not signed in or off is said quietly, since nothing is wrong with it. */
function statusVariant(status: ConnectionStatus): "success" | "neutral" {
  return status === "ready" ? "success" : "neutral";
}

function connectionWords(
  t: Translate,
  transport: ProviderStatus["transport"],
): string {
  return transport === "api"
    ? t("desktop.providers.connection_api")
    : t("desktop.providers.connection_app");
}

/** Why a change was not made, in words where it is a refusal we know. */
function refusalWords(t: Translate, code: string): string {
  switch (code) {
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
    default:
      return t("desktop.providers.change_failed");
  }
}

/** The one line that says what to do about a connection, or null where its
 * status already says it all. */
function detailWords(t: Translate, provider: ProviderStatus): string | null {
  const status = connectionStatus(provider);
  if (status === "off")
    return provider.credentialSaved
      ? t("desktop.providers.detail_off_kept")
      : t("desktop.providers.detail_off");
  if (provider.reason === "record_unreadable")
    return t("desktop.providers.reason_record_unreadable");
  if (provider.cliState === "not_installed")
    return t("desktop.providers.detail_app_missing", {
      provider: provider.name,
    });
  if (provider.authKind === "provider_sign_in_only") {
    if (status === "setup_needed")
      return t("desktop.providers.reason_check_settings");
    if (status === "sign_in_needed")
      return t("desktop.providers.detail_sign_in", { provider: provider.name });
    return null;
  }
  switch (provider.reason) {
    case undefined:
    case "turned_off":
    case "not_configured":
    case "sign_in_with_provider_tool":
      break;
    default:
      return refusalWords(t, provider.reason);
  }
  if (status === "setup_needed" && provider.readiness === "unusable")
    return t("desktop.providers.reason_check_settings");
  if (status === "sign_in_needed")
    return t("desktop.providers.detail_sign_in", { provider: provider.name });
  return null;
}

/**
 * Where a key or token is written to be saved. The field is the only place
 * the secret ever is: it is not kept as the field changes, only whether it
 * holds anything is. Saving reads it once, empties it and hands the secret
 * on; nothing here can show a stored one, and the field has no placeholder
 * that could be taken for a key.
 */
function SecretForm({
  provider,
  saving,
  onSave,
  onCancel,
}: {
  provider: ProviderStatus;
  saving: boolean;
  onSave: (secret: ProviderSecret) => void;
  onCancel: () => void;
}) {
  const t = useStrings();
  const secretId = useId();
  const addressId = useId();
  const secret = useRef<HTMLInputElement>(null);
  const address = useRef<HTMLInputElement>(null);
  const [filled, setFilled] = useState(false);
  const gateway = provider.authKind === "api_key_with_base_url";
  // A gateway without a default address needs one written.
  const needsAddress = gateway && !provider.defaultBaseUrl;
  const [addressFilled, setAddressFilled] = useState(Boolean(provider.baseUrl));
  const held = !filled || (needsAddress && !addressFilled) || saving;

  const save = (event: FormEvent) => {
    event.preventDefault();
    const field = secret.current;
    if (!field || held) return;
    const value = field.value.trim();
    field.value = "";
    setFilled(false);
    if (value === "") return;
    onSave({
      secret: value,
      ...(gateway ? { baseUrl: address.current?.value.trim() ?? "" } : {}),
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
          autoComplete="off"
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
          <Input
            ref={address}
            id={addressId}
            type="url"
            inputMode="url"
            spellCheck={false}
            defaultValue={provider.baseUrl ?? ""}
            aria-required={needsAddress}
            onInput={(event) =>
              setAddressFilled(event.currentTarget.value.trim() !== "")
            }
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
      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>
          {t("desktop.providers.cancel")}
        </Button>
        <Button type="submit" variant="primary" size="sm" disabled={held}>
          {saving ? t("desktop.providers.saving") : t("desktop.providers.save")}
        </Button>
      </div>
    </form>
  );
}

/**
 * One connection of a provider. Its header says where it stands and holds the
 * one switch that turns it on or off for the agent, the same for every
 * connection; setting it up (a key, or a sign-in) is a row of its own below,
 * offered while it is on.
 */
function WayRow({
  provider,
  busy,
  outcome,
  onSave,
  onTurnOff,
  onTurnOn,
  onReset,
  onRefresh,
  signInSupported,
  onSignIn,
}: {
  provider: ProviderStatus;
  busy: boolean;
  outcome?: ProviderOutcome;
  onSave: (secret: ProviderSecret) => void;
  onTurnOff: () => void;
  onTurnOn: () => void;
  onReset: () => void;
  onRefresh: () => void;
  signInSupported: boolean;
  onSignIn: () => void;
}) {
  const t = useStrings();
  const headingId = useId();
  const [editing, setEditing] = useState(false);
  const signInOnly = provider.authKind === "provider_sign_in_only";
  const hasKey = provider.mode === "key" || provider.mode === "oauth_token";
  const off = provider.mode === "disabled";
  const state = connectionStatus(provider);
  const detail = detailWords(t, provider);
  const connection = connectionWords(t, provider.transport);
  const address =
    provider.authKind === "api_key_with_base_url"
      ? (provider.baseUrl ?? provider.defaultBaseUrl)
      : undefined;
  return (
    <li
      data-lane={provider.id}
      aria-labelledby={headingId}
      className="way grid gap-2 rounded-lg border bg-card p-3"
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <h5
            id={headingId}
            className="min-w-0 font-medium wrap-anywhere text-foreground"
          >
            {connection}
          </h5>
          <Badge variant={statusVariant(state)}>{statusWords(t, state)}</Badge>
          {busy && (
            <span className="text-sm text-muted-foreground">
              {t("desktop.providers.saving")}
            </span>
          )}
        </div>
        <Switch
          checked={!off}
          disabled={busy}
          aria-label={t("desktop.providers.use_in_agent", {
            provider: provider.name,
            connection,
          })}
          onCheckedChange={(on) => (on ? onTurnOn() : onTurnOff())}
        />
      </div>
      {detail && <p className="text-sm text-foreground">{detail}</p>}
      {address && !off && (
        <p className="text-sm text-muted-foreground wrap-anywhere">
          {t("desktop.providers.address", { url: address })}
        </p>
      )}
      {outcome?.kind === "saved_unread" && (
        <p
          role="status"
          className="flex flex-wrap items-center gap-2 text-sm text-foreground"
        >
          <Icon name="info" className="text-muted-foreground" />
          <span className="flex-1">{t("desktop.providers.saved_unread")}</span>
          <Button variant="outline" size="xs" onClick={onRefresh}>
            {t("desktop.providers.refresh")}
          </Button>
        </p>
      )}
      {outcome?.kind === "refused" && (
        <p role="alert" className="flex items-start gap-2 text-sm">
          <Icon name="alert" className="mt-0.5 text-destructive" />
          <span>{refusalWords(t, outcome.code)}</span>
        </p>
      )}
      {!off && (
        <div className="grid gap-2 border-t pt-2">
          {signInOnly ? (
            signInSupported ? (
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={onSignIn}>
                  {t("desktop.providers.sign_in_action")}
                </Button>
              </div>
            ) : (
              <p role="note" className="text-sm text-muted-foreground">
                {t("desktop.providers.sign_in_unavailable", {
                  provider: provider.name,
                })}
              </p>
            )
          ) : editing ? (
            <SecretForm
              provider={provider}
              saving={busy}
              onSave={(secret) => {
                onSave(secret);
                setEditing(false);
              }}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => setEditing(true)}
              >
                {hasKey
                  ? t("desktop.providers.replace_key")
                  : t("desktop.providers.add_key")}
              </Button>
              {hasKey && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  onClick={onReset}
                >
                  {t("desktop.providers.remove_key")}
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </li>
  );
}

type ProviderGroup = {
  provider: string;
  name: string;
  lanes: ProviderStatus[];
};

/** Keep each provider's API and app connections together, but independent. */
function providerGroups(providers: readonly ProviderStatus[]): ProviderGroup[] {
  const groups = new Map<string, ProviderGroup>();
  for (const lane of inListOrder(providers)) {
    const group = groups.get(lane.provider);
    if (group) group.lanes.push(lane);
    else
      groups.set(lane.provider, {
        provider: lane.provider,
        name: lane.name,
        lanes: [lane],
      });
  }
  return [...groups.values()];
}

function ProviderGroupRow({
  group,
  t,
  renderLane,
}: {
  group: ProviderGroup;
  t: Translate;
  renderLane: (lane: ProviderStatus) => ReactNode;
}) {
  return (
    <li data-provider={group.provider} className="rounded-lg border bg-card">
      <details className="group/provider">
        <summary className="flex min-h-control-lg cursor-pointer list-none flex-wrap items-center gap-x-2 gap-y-2 rounded-lg px-3 py-2.5 outline-none hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
          <span className="flex min-w-0 flex-1 items-center gap-2">
            <ProviderMark provider={group.provider} size="md" />
            <h4 className="min-w-0 flex-1 font-medium break-words text-foreground">
              {group.name}
            </h4>
          </span>
          <Icon
            name="chevronDown"
            className="shrink-0 text-faint transition-transform group-open/provider:rotate-180"
          />
          <span className="flex w-full basis-full flex-wrap gap-1.5">
            {group.lanes.map((lane) => {
              const state = connectionStatus(lane);
              return (
                <Badge key={lane.id} variant={statusVariant(state)}>
                  {t("desktop.providers.summary", {
                    connection: connectionWords(t, lane.transport),
                    status: statusWords(t, state),
                  })}
                </Badge>
              );
            })}
          </span>
        </summary>
        <ul className="grid gap-2 px-2 pb-2">{group.lanes.map(renderLane)}</ul>
      </details>
    </li>
  );
}

/** The lanes with a provider's lanes together, in the order the provider's
 * first lane was served, its API lane before the other. */
function inListOrder(providers: readonly ProviderStatus[]) {
  const groups = new Map<string, ProviderStatus[]>();
  for (const lane of providers)
    groups.set(lane.provider, [...(groups.get(lane.provider) ?? []), lane]);
  return [...groups.values()].flatMap((lanes) =>
    [...lanes].sort(
      (a, b) => Number(a.transport === "cli") - Number(b.transport === "cli"),
    ),
  );
}

/**
 * The AI providers of the signed-in profile, one card for each connection the
 * agent has: named and drawn as the agent's provider list names and draws it,
 * with one status, the one thing to do about it, and the person's way to set
 * an API key or sign in. A stored key is never shown, and only these
 * controls, pressed by the person, change one.
 */
export function ProviderSettings({
  providers,
  busyId = null,
  outcomes = {},
  onSave,
  onTurnOff,
  onTurnOn,
  onReset,
  onRefresh,
  onSignInTerminal,
  signIn,
  signInProviders = [],
  signInMethods = {},
  revisions = {},
  identity = null,
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
  /** Signed-in profile identity, used to discard an open attempt on switch. */
  identity?: string | null;
}) {
  const t = useStrings();
  const titleId = useId();
  const searchId = useId();
  const [query, setQuery] = useState("");
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
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const visibleGroups = providerGroups(providers)
    .map((group) => ({
      ...group,
      lanes: group.lanes.filter((lane) => {
        if (!normalizedQuery) return true;
        const searchable = [
          group.name,
          connectionWords(t, lane.transport),
          statusWords(t, connectionStatus(lane)),
        ]
          .join(" ")
          .toLocaleLowerCase();
        return searchable.includes(normalizedQuery);
      }),
    }))
    .filter((group) => group.lanes.length > 0);
  return (
    <section aria-labelledby={titleId} className="provider-settings grid gap-2">
      <div className="grid gap-1">
        <h3 id={titleId} className="font-medium text-foreground">
          {t("desktop.providers.title")}
        </h3>
        <p className="text-sm text-muted-foreground">
          {t("desktop.providers.group_intro")}
        </p>
      </div>
      <Field>
        <FieldLabel htmlFor={searchId}>
          {t("desktop.providers.search_label")}
        </FieldLabel>
        <Input
          id={searchId}
          type="search"
          value={query}
          placeholder={t("desktop.providers.search_placeholder")}
          onChange={(event) => setQuery(event.currentTarget.value)}
        />
      </Field>
      <ul className="grid gap-2">
        {visibleGroups.map((group) => (
          <ProviderGroupRow
            key={group.provider}
            group={group}
            t={t}
            renderLane={(lane) => (
              <WayRow
                key={lane.id}
                provider={lane}
                busy={busyId === lane.id}
                outcome={outcomes[lane.id]}
                signInSupported={Boolean(
                  signIn?.openExternal &&
                  revisions[lane.id] &&
                  signInProviders.includes(lane.provider) &&
                  (signInMethods[lane.provider]?.length ?? 0) > 0,
                )}
                onSignIn={() => setSelection({ laneId: lane.id, identity })}
                onSave={(secret) => onSave(lane.id, secret)}
                onTurnOff={() => onTurnOff(lane.id)}
                onTurnOn={() => onTurnOn(lane.id)}
                onReset={() => onReset(lane.id)}
                onRefresh={onRefresh}
              />
            )}
          />
        ))}
      </ul>
      {visibleGroups.length === 0 && (
        <p
          role="status"
          className="rounded-lg border p-3 text-sm text-muted-foreground"
        >
          {t("desktop.providers.search_empty")}
        </p>
      )}
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
              )
              .catch(() => undefined);
          }}
        />
      )}
    </section>
  );
}
