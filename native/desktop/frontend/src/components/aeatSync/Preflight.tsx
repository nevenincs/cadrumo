import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings } from "../../shell/strings";
import { formatSize } from "../agent/files";
import { ProvisioningRow } from "../setup/ProvisioningRow";

// The things that can hold an update back before it reads AEAT: the secure
// browser it reads with, and AEAT access that is not set up. Each says in
// plain words what is missing and why, and offers the one way forward.

/** One held-back step: an icon, what is missing, why it matters and the
 * controls that move on. */
export function PreflightCard({
  icon,
  title,
  children,
  actions,
  testId,
}: {
  icon: IconName;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
  testId: string;
}) {
  return (
    <section
      data-testid={testId}
      className="grid gap-3 rounded-lg border bg-card p-4"
    >
      <h3 className="flex items-center gap-2 text-base font-semibold text-foreground">
        <Icon name={icon} />
        {title}
      </h3>
      {children}
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </section>
  );
}

/**
 * The secure browser is not installed. It says why it is needed and what it
 * costs in space, and installs it through the one setup engine: the row's own
 * progress, plan review, cancel and recovery wording, not a second
 * installer. The caller continues by itself once the row reads ready.
 */
export function BrowserCheck({
  bytes,
  locale,
  onBack,
}: {
  /** The download size the host served; null where it is not known yet. */
  bytes: number | null;
  locale: string;
  onBack: () => void;
}) {
  const t = useStrings();
  const store = useProvisioning();
  const row = store.rows.find((held) => held.kind === "browser") ?? null;
  const run = row ? store.runOf(row.item) : null;
  const working = run !== null && run.stage !== "settled";
  const stopped =
    run?.stage === "settled" &&
    run.outcome !== "completed" &&
    run.outcome !== "nothing_to_do";
  const recovering =
    row !== null &&
    (row.state === "failed" ||
      row.state === "blocked" ||
      row.state === "unknown");
  const showRow = row !== null && (working || stopped || recovering);
  return (
    <PreflightCard
      testId="aeat-sync-browser"
      icon="shield"
      title={t("desktop.aeat_sync.before.browser_title")}
      actions={
        !working && (
          <>
            {!showRow && (
              <Button
                disabled={!row || store.control.busy(row.item)}
                onClick={() => row && store.control.start(row.item)}
              >
                <Icon name="download" size="sm" />
                {t("desktop.aeat_sync.before.browser_install")}
              </Button>
            )}
            <Button variant="outline" onClick={onBack}>
              {t("desktop.aeat_sync.before.not_now")}
            </Button>
          </>
        )
      }
    >
      <p className="text-sm text-muted-foreground">
        {t("desktop.aeat_sync.before.browser_why")}
      </p>
      {!working && !stopped && (
        <p className="text-sm text-foreground">
          {bytes === null
            ? t("desktop.aeat_sync.before.browser_size_unknown")
            : t("desktop.aeat_sync.before.browser_size", {
                size: formatSize(locale, bytes),
              })}
        </p>
      )}
      {!row && (
        <p className="text-sm text-muted-foreground">
          {t("desktop.aeat_sync.before.browser_no_setup")}
        </p>
      )}
      {showRow && (
        <ul className="grid">
          <ProvisioningRow row={row} locale={locale} />
        </ul>
      )}
    </PreflightCard>
  );
}

/** AEAT access is not set up in the profile yet: one sentence and the way
 * into the existing access editor. */
export function AccessCheck({
  onOpenAccess,
  onCheckAgain,
  onBack,
}: {
  onOpenAccess: () => void;
  onCheckAgain: () => void;
  onBack: () => void;
}) {
  const t = useStrings();
  return (
    <PreflightCard
      testId="aeat-sync-access"
      icon="key"
      title={t("desktop.aeat_sync.before.access_title")}
      actions={
        <>
          <Button onClick={onOpenAccess}>
            {t("desktop.aeat_sync.before.access_open")}
          </Button>
          <Button variant="outline" onClick={onCheckAgain}>
            {t("desktop.aeat_sync.before.access_again")}
          </Button>
          <Button variant="ghost" onClick={onBack}>
            {t("desktop.aeat_sync.before.not_now")}
          </Button>
        </>
      }
    >
      <p className="text-sm text-muted-foreground">
        {t("desktop.aeat_sync.before.access_body")}
      </p>
    </PreflightCard>
  );
}
