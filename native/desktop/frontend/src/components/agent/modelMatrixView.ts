import { edgeRow, nextRow } from "@/components/ui/dataGridModel";
import type { Effort, EngineDoor } from "../../shell/agentCatalogContract";
import {
  EFFORTS,
  effortWords,
  heldModel,
  offerMatches,
  taskModelsOf,
  type AgentOffer,
  type OfferedLane,
} from "../../shell/agentOffer";
import { connectionWords } from "../../shell/providerConnection";
import type { ProviderSettingsRecord } from "../../shell/providerSettingsContract";
import type { Translate } from "../../shell/strings";

// What the model matrix shows of the agent's offer: each lane as a heading
// with its models as rows, and as columns the provider's own default and
// the efforts some shown model takes. It is a view of the one offer the
// column works out, with a search and filters over it; it names no lane,
// model or effort of its own.

/** Whether the matrix chooses what a background task runs with, or what the
 * conversation runs with. */
export type MatrixMode = "task" | "conversation";

/** The filters a matrix can apply: lanes on and lanes off, lanes ready and
 * lanes that need setting up. In each pair, none pressed shows both. */
export type MatrixFilters = {
  on: boolean;
  off: boolean;
  ready: boolean;
  setup: boolean;
};

/** Lanes that are on, whatever their standing: what a matrix starts with. */
export const STARTING_FILTERS: MatrixFilters = {
  on: true,
  off: false,
  ready: false,
  setup: false,
};

/** A column: the provider's own default, or one effort. */
export type MatrixColumn = "default" | Effort;

/** The step that brings a lane that cannot be chosen yet into use. */
export type MatrixStep = "sign_in" | "retry" | "download" | "set_up";

/** One model of a lane, as a row. */
export type MatrixRow = {
  /** Unique in the matrix: the lane and the model. */
  key: string;
  /** What a choice names: the model a task runs, or the column's entry. */
  id: string;
  name: string;
  description: string | null;
  /** False for a model this computer does not hold yet. */
  held: boolean;
  /** The efforts the model takes, lowest first. */
  efforts: Effort[];
  /** The effort the catalog names as the model's default, where it does. */
  defaultEffort: string | null;
  /** The row's model is written by the person, not listed. */
  written: boolean;
  /** A choice of the row can be made. */
  choosable: boolean;
  /** The catalog recommends starting the lane's conversations with it. */
  recommended: boolean;
};

/** One lane, as a heading over its rows. */
export type MatrixLane = {
  id: string;
  /** The way id the column chooses by; null for a lane the catalog does not
   * serve. */
  wayId: string | null;
  provider: string;
  providerName: string;
  /** The lane's name and connection, as a heading says them. */
  name: string;
  connection: string;
  /** Off in the provider settings, ready to run, or needing setting up. */
  standing: "off" | "ready" | "setup";
  /** Why the lane cannot be chosen, where it cannot; else a remark of the
   * picker's, as that choosing it continues in a new conversation. */
  words: string | null;
  /** The one step that brings the lane into use, and the engine's door where
   * the step is starting its engine. */
  step: MatrixStep | null;
  door: EngineDoor | null;
  rows: MatrixRow[];
};

export type MatrixView = {
  columns: MatrixColumn[];
  lanes: MatrixLane[];
  /** Lanes turned off that the filters keep out. */
  offHidden: number;
  /** No lane is on: there is nothing to choose until one is. */
  noneOn: boolean;
  /** The rows shown. */
  rows: number;
};

/** The key a row is known by: its lane and its model, which no lane id
 * contains a line break in. */
export const rowKey = (lane: string, model: string) => `${lane}\n${model}`;

/** The efforts of `levels` the contract names, in the order given. */
const efforts = (levels: readonly string[]): Effort[] =>
  levels.flatMap((level) => EFFORTS.filter((effort) => effort === level));

/** The words of a column, as its heading says it. */
export function columnWords(t: Translate, column: MatrixColumn): string {
  return column === "default"
    ? t("desktop.agent.effort_default")
    : effortWords(t, column);
}

/** The step a lane that cannot run is brought into use by: its engine's
 * door, signing in, asking again, downloading a model, or setting it up. */
function stepOf(lane: OfferedLane): {
  step: MatrixStep | null;
  door: EngineDoor | null;
} {
  if (lane.engineNotRunning)
    return { step: null, door: lane.engineNotRunning.door };
  if (lane.held?.step === "sign_in") return { step: "sign_in", door: null };
  if (lane.held?.step === "retry") return { step: "retry", door: null };
  if (lane.modelsToDownload) return { step: "download", door: null };
  return { step: "set_up", door: null };
}

function laneRows(
  offer: AgentOffer,
  lane: OfferedLane,
  mode: MatrixMode,
  ready: boolean,
): MatrixRow[] {
  if (!offer.observed) return [];
  if (mode === "task")
    return taskModelsOf(lane).map((model) => ({
      key: rowKey(lane.id, model.model),
      id: model.model,
      name: model.name,
      description: model.description,
      held: heldModel(model),
      efforts: efforts(model.backgroundEfforts),
      defaultEffort: model.defaultEffort,
      written: false,
      choosable: ready && heldModel(model),
      recommended: false,
    }));
  if (lane.modelWritten)
    return [
      {
        key: rowKey(lane.id, ""),
        id: "",
        name: lane.name,
        description: null,
        held: true,
        efforts: efforts(lane.modelWritten.efforts),
        defaultEffort: null,
        written: true,
        choosable: ready,
        recommended: false,
      },
    ];
  return (offer.models[lane.wayId] ?? []).map((model) => ({
    key: rowKey(lane.id, model.id),
    id: model.id,
    name: model.name,
    description: model.description ?? null,
    held: heldModel(model),
    efforts: efforts(model.efforts.map((effort) => effort.id)),
    defaultEffort: model.defaultEffort ?? null,
    written: false,
    choosable: ready && heldModel(model),
    recommended: model.id === lane.defaultEntryId,
  }));
}

/** Every lane the matrix can show for `mode`, filters and search aside. */
function everyLane(
  t: Translate,
  offer: AgentOffer,
  mode: MatrixMode,
  fixedWayId: string | undefined,
): MatrixLane[] {
  // A background task runs only on a lane that takes text for it and lists
  // its models; while the agent starts, every declared lane is shown.
  const offered = offer.providers.flatMap((provider) =>
    provider.lanes
      .filter(
        (lane) =>
          mode === "conversation" ||
          !offer.observed ||
          offer.taskLanes.some((held) => held.id === lane.id),
      )
      .map((lane): MatrixLane => {
        const ready = lane.runs && lane.on !== false;
        // A lane that runs can still list a model to download before it
        // can be chosen.
        const {
          step,
          door,
        }: { step: MatrixStep | null; door: EngineDoor | null } = ready
          ? { step: lane.modelsToDownload ? "download" : null, door: null }
          : stepOf(lane);
        return {
          id: lane.id,
          wayId: lane.wayId,
          provider: lane.provider,
          providerName: provider.name,
          name: lane.name,
          connection: connectionWords(t, lane),
          standing: lane.on === false ? "off" : lane.runs ? "ready" : "setup",
          words:
            lane.on === false
              ? t("desktop.providers.status_off")
              : !lane.runs
                ? (lane.held?.words ?? t("desktop.agent.unavailable"))
                : mode === "conversation" &&
                    fixedWayId !== undefined &&
                    lane.wayId !== fixedWayId
                  ? t("desktop.agent.continue_in_new_conversation")
                  : null,
          step: lane.on === false ? "set_up" : step,
          door: lane.on === false ? null : door,
          rows: laneRows(offer, lane, mode, ready),
        };
      }),
  );
  const off = offer.turnedOff.map(
    (record: ProviderSettingsRecord): MatrixLane => ({
      id: record.id,
      wayId: null,
      provider: record.provider,
      providerName: record.display_name,
      name: record.display_name,
      connection: connectionWords(t, {
        transport: record.transport,
        authKind: record.auth_kind,
      }),
      standing: "off",
      words: t("desktop.providers.status_off"),
      step: "set_up",
      door: null,
      rows: [],
    }),
  );
  return [...offered, ...off];
}

const laneWords = (lane: MatrixLane) => [
  lane.providerName,
  lane.name,
  lane.connection,
];

const rowWords = (t: Translate, row: MatrixRow) => [
  row.name,
  row.id,
  row.description ?? "",
  ...row.efforts.map((effort) => effortWords(t, effort)),
];

const passes = (lane: MatrixLane, filters: MatrixFilters) => {
  const on = lane.standing !== "off";
  const ready = lane.standing === "ready";
  return (
    (filters.on === filters.off || (on ? filters.on : filters.off)) &&
    (filters.ready === filters.setup || (ready ? filters.ready : filters.setup))
  );
};

/**
 * What the matrix shows of `offer` for `mode`: the lanes the filters keep,
 * each with the rows whose words, with their lane's, hold every word of
 * `query`; a lane with no rows is kept where its own words do. The columns
 * are the provider's default and the efforts some row shown takes, lowest
 * first.
 */
export function matrixView(
  t: Translate,
  offer: AgentOffer,
  mode: MatrixMode,
  query: string,
  filters: MatrixFilters,
  fixedWayId?: string,
): MatrixView {
  const every = everyLane(t, offer, mode, fixedWayId);
  const found = every.flatMap((lane): MatrixLane[] => {
    const words = laneWords(lane);
    const rows = lane.rows.filter((row) =>
      offerMatches([...words, ...rowWords(t, row)], query),
    );
    const kept =
      rows.length > 0 || (lane.rows.length === 0 && offerMatches(words, query));
    return kept ? [{ ...lane, rows }] : [];
  });
  const lanes = found.filter((lane) => passes(lane, filters));
  const shown = new Set(
    lanes.flatMap((lane) => lane.rows.flatMap((row) => row.efforts)),
  );
  return {
    columns: ["default", ...EFFORTS.filter((effort) => shown.has(effort))],
    lanes,
    offHidden: found.filter(
      (lane) => lane.standing === "off" && !lanes.includes(lane),
    ).length,
    noneOn: every.length > 0 && every.every((lane) => lane.standing === "off"),
    rows: lanes.reduce((count, lane) => count + lane.rows.length, 0),
  };
}

/** Where the keyboard stands in the matrix: a row by key and a column. */
export type MatrixCell = { row: string; column: MatrixColumn };

/** The cells a row has, in column order: the default, then each effort the
 * row's model takes that is a column. */
export const rowCells = (
  row: Pick<MatrixRow, "efforts">,
  columns: readonly MatrixColumn[],
): MatrixColumn[] =>
  columns.filter(
    (column) => column === "default" || row.efforts.includes(column),
  );

/** The keys that move in the matrix. */
export type MatrixKey =
  | "ArrowLeft"
  | "ArrowRight"
  | "ArrowUp"
  | "ArrowDown"
  | "Home"
  | "End"
  | "PageUp"
  | "PageDown";

/**
 * Where `key` moves from `at`: along the row to the next cell it has, up or
 * down to the nearest cell of the next row at or before the same column, to
 * the row's ends, or to the first row of the lane before or after. A move
 * past an edge stays where it is.
 */
export function matrixMove(
  view: Pick<MatrixView, "lanes" | "columns">,
  at: MatrixCell,
  key: MatrixKey,
): MatrixCell {
  const rows = view.lanes.flatMap((lane, group) =>
    lane.rows.map((row) => ({ row, group })),
  );
  const index = rows.findIndex((entry) => entry.row.key === at.row);
  const current = rows[index];
  if (!current) return at;
  const cells = rowCells(current.row, view.columns);
  const column = Math.max(0, cells.indexOf(at.column));
  const toRow = (target: number): MatrixCell => {
    const entry = rows[target];
    if (!entry) return at;
    const order = view.columns.indexOf(at.column);
    const there = rowCells(entry.row, view.columns);
    const nearest =
      [...there]
        .reverse()
        .find((held) => view.columns.indexOf(held) <= order) ??
      there[0] ??
      "default";
    return { row: entry.row.key, column: nearest };
  };
  const every = () => true;
  switch (key) {
    case "ArrowLeft":
      return {
        row: at.row,
        column: cells[Math.max(0, column - 1)] ?? at.column,
      };
    case "ArrowRight":
      return {
        row: at.row,
        column: cells[Math.min(cells.length - 1, column + 1)] ?? at.column,
      };
    case "Home":
      return { row: at.row, column: cells[0] ?? at.column };
    case "End":
      return { row: at.row, column: cells[cells.length - 1] ?? at.column };
    case "ArrowUp":
      return toRow(nextRow(rows.length, index, -1, every));
    case "ArrowDown":
      return toRow(nextRow(rows.length, index, 1, every));
    case "PageUp": {
      // The first row of this lane, or of the lane before where already there.
      const first = edgeRow(
        rows.length,
        "first",
        (at) => rows[at]?.group === current.group,
      );
      const target =
        first < index
          ? first
          : edgeRow(
              rows.length,
              "first",
              (at) => rows[at]?.group === (rows[index - 1]?.group ?? -1),
            );
      return target < 0 || target >= rows.length ? at : toRow(target);
    }
    case "PageDown": {
      const next = nextRow(
        rows.length,
        index,
        1,
        (at) => rows[at]?.group !== current.group,
      );
      return next === index ? at : toRow(next);
    }
  }
}
