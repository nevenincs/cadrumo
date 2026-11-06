import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import type { IconName } from "@/components/ui/icon";
import type { AgentRead } from "../../shell/agentViews";
import { useStrings } from "../../shell/strings";

/** A settings section that could not be read, and the way to read it again. */
export function SectionFailure({
  words,
  onRetry,
}: {
  words: string;
  onRetry: () => void;
}) {
  const t = useStrings();
  return (
    <div role="alert" className="grid justify-items-start gap-2">
      <p className="text-sm text-foreground">{words}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        {t("desktop.providers.refresh")}
      </Button>
    </div>
  );
}

/** A read that has no answer to show: not offered, on its way, or refused.
 * None of them is shown as empty. */
export function ReadState({
  read,
  icon,
}: {
  read: AgentRead<unknown>;
  icon: IconName;
}) {
  const t = useStrings();
  if (read.kind === "loading") return <EmptyState role="status" busy />;
  return (
    <EmptyState
      role={read.kind === "failed" ? "alert" : "status"}
      icon={read.kind === "failed" ? "alert" : icon}
      heading={
        read.kind === "failed"
          ? t("desktop.agent.read_failed")
          : t("desktop.agent.unavailable")
      }
    />
  );
}
