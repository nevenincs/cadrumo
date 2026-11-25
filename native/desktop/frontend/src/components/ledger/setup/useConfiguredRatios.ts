// The business-use ratios configured for the years of the movements the
// page shows, as Mixed names them: a Mixed movement's usage ratio is the
// category whose ratio is configured for its year. Read per year through
// `ledger.ratios.list`, again after the page's re-read and on `reload`,
// and dropped with the profile.

import { useCallback, useEffect, useState } from "react";
import type { LedgerPort } from "../../../shell/ledger";
import type { ConfiguredRatios } from "../../../shell/ledgerCommands";
import { useWritePause } from "../WritePause";
import { setupCall } from "./setupModel";

/** The ratios configured for each of `years`: a year not read yet is
 * absent, and one that could not be read, or whose ratios the censo
 * withholds, is null. */
export function useConfiguredRatios(
  port: LedgerPort,
  reader: string | null,
  years: readonly number[],
): { ratios: ConfiguredRatios; reload(): void } {
  const [ratios, setRatios] = useState<ConfiguredRatios>(new Map());
  const [round, setRound] = useState(0);
  const { round: reread } = useWritePause();
  const key = [...new Set(years)].sort().join(" ");
  useEffect(() => {
    setRatios(new Map());
    if (reader === null || key === "") return;
    let active = true;
    for (const year of key.split(" ").map(Number))
      void setupCall(port, "ledger.ratios.list", { year }, false).then(
        (read) => {
          if (!active) return;
          const found =
            read.kind === "done" && read.result.outcome === "available"
              ? new Set(read.result.rows.map((row) => row.category))
              : null;
          setRatios((before) => new Map(before).set(year, found));
        },
      );
    return () => {
      active = false;
    };
  }, [port, reader, key, round, reread]);
  const reload = useCallback(() => setRound((value) => value + 1), []);
  return { ratios, reload };
}
