import { useId, useRef, useState, type FormEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { useStrings, type Translate } from "../../shell/strings";
import type {
  ProviderConsumer,
  ProviderOutcome,
  ProviderReadiness,
  ProviderSecret,
  ProviderStatus,
} from "./types";

const READINESS_LOOK: Record<
  ProviderReadiness,
  "success" | "neutral" | "warning" | "danger"
> = {
  ready: "success",
  not_verified: "neutral",
  missing: "neutral",
  disabled: "neutral",
  sign_in_required: "warning",
  unusable: "danger",
};

function readinessWords(t: Translate, readiness: ProviderReadiness): string {
  switch (readiness) {
    case "ready":
      return t("desktop.providers.readiness_ready");
    case "not_verified":
      return t("desktop.providers.readiness_not_verified");
    case "missing":
      return t("desktop.providers.readiness_missing");
    case "disabled":
      return t("desktop.providers.readiness_disabled");
    case "sign_in_required":
      return t("desktop.providers.readiness_sign_in_required");
    case "unusable":
      return t("desktop.providers.readiness_unusable");
  }
}

function consumerWords(t: Translate, consumer: ProviderConsumer): string {
  return consumer === "assistant"
    ? t("desktop.providers.consumer_assistant")
    : t("desktop.providers.consumer_extraction");
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
    case "person_act_required":
      return t("desktop.providers.refused_person_act_required");
    default:
      return t("desktop.messages.failed", { code });
  }
}

/** Why a provider is not ready, in words; null where its standing already
 * says it. */
function reasonWords(t: Translate, provider: ProviderStatus): string | null {
  switch (provider.reason) {
    case undefined:
    case "turned_off":
      return null;
    case "not_configured":
      return t("desktop.providers.reason_not_configured");
    case "sign_in_with_provider_tool":
      return t("desktop.providers.reason_sign_in_with_provider_tool", {
        provider: provider.name,
      });
    case "record_unreadable":
      return t("desktop.providers.reason_record_unreadable");
    default:
      return refusalWords(t, provider.reason);
  }
}

/** Where the provider's credential stands, in a sentence; null when the
 * readiness alone says it. */
function standing(t: Translate, provider: ProviderStatus): string | null {
  const { name } = provider;
  if (provider.authKind === "provider_sign_in_only")
    return t("desktop.providers.sign_in_only", { provider: name });
  if (provider.mode === "disabled") return t("desktop.providers.disabled");
  if (provider.mode === "provider_sign_in")
    return t("desktop.providers.mode_provider_sign_in", { provider: name });
  if (provider.mode === "oauth_token") return t("desktop.providers.mode_token");
  if (provider.source === "profile")
    return t("desktop.providers.source_profile");
  if (provider.source === "environment")
    return t("desktop.providers.source_environment");
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
  const token = provider.authKind === "oauth_token_or_provider_sign_in";
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
          {token
            ? t("desktop.providers.token_label", { provider: provider.name })
            : t("desktop.providers.key_label", { provider: provider.name })}
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

function ProviderRow({
  provider,
  busy,
  outcome,
  onSave,
  onTurnOff,
  onReset,
  onRefresh,
}: {
  provider: ProviderStatus;
  busy: boolean;
  outcome?: ProviderOutcome;
  onSave: (secret: ProviderSecret) => void;
  onTurnOff: () => void;
  onReset: () => void;
  onRefresh: () => void;
}) {
  const t = useStrings();
  const nameId = useId();
  const [editing, setEditing] = useState(false);
  const signInOnly = provider.authKind === "provider_sign_in_only";
  const token = provider.authKind === "oauth_token_or_provider_sign_in";
  const secretAction =
    provider.mode === "key" || provider.mode === "oauth_token"
      ? token
        ? t("desktop.providers.replace_token")
        : t("desktop.providers.replace_key")
      : token
        ? t("desktop.providers.add_token")
        : t("desktop.providers.add_key");
  const sentence = standing(t, provider);
  const why = reasonWords(t, provider);
  const address =
    provider.authKind === "api_key_with_base_url"
      ? (provider.baseUrl ?? provider.defaultBaseUrl)
      : undefined;
  return (
    <li
      aria-labelledby={nameId}
      className="provider grid gap-2 border-b py-3 last:border-b-0"
    >
      <div className="flex min-w-0 items-start justify-between gap-2">
        <div className="grid min-w-0 gap-0.5">
          <h4 id={nameId} className="font-medium text-foreground">
            {provider.name}
            <span className="ml-1.5 font-normal text-muted-foreground">
              {provider.transport === "api"
                ? t("desktop.providers.transport_api")
                : t("desktop.providers.transport_cli")}
            </span>
          </h4>
          <p className="text-xs text-muted-foreground">
            {provider.consumers
              .map((consumer) => consumerWords(t, consumer))
              .join(" · ")}
          </p>
        </div>
        <Badge variant={READINESS_LOOK[provider.readiness]}>
          {readinessWords(t, provider.readiness)}
        </Badge>
      </div>
      {sentence && <p className="text-sm text-muted-foreground">{sentence}</p>}
      {why && <p className="text-sm text-foreground">{why}</p>}
      {address && (
        <p className="text-sm text-muted-foreground wrap-anywhere">
          {t("desktop.providers.through", { url: address })}
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
      {signInOnly ? null : editing ? (
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
            {secretAction}
          </Button>
          {provider.mode !== "disabled" && (
            <Button
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={onTurnOff}
            >
              {t("desktop.providers.disable")}
            </Button>
          )}
          {provider.mode !== "unset" && (
            <Button variant="ghost" size="sm" disabled={busy} onClick={onReset}>
              {t("desktop.providers.reset")}
            </Button>
          )}
        </div>
      )}
    </li>
  );
}

/**
 * The AI providers of the signed-in profile: for each, what uses it and
 * where it stands, and the person's ways to add, replace, turn off or reset
 * its key. A stored key is never shown, and only these controls, pressed by
 * the person, change one.
 */
export function ProviderSettings({
  providers,
  development,
  busyId = null,
  outcomes = {},
  onSave,
  onTurnOff,
  onReset,
  onRefresh,
}: {
  providers: readonly ProviderStatus[];
  /** A development build, where a provider with no key uses the
   * environment's. */
  development: boolean;
  /** The provider whose change is on its way. */
  busyId?: string | null;
  /** How the last change to each provider ended, by provider id. */
  outcomes?: Readonly<Record<string, ProviderOutcome>>;
  onSave: (providerId: string, secret: ProviderSecret) => void;
  onTurnOff: (providerId: string) => void;
  onReset: (providerId: string) => void;
  onRefresh: () => void;
}) {
  const t = useStrings();
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className="provider-settings grid gap-2">
      <div className="grid gap-1">
        <h3 id={titleId} className="font-medium text-foreground">
          {t("desktop.providers.title")}
        </h3>
        <p className="text-sm text-muted-foreground">
          {t("desktop.providers.lead")}
        </p>
        {development && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.providers.development_note")}
          </p>
        )}
        <p className="text-sm text-muted-foreground">
          {t("desktop.providers.disable_note")}{" "}
          {development
            ? t("desktop.providers.reset_note_development")
            : t("desktop.providers.reset_note")}
        </p>
      </div>
      <ul className="grid">
        {providers.map((provider) => (
          <ProviderRow
            key={provider.id}
            provider={provider}
            busy={busyId === provider.id}
            outcome={outcomes[provider.id]}
            onSave={(secret) => onSave(provider.id, secret)}
            onTurnOff={() => onTurnOff(provider.id)}
            onReset={() => onReset(provider.id)}
            onRefresh={onRefresh}
          />
        ))}
      </ul>
    </section>
  );
}
