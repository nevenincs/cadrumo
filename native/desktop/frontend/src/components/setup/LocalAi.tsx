import type { CatalogLane } from "../../shell/localModelLanes";
import type { LocalModelHost } from "../../shell/localModels";
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
// the listed models with it is not offered.

export function LocalAi({
  lanes,
  host,
  locale,
  onRemoved,
  signedOut = false,
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
}) {
  const t = useStrings();
  const store = useProvisioning();
  const row = store.localAiRow;
  return (
    <div data-slot="local-ai" className="grid gap-2">
      {row && (
        <ul className="grid">
          <ProvisioningRow
            row={row}
            locale={locale}
            heading={t("desktop.setup.part_program")}
            progress={store.programPart()}
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
        host && (
          // Linked to the program above by the rule beside it: the models are
          // what the program runs.
          <div className={row ? "ml-3 grid gap-3 border-l pl-3" : "grid gap-3"}>
            {(lanes.length > 0 ? lanes : [null]).map((lane) => (
              <LocalModels
                key={lane?.id ?? "none"}
                lane={lane}
                host={host}
                locale={locale}
                onRemoved={onRemoved}
              />
            ))}
          </div>
        )
      )}
    </div>
  );
}
