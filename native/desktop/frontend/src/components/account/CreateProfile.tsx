import { useId, useRef, useState, type RefObject } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import type { SignInRefusal } from "@/ipc/contract";
import {
  nameProblem,
  passwordProblem,
  PASSWORD_MIN,
  type NameProblem,
  type PasswordProblem,
} from "@/shell/profiles";
import type { SignInController } from "@/shell/signIn";
import { useStrings } from "@/shell/strings";

const NAME_PROBLEMS: Record<NameProblem, string> = {
  missing: "desktop.account.create.name_missing",
  hyphen: "desktop.account.create.name_hyphen",
  characters: "desktop.account.create.name_characters",
  long: "desktop.account.create.name_long",
  taken: "desktop.account.create.name_taken",
};

const PASSWORD_PROBLEMS: Record<PasswordProblem, string> = {
  short: "desktop.account.create.password_short",
  long: "desktop.account.create.password_long",
};

/** The product's refusal of a name that is already a profile's, whatever
 * prefix its code carries. */
const nameTaken = (refusal: SignInRefusal | null) =>
  refusal?.code.toUpperCase().endsWith("PROFILE_ALREADY_EXISTS") ?? false;

/**
 * The form that creates a profile: its name and its password, twice. Like
 * the sign-in form it sends once and never again; both password fields are
 * read when the form is submitted, handed over as bytes and cleared, and
 * neither is held in state. What the product would refuse is said before
 * anything is sent; the product still judges what is sent.
 */
export function CreateProfile({
  account,
  nameField,
  onDone,
  onBack,
}: {
  account: SignInController;
  nameField: RefObject<HTMLInputElement | null>;
  /** The profile exists: the way on is signing in to it. */
  onDone: () => void;
  /** Back to signing in, where there is a profile to sign in to. */
  onBack?: () => void;
}) {
  const t = useStrings();
  const first = useRef<HTMLInputElement>(null);
  const second = useRef<HTMLInputElement>(null);
  const [revealed, setRevealed] = useState(false);
  const [problem, setProblem] = useState<{
    name: NameProblem | null;
    password: PasswordProblem | null;
    mismatch: boolean;
  }>({ name: null, password: null, mismatch: false });
  const nameId = useId();
  const nameErrorId = useId();
  const passwordId = useId();
  const policyId = useId();
  const passwordErrorId = useId();
  const confirmId = useId();
  const confirmErrorId = useId();
  const busy = account.busy;
  const refused = account.createRefusal;
  const taken = problem.name ?? (nameTaken(refused) ? "taken" : null);
  return (
    <form
      className="create-profile grid grid-cols-1 gap-4"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        const name = nameField.current;
        const password = first.current;
        const again = second.current;
        if (!name || !password || !again || busy) return;
        const found = {
          name: nameProblem(name.value, account.profiles),
          password: passwordProblem(password.value),
          mismatch: password.value !== again.value,
        };
        setProblem(found);
        // Nothing is sent while something is known to be wrong: the
        // keyboard goes to the first field that is.
        const wrong = found.name
          ? name
          : found.password
            ? password
            : found.mismatch
              ? again
              : null;
        if (wrong) {
          wrong.focus();
          return;
        }
        const bytes = new TextEncoder().encode(password.value);
        password.value = "";
        again.value = "";
        setRevealed(false);
        void account.create(name.value.trim(), bytes).then((made) => {
          if (made) onDone();
          // Refused: the passwords are gone, so the form resumes from its
          // start, where the name that may have been refused is.
          else (nameField.current ?? first.current)?.focus();
        });
      }}
    >
      <Field data-invalid={taken !== null}>
        <FieldLabel htmlFor={nameId}>
          {t("desktop.account.create.name")}
        </FieldLabel>
        <Input
          ref={nameField}
          id={nameId}
          name="username"
          autoComplete="username"
          autoCapitalize="words"
          spellCheck={false}
          readOnly={busy}
          aria-invalid={taken !== null || undefined}
          aria-describedby={taken ? nameErrorId : undefined}
        />
        <FieldError id={nameErrorId}>
          {taken && t(NAME_PROBLEMS[taken])}
        </FieldError>
      </Field>
      <Field data-invalid={problem.password !== null}>
        <FieldLabel htmlFor={passwordId}>
          {t("desktop.signin.password")}
        </FieldLabel>
        <PasswordInput
          ref={first}
          id={passwordId}
          name="new-password"
          autoComplete="new-password"
          readOnly={busy}
          aria-invalid={problem.password !== null || undefined}
          aria-describedby={problem.password ? passwordErrorId : policyId}
          revealed={revealed}
          onRevealedChange={setRevealed}
          showLabel={t("desktop.signin.show_password")}
          hideLabel={t("desktop.signin.hide_password")}
        />
        {problem.password ? (
          <FieldError id={passwordErrorId}>
            {t(PASSWORD_PROBLEMS[problem.password], { min: PASSWORD_MIN })}
          </FieldError>
        ) : (
          <FieldDescription id={policyId}>
            {t("desktop.account.create.policy", { min: PASSWORD_MIN })}
          </FieldDescription>
        )}
      </Field>
      <Field data-invalid={problem.mismatch}>
        <FieldLabel htmlFor={confirmId}>
          {t("desktop.account.create.confirm")}
        </FieldLabel>
        {/* Shown and hidden with the password above it, by that field's
            one control. */}
        <Input
          ref={second}
          id={confirmId}
          type={revealed ? "text" : "password"}
          name="confirm-password"
          autoComplete="new-password"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          readOnly={busy}
          aria-invalid={problem.mismatch || undefined}
          aria-describedby={problem.mismatch ? confirmErrorId : undefined}
        />
        <FieldError id={confirmErrorId}>
          {problem.mismatch && t("desktop.account.create.mismatch")}
        </FieldError>
      </Field>

      <Alert icon={<Icon name="info" />} role="note">
        {t("desktop.account.create.keep_safe")}
      </Alert>

      {refused && !nameTaken(refused) && (
        <Alert tone="danger" role="alert" icon={<Icon name="alert" />}>
          {t("desktop.account.create.refused", { code: refused.code })}
        </Alert>
      )}
      {/* No answer came: it is not said that there is no such profile. */}
      {account.createUnknown && (
        <Alert
          className="create-unknown"
          tone="warning"
          role="alert"
          icon={<Icon name="alert" />}
        >
          {t("desktop.account.create.unknown", {
            code: account.createUnknown.code,
          })}
        </Alert>
      )}

      <Button type="submit" className="w-full" pending={busy}>
        {t(
          busy
            ? "desktop.account.create.submitting"
            : "desktop.account.create.submit",
        )}
      </Button>
      {/* The product takes its time over this on purpose: said while it
          does, so that the wait is not read as a window that has hung. */}
      {busy && (
        <p
          className="create-wait text-center text-sm text-muted-foreground"
          role="status"
        >
          {t("desktop.account.create.wait")}
        </p>
      )}
      {onBack && (
        <Button
          variant="ghost"
          size="sm"
          className="w-full"
          aria-disabled={busy || undefined}
          onClick={busy ? undefined : onBack}
        >
          {t("desktop.account.create.back")}
        </Button>
      )}
    </form>
  );
}
