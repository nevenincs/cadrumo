import {
  Fragment,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Input } from "@/components/ui/input";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { effortWords } from "../../shell/agentOffer";
import { useAgentOffer } from "../../shell/agentOfferContext";
import { described, noted } from "../../shell/compose";
import { countWords, useStrings, type Translate } from "../../shell/strings";
import { EngineDoor } from "../setup/EngineDoor";
import {
  columnWords,
  matrixMove,
  matrixView,
  MATRIX_AVAILABILITIES,
  MATRIX_STATES,
  rowCells,
  STARTING_FILTERS,
  type MatrixAvailability,
  type MatrixCell,
  type MatrixColumn,
  type MatrixFilters,
  type MatrixState,
  type MatrixKey,
  type MatrixLane,
  type MatrixMode,
  type MatrixRow,
  type MatrixStep,
} from "./modelMatrixView";
import { ProviderMark } from "./ProviderMark";
import { ReadState } from "./ReadState";

/** What a matrix shows as chosen: a model on a lane, by lane id, with an
 * effort, or none (the provider's own default). */
export type MatrixValue = {
  lane: string;
  model: string;
  effort: string | null;
};

/** One choice made in the matrix. */
export type MatrixChoice = {
  lane: MatrixLane;
  /** The model as the mode names it: the run id of a task, the column's
   * entry or the model id the person wrote. */
  model: string;
  /** Null for the provider's own default. */
  effort: string | null;
};

const MOVES: readonly string[] = [
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Home",
  "End",
  "PageUp",
  "PageDown",
] satisfies readonly MatrixKey[];
const isMove = (key: string): key is MatrixKey => MOVES.includes(key);

const STEP_WORDS = {
  sign_in: "desktop.providers.sign_in_action",
  retry: "desktop.agent.retry",
  download: "desktop.agent.download_models",
  set_up: "desktop.agent.set_up_providers",
} as const satisfies Record<MatrixStep, string>;

const FILTER_WORDS = {
  all: "desktop.agent.model_matrix_filter_all",
  on: "desktop.agent.model_matrix_filter_on",
  off: "desktop.agent.model_matrix_filter_off",
  ready: "desktop.agent.model_matrix_filter_ready",
  setup: "desktop.agent.model_matrix_filter_setup",
} as const satisfies Record<MatrixState | MatrixAvailability, string>;

/** The words of a row's default cell: the provider's own default, and the
 * catalog's where it names one. A conversation takes the catalog's default;
 * a background task names no effort, so the provider's own applies. */
function defaultWords(t: Translate, mode: MatrixMode, row: MatrixRow): string {
  const named = row.efforts.find((effort) => effort === row.defaultEffort);
  if (mode === "conversation")
    return named
      ? noted(t, t("desktop.agent.effort_default"), effortWords(t, named))
      : t("desktop.agent.effort_provider_default");
  return named
    ? noted(
        t,
        t("desktop.agent.effort_provider_default"),
        t("desktop.agent.effort_catalog_default", {
          effort: effortWords(t, named),
        }),
      )
    : t("desktop.agent.effort_provider_default");
}

const cellKey = (cell: MatrixCell) => `${cell.row}\t${cell.column}`;

/**
 * The models the agent offers, chosen with an effort in one press: each lane
 * a heading, each model a row, and as columns the provider's own default and
 * the efforts some shown model takes. One search runs over providers,
 * connections, models and efforts, every word typed having to match, and
 * filters keep lanes on or off, ready or needing setup. A lane turned off
 * is never left out unsaid: the lanes the filters keep out are counted with
 * a way to show them. A lane that cannot be chosen yet says why with the one
 * step that brings it into use, and its models are listed, dimmed, so the
 * person sees what that step gets them.
 *
 * It reads the agent's offer from the column; it holds the search, the
 * filters and where the keyboard stands, and hands every choice to
 * `onChoose`.
 */
export function ModelMatrix({
  mode,
  value,
  onChoose,
  label,
  fixedWayId,
  steps = {},
  onOpenProviders,
  disabled = false,
}: {
  mode: MatrixMode;
  value: MatrixValue | null;
  onChoose: (choice: MatrixChoice) => void;
  /** Names the grid. */
  label: string;
  /** The lane the conversation is fixed to, by way id: choosing another
   * continues in a new conversation, which its heading says. */
  fixedWayId?: string;
  /** What each step does where this window offers it; a step without one
   * is not offered. */
  steps?: Partial<Record<MatrixStep, (lane: MatrixLane) => void>>;
  /** Opens the AI providers, where a provider is turned on, for a matrix
   * with none on. */
  onOpenProviders?: () => void;
  /** No choice can be made while set. */
  disabled?: boolean;
}) {
  const t = useStrings();
  const offer = useAgentOffer();
  const gridId = useId();
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<MatrixFilters>(STARTING_FILTERS);
  const [active, setActive] = useState<MatrixCell | null>(null);
  // What the person wrote for a lane whose models are written, by lane id.
  const [written, setWritten] = useState<Record<string, string>>({});
  const cells = useRef(new Map<string, HTMLButtonElement>());
  const view = useMemo(
    () =>
      offer ? matrixView(t, offer, mode, query, filters, fixedWayId) : null,
    [offer, t, mode, query, filters, fixedWayId],
  );
  if (!offer || !view)
    return <ReadState read={{ kind: "loading" }} icon="settings" />;

  const chosen = (lane: MatrixLane, row: MatrixRow, column: MatrixColumn) =>
    value !== null &&
    value.lane === lane.id &&
    (row.written || value.model === row.id) &&
    (column === "default" ? value.effort === null : value.effort === column);
  const visible = view.lanes.flatMap((lane) =>
    lane.rows.flatMap((row) =>
      rowCells(row, view.columns).map((column) => ({ lane, row, column })),
    ),
  );
  const tabbable: MatrixCell | null = (() => {
    const at = (cell: MatrixCell | null) =>
      cell &&
      visible.some(
        (held) => held.row.key === cell.row && held.column === cell.column,
      )
        ? cell
        : null;
    const current = visible.find(({ lane, row, column }) =>
      chosen(lane, row, column),
    );
    const first = visible[0];
    return (
      at(active) ??
      (current ? { row: current.row.key, column: current.column } : null) ??
      (first ? { row: first.row.key, column: first.column } : null)
    );
  })();
  const filter = <Axis extends keyof MatrixFilters>(
    axis: Axis,
    choice: MatrixFilters[Axis],
  ) => setFilters((held) => ({ ...held, [axis]: choice }));
  const stepOf = (lane: MatrixLane) => {
    if (lane.door) return <EngineDoor door={lane.door} />;
    const act = lane.step ? steps[lane.step] : undefined;
    return (
      lane.step &&
      act && (
        <Button
          variant="outline"
          size="xs"
          data-held-step={lane.step}
          onClick={() => act(lane)}
        >
          {t(STEP_WORDS[lane.step])}
        </Button>
      )
    );
  };
  const choose = (lane: MatrixLane, row: MatrixRow, column: MatrixColumn) => {
    if (!row.choosable || disabled) return;
    onChoose({
      lane,
      model: row.written
        ? (written[lane.id] ?? (value?.lane === lane.id ? value.model : ""))
        : row.id,
      effort: column === "default" ? null : column,
    });
  };
  const onKeyDown = (event: KeyboardEvent) => {
    if (!isMove(event.key) || !tabbable) return;
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey)
      return;
    if (!(event.target instanceof HTMLButtonElement)) return;
    if (event.target.dataset.matrixCell === undefined) return;
    event.preventDefault();
    const next = matrixMove(view, tabbable, event.key);
    setActive(next);
    cells.current.get(cellKey(next))?.focus();
  };
  // Each filter is one labelled choice with "all" among its options, so what
  // is shown is always what both say.
  const axis = <Axis extends keyof MatrixFilters>(
    name: Axis,
    heading: string,
    options: readonly MatrixFilters[Axis][],
  ) => (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span id={`${gridId}-${name}`} className="text-sm text-muted-foreground">
        {t(heading)}
      </span>
      <SegmentedControl
        aria-labelledby={`${gridId}-${name}`}
        data-filter-axis={name}
        value={filters[name]}
        onValueChange={(choice) => {
          const held = options.find((option) => option === choice);
          if (held) filter(name, held);
        }}
      >
        {options.map((option) => (
          <SegmentedControlItem
            key={option}
            value={option}
            data-filter={option}
            className="text-sm"
          >
            {t(FILTER_WORDS[option])}
          </SegmentedControlItem>
        ))}
      </SegmentedControl>
    </div>
  );
  const span = view.columns.length + 1;
  return (
    // Wide, the matrix is a grid: the model column holds its room and stays
    // put while the efforts scroll beside it. Narrower than a grid of every
    // effort reads, each model is a line of its own with its efforts as
    // labelled choices under it, the same cells in the same order.
    <div
      data-slot="model-matrix"
      data-mode={mode}
      className="@container/matrix flex min-h-0 min-w-0 flex-1 flex-col gap-2"
    >
      <Input
        type="search"
        value={query}
        aria-label={t("desktop.agent.model_matrix_search_label")}
        placeholder={t("desktop.agent.model_matrix_search_label")}
        aria-controls={gridId}
        onChange={(event) => setQuery(event.currentTarget.value)}
      />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
        {axis("state", "desktop.agent.model_matrix_state", MATRIX_STATES)}
        {axis(
          "availability",
          "desktop.agent.model_matrix_availability",
          MATRIX_AVAILABILITIES,
        )}
      </div>
      <p
        role="status"
        data-slot="model-matrix-count"
        className="text-sm text-muted-foreground"
      >
        {countWords(
          t,
          view.models,
          {
            one: "desktop.agent.model_matrix_count_one",
            other: "desktop.agent.model_matrix_count",
          },
          { count: view.models },
        )}
      </p>
      {view.noneOn && filters.state === "on" ? (
        <div
          data-slot="model-matrix-none-on"
          className="grid justify-items-start gap-1.5 text-sm text-muted-foreground"
        >
          <p>{t("desktop.agent.model_matrix_none_on")}</p>
          {onOpenProviders && (
            <Button
              variant="outline"
              size="xs"
              data-held-step="set_up"
              onClick={onOpenProviders}
            >
              {t("desktop.agent.set_up_providers")}
            </Button>
          )}
        </div>
      ) : view.lanes.length === 0 ? (
        <div
          data-slot="model-matrix-empty"
          className="grid justify-items-start gap-1.5 text-sm text-muted-foreground"
        >
          <p>{t("desktop.agent.model_matrix_search_empty")}</p>
          {query && (
            <Button variant="outline" size="xs" onClick={() => setQuery("")}>
              {t("desktop.agent.model_matrix_clear_search")}
            </Button>
          )}
        </div>
      ) : (
        <div
          data-slot="model-matrix-scroller"
          className="max-h-96 min-h-0 shrink overflow-auto max-sm:max-h-none max-sm:flex-1 overscroll-contain rounded-md border bg-card"
        >
          <table
            id={gridId}
            role="grid"
            aria-label={label}
            className="w-full min-w-max border-separate border-spacing-0 text-sm @max-lg/matrix:block @max-lg/matrix:min-w-0"
            onKeyDown={onKeyDown}
          >
            <thead className="sticky top-0 z-(--layer-pinned) bg-card @max-lg/matrix:sr-only">
              <tr role="row">
                <th
                  role="columnheader"
                  scope="col"
                  className="sticky left-0 z-(--layer-pinned) bg-card px-2 py-1 text-left font-medium"
                >
                  {t("desktop.agent.model")}
                </th>
                {view.columns.map((column) => (
                  <th
                    key={column}
                    role="columnheader"
                    scope="col"
                    data-column={column}
                    className="w-0 px-2 py-1 text-center font-medium whitespace-nowrap"
                  >
                    {columnWords(t, column)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="@max-lg/matrix:block">
              {view.lanes.map((lane) => (
                <Fragment key={lane.id}>
                  <tr
                    role="row"
                    data-slot="model-matrix-lane"
                    data-lane={lane.id}
                    data-way={lane.wayId ?? undefined}
                    data-standing={lane.standing}
                    className="bg-muted/40 @max-lg/matrix:block"
                  >
                    <th
                      role="rowheader"
                      scope="colgroup"
                      colSpan={span}
                      aria-colspan={span}
                      className="border-t px-2 py-1.5 text-left font-normal @max-lg/matrix:block"
                    >
                      {/* The heading stays in view while the efforts
                          scroll sideways under it. */}
                      <span className="sticky left-2 flex max-w-dialog flex-wrap items-center gap-x-2 gap-y-1 @max-lg/matrix:static @max-lg/matrix:max-w-none">
                        <ProviderMark provider={lane.provider} />
                        <span className="font-medium">
                          {described(t, lane.name, lane.connection)}
                        </span>
                        {lane.words && (
                          <span
                            data-slot="model-matrix-lane-words"
                            className="text-muted-foreground"
                          >
                            {lane.words}
                          </span>
                        )}
                        {stepOf(lane)}
                        {lane.standing !== "ready" && lane.models > 0 && (
                          <span
                            data-slot="model-matrix-lane-models"
                            className="text-muted-foreground"
                          >
                            {countWords(
                              t,
                              lane.models,
                              {
                                one: "desktop.agent.model_matrix_lane_models_one",
                                other: "desktop.agent.model_matrix_lane_models",
                              },
                              { count: lane.models },
                            )}
                          </span>
                        )}
                      </span>
                    </th>
                  </tr>
                  {lane.rows.map((row) => (
                    <tr
                      key={row.key}
                      role="row"
                      data-slot="model-matrix-row"
                      data-lane={lane.id}
                      data-way={lane.wayId ?? undefined}
                      data-model={row.id}
                      data-held={row.held ? undefined : "false"}
                      data-recommended={row.recommended || undefined}
                      aria-disabled={!row.choosable || undefined}
                      className={cn(
                        "group/row @max-lg/matrix:flex @max-lg/matrix:flex-wrap @max-lg/matrix:items-center @max-lg/matrix:gap-1 @max-lg/matrix:border-t @max-lg/matrix:border-border/60 @max-lg/matrix:px-2 @max-lg/matrix:py-1.5",
                        !row.choosable && "text-muted-foreground",
                      )}
                    >
                      <th
                        role="rowheader"
                        scope="row"
                        className="sticky left-0 z-(--layer-pinned) min-w-field max-w-dialog border-t border-border/60 bg-card px-2 py-1.5 text-left align-top font-normal @max-lg/matrix:static @max-lg/matrix:min-w-0 @max-lg/matrix:max-w-none @max-lg/matrix:basis-full @max-lg/matrix:border-0 @max-lg/matrix:bg-transparent @max-lg/matrix:p-0"
                      >
                        {row.written ? (
                          <Input
                            controlSize="sm"
                            value={
                              written[lane.id] ??
                              (value?.lane === lane.id ? value.model : "")
                            }
                            aria-label={described(
                              t,
                              t("desktop.agent.model"),
                              lane.name,
                            )}
                            title={t("desktop.agent.model_written")}
                            disabled={!row.choosable || disabled}
                            onChange={(event) => {
                              const model = event.currentTarget.value;
                              setWritten((held) => ({
                                ...held,
                                [lane.id]: model,
                              }));
                              // The lane chosen takes the model as written.
                              if (value?.lane === lane.id)
                                onChoose({ lane, model, effort: value.effort });
                            }}
                          />
                        ) : (
                          <span className="grid min-w-0 gap-0.5">
                            <span className="font-medium wrap-anywhere">
                              {row.held
                                ? row.name
                                : t("desktop.agent.model_not_installed", {
                                    name: row.name,
                                  })}
                            </span>
                            {row.description && (
                              <span
                                className="line-clamp-2 text-xs text-muted-foreground"
                                title={row.description}
                              >
                                {row.description}
                              </span>
                            )}
                          </span>
                        )}
                      </th>
                      {view.columns.map((column) => {
                        if (!rowCells(row, view.columns).includes(column))
                          return (
                            <td
                              key={column}
                              role="gridcell"
                              className="w-0 border-t border-border/60 p-0 @max-lg/matrix:hidden"
                            />
                          );
                        const checked = chosen(lane, row, column);
                        const cell = { row: row.key, column };
                        const words =
                          column === "default"
                            ? defaultWords(t, mode, row)
                            : effortWords(t, column);
                        const off = !row.choosable || disabled;
                        return (
                          <td
                            key={column}
                            role="gridcell"
                            className="w-0 border-t border-border/60 px-1 py-0 text-center align-middle @max-lg/matrix:block @max-lg/matrix:w-auto @max-lg/matrix:border-0 @max-lg/matrix:p-0"
                          >
                            <button
                              type="button"
                              role="radio"
                              ref={(element) => {
                                if (element)
                                  cells.current.set(cellKey(cell), element);
                                else cells.current.delete(cellKey(cell));
                              }}
                              data-matrix-cell=""
                              data-column={column}
                              aria-checked={checked}
                              aria-disabled={off || undefined}
                              aria-label={t("desktop.agent.model_matrix_cell", {
                                model: row.written ? lane.name : row.name,
                                effort: words,
                              })}
                              title={words}
                              tabIndex={
                                tabbable &&
                                tabbable.row === cell.row &&
                                tabbable.column === cell.column
                                  ? 0
                                  : -1
                              }
                              onFocus={() => setActive(cell)}
                              onClick={() => choose(lane, row, column)}
                              className={cn(
                                "group/cell inline-flex size-control-sm cursor-pointer items-center justify-center gap-1.5 rounded-sm outline-none",
                                "hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring",
                                "aria-disabled:cursor-default aria-disabled:opacity-40 aria-disabled:hover:bg-transparent",
                                "@max-lg/matrix:w-auto @max-lg/matrix:rounded-full @max-lg/matrix:border @max-lg/matrix:px-2.5 @max-lg/matrix:aria-checked:border-primary",
                              )}
                            >
                              <span
                                aria-hidden
                                className={cn(
                                  "grid size-3.5 place-items-center rounded-full border border-input",
                                  checked && "border-primary",
                                )}
                              >
                                {checked && (
                                  <span className="size-2 rounded-full bg-primary" />
                                )}
                              </span>
                              {/* Without the column headings over it, a
                                  choice says its effort itself. */}
                              <span
                                aria-hidden
                                className="hidden text-xs whitespace-nowrap @max-lg/matrix:inline"
                              >
                                {columnWords(t, column)}
                              </span>
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {view.offHidden > 0 && (
        <p
          data-slot="model-matrix-off-hidden"
          className="flex flex-wrap items-center gap-x-1 text-sm text-muted-foreground"
        >
          <span>
            {countWords(
              t,
              view.offHidden,
              {
                one: "desktop.agent.model_matrix_off_hidden_one",
                other: "desktop.agent.model_matrix_off_hidden",
              },
              { count: view.offHidden },
            )}
          </span>
          <span aria-hidden>·</span>
          <Button
            variant="link"
            size="xs"
            onClick={() => filter("state", "all")}
          >
            {t("desktop.agent.model_matrix_show")}
          </Button>
        </p>
      )}
    </div>
  );
}
