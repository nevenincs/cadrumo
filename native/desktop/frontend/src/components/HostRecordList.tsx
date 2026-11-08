import { useEffect, useRef, type ComponentProps } from "react";
import type { Host } from "../shell/host";
import { useHostLogs } from "../shell/useHostLogs";
import { RecordList } from "./RecordList";

const REPORT_MS = 250;

/**
 * The log view on the host's own feed. It holds the feed itself, so a batch
 * renders the log and not the window around it: a busy log sends one every
 * few tens of milliseconds. The window hears only how many errors have
 * arrived, and only when that changes.
 */
export function HostRecordList({
  host,
  onErrors,
  ...view
}: {
  host: Host;
  onErrors: (count: number) => void;
} & Omit<
  ComponentProps<typeof RecordList>,
  "records" | "sourceStates" | "dropped" | "onRetry" | "interrupted" | "counts"
>) {
  const { records, dropped, sourceStates, interrupted, counts, retry } =
    useHostLogs(host);
  const errors = counts.errors;
  // A busy log changes the count on almost every batch, and the count
  // re-renders the whole window. Reporting it from this effect chained one
  // window commit to each batch's, faster than a long drawn span renders, so
  // the window hears the latest count at most every REPORT_MS, from a timer.
  const report = useRef({ errors, onErrors });
  const pending = useRef<number | null>(null);
  useEffect(() => {
    report.current = { errors, onErrors };
    if (pending.current !== null) return;
    pending.current = window.setTimeout(() => {
      pending.current = null;
      report.current.onErrors(report.current.errors);
    }, REPORT_MS);
  }, [errors, onErrors]);
  useEffect(
    () => () => {
      if (pending.current !== null) window.clearTimeout(pending.current);
      pending.current = null;
    },
    [],
  );
  return (
    <RecordList
      records={records}
      sourceStates={sourceStates}
      dropped={dropped}
      onRetry={retry}
      interrupted={interrupted}
      counts={counts}
      {...view}
    />
  );
}
