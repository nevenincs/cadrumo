import { useEffect, useId, useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { NativeSelect } from "@/components/ui/native-select";
import { PasswordInput } from "@/components/ui/password-input";
import { Spinner } from "@/components/ui/spinner";
import { useNavigationGuard } from "../../shell/navigation/hooks";
import {
  censoRequirementKeys,
  type CensoPort,
  type CensoReadiness,
} from "../../shell/profileCenso";
import { unreadDate } from "../../shell/profileInput";
import {
  AEAT_PROVIDER,
  AEAT_ROUTE,
  fieldAt,
  isEmpty,
} from "../../shell/profileRows";
import { useStrings } from "../../shell/strings";
import { ProfileValueEditor } from "./ProfileValueEditor";
import {
  credentialFailure,
  type AeatAccessPort,
  type AeatCertificate,
  type ProfileEdit,
  type ProfileField,
  type UserProfile,
} from "../../shell/userProfile";

/** The taxpayer's NIF/NIE. Cl@ve signs in as the taxpayer the profile
 * describes, so the backend reads this as the Cl@ve identity: it is asked here
 * only while the profile has none, and is written to the profile's own fact. */
const TAX_ID = "identity.tax_id";
/** The facts Cl@ve asks for, in the order the person is asked for them. */
const FACTS = [TAX_ID, "auth.numero_soporte", "auth.fecha_validez"] as const;
/** The route Cl@ve Móvil uses until the person or the product chooses one. */
const DEFAULT_ROUTE = "app_request";

/** What is said of a secret that was not saved, by how the save ended. */
const CREDENTIAL_WORDS = {
  refused: "desktop.profile.aeat.credential_failed",
  unavailable: "desktop.profile.aeat.credential_unavailable",
  unconfirmed: "desktop.profile.aeat.credential_unknown",
} as const;

type Readiness =
  | { state: "loading" }
  | { state: "failed"; code: string }
  | { state: "known"; value: CensoReadiness };
type Outcome =
  | { kind: "failed"; item: string }
  | {
      kind: "credential";
      result: ReturnType<typeof credentialFailure>;
      item: string;
    }
  | { kind: "picker"; invalid: boolean };

/** What the fact inputs start as: a masked fact is write-only, so it never
 * starts as its value. */
const factsOf = (profile: UserProfile) =>
  Object.fromEntries(
    FACTS.map((path) => {
      const field = fieldAt(profile, path);
      return [path, !field || field.masked ? "" : (field.value ?? "")];
    }),
  );

/**
 * The profile's AEAT access in one dialog: the sign-in method and its
 * Cl@ve Móvil route, the facts Cl@ve asks for, the certificate file and the
 * one secret the method keeps apart from the profile, with what AEAT
 * synchronization still needs. A save writes the changed facts, then the
 * method, then the secret, each under the revision the one before left. A
 * save confirmed whole, with every profile write read back at least as new as
 * the one before it, hands back to the page, which closes the editor and says
 * so; anything short of that stays in the editor and is told there. The secret is read from its input when the
 * form is sent and cleared there; no state holds it, and it is not retried
 * after an outcome that was not confirmed.
 */
export function AeatAccessEditor({
  base,
  current,
  port,
  censo,
  busy,
  blocked,
  error,
  latest,
  onRefresh,
  onSave,
  onSettled,
  onSaved,
  onClose,
}: {
  /** The profile as the editor opened on it. */
  base: UserProfile;
  /** The profile now; null where it cannot be read. */
  current: UserProfile | null;
  port: AeatAccessPort;
  /** Where the requirements are read, as the Censo band reads them; without
   * it the editor lists none. */
  censo?: Pick<CensoPort, "readiness">;
  /** A profile save is in flight. */
  busy: boolean;
  /** A profile save's outcome is not known. */
  blocked: boolean;
  error: string | null;
  /** The profile as last read, which a save has just left. */
  latest: () => UserProfile | null;
  onRefresh: () => void;
  onSave: (base: UserProfile, edit: ProfileEdit) => Promise<boolean>;
  /** Called once a save has ended, whatever came of it. */
  onSettled: () => void;
  /** Called once every edit the save sent was confirmed saved: the page
   * closes the editor and tells the person outside it. */
  onSaved: () => void;
  onClose: () => void;
}) {
  const t = useStrings(),
    id = useId();
  const [returnFocus] = useState(() => document.activeElement);
  // What the editor knows of the profile: its own saves advance it.
  const [known, setKnown] = useState(base);
  const stored = (path: string) => fieldAt(known, path);
  const storedMethod = stored(AEAT_PROVIDER)?.value ?? "";
  const storedRoute = stored(AEAT_ROUTE)?.value ?? "";
  const [method, setMethod] = useState(storedMethod);
  const [route, setRoute] = useState(storedRoute);
  const [facts, setFacts] = useState(() => factsOf(base));
  // Facts whose unreadable text is told: after the person leaves the field,
  // or tries to save with it.
  const [told, setTold] = useState<ReadonlySet<string>>(new Set());
  const [certificate, setCertificate] = useState<AeatCertificate | null>(null);
  const [typedSecret, setTypedSecret] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [readiness, setReadiness] = useState<Readiness>({ state: "loading" });
  const [recheck, setRecheck] = useState(0);
  const [working, setWorking] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const secret = useRef<HTMLInputElement>(null);

  const profileId = base.profile_id;
  useEffect(() => {
    if (!censo) return;
    let live = true;
    censo
      .readiness(profileId)
      .then((value) => {
        if (live) setReadiness({ state: "known", value });
      })
      .catch((failure: unknown) => {
        const code = (failure as { code?: unknown } | null)?.code;
        if (live)
          setReadiness({
            state: "failed",
            code: typeof code === "string" ? code : "unavailable",
          });
      });
    return () => {
      live = false;
    };
  }, [censo, profileId, recheck]);

  const movil = method === "clave_movil";
  const certified = method === "certificate";
  const permanente = method === "clave_permanente";
  const readinessRoute =
    readiness.state === "known" ? readiness.value.route : "";
  const routeNow = route || readinessRoute || DEFAULT_ROUTE;
  // The NIF/NIE is asked for only when the profile opened without one. The
  // answer is taken once, so neither the editor's own save nor a profile read
  // again while it is open takes the field away from under the person.
  const [taxIdMissing] = useState(() => {
    const field = fieldAt(base, TAX_ID);
    return field !== undefined && isEmpty(field);
  });
  const shownFacts = FACTS.map((path) => stored(path)).filter(
    (field): field is ProfileField =>
      field !== undefined &&
      (field.path === TAX_ID
        ? (movil || permanente) && taxIdMissing
        : movil && routeNow === "app_request"),
  );
  const factChanged = (field: ProfileField) => {
    const value = facts[field.path] ?? "";
    return (
      value.trim() !== "" && (field.masked || value !== (field.value ?? ""))
    );
  };
  const methodChanged =
    method !== storedMethod ||
    (movil && route !== storedRoute) ||
    (certified && certificate !== null);
  const secretShown = certified || permanente;
  const drafted =
    shownFacts.some(factChanged) ||
    methodChanged ||
    (secretShown && typedSecret);
  // The page's read can trail the editor's own save for a moment; only a
  // profile newer than the one the editor knows, or another at its revision,
  // changed elsewhere.
  const changed =
    !working &&
    (!current ||
      current.record_revision > known.record_revision ||
      (current.record_revision === known.record_revision &&
        current.content_digest !== known.content_digest));
  const idle = !(working || busy);
  const canSave = idle && !changed && !blocked && method !== "" && drafted;
  const providerField = stored(AEAT_PROVIDER);
  const routeField = stored(AEAT_ROUTE);
  // The method's own name, as the product words it, leads the password's.
  const secretLabel = certified
    ? t("desktop.profile.aeat.passphrase")
    : t("desktop.profile.aeat.password", {
        method:
          providerField?.choices.find((choice) => choice.value === method)
            ?.label ?? "",
      });

  const clearSecret = () => {
    if (secret.current) secret.current.value = "";
    setTypedSecret(false);
    setRevealed(false);
  };
  const close = () => {
    clearSecret();
    onClose();
  };
  useNavigationGuard(
    "profile",
    working ? "busy" : drafted ? "dirty" : "clean",
    {
      discard: close,
    },
  );

  const choose = async () => {
    try {
      const picked = await port.pickCertificate();
      if (picked) {
        setCertificate(picked);
        setOutcome(null);
      }
    } catch (failure) {
      setOutcome({
        kind: "picker",
        invalid: (failure as { code?: unknown } | null)?.code === "invalid",
      });
    }
  };

  const submit = async () => {
    if (!canSave) return;
    const unread = shownFacts.filter(
      (field) => unreadDate(field, facts[field.path] ?? "") !== null,
    );
    if (unread.length) {
      setTold(new Set(unread.map((field) => field.path)));
      return;
    }
    const typed = secretShown ? (secret.current?.value ?? "") : "";
    clearSecret();
    setOutcome(null);
    setWorking(true);
    let at = known;
    let saved = false;
    // Each edit is made under the revision the one before left.
    const apply = async (edit: ProfileEdit, item: string) => {
      const next = (await onSave(at, edit)) ? latest() : null;
      // A readback older than the profile the edit was made on does not show
      // the edit saved.
      if (!next || next.record_revision < at.record_revision) {
        setOutcome({ kind: "failed", item });
        return false;
      }
      at = next;
      setKnown(next);
      return true;
    };
    try {
      for (const field of shownFacts.filter(factChanged)) {
        const edit: ProfileEdit = {
          kind: "field",
          path: field.path,
          value: facts[field.path] ?? "",
        };
        if (!(await apply(edit, field.label))) return;
        if (field.masked) setFacts((now) => ({ ...now, [field.path]: "" }));
      }
      if (methodChanged) {
        const edit: ProfileEdit = {
          kind: "auth_method",
          provider: method,
          clave_movil_route: movil ? routeNow : null,
          certificate: certified ? (certificate?.token ?? null) : null,
        };
        if (!(await apply(edit, providerField?.label ?? method))) return;
        setRoute(movil ? routeNow : "");
        setCertificate(null);
      }
      if (typed !== "") {
        try {
          await port.saveCredential({
            profile_id: at.profile_id,
            provider: certified ? "certificate" : "clave_permanente",
            password: typed,
          });
        } catch (failure) {
          setOutcome({
            kind: "credential",
            result: credentialFailure(failure),
            item: secretLabel,
          });
          return;
        }
      }
      saved = true;
    } finally {
      setWorking(false);
      onSettled();
      if (saved) onSaved();
      else setRecheck((count) => count + 1);
    }
  };

  const said =
    outcome?.kind === "failed"
      ? t("desktop.profile.aeat.failed", { item: outcome.item })
      : outcome?.kind === "credential"
        ? t(CREDENTIAL_WORDS[outcome.result], { item: outcome.item })
        : outcome?.kind === "picker"
          ? t(
              outcome.invalid
                ? "auth.sync.requirement.certificate_file_required"
                : "desktop.profile.aeat.certificate_failed",
            )
          : null;
  const fileSaved =
    readiness.state === "known" &&
    readiness.value.requirements.some(
      (item) => item.field === "certificate.file" && item.satisfied,
    );
  const missing =
    readiness.state === "known"
      ? readiness.value.requirements.filter((item) => !item.satisfied)
      : [];

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && idle) close();
      }}
    >
      <DialogContent
        modalLayer={false}
        closeLabel={idle ? t("desktop.profile.cancel") : undefined}
        onCloseAutoFocus={(event) => {
          if (returnFocus instanceof HTMLElement && returnFocus.isConnected) {
            event.preventDefault();
            returnFocus.focus();
          }
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("desktop.profile.action.aeat_access")}</DialogTitle>
          <DialogDescription>
            {t("desktop.profile.aeat.description")}
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid min-w-0 gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <Field>
            <FieldLabel htmlFor={`${id}-method`}>
              {providerField?.label}
            </FieldLabel>
            <NativeSelect
              id={`${id}-method`}
              value={method}
              disabled={!idle}
              onChange={(event) => setMethod(event.target.value)}
            >
              <option value="">{t("desktop.profile.not_set")}</option>
              {providerField?.choices.map((choice) => (
                <option key={choice.value} value={choice.value}>
                  {choice.label}
                </option>
              ))}
            </NativeSelect>
          </Field>
          {movil && (
            <Field>
              <FieldLabel htmlFor={`${id}-route`}>
                {routeField?.label}
              </FieldLabel>
              <NativeSelect
                id={`${id}-route`}
                value={routeNow}
                disabled={!idle}
                onChange={(event) => setRoute(event.target.value)}
              >
                {routeField?.choices.map((choice) => (
                  <option key={choice.value} value={choice.value}>
                    {choice.label}
                  </option>
                ))}
              </NativeSelect>
            </Field>
          )}
          {shownFacts.map((field, index) => {
            const text = unreadDate(field, facts[field.path] ?? "");
            const refusal = text !== null && told.has(field.path) ? text : null;
            return (
              <Field key={field.path} data-invalid={refusal !== null}>
                <FieldLabel htmlFor={`${id}-fact-${index}`}>
                  {field.label}
                </FieldLabel>
                <ProfileValueEditor
                  field={field}
                  id={`${id}-fact-${index}`}
                  value={facts[field.path] ?? ""}
                  disabled={!idle}
                  invalid={refusal !== null || undefined}
                  describedBy={
                    [
                      refusal !== null ? `${id}-fact-${index}-refused` : null,
                      field.masked && !isEmpty(field)
                        ? `${id}-fact-${index}-saved`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(" ") || undefined
                  }
                  onBlur={() => setTold(new Set(told).add(field.path))}
                  onChange={(value) => {
                    setTold(new Set([...told].filter((p) => p !== field.path)));
                    setFacts({ ...facts, [field.path]: value });
                  }}
                />
                <FieldError id={`${id}-fact-${index}-refused`}>
                  {refusal !== null &&
                    t("desktop.editor.date.refused", { raw: refusal })}
                </FieldError>
                {field.masked && !isEmpty(field) && (
                  <FieldDescription id={`${id}-fact-${index}-saved`}>
                    {t("desktop.profile.aeat.saved_value")}
                  </FieldDescription>
                )}
              </Field>
            );
          })}
          {movil && routeNow === "app_request" && (
            <p className="text-sm text-muted-foreground">
              {t("desktop.profile.aeat.document_hint")}
            </p>
          )}
          {certified && (
            <Field>
              <FieldLabel id={`${id}-file-label`}>
                {t("desktop.profile.aeat.certificate")}
              </FieldLabel>
              <div className="flex min-w-0 items-center gap-2">
                <span
                  id={`${id}-file`}
                  className="min-w-0 flex-1 truncate text-sm text-muted-foreground"
                >
                  {certificate?.name ??
                    t(
                      fileSaved
                        ? "desktop.profile.aeat.certificate_saved"
                        : "desktop.profile.aeat.certificate_none",
                    )}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!idle}
                  aria-describedby={`${id}-file-label ${id}-file`}
                  onClick={() => void choose()}
                >
                  {t(
                    certificate || fileSaved
                      ? "desktop.profile.aeat.certificate_replace"
                      : "desktop.profile.aeat.certificate_choose",
                  )}
                </Button>
              </div>
            </Field>
          )}
          {secretShown && (
            <Field>
              <FieldLabel htmlFor={`${id}-secret`}>{secretLabel}</FieldLabel>
              <PasswordInput
                ref={secret}
                id={`${id}-secret`}
                name="secret"
                autoComplete="new-password"
                disabled={!idle}
                revealed={revealed}
                onRevealedChange={setRevealed}
                showLabel={t("desktop.signin.show_password")}
                hideLabel={t("desktop.signin.hide_password")}
                aria-describedby={`${id}-secret-help`}
                onChange={(event) =>
                  setTypedSecret(event.currentTarget.value !== "")
                }
              />
              <FieldDescription id={`${id}-secret-help`}>
                {t("desktop.profile.aeat.secret_help")}
              </FieldDescription>
            </Field>
          )}
          <section
            aria-labelledby={`${id}-readiness`}
            className="grid gap-1.5 rounded-md border bg-chrome px-3 py-2 text-sm"
          >
            <h3 id={`${id}-readiness`} className="font-medium text-foreground">
              {t("desktop.profile.aeat.readiness")}
            </h3>
            <div role="status" className="text-foreground">
              {readiness.state === "loading" ? (
                <span className="flex items-center gap-1.5">
                  <Spinner className="size-icon-xs" />
                  {t("desktop.profile.censo.checking")}
                </span>
              ) : readiness.state === "failed" ? (
                <span className="flex flex-wrap items-center gap-2">
                  {t("desktop.profile.censo.unavailable")} ({readiness.code})
                  <Button
                    type="button"
                    size="xs"
                    variant="outline"
                    disabled={!idle}
                    onClick={() => {
                      setReadiness({ state: "loading" });
                      setRecheck((count) => count + 1);
                    }}
                  >
                    {t("desktop.profile.refresh")}
                  </Button>
                </span>
              ) : readiness.value.ready ? (
                t("desktop.profile.censo.ready")
              ) : (
                <>
                  {t("desktop.profile.censo.blocked")}
                  <ul className="mt-0.5 list-disc pl-5">
                    {missing.map((item) => (
                      <li key={`${item.field}:${item.reason}`}>
                        {t(
                          censoRequirementKeys[
                            item.reason as keyof typeof censoRequirementKeys
                          ] ?? "auth.sync.requirement.unavailable",
                        )}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </section>
          {changed && (
            <Alert tone="warning">{t("desktop.profile.conflict")}</Alert>
          )}
          {said && (
            <Alert role="alert" tone="danger">
              {said}
            </Alert>
          )}
          {error && (
            <Alert role="alert" tone="danger">
              {error}
            </Alert>
          )}
          <DialogFooter>
            {blocked && (
              <Button
                type="button"
                variant="outline"
                onClick={onRefresh}
                disabled={!idle}
              >
                {t("desktop.profile.refresh")}
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              disabled={!idle}
              onClick={close}
            >
              {t("desktop.profile.cancel")}
            </Button>
            <Button type="submit" disabled={!canSave}>
              {!idle && <Spinner />}
              {t(idle ? "desktop.profile.save" : "desktop.profile.saving")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
