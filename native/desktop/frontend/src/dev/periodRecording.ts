// The periods `ledger.entry-options` serves, answered from the recording of that
// read in the generated `ledgerEntryOptions.json`, which a backend test holds to the
// ledger's own period read. Nothing here works a period out: a year's table is
// the recorded one, and a day or a span is answered by finding the recorded
// periods whose recorded days hold it. What the recording holds no answer for
// is not answered, as a read that failed.

import servedEntryOptions from "@fixtures/ledger-entry-options/ledgerEntryOptions.json" with { type: "json" };
import { holdLedgerPeriods } from "../shell/ledgerPeriods";
import type {
  LedgerEntryOptionsRequest,
  LedgerServedDay,
  LedgerServedPeriod,
  LedgerServedPeriods,
} from "../shell/ledgerSetup";

type Language = NonNullable<LedgerEntryOptionsRequest["output_language"]>;
type Query = NonNullable<LedgerEntryOptionsRequest["periods"]>;

const recording = servedEntryOptions.periods;
const tables = recording.years as unknown as Record<
  string,
  Record<string, LedgerServedPeriod[]>
>;
const reference = recording.containing as unknown as LedgerServedDay;

/** The language a read without one is answered in, as the backend's. */
export const RECORDED_DEFAULT_LANGUAGE: Language = "es";
/** The year a read without one lists. */
export const RECORDED_YEAR = reference.annual.filing_year;

const rowsOf = (language: Language): LedgerServedPeriod[] =>
  Object.values(tables[language] ?? {}).flat();

/** The recorded table of `year` in `language`, or null where none is recorded. */
function yearTable(
  language: Language,
  year: number,
): LedgerServedPeriod[] | null {
  return tables[language]?.[String(year)] ?? null;
}

function dayPeriods(language: Language, day: string): LedgerServedDay | null {
  const holding = rowsOf(language).filter(
    (row) => row.first_day <= day && day <= row.last_day,
  );
  const annual = holding.find((row) => row.kind === "annual");
  const quarterly = holding.find((row) => row.kind === "quarterly");
  const monthly = holding.find((row) => row.kind === "monthly");
  return annual && quarterly && monthly
    ? {
        day,
        annual: annual.period,
        quarterly: quarterly.period,
        monthly: monthly.period,
      }
    : null;
}

function spanPeriod(
  language: Language,
  first: string,
  last: string,
): { found: boolean; period: LedgerServedPeriod["period"] | null } {
  const rows = rowsOf(language);
  const year = rows.find(
    (row) =>
      row.kind === "annual" && row.first_day <= first && first <= row.last_day,
  );
  // A span that begins in a year with no recorded table has no recorded answer.
  if (!year) return { found: false, period: null };
  for (const kind of ["monthly", "quarterly", "annual"] as const) {
    const holds = rows.find(
      (row) =>
        row.kind === kind && row.first_day <= first && last <= row.last_day,
    );
    if (holds) return { found: true, period: holds.period };
  }
  return { found: true, period: null };
}

/** Answers a period read from the recording, or null where it holds no answer. */
export function answerPeriods(
  language: Language,
  query: Query,
): LedgerServedPeriods | null {
  const year = query.year ?? RECORDED_YEAR;
  const table = yearTable(language, year);
  if (table === null) return null;
  const days: LedgerServedDay[] = [];
  for (const day of query.days ?? []) {
    const found = dayPeriods(language, day);
    if (found === null) return null;
    days.push(found);
  }
  let covering: LedgerServedPeriods["covering"];
  if (query.covering) {
    const found = spanPeriod(
      language,
      query.covering.first_day,
      query.covering.last_day,
    );
    if (!found.found) return null;
    covering = { ...query.covering, period: found.period };
  }
  return {
    year,
    annual_code: recording.annual_code,
    periods: table,
    containing: reference,
    ...(covering ? { covering } : {}),
    days,
  };
}

/** The first and last day of a recorded period, or null where none is. */
export function recordedSpan(
  year: number,
  code: string,
): { from: string; to: string } | null {
  const row = yearTable("en", year)?.find(
    (found) => found.period.code === code,
  );
  return row ? { from: row.first_day, to: row.last_day } : null;
}

/** The recorded periods a story or a model test is drawn with: every year
 * recorded in `language`, held as the page holds what it was served. */
export function holdRecordedPeriods(language: Language): void {
  holdLedgerPeriods(null, null);
  for (const year of Object.keys(tables[language] ?? {})) {
    const served = answerPeriods(language, { year: Number(year) });
    if (served) holdLedgerPeriods(language, served);
  }
}
