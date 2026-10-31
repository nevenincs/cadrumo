import { useEffect, useRef, useState, type ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuList,
  DropdownMenuNote,
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
  onAbout,
  onProfile,
  onManage,
  google,
}: {
  account: SignInController;
  onSignIn: () => void;
  onSignOut: () => void;
  onCreate: () => void;
  /** Opens the About dialog, where the host can say what is installed. */
  onAbout?: () => void;
  onProfile?: () => void;
  onManage?: () => void;
  google?: ReactNode;
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
  // The state in words, where the profile's name leaves it unsaid.
  const status = label && profile ? t(label) : null;
  const choices =
    account.offering && account.profiles?.complete
      ? account.profiles.profiles
      : [];
  const hasActions =
    signedIn ||
    choices.length > 0 ||
    account.canSignIn ||
    (account.offering && account.canCreate) ||
    !!onManage ||
    !!onAbout;
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
          {/* One label: the profile, or the state where there is none. A
              named profile's state is its dot, and the menu says it in words. */}
          {status && (
            <span
              className={`profile-status ${signedIn ? "signed-in" : "signed-out"}`}
              aria-hidden="true"
            />
          )}
          <span className="profile-name" title={profile ?? undefined}>
            {profileText}
          </span>
          {status && <span className="sr-only">, {status}</span>}
          <Icon name="chevronDown" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        // Unstyled: the scenarios find the menu by it.
        className="account-menu max-w-palette-max"
        role="dialog"
        aria-orientation={undefined}
        aria-label={t("desktop.titlebar.profile_menu")}
        onCloseAutoFocus={(event) => {
          if (transferredFocus.current) event.preventDefault();
          transferredFocus.current = false;
        }}
      >
        <div className="grid gap-1 px-2.5 py-2 wrap-anywhere">
          <span className="text-xs text-muted-foreground">
            {t("desktop.signin.profile")}
          </span>
          <strong className="truncate" title={profile ?? undefined}>
            {profileText}
          </strong>
          {status && (
            <span className="text-xs text-muted-foreground">{status}</span>
          )}
        </div>
        <DropdownMenuSeparator />
        {hasActions && (
          <DropdownMenuList aria-label={t("desktop.titlebar.profile_menu")}>
            {signedIn ? (
              <>
                {onProfile && (
                  <DropdownMenuItem
                    icon="user"
                    onSelect={() => transfer(onProfile)}
                  >
                    {t("desktop.profile.title")}
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem
                  icon="signOut"
                  disabled={account.busy}
                  onSelect={(event) => {
                    event.preventDefault();
                    onSignOut();
                  }}
                >
                  {t("desktop.account.sign_out")}
                </DropdownMenuItem>
              </>
            ) : (
              <>
                {choices.map((choice) => (
                  <DropdownMenuItem
                    key={choice.name}
                    icon={profile === choice.name ? "check" : "user"}
                    disabled={
                      account.busy || (!choice.active && !nameable(choice.name))
                    }
                    onSelect={() => {
                      account.choose(choice.name);
                      transfer(onSignIn);
                    }}
                  >
                    <span className="min-w-0 break-words">{choice.name}</span>
                  </DropdownMenuItem>
                ))}
                {choices.length > 0 && <DropdownMenuSeparator />}
                {account.canSignIn && (
                  <DropdownMenuItem
                    icon="lock"
                    disabled={account.busy}
                    onSelect={() => transfer(onSignIn)}
                  >
                    {t("desktop.signin.submit")}
                  </DropdownMenuItem>
                )}
                {account.offering && account.canCreate && (
                  <DropdownMenuItem
                    icon="userAdd"
                    disabled={account.busy}
                    onSelect={() => transfer(onCreate)}
                  >
                    {t("desktop.account.new_profile")}
                  </DropdownMenuItem>
                )}
              </>
            )}
            {onManage && (
              <DropdownMenuItem
                icon="user"
                disabled={account.busy}
                onSelect={() => transfer(onManage)}
              >
                {t("desktop.account.manage.title")}
              </DropdownMenuItem>
            )}
            {onAbout && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  icon="info"
                  onSelect={() => transfer(onAbout)}
                >
                  {t("desktop.about.open")}
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuList>
        )}
        {signedIn && (
          <>
            <DropdownMenuNote className="max-w-dialog">
              {t("desktop.account.sign_out_hint")}
            </DropdownMenuNote>
            {account.canCreate && (
              <DropdownMenuNote className="max-w-dialog">
                {t("desktop.account.switch_hint")}
              </DropdownMenuNote>
            )}
          </>
        )}
        {signedIn && google && (
          <>
            <DropdownMenuSeparator />
            <div className="px-2 py-2">{google}</div>
          </>
        )}
        {account.profiles && !account.profiles.complete && (
          <Alert tone="warning" role="status" icon={<Icon name="alert" />}>
            {t("desktop.signin.profiles_unread")}
          </Alert>
        )}
        {/* The reason the last try failed, beside the sign-in it leaves open. */}
        <AccountRefusal
          refusal={account.refusal}
          seconds={account.retrySeconds}
        />
        {/* Only what the product says stands is said. The saved setting
            stays after a sign-out; whether a key can still admit is a
            separate answer, and null is no answer. */}
        {account.remaining?.remainingAccess.automationAccessRemains ===
          true && (
          <Alert icon={<Icon name="info" />}>
            {t("desktop.account.remaining_access")}
          </Alert>
        )}
        {failure && (
          <Alert tone="danger" role="alert" icon={<Icon name="alert" />}>
            {t("desktop.account.sign_out_failed")}
          </Alert>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
