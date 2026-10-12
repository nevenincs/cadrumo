import { useEffect, useMemo, type ComponentProps } from "react";
import type { Host } from "../shell/host";
import { useHostLogs } from "../shell/useHostLogs";
import { RecordList } from "./RecordList";

/**
 * The log view on the host's own feed. It holds the feed itself, so a batch
 * renders the log and not the window around it: a busy log sends one every
 * few tens of milliseconds. The window hears only how many records are
 * errors, and only when that changes.
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
  "records" | "sourceStates" | "dropped"
>) {
  const { records, dropped, sourceStates } = useHostLogs(host);
  const errors = useMemo(
    () =>
      (records ?? []).filter(
        (record) => record.level === "ERROR" || record.level === "CRITICAL",
      ).length,
    [records],
  );
  useEffect(() => onErrors(errors), [errors, onErrors]);
  return (
    <RecordList
      records={records}
      sourceStates={sourceStates}
      dropped={dropped}
      {...view}
    />
  );
}
