import { useId, useState } from "react";
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
import { Kbd } from "@/components/ui/kbd";
import { PasswordInput } from "@/components/ui/password-input";
import { Spinner } from "@/components/ui/spinner";
import type { PasswordChangeResult } from "../../ipc/contract";
import { chordLabel } from "../../shell/actions";
import {
  PASSWORD_MIN,
  passwordChange,
  passwordProblem,
  type ProfileAccounts,
} from "../../shell/profiles";
import { useStrings } from "../../shell/strings";

const chord = (key: string, shift = false) =>
  chordLabel({ code: `Key${key}`, key, mod: true, shift, scope: "app" });

/** Every key the profile page answers, as one sheet. */
export function ProfileShortcuts({
  open,
  onClose,
}: {
  open: boolean;
  onClose(): void;
}) {
  const t = useStrings();
  const rows: [string[], string][] = [
    [["↑", "↓"], t("desktop.profile.keys.move")],
    [["Home", "End"], t("desktop.profile.keys.first_last")],
    [["[", "]"], t("desktop.profile.keys.section")],
    [["←", "→"], t("desktop.profile.keys.toggle")],
    [["Enter"], t("desktop.profile.keys.edit")],
    [["Shift+F10"], t("desktop.profile.keys.menu")],
    [[chord("C")], t("desktop.profile.keys.copy")],
    [["/"], t("desktop.profile.keys.search")],
    [["Esc"], t("desktop.profile.keys.clear")],
    [[chord("K")], t("desktop.profile.keys.actions")],
    [[chord("M", true)], t("desktop.profile.keys.full")],
    [["?"], t("desktop.profile.keys.help")],
  ];
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
    >
      <DialogContent closeLabel={t("desktop.profile.close_dialog")}>
        <DialogHeader>
          <DialogTitle>{t("desktop.profile.keys.title")}</DialogTitle>
          <DialogDescription>
            {t("desktop.profile.keys.lead")}
          </DialogDescription>
        </DialogHeader>
        <dl className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-2">
          {rows.map(([keys, text]) => (
            <div key={text} className="contents">
              <dt className="flex gap-1">
                {keys.map((key) => (
                  <Kbd key={key}>{key}</Kbd>
                ))}
              </dt>
              <dd>{text}</dd>
            </div>
          ))}
        </dl>
      </DialogContent>
    </Dialog>
  );
}

type Problem = "short" | "long" | "mismatch";
type Outcome = Exclude<PasswordChangeResult, { kind: "changed" }>;

/**
 * Changes the signed-in profile's password. The three fields are read when
 * the form is sent, handed over as bytes and cleared; none is held in state.
 * One attempt per send, and none after an outcome that was not confirmed.
 */
export function PasswordChange({
  change,
  open,
  onClose,
  onChanged,
}: {
  change: NonNullable<ProfileAccounts["changePassword"]>;
  open: boolean;
  onClose(): void;
  onChanged(): void;
}) {
  const t = useStrings();
  const id = useId();
  const [revealed, setRevealed] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [busy, setBusy] = useState(false);
  const unknown = outcome?.kind === "unknown";
  const close = () => {
    if (busy) return;
    setProblem(null);
    setOutcome(null);
    setRevealed(false);
    onClose();
  };
  const said =
    outcome?.kind === "unknown"
      ? t("desktop.profile.password.unknown")
      : outcome?.code === "CREDENTIAL_REJECTED"
        ? t("desktop.profile.password.rejected")
        : outcome?.code === "THROTTLED"
          ? t("desktop.signin.refused.throttled", {
              seconds: outcome.retryAfterSeconds ?? 0,
            })
          : outcome?.code === "not_signed_in"
            ? t("desktop.profile.signed_out")
            : outcome
              ? t("desktop.profile.password.refused")
              : problem === "mismatch"
                ? t("desktop.account.create.mismatch")
                : problem === "long"
                  ? t("desktop.account.create.password_long")
                  : problem === "short"
                    ? t("desktop.account.create.password_short", {
                        min: PASSWORD_MIN,
                      })
                    : null;
  const field = (name: string) => `${id}-${name}`;
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) close();
      }}
    >
      <DialogContent closeLabel={t("desktop.profile.cancel")}>
        <DialogHeader>
          <DialogTitle>{t("desktop.profile.password.title")}</DialogTitle>
          <DialogDescription>
            {t("desktop.profile.password.lead")}
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (busy || unknown) return;
            const form = event.currentTarget;
            const values = new FormData(form);
            const read = (name: string) => String(values.get(name) ?? "");
            const next = read("new");
            const found = passwordProblem(next);
            setOutcome(null);
            if (found || next !== read("again")) {
              setProblem(found ?? "mismatch");
              return;
            }
            setProblem(null);
            const passwords = passwordChange(read("current"), next, next);
            form.reset();
            setBusy(true);
            change(passwords)
              .then((result) => {
                if (result.kind === "changed") {
                  setRevealed(false);
                  onChanged();
                } else setOutcome(result);
              })
              // A lost answer is no proof that nothing changed.
              .catch(() => setOutcome({ kind: "unknown" }))
              .finally(() => {
                passwords.fill(0);
                setBusy(false);
              });
          }}
        >
          {(
            [
              [
                "current",
                "desktop.profile.password.current",
                "current-password",
              ],
              ["new", "desktop.profile.password.new", "new-password"],
              ["again", "desktop.profile.password.again", "new-password"],
            ] as const
          ).map(([name, label, complete]) => (
            <Field key={name}>
              <FieldLabel htmlFor={field(name)}>{t(label)}</FieldLabel>
              <PasswordInput
                id={field(name)}
                name={name}
                required
                disabled={busy || unknown}
                autoComplete={complete}
                revealed={revealed}
                onRevealedChange={setRevealed}
                showLabel={t("desktop.signin.show_password")}
                hideLabel={t("desktop.signin.hide_password")}
                aria-describedby={name === "new" ? field("policy") : undefined}
              />
              {name === "new" && (
                <FieldDescription id={field("policy")}>
                  {t("desktop.account.create.policy", { min: PASSWORD_MIN })}
                </FieldDescription>
              )}
            </Field>
          ))}
          {said && (
            <Alert role="alert" tone="danger">
              {said}
            </Alert>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={close}
            >
              {t("desktop.profile.cancel")}
            </Button>
            <Button type="submit" disabled={busy || unknown}>
              {busy && <Spinner />}
              {t(
                busy
                  ? "desktop.profile.password.changing"
                  : "desktop.profile.password.title",
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
