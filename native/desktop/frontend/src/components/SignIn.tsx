import { CreateProfile } from "./account/CreateProfile";
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
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field";
import { Icon, type IconName } from "@/components/ui/icon";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { PasswordInput } from "@/components/ui/password-input";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import type { SignInRefusal } from "../ipc/contract";
import { nameable } from "../shell/profiles";
import type { AccountPhase, SignInController } from "../shell/signIn";
import { useStrings } from "../shell/strings";
import { accountLabel, GATES } from "./accountWords";
import { Logo } from "./Logo";
import { AccountLoading } from "./AccountLoading";

type Tone = "neutral" | "warning" | "danger";

// How each typed refusal is said: its text, its tone and its icon. A code the
// shell does not name is still shown, with the code, never swallowed.
const REFUSALS: Record<string, { key: string; tone: Tone; icon: IconName }> = {
  INSTALLATION_UNAVAILABLE: {
    key: "desktop.signin.refused.installation_unavailable",
    tone: "warning",
    icon: "unplug",
  },
  INSTALLATION_REFUSED: {
    key: "desktop.signin.refused.installation_refused",
    tone: "danger",
    icon: "alert",
  },
  INSTALLATION_CANCELLED: {
    key: "desktop.signin.refused.installation_cancelled",
    tone: "neutral",
    icon: "info",
  },
  INSTALLATION_FAILED: {
    key: "desktop.signin.refused.installation_failed",
    tone: "danger",
    icon: "alert",
  },
  INSTALLATION_UNSETTLED: {
    key: "desktop.signin.refused.installation_unsettled",
    tone: "warning",
    icon: "alert",
  },
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
 * runs down and leaves when the wait is over; the running number is for the
 * eye only, so a screen reader hears the wait once, not every second.
 */
function Refusal({
  refusal,
  seconds,
  quiet = false,
}: {
  refusal: SignInRefusal | null;
  seconds: number;
  /** A second copy of what another pane already announces: read in place,
   * not announced again. */
  quiet?: boolean;
}) {
  const t = useStrings();
  if (!refusal) return null;
  const code = refusalCode(refusal);
  const entry =
    refusal.operation === "manager"
      ? { ...OTHER, key: "desktop.signin.refused.manager" }
      : (code && REFUSALS[code]) || OTHER;
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
      role={quiet ? "note" : entry.tone === "danger" ? "alert" : "status"}
      icon={<Icon name={entry.icon} />}
    >
      {t(entry.key, { code: refusal.code })}
      {refusal.operation && (
        <code className="text-sm text-muted-foreground">
          {[refusal.operation, refusal.ioKind, refusal.osCode]
            .filter((value) => value !== undefined)
            .join(" · ")}
        </code>
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
 *
 * While an answer is pending nothing in it is disabled, so focus stays where
 * it was: the field is read-only and the button reports itself busy.
 */
export function SignInDialog({
  account,
  open,
  onOpenChange,
  onClosed,
  onOpening,
  onOpenTui,
  create,
  onCreateChange,
}: {
  account: SignInController;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The dialog is about to take focus from this element. */
  onOpening?: (from: Element | null) => void;
  /** The dialog has closed: put focus where the person continues. */
  onClosed: () => void;
  /** Carry on in the TUI's own flow. */
  onOpenTui: () => void;
  /** The person asked to create a profile rather than sign in to one. */
  create?: boolean;
  onCreateChange?: (create: boolean) => void;
}) {
  const t = useStrings();
  const input = useRef<HTMLInputElement>(null);
  const handover = useRef<HTMLButtonElement>(null);
  const nameField = useRef<HTMLInputElement>(null);
  const choice = useRef<HTMLSelectElement>(null);
  const [revealed, setRevealed] = useState(false);
  const [unchosen, setUnchosen] = useState(false);
  const errorId = useId();
  const choiceErrorId = useId();
  const choiceHintId = useId();
  const status = account.status;
  // With no profile on this computer the dialog is the form that makes
  // one; with some, it is that form when the person asks for it.
  // While one is being made it stays that form, whatever else is asked.
  const creating =
    account.creating ||
    (account.canCreate &&
      account.offering &&
      (create === true || account.phase === "no-profile"));
  // Changing between the two forms moves the keyboard to the new one's
  // first field: what held it is gone.
  const wasCreating = useRef(creating);
  useEffect(() => {
    if (wasCreating.current !== creating && open)
      (creating ? nameField.current : input.current)?.focus();
    wasCreating.current = creating;
  }, [creating, open]);

  // A refused submission returns the keyboard to the field for the next try.
  const busy = account.busy;
  const wasBusy = useRef(busy);
  useEffect(() => {
    if (wasBusy.current && !busy && open) {
      const held = document.activeElement;
      // Unless the person has taken it somewhere else in the meantime.
      if (
        !held ||
        held === document.body ||
        input.current?.form?.contains(held)
      )
        input.current?.focus();
    }
    wasBusy.current = busy;
  }, [busy, open]);

  // Shown again before it had finished leaving, the dialog is never mounted
  // anew, so nothing would place focus in it: it is placed here, whenever
  // the dialog is opened.
  useEffect(() => {
    if (open) (nameField.current ?? input.current ?? handover.current)?.focus();
  }, [open]);

  // Nothing to show until the account is known: a dialog opened on a
  // guess would put the keyboard on a way out that is about to change.
  if (!status || account.phase === "checking" || account.phase === "starting")
    return null;

  const seconds = account.retrySeconds;
  const rejected = refusalCode(account.refusal) === "CREDENTIAL_REJECTED";
  // Where a password cannot help, the form is not offered: with no profile
  // the dialog offers the way to set one up, and with no services running it
  // says so in its title, as the rest of the window does.
  const setUpInTui = account.phase === "no-profile" && !creating;
  const servicesDown = account.phase === "services-down";
  const waitingForServices =
    account.startingServices && !status.runtimeAvailable;
  const answerable = !creating && status.runtimeAvailable && account.canSignIn;
  // The choice is offered only while nobody is signed in, from a list
  // that was read coherently.
  const choices =
    account.offering && account.profiles?.complete
      ? account.profiles.profiles
      : [];
  const named = account.target?.name ?? status.active_profile;
  const mustChoose = account.mustChoose;
  // A profile the host would not name as written can be signed in to only
  // while it is the selected one.
  const unnameable = choices.some((p) => !p.active && !nameable(p.name));
  // A refusal that hands over to the TUI is the explanation: no lead then
  // says it a second way.
  const lead = creating
    ? t("desktop.account.create.lead")
    : setUpInTui
      ? t("desktop.account.no_profile_lead")
      : servicesDown
        ? null
        : answerable
          ? t("desktop.signin.lead")
          : account.refusal
            ? null
            : t("desktop.signin.open_tui_hint");
  // Titled as a sign-in only where there is something to sign in with.
  const title = waitingForServices
    ? "desktop.signin.starting_services"
    : creating
      ? "desktop.account.create.title"
      : answerable
        ? "desktop.signin.title"
        : (accountLabel(account.phase) ?? "desktop.signin.title");

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        // Not put aside while a profile is being made: what becomes of it
        // is said here, and nowhere else.
        if (!next && account.creating) return;
        if (!next) {
          setRevealed(false);
          setUnchosen(false);
          onCreateChange?.(false);
        }
        onOpenChange(next);
      }}
    >
      <DialogContent
        className="sign-in"
        closeLabel={t("desktop.signin.dismiss")}
        {...(lead ? {} : { "aria-describedby": undefined })}
        onOpenAutoFocus={(event) => {
          onOpening?.(document.activeElement);
          // The first field where there is one, else the way on.
          const target = nameField.current ?? input.current ?? handover.current;
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
            <DialogTitle>{t(title)}</DialogTitle>
            {lead && <DialogDescription>{lead}</DialogDescription>}
          </div>
        </DialogHeader>

        {account.profiles && !account.profiles.complete && (
          <Alert tone="warning" role="status" icon={<Icon name="alert" />}>
            {t("desktop.signin.profiles_unread")}
          </Alert>
        )}

        {waitingForServices && <AccountLoading starting />}

        {creating ? (
          <CreateProfile
            account={account}
            nameField={nameField}
            onDone={() => onCreateChange?.(false)}
            {...(choices.length > 0
              ? { onBack: () => onCreateChange?.(false) }
              : {})}
          />
        ) : choices.length > 1 && answerable ? null : (
          named && <ProfileNamed name={named} />
        )}

        {!creating && account.created && (
          <Alert tone="success" role="status" icon={<Icon name="check" />}>
            {t("desktop.account.create.done", { name: account.created })}
          </Alert>
        )}

        {creating ? null : answerable ? (
          <form
            className="grid grid-cols-1 gap-4"
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              const field = input.current;
              if (!field || busy || seconds > 0) return;
              // With several profiles and none chosen there is nothing to
              // send a password to: the choice comes first.
              if (mustChoose) {
                setUnchosen(true);
                choice.current?.focus();
                return;
              }
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
            {named && (
              <input
                type="text"
                name="username"
                autoComplete="username"
                value={named}
                readOnly
                hidden
              />
            )}
            {choices.length > 1 && (
              <Field data-invalid={unchosen && mustChoose}>
                <FieldLabel htmlFor="profile-choice">
                  {t("desktop.signin.profile")}
                </FieldLabel>
                <NativeSelect
                  ref={choice}
                  id="profile-choice"
                  className="profile-choice"
                  value={account.target?.name ?? ""}
                  aria-invalid={(unchosen && mustChoose) || undefined}
                  // What is wrong with the choice, and why one of the
                  // profiles in it cannot be chosen: both are heard with it.
                  aria-describedby={
                    [
                      unchosen && mustChoose ? choiceErrorId : null,
                      unnameable ? choiceHintId : null,
                    ]
                      .filter(Boolean)
                      .join(" ") || undefined
                  }
                  onChange={(event) => {
                    // Not while an answer is pending: it is that profile's.
                    if (busy) return;
                    setUnchosen(false);
                    account.choose(event.target.value);
                  }}
                >
                  {mustChoose && (
                    <option value="" disabled>
                      {t("desktop.signin.choose_profile")}
                    </option>
                  )}
                  {choices.map((profile) => (
                    <option
                      key={profile.name}
                      value={profile.name}
                      disabled={!profile.active && !nameable(profile.name)}
                    >
                      {profile.name}
                    </option>
                  ))}
                </NativeSelect>
                <FieldError id={choiceErrorId}>
                  {unchosen && mustChoose && t("desktop.signin.choose_profile")}
                </FieldError>
                {unnameable && (
                  <FieldDescription
                    id={choiceHintId}
                    className="profile-unnameable"
                  >
                    {t("desktop.signin.unnameable")}
                  </FieldDescription>
                )}
              </Field>
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
        ) : setUpInTui ? null : (
          <Refusal refusal={account.refusal} seconds={seconds} />
        )}

        {!creating && servicesDown && account.canStartServices && (
          <Button
            className="w-full"
            pending={account.startingServices}
            onClick={() => void account.startServices()}
          >
            {t(
              account.startingServices
                ? "desktop.signin.starting_services"
                : "desktop.signin.start_services",
            )}
          </Button>
        )}

        {!creating && servicesDown && account.canInstallServices && (
          <div className="grid gap-2">
            <Button
              variant="outline"
              pending={account.startingServices}
              onClick={() => void account.startServices("user")}
            >
              {t("desktop.signin.install_user_services")}
            </Button>
            <Button
              variant="outline"
              pending={account.startingServices}
              onClick={() => void account.startServices("machine")}
            >
              {t("desktop.signin.install_machine_services")}
            </Button>
            <p className="text-sm text-muted-foreground">
              {t("desktop.signin.install_machine_permission")}
            </p>
          </div>
        )}

        {creating ? null : answerable ? (
          <>
            <Separator />
            {account.canCreate && account.offering && (
              <Button
                className="new-profile w-full"
                variant="outline"
                size="sm"
                aria-disabled={busy || undefined}
                onClick={busy ? undefined : () => onCreateChange?.(true)}
              >
                <Icon name="userAdd" />
                {t("desktop.account.new_profile")}
              </Button>
            )}
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              <p className="min-w-40 flex-1 text-sm text-muted-foreground">
                {t(
                  account.canCreate
                    ? "desktop.signin.recovery_hint"
                    : "desktop.signin.open_tui_hint",
                )}
              </p>
              <Button
                ref={handover}
                variant="outline"
                size="sm"
                aria-disabled={busy || undefined}
                onClick={busy ? undefined : onOpenTui}
              >
                {t("desktop.signin.open_tui")}
              </Button>
            </div>
          </>
        ) : (
          <Button ref={handover} className="w-full" onClick={onOpenTui}>
            {t(
              setUpInTui
                ? "desktop.account.create_profile"
                : "desktop.signin.open_tui",
            )}
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** The profile a password is for, where there is nothing to choose: named
 * under its own label, as a field is, so that it cannot be missed. */
function ProfileNamed({ name }: { name: string }) {
  const t = useStrings();
  const id = useId();
  return (
    <div
      className="profile-named grid grid-cols-1 gap-1.5"
      role="group"
      aria-labelledby={id}
    >
      <Label asChild>
        <span id={id}>{t("desktop.signin.profile")}</span>
      </Label>
      <span className="flex min-w-0 items-center gap-2">
        <Icon name="user" className="text-muted-foreground" />
        {/* Cut where it is long: the whole of it is its title. */}
        <span className="truncate font-medium" title={name}>
          {name}
        </span>
      </span>
    </div>
  );
}

/**
 * What a pane shows while the account withholds it: the status check in
 * flight, or what stands in the way with the ways forward. The TUI pane and
 * the calendar say it with this one component, so they cannot disagree. The
 * primary action takes `signInButton`, so focus has somewhere to go in every
 * phase.
 */
export function SignedOut({
  account,
  lead,
  quiet = false,
  onSignIn,
  onOpenTui,
  signInButton,
}: {
  account: SignInController;
  /** What signing in gives here, where a password can answer. The TUI's
   * own sentence where it is left out. */
  lead?: string;
  /** Beside another pane that says the same, the actions are drawn
   * quietly: one filled button in the window, not two. */
  quiet?: boolean;
  onSignIn: () => void;
  onOpenTui: () => void;
  signInButton?: RefObject<HTMLButtonElement | null>;
}) {
  const t = useStrings();
  const gate = GATES[account.phase];
  if (
    account.phase === "checking" ||
    account.phase === "starting" ||
    (account.startingServices && !account.status?.runtimeAvailable)
  )
    return (
      <AccountLoading
        starting={account.phase === "starting" || account.startingServices}
        quiet={quiet}
      />
    );
  if (!gate)
    return (
      <Empty role="status">
        <Spinner />
        <EmptyDescription>{t("desktop.signin.checking")}</EmptyDescription>
      </Empty>
    );
  const password = account.canSignIn;
  // With no profile on this computer, and a host that can make one, the way
  // on is the form that does: the dialog is that form in this phase.
  const makes = account.phase === "no-profile" && account.canCreate;
  // A refusal no password can answer takes the lead's place: it is why the
  // only way on is the TUI.
  const refused =
    !password && account.refusal && account.phase !== "no-profile";
  return (
    <Empty>
      <EmptyMedia>
        <Icon name={gate.icon} />
      </EmptyMedia>
      <div className="grid gap-1">
        <EmptyTitle>{t(gate.title)}</EmptyTitle>
        {gate.lead && !refused && (
          <EmptyDescription>
            {makes
              ? t("desktop.account.first_run_lead")
              : password && lead
                ? lead
                : t(gate.lead)}
          </EmptyDescription>
        )}
      </div>
      {refused && (
        <div className="w-full max-w-dialog text-left">
          <Refusal
            refusal={account.refusal}
            seconds={account.retrySeconds}
            quiet={quiet}
          />
        </div>
      )}
      <div className="flex flex-wrap justify-center gap-2">
        {(password || makes) && (
          <Button
            ref={signInButton}
            variant={quiet ? "outline" : "primary"}
            onClick={onSignIn}
          >
            {t(makes ? "desktop.account.new_profile" : "desktop.signin.submit")}
          </Button>
        )}
        <Button
          ref={password || makes ? undefined : signInButton}
          variant={password || makes ? "ghost" : quiet ? "outline" : "primary"}
          aria-disabled={account.busy || undefined}
          onClick={account.busy ? undefined : onOpenTui}
        >
          {t(
            account.phase === "no-profile" && !makes
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
 * It closes with the line that sets it apart from what follows, so settings
 * draws none where there is no account to show.
 */
export function Account({
  account,
  onSignIn,
  onSignOut,
  onSwitch,
  onOpenTui,
}: {
  account: SignInController;
  onSignIn: () => void;
  onSignOut: () => void;
  /** Sign out of this profile and go on to the choice of another. */
  onSwitch?: () => void;
  onOpenTui: () => void;
}) {
  const t = useStrings();
  const profileId = useId();
  const sessionId = useId();
  const status = account.status;
  const phase = account.phase;
  if (!status?.supported) return null;
  const label = accountLabel(phase === "no-profile" ? "signed-out" : phase);
  // The TUI's own flow is the way on where the account is not settled and
  // no password can settle it. With no profile, that is the profile's line.
  const handover =
    !account.canSignIn &&
    (phase === "signed-out" ||
      phase === "unknown" ||
      phase === "services-down");
  // The profile is shown where it is known, by name or as none. With no
  // runtime to ask it is simply not known, and the section is left out.
  const profile = status.active_profile !== null || phase === "no-profile";
  return (
    <>
      {profile && (
        <section className="grid grid-cols-1 gap-2" aria-labelledby={profileId}>
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
                title={status.active_profile ?? undefined}
              >
                {status.active_profile ?? t("desktop.account.no_profile")}
              </span>
            </span>
            {phase === "no-profile" && (
              <Button
                variant="outline"
                size="sm"
                onClick={account.canCreate ? onSignIn : onOpenTui}
              >
                {t(
                  account.canCreate
                    ? "desktop.account.new_profile"
                    : "desktop.account.create_profile",
                )}
              </Button>
            )}
          </div>
        </section>
      )}
      <section
        className="account grid grid-cols-1 gap-2"
        aria-labelledby={sessionId}
      >
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
            <span className="flex flex-wrap items-center gap-2">
              {account.canCreate && onSwitch && (
                <Button
                  className="switch-profile"
                  variant="ghost"
                  size="sm"
                  aria-disabled={account.busy || undefined}
                  onClick={account.busy ? undefined : onSwitch}
                >
                  <Icon name="swap" />
                  {t("desktop.account.switch_profile")}
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                pending={account.busy}
                onClick={onSignOut}
              >
                {!account.busy && <Icon name="signOut" />}
                {t("desktop.account.sign_out")}
              </Button>
            </span>
          ) : account.canSignIn ? (
            <Button variant="outline" size="sm" onClick={onSignIn}>
              {t("desktop.signin.submit")}
            </Button>
          ) : handover ? (
            <Button variant="outline" size="sm" onClick={onOpenTui}>
              {t("desktop.signin.open_tui")}
            </Button>
          ) : null}
        </div>
        {handover && (
          <Refusal refusal={account.refusal} seconds={account.retrySeconds} />
        )}
        {phase === "signed-in" && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.account.sign_out_hint")}
          </p>
        )}
        {phase === "signed-in" && account.canCreate && (
          <p className="switch-hint text-sm text-muted-foreground">
            {t("desktop.account.switch_hint")}
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
      <Separator />
    </>
  );
}
