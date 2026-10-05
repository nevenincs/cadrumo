import { useEffect, useId, useRef, useState, type RefObject } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import type { SignInController } from "../shell/signIn";
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

const refusalCode = (refusal: SignInRefusal | null) =>
  refusal?.code.toUpperCase() ?? null;

/**
 * A refusal, said in the shell's own words. A throttle shows its wait as it
 * runs down and leaves when the wait is over.
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
  const throttled = code === "THROTTLED";
  if (throttled && seconds <= 0) return null;
  const total = refusal.retryAfterSeconds ?? 0;
  return (
    <Alert
      tone={entry.tone}
      role={entry.tone === "danger" ? "alert" : "status"}
      icon={<Icon name={entry.icon} />}
    >
      <AlertTitle className="font-normal">
        {t(entry.key, { code: refusal.code, seconds })}
      </AlertTitle>
      {throttled && total > 0 && (
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

/**
 * The sign-in screen: a dialog over the window, opened while the active
 * profile has no live sign-in. It submits once through the account controller
 * and never retries. The password is read from the field when the form is
 * submitted, handed over as bytes and cleared from the field; it is never
 * held in state here.
 */
export function SignInDialog({
  account,
  open,
  onOpenChange,
  returnFocus,
}: {
  account: SignInController;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Where focus goes when the dialog is dismissed. */
  returnFocus: RefObject<HTMLElement | null>;
}) {
  const t = useStrings();
  const input = useRef<HTMLInputElement>(null);
  const handover = useRef<HTMLButtonElement>(null);
  const [revealed, setRevealed] = useState(false);
  const errorId = useId();
  const status = account.status;

  // A refused submission hands the keyboard back to the field: it was
  // disabled while the answer was pending, which drops focus.
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
  const locked = account.busy || !available;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sign-in gap-5 p-6"
        closeLabel={t("desktop.signin.dismiss")}
        onOpenAutoFocus={(event) => {
          // The password field first; where it cannot be used, the way on.
          event.preventDefault();
          (input.current?.disabled ? handover.current : input.current)?.focus();
        }}
        onCloseAutoFocus={(event) => {
          if (!returnFocus.current) return;
          event.preventDefault();
          returnFocus.current.focus();
        }}
      >
        <DialogHeader className="gap-4">
          <Logo />
          <div className="grid gap-1">
            <DialogTitle>{t("desktop.signin.title")}</DialogTitle>
            <DialogDescription>{t("desktop.signin.lead")}</DialogDescription>
          </div>
        </DialogHeader>

        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            const field = input.current;
            if (!field || locked || seconds > 0) return;
            const bytes = new TextEncoder().encode(field.value);
            field.value = "";
            setRevealed(false);
            void account.submit(bytes);
          }}
        >
          {status.active_profile && (
            <p className="flex w-fit max-w-full min-w-0 items-center gap-1.5 rounded-full bg-accent py-1 pr-3 pl-2 text-sm text-muted-foreground">
              <Icon name="user" />
              <span className="sr-only">{t("desktop.signin.profile")}</span>
              <span className="truncate font-medium text-foreground">
                {status.active_profile}
              </span>
            </p>
          )}

          <Field data-invalid={rejected} data-disabled={locked}>
            <FieldLabel htmlFor="profile-password">
              {t("desktop.signin.password")}
            </FieldLabel>
            <PasswordInput
              ref={input}
              id="profile-password"
              name="password"
              required
              disabled={locked}
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

          {!rejected && <Refusal refusal={account.refusal} seconds={seconds} />}
          {!available && !account.refusal && (
            <Alert tone="warning" icon={<Icon name="unplug" />}>
              <AlertTitle className="font-normal">
                {t("desktop.signin.refused.runtime_unavailable")}
              </AlertTitle>
            </Alert>
          )}

          <Button
            type="submit"
            size="lg"
            className="w-full"
            pending={account.busy}
            disabled={seconds > 0 || !available}
          >
            {t(
              account.busy
                ? "desktop.signin.submitting"
                : "desktop.signin.submit",
            )}
          </Button>
        </form>

        <Separator />

        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <p className="min-w-40 flex-1 text-sm text-muted-foreground">
            {t("desktop.signin.open_tui_hint")}
          </p>
          <Button
            ref={handover}
            variant="outline"
            size="sm"
            onClick={account.openTui}
            disabled={account.busy}
          >
            {t("desktop.signin.open_tui")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/**
 * What the TUI pane shows while it is gated: the status check in flight, or
 * the signed-out state with the ways forward.
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
  if (!account.status)
    return (
      <Empty role="status">
        <Spinner />
        <EmptyDescription>{t("desktop.signin.checking")}</EmptyDescription>
      </Empty>
    );
  return (
    <Empty>
      <EmptyMedia>
        <Icon name="lock" />
      </EmptyMedia>
      <div className="grid gap-1">
        <EmptyTitle>{t("desktop.account.signed_out")}</EmptyTitle>
        <EmptyDescription>
          {t("desktop.signin.signed_out_lead")}
        </EmptyDescription>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        <Button ref={signInButton} onClick={onSignIn}>
          {t("desktop.signin.submit")}
        </Button>
        <Button variant="ghost" onClick={account.openTui}>
          {t("desktop.signin.open_tui")}
        </Button>
      </div>
    </Empty>
  );
}

/** The Account section of settings: who is signed in, and signing out. */
export function Account({
  account,
  onSignOut,
}: {
  account: SignInController;
  onSignOut: () => void;
}) {
  const t = useStrings();
  const status = account.status;
  if (!status?.supported) return null;
  const present = status.state === "present";
  return (
    <section
      className="account grid gap-2"
      aria-label={t("desktop.account.title")}
    >
      <h3 className="text-sm font-medium text-muted-foreground">
        {t("desktop.account.title")}
      </h3>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2">
          <Icon name="user" className="text-muted-foreground" />
          {status.active_profile && (
            <span className="truncate font-medium">
              {status.active_profile}
            </span>
          )}
          <Badge variant={present ? "success" : "neutral"}>
            {t(
              present
                ? "desktop.account.signed_in"
                : status.state === "absent"
                  ? "desktop.account.signed_out"
                  : "desktop.account.unknown",
            )}
          </Badge>
        </span>
        <Button
          variant="outline"
          size="sm"
          pending={account.busy}
          disabled={!present}
          onClick={onSignOut}
        >
          {!account.busy && <Icon name="signOut" />}
          {t("desktop.account.sign_out")}
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">
        {t("desktop.account.sign_out_hint")}
      </p>
      {account.remaining &&
        account.remaining.remainingAccess.automationEnabled !== false && (
          <Alert icon={<Icon name="info" />}>
            <AlertDescription className="text-foreground">
              {t("desktop.account.remaining_access")}
            </AlertDescription>
          </Alert>
        )}
      <Refusal refusal={account.refusal} seconds={account.retrySeconds} />
    </section>
  );
}
