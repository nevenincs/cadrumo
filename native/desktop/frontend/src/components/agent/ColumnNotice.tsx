import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../shell/strings";
import { refusalWords } from "./agentRefusalWords";

/**
 * What is said over the composer: why the last send or request was refused,
 * else why the agent cannot answer now, with the way on where there is one:
 * asking the service again, or setting up a provider.
 */
export function ColumnNotice({
  failure,
  notice,
  onRetry,
  onSetUpProviders,
}: {
  /** The refusal code of the last send or request, null where none. */
  failure: string | null;
  notice: string | null;
  onRetry?: () => void;
  onSetUpProviders?: () => void;
}) {
  const t = useStrings();
  return failure !== null ? (
    <p role="alert" className="flex items-start gap-2 text-sm">
      <Icon name="alert" className="mt-0.5 text-destructive" />
      <span>{refusalWords(t, failure)}</span>
    </p>
  ) : (
    notice && (
      <p
        role="status"
        className="flex items-start gap-2 text-sm text-muted-foreground"
      >
        <Icon name="info" className="mt-0.5" />
        <span className="grid justify-items-start gap-1.5">
          {notice}
          {onRetry && (
            <Button variant="outline" size="xs" onClick={onRetry}>
              {t("desktop.agent.retry")}
            </Button>
          )}
          {onSetUpProviders && (
            <Button variant="outline" size="xs" onClick={onSetUpProviders}>
              {t("desktop.agent.set_up_providers")}
            </Button>
          )}
        </span>
      </p>
    )
  );
}
