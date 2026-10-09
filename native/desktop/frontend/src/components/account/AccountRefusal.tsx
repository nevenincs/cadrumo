import { Alert } from "@/components/ui/alert";
import { Icon, type IconName } from "@/components/ui/icon";
import { Progress } from "@/components/ui/progress";
import type { SignInRefusal } from "../../ipc/contract";
import { useStrings } from "../../shell/strings";

type Tone = "neutral" | "warning" | "danger";

// How each typed refusal is said: its text, its tone and its icon. A code the
// shell does not name is still shown, with the code, never swallowed.
const REFUSALS: Record<string, { key: string; tone: Tone; icon: IconName }> = {
  INSTALLATION_UNAVAILABLE: {
    key: "desktop.signin.refused.installation_unavailable",
    tone: "warning",
    icon: "unplug",
  },
  INSTALLATION_REFUSED: {
    key: "desktop.signin.refused.installation_refused",
    tone: "danger",
    icon: "alert",
  },
  INSTALLATION_CANCELLED: {
    key: "desktop.signin.refused.installation_cancelled",
    tone: "neutral",
    icon: "info",
  },
  INSTALLATION_FAILED: {
    key: "desktop.signin.refused.installation_failed",
    tone: "danger",
    icon: "alert",
  },
  INSTALLATION_UNSETTLED: {
    key: "desktop.signin.refused.installation_unsettled",
    tone: "warning",
    icon: "alert",
  },
  CREDENTIAL_REJECTED: {
    key: "desktop.signin.refused.invalid",
    tone: "danger",
    icon: "alert",
  },
  THROTTLED: {
    key: "desktop.signin.refused.throttled",
    tone: "warning",
    icon: "clock",
  },
  PROFILE_LOCKED: {
    key: "desktop.signin.refused.profile_locked",
    tone: "warning",
    icon: "lock",
  },
  KEYRING_UNAVAILABLE: {
    key: "desktop.signin.refused.keyring_unavailable",
    tone: "warning",
    icon: "lock",
  },
  RUNTIME_UNAVAILABLE: {
    key: "desktop.signin.refused.runtime_unavailable",
    tone: "warning",
    icon: "unplug",
  },
  RECEIPT_ABSENT: {
    key: "desktop.signin.refused.receipt_absent",
    tone: "neutral",
    icon: "info",
  },
  RECEIPT_EXPIRED: {
    key: "desktop.signin.refused.receipt_expired",
    tone: "neutral",
    icon: "info",
  },
  CUSTODY_CHANGED: {
    key: "desktop.signin.refused.custody_changed",
    tone: "neutral",
    icon: "info",
  },
  LOGIN_MISMATCH: {
    key: "desktop.signin.refused.login_mismatch",
    tone: "neutral",
    icon: "info",
  },
  GENERATION_CHANGED: {
    key: "desktop.signin.refused.generation_changed",
    tone: "neutral",
    icon: "info",
  },
};

const OTHER = {
  key: "desktop.signin.refused.other",
  tone: "danger",
  icon: "alert",
} as const;

/**
 * A refusal, said in the shell's own words. A throttle shows its wait as it
 * runs down and leaves when the wait is over; the running number is for the
 * eye only, so a screen reader hears the wait once, not every second.
 */
export function AccountRefusal({
  refusal,
  seconds,
  quiet = false,
}: {
  refusal: SignInRefusal | null;
  seconds: number;
  /** A second copy of what another pane already announces: read in place,
   * not announced again. */
  quiet?: boolean;
}) {
  const t = useStrings();
  if (!refusal) return null;
  const code = refusal.code.toUpperCase();
  const entry =
    refusal.operation === "manager"
      ? { ...OTHER, key: "desktop.signin.refused.manager" }
      : (code && REFUSALS[code]) || OTHER;
  const total = refusal.retryAfterSeconds ?? 0;
  if (code === "THROTTLED") {
    if (seconds <= 0) return null;
    return (
      <Alert tone="warning" icon={<Icon name="clock" />}>
        <span className="sr-only">{t(entry.key, { seconds: total })}</span>
        <span aria-hidden="true">{t(entry.key, { seconds })}</span>
        {total > 0 && (
          <Progress
            className="mt-1.5"
            value={total - seconds}
            max={total}
            aria-hidden="true"
          />
        )}
      </Alert>
    );
  }
  return (
    <Alert
      tone={entry.tone}
      role={quiet ? "note" : entry.tone === "danger" ? "alert" : "status"}
      icon={<Icon name={entry.icon} />}
    >
      {t(entry.key, { code: refusal.code })}
      {refusal.operation && (
        <code className="text-sm text-muted-foreground">
          {[refusal.operation, refusal.ioKind, refusal.osCode]
            .filter((value) => value !== undefined)
            .join(" · ")}
        </code>
      )}
    </Alert>
  );
}
