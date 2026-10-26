import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Spinner } from "@/components/ui/spinner";
import {
  censoRequirementKeys,
  type useCensoSync,
} from "../../shell/profileCenso";
import { useStrings } from "../../shell/strings";

/**
 * Censo synchronization as a band of the profile page: what it still needs,
 * the pull in progress, and its review, whose values are shown on the
 * details they would change. The review is answered as a whole.
 */
export function ProfileSync({
  sync,
  compact,
  onTaxId,
  onSetup,
  onReview,
}: {
  sync: ReturnType<typeof useCensoSync>;
  compact: boolean;
  onTaxId(): void;
  onSetup(): void;
  onReview(): void;
}) {
  const t = useStrings();
  const { readiness, snapshot, busy, error, uncertain } = sync;
  const stop = snapshot?.can_cancel && (
    <Button
      size="xs"
      variant="outline"
      disabled={busy}
      onClick={() => void sync.answer("cancel")}
    >
      {t("desktop.profile.censo.cancel")}
    </Button>
  );
  const pull = (
    <Button
      size="xs"
      variant="outline"
      disabled={busy || uncertain}
      onClick={() => void sync.start()}
    >
      {busy ? <Spinner /> : <Icon name="sync" size="xs" />}
      {t("desktop.profile.censo.pull")}
    </Button>
  );
  let glyph: ReactNode = <Icon name="sync" />;
  let status: ReactNode;
  let actions: ReactNode = null;
  if (error || snapshot?.state === "unknown") {
    glyph = <Icon name="alert" />;
    status = t(
      uncertain || snapshot?.state === "unknown"
        ? "desktop.profile.censo.unknown"
        : "desktop.profile.censo.unavailable",
    );
    actions = (
      <Button size="xs" variant="outline" disabled={busy} onClick={sync.retry}>
        {t("desktop.profile.refresh")}
      </Button>
    );
  } else if (!snapshot) {
    if (!readiness) {
      glyph = <Spinner />;
      status = t("desktop.profile.censo.checking");
    } else if (!readiness.ready) {
      glyph = <Icon name="alert" />;
      const missing = readiness.requirements.filter((item) => !item.satisfied);
      status = (
        <span className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <span>{t("desktop.profile.censo.blocked")}</span>
          {missing.map((item) => (
            <span
              key={`${item.field}:${item.reason}`}
              className="inline-flex items-center gap-1"
            >
              <Icon name="close" size="xs" />
              {t(
                censoRequirementKeys[
                  item.reason as keyof typeof censoRequirementKeys
                ] ?? "auth.sync.requirement.unavailable",
              )}
            </span>
          ))}
        </span>
      );
      const needsTaxId = missing.some(
        (item) => item.field === "identity.tax_id",
      );
      actions = (
        <>
          {needsTaxId && (
            <Button size="xs" variant="outline" onClick={onTaxId}>
              {t("desktop.profile.censo.identity")}
            </Button>
          )}
          <Button size="xs" variant="outline" onClick={onSetup}>
            {t("desktop.profile.censo.setup")}
          </Button>
        </>
      );
    } else {
      status = (
        <span>
          {t("desktop.profile.censo.ready")}
          {!compact && (
            <span className="ml-2 text-muted-foreground">
              {t("desktop.profile.censo.scope")}
            </span>
          )}
        </span>
      );
      actions = pull;
    }
  } else
    switch (snapshot.state) {
      case "reading":
        glyph = <Spinner />;
        status = t("desktop.profile.censo.reading");
        actions = stop;
        break;
      case "device":
        glyph = <Icon name="device" />;
        status = (
          <span className="font-medium">
            {t("desktop.profile.censo.device")}
          </span>
        );
        actions = stop;
        break;
      case "review":
        glyph = <Icon name="selectAll" />;
        status = (
          <span>
            <button
              type="button"
              className="cursor-pointer font-medium underline underline-offset-2"
              onClick={onReview}
            >
              {t("desktop.profile.censo.review_count", {
                count: snapshot.fields.length,
              })}
            </button>
            {!compact && (
              <span className="ml-2 text-muted-foreground">
                {t("desktop.profile.censo.review_hint")}
              </span>
            )}
          </span>
        );
        actions = (
          <>
            <Button
              size="xs"
              variant="outline"
              disabled={busy}
              onClick={() => void sync.answer("reject")}
            >
              {t("desktop.profile.censo.reject")}
            </Button>
            <Button
              size="xs"
              disabled={busy}
              onClick={() => void sync.answer("apply")}
            >
              {busy && <Spinner />}
              {t("desktop.profile.censo.apply")}
            </Button>
          </>
        );
        break;
      case "done":
        glyph = <Icon name="tick" />;
        status = t("desktop.profile.censo.done");
        actions = (
          <IconButton
            size="xs"
            variant="ghost"
            label={t("desktop.profile.dismiss")}
            onClick={sync.dismiss}
          >
            <Icon name="close" size="xs" />
          </IconButton>
        );
        break;
      case "stopped":
        glyph = <Icon name="alert" />;
        status = t("desktop.profile.censo.stopped");
        actions = pull;
        break;
      case "unsupported":
        glyph = <Icon name="alert" />;
        status = t("desktop.profile.censo.unsupported");
        actions = stop;
        break;
    }
  return (
    <div
      role="region"
      aria-label={t("desktop.profile.censo.band")}
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b bg-chrome px-4 py-2 text-sm",
        snapshot?.state === "review" && "border-b-2 border-b-foreground",
      )}
    >
      <span className="flex items-center gap-2 font-semibold text-foreground">
        {glyph}
        {t("desktop.profile.censo.band")}
      </span>
      <span role="status" className="min-w-0 flex-1 basis-48 text-foreground">
        {status}
      </span>
      {actions && (
        <span className="flex shrink-0 items-center gap-1.5">{actions}</span>
      )}
    </div>
  );
}
