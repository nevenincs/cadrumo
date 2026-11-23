import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { catalogReadBusy } from "../../shell/catalogReadPolicy";
import {
  intendedProvider,
  laneSelection,
  ranSelection,
  readingSelection,
  restoredSelection,
  selectionRecord,
} from "../../shell/agentCatalog";
import {
  agentOffer,
  catalogStillReading,
  laneIdOf,
} from "../../shell/agentOffer";
import { useRememberedChoice } from "../../shell/agentChoice";
import type {
  AgentServiceStatus,
  AgentSession,
} from "../../shell/agentSession";
import type { ServedCatalogAnswer } from "../../shell/agentCatalogContract";
import type { ProviderSettingsAnswer } from "../../shell/providerSettingsContract";
import { useAgentRead } from "../../shell/agentViews";
import { modelListState, useWindowReturn } from "../../shell/modelListState";
import {
  useReadingModel,
  type ReadingModelHost,
} from "../../shell/readingModel";
import type { Translate } from "../../shell/strings";
import type { AgentSelection } from "./types";
import type { AgentRanWith } from "../../shell/agentSnapshotContract";

/**
 * What the agent can run, which is the agent's own catalog, every lane of
 * it, and what the next message runs with. While the agent starts, the
 * service answers with the lanes the agent declares, which are listed but
 * cannot be chosen; the catalog is read again once the agent is ready, after
 * a settled setup, and as the provider settings or the local lists change.
 */
export function useAgentCatalog({
  t,
  reader,
  session,
  status,
  readingHost,
  setupSettled,
  settingsChanges,
  settings,
  opened,
  listChanges,
  pickerOpened,
  chosen,
  ranWith,
  fixedWay,
}: {
  t: Translate;
  reader: string | null;
  session: AgentSession | undefined;
  status: AgentServiceStatus | null;
  /** The local lists and the reading model, where the agent runs. */
  readingHost: ReadingModelHost | null;
  /** The last setup that settled, by operation. */
  setupSettled: string | null;
  /** Changes made in the provider settings. */
  settingsChanges: number;
  /** The provider settings as last read; null while unread. */
  settings: Pick<ProviderSettingsAnswer, "providers"> | null;
  /** How many times the settings were opened. */
  opened: number;
  /** Changes made to the local lists. */
  listChanges: number;
  /** How many times the model picker was opened. */
  pickerOpened: number;
  /** What the person chose while the conversation is shown. */
  chosen: AgentSelection | null;
  /** What the conversation shown last ran with. */
  ranWith: AgentRanWith | undefined;
  /** The lane the conversation shown is fixed to, by way id; null for a
   * conversation that has not run. */
  fixedWay: string | null;
}) {
  const ready = status?.state === "ready";
  const starting = status?.state === "starting";
  const [catalogRetry, setCatalogRetry] = useState(0);
  // The status the service last published, and the one the newest catalog
  // read was asked under, so a publication that already caused a read does
  // not cause a second one.
  const published = useRef(status);
  useLayoutEffect(() => {
    published.current = status;
  }, [status]);
  const askedUnder = useRef(status);
  // Reads asked for by anything but an opening of the settings, which an
  // answer asked before them cannot serve.
  const [catalogAgain, setCatalogAgain] = useState(0);
  const freshness = catalogAgain + settingsChanges;
  const fresh = useRef(freshness);
  useLayoutEffect(() => {
    fresh.current = freshness;
  }, [freshness]);
  const catalogRequest = useMemo(
    () => ({ reader, ready, starting, session, retry: catalogRetry }),
    [reader, ready, starting, session, catalogRetry],
  );
  const readCatalog = useMemo(() => {
    const { reader, ready, starting, session } = catalogRequest;
    // The read still out, which an opening of the settings shares rather
    // than asking the catalog a second time.
    let out: { promise: Promise<ServedCatalogAnswer>; fresh: number } | null =
      null;
    return reader !== null && (ready || starting) && session
      ? () => {
          if (out && out.fresh === fresh.current) return out.promise;
          askedUnder.current = published.current;
          // A refusal that says where setup stands is noted as that state:
          // nothing is scheduled after it, and the next cue reads again.
          const promise = session.providerCatalog();
          const mine = { promise, fresh: fresh.current };
          out = mine;
          const settled = () => {
            if (out === mine) out = null;
          };
          promise.then(settled, settled);
          return promise;
        }
      : null;
  }, [catalogRequest]);
  // Setup, provider settings and the cues of a wait ask for the catalog
  // independently; an opening joins a read still out.
  const catalog = useAgentRead(
    readCatalog,
    catalogAgain + settingsChanges + opened + pickerOpened,
  );
  // A settled setup may have downloaded a model: what the catalog says this
  // computer holds is read again.
  useEffect(() => {
    if (setupSettled) setCatalogAgain((count) => count + 1);
  }, [setupSettled]);
  // A service still busy starting the agent, or still busy just after it
  // became ready, answers the catalog late; a session the runtime keeps
  // suspended is the same wait: it is not a sign-out and it comes back.
  const catalogBusy =
    catalog.kind === "failed" && catalogReadBusy(catalog.code);
  // A catalog that answered where setup stands, or that says the service is
  // still reading some lane (a packaged model list in place of the
  // account's, a sign-in or catalog not yet known), waits on a cue: a status
  // the service publishes, the person coming back to the window, opening the
  // picker or the settings, or a setup they ran. No timer asks again.
  const stillReading =
    catalog.kind === "ready" && catalogStillReading(catalog.value);
  const catalogWaits =
    readCatalog !== null &&
    ((catalog.kind === "failed" && modelListState(catalog.code) !== null) ||
      stillReading);
  useEffect(() => {
    if (catalogWaits && askedUnder.current !== status)
      setCatalogAgain((count) => count + 1);
  }, [catalogWaits, status]);
  // What the next message runs with: what the person chose while this
  // conversation is shown, else what the conversation last ran with, else the
  // profile's last choice, each only where the catalog still offers it.
  const { remembered, remember } = useRememberedChoice(reader);
  // The person's last choice is also the model documents are read with. The
  // service keeps it beside the local lists, which are also what the picker
  // offers of a lane on this computer.
  const [rememberedRecord, setRememberedRecord] = useState<{
    lane: string;
    model: string;
  } | null>(null);
  // Read only where the catalog is: a profile is signed in and the agent runs.
  const lists = useReadingModel(
    readCatalog ? readingHost : null,
    rememberedRecord,
    catalogAgain + settingsChanges + opened + pickerOpened + listChanges,
    reader,
  );
  const { stored, retry: retryLists } = lists;
  const listsWait =
    lists.failure !== null && modelListState(lists.failure) !== null;
  // Lists that answered where setup stands are read again once the service
  // publishes a status after that answer.
  const listsSeen = useRef(status);
  useEffect(() => {
    if (listsWait && listsSeen.current !== status) retryLists();
    listsSeen.current = status;
  }, [listsWait, status, retryLists]);
  // The person coming back to the window is a cue for whatever still waits.
  useWindowReturn(
    catalogWaits || listsWait
      ? () => {
          if (catalogWaits) setCatalogAgain((count) => count + 1);
          else retryLists();
        }
      : null,
  );
  // What the agent offers, from the catalog, the lists and the settings,
  // worked out once for every surface of the column.
  const offer = useMemo(
    () =>
      catalog.kind === "ready"
        ? agentOffer(t, catalog.value, stored, settings)
        : null,
    [catalog, t, stored, settings],
  );
  // Only a choice the picker still offers is the one documents are read
  // with; one it no longer offers, such as a model taken off its list, is not.
  const restoredRemembered =
    offer && remembered ? restoredSelection(offer, [remembered]) : null;
  const offeredRemembered =
    remembered &&
    restoredRemembered?.wayId === remembered.wayId &&
    restoredRemembered.modelId === remembered.modelId &&
    offer
      ? selectionRecord(offer, remembered)
      : null;
  const wantedLane = offeredRemembered
    ? laneIdOf(offeredRemembered.provider, offeredRemembered.transport)
    : null;
  const wantedModel = offeredRemembered?.model ?? null;
  if (
    (rememberedRecord?.lane ?? null) !== wantedLane ||
    (rememberedRecord?.model ?? null) !== wantedModel
  )
    setRememberedRecord(
      wantedLane !== null && wantedModel !== null
        ? { lane: wantedLane, model: wantedModel }
        : null,
    );
  // The model the service reads documents with, chosen or the installed
  // default it serves, stands in for a choice the person has not made, so
  // the picker shows what a reading runs with rather than a start of its own.
  const servedReading =
    stored?.unreadable === false && stored.reading && offer
      ? readingSelection(offer, stored.reading)
      : null;
  const heldChoices = [
    chosen,
    ranWith && offer ? ranSelection(offer, ranWith) : null,
    remembered,
    servedReading,
  ];
  // A conversation fixed to a lane runs on it or not at all: a choice the
  // catalog offers only in another lane is never sent in its place.
  const selection = offer
    ? fixedWay !== null
      ? laneSelection(offer, heldChoices, fixedWay)
      : restoredSelection(offer, heldChoices)
    : null;
  // The provider the person is on. Where no way can run there is no selection,
  // and it is the provider they chose last, else the first the catalog serves.
  const provider = offer
    ? selection
      ? offer.providers.find((one) => one.id === selection.providerId)
      : intendedProvider(offer, heldChoices)
    : undefined;
  return {
    catalog,
    catalogBusy,
    /** Why the person's lists could not be read, which the picker says in
     * place of offering the local lanes' lists, and the way to read them
     * again; null once they are read. */
    lists: { failure: lists.failure, retry: retryLists },
    offer,
    selection,
    provider,
    remember,
    /** Reads the catalog again after a failed read, at once. */
    retry: () => setCatalogRetry((count) => count + 1),
    /** Reads the catalog again: what this computer holds changed. */
    refresh: () => setCatalogAgain((count) => count + 1),
  };
}
