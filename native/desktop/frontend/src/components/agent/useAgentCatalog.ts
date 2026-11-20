import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  accountListPause,
  CATALOG_BUSY_QUIET_MS,
  catalogBusyPause,
  catalogReadBusy,
  catalogReadRetry,
} from "../../shell/catalogReadPolicy";
import {
  catalogChoices,
  catalogStillReading,
  intendedProvider,
  laneSelection,
  laneEngines,
  ranSelection,
  readingSelection,
  restoredSelection,
  selectionRecord,
} from "../../shell/agentCatalog";
import { useRememberedChoice } from "../../shell/agentChoice";
import type {
  AgentServiceStatus,
  AgentSession,
} from "../../shell/agentSession";
import type { ServedCatalogAnswer } from "../../shell/agentCatalogContract";
import { useAgentRead } from "../../shell/agentViews";
import { catalogLanes } from "../../shell/localModelLanes";
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
  // The status the service last published, the one the newest catalog read
  // was asked under, and the pauses taken since a read was asked under it.
  const published = useRef(status);
  useLayoutEffect(() => {
    published.current = status;
  }, [status]);
  const askedUnder = useRef(status);
  const busyPauses = useRef(0);
  // The busy wait the column is in: the service state it began under, when
  // its first busy refusal came, and whether its outliving the quiet bound
  // was noted. Busy refusals within the bound are the start the column
  // expects; the first one past it is noted once as a warning.
  const busyWait = useRef<{
    under: AgentServiceStatus["state"];
    since: number;
    noted: boolean;
  } | null>(null);
  // Whether a read is wanted, so a busy refusal is followed by another.
  const reading = useRef(false);
  // Reads asked for by anything but an opening of the settings, which an
  // answer asked before them cannot serve.
  const [catalogAgain, setCatalogAgain] = useState(0);
  const [busyReads, setBusyReads] = useState(0);
  const freshness = catalogAgain + settingsChanges + busyReads;
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
          // A read asked under a newly published status starts its pauses
          // afresh.
          if (askedUnder.current !== published.current) {
            askedUnder.current = published.current;
            busyPauses.current = 0;
          }
          // The wait is keyed by the service's state rather than by each
          // publication, so a repeated notice of the same state does not
          // start it afresh.
          const under = published.current?.state ?? "starting";
          const expected = () => {
            const now = performance.now();
            let wait = busyWait.current;
            if (wait?.under !== under) {
              wait = { under, since: now, noted: false };
              busyWait.current = wait;
            }
            if (wait.noted || now - wait.since < CATALOG_BUSY_QUIET_MS)
              return true;
            wait.noted = true;
            return false;
          };
          const promise = session.providerCatalog(
            catalogReadRetry(() => reading.current, expected),
          );
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
  useLayoutEffect(() => {
    reading.current = readCatalog !== null;
    return () => {
      reading.current = false;
    };
  }, [readCatalog]);
  // Setup, provider settings and a busy answer ask for the catalog
  // independently; an opening joins a read still out.
  const catalog = useAgentRead(
    readCatalog,
    catalogAgain + settingsChanges + busyReads + opened + pickerOpened,
  );
  // A settled setup may have downloaded a model: what the catalog says this
  // computer holds is read again.
  useEffect(() => {
    if (setupSettled) setCatalogAgain((count) => count + 1);
  }, [setupSettled]);
  // The catalog's lanes with their models, whose list a lane on this computer
  // shows in its provider settings.
  const localLanes = useMemo(
    () => (catalog.kind === "ready" ? catalogLanes(catalog.value) : []),
    [catalog],
  );
  // Whether each local engine's lane has its engine running, as the catalog
  // states it, which the lane's provider settings say.
  const engines = useMemo(
    () => (catalog.kind === "ready" ? laneEngines(catalog.value) : {}),
    [catalog],
  );
  // A service still busy starting the agent, or still busy just after it
  // became ready, answers the catalog late. The column says the agent is
  // still starting and asks again: at once when the service published a
  // status after the busy read was asked, and otherwise after a pause that
  // grows to a ceiling, until the service answers. A read the published
  // status already caused is not repeated at once, so two reads never land
  // back to back in the same busy moment. A session the runtime keeps
  // suspended is the same wait: it is not a sign-out and it comes back.
  const catalogBusy =
    catalog.kind === "failed" && catalogReadBusy(catalog.code);
  // The repeat stops when the catalog loads, when no read is wanted because
  // the service reports it stopped or refused, or the profile is gone, and
  // when the hook unmounts: each ends with the cleanup clearing the pending
  // pause, and nothing schedules another. Only a newly published status or
  // the person's retry asks again after that.
  const followBusy = catalogBusy && readCatalog !== null;
  useEffect(() => {
    if (catalog.kind === "ready") busyPauses.current = 0;
    // An answer, or a refusal that waiting does not cure, ends the busy wait.
    if (
      catalog.kind === "ready" ||
      (catalog.kind === "failed" && !catalogReadBusy(catalog.code))
    )
      busyWait.current = null;
    if (!followBusy) return;
    if (askedUnder.current !== status) {
      setBusyReads((count) => count + 1);
      return;
    }
    const pause = catalogBusyPause(busyPauses.current);
    busyPauses.current += 1;
    const again = window.setTimeout(
      () => setBusyReads((count) => count + 1),
      pause,
    );
    return () => window.clearTimeout(again);
  }, [catalog, followBusy, status]);
  // A cold read answers a lane's packaged model list as stale, or a lane's
  // sign-in or catalog as not yet known, while the service is still reading
  // it; the settled answer is served on a later read. So the catalog is read
  // again, after pauses that grow to a ceiling, for as long as the served
  // catalog says some lane is still being read. The count starts afresh for a
  // new reader and once nothing is being read, and the pending pause is
  // cleared when the catalog changes or the hook unmounts.
  const accountReads = useRef({ reader, count: 0 });
  if (accountReads.current.reader !== reader)
    accountReads.current = { reader, count: 0 };
  const stillReading =
    catalog.kind === "ready" && catalogStillReading(catalog.value);
  useEffect(() => {
    const reads = accountReads.current;
    if (!stillReading) {
      reads.count = 0;
      return;
    }
    const again = window.setTimeout(() => {
      reads.count += 1;
      setCatalogAgain((count) => count + 1);
    }, accountListPause(reads.count));
    return () => window.clearTimeout(again);
  }, [stillReading, catalog, reader]);
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
  const stored = useReadingModel(
    readCatalog ? readingHost : null,
    rememberedRecord,
    catalogAgain + settingsChanges + opened + listChanges,
    reader,
  );
  const offer = useMemo(() => {
    if (catalog.kind !== "ready") return null;
    const lists =
      stored === null
        ? null
        : {
            lanes: stored.local_lanes,
            added: (lane: string) =>
              !stored.unreadable
                ? stored.models
                    .filter((entry) => entry.lane === lane)
                    .map((entry) => entry.model)
                : [],
          };
    return catalogChoices(t, catalog.value, lists);
  }, [catalog, t, stored]);
  // Only a choice the picker still offers is the one documents are read
  // with; one it no longer offers, such as a model taken off its list, is not.
  const restoredRemembered =
    offer && remembered ? restoredSelection(offer, [remembered]) : null;
  const offeredRemembered =
    remembered &&
    restoredRemembered?.wayId === remembered.wayId &&
    restoredRemembered.modelId === remembered.modelId &&
    catalog.kind === "ready"
      ? selectionRecord(catalog.value, remembered)
      : null;
  const wantedLane = offeredRemembered
    ? `${offeredRemembered.provider}_${offeredRemembered.transport}`
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
    stored?.unreadable === false && stored.reading && catalog.kind === "ready"
      ? readingSelection(catalog.value, stored.reading)
      : null;
  const heldChoices = [
    chosen,
    ranWith && catalog.kind === "ready"
      ? ranSelection(catalog.value, ranWith)
      : null,
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
    localLanes,
    engines,
    offer,
    selection,
    provider,
    remember,
    /** Reads the catalog again after a failed read, at once, and starts the
     * pauses before any busy re-read afresh. */
    retry: () => {
      busyPauses.current = 0;
      setCatalogRetry((count) => count + 1);
    },
    /** Reads the catalog again: what this computer holds changed. */
    refresh: () => setCatalogAgain((count) => count + 1),
  };
}
