// How the plan and the timeline read their element: one attempt per read,
// again after the page re-reads a write it had to hold, and never drawn
// after a later read replaced it. They write nothing and keep nothing.

import { useCallback, useEffect, useState } from "react";
import type { LedgerPort } from "../../../shell/ledger";
import type {
  ActivityAssetPlanResult,
  ActivityAssetTimelineResult,
  TimelineClaimUse,
} from "../../../shell/ledgerSetup";
import { useWritePause } from "../WritePause";
import { setupCall, type SetupCall } from "../setup/setupModel";

export const readPlan = (
  port: LedgerPort,
  assetId: string,
): Promise<SetupCall<ActivityAssetPlanResult>> =>
  setupCall(port, "ledger.actividad-asset.plan", { asset_id: assetId }, false);

export const readTimeline = (
  port: LedgerPort,
  assetId: string,
): Promise<SetupCall<ActivityAssetTimelineResult>> =>
  setupCall(
    port,
    "ledger.actividad-asset.timeline",
    { asset_id: assetId },
    false,
  );

/**
 * Reads one element's plan or timeline while the view shows, and again when
 * the element changes or the page re-reads. A null `reader` means the account
 * withholds the ledger: nothing is read. Omitted, the port's own ledger is.
 */
export function useAssetRead<Result>(
  load: (port: LedgerPort, assetId: string) => Promise<SetupCall<Result>>,
  port: LedgerPort,
  reader: string | null | undefined,
  assetId: string,
): { read: SetupCall<Result> | null; reload(): void } {
  const [read, setRead] = useState<SetupCall<Result> | null>(null);
  const [round, setRound] = useState(0);
  const { round: reread } = useWritePause();
  useEffect(() => {
    setRead(null);
    if (reader === null) return;
    let active = true;
    void load(port, assetId).then((answer) => {
      if (active) setRead(answer);
    });
    return () => {
      active = false;
    };
  }, [load, port, reader, assetId, round, reread]);
  const reload = useCallback(() => setRound((value) => value + 1), []);
  return { read, reload };
}

/** What the history says of each claim: whether it still matches the schedule,
 * why not, and what uses it. Empty while the history is not read, or where it
 * was refused, so no claim is marked from a history that was not read. */
export function claimUses(
  read: SetupCall<ActivityAssetTimelineResult> | null,
): ReadonlyMap<string, TimelineClaimUse> {
  const uses = new Map<string, TimelineClaimUse>();
  if (read?.kind !== "done" || read.result.events === null) return uses;
  for (const event of read.result.events)
    if (event.claim !== null) uses.set(event.record_id, event.claim);
  return uses;
}
