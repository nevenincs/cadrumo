import { Icon } from "@/components/ui/icon";
import { useStrings } from "@/shell/strings";

/** Where the backend serves nothing yet: the window draws this note and no
 * stand-in of its own. `operation` names what would serve it, for review. */
export function Gap({ operation }: { operation: string }) {
  const t = useStrings();
  return (
    <div
      data-gap={operation}
      className="flex items-start gap-2 rounded-md border border-dashed border-border-strong px-3 py-2 text-sm text-muted-foreground"
    >
      <Icon name="pending" size="sm" className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        <div className="font-medium text-foreground">
          {t("desktop.renta.proto.gap.title")}
        </div>
        <div>{t("desktop.renta.proto.gap.body")}</div>
        <div className="font-mono text-xs text-faint">
          {t("desktop.renta.proto.gap.operation", { operation })}
        </div>
      </div>
    </div>
  );
}
