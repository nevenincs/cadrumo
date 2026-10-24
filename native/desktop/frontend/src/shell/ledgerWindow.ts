// The period window the Ledger page shows: every movement of one period,
// read through `ledger.list` in pages under one stable order and assembled
// before anything groups or sums it, and the readiness checks frozen at the
// moment they ran. A failed read is a failure, never an empty period, and an
// answer to a read no longer being asked is dropped.

import { useCallback, useEffect, useReducer, useRef } from "react";
import {
  ledgerFailure,
  type LedgerFailureCode,
  type LedgerListRequest,
  type LedgerListResult,
  type LedgerOutcome,
  type LedgerPort,
  type LedgerPreflightResult,
  type LedgerRow,
  type LedgerSortField,
  type LedgerSortOrder,
  type LedgerStatusResult,
} from "./ledger";
import {
  periodFilters,
  publicPeriod,
  samePeriod,
  type LedgerPeriod,
} from "./ledgerGrammar";

const NO_SCOPE: LedgerWindowScope = {};

/** Rows per `ledger.list` call: a page stays well inside one relay reply. */
export const LEDGER_PAGE_SIZE = 250;
/** Rows "All periods" reads before it asks to read on. A period is always
 * read whole. */
export const LEDGER_OPEN_WINDOW_ROWS = 1_000;
/** How often a read starts over because the ledger changed under it before
 * it gives up. */
const RESTART_LIMIT = 2;

/** Why the window could not be read. */
export type LedgerReadFailure =
  | {
      /** The call did not answer. */
      kind: "failed";
      code: LedgerFailureCode;
      reason: string | null;
    }
  | {
      /** The runtime settled the read without answering it. */
      kind: "refused";
      reason: string | null;
    }
  | {
      /** The ledger kept changing while its pages were read. */
      kind: "unsettled";
    };

/** The rows of a window read whole, kept on screen while it is read again. */
export type HeldWindow = { rows: LedgerRow[]; total: number };

/** What a window reads beside its period: further filter clauses, and the
 * server's order and group partition where the page cannot sort or group
 * the rows itself, as when "All periods" is read only in part. */
export type LedgerWindowScope = {
  filters?: readonly string[];
  sort_by?: LedgerSortField;
  sort_order?: LedgerSortOrder;
  by_group?: boolean;
  exclude_llm_rejected?: boolean;
};

/** A scope as one comparable text: two scopes that read the same rows in
 * the same order are equal. `scopeOfKey` reads it back. */
export function scopeKey(scope: LedgerWindowScope): string {
  return JSON.stringify([
    [...(scope.filters ?? [])].sort(),
    scope.sort_by ?? "date",
    scope.sort_order ?? "asc",
    scope.by_group === true,
    scope.exclude_llm_rejected === true,
  ]);
}
export function scopeOfKey(key: string): LedgerWindowScope {
  const [filters, sortBy, sortOrder, byGroup, excludeRejected] = JSON.parse(
    key,
  ) as [string[], LedgerSortField, LedgerSortOrder, boolean, boolean];
  return {
    ...(filters.length ? { filters } : {}),
    sort_by: sortBy,
    sort_order: sortOrder,
    ...(byGroup ? { by_group: true } : {}),
    ...(excludeRejected ? { exclude_llm_rejected: true } : {}),
  };
}

export type LedgerWindow = {
  /** Which read this is; an answer to an older one is dropped. */
  generation: number;
  /** The period read, or null for every period. */
  period: LedgerPeriod | null;
  scope: LedgerWindowScope;
  phase: "reading" | "ready" | "failed";
  /** The rows read so far, in the read's order. */
  rows: LedgerRow[];
  /** How many rows the period has, once the first page said. */
  total: number | null;
  /** How many rows to read before stopping. */
  wanted: number;
  restarts: number;
  failure: LedgerReadFailure | null;
  /** The last window read whole for the same period, shown while this one
   * is read. */
  held: HeldWindow | null;
};

export type LedgerWindowEvent =
  | {
      type: "open";
      generation: number;
      period: LedgerPeriod | null;
      wanted?: number;
      scope?: LedgerWindowScope;
      /** Keep the window read whole on screen while it is read again. */
      hold?: boolean;
    }
  | {
      type: "page";
      generation: number;
      offset: number;
      result: LedgerListResult;
    }
  | { type: "failed"; generation: number; failure: LedgerReadFailure }
  | { type: "more"; generation: number; wanted: number };

const wantedFor = (period: LedgerPeriod | null, wanted?: number) =>
  wanted ?? (period === null ? LEDGER_OPEN_WINDOW_ROWS : Infinity);

export function openWindow(
  generation: number,
  period: LedgerPeriod | null,
  wanted?: number,
  scope: LedgerWindowScope = {},
): LedgerWindow {
  return {
    generation,
    period,
    scope,
    phase: "reading",
    rows: [],
    total: null,
    wanted: wantedFor(period, wanted),
    restarts: 0,
    failure: null,
    held: null,
  };
}

/** The window read whole, or null while it is not. */
function heldOf(current: LedgerWindow): HeldWindow | null {
  if (current.phase === "ready" && current.total !== null)
    return { rows: current.rows, total: current.total };
  return current.held;
}

function restart(current: LedgerWindow): LedgerWindow {
  if (current.restarts >= RESTART_LIMIT)
    return { ...current, phase: "failed", failure: { kind: "unsettled" } };
  return {
    ...current,
    rows: [],
    total: null,
    restarts: current.restarts + 1,
  };
}

export function reduceWindow(
  current: LedgerWindow,
  event: LedgerWindowEvent,
): LedgerWindow {
  if (event.type === "open") {
    const next = openWindow(
      event.generation,
      event.period,
      event.wanted,
      event.scope,
    );
    // Rows read under another scope are other rows: none is held for them.
    return event.hold !== false &&
      samePeriod(current.period, event.period) &&
      scopeKey(current.scope) === scopeKey(next.scope)
      ? { ...next, held: heldOf(current) }
      : next;
  }
  // An answer to a read no longer being asked is not shown.
  if (event.generation !== current.generation) return current;
  if (event.type === "failed")
    return current.phase === "reading"
      ? { ...current, phase: "failed", failure: event.failure }
      : current;
  if (event.type === "more") {
    if (current.phase !== "ready" || event.wanted <= current.wanted)
      return current;
    const done = current.total !== null && current.rows.length >= current.total;
    return done
      ? { ...current, wanted: event.wanted }
      : { ...current, wanted: event.wanted, phase: "reading" };
  }
  if (current.phase !== "reading" || event.offset !== current.rows.length)
    return current;
  const result = event.result;
  if (result.offset !== event.offset) return restart(current);
  // A total that moved, or a row seen twice, means the ledger changed
  // between pages: the pages no longer join into one window.
  if (current.total !== null && result.total !== current.total)
    return restart(current);
  const seen = new Set(
    current.rows.map((row) => row.transaction.transaction_id),
  );
  if (result.rows.some((row) => seen.has(row.transaction.transaction_id)))
    return restart(current);
  const rows = [...current.rows, ...result.rows];
  const total = result.total;
  if (result.rows.length === 0 && rows.length < total) return restart(current);
  const done = rows.length >= Math.min(total, current.wanted);
  return {
    ...current,
    rows,
    total,
    phase: done ? "ready" : "reading",
    held: done ? null : current.held,
  };
}

/** The next page a reading window asks for, or null when it asks for
 * none. The order is the product's date order unless the scope names
 * another, ties by id, so pages join. */
export function nextPageRequest(
  current: LedgerWindow,
): LedgerListRequest | null {
  if (current.phase !== "reading") return null;
  const remaining =
    current.total === null
      ? current.wanted
      : Math.min(current.total, current.wanted) - current.rows.length;
  if (remaining <= 0) return null;
  const scope = current.scope;
  return {
    filters: [
      ...(current.period ? periodFilters(current.period) : []),
      ...(scope.filters ?? []),
    ],
    sort_by: scope.sort_by ?? "date",
    sort_order: scope.sort_order ?? "asc",
    ...(scope.by_group ? { by_group: true } : {}),
    ...(scope.exclude_llm_rejected ? { exclude_llm_rejected: true } : {}),
    offset: current.rows.length,
    limit: Math.min(LEDGER_PAGE_SIZE, remaining),
  };
}

/** How much of the window is read: "Reading 500 of 1,240". */
export function windowProgress(current: LedgerWindow): {
  loaded: number;
  total: number | null;
} {
  return { loaded: current.rows.length, total: current.total };
}

/** Whether every row of the window is read, so grouping and totals may be
 * offered. */
export function windowComplete(current: LedgerWindow): boolean {
  return (
    current.phase === "ready" &&
    current.total !== null &&
    current.rows.length === current.total
  );
}

/** The rows the page may show: the window read whole, or the one held
 * while it is read again. */
export function shownRows(current: LedgerWindow): HeldWindow | null {
  return heldOf(current);
}

/** Where a window read only partly stops: "200 loaded of 340". Null when
 * it is whole or still reading. */
export function windowTruncation(
  current: LedgerWindow,
): { loaded: number; total: number } | null {
  if (current.phase !== "ready" || current.total === null) return null;
  return current.rows.length < current.total
    ? { loaded: current.rows.length, total: current.total }
    : null;
}

/** A map from id to row for the rows a window shows. */
export function rowsById(rows: readonly LedgerRow[]): Map<string, LedgerRow> {
  return new Map(rows.map((row) => [row.transaction.transaction_id, row]));
}

/** What one read call answered. */
export type ReadAnswer<Result> =
  | { kind: "answer"; result: Result }
  | { kind: "failed"; failure: LedgerReadFailure };

/** The answer of a settled read, or why there is none. A read that comes
 * back waiting or running did not answer. */
export function readAnswer<Result>(
  outcome: LedgerOutcome<Result>,
): ReadAnswer<Result> {
  if (outcome.kind === "settled")
    return { kind: "answer", result: outcome.result };
  if (outcome.kind === "refused")
    return {
      kind: "failed",
      failure: { kind: "refused", reason: outcome.reason },
    };
  return {
    kind: "failed",
    failure: { kind: "failed", code: "unavailable", reason: null },
  };
}
export function readFailure(error: unknown): LedgerReadFailure {
  const failure = ledgerFailure(error);
  return { kind: "failed", code: failure.code, reason: failure.reason ?? null };
}

/** Reads one page of `window`. */
export async function readPage(
  port: LedgerPort,
  request: LedgerListRequest,
): Promise<ReadAnswer<LedgerListResult>> {
  try {
    return readAnswer(await port.submit("ledger.list", request));
  } catch (error) {
    return { kind: "failed", failure: readFailure(error) };
  }
}

/** Reads a period's window whole, page by page, outside any view: the
 * read an apply makes before it writes. */
export async function readWindow(
  port: LedgerPort,
  period: LedgerPeriod | null,
  wanted = Infinity,
  scope: LedgerWindowScope = {},
): Promise<
  | { kind: "read"; rows: LedgerRow[]; total: number }
  | { kind: "failed"; failure: LedgerReadFailure }
> {
  let state = openWindow(1, period, wanted, scope);
  for (
    let request = nextPageRequest(state);
    request;
    request = nextPageRequest(state)
  ) {
    const offset = request.offset ?? 0;
    const answer = await readPage(port, request);
    state = reduceWindow(
      state,
      answer.kind === "answer"
        ? { type: "page", generation: 1, offset, result: answer.result }
        : { type: "failed", generation: 1, failure: answer.failure },
    );
  }
  return state.failure
    ? { kind: "failed", failure: state.failure }
    : { kind: "read", rows: state.rows, total: state.total ?? 0 };
}

/**
 * The period window of one profile, read when the page is shown and again
 * on `reread`. `reader` names whose ledger it is and is null while the
 * account withholds it: what was read is dropped whenever it changes, and
 * nothing of one profile is held on screen under another. A changed
 * `scope` reads the window again.
 */
export function useLedgerWindow(
  port: LedgerPort | undefined,
  reader: string | null,
  period: LedgerPeriod | null,
  shown: boolean,
  scope: LedgerWindowScope = NO_SCOPE,
) {
  const generation = useRef(0);
  const lastReader = useRef(reader);
  // Nothing is asked for until the page is shown.
  const [state, dispatch] = useReducer(reduceWindow, period, (first) =>
    openWindow(0, first, 0),
  );
  const year = period?.year ?? null;
  const code = period?.code ?? null;
  const scoped = scopeKey(scope);

  const open = useCallback(
    (hold: boolean) => {
      generation.current += 1;
      dispatch({
        type: "open",
        generation: generation.current,
        period: year === null || code === null ? null : { year, code },
        scope: scopeOfKey(scoped),
        hold,
      });
    },
    [year, code, scoped],
  );
  const reread = useCallback(() => open(true), [open]);

  useEffect(() => {
    const sameReader = lastReader.current === reader;
    lastReader.current = reader;
    if (shown && reader !== null) open(sameReader);
    else if (!sameReader) open(false);
  }, [shown, reader, open]);

  useEffect(() => {
    if (!port || !shown || reader === null) return;
    const request = nextPageRequest(state);
    if (!request) return;
    let active = true;
    const mine = state.generation;
    const offset = request.offset ?? 0;
    void readPage(port, request).then((answer) => {
      if (!active) return;
      dispatch(
        answer.kind === "answer"
          ? { type: "page", generation: mine, offset, result: answer.result }
          : { type: "failed", generation: mine, failure: answer.failure },
      );
    });
    return () => {
      active = false;
    };
  }, [port, shown, reader, state]);

  const readMore = useCallback(
    (rows = LEDGER_OPEN_WINDOW_ROWS) =>
      dispatch({
        type: "more",
        generation: state.generation,
        wanted: state.wanted + rows,
      }),
    [state.generation, state.wanted],
  );
  const readAll = useCallback(
    () =>
      dispatch({
        type: "more",
        generation: state.generation,
        wanted: Infinity,
      }),
    [state.generation],
  );
  return {
    window: reader === null ? null : state,
    reread,
    readMore,
    readAll,
  };
}

// ---- Readiness ---------------------------------------------------------------

/** The readiness checks as they stood when they ran. Nothing here is
 * recounted in the window: after a change it is out of date, not redone. */
export type ReadinessSnapshot = {
  period: LedgerPeriod | null;
  /** When the checks ran, in the clock's milliseconds. */
  checkedAt: number;
  status: LedgerStatusResult;
  /** The period's preflight; "All periods" has none. */
  preflight: LedgerPreflightResult | null;
  /** Changes saved since the checks ran. */
  savedSince: number;
};

export type Readiness =
  | { kind: "not_checked" }
  | { kind: "checking"; held: ReadinessSnapshot | null }
  | { kind: "checked"; snapshot: ReadinessSnapshot }
  | {
      kind: "failed";
      failure: LedgerReadFailure;
      held: ReadinessSnapshot | null;
    };

/** Runs the status and, for one period, the preflight read. */
export async function checkReadiness(
  port: LedgerPort,
  period: LedgerPeriod | null,
  now: () => number,
): Promise<
  | { kind: "checked"; snapshot: ReadinessSnapshot }
  | { kind: "failed"; failure: LedgerReadFailure }
> {
  try {
    const wire = period ? publicPeriod(period) : null;
    const status = readAnswer(
      await port.submit("ledger.status", { period: wire }),
    );
    if (status.kind === "failed") return status;
    let preflight: LedgerPreflightResult | null = null;
    if (wire) {
      const answer = readAnswer(
        await port.submit("ledger.preflight", { period: wire }),
      );
      if (answer.kind === "failed") return answer;
      preflight = answer.result;
    }
    return {
      kind: "checked",
      snapshot: {
        period,
        checkedAt: now(),
        status: status.result,
        preflight,
        savedSince: 0,
      },
    };
  } catch (error) {
    return { kind: "failed", failure: readFailure(error) };
  }
}

/** The snapshot the page shows, if any. */
export function readinessSnapshot(
  readiness: Readiness,
): ReadinessSnapshot | null {
  if (readiness.kind === "checked") return readiness.snapshot;
  if (readiness.kind === "not_checked") return null;
  return readiness.held;
}
