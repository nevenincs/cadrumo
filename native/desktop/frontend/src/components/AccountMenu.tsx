import { useEffect, useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icon";
import type { SignInController } from "../shell/signIn";
import { nameable } from "../shell/profiles";
import { useStrings } from "../shell/strings";
import { accountLabel } from "./accountWords";
import { AccountRefusal } from "./account/AccountRefusal";

export function AccountMenu({
  account,
  onSignIn,
  onSignOut,
  onCreate,
  onOpenTui,
}: {
  account: SignInController;
  onSignIn: () => void;
  onSignOut: () => void;
  onCreate: () => void;
  onOpenTui: () => void;
}) {
  const t = useStrings();
  const [open, setOpen] = useState(false);
  const transferredFocus = useRef(false);
  const transfer = (action: () => void) => {
    transferredFocus.current = true;
    action();
  };
  const failure = account.signOutFailure;
  useEffect(() => {
    if (failure) setOpen(true);
  }, [failure]);
  const phase = account.phase;
  const profile = account.target?.name ?? account.status?.active_profile;
  const label = accountLabel(phase);
  const signedIn = phase === "signed-in";
  const profileText =
    profile ??
    t(
      account.mustChoose
        ? "desktop.signin.choose_profile"
        : phase === "no-profile"
          ? "desktop.account.no_profile"
          : (label ?? "desktop.account.unknown"),
    );
  const choices =
    account.offering && account.profiles?.complete
      ? account.profiles.profiles
      : [];
  const handover =
    ((!account.canSignIn && account.gated) || phase === "no-profile") &&
    phase !== "checking" &&
    phase !== "starting";
  const hasActions =
    signedIn ||
    choices.length > 0 ||
    account.canSignIn ||
    (account.offering && account.canCreate) ||
    handover;
  return (
    <DropdownMenu
      modal={false}
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) account.settle();
      }}
    >
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="profile-trigger text-foreground"
          aria-haspopup="dialog"
        >
          <span className="sr-only">
            {t("desktop.titlebar.profile_menu")}:{" "}
          </span>
          <Icon name="user" />
          <span className="profile-name" title={profile ?? undefined}>
            {profileText}
          </span>
          {label && (
            <span
              className={`profile-status ${signedIn ? "signed-in" : "signed-out"}`}
            >
              <span aria-hidden="true" />
              {t(label)}
            </span>
          )}
          <Icon name="chevronDown" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="account-menu"
        role="dialog"
        aria-orientation={undefined}
        aria-label={t("desktop.titlebar.profile_menu")}
        onCloseAutoFocus={(event) => {
          if (transferredFocus.current) event.preventDefault();
          transferredFocus.current = false;
        }}
      >
        <div className="profile-menu-heading">
          <span>{t("desktop.signin.profile")}</span>
          <strong title={profile ?? undefined}>{profileText}</strong>
          {label && <span>{t(label)}</span>}
        </div>
        <DropdownMenuSeparator />
        <div
          role={hasActions ? "menu" : undefined}
          aria-label={
            hasActions ? t("desktop.titlebar.profile_menu") : undefined
          }
        >
          {signedIn ? (
            <>
              <DropdownMenuItem
                disabled={account.busy}
                onSelect={(event) => {
                  event.preventDefault();
                  onSignOut();
                }}
              >
                <Icon name="signOut" />
                {t("desktop.account.sign_out")}
              </DropdownMenuItem>
            </>
          ) : (
            <>
              {choices.map((choice) => (
                <DropdownMenuItem
                  key={choice.name}
                  disabled={
                    account.busy || (!choice.active && !nameable(choice.name))
                  }
                  onSelect={() => {
                    account.choose(choice.name);
                    transfer(onSignIn);
                  }}
                >
                  <Icon name={profile === choice.name ? "check" : "user"} />
                  <span className="min-w-0 break-words">{choice.name}</span>
                </DropdownMenuItem>
              ))}
              {choices.length > 0 && <DropdownMenuSeparator />}
              {account.canSignIn && (
                <DropdownMenuItem
                  disabled={account.busy}
                  onSelect={() => transfer(onSignIn)}
                >
                  <Icon name="lock" />
                  {t("desktop.signin.submit")}
                </DropdownMenuItem>
              )}
              {account.offering && account.canCreate && (
                <DropdownMenuItem
                  disabled={account.busy}
                  onSelect={() => transfer(onCreate)}
                >
                  <Icon name="userAdd" />
                  {t("desktop.account.new_profile")}
                </DropdownMenuItem>
              )}
              {handover && (
                <DropdownMenuItem
                  disabled={account.busy}
                  onSelect={() => transfer(onOpenTui)}
                >
                  <Icon name="tui" />
                  {t(
                    phase === "no-profile"
                      ? "desktop.account.create_profile"
                      : "desktop.signin.open_tui",
                  )}
                </DropdownMenuItem>
              )}
            </>
          )}
        </div>
        {signedIn && (
          <>
            <p className="profile-menu-hint">
              {t("desktop.account.sign_out_hint")}
            </p>
            {account.canCreate && (
              <p className="profile-menu-hint">
                {t("desktop.account.switch_hint")}
              </p>
            )}
          </>
        )}
        {account.profiles && !account.profiles.complete && (
          <Alert tone="warning" role="status" icon={<Icon name="alert" />}>
            {t("desktop.signin.profiles_unread")}
          </Alert>
        )}
        {!account.canSignIn && (
          <AccountRefusal
            refusal={account.refusal}
            seconds={account.retrySeconds}
          />
        )}
        {account.remaining &&
          account.remaining.remainingAccess.automationEnabled !== false && (
            <Alert icon={<Icon name="info" />}>
              {t("desktop.account.remaining_access")}
            </Alert>
          )}
        {failure && (
          <Alert tone="danger" role="alert" icon={<Icon name="alert" />}>
            {t("desktop.account.sign_out_failed", { code: failure.code })}
          </Alert>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
