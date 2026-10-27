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
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { PasswordInput } from "@/components/ui/password-input";
import { Spinner } from "@/components/ui/spinner";
import { useNavigationGuard } from "../../shell/navigation/hooks";
import {
  censoRequirementKeys,
  type CensoPort,
  type CensoReadiness,
} from "../../shell/profileCenso";
import { profileInput } from "../../shell/profileInput";
import {
  AEAT_PROVIDER,
  AEAT_ROUTE,
  fieldAt,
  isEmpty,
} from "../../shell/profileRows";
import { useStrings } from "../../shell/strings";
import {
  credentialFailure,
  type AeatAccessPort,
  type AeatCertificate,
  type ProfileEdit,
  type ProfileField,
  type UserProfile,
} from "../../shell/userProfile";

const DNI_NIE = "auth.dni_nie";
/** The facts Cl@ve asks for, in the order the person is asked for them. */
const FACTS = [DNI_NIE, "auth.numero_soporte", "auth.fecha_validez"] as const;
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
  | { state: "failed" }
  | { state: "known"; value: CensoReadiness };
type Outcome =
  | { kind: "saved" }
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
 * method, then the secret, each under the revision the one before left, and
 * reads the requirements again. The secret is read from its input when the
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
      .catch(() => {
        if (live) setReadiness({ state: "failed" });
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
  const shownFacts = FACTS.map((path) => stored(path)).filter(
    (field): field is ProfileField =>
      field !== undefined &&
      (field.path === DNI_NIE
        ? movil || permanente
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
  const changed =
    !working &&
    (!current ||
      current.record_revision !== known.record_revision ||
      current.content_digest !== known.content_digest);
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
    const typed = secretShown ? (secret.current?.value ?? "") : "";
    clearSecret();
    setOutcome(null);
    setWorking(true);
    let at = known;
    // Each edit is made under the revision the one before left.
    const apply = async (edit: ProfileEdit, item: string) => {
      const next = (await onSave(at, edit)) ? latest() : null;
      if (!next) {
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
      setOutcome({ kind: "saved" });
    } finally {
      setWorking(false);
      setRecheck((count) => count + 1);
      onSettled();
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
          {shownFacts.map((field, index) => (
            <Field key={field.path}>
              <FieldLabel htmlFor={`${id}-fact-${index}`}>
                {field.label}
              </FieldLabel>
              <Input
                {...profileInput(field)}
                id={`${id}-fact-${index}`}
                value={facts[field.path] ?? ""}
                maxLength={4096}
                disabled={!idle}
                aria-describedby={
                  field.masked && !isEmpty(field)
                    ? `${id}-fact-${index}-saved`
                    : undefined
                }
                onChange={(event) =>
                  setFacts({ ...facts, [field.path]: event.target.value })
                }
              />
              {field.masked && !isEmpty(field) && (
                <FieldDescription id={`${id}-fact-${index}-saved`}>
                  {t("desktop.profile.aeat.saved_value")}
                </FieldDescription>
              )}
            </Field>
          ))}
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
                autoComplete="off"
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
                  {t("desktop.profile.censo.unavailable")}
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
          {outcome?.kind === "saved" && (
            <Alert tone="success">{t("desktop.profile.aeat.saved")}</Alert>
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
              {t(
                outcome?.kind === "saved"
                  ? "desktop.profile.aeat.done"
                  : "desktop.profile.cancel",
              )}
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
