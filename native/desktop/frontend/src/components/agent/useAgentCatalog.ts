import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  catalogBusyPause,
  catalogReadBusy,
  catalogReadRetry,
} from "../../shell/catalogReadPolicy";
import {
  catalogChoices,
  ranSelection,
  restoredSelection,
  selectionRecord,
} from "../../shell/agentCatalog";
import { useRememberedChoice } from "../../shell/agentChoice";
import type {
  AgentServiceStatus,
  AgentSession,
} from "../../shell/agentSession";
import { useAgentRead, type AgentRanWith } from "../../shell/agentViews";
import { catalogLanes } from "../../shell/localModelLanes";
import {
  useReadingModel,
  type ReadingModelHost,
} from "../../shell/readingModel";
import type { Translate } from "../../shell/strings";
import type { AgentSelection } from "./types";

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
  chosen,
  ranWith,
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
  /** What the person chose while the conversation is shown. */
  chosen: AgentSelection | null;
  /** What the conversation shown last ran with. */
  ranWith: AgentRanWith | undefined;
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
  // Whether a read is wanted, so a busy refusal is followed by another.
  const reading = useRef(false);
  const catalogRequest = useMemo(
    () => ({ reader, ready, starting, session, retry: catalogRetry }),
    [reader, ready, starting, session, catalogRetry],
  );
  const readCatalog = useMemo(() => {
    const { reader, ready, starting, session } = catalogRequest;
    return reader !== null && (ready || starting) && session
      ? () => {
          // A read asked under a newly published status starts its pauses
          // afresh.
          if (askedUnder.current !== published.current) {
            askedUnder.current = published.current;
            busyPauses.current = 0;
          }
          return session.providerCatalog(
            catalogReadRetry(() => reading.current),
          );
        }
      : null;
  }, [catalogRequest]);
  useLayoutEffect(() => {
    reading.current = readCatalog !== null;
    return () => {
      reading.current = false;
    };
  }, [readCatalog]);
  // Setup and provider settings invalidate the catalog independently.
  const [catalogAgain, setCatalogAgain] = useState(0);
  // Reads asked for while the service was busy.
  const [busyReads, setBusyReads] = useState(0);
  const catalog = useAgentRead(
    readCatalog,
    catalogAgain + settingsChanges + busyReads + opened,
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
              stored.state === "readable"
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
  const selection = offer
    ? restoredSelection(offer, [
        chosen,
        ranWith && catalog.kind === "ready"
          ? ranSelection(catalog.value, ranWith)
          : null,
        remembered,
      ])
    : null;
  return {
    catalog,
    catalogBusy,
    localLanes,
    offer,
    selection,
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
