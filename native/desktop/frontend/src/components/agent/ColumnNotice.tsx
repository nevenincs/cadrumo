import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { sendRefusalStep } from "../../shell/agentSendRefusals";
import { useStrings } from "../../shell/strings";
import { refusalWords } from "./agentRefusalWords";

/**
 * What is said over the composer: why the last send or request was refused,
 * else why the agent cannot answer now, with the way on where there is one:
 * asking the service again, setting up a provider, or downloading a model.
 */
export function ColumnNotice({
  failure,
  notice,
  onRetry,
  onSetUpProviders,
  onDownloadModels,
  onOpenModelSettings,
}: {
  /** The refusal code of the last send or request, null where none. */
  failure: string | null;
  notice: string | null;
  onRetry?: () => void;
  onSetUpProviders?: () => void;
  /** Offered with the notice: no model the agent can run is on this
   * computer yet. */
  onDownloadModels?: () => void;
  /** Opens the settings that download a model, the way on from a send
   * refused for a model this computer does not hold. */
  onOpenModelSettings?: () => void;
}) {
  const t = useStrings();
  const download = (open: () => void) => (
    <Button variant="outline" size="xs" onClick={open}>
      {t("desktop.agent.download_models")}
    </Button>
  );
  const failureStep =
    failure !== null && sendRefusalStep(failure) === "local_models"
      ? onOpenModelSettings
      : undefined;
  return failure !== null ? (
    <p role="alert" className="flex items-start gap-2 text-sm">
      <Icon name="alert" className="mt-0.5 text-destructive" />
      <span className="grid justify-items-start gap-1.5">
        {refusalWords(t, failure)}
        {failureStep && download(failureStep)}
      </span>
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
          {onDownloadModels && download(onDownloadModels)}
        </span>
      </p>
    )
  );
}
