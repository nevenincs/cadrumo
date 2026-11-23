import type {
  Effort,
  ServedCatalogAnswer,
  ServedCatalogModel,
} from "../shell/agentCatalogContract";
import type { AgentSession } from "../shell/agentSession";
import type {
  LocalEngine,
  LocalEngineStatus,
  LocalModelListStatus,
  LocalPlacement,
  TaskModelEntry,
} from "../shell/localModelsContract";
import type { ProviderSettingsRecord } from "../shell/providerSettingsContract";
import { fixtureTaskModels } from "./fixtureTaskModels";
import {
  catalogsUnderEngine,
  FIXTURE_CATALOG,
  fixtureCatalogRefusal,
  FIXTURE_DECLARED_CATALOG,
  withEngineHealth,
  type FixtureCatalog,
  type FixtureEngineHealth,
  type FixtureModelPresence,
} from "./fixtures/agentCatalog";
import { FIXTURE_SETTINGS_LANES } from "./providerSettingsFixture";
import { withScenarioReads } from "./fixtures/agentLanes";
import type {
  FixtureEngineChoices,
  FixtureLocalModels,
} from "./agentFixtureOptions";

// The scenario host agent's catalog, local model lists and local engine
// record: what the made-up service answers about which models a lane serves,
// which of them this computer holds and which engine runs them. The record the
// lists and the engine share is one stored record, so one revision names both.

/** The generic local lane, the one the "local-only" catalog serves alone. */
const FIXTURE_LOCAL_LANE = "zai_api";
/** The hosted lane the "hosted-signed-out" catalog serves beside the local
 * lane: the fixture catalog holds it back as signed out. */
const FIXTURE_HOSTED_SIGNED_OUT_LANE = "kimi_cli";
/** The lanes whose model lists the made-up service keeps: every keyless lane
 * on this computer, the generic local lane and each engine's lane. */
const FIXTURE_LISTED_LANES: readonly string[] = FIXTURE_SETTINGS_LANES.filter(
  (seed) => seed.auth_kind === "none",
).map((seed) => seed.id);
/** The most models the lists hold. */
const FIXTURE_LIST_LIMIT = 64;

const revisionOf = (count: number) => count.toString(16).padStart(64, "0");

export const coded = (code: string) => Object.assign(new Error(code), { code });

type ModelHostMethods = Pick<
  AgentSession,
  | "providerCatalog"
  | "localModels"
  | "addLocalModel"
  | "removeLocalModel"
  | "resetLocalModels"
  | "localEngine"
  | "chooseLocalEngine"
  | "chooseReadingModel"
  | "chooseTaskModel"
  | "modelLicence"
>;

export function fixtureModelHost({
  say,
  check,
  catalog,
  turnedOff,
  models,
  localModels,
  engineHealth,
  engineChoices,
  localEngine,
  readingDefault,
}: {
  say: (call: string) => void;
  /** Takes the host's time and refuses when the profile cannot be read. */
  check: () => Promise<void>;
  catalog: FixtureCatalog;
  turnedOff: () => ReadonlySet<string>;
  models?: FixtureModelPresence;
  localModels?: FixtureLocalModels;
  engineHealth?: FixtureEngineHealth;
  engineChoices?: FixtureEngineChoices;
  localEngine?: LocalEngine;
  readingDefault?: { lane: string; model: string };
}): {
  /** What the catalog is doing now; the host's status publication moves it. */
  state: { busy: boolean; declared: boolean };
  methods: ModelHostMethods;
  /** Commits a change to the list as another window would, so the
   * revision this one read is out of date. */
  changeListElsewhere: () => void;
  /** The local engine the stored record selects now. */
  selectedEngine: () => string;
} {
  const state = {
    busy: catalog === "busy" || catalog === "busy-past-ready",
    declared: catalog === "declared",
  };

  // The models the person added to the local lane's list, as the made-up
  // service stores them, and how many changes it has committed, which its
  // revision names.
  const added: { lane: string; model: string }[] = [];
  let reading: { lane: string; model: string } | null = null;
  const tasks = fixtureTaskModels(FIXTURE_CATALOG);
  let committed = 0;
  // The engine record shares the lists' revision, as one stored record
  // holds both. The bundled llama.cpp is the engine until a scenario starts
  // the record on the other.
  let engine: {
    engine: LocalEngine;
    placement: LocalPlacement;
  } = { engine: localEngine ?? "llamacpp", placement: "auto" };
  // Whether the record holds the person's choice: a scenario that starts it
  // on an engine stored one, and any change stores one.
  let engineChosen = localEngine !== undefined;
  // The lists are served as written; a scenario that writes a token the
  // contract does not know breaks the contract on purpose.
  const engineChoicesServed = () => ({
    choices: {
      engine: [
        ...(engineChoices?.engines ?? ["llamacpp", "ollama"]),
      ] as LocalEngine[],
      placement: [
        ...(engineChoices?.placements ?? ["auto", "cpu_only"]),
      ] as LocalPlacement[],
    },
  });
  const engineSnapshot = (): LocalEngineStatus => ({
    unreadable: false,
    chosen: engineChosen,
    ...engine,
    ...engineChoicesServed(),
    revision: revisionOf(committed),
  });
  const listSnapshot = (): LocalModelListStatus => ({
    unreadable: false,
    models: added.map((entry) => ({ ...entry })),
    ...(reading
      ? { reading: { ...reading }, reading_source: "chosen" as const }
      : readingDefault
        ? { reading: { ...readingDefault }, reading_source: "default" as const }
        : { reading: null, reading_source: "none" as const }),
    tasks: tasks.entries(),
    local_lanes: [...FIXTURE_LISTED_LANES],
    revision: revisionOf(committed),
  });
  const guarded = async (expectedRevision: string) => {
    await check();
    if (expectedRevision !== revisionOf(committed))
      throw coded("agent_local_models_revision_conflict");
  };
  /** The models the catalog recommends for a local lane. */
  const recommendedOn = (lane: string): string[] =>
    Object.values(
      (FIXTURE_CATALOG.providers ?? []).find(
        (held) => `${held.provider_id}_${held.transport}` === lane,
      )?.catalog.recommended ?? {},
    );
  // The local lanes' program holds none of their models, or all of them.
  if (localModels)
    for (const held of FIXTURE_CATALOG.providers ?? [])
      if (
        FIXTURE_LISTED_LANES.includes(`${held.provider_id}_${held.transport}`)
      )
        for (const entry of held.catalog.models ?? [])
          models?.mark(entry.model, localModels === "all");
  /** The models of a lane of the catalog the service would answer now, by
   * catalogue lane id, as a run names them. */
  const laneModels = (laneId: string) => {
    if (turnedOff().has(laneId)) return undefined;
    if (state.declared)
      return FIXTURE_DECLARED_CATALOG.catalog.providers
        ?.find((held) => held.id === laneId)
        ?.models?.map((model) => ({
          id: model.id,
          vision: model.vision ?? null,
          licence: model.licence ?? null,
        }));
    return (FIXTURE_CATALOG.providers ?? [])
      .find((held) => `${held.provider_id}_${held.transport}` === laneId)
      ?.catalog.models?.map((entry) => ({
        id: entry.model,
        vision: entry.vision ?? null,
        licence: entry.licence ?? null,
      }));
  };
  const methods: ModelHostMethods = {
    async providerCatalog() {
      say("agentProviderCatalog");
      await check();
      if (state.busy) throw coded("agent_service_busy");
      await window.__fixtureProviderCatalogRead?.();
      const refused = fixtureCatalogRefusal(catalog);
      if (refused) throw refused;
      say("agentProviderCatalogResolved");
      // A lane turned off in the settings is not offered, as the service
      // leaves it out of the catalog it serves; nor is the keyless lane of a
      // local engine other than the one the engine record selects.
      const off = turnedOff();
      const { served: scoped, declared } = catalogsUnderEngine(engine.engine);
      if (state.declared)
        return {
          ...declared,
          catalog: {
            ...declared.catalog,
            providers: (declared.catalog.providers ?? []).filter(
              (lane) => !off.has(lane.id),
            ),
          },
        };
      const served = {
        ...scoped,
        providers: (scoped.providers ?? []).filter((lane) => {
          const id = `${lane.provider_id}_${lane.transport}`;
          return (
            !off.has(id) &&
            (catalog !== "local-only" || id === FIXTURE_LOCAL_LANE) &&
            (catalog !== "engines-only" ||
              lane.provider_id === "llamacpp" ||
              lane.provider_id === "ollama") &&
            (catalog !== "hosted-signed-out" ||
              id === FIXTURE_LOCAL_LANE ||
              id === FIXTURE_HOSTED_SIGNED_OUT_LANE)
          );
        }),
      };
      const stated = engineHealth
        ? withEngineHealth(served, engineHealth)
        : served;
      return withScenarioReads(models ? models.report(stated) : stated);
    },
    async localModels() {
      say("agentLocalModels");
      await check();
      const answered = await window.__fixtureLocalModelsRead?.();
      return answered ?? listSnapshot();
    },
    async addLocalModel(lane, model, expectedRevision) {
      say(`agentLocalModelAdd ${model}`);
      await guarded(expectedRevision);
      // Only a keyless lane on this computer keeps a list.
      if (!FIXTURE_LISTED_LANES.includes(lane) || !laneModels(lane))
        throw coded("agent_local_models_unknown");
      const listed =
        recommendedOn(lane).includes(model) ||
        added.some((entry) => entry.lane === lane && entry.model === model);
      if (listed) return listSnapshot();
      if (added.length >= FIXTURE_LIST_LIMIT)
        throw coded("agent_local_models_full");
      added.push({ lane, model });
      committed += 1;
      return listSnapshot();
    },
    async removeLocalModel(lane, model, expectedRevision) {
      say(`agentLocalModelRemove ${model}`);
      await guarded(expectedRevision);
      const index = added.findIndex(
        (entry) => entry.lane === lane && entry.model === model,
      );
      if (index < 0) throw coded("agent_local_models_unknown");
      added.splice(index, 1);
      committed += 1;
      return listSnapshot();
    },
    async resetLocalModels(expectedRevision) {
      say("agentLocalModelsReset");
      await guarded(expectedRevision);
      added.splice(0, added.length);
      reading = null;
      tasks.clear();
      committed += 1;
      return listSnapshot();
    },
    async localEngine() {
      say("agentLocalEngine");
      await check();
      await window.__fixtureLocalEngineRead?.();
      return engineSnapshot();
    },
    async chooseLocalEngine(chosen, placement, expectedRevision) {
      say(`agentLocalEngineChoose ${chosen} ${placement} ${expectedRevision}`);
      await guarded(expectedRevision);
      await window.__fixtureLocalEngineChange?.();
      if (engine.engine === chosen && engine.placement === placement)
        return engineSnapshot();
      engine = { engine: chosen, placement };
      engineChosen = true;
      committed += 1;
      return engineSnapshot();
    },
    async chooseReadingModel(lane, model, expectedRevision) {
      say(`agentReadingModelChoose ${lane} ${model}`);
      await guarded(expectedRevision);
      // Any lane the catalogue reports, local or not.
      const reported = (FIXTURE_CATALOG.providers ?? []).some(
        (held) => `${held.provider_id}_${held.transport}` === lane,
      );
      if (!reported) throw coded("agent_local_models_unknown");
      if (reading?.lane === lane && reading.model === model)
        return listSnapshot();
      reading = { lane, model };
      committed += 1;
      return listSnapshot();
    },
    async chooseTaskModel(taskKind, choice, expectedRevision) {
      say(`agentTaskModelChoose ${taskKind} ${choice?.model ?? "-"}`);
      await guarded(expectedRevision);
      if (!tasks.served(taskKind, choice))
        throw coded("agent_local_models_unknown");
      if (tasks.choose(taskKind, choice)) committed += 1;
      return listSnapshot();
    },
    async modelLicence(provider, transport, model) {
      say(`agentModelLicence ${model}`);
      await check();
      // Only a ready agent serves licence texts.
      if (state.declared) throw coded("agent_service_not_ready");
      const entry = laneModels(`${provider}_${transport}`)?.find(
        (held) => held.id === model,
      );
      if (!entry?.licence) throw coded("agent_gateway_licence_unknown");
      return {
        provider,
        transport,
        model,
        installed: true,
        spdx: entry.licence.spdx,
        name: entry.licence.name,
        digest: entry.licence.digest,
        text: `${entry.licence.name}\n\nA made-up licence text for ${model}, served by the scenario host.`,
      };
    },
  };

  return {
    state,
    methods,
    changeListElsewhere: () => {
      committed += 1;
    },
    selectedEngine: () => engine.engine,
  };
}

// The reads a model picker's specimen works its offer out from: six made-up
// providers out of the fixture catalog, each standing differently. One is on
// and ready by its API and signed out by its app; one serves forty models
// that take every effort; the lane on this computer lists a model the
// catalog does not, beside one not downloaded; one is not configured; one is
// turned off, so the catalog leaves it out; and one is a local engine that
// does not run.

/** The providers of the specimen, out of the fixture catalog. */
const OFFER_PROVIDERS = new Set([
  "kimi",
  "qwen",
  "zai",
  "deepseek",
  "antigravity",
  "llamacpp",
]);
/** The specimen's provider turned off in its settings. */
const OFFER_OFF = "antigravity_cli";
/** The specimen's lane with many models. */
const OFFER_MANY = "qwen_api";
const OFFER_EFFORTS: Effort[] = [
  "low",
  "medium",
  "high",
  "xhigh",
  "max",
  "ultra",
];

/** Forty made-up models, each taking a run of the efforts from the lowest. */
const manyModels = (): ServedCatalogModel[] =>
  Array.from({ length: 40 }, (_, index): ServedCatalogModel => {
    const number = String(index + 1).padStart(2, "0");
    const efforts = OFFER_EFFORTS.slice(0, (index % OFFER_EFFORTS.length) + 1);
    return {
      entry_id: `example-many-${number}`,
      model: `example-many-${number}`,
      display_name: `Example Many ${number}`,
      ...(index % 5 === 0
        ? { description: `A made-up model, number ${number} of forty.` }
        : {}),
      native_control_ids: [],
      efforts: index % 7 === 6 ? [] : efforts,
      default_effort: index % 3 === 0 ? (efforts[0] ?? null) : null,
      vision: null,
      size_bytes: null,
      context_length: null,
      licence: null,
      llamacpp_default_context: null,
    };
  });

/** What the specimen's settings serve of each lane, by lane id. */
const OFFER_STANDINGS: Record<
  string,
  Pick<
    ProviderSettingsRecord,
    "mode" | "available" | "source" | "readiness" | "reason" | "cli_state"
  > & { credential_saved?: boolean }
> = {
  kimi_api: {
    mode: "key",
    available: true,
    source: "profile",
    readiness: "not_verified",
    credential_saved: true,
  },
  kimi_cli: {
    mode: "unset",
    available: false,
    source: "none",
    readiness: "sign_in_required",
    reason: "sign_in_with_provider_tool",
    cli_state: "installed_signed_out",
  },
  qwen_api: {
    mode: "key",
    available: true,
    source: "profile",
    readiness: "not_verified",
    credential_saved: true,
  },
  // The service never serves readiness "ready": it checks a lane on use.
  qwen_cli: {
    mode: "provider_sign_in",
    available: true,
    source: "none",
    readiness: "not_verified",
    cli_state: "installed_signed_in",
  },
  zai_api: {
    mode: "unset",
    available: true,
    source: "none",
    readiness: "not_verified",
  },
  // An app lane whose app is not on this computer is not set up: it says so
  // and how to get the app, never asks for a key.
  deepseek_cli: {
    mode: "unset",
    available: false,
    source: "none",
    readiness: "sign_in_required",
    reason: "sign_in_with_provider_tool",
    cli_state: "not_installed",
  },
  antigravity_cli: {
    mode: "disabled",
    available: false,
    source: "none",
    readiness: "disabled",
    reason: "turned_off",
  },
  llamacpp_api: {
    mode: "unset",
    available: true,
    source: "none",
    readiness: "not_verified",
  },
};

/** How a specimen's reads stand: the agent ready or still starting, the
 * reading model chosen or a default standing in, what the tasks are set to,
 * and every provider off. */
export type FixtureOfferScene = {
  declared?: boolean;
  reading?: "chosen" | "default" | "none";
  tasks?: readonly TaskModelEntry[];
  allOff?: boolean;
};

/** The catalog, the lists and the settings a specimen's offer is worked out
 * from. */
export function fixtureOfferReads({
  declared = false,
  reading = "default",
  tasks = [],
  allOff = false,
}: FixtureOfferScene = {}): {
  catalog: ServedCatalogAnswer;
  lists: LocalModelListStatus;
  settings: { providers: ProviderSettingsRecord[] };
} {
  const kept = (lane: { provider_id: string; transport: string }) =>
    OFFER_PROVIDERS.has(lane.provider_id) &&
    `${lane.provider_id}_${lane.transport}` !== OFFER_OFF &&
    !allOff;
  const served = withEngineHealth(
    {
      ...FIXTURE_CATALOG,
      providers: (FIXTURE_CATALOG.providers ?? []).filter(kept).map((lane) =>
        `${lane.provider_id}_${lane.transport}` === OFFER_MANY
          ? {
              ...lane,
              catalog: { ...lane.catalog, models: manyModels() },
              background_requests: {
                ...lane.background_requests,
                options: ["effort"],
              },
            }
          : lane,
      ),
    },
    {
      llamacpp: {
        engine: "llamacpp",
        state: "not_running",
        reason: "not_reachable",
        door: "local_ai_setup",
      },
    },
  );
  const catalog: ServedCatalogAnswer = declared
    ? {
        ...FIXTURE_DECLARED_CATALOG,
        catalog: {
          ...FIXTURE_DECLARED_CATALOG.catalog,
          providers: FIXTURE_DECLARED_CATALOG.catalog.providers.filter((lane) =>
            kept({ provider_id: lane.provider, transport: lane.transport }),
          ),
        },
      }
    : served;
  const readingModel = { lane: "zai_api", model: "synthetic-text:1" };
  const lists: LocalModelListStatus = {
    unreadable: false,
    models: [{ lane: "zai_api", model: "synthetic-added:1" }],
    reading: reading === "none" ? null : readingModel,
    reading_source: reading,
    tasks: [...tasks],
    local_lanes: ["zai_api", "llamacpp_api"],
    revision: revisionOf(1),
  };
  const settings = FIXTURE_SETTINGS_LANES.filter((seed) =>
    OFFER_PROVIDERS.has(seed.provider),
  ).flatMap((seed): ProviderSettingsRecord[] => {
    const standing = OFFER_STANDINGS[seed.id];
    if (!standing) return [];
    const off = allOff || seed.id === OFFER_OFF;
    return [
      {
        ...seed,
        ...standing,
        ...(off
          ? {
              mode: "disabled",
              available: false,
              readiness: "disabled",
              reason: "turned_off",
            }
          : {}),
        sign_out_available: false,
        revision: revisionOf(2),
      },
    ];
  });
  return { catalog, lists, settings: { providers: settings } };
}
