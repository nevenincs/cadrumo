import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { ContextFit } from "../../errors";
import { sendRefusalStep } from "../../shell/agentSendRefusals";
import { useStrings } from "../../shell/strings";
import { EngineDoor } from "../setup/EngineDoor";
import { refusalWords } from "./agentRefusalWords";

/** A local engine that does not run, as the notice says it. */
export type EngineNotice = {
  /** The way it belongs to. */
  id: string;
  /** What is said, already worded and named for its provider. */
  words: string;
  /** The door id the service names for the way on. */
  door: string;
};

/**
 * What is said over the composer: why the last send or request was refused,
 * else why the agent cannot answer now, with the way on where there is one:
 * asking the service again, setting up a provider, downloading a model, or
 * the door the service names for a local engine that does not run.
 */
export function ColumnNotice({
  failure,
  fit = null,
  notice,
  engines,
  onRetry,
  onSetUpProviders,
  onDownloadModels,
  onOpenModelSettings,
}: {
  /** The refusal code of the last send or request, null where none. */
  failure: string | null;
  /** The context sizes the refusal stated, said with its code. */
  fit?: ContextFit | null;
  notice: string | null;
  /** The local engines that do not run, said in place of `notice`. */
  engines?: readonly EngineNotice[];
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
        {refusalWords(t, failure, fit)}
        {failureStep && download(failureStep)}
      </span>
    </p>
  ) : engines && engines.length > 0 ? (
    <>
      {engines.map((engine) => (
        <p
          key={engine.id}
          role="status"
          data-engine-notice={engine.id}
          className="flex items-start gap-2 text-sm text-muted-foreground"
        >
          <Icon name="alert" className="mt-0.5" />
          <span className="grid justify-items-start gap-1.5">
            {engine.words}
            <EngineDoor door={engine.door} />
          </span>
        </p>
      ))}
    </>
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
