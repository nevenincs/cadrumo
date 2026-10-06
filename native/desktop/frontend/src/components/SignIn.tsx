import { useEffect, useId, useRef, useState, type RefObject } from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Empty,
  EmptyDescription,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Icon, type IconName } from "@/components/ui/icon";
import { PasswordInput } from "@/components/ui/password-input";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import type { SignInRefusal } from "../ipc/contract";
import type { AccountPhase, SignInController } from "../shell/signIn";
import { useStrings } from "../shell/strings";
import { Logo } from "./Logo";

type Tone = "neutral" | "warning" | "danger";

// How each typed refusal is said: its text, its tone and its icon. A code the
// shell does not name is still shown, with the code, never swallowed.
const REFUSALS: Record<string, { key: string; tone: Tone; icon: IconName }> = {
  CREDENTIAL_REJECTED: {
    key: "desktop.signin.refused.invalid",
    tone: "danger",
    icon: "alert",
  },
  THROTTLED: {
    key: "desktop.signin.refused.throttled",
    tone: "warning",
    icon: "clock",
  },
  PROFILE_LOCKED: {
    key: "desktop.signin.refused.profile_locked",
    tone: "warning",
    icon: "lock",
  },
  KEYRING_UNAVAILABLE: {
    key: "desktop.signin.refused.keyring_unavailable",
    tone: "warning",
    icon: "lock",
  },
  RUNTIME_UNAVAILABLE: {
    key: "desktop.signin.refused.runtime_unavailable",
    tone: "warning",
    icon: "unplug",
  },
  RECEIPT_ABSENT: {
    key: "desktop.signin.refused.receipt_absent",
    tone: "neutral",
    icon: "info",
  },
  RECEIPT_EXPIRED: {
    key: "desktop.signin.refused.receipt_expired",
    tone: "neutral",
    icon: "info",
  },
  CUSTODY_CHANGED: {
    key: "desktop.signin.refused.custody_changed",
    tone: "neutral",
    icon: "info",
  },
  LOGIN_MISMATCH: {
    key: "desktop.signin.refused.login_mismatch",
    tone: "neutral",
    icon: "info",
  },
  GENERATION_CHANGED: {
    key: "desktop.signin.refused.generation_changed",
    tone: "neutral",
    icon: "info",
  },
};

const OTHER = {
  key: "desktop.signin.refused.other",
  tone: "danger",
  icon: "alert",
} as const;

// Refusals the password form cannot answer: the way on is the TUI's own flow.
const HANDED_OVER = new Set(["PROFILE_LOCKED", "KEYRING_UNAVAILABLE"]);

const refusalCode = (refusal: SignInRefusal | null) =>
  refusal?.code.toUpperCase() ?? null;

// How each phase that withholds the TUI is said, wherever it is said: in the
// TUI pane, in its header, in the dialog and in settings.
const GATES: Partial<
  Record<AccountPhase, { icon: IconName; title: string; lead: string | null }>
> = {
  "signed-out": {
    icon: "lock",
    title: "desktop.account.signed_out",
    lead: "desktop.signin.signed_out_lead",
  },
  "no-profile": {
    icon: "user",
    title: "desktop.account.no_profile",
    lead: "desktop.account.no_profile_lead",
  },
  "services-down": {
    icon: "unplug",
    title: "desktop.account.services_down",
    lead: "desktop.signin.open_tui_hint",
  },
  unknown: { icon: "alert", title: "desktop.account.unknown", lead: null },
};

/** The string that names an account phase in a line: a header's note, a
 * badge. Null where the phase has nothing to say. */
export function accountLabel(phase: AccountPhase): string | null {
  if (phase === "checking") return "desktop.signin.checking";
  if (phase === "signed-in") return "desktop.account.signed_in";
  if (phase === "in-tui") return "desktop.account.in_tui";
  return GATES[phase]?.title ?? null;
}

/** Whether a password can settle this phase. */
const signsIn = (phase: AccountPhase) =>
  phase === "signed-out" || phase === "unknown";

/**
 * A refusal, said in the shell's own words. A throttle shows its wait as it
 * runs down and leaves when the wait is over; the running number is for the
 * eye only, so a screen reader hears the wait once, not every second.
 */
function Refusal({
  refusal,
  seconds,
}: {
  refusal: SignInRefusal | null;
  seconds: number;
}) {
  const t = useStrings();
  if (!refusal) return null;
  const code = refusalCode(refusal);
  const entry = (code && REFUSALS[code]) || OTHER;
  const total = refusal.retryAfterSeconds ?? 0;
  if (code === "THROTTLED") {
    if (seconds <= 0) return null;
    return (
      <Alert tone="warning" icon={<Icon name="clock" />}>
        <span className="sr-only">{t(entry.key, { seconds: total })}</span>
        <span aria-hidden="true">{t(entry.key, { seconds })}</span>
        {total > 0 && (
          <Progress
            className="mt-1.5"
            value={total - seconds}
            max={total}
            aria-hidden="true"
          />
        )}
      </Alert>
    );
  }
  return (
    <Alert
      tone={entry.tone}
      role={entry.tone === "danger" ? "alert" : "status"}
      icon={<Icon name={entry.icon} />}
    >
      {t(entry.key, { code: refusal.code })}
    </Alert>
  );
}

/**
 * The sign-in screen: a dialog over the window, opened while the active
 * profile has no live sign-in. It submits once through the account controller
 * and never retries. The password is read from the field when the form is
 * submitted, handed over as bytes and cleared from the field; it is never
 * held in state here.
 *
 * While an answer is pending nothing in it is disabled, so focus stays where
 * it was: the field is read-only and the button reports itself busy.
 */
export function SignInDialog({
  account,
  open,
  onOpenChange,
  onClosed,
}: {
  account: SignInController;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The dialog has closed: put focus where the person continues. */
  onClosed: () => void;
}) {
  const t = useStrings();
  const input = useRef<HTMLInputElement>(null);
  const handover = useRef<HTMLButtonElement>(null);
  const [revealed, setRevealed] = useState(false);
  const errorId = useId();
  const status = account.status;

  // A refused submission returns the keyboard to the field for the next try.
  const busy = account.busy;
  const wasBusy = useRef(busy);
  useEffect(() => {
    if (wasBusy.current && !busy && open) input.current?.focus();
    wasBusy.current = busy;
  }, [busy, open]);

  if (!status) return null;

  const seconds = account.retrySeconds;
  const code = refusalCode(account.refusal);
  const rejected = code === "CREDENTIAL_REJECTED";
  const available = status.runtimeAvailable;
  // Where a password cannot help, the form is not offered.
  const handedOver = code !== null && HANDED_OVER.has(code);
  // With no profile there is nothing to sign in to: the dialog offers the
  // way to create one.
  const creating = account.phase === "no-profile";
  const answerable = available && !handedOver && !creating;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setRevealed(false);
        onOpenChange(next);
      }}
    >
      <DialogContent
        className="sign-in"
        closeLabel={t("desktop.signin.dismiss")}
        onOpenAutoFocus={(event) => {
          // The password field where there is one, else the way on.
          const target = input.current ?? handover.current;
          if (!target) return;
          event.preventDefault();
          target.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          onClosed();
        }}
      >
        <DialogHeader className="gap-3 pr-0">
          <Logo className="pr-8" />
          <div className="grid gap-1">
            <DialogTitle>
              {t(
                creating
                  ? "desktop.account.no_profile"
                  : "desktop.signin.title",
              )}
            </DialogTitle>
            <DialogDescription>
              {creating
                ? t("desktop.account.no_profile_lead")
                : answerable
                  ? t("desktop.signin.lead")
                  : t("desktop.signin.open_tui_hint")}
            </DialogDescription>
          </div>
        </DialogHeader>

        {status.active_profile && (
          <Badge variant="soft">
            <Icon name="user" />
            <span className="sr-only">{t("desktop.signin.profile")}</span>
            <span className="truncate">{status.active_profile}</span>
          </Badge>
        )}

        {answerable ? (
          <form
            className="grid gap-4"
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              const field = input.current;
              if (!field || busy || seconds > 0) return;
              // An empty field is not an attempt: nothing is sent.
              if (!field.value) {
                field.focus();
                return;
              }
              const bytes = new TextEncoder().encode(field.value);
              field.value = "";
              setRevealed(false);
              void account.submit(bytes);
            }}
          >
            {/* Not shown and not reachable: it tells a password manager
                which account this password belongs to. */}
            {status.active_profile && (
              <input
                type="text"
                name="username"
                autoComplete="username"
                value={status.active_profile}
                readOnly
                hidden
              />
            )}
            <Field data-invalid={rejected}>
              <FieldLabel htmlFor="profile-password">
                {t("desktop.signin.password")}
              </FieldLabel>
              <PasswordInput
                ref={input}
                id="profile-password"
                name="password"
                readOnly={busy}
                aria-busy={busy || undefined}
                aria-invalid={rejected || undefined}
                aria-describedby={rejected ? errorId : undefined}
                revealed={revealed}
                onRevealedChange={setRevealed}
                showLabel={t("desktop.signin.show_password")}
                hideLabel={t("desktop.signin.hide_password")}
              />
              <FieldError id={errorId}>
                {rejected && t("desktop.signin.refused.invalid")}
              </FieldError>
            </Field>

            {!rejected && (
              <Refusal refusal={account.refusal} seconds={seconds} />
            )}

            <Button
              type="submit"
              className="w-full"
              pending={busy}
              disabled={seconds > 0}
            >
              {t(busy ? "desktop.signin.submitting" : "desktop.signin.submit")}
            </Button>
          </form>
        ) : creating ? null : account.refusal ? (
          <Refusal refusal={account.refusal} seconds={seconds} />
        ) : (
          <Alert tone="warning" icon={<Icon name="unplug" />}>
            {t("desktop.signin.refused.runtime_unavailable")}
          </Alert>
        )}

        {answerable ? (
          <>
            <Separator />
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              <p className="min-w-40 flex-1 text-sm text-muted-foreground">
                {t("desktop.signin.open_tui_hint")}
              </p>
              <Button
                ref={handover}
                variant="outline"
                size="sm"
                aria-disabled={busy || undefined}
                onClick={busy ? undefined : account.openTui}
              >
                {t("desktop.signin.open_tui")}
              </Button>
            </div>
          </>
        ) : (
          <Button ref={handover} className="w-full" onClick={account.openTui}>
            {t(
              creating
                ? "desktop.account.create_profile"
                : "desktop.signin.open_tui",
            )}
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
}

/**
 * What the TUI pane shows while the account is not settled: the status check
 * in flight, or what stands in the way with the ways forward. The primary
 * action takes `signInButton`, so focus has somewhere to go in every phase.
 */
export function SignedOut({
  account,
  onSignIn,
  signInButton,
}: {
  account: SignInController;
  onSignIn: () => void;
  signInButton: RefObject<HTMLButtonElement | null>;
}) {
  const t = useStrings();
  const gate = GATES[account.phase];
  if (!gate)
    return (
      <Empty role="status">
        <Spinner />
        <EmptyDescription>{t("desktop.signin.checking")}</EmptyDescription>
      </Empty>
    );
  const password = signsIn(account.phase);
  return (
    <Empty>
      <EmptyMedia>
        <Icon name={gate.icon} />
      </EmptyMedia>
      <div className="grid gap-1">
        <EmptyTitle>{t(gate.title)}</EmptyTitle>
        {gate.lead && <EmptyDescription>{t(gate.lead)}</EmptyDescription>}
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {password && (
          <Button ref={signInButton} onClick={onSignIn}>
            {t("desktop.signin.submit")}
          </Button>
        )}
        <Button
          ref={password ? undefined : signInButton}
          variant={password ? "ghost" : "primary"}
          aria-disabled={account.busy || undefined}
          onClick={account.busy ? undefined : account.openTui}
        >
          {t(
            account.phase === "no-profile"
              ? "desktop.account.create_profile"
              : "desktop.signin.open_tui",
          )}
        </Button>
      </div>
    </Empty>
  );
}

const SESSION_TONE: Partial<
  Record<AccountPhase, "success" | "warning" | "neutral">
> = { "signed-in": "success", "services-down": "warning" };

/**
 * The account in settings, as two sections: which profile this window works
 * in, and its sign-in. Each says the same phase the rest of the window shows.
 */
export function Account({
  account,
  onSignIn,
  onSignOut,
}: {
  account: SignInController;
  onSignIn: () => void;
  onSignOut: () => void;
}) {
  const t = useStrings();
  const profileId = useId();
  const sessionId = useId();
  const status = account.status;
  const phase = account.phase;
  if (!status?.supported) return null;
  const label = accountLabel(phase === "no-profile" ? "signed-out" : phase);
  return (
    <>
      <section className="grid gap-2" aria-labelledby={profileId}>
        <h3
          id={profileId}
          className="text-sm font-medium text-muted-foreground"
        >
          {t("desktop.signin.profile")}
        </h3>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2">
            <Icon name="user" className="text-muted-foreground" />
            <span
              className={
                status.active_profile
                  ? "truncate font-medium"
                  : "text-muted-foreground"
              }
            >
              {/* Unnamed is only "none" where that is known: with no runtime
                  to ask, the profile is simply not known. */}
              {status.active_profile ??
                (phase === "no-profile"
                  ? t("desktop.account.no_profile")
                  : "—")}
            </span>
          </span>
          {phase === "no-profile" && (
            <Button variant="outline" size="sm" onClick={account.openTui}>
              {t("desktop.account.create_profile")}
            </Button>
          )}
        </div>
      </section>
      <section className="account grid gap-2" aria-labelledby={sessionId}>
        <h3
          id={sessionId}
          className="text-sm font-medium text-muted-foreground"
        >
          {t("desktop.settings.session")}
        </h3>
        <div className="flex flex-wrap items-center justify-between gap-2">
          {label && (
            <Badge variant={SESSION_TONE[phase] ?? "neutral"}>{t(label)}</Badge>
          )}
          {phase === "signed-in" ? (
            <Button
              variant="outline"
              size="sm"
              pending={account.busy}
              onClick={onSignOut}
            >
              {!account.busy && <Icon name="signOut" />}
              {t("desktop.account.sign_out")}
            </Button>
          ) : signsIn(phase) ? (
            <Button variant="outline" size="sm" onClick={onSignIn}>
              {t("desktop.signin.submit")}
            </Button>
          ) : null}
        </div>
        {phase === "signed-in" && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.account.sign_out_hint")}
          </p>
        )}
        {account.remaining &&
          account.remaining.remainingAccess.automationEnabled !== false && (
            <Alert icon={<Icon name="info" />}>
              {t("desktop.account.remaining_access")}
            </Alert>
          )}
        {account.signOutFailure && (
          <Alert tone="danger" role="alert" icon={<Icon name="alert" />}>
            {t("desktop.account.sign_out_failed", {
              code: account.signOutFailure.code,
            })}
          </Alert>
        )}
      </section>
    </>
  );
}
