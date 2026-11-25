import { useMemo, type SetStateAction } from "react";
import type { Action } from "./actions";
import type { Host } from "./host";
import type { PanelTab } from "./layout";
import { levelRank, type RecordFilters } from "./records";
import type { Translate } from "./strings";

/** The log's: its errors, its filters reset, and the log file revealed. */
export function useLogActions({
  t,
  selectLogLevel,
  openTab,
  setFilters,
  defaultFilters,
  host,
  revealLogs,
}: {
  t: Translate;
  selectLogLevel: (minLevel: number) => void;
  openTab: (tab: PanelTab, options?: { toggle?: boolean }) => void;
  setFilters: (update: SetStateAction<RecordFilters>) => void;
  defaultFilters: RecordFilters;
  host: Host;
  revealLogs: () => void;
}): Action[] {
  return useMemo<Action[]>(
    () => [
      {
        id: "logs.errors",
        label: t("desktop.action.logs_errors"),
        group: "logs",
        icon: "logs",
        run: () => {
          selectLogLevel(levelRank("ERROR"));
          openTab("logs", { toggle: false });
        },
      },
      {
        id: "logs.reset",
        label: t("desktop.action.logs_reset"),
        group: "logs",
        icon: "logs",
        run: () => setFilters(defaultFilters),
      },
      {
        id: "logs.reveal",
        label: t("desktop.logs.reveal"),
        group: "logs",
        icon: "logs",
        enabled: () => !!host.revealLogs,
        run: revealLogs,
      },
    ],
    [t, selectLogLevel, openTab, setFilters, defaultFilters, host, revealLogs],
  );
}
