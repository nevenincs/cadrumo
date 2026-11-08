import type { Dispatch, SetStateAction } from "react";
import type { AboutState } from "../shell/about";
import type { Host } from "../shell/host";
import type { Layout } from "../shell/layout";
import type { useNavigator } from "../shell/navigation/useNavigator";
import type { SignInController } from "../shell/signIn";
import type { Translate } from "../shell/strings";
import type { useFullscreen } from "../shell/useFullscreen";
import type { useSignInFlow } from "../shell/useSignInFlow";
import type { useWindowSetup } from "../shell/useWindowSetup";
import { AccountMenu } from "./AccountMenu";
import { GoogleAccount } from "./GoogleAccount";
import { Titlebar } from "./Titlebar";

type Flag = Dispatch<SetStateAction<boolean>>;

/** The window's title bar and the account menu it carries: signing in,
 * the profile, the Google account, the profiles and About. */
export function WindowTitlebar({
  host,
  t,
  account,
  signIn,
  setup,
  fullscreen,
  guardNavigation,
  say,
  about,
  setSettingsOpen,
  setAboutOpen,
  setPage,
  setLayout,
}: {
  host: Host;
  t: Translate;
  account: SignInController;
  signIn: ReturnType<typeof useSignInFlow>;
  setup: ReturnType<typeof useWindowSetup>;
  fullscreen: ReturnType<typeof useFullscreen>;
  guardNavigation: ReturnType<typeof useNavigator>["guard"];
  say: (text: string) => void;
  about: AboutState | null;
  setSettingsOpen: Flag;
  setAboutOpen: Flag;
  setPage: (next: Layout["page"]) => void;
  setLayout: Dispatch<SetStateAction<Layout>>;
}) {
  const {
    signedIn,
    signInOpener,
    setCreatingProfile,
    setSignInDismissed,
    setManagingProfiles,
    signOut,
    askNewProfile,
  } = signIn;
  const { setupOffered, setupSnapshot } = setup;
  return (
    <Titlebar
      host={host}
      onPresentation={fullscreen.observe}
      guardClose={(proceed) => guardNavigation({ kind: "close" }, proceed)}
      onFailure={() => say(t("desktop.titlebar.failed"))}
    >
      <AccountMenu
        account={account}
        onSignIn={() => {
          setSettingsOpen(false);
          signInOpener.current = null;
          setCreatingProfile(false);
          setSignInDismissed(false);
        }}
        google={
          signedIn && setupOffered && setupSnapshot ? (
            <GoogleAccount
              google={setupSnapshot.google}
              disabled={setup.setup.pending || account.busy}
              refusal={
                setup.setup.refusal?.item === null
                  ? setup.setup.refusal.code
                  : null
              }
              onSignIn={setup.setup.signInGoogle}
              onSignOut={setup.setup.signOutGoogle}
            />
          ) : undefined
        }
        onProfile={
          host.userProfile
            ? () => {
                setPage("profile");
                setLayout((current) => ({
                  ...current,
                  maximized: null,
                }));
              }
            : undefined
        }
        onSignOut={signOut}
        onCreate={askNewProfile}
        onManage={
          host.profiles
            ? () => {
                setSignInDismissed(true);
                setManagingProfiles(true);
              }
            : undefined
        }
        onAbout={
          about
            ? () => {
                setSettingsOpen(false);
                setAboutOpen(true);
              }
            : undefined
        }
      />
    </Titlebar>
  );
}
