// How the plan and the timeline read their element: one attempt per read,
// again after the page re-reads a write it had to hold, and never drawn
// after a later read replaced it. They write nothing and keep nothing.

import { useCallback, useEffect, useState } from "react";
import type { LedgerPort } from "../../../shell/ledger";
import { useWritePause } from "../WritePause";
import { callFailure, callOutcome, type SetupCall } from "../setup/setupModel";
import { submitProvisional, type ProvisionalResults } from "./assetsContract";

type PlanResult = ProvisionalResults["ledger.actividad-asset.plan"];
type TimelineResult = ProvisionalResults["ledger.actividad-asset.timeline"];

export const readPlan = async (
  port: LedgerPort,
  assetId: string,
): Promise<SetupCall<PlanResult>> => {
  try {
    return callOutcome(
      await submitProvisional(port, "ledger.actividad-asset.plan", {
        asset_id: assetId,
      }),
      false,
    );
  } catch (error) {
    return callFailure(error);
  }
};

export const readTimeline = async (
  port: LedgerPort,
  assetId: string,
): Promise<SetupCall<TimelineResult>> => {
  try {
    return callOutcome(
      await submitProvisional(port, "ledger.actividad-asset.timeline", {
        asset_id: assetId,
      }),
      false,
    );
  } catch (error) {
    return callFailure(error);
  }
};

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
