import type { Dispatch, RefObject, SetStateAction } from "react";
import type { Host, TerminalKind } from "../shell/host";
import type { PanelTab } from "../shell/layout";
import type { SignInController } from "../shell/signIn";
import { ManageProfiles } from "./account/ManageProfiles";
import type { DocsFrameApi } from "./DocsFrame";
import { SignInDialog } from "./SignIn";

/** What held focus when the sign-in dialog was asked for, and whether that
 * was in the calendar. */
export type SignInOpener = {
  element: Element | null;
  calendar: boolean;
} | null;

type Flag = Dispatch<SetStateAction<boolean>>;

/** The sign-in dialog, which also creates a profile, and the profiles it
 * leads to; and where focus goes when the dialog is put aside. */
export function AccountDialogs({
  host,
  account,
  accountRef,
  signInAsked,
  signInDismissed,
  setSignInDismissed,
  creatingProfile,
  setCreatingProfile,
  managingProfiles,
  setManagingProfiles,
  askNewProfile,
  signInOpener,
  signInButton,
  calendarPage,
  docs,
  grantFocus,
  focusView,
  focusRail,
  panelMaximized,
  tab,
  tuiVisible,
}: {
  host: Host;
  account: SignInController;
  accountRef: RefObject<SignInController>;
  signInAsked: boolean;
  signInDismissed: boolean;
  setSignInDismissed: Flag;
  creatingProfile: boolean;
  setCreatingProfile: Flag;
  managingProfiles: boolean;
  setManagingProfiles: Flag;
  askNewProfile: () => void;
  signInOpener: RefObject<SignInOpener>;
  signInButton: RefObject<HTMLButtonElement | null>;
  calendarPage: RefObject<HTMLElement | null>;
  docs: RefObject<DocsFrameApi | null>;
  grantFocus: () => void;
  focusView: (view: TerminalKind | "logs") => void;
  focusRail: () => void;
  panelMaximized: boolean;
  tab: PanelTab;
  tuiVisible: boolean;
}) {
  return (
    <>
      {managingProfiles && host.profiles && (
        <ManageProfiles
          profiles={host.profiles}
          account={account}
          onClose={() => setManagingProfiles(false)}
          onCreate={() => {
            setManagingProfiles(false);
            askNewProfile();
          }}
        />
      )}
      <SignInDialog
        account={account}
        open={signInAsked && !signInDismissed && !managingProfiles}
        onOpenChange={(open) => {
          setSignInDismissed(!open);
          if (!open) accountRef.current.settle();
        }}
        create={creatingProfile}
        onCreateChange={setCreatingProfile}
        onManage={
          host.profiles
            ? () => {
                setSignInDismissed(true);
                setManagingProfiles(true);
              }
            : undefined
        }
        // Opened by the gate closing rather than by a press, the dialog
        // still took focus from somewhere: that is where it returns.
        onOpening={(from) => {
          signInOpener.current ??= {
            element: from,
            calendar: from?.closest(".calendar-page") != null,
          };
        }}
        // Put aside, focus goes back to what the dialog took it from
        // while that is on screen, else to the page it was in, else to
        // the TUI's way back in. Admitted, it goes on: to the calendar
        // the sign-in was asked from, else to the TUI that has started.
        // The rail is the last resort of both.
        onClosed={() => {
          const opener = signInOpener.current;
          signInOpener.current = null;
          // Something asked for while the dialog was up comes first.
          grantFocus();
          // The dialog takes a moment to leave. Focus the person has
          // already put somewhere in that moment is left where it is.
          const held = document.activeElement;
          if (held && held !== document.body && !held.closest(".sign-in"))
            return;
          const shown = (element: Element | null): element is HTMLElement =>
            element instanceof HTMLElement &&
            element.isConnected &&
            element.offsetParent !== null;
          const from = opener?.element ?? null;
          const page = calendarPage.current;
          const frame = document.querySelector(".docs-frame");
          if (account.gated) {
            if (shown(from)) from.focus();
            else if (opener?.calendar && shown(page)) page.focus();
            else if (shown(signInButton.current)) signInButton.current.focus();
            else if (shown(page)) page.focus();
            else if (shown(frame) && docs.current) docs.current.focus();
            else focusRail();
          } else if (opener?.calendar && shown(page)) page.focus();
          else if (panelMaximized) focusView(tab);
          else if (tuiVisible) focusView("tui");
          else if (shown(page)) page.focus();
          else if (shown(frame) && docs.current) docs.current.focus();
          else focusRail();
        }}
      />
    </>
  );
}
