import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import {
  aeatSignInFailure,
  type AeatSyncPreparePort,
} from "../../shell/aeatSyncPrepare";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings } from "../../shell/strings";
import { AccessCheck, BrowserCheck, PreflightCard } from "./Preflight";

// What stands between "Update from AEAT" and the first read. The person is
// signed in already, so nothing is asked unless something blocks: the secure
// browser is missing, AEAT access is not set up, AEAT waits for approval on
// the phone, or the session ran out part-way through an update.

type Step =
  | { kind: "checking" }
  | { kind: "browser"; bytes: number | null }
  | { kind: "access" }
  | { kind: "phone" }
  | { kind: "ended" }
  | { kind: "failed" };

/**
 * Checks what an update needs and signs in, then calls `onReady` so the
 * update runs. `reason` is `"start"` for an update about to begin and
 * `"session_ended"` once AEAT ended the session part-way, which says so and
 * waits for the person before signing in again; the update then carries on
 * where it stopped. `onClose` leaves without updating.
 */
export function AeatSyncFlow({
  port,
  locale,
  reason = "start",
  onReady,
  onClose,
  onOpenAccess,
}: {
  port: AeatSyncPreparePort;
  locale: string;
  reason?: "start" | "session_ended";
  onReady: () => void;
  onClose: () => void;
  /** Opens the existing AEAT access editor in the profile. */
  onOpenAccess: () => void;
}) {
  const t = useStrings();
  const [step, setStep] = useState<Step>(
    reason === "session_ended" ? { kind: "ended" } : { kind: "checking" },
  );
  // Each attempt that checks and signs in; a new number starts it again.
  const [attempt, setAttempt] = useState(reason === "session_ended" ? 0 : 1);
  const again = useCallback(() => {
    setStep({ kind: "checking" });
    setAttempt((held) => held + 1);
  }, []);

  useEffect(() => {
    if (attempt === 0) return;
    let alive = true;
    void (async () => {
      try {
        const prepared = await port.prepare();
        if (!alive) return;
        if (prepared.browser.state !== "ready")
          return setStep({
            kind: "browser",
            bytes:
              prepared.browser.state === "missing"
                ? prepared.browser.bytes
                : null,
          });
        if (prepared.access === "needs_access")
          return setStep({ kind: "access" });
        await port.signIn(() => {
          if (alive) setStep({ kind: "phone" });
        });
        if (alive) onReady();
      } catch (error) {
        if (!alive) return;
        const failure = aeatSignInFailure(error);
        if (failure === "cancelled") onClose();
        else if (failure === "needs_access") setStep({ kind: "access" });
        else setStep({ kind: "failed" });
      }
    })();
    return () => {
      alive = false;
    };
  }, [attempt, port, onReady, onClose]);

  // The browser finishing its setup is what the update waited for.
  const store = useProvisioning();
  const browserReady =
    store.rows.find((row) => row.kind === "browser")?.state === "ready";
  const waitingOnBrowser = step.kind === "browser";
  useEffect(() => {
    if (waitingOnBrowser && browserReady) again();
  }, [waitingOnBrowser, browserReady, again]);

  switch (step.kind) {
    case "checking":
      return (
        <div
          role="status"
          data-testid="aeat-sync-checking"
          className="flex items-center gap-2 text-muted-foreground"
        >
          <Spinner />
          {t("desktop.aeat_sync.before.checking")}
        </div>
      );
    case "browser":
      return (
        <BrowserCheck bytes={step.bytes} locale={locale} onBack={onClose} />
      );
    case "access":
      return (
        <AccessCheck
          onOpenAccess={onOpenAccess}
          onCheckAgain={again}
          onBack={onClose}
        />
      );
    case "phone":
      return (
        <PreflightCard
          testId="aeat-sync-phone"
          icon="phone"
          title={t("desktop.aeat_sync.before.phone_title")}
          actions={
            <Button
              variant="outline"
              onClick={() => void port.cancelSignIn().catch(() => undefined)}
            >
              {t("desktop.aeat_sync.before.cancel")}
            </Button>
          }
        >
          <p
            role="status"
            className="flex items-start gap-2 text-sm text-muted-foreground"
          >
            <Spinner className="mt-0.5" />
            <span>{t("desktop.aeat_sync.before.phone_body")}</span>
          </p>
        </PreflightCard>
      );
    case "ended":
      return (
        <PreflightCard
          testId="aeat-sync-ended"
          icon="clock"
          title={t("desktop.aeat_sync.before.ended_title")}
          actions={
            <>
              <Button onClick={again}>
                <Icon name="key" size="sm" />
                {t("desktop.aeat_sync.before.ended_sign_in")}
              </Button>
              <Button variant="outline" onClick={onClose}>
                {t("desktop.aeat_sync.before.not_now")}
              </Button>
            </>
          }
        >
          <p className="text-sm text-muted-foreground">
            {t("desktop.aeat_sync.before.ended_body")}
          </p>
        </PreflightCard>
      );
    case "failed":
      return (
        <PreflightCard
          testId="aeat-sync-sign-in-failed"
          icon="alert"
          title={t("desktop.aeat_sync.before.failed_title")}
          actions={
            <>
              <Button onClick={again}>
                {t("desktop.aeat_sync.before.try_again")}
              </Button>
              <Button variant="outline" onClick={onClose}>
                {t("desktop.aeat_sync.before.not_now")}
              </Button>
            </>
          }
        >
          <p role="alert" className="text-sm text-muted-foreground">
            {t("desktop.aeat_sync.before.failed_body")}
          </p>
        </PreflightCard>
      );
  }
}
