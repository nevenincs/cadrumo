import { useId } from "react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { GoogleAccount as GoogleAccountState } from "../ipc/contract";
import { useStrings } from "../shell/strings";
import { canSignInGoogle, googleWords } from "./setup/setupWords";

/** The signed-in profile's Google account in Settings: whether it is signed
 * in, and the one act that changes that. It is the profile's own sign-in,
 * not a component of Cadrumo, so it stands apart from setup. */
export function GoogleAccount({
  google,
  disabled,
  onSignIn,
  onSignOut,
}: {
  google: GoogleAccountState;
  disabled?: boolean;
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
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2">
        <p
          role="status"
          className="flex min-w-0 flex-1 items-center gap-2 text-sm wrap-anywhere text-foreground"
        >
          {(busy || google.state === null) && <Spinner />}
          {googleWords(t, google)}
        </p>
        {signedIn ? (
          <Button
            variant="outline"
            size="sm"
            aria-label={t("desktop.google.sign_out_label")}
            disabled={disabled || busy}
            onClick={onSignOut}
          >
            {t("desktop.google.sign_out")}
          </Button>
        ) : (
          canSignInGoogle(google) && (
            <Button
              variant="outline"
              size="sm"
              aria-label={t("desktop.google.sign_in_label")}
              disabled={disabled}
              onClick={onSignIn}
            >
              {t("desktop.google.sign_in")}
            </Button>
          )
        )}
      </div>
    </section>
  );
}
