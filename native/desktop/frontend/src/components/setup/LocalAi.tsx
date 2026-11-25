import { useState } from "react";
import type { AgentServiceStatus } from "../../shell/agentSession";
import type { CatalogLane } from "../../shell/agentOffer";
import { Icon } from "../ui/icon";
import { Spinner } from "../ui/spinner";
import { serviceWords } from "../agent/agentRefusalWords";
import { ModelListNotice } from "../agent/ModelListNotice";
import {
  ReviewClaimContext,
  type LocalModelHost,
} from "../../shell/localModels";
import { useProvisioning } from "../../shell/provisioning";
import { useStrings } from "../../shell/strings";
import { LocalModels } from "../settings/LocalModels";
import { ItemRemoval } from "./ItemRemoval";
import { ProvisioningRow } from "./ProvisioningRow";

// The local AI as one element with two concerns: the program that runs the
// models, with its own status, size and controls, and beneath it, grouped
// with it, the person's local model list, each model with its own download,
// progress and removal. The provisioning panel and the agent's settings for
// the lane on this computer render this same component. The program is this
// installation's; the model list is the signed-in person's, so while nobody
// is signed in it says that a sign-in is needed, and the removal that takes
// the listed models with it is not offered. While the agent does not serve
// the list, or its read answers where setup stands, that is said in the
// list's place; only a fault offers asking again.

export function LocalAi({
  lanes,
  host,
  locale,
  onRemoved,
  signedOut = false,
  status = "ready",
  failure = null,
  service = null,
  onRetry,
}: {
  /** The keyless lanes whose model lists are shown; none says no lane on
   * this computer lists models. */
  lanes: readonly CatalogLane[];
  /** The person's lists, where the host offers reading and changing them;
   * without it no model list is shown. */
  host: LocalModelHost | null;
  locale: string;
  /** Told once a model is removed from this computer. */
  onRemoved?: () => void;
  /** Nobody is signed in, so there is no person's model list to show. */
  signedOut?: boolean;
  status?: "loading" | "failed" | "ready";
  /** The refusal the lanes' read answered, while `status` is failed. */
  failure?: string | null;
  /** The agent service's status while it does not serve the list. */
  service?: AgentServiceStatus | null;
  onRetry?: () => void;
}) {
  const t = useStrings();
  const store = useProvisioning();
  const row = store.localAiRow;
  // The plan is answered on the row of the model asked for while that row is
  // on screen showing it, which the row itself says; otherwise on the
  // program's row, so a plan never waits with no way to answer it.
  const [claimed, setClaimed] = useState(false);
  return (
    <div data-slot="local-ai" data-testid="local-ai" className="grid gap-2">
      {row && (
        <ul className="grid">
          <ProvisioningRow
            row={row}
            locale={locale}
            heading={t("desktop.setup.part_program")}
            progress={store.programPart()}
            reviewElsewhere={claimed}
          >
            <ItemRemoval
              row={row}
              removals={
                signedOut
                  ? ["local_ai_program"]
                  : ["local_ai", "local_ai_program"]
              }
              onRemoved={onRemoved}
            />
          </ProvisioningRow>
        </ul>
      )}
      {signedOut ? (
        <p
          data-slot="local-models-signed-out"
          className={
            row
              ? "ml-3 border-l pl-3 text-sm text-muted-foreground"
              : "text-sm text-muted-foreground"
          }
        >
          {t("desktop.setup.models_signed_out")}
        </p>
      ) : (
        (host || service) && (
          // Linked to the program above by the rule beside it: the models are
          // what the program runs.
          <div className={row ? "ml-3 grid gap-3 border-l pl-3" : "grid gap-3"}>
            {service ? (
              <p
                role="status"
                data-slot="local-models-service"
                className="flex items-start gap-2 text-sm text-muted-foreground"
              >
                <Icon name="info" className="mt-0.5" />
                <span>{serviceWords(t, service)}</span>
              </p>
            ) : !host ? null : status === "loading" ? (
              <p
                role="status"
                className="flex items-center gap-2 text-sm text-muted-foreground"
              >
                <Spinner />
                <span>{t("desktop.providers.local_models_loading")}</span>
              </p>
            ) : status === "failed" ? (
              <ModelListNotice
                code={failure ?? ""}
                fault={t("desktop.providers.load_failed")}
                onRetry={onRetry}
                slot="local-models-lanes"
              />
            ) : (
              <ReviewClaimContext.Provider value={setClaimed}>
                {(lanes.length > 0 ? lanes : [null]).map((lane, index) => (
                  <LocalModels
                    key={lane?.id ?? "none"}
                    lane={lane}
                    withEngine={index === 0}
                    host={host}
                    locale={locale}
                    onRemoved={onRemoved}
                  />
                ))}
              </ReviewClaimContext.Provider>
            )}
          </div>
        )
      )}
    </div>
  );
}
