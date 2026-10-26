import { useId } from "react";
import { Alert } from "@/components/ui/alert";
import {
  DropdownMenuItem,
  DropdownMenuList,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";
import type { GoogleAccount as GoogleAccountState } from "../ipc/contract";
import { useStrings } from "../shell/strings";
import { canSignInGoogle, googleWords, refusalWords } from "./setup/setupWords";

/** The signed-in profile's Google account: whether it is signed
 * in, and the one act that changes that. It is the profile's own sign-in,
 * not a component of Cadrumo, so it stands apart from setup. */
export function GoogleAccount({
  google,
  disabled,
  refusal,
  onSignIn,
  onSignOut,
}: {
  google: GoogleAccountState;
  disabled?: boolean;
  refusal?: string | null;
  onSignIn: () => void;
  onSignOut: () => void;
}) {
  const t = useStrings();
  const headingId = useId();
  const busy = google.stage === "signing_in" || google.stage === "signing_out";
  const signedIn = google.state === "signed_in";
  return (
    <section
      className="google-account grid gap-2"
      data-google-account={google.state ?? "unread"}
      aria-labelledby={headingId}
    >
      <h3 id={headingId} className="text-sm font-medium text-muted-foreground">
        {t("desktop.google.title")}
      </h3>
      <div className="grid min-w-0 gap-2">
        <p
          role="status"
          className="flex min-w-0 flex-1 items-center gap-2 text-sm wrap-anywhere text-foreground"
        >
          {(busy || google.state === null) && <Spinner />}
          {googleWords(t, google)}
        </p>
        {(signedIn || canSignInGoogle(google) || busy) && (
          <DropdownMenuList aria-labelledby={headingId}>
            <DropdownMenuItem
              icon={signedIn ? "signOut" : "user"}
              aria-label={t(
                signedIn
                  ? "desktop.google.sign_out_label"
                  : "desktop.google.sign_in_label",
              )}
              disabled={disabled || busy}
              onSelect={(event) => {
                event.preventDefault();
                if (signedIn) onSignOut();
                else onSignIn();
              }}
            >
              {t(
                signedIn ? "desktop.google.sign_out" : "desktop.google.sign_in",
              )}
            </DropdownMenuItem>
          </DropdownMenuList>
        )}
      </div>
      {refusal && <Alert role="alert">{refusalWords(t, refusal)}</Alert>}
    </section>
  );
}
