import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import type { SignInOpener } from "../components/AccountDialogs";
import type { Host } from "./host";
import type { useNavigator } from "./navigation/useNavigator";
import type { SignInController } from "./signIn";
import { usePersonActivity } from "./usePersonActivity";

/** The window's way through the account: when the sign-in dialog is asked
 * for or put aside, as the sign-in or as the form that creates a profile,
 * signing out and switching profile past the navigation guards, and whose
 * views the window reads. */
export function useSignInFlow({
  host,
  account,
  guardNavigation,
  setSettingsOpen,
}: {
  host: Host;
  account: SignInController;
  guardNavigation: ReturnType<typeof useNavigator>["guard"];
  setSettingsOpen: Dispatch<SetStateAction<boolean>>;
}) {
  // What held focus when the sign-in dialog was asked for, and whether
  // that was in the calendar: the control itself may be gone by the close.
  const signInOpener = useRef<SignInOpener>(null);
  // The sign-in dialog opens by itself whenever the TUI becomes gated; a
  // person who dismisses it, or who has just signed out here, reopens it.
  const [signInDismissed, setSignInDismissed] = useState(false);
  // The dialog as the form that creates a profile, where one was asked for.
  const [creatingProfile, setCreatingProfile] = useState(false);
  const [managingProfiles, setManagingProfiles] = useState(false);
  const signInButton = useRef<HTMLButtonElement>(null);

  const gated = account.gated;
  const phase = account.phase;
  const signedIn = phase === "signed-in";
  // The sign-in form is asked for by a gate that withholds the TUI, and by a
  // session the runtime keeps suspended that only the password can bring back.
  const signInAsked = gated || account.reconnecting?.passwordRequired === true;
  usePersonActivity(host, signedIn);
  const accountRef = useRef(account);
  accountRef.current = account;
  const signOut = useCallback(() => {
    guardNavigation({ kind: "sign_out" }, () => {
      // Signing out here is not a reason to ask for the password again.
      setSignInDismissed(true);
      void accountRef.current.signOut();
    });
  }, [guardNavigation]);
  // The palette shortcut enters the same account flow as the header.
  const switchProfile = useCallback(() => {
    guardNavigation({ kind: "switch" }, () => {
      setSettingsOpen(false);
      signInOpener.current = null;
      setSignInDismissed(false);
      void accountRef.current.signOut();
    });
  }, [guardNavigation, setSettingsOpen]);
  useEffect(() => {
    if (signInAsked) return;
    // Admitted: the next time the gate closes, the dialog opens again, and
    // as the sign-in, whatever it was last asked to be.
    setSignInDismissed(false);
    setCreatingProfile(false);
  }, [signInAsked]);
  const signOutFailed = account.signOutFailure !== null;
  useEffect(() => {
    // A sign-out that failed leaves the person signed in: the next time the
    // gate closes it is not by their choice, so the dialog opens.
    if (signOutFailed) setSignInDismissed(false);
  }, [signOutFailed]);
  const mayEnterPassword = account.canSignIn;

  // Whose views are read: the signed-in profile's. Where the platform signs
  // in inside the TUI the shell cannot tell, so it asks and shows the answer.
  const reader =
    signedIn || phase === "unsupported"
      ? (account.status?.active_profile ?? "")
      : null;
  const recheckAccount = useCallback(() => accountRef.current.recheck(), []);
  const askSignIn = useCallback(() => {
    const element = document.activeElement;
    signInOpener.current = {
      element,
      calendar: element?.closest(".calendar-page") != null,
    };
    setSignInDismissed(false);
  }, []);
  const canCreateProfile = account.canCreate;
  // Another profile, or a new one, only while nobody is signed in.
  const offersProfiles = account.offering;
  const askNewProfile = useCallback(() => {
    setSettingsOpen(false);
    askSignIn();
    setCreatingProfile(true);
  }, [askSignIn, setSettingsOpen]);
  // Whether the dialog stands over the window: the gate asks for it and it
  // was not put aside, or the profiles are being managed.
  const dialogHeld = (signInAsked && !signInDismissed) || managingProfiles;

  return {
    accountRef,
    signInOpener,
    signInButton,
    signInDismissed,
    setSignInDismissed,
    creatingProfile,
    setCreatingProfile,
    managingProfiles,
    setManagingProfiles,
    gated,
    phase,
    signedIn,
    signInAsked,
    signOut,
    switchProfile,
    mayEnterPassword,
    reader,
    recheckAccount,
    askSignIn,
    canCreateProfile,
    offersProfiles,
    askNewProfile,
    dialogHeld,
  };
}
