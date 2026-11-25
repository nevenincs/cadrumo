import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import type { Host } from "./host";
import type { Layout } from "./layout";
import { DEFAULT_FILTERS, levelRank, type RecordFilters } from "./records";
import { saveLogs } from "./saveLogs";
import type { Translate } from "./strings";
import type { useDesktopEnvironment } from "./useDesktopEnvironment";

/** The log view's filters, its level remembered with the layout, how many
 * of its records are errors, and what the window does with the log's text:
 * copy, reveal and export it. */
export function useLogControls({
  host,
  environment,
  logLevel,
  setLayout,
  say,
  t,
}: {
  host: Host;
  environment: ReturnType<typeof useDesktopEnvironment>;
  logLevel: Layout["logLevel"];
  setLayout: Dispatch<SetStateAction<Layout>>;
  say: (text: string) => void;
  t: Translate;
}) {
  // How many log records are errors, as the log view reports it.
  const [errorCount, setErrorCount] = useState(0);
  const defaultFilters = useMemo(
    () => ({
      ...DEFAULT_FILTERS,
      minLevel: levelRank(
        environment.state === "ready" ? environment.value.logLevel : "INFO",
      ),
    }),
    [environment],
  );
  const [filterOverride, setFilterOverride] = useState<RecordFilters | null>(
    null,
  );
  const filters = useMemo(
    () => ({
      ...(filterOverride ?? defaultFilters),
      minLevel: logLevel ?? defaultFilters.minLevel,
    }),
    [filterOverride, defaultFilters, logLevel],
  );
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const setFilters = useCallback(
    (update: SetStateAction<RecordFilters>) => {
      const next =
        typeof update === "function" ? update(filtersRef.current) : update;
      filtersRef.current = next;
      setFilterOverride(next);
      if (update === defaultFilters)
        setLayout((current) => ({ ...current, logLevel: null }));
    },
    [defaultFilters, setLayout],
  );
  const selectLogLevel = useCallback(
    (minLevel: number) => {
      setFilters((current) => ({ ...current, minLevel }));
      setLayout((current) => ({ ...current, logLevel: minLevel }));
    },
    [setFilters, setLayout],
  );

  const copyLogs = useCallback(
    (text: string) => {
      if (!text) return;
      (host.copyLogs ? host.copyLogs(text) : host.writeClipboard(text)).then(
        () => say(t("desktop.toast.copied")),
        () => say(t("desktop.toast.copy_failed")),
      );
    },
    [host, say, t],
  );

  const revealLogs = useCallback(() => {
    host.revealLogs?.().catch(() => say(t("desktop.toast.open_failed")));
  }, [host, say, t]);

  const exportLogs = useCallback(
    async (text: string) => {
      try {
        if (host.exportLogs) {
          const path = await host.exportLogs(text);
          say(t("desktop.logs.exported", { path }));
        } else {
          await saveLogs(text, t("desktop.logs.file_type"));
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError")
          return;
        say(t("desktop.logs.export_failed"));
      }
    },
    [host, say, t],
  );
  return {
    errorCount,
    setErrorCount,
    defaultFilters,
    filters,
    setFilters,
    selectLogLevel,
    copyLogs,
    revealLogs,
    exportLogs,
  };
}
