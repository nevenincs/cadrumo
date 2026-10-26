import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { FilterChip } from "@/components/ui/filter-chip";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import type { LedgerReviewStatus } from "../../../shell/ledger";
import type { OwnAccountChoice } from "../../../shell/ledgerMovementReads";
import {
  CLASSIFICATIONS,
  DIRECTIONS,
  IMPORT_ISSUES,
  LIFECYCLE_STATES,
  type ImportIssue,
} from "../../../shell/ledgerVocabulary";
import { useStrings, type Translate } from "../../../shell/strings";
import { ColumnChooser } from "./ColumnChooser";
import {
  GROUPING_IDS,
  NO_FILTERS,
  SAVED_VIEW_IDS,
  SORT_KEYS,
  activeFilters,
  type ColumnId,
  type GroupingId,
  type MovementFilters,
  type MovementSort,
  type SavedViewId,
  type SortKey,
} from "./movementsModel";
import {
  classificationLabel,
  directionLabel,
  lifecycleLabel,
  reasonShort,
} from "./movementWords";

const REVIEW_STATUSES: readonly LedgerReviewStatus[] = [
  "pending",
  "reviewed",
  "skipped",
  "excluded",
];

/** The longest search the product's text filter takes. */
const SEARCH_LIMIT = 128;

const sortKeyLabel = (t: Translate, key: SortKey) =>
  t(`desktop.ledger.sort.key.${key}`);

const importIssueLabel = (t: Translate, issue: ImportIssue) =>
  t(`desktop.ledger.import_issue.${issue.replace("-", "_")}`);

const toggled = <T,>(list: readonly T[], value: T): T[] =>
  list.includes(value)
    ? list.filter((entry) => entry !== value)
    : [...list, value];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="grid gap-1.5">
      <legend className="mb-1.5 text-xs font-medium text-muted-foreground">
        {title}
      </legend>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </fieldset>
  );
}

/** The chips of the filters in force, each with its own way off. */
function filterChips(
  t: Translate,
  filters: MovementFilters,
  accounts: readonly OwnAccountChoice[] | null,
  set: (filters: MovementFilters) => void,
): { key: string; label: string; remove: () => void }[] {
  const chips: { key: string; label: string; remove: () => void }[] = [];
  const off = (patch: Partial<MovementFilters>) => () =>
    set({ ...filters, ...patch });
  for (const status of filters.status)
    chips.push({
      key: `status-${status}`,
      label: t(`desktop.ledger.review.${status}`),
      remove: off({ status: toggled(filters.status, status) }),
    });
  for (const direction of filters.direction)
    chips.push({
      key: `direction-${direction}`,
      label: directionLabel(t, direction),
      remove: off({ direction: toggled(filters.direction, direction) }),
    });
  for (const classification of filters.classification)
    chips.push({
      key: `classification-${classification}`,
      label: classificationLabel(t, classification),
      remove: off({
        classification: toggled(filters.classification, classification),
      }),
    });
  for (const state of filters.lifecycle)
    chips.push({
      key: `lifecycle-${state}`,
      label: lifecycleLabel(t, state),
      remove: off({ lifecycle: toggled(filters.lifecycle, state) }),
    });
  if (filters.account)
    chips.push({
      key: "account",
      label:
        accounts?.find((account) => account.id === filters.account)?.label ??
        filters.account,
      remove: off({ account: null }),
    });
  if (filters.importBatches.length)
    chips.push({
      key: "import",
      label: t("desktop.ledger.filters.import_chip"),
      remove: off({ importBatches: [] }),
    });
  if (filters.importIssue)
    chips.push({
      key: "issue",
      label: importIssueLabel(t, filters.importIssue),
      remove: off({ importIssue: null }),
    });
  if (filters.group)
    chips.push({
      key: "group",
      label: filters.group.label ?? t("desktop.ledger.filters.no_group"),
      remove: off({ group: null }),
    });
  if (filters.reason)
    chips.push({
      key: "reason",
      label: reasonShort(t, filters.reason),
      remove: off({ reason: null }),
    });
  if (filters.readiness)
    chips.push({
      key: "readiness",
      label: t(`desktop.ledger.readiness_filter.${filters.readiness}`),
      remove: off({ readiness: null }),
    });
  if (filters.hideRejected)
    chips.push({
      key: "rejected",
      label: t("desktop.ledger.filters.hide_rejected_chip"),
      remove: off({ hideRejected: false }),
    });
  if (filters.foreignOnly)
    chips.push({
      key: "foreign",
      label: t("desktop.ledger.filters.foreign_chip"),
      remove: off({ foreignOnly: false }),
    });
  if (filters.toMatch)
    chips.push({
      key: "to_match",
      label: t("desktop.ledger.filters.to_match_chip"),
      remove: off({ toMatch: false }),
    });
  return chips;
}

/**
 * The movements' toolbar: the search, the filters and the chips in force,
 * the saved views, grouping, sorting, the columns and the density. Icon
 * buttons carry their name and state in a tooltip; nothing here takes a
 * key the grid or the shell needs.
 */
export function MovementsToolbar({
  search,
  onSearch,
  onLeaveSearch,
  filters,
  onFilters,
  savedView,
  onChooseView,
  groupBy,
  onGroupBy,
  groupAllowed,
  onFoldAll,
  sort,
  onSort,
  sortAllowed,
  layout,
  onLayout,
  density,
  onDensity,
  accounts,
  onWantAccounts,
  groupLabels,
  reasons,
  status,
  selectionActions,
}: {
  search: string;
  onSearch: (search: string) => void;
  /** ArrowDown or Enter in the search: on to the grid. */
  onLeaveSearch: () => void;
  filters: MovementFilters;
  onFilters: (filters: MovementFilters) => void;
  savedView: SavedViewId | null;
  onChooseView: (view: SavedViewId) => void;
  groupBy: GroupingId | null;
  onGroupBy: (groupBy: GroupingId | null) => void;
  /** Whether a grouping can be offered, and why not. */
  groupAllowed: (groupBy: GroupingId) => boolean;
  onFoldAll: (folded: boolean) => void;
  sort: MovementSort;
  onSort: (sort: MovementSort) => void;
  sortAllowed: (key: SortKey) => boolean;
  layout: { order: readonly ColumnId[]; hidden: ReadonlySet<ColumnId> };
  onLayout: (order: ColumnId[], hidden: ColumnId[]) => void;
  density: "compact" | "comfortable";
  onDensity: (density: "compact" | "comfortable") => void;
  accounts: readonly OwnAccountChoice[] | null;
  onWantAccounts: () => void;
  /** The group labels the window's movements carry. */
  groupLabels: readonly string[];
  /** The readiness reasons the last check found. */
  reasons: readonly string[];
  /** How many movements are shown and selected, as one line. */
  status: string;
  /** What acts on a selection of several, beside the line that counts
   * it. */
  selectionActions?: ReactNode;
}) {
  const t = useStrings();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [groupOpen, setGroupOpen] = useState(false);
  const count = activeFilters(filters);
  const chips = filterChips(t, filters, accounts, onFilters);
  const pills = <T extends string>(
    key: "status" | "direction" | "classification" | "lifecycle",
    values: readonly T[],
    label: (value: T) => string,
  ) =>
    values.map((value) => (
      <Button
        key={value}
        variant="pill"
        size="xs"
        aria-pressed={(filters[key] as readonly string[]).includes(value)}
        onClick={() =>
          onFilters({
            ...filters,
            [key]: toggled(filters[key] as readonly string[], value),
          })
        }
      >
        {label(value)}
      </Button>
    ));
  // With nothing filtered, every movement is shown: that is the "All" view.
  const shownView = savedView ?? (count === 0 ? "all" : null);
  const viewName = shownView
    ? t(`desktop.ledger.view.${shownView}`)
    : t("desktop.ledger.view.custom");
  return (
    <div className="grid gap-2">
      <div
        role="toolbar"
        aria-label={t("desktop.ledger.toolbar")}
        className="ledger-toolbar flex flex-wrap items-center gap-1"
      >
        <div role="search" className="relative w-field">
          <Icon
            name="search"
            size="sm"
            className="pointer-events-none absolute top-1/2 left-2 -translate-y-1/2 text-faint"
          />
          <Input
            type="search"
            controlSize="sm"
            className="ledger-search pl-7"
            maxLength={SEARCH_LIMIT}
            value={search}
            aria-label={t("desktop.ledger.search.label")}
            placeholder={t("desktop.ledger.search.placeholder")}
            onChange={(event) => onSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape" && search) {
                event.preventDefault();
                event.stopPropagation();
                onSearch("");
              } else if (event.key === "ArrowDown" || event.key === "Enter") {
                event.preventDefault();
                onLeaveSearch();
              }
            }}
          />
        </div>
        <Popover
          open={filtersOpen}
          onOpenChange={(open) => {
            setFiltersOpen(open);
            if (open) onWantAccounts();
          }}
        >
          <PopoverTrigger asChild>
            <IconButton
              label={t("desktop.ledger.filters.title")}
              hint={
                count
                  ? t("desktop.ledger.filters.active", { count })
                  : undefined
              }
              size="sm"
              variant={count ? "outline" : "ghost"}
            >
              <Icon name="filter" />
            </IconButton>
          </PopoverTrigger>
          <PopoverContent
            align="start"
            aria-label={t("desktop.ledger.filters.title")}
            className="ledger-filters grid w-dialog gap-3"
          >
            <div className="flex items-center">
              <span className="flex-1 font-medium">
                {t("desktop.ledger.filters.title")}
              </span>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => onFilters(NO_FILTERS)}
              >
                <Icon name="reset" size="xs" />
                {t("desktop.ledger.filters.reset")}
              </Button>
            </div>
            <Section title={t("desktop.ledger.filters.status")}>
              {pills("status", REVIEW_STATUSES, (status) =>
                t(`desktop.ledger.review.${status}`),
              )}
            </Section>
            <Section title={t("desktop.ledger.filters.direction")}>
              {pills("direction", DIRECTIONS, (direction) =>
                directionLabel(t, direction),
              )}
            </Section>
            <Section title={t("desktop.ledger.filters.classification")}>
              {pills("classification", CLASSIFICATIONS, (classification) =>
                classificationLabel(t, classification),
              )}
            </Section>
            <Section title={t("desktop.ledger.filters.lifecycle")}>
              {pills("lifecycle", LIFECYCLE_STATES, (state) =>
                lifecycleLabel(t, state),
              )}
            </Section>
            <div className="grid grid-cols-2 gap-3">
              <label className="grid gap-1 text-sm">
                {t("desktop.ledger.filters.account")}
                <NativeSelect
                  controlSize="sm"
                  value={filters.account ?? ""}
                  onChange={(event) =>
                    onFilters({
                      ...filters,
                      account: event.target.value || null,
                    })
                  }
                >
                  <option value="">{t("desktop.ledger.filters.any")}</option>
                  {(accounts ?? []).map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.label}
                    </option>
                  ))}
                </NativeSelect>
              </label>
              <label className="grid gap-1 text-sm">
                {t("desktop.ledger.filters.import_issue")}
                <NativeSelect
                  controlSize="sm"
                  value={filters.importIssue ?? ""}
                  onChange={(event) =>
                    onFilters({
                      ...filters,
                      importIssue:
                        (event.target.value as ImportIssue | "") || null,
                    })
                  }
                >
                  <option value="">{t("desktop.ledger.filters.any")}</option>
                  {IMPORT_ISSUES.map((issue) => (
                    <option key={issue} value={issue}>
                      {importIssueLabel(t, issue)}
                    </option>
                  ))}
                </NativeSelect>
              </label>
              <label className="grid gap-1 text-sm">
                {t("desktop.ledger.filters.group")}
                <NativeSelect
                  controlSize="sm"
                  value={
                    filters.group === null
                      ? "any"
                      : filters.group.label === null
                        ? "none"
                        : `label:${filters.group.label}`
                  }
                  onChange={(event) => {
                    const value = event.target.value;
                    onFilters({
                      ...filters,
                      group:
                        value === "any"
                          ? null
                          : value === "none"
                            ? { label: null }
                            : { label: value.slice("label:".length) },
                    });
                  }}
                >
                  <option value="any">{t("desktop.ledger.filters.any")}</option>
                  <option value="none">
                    {t("desktop.ledger.filters.no_group")}
                  </option>
                  {groupLabels.map((label) => (
                    <option key={label} value={`label:${label}`}>
                      {label}
                    </option>
                  ))}
                </NativeSelect>
              </label>
              <label className="grid gap-1 text-sm">
                {t("desktop.ledger.filters.reason")}
                <NativeSelect
                  controlSize="sm"
                  value={filters.reason ?? ""}
                  onChange={(event) =>
                    onFilters({
                      ...filters,
                      reason: event.target.value || null,
                    })
                  }
                >
                  <option value="">{t("desktop.ledger.filters.any")}</option>
                  {reasons.map((reason) => (
                    <option key={reason} value={reason}>
                      {reasonShort(t, reason)}
                    </option>
                  ))}
                </NativeSelect>
              </label>
            </div>
            {(
              [
                ["hideRejected", "desktop.ledger.filters.hide_rejected"],
                ["foreignOnly", "desktop.ledger.filters.foreign"],
                ["toMatch", "desktop.ledger.filters.to_match"],
              ] as const
            ).map(([key, name]) => (
              <label key={key} className="flex items-center gap-2 text-sm">
                <Switch
                  checked={filters[key]}
                  onCheckedChange={(checked) =>
                    onFilters({ ...filters, [key]: checked })
                  }
                />
                {t(name)}
              </label>
            ))}
          </PopoverContent>
        </Popover>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="ledger-views"
              aria-label={t("desktop.ledger.view.named", { view: viewName })}
            >
              <Icon name="bookmark" size="sm" />
              {viewName}
              <Icon name="chevronDown" size="xs" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuGroup label={t("desktop.ledger.view.title")}>
              <DropdownMenuRadioGroup value={shownView ?? ""}>
                {SAVED_VIEW_IDS.map((view) => (
                  <DropdownMenuRadioItem
                    key={view}
                    value={view}
                    onSelect={() => onChooseView(view)}
                  >
                    {t(`desktop.ledger.view.${view}`)}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu open={groupOpen} onOpenChange={setGroupOpen}>
          <DropdownMenuTrigger asChild>
            <IconButton
              label={t("desktop.ledger.group.title")}
              hint={
                groupBy
                  ? t(`desktop.ledger.group.${groupBy}`)
                  : t("desktop.ledger.group.none")
              }
              size="sm"
              variant={groupBy ? "outline" : "ghost"}
            >
              <Icon name="group" />
            </IconButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuGroup label={t("desktop.ledger.group.by")}>
              <DropdownMenuRadioGroup value={groupBy ?? "none"}>
                <DropdownMenuRadioItem
                  value="none"
                  onSelect={() => {
                    onGroupBy(null);
                    setGroupOpen(false);
                  }}
                >
                  {t("desktop.ledger.group.none")}
                </DropdownMenuRadioItem>
                {GROUPING_IDS.map((grouping) => {
                  const allowed = groupAllowed(grouping);
                  return (
                    <DropdownMenuRadioItem
                      key={grouping}
                      value={grouping}
                      disabled={!allowed}
                      onSelect={() => {
                        onGroupBy(grouping);
                        setGroupOpen(false);
                      }}
                    >
                      {t(`desktop.ledger.group.${grouping}`)}
                      {!allowed && (
                        <DropdownMenuShortcut>
                          {t("desktop.ledger.group.waits")}
                        </DropdownMenuShortcut>
                      )}
                    </DropdownMenuRadioItem>
                  );
                })}
              </DropdownMenuRadioGroup>
            </DropdownMenuGroup>
            {groupBy && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => onFoldAll(false)}>
                  <Icon name="expandAll" />
                  {t("desktop.ledger.group.expand_all")}
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => onFoldAll(true)}>
                  <Icon name="collapseAll" />
                  {t("desktop.ledger.group.collapse_all")}
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <IconButton
              label={t("desktop.ledger.sort.title")}
              hint={t("desktop.ledger.sort.current", {
                key: sortKeyLabel(t, sort.key),
                direction: t(`desktop.ledger.sort.${sort.direction}`),
              })}
              size="sm"
            >
              <Icon name={sort.direction === "asc" ? "sortAsc" : "sortDesc"} />
            </IconButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuGroup label={t("desktop.ledger.sort.by")}>
              <DropdownMenuRadioGroup value={sort.key}>
                {SORT_KEYS.map((key) => {
                  const allowed = sortAllowed(key);
                  return (
                    <DropdownMenuRadioItem
                      key={key}
                      value={key}
                      disabled={!allowed}
                      onSelect={() => onSort({ ...sort, key })}
                    >
                      {sortKeyLabel(t, key)}
                      {!allowed && (
                        <DropdownMenuShortcut>
                          {t("desktop.ledger.sort.waits")}
                        </DropdownMenuShortcut>
                      )}
                    </DropdownMenuRadioItem>
                  );
                })}
              </DropdownMenuRadioGroup>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuRadioGroup value={sort.direction}>
              {(["asc", "desc"] as const).map((direction) => (
                <DropdownMenuRadioItem
                  key={direction}
                  value={direction}
                  onSelect={() => onSort({ ...sort, direction })}
                >
                  {t(`desktop.ledger.sort.${direction}`)}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
        <ColumnChooser layout={layout} onLayout={onLayout} />
        <IconButton
          label={t("desktop.ledger.density.comfortable")}
          size="sm"
          aria-pressed={density === "comfortable"}
          onClick={() =>
            onDensity(density === "comfortable" ? "compact" : "comfortable")
          }
        >
          <Icon name="density" />
        </IconButton>
        <span
          role="status"
          className="ledger-count ml-auto text-sm text-muted-foreground tabular-nums"
        >
          {status}
        </span>
        {selectionActions}
      </div>
      {chips.length > 0 && (
        <ul
          aria-label={t("desktop.ledger.filters.in_force")}
          className="ledger-chips flex flex-wrap items-center gap-1.5"
        >
          {chips.map((chip) => (
            <li key={chip.key}>
              <FilterChip
                removeLabel={t("desktop.ledger.filters.remove", {
                  filter: chip.label,
                })}
                onRemove={chip.remove}
              >
                {chip.label}
              </FilterChip>
            </li>
          ))}
          <li>
            <Button
              variant="link"
              size="xs"
              onClick={() => onFilters(NO_FILTERS)}
            >
              {t("desktop.ledger.filters.clear_all")}
            </Button>
          </li>
        </ul>
      )}
    </div>
  );
}
