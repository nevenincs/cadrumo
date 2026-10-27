import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { Reconnecting } from "../ipc/contract";
import { useStrings } from "../shell/strings";

/**
 * Said while the runtime keeps the window's session suspended after the
 * profile's worker was lost: the person is not signed out, and the window
 * carries on by itself once the session is back. Only when the saved sign-in
 * could not bring it back is there something to do, which is to type the
 * password.
 */
export function ReconnectingNotice({
  reconnecting,
  onSignIn,
}: {
  reconnecting: Reconnecting | null;
  /** Opens the password form, which a person may have put aside. */
  onSignIn: () => void;
}) {
  const t = useStrings();
  if (!reconnecting) return null;
  return (
    <div
      data-slot="reconnecting"
      className="pointer-events-none fixed inset-x-0 top-16 z-(--layer-toast) flex justify-center px-4"
    >
      <Alert
        tone="warning"
        icon={<Icon name="clock" />}
        className="pointer-events-auto max-w-dialog shadow-overlay"
      >
        <AlertTitle>{t("desktop.account.reconnecting")}</AlertTitle>
        <AlertDescription>
          {t("desktop.account.reconnecting_lead")}
        </AlertDescription>
        {reconnecting.passwordRequired && (
          <div className="pt-1">
            <Button size="sm" onClick={onSignIn}>
              {t("desktop.signin.submit")}
            </Button>
          </div>
        )}
      </Alert>
    </div>
  );
}
