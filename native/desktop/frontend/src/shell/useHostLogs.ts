import { useEffect, useState } from "react";
import type { LogRecord, LogSourceStates } from "@/ipc/contract";
import type { Host } from "./host";

const RECORD_CAP = 10000;

export function useHostLogs(host: Host) {
  // The log ring and what it has lost, held together: a batch changes both.
  const [log, setLog] = useState<{
    records: LogRecord[] | null;
    dropped: number;
  }>({ records: null, dropped: 0 });
  const { records, dropped } = log;
  const [sourceStates, setSourceStates] = useState<
    LogSourceStates | "unavailable" | null
  >(null);
  // Log batches: a bounded ring; a missing or unreadable source keeps its state.
  useEffect(() => {
    let unsubscribe: (() => void) | null = null;
    let current = true;
    host
      .subscribeLogs((batch) => {
        if (!current) return;
        setSourceStates(batch.states);
        setLog((held) => {
          const next = [...(held.records ?? []), ...batch.records];
          const over = Math.max(0, next.length - RECORD_CAP);
          return {
            records: over ? next.slice(over) : next,
            dropped: held.dropped + batch.dropped + over,
          };
        });
      })
      .then((stop) => {
        if (current) unsubscribe = stop;
        else stop();
      })
      .catch(() => {
        if (current) setSourceStates("unavailable");
      });
    return () => {
      current = false;
      unsubscribe?.();
    };
  }, [host]);

  return { records, dropped, sourceStates };
}
