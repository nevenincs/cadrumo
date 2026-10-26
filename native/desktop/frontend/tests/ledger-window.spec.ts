import { expect, test } from "@playwright/test";
import type {
  LedgerListResult,
  LedgerRow,
  LedgerStatusResult,
} from "../src/shell/ledger";
import {
  checkReadiness,
  LEDGER_OPEN_WINDOW_ROWS,
  LEDGER_PAGE_SIZE,
  nextPageRequest,
  openWindow,
  readWindow,
  reduceWindow,
  shownRows,
  windowComplete,
  windowProgress,
  windowTruncation,
  type LedgerWindow,
} from "../src/shell/ledgerWindow";
import { fakePort, hexId, listPage, movement, PROFILE } from "./support/ledger";

// The period window and the frozen readiness checks. No page is opened.

const Q3 = { year: 2026, code: "3T" } as const;
const rows = (count: number, from = 0): LedgerRow[] =>
  Array.from({ length: count }, (_, at) => movement(hexId(`m${from + at}`)));
const page = (all: LedgerRow[], offset: number, limit = LEDGER_PAGE_SIZE) =>
  listPage(
    all.slice(offset, offset + limit),
    all.length,
    offset,
    limit,
  ) as unknown as LedgerListResult;

/** Feeds a window the pages it asks for from `all` until it stops. */
function readAll(window: LedgerWindow, all: LedgerRow[]): LedgerWindow {
  for (let request = nextPageRequest(window); request;) {
    window = reduceWindow(window, {
      type: "page",
      generation: window.generation,
      offset: request.offset!,
      result: page(all, request.offset!, request.limit!),
    });
    request = nextPageRequest(window);
  }
  return window;
}

test("a period is read in pages of 250 under one stable order", () => {
  const window = openWindow(1, Q3);
  expect(nextPageRequest(window)).toEqual({
    filters: ["period=3T", "year=2026"],
    sort_by: "date",
    sort_order: "asc",
    offset: 0,
    limit: 250,
  });
  const all = rows(612);
  let read = reduceWindow(window, {
    type: "page",
    generation: 1,
    offset: 0,
    result: page(all, 0),
  });
  expect(read.phase).toBe("reading");
  expect(windowProgress(read)).toEqual({ loaded: 250, total: 612 });
  expect(windowComplete(read)).toBe(false);
  // Nothing is shown to group or sum while the window is partly read.
  expect(shownRows(read)).toBeNull();
  expect(nextPageRequest(read)).toMatchObject({ offset: 250, limit: 250 });
  read = readAll(read, all);
  expect(read.phase).toBe("ready");
  expect(read.rows.map((row) => row.transaction.transaction_id)).toEqual(
    all.map((row) => row.transaction.transaction_id),
  );
  expect(windowComplete(read)).toBe(true);
  expect(windowTruncation(read)).toBeNull();
  expect(nextPageRequest(read)).toBeNull();
});

test("an empty period is ready and empty, and a failed read is never empty", () => {
  const empty = readAll(openWindow(1, Q3), []);
  expect(empty.phase).toBe("ready");
  expect(windowComplete(empty)).toBe(true);
  expect(shownRows(empty)).toEqual({ rows: [], total: 0 });

  const failed = reduceWindow(openWindow(1, Q3), {
    type: "failed",
    generation: 1,
    failure: { kind: "failed", code: "unavailable", reason: null },
  });
  expect(failed.phase).toBe("failed");
  expect(shownRows(failed)).toBeNull();
  expect(windowComplete(failed)).toBe(false);
});

test("an answer to an older read is dropped", () => {
  const all = rows(30);
  let window = openWindow(1, Q3);
  window = reduceWindow(window, {
    type: "open",
    generation: 2,
    period: { year: 2026, code: "4T" },
  });
  const stale = reduceWindow(window, {
    type: "page",
    generation: 1,
    offset: 0,
    result: page(all, 0),
  });
  expect(stale).toBe(window);
  const staleFailure = reduceWindow(window, {
    type: "failed",
    generation: 1,
    failure: { kind: "refused", reason: "x" },
  });
  expect(staleFailure).toBe(window);
  // A page for an offset the window is not at is not joined either.
  const misplaced = reduceWindow(window, {
    type: "page",
    generation: 2,
    offset: 250,
    result: page(all, 0),
  });
  expect(misplaced).toBe(window);
});

test("a ledger that changes between pages makes the read start over, then fail", () => {
  const all = rows(400);
  let window = reduceWindow(openWindow(1, Q3), {
    type: "page",
    generation: 1,
    offset: 0,
    result: page(all, 0),
  });
  // A row added since the first page moves the total.
  const grown = [...all, ...rows(1, 900)];
  window = reduceWindow(window, {
    type: "page",
    generation: 1,
    offset: 250,
    result: page(grown, 250),
  });
  expect(window.rows).toEqual([]);
  expect(window.restarts).toBe(1);
  expect(nextPageRequest(window)).toMatchObject({ offset: 0 });
  // A row seen twice also breaks the join.
  window = reduceWindow(window, {
    type: "page",
    generation: 1,
    offset: 0,
    result: page(all, 0),
  });
  const repeated = { ...page(all, 250), rows: all.slice(249, 499) };
  window = reduceWindow(window, {
    type: "page",
    generation: 1,
    offset: 250,
    result: repeated,
  });
  expect(window.restarts).toBe(2);
  window = reduceWindow(window, {
    type: "page",
    generation: 1,
    offset: 0,
    result: page(all, 0),
  });
  window = reduceWindow(window, {
    type: "page",
    generation: 1,
    offset: 250,
    result: page(grown, 250),
  });
  expect(window.phase).toBe("failed");
  expect(window.failure).toEqual({ kind: "unsettled" });
});

test("all periods stops at a bound, says how much it shows, and reads on", () => {
  const all = rows(1_340);
  let window = readAll(openWindow(1, null), all);
  expect(nextPageRequest(openWindow(1, null))?.filters).toEqual([]);
  expect(window.phase).toBe("ready");
  expect(window.rows).toHaveLength(LEDGER_OPEN_WINDOW_ROWS);
  expect(windowComplete(window)).toBe(false);
  expect(windowTruncation(window)).toEqual({ loaded: 1_000, total: 1_340 });
  window = reduceWindow(window, {
    type: "more",
    generation: 1,
    wanted: Infinity,
  });
  expect(window.phase).toBe("reading");
  window = readAll(window, all);
  expect(window.rows).toHaveLength(1_340);
  expect(windowTruncation(window)).toBeNull();
  expect(windowComplete(window)).toBe(true);
});

test("reading the same period again holds the whole window until the new one is whole", () => {
  const all = rows(300);
  const first = readAll(openWindow(1, Q3), all);
  const again = reduceWindow(first, {
    type: "open",
    generation: 2,
    period: Q3,
  });
  expect(again.phase).toBe("reading");
  expect(shownRows(again)?.rows).toHaveLength(300);
  const partly = reduceWindow(again, {
    type: "page",
    generation: 2,
    offset: 0,
    result: page(all, 0),
  });
  expect(shownRows(partly)?.rows).toHaveLength(300);
  const whole = readAll(partly, all);
  expect(whole.held).toBeNull();
  // Another period, or another profile's read, holds nothing.
  const other = reduceWindow(first, {
    type: "open",
    generation: 3,
    period: { year: 2025, code: "4T" },
  });
  expect(shownRows(other)).toBeNull();
  const otherProfile = reduceWindow(first, {
    type: "open",
    generation: 4,
    period: Q3,
    hold: false,
  });
  expect(shownRows(otherProfile)).toBeNull();
});

test("a whole-window read follows every page and reports a refusal as such", async () => {
  const all = rows(520);
  const { port, calls } = fakePort((call) => {
    if (call.kind !== "submit") throw new Error("unexpected");
    const offset = call.payload.offset as number;
    return { settle: page(all, offset, call.payload.limit as number) };
  });
  const read = await readWindow(port, Q3);
  expect(read.kind).toBe("read");
  expect(read.kind === "read" && read.rows.length).toBe(520);
  expect(
    calls.map((call) => call.kind === "submit" && call.payload.offset),
  ).toEqual([0, 250, 500]);

  const refused = fakePort(() => ({ refuse: "operation_unavailable" }));
  expect(await readWindow(refused.port, Q3)).toEqual({
    kind: "failed",
    failure: { kind: "refused", reason: "operation_unavailable" },
  });
  const unavailable = fakePort(() => ({
    fail: { code: "not_signed_in", operation_id: null },
  }));
  expect(await readWindow(unavailable.port, Q3)).toEqual({
    kind: "failed",
    failure: { kind: "failed", code: "not_signed_in", reason: null },
  });
});

const status = (ready: boolean | null): LedgerStatusResult => ({
  profile_id: PROFILE,
  period: { filing_year: 2026, code: "3T" },
  business_income_total: "0",
  business_expense_total: "0",
  business_net_total: "0",
  total_count: 3,
  active_count: 3,
  archived_count: 0,
  stashed_count: 0,
  split_count: 0,
  pending_review_count: 1,
  reviewed_count: 2,
  skipped_count: 0,
  checked_transaction_count: 3,
  readiness_issue_count: 1,
  unconverted_currency_count: 0,
  ready,
  readiness_issues: [],
  stale_filings: [],
});

test("readiness is read through status and preflight and frozen at its check", async () => {
  const { port, calls } = fakePort((call) => {
    if (call.kind === "submit" && call.definition === "ledger.status")
      return { settle: status(false) };
    return {
      settle: {
        profile_id: PROFILE,
        period: { filing_year: 2026, code: "3T" },
        bucket_id: PROFILE,
        checked_transaction_count: 3,
        issues: [],
        ready: false,
      },
    };
  });
  const checked = await checkReadiness(port, Q3, () => 1_000);
  expect(
    calls.map((call) => call.kind === "submit" && call.definition),
  ).toEqual(["ledger.status", "ledger.preflight"]);
  expect(checked.kind).toBe("checked");
  if (checked.kind !== "checked") return;
  const snapshot = checked.snapshot;
  expect(snapshot.checkedAt).toBe(1_000);
  expect(snapshot.status.ready).toBe(false);
  expect(snapshot.savedSince).toBe(0);

  // All periods has no preflight.
  const open = fakePort(() => ({ settle: status(null) }));
  const all = await checkReadiness(open.port, null, () => 5);
  expect(open.calls).toHaveLength(1);
  expect(all.kind === "checked" && all.snapshot.preflight).toBeNull();
  // Unknown stays unknown: a null `ready` is not measured, not ready.
  expect(all.kind === "checked" && all.snapshot.status.ready).toBeNull();

  const failing = fakePort(() => ({
    fail: { code: "unavailable", operation_id: null },
  }));
  expect(await checkReadiness(failing.port, Q3, () => 0)).toEqual({
    kind: "failed",
    failure: { kind: "failed", code: "unavailable", reason: null },
  });
});
