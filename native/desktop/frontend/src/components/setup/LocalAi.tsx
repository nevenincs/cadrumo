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
// the lane on this computer render this same component.

export function LocalAi({
  lanes,
  host,
  locale,
  onRemoved,
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
              removals={["local_ai", "local_ai_program"]}
              onRemoved={onRemoved}
            />
          </ProvisioningRow>
        </ul>
      )}
      {host && (
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
      )}
    </div>
  );
}
