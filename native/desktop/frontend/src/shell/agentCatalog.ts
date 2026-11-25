import type {
  AgentSelection,
  ModelOption,
  ProviderOption,
  ProviderWay,
} from "@/components/agent/types";
import type { AgentSelectionRecord } from "./agentSession";
import type { LocalModelListEntry } from "./localModelsContract";
import type { AgentRanWith } from "./agentSnapshotContract";
import { heldModel, type AgentOffer, type OfferedLane } from "./agentOffer";

// What the agent column runs with, chosen among what the agent offers
// (agentOffer.ts): the selection kept, restored or started, and the record a
// run start takes. A run takes a provider, a transport, a model and an
// effort, and nothing else (AgentSpec, agent/spec.py): the execution mode and
// the catalog entry are the service's to resolve.

/** The column's choices of an offer: its providers and each way's models. */
export type OfferChoices = Pick<AgentOffer, "providers" | "models">;

/** The observed lane `way` names, by way id; none while only declared. */
const laneOfWay = (
  offer: Pick<AgentOffer, "observed" | "lanes">,
  way: string,
): OfferedLane | undefined =>
  offer.observed
    ? [...offer.lanes.values()].find((held) => held.wayId === way)
    : undefined;

/** Whether some way into `provider` lists a model this computer does not hold
 * yet, so that downloading one is a way on for it. A hosted provider has no
 * model to download. */
export const providerModelsToDownload = (provider: ProviderOption) =>
  provider.ways.some((way) => way.modelsToDownload === true);

/**
 * The provider the person is on, even where none of its ways can run now: the
 * provider of the first of `held` the offer serves, else the first provider
 * served, which is where a start with nothing kept begins. Undefined only for
 * an offer serving no provider.
 */
export function intendedProvider(
  choices: OfferChoices,
  held: readonly (AgentSelection | null | undefined)[],
): ProviderOption | undefined {
  for (const selection of held) {
    const provider = choices.providers.find(
      (one) => one.id === selection?.providerId,
    );
    if (provider) return provider;
  }
  return choices.providers[0];
}

/** The model a way starts with: the catalog's recommendation where it lists
 * it, else its first, each only where this computer holds it. */
export function startingModel(
  way: ProviderWay,
  models: readonly ModelOption[],
): ModelOption | undefined {
  const held = models.filter((model) => heldModel(model));
  return held.find((model) => model.id === way.defaultModelId) ?? held[0];
}

/** What a provider starts with once `way` is chosen: its starting model, or,
 * where the person writes the model, none yet. It holds no effort: a model's
 * default is the provider's to apply, and an effort is held only once the
 * person has chosen one. */
export function startingSelection(
  provider: ProviderOption,
  way: ProviderWay,
  models: readonly ModelOption[],
): AgentSelection | null {
  if (way.modelWritten)
    return { providerId: provider.id, wayId: way.id, modelId: "" };
  const model = startingModel(way, models);
  if (!model) return null;
  return { providerId: provider.id, wayId: way.id, modelId: model.id };
}

/** The way and model `selection` names, where the offer has a way that can
 * be chosen and, unless the person writes the model, that model in it. */
function offeredParts(choices: OfferChoices, selection: AgentSelection) {
  const provider = choices.providers.find(
    (held) => held.id === selection.providerId,
  );
  const way = provider?.ways.find((held) => held.id === selection.wayId);
  const model = choices.models[selection.wayId]?.find(
    (held) => held.id === selection.modelId && heldModel(held),
  );
  if (!way?.selectable || !(way.modelWritten || model)) return null;
  return { efforts: way.modelWritten?.efforts ?? model?.efforts ?? [] };
}

/** `selection` where the offer still has it, else where the first way that
 * can be chosen starts; null when none can. */
export function offeredSelection(
  choices: OfferChoices,
  selection: AgentSelection | null,
): AgentSelection | null {
  return restoredSelection(choices, [selection], false);
}

/**
 * The first of `held` the offer still has, else where the first way that can
 * be chosen starts; null when none can. A choice kept from before, such as
 * the last one made or the one a conversation ran with, can name an effort
 * its model no longer takes: with `dropEffort` that effort is left out and
 * the rest of the choice kept, so the provider's default applies.
 */
export function restoredSelection(
  choices: OfferChoices,
  held: readonly (AgentSelection | null | undefined)[],
  dropEffort = true,
): AgentSelection | null {
  for (const selection of held) {
    if (!selection) continue;
    const parts = offeredParts(choices, selection);
    if (!parts) continue;
    const { effort } = selection;
    if (effort === undefined || parts.efforts.some((one) => one.id === effort))
      return selection;
    if (!dropEffort) continue;
    return {
      providerId: selection.providerId,
      wayId: selection.wayId,
      modelId: selection.modelId,
    };
  }
  for (const provider of choices.providers) {
    for (const way of provider.ways) {
      if (!way.selectable) continue;
      const start = startingSelection(
        provider,
        way,
        choices.models[way.id] ?? [],
      );
      if (start) return start;
    }
  }
  return null;
}

// A model id the agent accepts: bounded, with no control character
// (agent/spec.py `MODEL_ID_PATTERN`, `MAX_MODEL_ID_CHARS`).
const MODEL_ID_MAX = 512;
const isModelId = (id: string) =>
  id.length > 0 &&
  id.length <= MODEL_ID_MAX &&
  [...id].every((char) => {
    const code = char.codePointAt(0) ?? 0;
    return code > 0x1f && code !== 0x7f;
  });

/** What a send runs with, as a run start takes it; null while the model is
 * not one the way offers or the person has written, or one the catalog says
 * this computer does not hold. */
export function selectionRecord(
  offer: Pick<AgentOffer, "observed" | "lanes">,
  selection: AgentSelection,
): AgentSelectionRecord | null {
  const lane = laneOfWay(offer, selection.wayId);
  if (!lane) return null;
  const base = { provider: lane.provider, transport: lane.transport };
  if (lane.modelWritten) {
    const model = selection.modelId.trim();
    if (!isModelId(model)) return null;
    const effort = lane.modelWritten.efforts.find(
      (held) => held === selection.effort,
    );
    return { ...base, model, ...(effort ? { effort } : {}) };
  }
  const entry = lane.models.find((held) => held.entryId === selection.modelId);
  // A model the catalog says this computer lacks is not run.
  if (!entry || entry.installed === false) return null;
  const effort = entry.efforts.find((held) => held === selection.effort);
  return { ...base, model: entry.model, ...(effort ? { effort } : {}) };
}

/** The name the picker gives the model `model` (the id a run names) in the
 * lane `way`: the catalog's own name, and the id itself only where the
 * catalog does not list it, as for a model the person writes. */
export function modelDisplayName(
  offer: Pick<AgentOffer, "observed" | "lanes">,
  way: string | null,
  model: string,
): string {
  const lane = way === null ? undefined : laneOfWay(offer, way);
  return lane?.models.find((held) => held.model === model)?.name ?? model;
}

/** The model the service reads documents with, as the column holds a choice:
 * null where the offer does not have its lane or no longer lists it. */
export function readingSelection(
  offer: Pick<AgentOffer, "observed" | "lanes">,
  reading: LocalModelListEntry,
): AgentSelection | null {
  const lane = offer.observed ? offer.lanes.get(reading.lane) : undefined;
  if (!lane) return null;
  return ranSelection(offer, {
    provider: lane.provider,
    transport: lane.transport,
    model: reading.model,
  });
}

/** The choice a run was made with, as the column holds it: the inverse of
 * `selectionRecord`. Null where the offer no longer has its lane, or no
 * longer lists its model, or where the agent served no provider or model. */
export function ranSelection(
  offer: Pick<AgentOffer, "observed" | "lanes">,
  ran: Pick<AgentRanWith, "transport"> & {
    provider: string | null;
    model: string | null;
    effort?: AgentRanWith["effort"];
  },
): AgentSelection | null {
  if (ran.provider === null || ran.model === null || !offer.observed)
    return null;
  const lane = [...offer.lanes.values()].find(
    (held) =>
      held.provider === ran.provider && held.transport === ran.transport,
  );
  if (!lane) return null;
  const effort = ran.effort ? { effort: ran.effort } : {};
  const base = { providerId: lane.provider, wayId: lane.wayId };
  if (lane.modelWritten) return { ...base, modelId: ran.model, ...effort };
  const entry = lane.models.find((held) => held.model === ran.model);
  return entry && entry.entryId !== null
    ? { ...base, modelId: entry.entryId, ...effort }
    : null;
}

/**
 * What a conversation fixed to the lane `way` runs with next: the first of
 * `held` in that lane the offer still has, else where that lane starts; null
 * while the lane cannot be chosen. A choice in another lane is never taken in
 * its place: a conversation keeps its lane, and the person changes lanes only
 * by starting a new conversation.
 */
export function laneSelection(
  choices: OfferChoices,
  held: readonly (AgentSelection | null | undefined)[],
  way: string,
): AgentSelection | null {
  const providers = choices.providers.flatMap((provider) => {
    const ways = provider.ways.filter((one) => one.id === way);
    return ways.length > 0 ? [{ ...provider, ways }] : [];
  });
  return restoredSelection(
    { ...choices, providers },
    held.filter((selection) => selection?.wayId === way),
  );
}
