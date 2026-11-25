import { useMemo, type Dispatch, type SetStateAction } from "react";
import { canSignInGoogle } from "../components/setup/setupWords";
import type { Action } from "./actions";
import type { Host } from "./host";
import type { SetupControl } from "./setup";
import type { Translate } from "./strings";

type Flag = Dispatch<SetStateAction<boolean>>;

/** The account's: signing in and out, the profiles, Google, and the census from any page. */
export function useAccountActions({
  t,
  mayEnterPassword,
  askSignIn,
  canCreateProfile,
  offersProfiles,
  askNewProfile,
  signedIn,
  signOut,
  setupOffered,
  setupSnapshot,
  setup,
  host,
  setSignInDismissed,
  setManagingProfiles,
  switchProfile,
  askCenso,
}: {
  t: Translate;
  mayEnterPassword: boolean;
  askSignIn: () => void;
  canCreateProfile: boolean;
  offersProfiles: boolean;
  askNewProfile: () => void;
  signedIn: boolean;
  signOut: () => void;
  setupOffered: boolean;
  setupSnapshot: SetupControl["snapshot"];
  setup: SetupControl;
  host: Host;
  setSignInDismissed: Flag;
  setManagingProfiles: Flag;
  switchProfile: () => void;
  askCenso: () => void;
}): Action[] {
  return useMemo<Action[]>(
    () => [
      {
        id: "account.signIn",
        label: t("desktop.signin.submit"),
        group: "account",
        icon: "lock",
        keywords: t("desktop.palette.keywords.sign_in"),
        enabled: () => mayEnterPassword,
        run: askSignIn,
      },
      {
        id: "account.createProfile",
        label: t("desktop.account.new_profile"),
        group: "account",
        icon: "userAdd",
        keywords: t("desktop.palette.keywords.create_profile"),
        enabled: () => canCreateProfile && offersProfiles,
        run: askNewProfile,
      },
      {
        id: "account.signOut",
        label: t("desktop.account.sign_out"),
        group: "account",
        icon: "signOut",
        keywords: t("desktop.palette.keywords.sign_out"),
        enabled: () => signedIn,
        run: signOut,
      },
      {
        // The profile's own Google sign-in; not part of setup.
        id: "account.google",
        label: t("desktop.google.palette_sign_in"),
        group: "account",
        icon: "user",
        keywords: t("desktop.palette.keywords.google_sign_in"),
        enabled: () =>
          signedIn &&
          setupOffered &&
          canSignInGoogle(setupSnapshot?.google ?? null),
        run: () => setup.signInGoogle(),
      },
      {
        id: "account.manageProfiles",
        label: t("desktop.account.manage.title"),
        group: "account",
        icon: "users",
        keywords: t("desktop.palette.keywords.manage_profiles"),
        enabled: () => host.profiles !== undefined,
        run: () => {
          setSignInDismissed(true);
          setManagingProfiles(true);
        },
      },
      {
        id: "account.switchProfile",
        label: t("desktop.account.switch_profile"),
        group: "account",
        icon: "swap",
        keywords: t("desktop.palette.keywords.switch_profile"),
        enabled: () => signedIn && canCreateProfile,
        run: switchProfile,
      },
      {
        // The one census flow, from any page: the profile page runs it.
        id: "census.sync",
        label: t("desktop.profile.censo.title"),
        group: "profile",
        icon: "sync",
        keywords: t("desktop.palette.keywords.census_sync"),
        enabled: () => signedIn && !!host.censo && !!host.userProfile,
        run: askCenso,
      },
    ],
    [
      t,
      mayEnterPassword,
      askSignIn,
      canCreateProfile,
      offersProfiles,
      askNewProfile,
      signedIn,
      signOut,
      setupOffered,
      setupSnapshot,
      setup,
      host,
      setSignInDismissed,
      setManagingProfiles,
      switchProfile,
      askCenso,
    ],
  );
}
