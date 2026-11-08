import { useEffect, useRef, useState } from "react";
import type { LogRecord, LogSourceStates } from "@/ipc/contract";
import type { Host } from "./host";
import { notifyInternalFailure } from "./internalFailures";

const RECORD_CAP = 10000;

/** How many errors and warnings arrived since the window began following the
 * log, each counted once by its host sequence, whatever the ring still holds. */
export type LogCounts = { errors: number; warnings: number };

const NO_LOG = {
  records: null,
  dropped: 0,
  interrupted: false,
  counts: { errors: 0, warnings: 0 },
  countedThrough: 0,
};

export function useHostLogs(host: Host) {
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  const retrying = useRef(false);
  const owner = useRef(host);
  owner.current = host;
  // The log ring, what it has lost and what it has counted, held together:
  // a batch changes all three.
  const [log, setLog] = useState<{
    owner: Host;
    records: LogRecord[] | null;
    dropped: number;
    interrupted: boolean;
    counts: LogCounts;
    countedThrough: number;
  }>({ owner: host, ...NO_LOG });
  const { records, dropped, interrupted, counts } = log;
  const [sourceStates, setSourceStates] = useState<
    LogSourceStates | "unavailable" | null
  >(null);
  if (log.owner !== host) {
    setLog({ owner: host, ...NO_LOG });
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
          const mine = held.owner === host;
          const previous = mine ? (held.records ?? []) : [];
          // A replayed record was counted when it first arrived.
          let countedThrough = mine ? held.countedThrough : 0;
          let { errors, warnings } = mine ? held.counts : NO_LOG.counts;
          for (const record of batch.records) {
            if (record.seq <= countedThrough) continue;
            countedThrough = record.seq;
            if (record.level === "ERROR" || record.level === "CRITICAL")
              errors += 1;
            else if (record.level === "WARNING") warnings += 1;
          }
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
            counts: { errors, warnings },
            countedThrough,
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
  return { records, dropped, sourceStates, interrupted, counts, retry };
}
