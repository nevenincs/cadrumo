import type {
  Choice,
  HeldStep,
  ModelOption,
  ProviderOption,
  ProviderWay,
} from "@/components/agent/types";
import type {
  AuthKind,
  BackgroundTaskKind,
  DeclaredLicence,
  DeclaredTaskKind,
  Effort,
  EngineDoor,
  ProviderTransport,
  ServedCatalogAnswer,
  ServedCatalogModel,
  ServedDeclaredProviderCatalog,
  ServedProviderLane,
} from "./agentCatalogContract";
import type { AgentEngineHealth } from "./agentSession";
import { parseEngineHealth } from "./agentSession";
import { engineNotRunningWords } from "./engineHealth";
import { addedTo } from "./localModelLanes";
import type {
  LocalModelListStatus,
  ReadingSource,
  TaskModelEntry,
} from "./localModelsContract";
import type {
  ProviderSettingsAnswer,
  ProviderSettingsRecord,
} from "./providerSettingsContract";
import type { Translate } from "./strings";

// What the agent offers, as one typed projection of the backend's reads: the
// agent's provider catalog (served, or declared while the agent starts), the
// person's local model lists, and the provider settings. Every surface that
// lists lanes, models, efforts or task settings reads this one projection; it
// names no provider, model, effort or capability of its own.
//
// A provider is the catalog's `provider_id` and a way into it is its
// `transport`; the pair is a lane's identity (ExecutionLane.selection_key).
// A lane has two ids, each built here alone: the catalogue lane id
// `<provider>_<transport>` the service's lists and task settings store, and
// the way id `<provider>/<transport>` the agent column keys its choices and
// remembered selections by.
//
// A lane whose engine health breaks the pairing the schema leaves open is not
// offered, and a catalog of only such lanes is incompatible. While no agent is
// ready the service answers with the declared catalog (`kind: "declared"`):
// every lane of it is listed as not yet observed and none can be chosen.
//
// Interim: where the backend does not serve a fact yet, the projection still
// derives it here, and only here: whether a lane can run (`runs`, which the
// served `health.selectable` is to become), why it is held, and whether the
// service is still reading a lane (`stillReading`).

/** A catalogue lane id: `<provider>_<transport>`, as the lists store it. */
export type LaneId = string;

/** The catalogue lane id of a provider reached one way. */
export const laneIdOf = (provider: string, transport: string): LaneId =>
  `${provider}_${transport}`;

/** The way id of a provider reached one way, as the column keys choices. */
export const wayIdOf = (provider: string, transport: string): string =>
  `${provider}/${transport}`;

/** The catalog answer is the agent's declared catalog, not a served one. */
export const isDeclared = (
  answer: ServedCatalogAnswer,
): answer is ServedDeclaredProviderCatalog =>
  "kind" in answer && answer.kind === "declared";

/** The served lanes of a catalog answer; a declared catalog serves none. */
const servedLanes = (answer: ServedCatalogAnswer): ServedProviderLane[] =>
  isDeclared(answer) ? [] : (answer.providers ?? []);

const wayOfLane = (lane: ServedProviderLane) =>
  wayIdOf(lane.provider_id, lane.transport);

// A lane that states its engine's health outside the contract is not
// understood: it is not offered.
const understood = (lane: ServedProviderLane) =>
  parseEngineHealth(lane) !== "malformed";

/**
 * `lanes` grouped by provider: the providers in the order their first lane
 * comes, each group's API lane before its command-line app, whatever order
 * they came in. The one place lanes are grouped and ordered.
 */
export function groupedByProvider<T>(
  lanes: readonly T[],
  providerOf: (lane: T) => string,
  transportOf: (lane: T) => string,
): T[][] {
  const groups = new Map<string, T[]>();
  for (const lane of lanes)
    groups.set(providerOf(lane), [
      ...(groups.get(providerOf(lane)) ?? []),
      lane,
    ]);
  return [...groups.values()].map((group) =>
    [...group].sort(
      (a, b) =>
        Number(transportOf(a) === "cli") - Number(transportOf(b) === "cli"),
    ),
  );
}

/** Whether the words of an entry hold what was typed: each word of the
 * query, in lower case, somewhere in the words joined, in any order. A fuzzy
 * match would let a short word like "app" match almost everything. An empty
 * query matches every entry. The one search the settings and the picker
 * share. */
export function offerMatches(words: readonly string[], query: string): boolean {
  const held = words.join(" ").toLocaleLowerCase();
  return query
    .toLocaleLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((typed) => held.includes(typed));
}

/** The words for each effort cadrumo-agent names (agent/spec.py `Effort`). */
const EFFORT_WORDS = {
  low: "desktop.agent.effort_low",
  medium: "desktop.agent.effort_medium",
  high: "desktop.agent.effort_high",
  xhigh: "desktop.agent.effort_xhigh",
  max: "desktop.agent.effort_max",
  ultra: "desktop.agent.effort_ultra",
} as const satisfies Record<Effort, string>;

const isEffort = (value: string): value is Effort =>
  Object.hasOwn(EFFORT_WORDS, value);

/** Every effort the contract names, lowest first. */
export const EFFORTS: readonly Effort[] =
  Object.keys(EFFORT_WORDS).filter(isEffort);

export function effortWords(t: Translate, effort: Effort): string {
  return t(EFFORT_WORDS[effort]);
}

const effortChoice = (t: Translate, effort: Effort): Choice => ({
  id: effort,
  name: effortWords(t, effort),
});

/** A model the catalog does not say this computer lacks, so a run can name
 * it. Whether it is held is the catalog's to say; the column never decides. */
export const heldModel = (model: { installed?: boolean | null }) =>
  model.installed !== false;

/** The capabilities a person chooses a provider by, in words; the agent's
 * own machinery (tools, subagents) is not one of them. */
function capabilityWords(t: Translate, capability: string): string | undefined {
  switch (capability) {
    case "writing":
      return t("desktop.agent.can_write");
    case "web_retrieval":
      return t("desktop.agent.can_search_web");
    case "image_reading":
      return t("desktop.agent.can_read_images");
    case "pdf_reading":
      return t("desktop.agent.can_read_pdfs");
    default:
      return undefined;
  }
}

/** What the lane has been proven to do on this host. A proof is the lane's,
 * not a model's: `entry` on one names a tool server, not a model. A
 * generation-scoped proof is not a claim about the whole way, so it is left
 * out of this lane-level summary. */
function provenCapabilities(t: Translate, lane: ServedProviderLane): string[] {
  const words = (lane.capability_proofs ?? [])
    .filter(
      (proof) =>
        proof.state === "proven" &&
        (proof.generation === undefined || proof.generation === null),
    )
    .map((proof) => capabilityWords(t, proof.capability))
    .filter((word): word is string => word !== undefined);
  return [...new Set(words)];
}

/** Interim (backend B1/B2): why a lane cannot be chosen, from the first of
 * its health axes that says so, and the step the person can take where one
 * exists: signing in to a lane that is signed out, and asking again for a
 * lane whose models could not be read. */
function laneHeld(
  t: Translate,
  lane: ServedProviderLane,
): { words: string; step?: HeldStep } {
  const { health } = lane;
  if (health.configured === "unavailable")
    return { words: t("desktop.agent.lane_not_configured") };
  if (health.authentication === "unauthenticated")
    return { words: t("desktop.agent.lane_signed_out"), step: "sign_in" };
  // A local engine that does not run is the cause behind an unreachable
  // transport, so it is said before the transport.
  const engine = parseEngineHealth(lane);
  const engineWords =
    engine !== null && engine !== "malformed"
      ? engineNotRunningWords(t, engine)
      : null;
  if (engineWords !== null) return { words: engineWords };
  if (health.transport === "unavailable" || !lane.executable)
    return { words: t("desktop.agent.lane_unreachable") };
  if (health.admission === "not_admitted")
    return { words: t("desktop.agent.lane_not_admitted") };
  if (health.catalog === "unavailable" || health.catalog === "unknown")
    return { words: t("desktop.agent.lane_no_catalog"), step: "retry" };
  return { words: t("desktop.agent.unavailable"), step: "retry" };
}

/** That a lane's engine does not run, in words, with the door the service
 * names; null for a running engine. */
function engineWordsOf(
  t: Translate,
  engine: AgentEngineHealth,
): { words: string; door: EngineDoor } | null {
  const words = engineNotRunningWords(t, engine);
  return words !== null && engine.state === "not_running"
    ? { words, door: engine.door }
    : null;
}

/** Interim (backend B2): authentication and saved configuration are
 * independent of a provider's capability proof, so an installed or selected
 * CLI does not become runnable without live authentication evidence. */
function hasRunAuthentication(lane: ServedProviderLane): boolean {
  const { health } = lane;
  const authenticated =
    health.authentication === "authenticated" ||
    health.authentication === "not_applicable";
  return (
    health.configured === "available" &&
    health.transport === "available" &&
    health.catalog === "available" &&
    authenticated
  );
}

const writesModel = (lane: ServedProviderLane) =>
  lane.model_source === "declared";

/** The efforts a lane that lists no models accepts with any model: the options
 * of its one thought-level control that are efforts, which is how a gateway's
 * declared efforts are served (providers/effort.py `declared_effort_control`
 * makes each option's id the effort's value). */
function laneEfforts(lane: ServedProviderLane): Effort[] {
  const levels = (lane.catalog.native_controls ?? []).filter(
    (control) => control.kind === "thought_level",
  );
  if (levels.length !== 1) return [];
  return (levels[0]?.options ?? []).flatMap((option) =>
    isEffort(option.option_id) ? [option.option_id] : [],
  );
}

/** Interim (backend B3): whether the service is still reading `lane`: its
 * packaged model list is shown in place of the account's, or the lane cannot
 * be chosen only because a health axis is not yet known. A lane held by
 * something the service has settled (not configured, signed out, an engine
 * that does not run, an unreachable transport, not admitted) is not being
 * read. */
function laneStillReading(lane: ServedProviderLane): boolean {
  if (
    lane.catalog.model_list_source === "packaged" &&
    lane.catalog.state.status === "stale"
  )
    return true;
  const { health } = lane;
  if (health.selectable) return false;
  const engine = parseEngineHealth(lane);
  if (
    engine !== null &&
    engine !== "malformed" &&
    engine.state === "not_running"
  )
    return false;
  if (
    health.configured === "unavailable" ||
    health.transport === "unavailable" ||
    !lane.executable ||
    health.authentication === "unauthenticated" ||
    health.admission === "not_admitted"
  )
    return false;
  // Anything else that holds it (a login, catalog or launcher measurement not
  // yet known, a catalog not observed again in time) the service settles on a
  // later read.
  return true;
}

/**
 * Whether the service still reads some lane of the catalog, which it answers
 * as a packaged model list or an axis not yet known and settles on a later
 * read, so the catalog is asked again until none is.
 */
export function catalogStillReading(catalog: ServedCatalogAnswer): boolean {
  return servedLanes(catalog).some(
    (lane) => understood(lane) && laneStillReading(lane),
  );
}

// A local lane's model list: the models cadrumo-agent's catalog recommends
// for the lane, then the models the person added by name. Cadrumo ranks none
// beyond the catalog's own order.

/** One model of a lane, with what the catalog states of it. */
export type LaneModel = {
  /** The model as a run names it. */
  id: string;
  name: string;
  sizeBytes: number | null;
  licence: DeclaredLicence | null;
  /** Whether this computer holds the model; null where the catalog does not
   * say, as the declared one does not. */
  installed: boolean | null;
};

/** One catalog lane with its models and the ones it recommends. */
export type CatalogLane = {
  /** The catalogue lane id the lists store. */
  id: string;
  provider: string;
  transport: ProviderTransport;
  name: string;
  models: LaneModel[];
  /** What cadrumo-agent recommends on this lane, in its capability order,
   * each once. Each names one of `models`. */
  recommended: string[];
};

/** One entry of a lane's model list. */
export type ListedLaneModel = {
  model: LaneModel;
  /** Added by the person, so the person can take it off the list; a
   * recommended model stays listed. */
  added: boolean;
};

/** The capabilities cadrumo-agent recommends a lane's model for, in the
 * order the list shows them. */
const CAPABILITIES = ["vision", "text"] as const;

function recommendedOf(
  recommended: Readonly<Record<string, string>> | undefined,
  models: readonly LaneModel[],
): string[] {
  const named = CAPABILITIES.flatMap((capability) => {
    const model = recommended?.[capability];
    return model && models.some((held) => held.id === model) ? [model] : [];
  });
  return named.filter((id, index) => named.indexOf(id) === index);
}

const servedLaneModel = (entry: ServedCatalogModel): LaneModel => ({
  id: entry.model,
  name: entry.display_name,
  sizeBytes: entry.size_bytes,
  licence: entry.licence,
  // The served catalog marks only a model this computer lacks.
  installed: entry.installed ?? true,
});

/** The model list lane of one served lane, where it lists models. */
function servedCatalogLane(lane: ServedProviderLane): CatalogLane | null {
  if (lane.model_source !== "catalog" || !understood(lane)) return null;
  const models = (lane.catalog.models ?? []).map(servedLaneModel);
  if (models.length === 0) return null;
  return {
    id: laneIdOf(lane.provider_id, lane.transport),
    provider: lane.provider_id,
    transport: lane.transport,
    name: lane.display_name,
    models,
    recommended: recommendedOf(lane.catalog.recommended, models),
  };
}

/** Every lane of `answer` that lists models, as a model list shows it. A
 * lane whose models the person writes lists none, so it is not one. */
export function catalogLanes(answer: ServedCatalogAnswer): CatalogLane[] {
  if (isDeclared(answer))
    return answer.catalog.providers.flatMap((lane): CatalogLane[] => {
      const models = lane.models.map((model): LaneModel => ({
        id: model.id,
        name: model.display_name,
        sizeBytes: model.size_bytes,
        licence: model.licence,
        installed: null,
      }));
      if (models.length === 0) return [];
      return [
        {
          id: lane.id,
          provider: lane.provider,
          transport: lane.transport,
          name: lane.display_name,
          models,
          recommended: recommendedOf(lane.recommended, models),
        },
      ];
    });
  return servedLanes(answer).flatMap((lane) => {
    const listed = servedCatalogLane(lane);
    return listed ? [listed] : [];
  });
}

/** `lane`'s model list: the recommended models, then `added` that are not
 * already listed. An added model the catalog lists carries its facts; one it
 * does not list is known by its name alone. */
export function laneModelList(
  lane: CatalogLane,
  added: readonly string[],
): ListedLaneModel[] {
  const entry = (id: string): LaneModel =>
    lane.models.find((model) => model.id === id) ?? {
      id,
      name: id,
      sizeBytes: null,
      licence: null,
      installed: null,
    };
  const recommended = lane.recommended.map((id) => ({
    model: entry(id),
    added: false,
  }));
  const extra = added
    .filter(
      (id, index) =>
        !lane.recommended.includes(id) && added.indexOf(id) === index,
    )
    .map((id) => ({ model: entry(id), added: true }));
  return [...recommended, ...extra];
}

/** One model a lane offers. */
export type OfferedModel = {
  /** The catalog entry, as the column's choices key it; null for a model the
   * person added that the catalog does not list. */
  entryId: string | null;
  /** The model as a run names it, and as the lists and tasks store it. */
  model: string;
  name: string;
  description: string | null;
  /** Whether this computer holds it; null where the catalog does not say. */
  installed: boolean | null;
  /** The efforts the model accepts, lowest first. */
  efforts: Effort[];
  defaultEffort: Effort | null;
  /** The efforts a background run on the lane can ask it for: its efforts
   * where the lane takes an effort for a background request, else none. */
  backgroundEfforts: Effort[];
  /** Interim: the model is on the lane's list for the column, recommended
   * for some capability or added by the person. */
  onList: boolean;
};

/** One lane, with everything the reads say of it. */
export type OfferedLane = {
  id: LaneId;
  /** The way id the column's choices and remembered selections use. */
  wayId: string;
  provider: string;
  transport: ProviderTransport;
  authKind: AuthKind;
  name: string;
  /** False for a lane of the declared catalogue, not yet observed. */
  observed: boolean;
  /** The provider settings record of the lane, as served; null while the
   * settings are unread or serve none for it. */
  setting: ProviderSettingsRecord | null;
  /** The lane is on in the provider settings; null where `setting` is. */
  on: boolean | null;
  readsOffHost: boolean | null;
  /** Interim (backend B2): a run can be started on the lane now. */
  runs: boolean;
  /** Why the lane cannot be chosen and the step the person can take, where
   * it cannot; null where it runs. */
  held: { words: string; step?: HeldStep } | null;
  /** The lane's local engine does not run: why, and the door on. */
  engineNotRunning: { words: string; door: EngineDoor } | null;
  engine: AgentEngineHealth | null;
  /** What a background request on the lane takes; null while not observed. */
  background: { text: boolean; effort: boolean } | null;
  /** Present where the person writes the model's id: the efforts the lane
   * accepts with any model. */
  modelWritten: { efforts: Effort[] } | null;
  /** The catalog's models, in its order. */
  models: OfferedModel[];
  /** The person's list of a lane on this computer, in list order
   * (recommended, then added, uncatalogued names included); null for a lane
   * the lists do not hold. */
  listed: OfferedModel[] | null;
  /** The entry the catalog recommends starting with. */
  defaultEntryId: string | null;
  capabilities: string[];
  /** The lane lists a model to download before it runs. */
  modelsToDownload: boolean;
};

/** A provider as the column offers it, with its lanes. */
export type OfferedProvider = ProviderOption & {
  lanes: readonly OfferedLane[];
};

/** One kind of background task, with the setting the service stores. */
export type OfferedTask = {
  id: BackgroundTaskKind;
  name: string;
  description: string;
  /** Null when the kind runs on the model documents are read with. */
  setting: TaskModelEntry | null;
  /** `setting` names a model a task lane offers. */
  offered: boolean;
};

export type AgentOffer = {
  /** False while the lanes are only the agent's declared ones. */
  observed: boolean;
  /** The catalog lists lanes, but none says what provider or transport it
   * is: the service is older than this window. */
  incompatible: boolean;
  /** Interim (backend B3): some lane is still being read by the service. */
  stillReading: boolean;
  /** Providers in served order, each with its ways, the API first. */
  providers: OfferedProvider[];
  /** Each way's models as the column offers them, by way id. */
  models: Record<string, ModelOption[]>;
  /** Every offered lane, by lane id, in served order. */
  lanes: ReadonlyMap<LaneId, OfferedLane>;
  /** The settings records of the lanes turned off that the catalog does not
   * serve, as the service leaves a turned-off lane out of it: they are not
   * offered, yet still the person's to turn on. */
  turnedOff: ProviderSettingsRecord[];
  /** The lanes a background task can run on, in served order. */
  taskLanes: OfferedLane[];
  /** The catalog's kinds of background task, with their settings. */
  tasks: OfferedTask[];
  /** The lanes that list models, as a local model list shows them. */
  modelLanes: CatalogLane[];
  /** The model documents are read with, and where that comes from. */
  reading: { lane: string; model: string; source: ReadingSource } | null;
  listsUnreadable: boolean;
  listsRevision: string | null;
};

/** The models a task kind can run with on `lane`: the person's list of a
 * lane on this computer, else the catalog's models. */
export const taskModelsOf = (lane: OfferedLane): OfferedModel[] =>
  lane.listed ?? lane.models;

const kindsOf = (answer: ServedCatalogAnswer): DeclaredTaskKind[] =>
  isDeclared(answer) ? answer.catalog.task_kinds : answer.task_kinds;

const settingOf = (
  settings: Pick<ProviderSettingsAnswer, "providers"> | null,
  id: LaneId,
) => settings?.providers.find((record) => record.id === id) ?? null;

function servedOfferedLane(
  t: Translate,
  lane: ServedProviderLane,
  lists: LocalModelListStatus | null,
  settings: Pick<ProviderSettingsAnswer, "providers"> | null,
): { offered: OfferedLane; column: ModelOption[] } {
  const id = laneIdOf(lane.provider_id, lane.transport);
  const local = lists !== null && lists.local_lanes.includes(id);
  const added = lists ? addedTo(lists, id) : [];
  const recommended = Object.values(lane.catalog.recommended ?? {});
  const takesEffort = lane.background_requests.options.includes("effort");
  const models = (lane.catalog.models ?? []).map((entry): OfferedModel => ({
    entryId: entry.entry_id,
    model: entry.model,
    name: entry.display_name,
    description: entry.description ?? null,
    installed: entry.installed ?? true,
    efforts: entry.efforts ?? [],
    defaultEffort: entry.default_effort ?? null,
    backgroundEfforts: takesEffort ? (entry.efforts ?? []) : [],
    onList: recommended.includes(entry.model) || added.includes(entry.model),
  }));
  const catalogued = servedCatalogLane(lane);
  const listed = local
    ? catalogued
      ? laneModelList(catalogued, added).map(
          ({ model }): OfferedModel =>
            models.find((held) => held.model === model.id) ?? {
              entryId: null,
              model: model.id,
              name: model.name,
              description: null,
              installed: model.installed,
              efforts: [],
              defaultEffort: null,
              backgroundEfforts: [],
              onList: true,
            },
        )
      : []
    : null;
  const writes = writesModel(lane);
  // The column offers a lane on this computer the models of its list, in the
  // catalog's order.
  const column: ModelOption[] = writes
    ? []
    : models
        .filter((model) => !local || model.onList)
        .map((model) => ({
          id: model.entryId ?? model.model,
          name: model.name,
          ...(model.description ? { description: model.description } : {}),
          efforts: model.efforts.map((effort) => effortChoice(t, effort)),
          ...(model.defaultEffort
            ? { defaultEffort: model.defaultEffort }
            : {}),
          // The served catalog marks only a model this computer lacks.
          ...(model.installed === false ? { installed: false } : {}),
        }));
  const runs =
    lane.health.selectable && hasRunAuthentication(lane) && lane.executable;
  // A lane whose listed models this computer holds none of runs nothing
  // until one is downloaded.
  const noneHeld =
    !writes && column.length > 0 && !column.some((model) => heldModel(model));
  const usable = runs && (writes || (column.length > 0 && !noneHeld));
  const reason = usable || (runs && noneHeld) ? null : laneHeld(t, lane);
  const engine = parseEngineHealth(lane);
  const health = engine !== null && engine !== "malformed" ? engine : null;
  const setting = settingOf(settings, id);
  return {
    column,
    offered: {
      id,
      wayId: wayOfLane(lane),
      provider: lane.provider_id,
      transport: lane.transport,
      authKind: lane.auth_kind,
      name: lane.display_name,
      observed: true,
      setting,
      on: setting ? setting.mode !== "disabled" : null,
      readsOffHost: setting ? setting.reads_off_host : null,
      runs: usable,
      held: usable
        ? null
        : {
            words: reason?.words ?? t("desktop.agent.lane_no_installed_model"),
            ...(reason?.step ? { step: reason.step } : {}),
          },
      engineNotRunning: health ? engineWordsOf(t, health) : null,
      engine: health,
      background: {
        text: lane.background_requests.text !== "unsupported",
        effort: takesEffort,
      },
      modelWritten: writes ? { efforts: laneEfforts(lane) } : null,
      models,
      listed,
      defaultEntryId: lane.catalog.recommended_entry_id ?? null,
      capabilities: provenCapabilities(t, lane),
      // Downloading is a way on where the service says the lane's models
      // are downloaded to this computer and it lists one not held yet.
      modelsToDownload:
        lane.model_download === "required" &&
        column.some((model) => !heldModel(model)),
    },
  };
}

/** The column's view of one lane, a way into its provider. */
function wayOf(t: Translate, lane: OfferedLane): ProviderWay {
  return {
    id: lane.wayId,
    transport: lane.transport,
    authKind: lane.authKind,
    selectable: lane.runs,
    ...(lane.held
      ? {
          unavailableReason: lane.held.words,
          ...(lane.held.step ? { heldStep: lane.held.step } : {}),
        }
      : {}),
    ...(lane.modelsToDownload ? { modelsToDownload: true } : {}),
    ...(lane.engineNotRunning
      ? { engineNotRunning: lane.engineNotRunning }
      : {}),
    ...(lane.capabilities.length > 0
      ? { capabilities: lane.capabilities }
      : {}),
    ...(lane.defaultEntryId ? { defaultModelId: lane.defaultEntryId } : {}),
    ...(lane.modelWritten
      ? {
          modelWritten: {
            efforts: lane.modelWritten.efforts.map((effort) =>
              effortChoice(t, effort),
            ),
          },
        }
      : {}),
  };
}

/** The declared lanes, each listed under its provider and none choosable. */
function declaredLanes(
  t: Translate,
  catalog: ServedDeclaredProviderCatalog,
  settings: Pick<ProviderSettingsAnswer, "providers"> | null,
): OfferedLane[] {
  const declared = catalog.catalog.providers;
  const key = (lane: (typeof declared)[number]) =>
    wayIdOf(lane.provider, lane.transport);
  return declared
    .filter(
      (lane, index) =>
        declared.findIndex((held) => key(held) === key(lane)) === index,
    )
    .map((lane): OfferedLane => {
      const id = laneIdOf(lane.provider, lane.transport);
      const setting = settingOf(settings, id);
      return {
        id,
        wayId: key(lane),
        provider: lane.provider,
        transport: lane.transport,
        authKind: lane.auth_kind,
        name: lane.display_name,
        observed: false,
        setting,
        on: setting ? setting.mode !== "disabled" : null,
        readsOffHost: setting ? setting.reads_off_host : null,
        runs: false,
        held: { words: t("desktop.agent.lane_not_observed"), step: "retry" },
        engineNotRunning: null,
        engine: null,
        background: null,
        modelWritten: null,
        models: lane.models.map((model) => ({
          entryId: null,
          model: model.id,
          name: model.display_name,
          description: null,
          installed: null,
          efforts: [],
          defaultEffort: null,
          backgroundEfforts: [],
          onList: false,
        })),
        listed: null,
        defaultEntryId: null,
        capabilities: [],
        modelsToDownload: false,
      };
    });
}

/**
 * What the agent offers, from the catalog answer, the person's local model
 * lists (null while unread) and the provider settings (null while unread).
 * A lane on this computer offers the models of its list where the lists say
 * which those are.
 */
export function agentOffer(
  t: Translate,
  catalog: ServedCatalogAnswer,
  lists: LocalModelListStatus | null,
  settings: Pick<ProviderSettingsAnswer, "providers"> | null,
): AgentOffer {
  const served = servedLanes(catalog);
  const models: Record<string, ModelOption[]> = {};
  const offered = isDeclared(catalog)
    ? declaredLanes(t, catalog, settings).map((lane) => {
        models[lane.wayId] = [];
        return lane;
      })
    : served
        .filter(
          (lane, index) =>
            understood(lane) &&
            served.findIndex((held) => wayOfLane(held) === wayOfLane(lane)) ===
              index,
        )
        .map((lane) => {
          const { offered, column } = servedOfferedLane(
            t,
            lane,
            lists,
            settings,
          );
          models[offered.wayId] = column;
          return offered;
        });
  const providers = groupedByProvider(
    offered,
    (lane) => lane.provider,
    (lane) => lane.transport,
  ).map((group): OfferedProvider => {
    const ways = group.map((lane) => wayOf(t, lane));
    // Each lane of a provider carries its name; the first served is the
    // provider's, whichever way it is.
    const first = offered.find((lane) => lane.provider === group[0]?.provider);
    return {
      id: first?.provider ?? "",
      name: first?.name ?? "",
      selectable: ways.some((way) => way.selectable),
      ways,
      lanes: group,
    };
  });
  const observed = !isDeclared(catalog);
  const taskLanes = offered.filter(
    (lane) =>
      lane.observed &&
      lane.modelWritten === null &&
      lane.background?.text === true,
  );
  const readable = lists !== null && !lists.unreadable;
  const tasks = kindsOf(catalog).map((kind): OfferedTask => {
    const setting = readable
      ? (lists.tasks.find((entry) => entry.task_kind === kind.id) ?? null)
      : null;
    return {
      id: kind.id,
      name: kind.display_name,
      description: kind.description,
      setting,
      offered:
        setting !== null &&
        taskLanes.some(
          (lane) =>
            lane.id === setting.lane &&
            taskModelsOf(lane).some((model) => model.model === setting.model),
        ),
    };
  });
  return {
    observed,
    incompatible: observed && served.length > 0 && offered.length === 0,
    stillReading: catalogStillReading(catalog),
    providers,
    models,
    lanes: new Map(offered.map((lane) => [lane.id, lane])),
    turnedOff: (settings?.providers ?? []).filter(
      (record) =>
        record.mode === "disabled" &&
        !offered.some((lane) => lane.id === record.id),
    ),
    taskLanes,
    tasks,
    modelLanes: catalogLanes(catalog),
    reading:
      readable && lists.reading
        ? {
            lane: lists.reading.lane,
            model: lists.reading.model,
            source: lists.reading_source,
          }
        : null,
    listsUnreadable: lists?.unreadable ?? false,
    listsRevision: lists?.revision ?? null,
  };
}

/** Where a lane stands, in one word the settings show. */
export type LaneStatus =
  | "off"
  | "setup_needed"
  | "saved"
  | "sign_in_needed"
  | "unconfirmed"
  | "signed_in"
  | "not_checked"
  | "engine_not_running"
  | "ready";

/** Why a lane stands where it does, which the settings say with the step
 * that moves it on. Every status has one. */
export type LaneReason =
  | "turned_off"
  | "record_unreadable"
  | "app_missing"
  | "add_key"
  | "check_settings"
  | "key_saved"
  | "sign_in"
  | "app_unconfirmed"
  | "signed_in"
  | "not_checked"
  | "engine_not_running"
  | "local_setup"
  | "local_ready";

/** What the provider settings serve of a lane that its status is read from. */
export type LaneStanding = {
  authKind: AuthKind;
  mode: ProviderSettingsRecord["mode"];
  readiness: ProviderSettingsRecord["readiness"];
  available: boolean;
  reason?: ProviderSettingsRecord["reason"];
  cliState?: ProviderSettingsRecord["cli_state"];
  cliStateCause?: string | null;
};

/**
 * Interim (backend B1): a lane's status and its reason, read from its served
 * settings record (mode, readiness, `available`, reason and its app's state)
 * and, for a keyless lane on this computer, from the local AI's served setup
 * row (`setupReady`, null without one) or its engine's measured health. The
 * service is to serve this status on the record; until then it is decided
 * here alone.
 *
 * The service never serves `readiness: "ready"` (resolution.py): a stored key
 * is `not_verified` and `available` until its first use, so it reads as a
 * saved key, never as ready. A lane signing in through its app is available
 * exactly when the service found that app signed in.
 */
export function laneStatus(
  lane: LaneStanding,
  engine: AgentEngineHealth | null,
  setupReady: boolean | null,
): { status: LaneStatus; reason: LaneReason } {
  if (lane.reason === "record_unreadable")
    return { status: "setup_needed", reason: "record_unreadable" };
  if (lane.mode === "disabled") return { status: "off", reason: "turned_off" };
  // An app connection needs its app, whatever it signs in with.
  if (lane.cliState === "not_installed")
    return { status: "setup_needed", reason: "app_missing" };
  if (lane.authKind === "none") {
    if (setupReady !== null)
      return setupReady
        ? { status: "ready", reason: "local_ready" }
        : { status: "setup_needed", reason: "local_setup" };
    if (engine?.state === "not_running")
      return { status: "engine_not_running", reason: "engine_not_running" };
    if (engine?.state === "running")
      return { status: "ready", reason: "local_ready" };
    return { status: "not_checked", reason: "not_checked" };
  }
  if (
    lane.authKind === "provider_sign_in_only" ||
    lane.mode === "provider_sign_in"
  ) {
    if (lane.available) return { status: "signed_in", reason: "signed_in" };
    // The probe could not say, and said why: that is not "signed out".
    if (lane.cliState === "unknown" && lane.cliStateCause)
      return { status: "unconfirmed", reason: "app_unconfirmed" };
    if (
      lane.readiness === "sign_in_required" ||
      lane.cliState === "installed_signed_out"
    )
      return { status: "sign_in_needed", reason: "sign_in" };
    return { status: "not_checked", reason: "not_checked" };
  }
  if (lane.available) return { status: "saved", reason: "key_saved" };
  if (lane.readiness === "unusable")
    return { status: "setup_needed", reason: "check_settings" };
  return { status: "setup_needed", reason: "add_key" };
}
