import type { TaskModelChoice } from "../shell/agentSession";
import type { ServedProviderCatalog } from "../shell/agentCatalogContract";
import type { TaskModelEntry } from "../shell/localModelsContract";

/**
 * The made-up service's setting per task kind, in the order set: only a kind
 * the catalogue serves, on a lane it reports, as the service checks them.
 */
export function fixtureTaskModels(catalog: ServedProviderCatalog) {
  const tasks: TaskModelEntry[] = [];
  return {
    entries: () => tasks.map((entry) => ({ ...entry })),
    clear: () => void tasks.splice(0, tasks.length),
    /** Whether `taskKind` and `choice` are ones the catalogue serves. */
    served: (taskKind: string, choice: TaskModelChoice | null) =>
      catalog.task_kinds.some((kind) => kind.id === taskKind) &&
      (!choice ||
        (catalog.providers ?? []).some(
          (held) => `${held.provider_id}_${held.transport}` === choice.lane,
        )),
    /** Stores `choice` for `taskKind`, or clears it; false when nothing
     * changed. */
    choose: (taskKind: string, choice: TaskModelChoice | null): boolean => {
      const index = tasks.findIndex((entry) => entry.task_kind === taskKind);
      const stored = index < 0 ? null : tasks[index];
      const unchanged = choice
        ? stored?.lane === choice.lane &&
          stored.model === choice.model &&
          stored.effort === choice.effort
        : !stored;
      if (unchanged) return false;
      if (!choice) tasks.splice(index, 1);
      else if (index >= 0) tasks[index] = { task_kind: taskKind, ...choice };
      else tasks.push({ task_kind: taskKind, ...choice });
      return true;
    },
  };
}
