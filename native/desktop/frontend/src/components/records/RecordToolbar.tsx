import { useMemo, type RefObject } from "react";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import type { LogRecord } from "@/ipc/contract";
import {
  levelRank,
  recordOrigin,
  recordsText,
  type RecordFilters,
} from "@/shell/records";
import { useStrings } from "@/shell/strings";

export function RecordToolbar({
  all,
  visible,
  filters,
  defaultFilters,
  setFilters,
  filterInput,
  follow,
  onFollow,
  onSelectAll,
  onCopy,
  onExport,
  onReveal,
}: {
  all: LogRecord[];
  visible: LogRecord[];
  filters: RecordFilters;
  defaultFilters: RecordFilters;
  setFilters: (filters: RecordFilters) => void;
  filterInput: RefObject<HTMLInputElement | null>;
  follow: boolean;
  onFollow: () => void;
  onSelectAll: () => void;
  onCopy?: (text: string) => void;
  onExport?: (text: string) => void;
  onReveal?: () => void;
}) {
  const t = useStrings();
  const { sources, origins, loggers } = useMemo(() => {
    const sources = [...new Set(all.map((record) => record.source))].sort();
    const origins = [
      ...new Set(all.filter((record) => record.process).map(recordOrigin)),
    ].sort();
    const loggers = [
      ...new Set(
        all.flatMap((record) => (record.logger ? [record.logger] : [])),
      ),
    ].sort();
    return { sources, origins, loggers };
  }, [all]);
  const active =
    !!filters.origin ||
    !!filters.logger ||
    filters.hiddenSources.length > 0 ||
    filters.minLevel !== defaultFilters.minLevel;
  return (
    <div className="log-toolbar flex shrink-0 flex-wrap items-center gap-1 border-b bg-chrome py-1 pr-1.5 pl-3">
      <div
        data-log-group="filters"
        className="flex min-w-40 flex-1 basis-field items-center gap-1 panel-short:basis-0"
      >
        <Input
          ref={filterInput}
          className="filter-text min-w-0 flex-1"
          controlSize="sm"
          type="search"
          placeholder={t("desktop.logs.filter")}
          aria-label={t("desktop.logs.filter")}
          value={filters.text}
          onChange={(event) =>
            setFilters({ ...filters, text: event.target.value })
          }
        />
        <Popover>
          <PopoverTrigger asChild>
            <IconButton label={t("desktop.logs.filters")} aria-pressed={active}>
              <Icon name="filter" />
            </IconButton>
          </PopoverTrigger>
          <PopoverContent
            align="end"
            className="grid w-dialog gap-3"
            aria-label={t("desktop.logs.filters")}
          >
            <label className="grid gap-1.5 text-sm">
              {t("desktop.logs.origin")}
              <NativeSelect
                aria-label={t("desktop.logs.origin")}
                value={filters.origin ?? ""}
                onChange={(event) =>
                  setFilters({
                    ...filters,
                    origin: event.target.value,
                    hiddenSources: [],
                  })
                }
              >
                <option value="">{t("desktop.logs.all_origins")}</option>
                {filters.origin &&
                  !sources.includes(filters.origin) &&
                  !origins.includes(filters.origin) && (
                    <option value={filters.origin}>{filters.origin}</option>
                  )}
                {sources.map((source) => (
                  <optgroup key={source} label={source}>
                    <option value={source}>{source}</option>
                    {origins
                      .filter((origin) => origin.startsWith(`${source} / `))
                      .map((origin) => (
                        <option key={origin} value={origin}>
                          {origin}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </NativeSelect>
            </label>
            <label className="grid gap-1.5 text-sm">
              {t("desktop.logs.minimum_level")}
              <NativeSelect
                aria-label={t("desktop.logs.minimum_level")}
                value={filters.minLevel}
                onChange={(event) =>
                  setFilters({
                    ...filters,
                    minLevel: Number(event.target.value),
                  })
                }
              >
                <option value={levelRank("DEBUG")}>
                  {t("desktop.logs.level_all")}
                </option>
                <option value={levelRank("INFO")}>
                  {t("desktop.logs.level_info")}
                </option>
                <option value={levelRank("WARNING")}>
                  {t("desktop.logs.level_warning")}
                </option>
                <option value={levelRank("ERROR")}>
                  {t("desktop.logs.level_error")}
                </option>
                <option value={levelRank("CRITICAL")}>
                  {t("desktop.logs.level_critical")}
                </option>
              </NativeSelect>
            </label>
            <label className="grid gap-1.5 text-sm">
              {t("desktop.logs.logger")}
              <NativeSelect
                aria-label={t("desktop.logs.logger")}
                value={filters.logger ?? ""}
                onChange={(event) =>
                  setFilters({ ...filters, logger: event.target.value || null })
                }
              >
                <option value="">{t("desktop.logs.all_loggers")}</option>
                {filters.logger && !loggers.includes(filters.logger) && (
                  <option value={filters.logger}>{filters.logger}</option>
                )}
                {loggers.map((logger) => (
                  <option key={logger} value={logger}>
                    {logger}
                  </option>
                ))}
              </NativeSelect>
            </label>
            <IconButton
              label={t("desktop.action.logs_reset")}
              onClick={() => setFilters(defaultFilters)}
            >
              <Icon name="reset" />
            </IconButton>
          </PopoverContent>
        </Popover>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <span aria-hidden="true" className="mx-1 h-4 w-px bg-border" />
        <div data-log-group="selection" className="flex items-center gap-1">
          <IconButton
            label={t("desktop.menu.select_all")}
            disabled={!visible.length}
            onClick={onSelectAll}
          >
            <Icon name="selectAll" />
          </IconButton>
          {onCopy && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <IconButton
                  label={t("desktop.menu.copy")}
                  disabled={!all.length}
                >
                  <Icon name="copy" />
                </IconButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  disabled={!visible.length}
                  onSelect={() => onCopy(recordsText(visible))}
                >
                  <Icon name="copy" />
                  {t("desktop.menu.copy_visible")}
                </DropdownMenuItem>
                <DropdownMenuItem
                  disabled={!all.length}
                  onSelect={() => onCopy(recordsText(all))}
                >
                  <Icon name="copyAll" />
                  {t("desktop.logs.copy_all")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
        <span aria-hidden="true" className="mx-1 h-4 w-px bg-border" />
        <div data-log-group="files" className="flex items-center gap-1">
          {onExport && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <IconButton
                  label={t("desktop.logs.export")}
                  disabled={!all.length}
                >
                  <Icon name="download" />
                </IconButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  disabled={!visible.length}
                  onSelect={() => onExport(recordsText(visible))}
                >
                  <Icon name="download" />
                  {t("desktop.logs.export_visible")}
                </DropdownMenuItem>
                <DropdownMenuItem
                  disabled={!all.length}
                  onSelect={() => onExport(recordsText(all))}
                >
                  <Icon name="downloadAll" />
                  {t("desktop.logs.export_all")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <IconButton
            label={t("desktop.logs.reveal")}
            disabled={!onReveal}
            onClick={onReveal}
          >
            <Icon name="folder" />
          </IconButton>
        </div>
        <span aria-hidden="true" className="mx-1 h-4 w-px bg-border" />
        <div data-log-group="follow" className="flex items-center">
          <IconButton
            label={t("desktop.logs.follow")}
            data-follow=""
            accessibleName={t("desktop.logs.follow")}
            hint={t("desktop.logs.follow_hint")}
            aria-pressed={follow}
            onClick={onFollow}
          >
            <Icon name={follow ? "pause" : "play"} />
          </IconButton>
        </div>
      </div>
    </div>
  );
}
