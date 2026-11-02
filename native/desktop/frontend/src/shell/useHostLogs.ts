import { useEffect, useRef, useState } from "react";
import type { LogRecord, LogSourceStates } from "@/ipc/contract";
import type { Host } from "./host";
import { notifyInternalFailure } from "./internalFailures";

const RECORD_CAP = 10000;

export function useHostLogs(host: Host) {
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  const retrying = useRef(false);
  const owner = useRef(host);
  owner.current = host;
  // The log ring and what it has lost, held together: a batch changes both.
  const [log, setLog] = useState<{
    owner: Host;
    records: LogRecord[] | null;
    dropped: number;
    interrupted: boolean;
  }>({ owner: host, records: null, dropped: 0, interrupted: false });
  const { records, dropped, interrupted } = log;
  const [sourceStates, setSourceStates] = useState<
    LogSourceStates | "unavailable" | null
  >(null);
  if (log.owner !== host) {
    setLog({ owner: host, records: null, dropped: 0, interrupted: false });
    setSourceStates(null);
  }
  // Log batches: a bounded ring; a missing or unreadable source keeps its state.
  useEffect(() => {
    const version = generation.current;
    const attachedAt = Date.now();
    let unsubscribe: (() => void) | null = null;
    let current = true;
    host
      .subscribeLogs((batch) => {
        if (
          !current ||
          owner.current !== host ||
          version !== generation.current
        )
          return;
        if (
          batch.records.some(
            (record) =>
              record.source === "host" &&
              record.timestampMs !== null &&
              record.timestampMs >= attachedAt &&
              (record.level === "ERROR" || record.level === "CRITICAL") &&
              record.context.diagnostic_origin !== "frontend",
          )
        )
          notifyInternalFailure();
        setSourceStates(batch.states);
        setLog((held) => {
          const previous = held.owner === host ? (held.records ?? []) : [];
          // A new subscription replays a backlog using the same host sequence.
          const last = previous.at(-1)?.seq;
          const next =
            last !== undefined &&
            batch.records.some((record) => record.seq <= last)
              ? [
                  ...new Map(
                    [...previous, ...batch.records].map((record) => [
                      record.seq,
                      record,
                    ]),
                  ).values(),
                ].sort((a, b) => a.seq - b.seq)
              : [...previous, ...batch.records];
          const over = Math.max(0, next.length - RECORD_CAP);
          return {
            owner: host,
            records: over ? next.slice(over) : next,
            dropped: held.dropped + batch.dropped + over,
            interrupted:
              held.interrupted ||
              (attempt > 0 &&
                last !== undefined &&
                batch.records.length > 0 &&
                batch.records[0]!.seq > last + 1),
          };
        });
      })
      .then((stop) => {
        if (
          current &&
          owner.current === host &&
          version === generation.current
        ) {
          unsubscribe = stop;
          retrying.current = false;
        } else stop();
      })
      .catch(() => {
        if (
          current &&
          owner.current === host &&
          version === generation.current
        ) {
          current = false;
          retrying.current = false;
          setSourceStates("unavailable");
          notifyInternalFailure();
        }
      });
    return () => {
      current = false;
      unsubscribe?.();
    };
  }, [host, attempt]);

  const retry = () => {
    if (sourceStates !== "unavailable" || retrying.current) return;
    retrying.current = true;
    generation.current += 1;
    setSourceStates(null);
    setAttempt((value) => value + 1);
  };
  return { records, dropped, sourceStates, interrupted, retry };
}
