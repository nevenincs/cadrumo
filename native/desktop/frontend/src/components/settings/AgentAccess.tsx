import { useId, useState, type FormEvent } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { useStrings, type Translate } from "../../shell/strings";

// The keys the signed-in profile has issued to agents outside Cadrumo: AI
// agents that reach it through its MCP server. A key is a person's act to
// issue and to revoke, and nothing here can show one: the list says what each
// key may do and when it was used, and the one thing handed back when a key is
// issued is the reference the agent's launch configuration names it by.

/** Where a key stands now. `expired` is a time, the rest are the profile's. */
export type AgentCredentialStanding =
  "active" | "pending" | "suspended" | "revoked" | "expired";

/** What a key lets its agent see. */
export type AgentCredentialCategory =
  "profile_values" | "operation_metadata" | "tax_values";

export type AgentCredential = {
  /** What a revoke names. */
  id: string;
  standing: AgentCredentialStanding;
  /** When it became valid, which is when it was issued, as an ISO instant. */
  issuedAt: string;
  expiresAt: string;
  /** When it last let an agent in, if it ever has. */
  lastUsedAt?: string;
  categories: readonly AgentCredentialCategory[];
  /** It may run every operation an agent may, rather than a chosen few. */
  allOperations: boolean;
};

/** How the last revoke of a key ended, as the section says it. */
export type AgentCredentialOutcome =
  /** Revoked: it admits nothing, but its stored key is still being removed
   * from this computer. */
  { kind: "revoked_cleanup_pending" } | { kind: "refused"; code: string };

/** What a key just issued is named by. It is not the key, and it is not kept:
 * the section shows it until it is closed. */
export type IssuedKey = { reference: string };

/** What the person chose for a key. */
export type AgentKeyChoice = { taxValues: boolean };

const BADGE_LOOK: Record<
  AgentCredentialStanding,
  "success" | "neutral" | "warning" | "danger"
> = {
  active: "success",
  pending: "neutral",
  suspended: "warning",
  revoked: "neutral",
  expired: "neutral",
};

function standingWords(t: Translate, standing: AgentCredentialStanding) {
  switch (standing) {
    case "active":
      return t("desktop.automation_access.standing_active");
    case "pending":
      return t("desktop.automation_access.standing_pending");
    case "suspended":
      return t("desktop.automation_access.standing_suspended");
    case "revoked":
      return t("desktop.automation_access.standing_revoked");
    case "expired":
      return t("desktop.automation_access.standing_expired");
  }
}

function categoryWords(t: Translate, category: AgentCredentialCategory) {
  switch (category) {
    case "profile_values":
      return t("desktop.automation_access.scope_profile_values");
    case "operation_metadata":
      return t("desktop.automation_access.scope_operations_seen");
    case "tax_values":
      return t("desktop.automation_access.scope_tax_values");
  }
}

/** Why a change was not made, in words where it is a refusal we know. */
function refusalWords(t: Translate, code: string): string {
  switch (code) {
    case "not_signed_in":
      return t("desktop.automation_access.refused_not_signed_in");
    case "profile_locked":
      return t("desktop.automation_access.refused_profile_locked");
    case "not_found":
      return t("desktop.automation_access.refused_not_found");
    case "outcome_unknown":
      return t("desktop.automation_access.refused_outcome_unknown");
    case "person_act_required":
      return t("desktop.automation_access.refused_person_act_required");
    case "issue_unavailable":
      return t("desktop.agent.unavailable");
    default:
      return t("desktop.messages.failed", { code });
  }
}

/** A key has no name of its own, so it is told apart by the start of its id. */
const shortId = (id: string) => id.slice(0, 8);

/** An instant in the person's language, or null where it cannot be read. */
function when(locale: string, instant: string, time: boolean): string | null {
  const at = new Date(instant);
  if (!Number.isFinite(at.getTime())) return null;
  return new Intl.DateTimeFormat(
    locale,
    time
      ? { dateStyle: "medium", timeStyle: "short" }
      : { dateStyle: "medium" },
  ).format(at);
}

function Refusal({ children }: { children: string }) {
  return (
    <p role="alert" className="flex items-start gap-2 text-sm">
      <Icon name="alert" className="mt-0.5 text-destructive" />
      <span>{children}</span>
    </p>
  );
}

function CredentialRow({
  credential,
  locale,
  busy,
  outcome,
  onRevoke,
  onRefresh,
}: {
  credential: AgentCredential;
  locale: string;
  busy: boolean;
  outcome?: AgentCredentialOutcome;
  onRevoke: () => void;
  onRefresh: () => void;
}) {
  const t = useStrings();
  const nameId = useId();
  const [confirming, setConfirming] = useState(false);
  const issued = when(locale, credential.issuedAt, false);
  const expires = when(locale, credential.expiresAt, false);
  const used = credential.lastUsedAt
    ? when(locale, credential.lastUsedAt, true)
    : null;
  return (
    <li
      aria-labelledby={nameId}
      className="agent-key grid gap-2 border-b py-3 last:border-b-0"
    >
      <div className="flex min-w-0 items-start justify-between gap-2">
        <h4 id={nameId} className="font-medium text-foreground">
          {t("desktop.automation_access.key_title", {
            id: shortId(credential.id),
          })}
        </h4>
        <Badge variant={BADGE_LOOK[credential.standing]}>
          {standingWords(t, credential.standing)}
        </Badge>
      </div>
      <ul className="grid gap-0.5 text-sm text-muted-foreground">
        {credential.categories.map((category) => (
          <li key={category}>{categoryWords(t, category)}</li>
        ))}
        {!credential.categories.includes("tax_values") && (
          <li>{t("desktop.automation_access.scope_no_tax_values")}</li>
        )}
        <li>
          {credential.allOperations
            ? t("desktop.automation_access.scope_all_operations")
            : t("desktop.automation_access.scope_some_operations")}
        </li>
      </ul>
      <p className="text-sm text-muted-foreground">
        {[
          issued && t("desktop.automation_access.issued_on", { date: issued }),
          // A revoked key's own end is no longer what matters.
          expires &&
            credential.standing !== "revoked" &&
            t(
              credential.standing === "expired"
                ? "desktop.automation_access.expired_on"
                : "desktop.automation_access.expires_on",
              { date: expires },
            ),
          used
            ? t("desktop.automation_access.last_used", { date: used })
            : t("desktop.automation_access.never_used"),
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      {outcome?.kind === "revoked_cleanup_pending" && (
        <p
          role="status"
          className="flex flex-wrap items-center gap-2 text-sm text-foreground"
        >
          <Icon name="info" className="text-muted-foreground" />
          <span className="flex-1">
            {t("desktop.automation_access.cleanup_pending")}
          </span>
          <Button variant="outline" size="xs" onClick={onRefresh}>
            {t("desktop.automation_access.refresh")}
          </Button>
        </p>
      )}
      {outcome?.kind === "refused" && (
        <Refusal>{refusalWords(t, outcome.code)}</Refusal>
      )}
      {credential.standing === "revoked" ? null : confirming ? (
        <div className="grid gap-2">
          <p className="text-sm text-foreground">
            {t("desktop.automation_access.revoke_confirm")}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirming(false)}
            >
              {t("desktop.automation_access.cancel")}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                setConfirming(false);
                onRevoke();
              }}
            >
              {t("desktop.automation_access.revoke_confirm_action")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            pending={busy}
            onClick={() => setConfirming(true)}
          >
            {busy
              ? t("desktop.automation_access.revoking")
              : t("desktop.automation_access.revoke")}
          </Button>
        </div>
      )}
    </li>
  );
}

/**
 * What the person chooses for a key, and the one press that issues it. Issuing
 * is the signed-in person's own act: nothing is asked again, and no step
 * stands between the press and the key.
 */
function IssueForm({
  issuing,
  refusal,
  onIssue,
  onRefresh,
}: {
  issuing: boolean;
  refusal: string | null;
  onIssue: (choice: AgentKeyChoice) => void;
  onRefresh: () => void;
}) {
  const t = useStrings();
  const taxId = useId();
  const [taxValues, setTaxValues] = useState(false);

  const send = (event: FormEvent) => {
    event.preventDefault();
    if (issuing) return;
    onIssue({ taxValues });
  };

  return (
    <form
      aria-label={t("desktop.automation_access.issue")}
      className="grid gap-3"
      onSubmit={send}
    >
      <p className="text-sm text-muted-foreground">
        {t("desktop.automation_access.issue_lead")}
      </p>
      <div className="flex items-start gap-2">
        <input
          id={taxId}
          type="checkbox"
          className="mt-1 size-icon-sm shrink-0 accent-primary"
          checked={taxValues}
          disabled={issuing}
          onChange={(event) => setTaxValues(event.currentTarget.checked)}
        />
        <div className="grid gap-0.5">
          <FieldLabel htmlFor={taxId}>
            {t("desktop.automation_access.tax_values")}
          </FieldLabel>
          <FieldDescription>
            {t("desktop.automation_access.tax_values_note")}
          </FieldDescription>
        </div>
      </div>
      {refusal !== null && (
        <div className="grid gap-2">
          {refusal === "issue_unavailable" ? (
            // Not something the person did wrong, so not drawn as a failure.
            <p
              role="status"
              className="flex items-start gap-2 text-sm text-muted-foreground"
            >
              <Icon name="info" className="mt-0.5" />
              <span>{refusalWords(t, refusal)}</span>
            </p>
          ) : (
            <Refusal>{refusalWords(t, refusal)}</Refusal>
          )}
          {refusal === "outcome_unknown" && (
            <div>
              <Button
                type="button"
                variant="outline"
                size="xs"
                onClick={onRefresh}
              >
                {t("desktop.automation_access.refresh")}
              </Button>
            </div>
          )}
        </div>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button type="submit" variant="primary" size="sm" pending={issuing}>
          {issuing
            ? t("desktop.automation_access.issuing")
            : t("desktop.automation_access.issue_submit")}
        </Button>
      </div>
    </form>
  );
}

/**
 * The reference a key just issued is named by, shown until it is closed. The
 * key itself was put in this computer's secure store and is not here; the
 * reference is what the agent's launch configuration asks for, and the list
 * cannot give it again.
 */
function IssuedPanel({
  issued,
  onCopy,
  onDone,
}: {
  issued: IssuedKey;
  onCopy?: (text: string) => Promise<void>;
  onDone: () => void;
}) {
  const t = useStrings();
  const referenceId = useId();
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");
  return (
    <div className="grid gap-3">
      <Alert tone="success" icon={<Icon name="check" />}>
        <AlertTitle>{t("desktop.automation_access.issued_title")}</AlertTitle>
        <AlertDescription>
          {t("desktop.automation_access.issued_lead")}
        </AlertDescription>
      </Alert>
      <Field>
        <FieldLabel htmlFor={referenceId}>
          {t("desktop.automation_access.reference_label")}
        </FieldLabel>
        <Input
          id={referenceId}
          readOnly
          spellCheck={false}
          autoComplete="off"
          value={issued.reference}
          onFocus={(event) => event.currentTarget.select()}
        />
        <FieldDescription>
          {t("desktop.automation_access.issued_once")}
        </FieldDescription>
      </Field>
      {copy === "failed" && (
        <Refusal>{t("desktop.automation_access.copy_failed")}</Refusal>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        {onCopy && (
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              onCopy(issued.reference).then(
                () => setCopy("copied"),
                () => setCopy("failed"),
              )
            }
          >
            {copy === "copied"
              ? t("desktop.automation_access.copied")
              : t("desktop.automation_access.copy")}
          </Button>
        )}
        <Button variant="primary" size="sm" onClick={onDone}>
          {t("desktop.automation_access.done")}
        </Button>
      </div>
    </div>
  );
}

/**
 * The API keys of the signed-in profile for AI agents outside Cadrumo: what
 * each may do and when it was used, and the person's ways to issue a key and
 * to revoke one. No key is ever shown. Issuing one is a single press by the
 * signed-in person; revoking one asks to be confirmed, since it ends access.
 */
export function AgentAccess({
  credentials,
  locale,
  busyId = null,
  outcomes = {},
  issuing = false,
  issueRefusal = null,
  issued = null,
  onIssue,
  onCloseIssue,
  onRevoke,
  onRefresh,
  onCopy,
}: {
  credentials: readonly AgentCredential[];
  /** The language dates are written in. */
  locale: string;
  /** The key whose revoke is on its way. */
  busyId?: string | null;
  /** How the last change to each key ended, by key id. */
  outcomes?: Readonly<Record<string, AgentCredentialOutcome>>;
  /** A key is being issued: the host has not yet answered. */
  issuing?: boolean;
  /** Why the last attempt to issue a key did not make one, as a code. */
  issueRefusal?: string | null;
  /** The key just issued, until the person closes it. */
  issued?: IssuedKey | null;
  onIssue: (choice: AgentKeyChoice) => void;
  /** The key just issued is closed: it is forgotten, and so is any refusal of
   * the last attempt. */
  onCloseIssue: () => void;
  onRevoke: (id: string) => void;
  onRefresh: () => void;
  /** Puts text on the clipboard; without it the reference is only shown. */
  onCopy?: (text: string) => Promise<void>;
}) {
  const t = useStrings();
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className="agent-access grid gap-2">
      <div className="grid gap-1">
        <h3 id={titleId} className="font-medium text-foreground">
          {t("desktop.automation_access.title")}
        </h3>
        <p className="text-sm text-muted-foreground">
          {t("desktop.automation_access.lead")}
        </p>
      </div>
      {issued ? (
        <IssuedPanel issued={issued} onCopy={onCopy} onDone={onCloseIssue} />
      ) : (
        <IssueForm
          issuing={issuing}
          refusal={issueRefusal}
          onIssue={onIssue}
          onRefresh={onRefresh}
        />
      )}
      {credentials.length === 0 ? (
        <p className="py-2 text-sm text-muted-foreground">
          {t("desktop.automation_access.empty")}
        </p>
      ) : (
        <ul className="grid">
          {credentials.map((credential) => (
            <CredentialRow
              key={credential.id}
              credential={credential}
              locale={locale}
              busy={busyId === credential.id}
              outcome={outcomes[credential.id]}
              onRevoke={() => onRevoke(credential.id)}
              onRefresh={onRefresh}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
