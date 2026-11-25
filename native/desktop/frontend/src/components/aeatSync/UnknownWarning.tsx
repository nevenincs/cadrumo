import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../shell/strings";

/**
 * The warning that guards reading again data whose outcome is unknown: it may
 * already have been brought, so the person is told before it is read again.
 */
export function UnknownWarning({
  busy,
  onProceed,
  onCancel,
}: {
  busy: boolean;
  /** The person was told and wants it read again. */
  onProceed(): void;
  onCancel(): void;
}) {
  const t = useStrings();
  const key = "desktop.aeat_sync.progress.";
  return (
    <Alert tone="warning" icon={<Icon name="alert" />}>
      {t(`${key}warn_unknown`)}
      <span className="mt-1 flex flex-wrap gap-2">
        <Button size="xs" variant="outline" disabled={busy} onClick={onProceed}>
          {t(`${key}warn_confirm`)}
        </Button>
        <Button size="xs" variant="ghost" onClick={onCancel}>
          {t(`${key}warn_cancel`)}
        </Button>
      </span>
    </Alert>
  );
}
