import type {
  DeclaredTaskKind,
  Effort,
  ServedCatalogAnswer,
  ServedProviderLane,
} from "./agentCatalogContract";
import { isDeclared } from "./agentCatalog";
import { parseEngineHealth } from "./agentSession";
import { addedTo, catalogLanes, laneModelList } from "./localModelLanes";
import type {
  LocalModelListStatus,
  TaskModelEntry,
} from "./localModelsContract";

// What each kind of background task runs with: the kinds are cadrumo-agent's,
// served in its catalogue; the lanes, the models and their effort levels are
// what the running agent serves; the setting per kind is the one the agent
// service stores beside the model documents are read with. A kind with no
// setting runs on that reading model. Cadrumo names no kind, lane, model or
// effort here.

/** One kind of background task, with the setting the service stores for it. */
export type TaskKindRow = {
  id: string;
  name: string;
  description: string;
  /** Null when the kind runs on the model documents are read with. */
  setting: TaskModelEntry | null;
};

/** One model a task kind can be set to run with. */
export type TaskModelOption = {
  id: string;
  name: string;
  /** False where the catalog says this computer does not hold the model. */
  installed: boolean;
  /** The effort levels a background run on the lane can ask this model for,
   * lowest first; empty where the lane takes no effort or the model states
   * none. */
  efforts: Effort[];
};

/** One lane a task kind can be set to run on, with the models it offers. */
export type TaskLaneOption = {
  /** The catalogue lane id the service stores. */
  id: string;
  /** The provider and the way into it, as the model picker keys them. */
  provider: string;
  way: string;
  name: string;
  models: TaskModelOption[];
};

const kindsOf = (answer: ServedCatalogAnswer): DeclaredTaskKind[] =>
  isDeclared(answer) ? answer.catalog.task_kinds : answer.task_kinds;

/** Every kind the catalogue serves, in its order, each with the setting the
 * service stores for it. An unreadable record sets none. */
export function taskKindRows(
  answer: ServedCatalogAnswer,
  lists: LocalModelListStatus,
): TaskKindRow[] {
  return kindsOf(answer).map((kind) => ({
    id: kind.id,
    name: kind.display_name,
    description: kind.description,
    setting: lists.unreadable
      ? null
      : (lists.tasks.find((entry) => entry.task_kind === kind.id) ?? null),
  }));
}

const laneIdOf = (lane: ServedProviderLane) =>
  `${lane.provider_id}_${lane.transport}`;

/** Whether a background run on `lane` can be asked for an effort. */
const takesEffort = (lane: ServedProviderLane) =>
  lane.background_requests.options.includes("effort");

/**
 * The lanes a task kind can run on, each with the models it offers: a lane
 * the running agent serves that lists its models and takes a background
 * request's text. A lane on this computer offers the models on its list, as
 * the model picker does. A lane can offer none yet (signed out, its list
 * empty): it is still served, so the settings can say what it waits on, but
 * nothing on it can be chosen. While the agent starts, nothing is served.
 */
export function taskLanes(
  answer: ServedCatalogAnswer,
  lists: LocalModelListStatus,
): TaskLaneOption[] {
  if (isDeclared(answer)) return [];
  const local = new Set(lists.local_lanes);
  const listed = new Map(
    catalogLanes(answer).map((lane) => [lane.id, lane] as const),
  );
  return (answer.providers ?? []).flatMap((lane): TaskLaneOption[] => {
    const id = laneIdOf(lane);
    if (
      lane.model_source !== "catalog" ||
      lane.background_requests.text === "unsupported" ||
      parseEngineHealth(lane) === "malformed"
    )
      return [];
    const served = lane.catalog.models ?? [];
    const effortsOf = (model: string): Effort[] =>
      takesEffort(lane)
        ? (served.find((entry) => entry.model === model)?.efforts ?? [])
        : [];
    const catalogued = listed.get(id);
    const models: TaskModelOption[] = local.has(id)
      ? catalogued
        ? laneModelList(catalogued, addedTo(lists, id)).map(({ model }) => ({
            id: model.id,
            name: model.name,
            installed: model.installed !== false,
            efforts: effortsOf(model.id),
          }))
        : []
      : served.map((entry) => ({
          id: entry.model,
          name: entry.display_name,
          installed: entry.installed !== false,
          efforts: effortsOf(entry.model),
        }));
    return [
      {
        id,
        provider: lane.provider_id,
        way: `${lane.provider_id}/${lane.transport}`,
        name: lane.display_name,
        models,
      },
    ];
  });
}

/** The effort levels `model` on `lane` can be asked for, as `lanes` offer them. */
export function taskEfforts(
  lanes: readonly TaskLaneOption[],
  lane: string,
  model: string,
): Effort[] {
  return (
    lanes
      .find((held) => held.id === lane)
      ?.models.find((held) => held.id === model)?.efforts ?? []
  );
}
