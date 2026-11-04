// The filing periods the Ledger page selects among, as the backend serves them
// with `ledger.entry-options`: each year's periods with their days, the periods
// either side of each across year ends, their names in the language the window
// shows, the periods that hold a day, and the period that holds a span. This is
// the one place the window holds them, and only while the Ledger page is open:
// it works out no bound, neighbour, bucket or name of its own, so what has not
// been served is unknown and every answer says so with null, never with a
// guessed period.
//
// A caller names what it needs with `usePeriods`; the page's reader asks the
// backend for what is missing, once, and the caller draws again when it comes.
// A read that fails stays unknown until the page is opened again.

import { useEffect, useRef, useSyncExternalStore } from "react";
import type { LedgerPort, PublicPeriod } from "./ledger";
import { isPeriodCode, parseIsoDate, type LedgerPeriod } from "./ledgerGrammar";
import type {
  LedgerEntryOptionsRequest,
  LedgerServedDay,
  LedgerServedPeriod,
  LedgerServedPeriods,
} from "./ledgerSetup";
import { readAnswer } from "./ledgerWindow";

type OutputLanguage = NonNullable<LedgerEntryOptionsRequest["output_language"]>;
type Query = NonNullable<LedgerEntryOptionsRequest["periods"]>;

/** The most days one read may ask the periods of. */
const DAYS_PER_READ = 64;

/** What a caller needs served. */
export type PeriodWants = {
  years?: readonly number[];
  days?: readonly string[];
  spans?: readonly { from: string; to: string }[];
};

/** Asks the backend for periods in one language. Null where it could not. */
type Ask = (query: Query) => Promise<LedgerServedPeriods | null>;

type Held = {
  language: OutputLanguage | null;
  annualCode: string | null;
  today: LedgerServedDay | null;
  years: ReadonlyMap<number, readonly LedgerServedPeriod[]>;
  days: ReadonlyMap<string, LedgerServedDay>;
  covers: ReadonlyMap<string, PublicPeriod | null>;
};

const EMPTY: Held = {
  language: null,
  annualCode: null,
  today: null,
  years: new Map(),
  days: new Map(),
  covers: new Map(),
};

let held: Held = EMPTY;
let version = 0;
let reader: { language: OutputLanguage; ask: Ask } | null = null;
// Whether the entry options read, which serves today's periods with the
// vocabularies, came back unanswered.
let todayFailed = false;
// What was asked since the reader was registered, answered or not.
let asked = new Set<string>();
let epoch = 0;
const listeners = new Set<() => void>();

function changed(next: Held): void {
  held = next;
  version += 1;
  for (const listener of listeners) listener();
}

const spanKey = (from: string, to: string) => `${from}/${to}`;

function merge(language: OutputLanguage, served: LedgerServedPeriods): void {
  if (held.language !== null && held.language !== language) return;
  const years = new Map(held.years);
  years.set(served.year, served.periods);
  const days = new Map(held.days);
  for (const day of served.days ?? []) days.set(day.day, day);
  const covers = new Map(held.covers);
  if (served.covering)
    covers.set(
      spanKey(served.covering.first_day, served.covering.last_day),
      served.covering.period,
    );
  changed({
    language,
    annualCode: served.annual_code,
    today: held.today ?? served.containing,
    years,
    days,
    covers,
  });
}

/** Holds periods served elsewhere: the answer of a read the page made, or a
 * recording. Null drops everything held. */
export function holdLedgerPeriods(
  language: OutputLanguage | null,
  served: LedgerServedPeriods | null,
): void {
  if (served === null || language === null) {
    asked = new Set();
    epoch += 1;
    if (held !== EMPTY) changed(EMPTY);
    return;
  }
  if (held.language !== null && held.language !== language) {
    asked = new Set();
    epoch += 1;
    changed(EMPTY);
  }
  merge(language, served);
}

/** Records that the read which serves today's periods came back unanswered,
 * or that it has not. */
export function holdLedgerPeriodsUnread(unread: boolean): void {
  if (todayFailed === unread) return;
  todayFailed = unread;
  changed(held);
}

/** Registers how periods are read, in the language the window shows; null
 * unregisters. A new reader or language drops what was held, whose words are
 * another's. */
export function registerPeriodsReader(
  language: OutputLanguage | null,
  ask: Ask | null,
): void {
  const next = language !== null && ask !== null ? { language, ask } : null;
  if (reader === next) return;
  reader = next;
  asked = new Set();
  epoch += 1;
  todayFailed = false;
  changed(EMPTY);
}

function read(query: Query, key: string): void {
  const current = reader;
  if (current === null || asked.has(key)) return;
  asked.add(key);
  const mine = epoch;
  void current
    .ask(query)
    .catch(() => null)
    .then((served) => {
      if (mine !== epoch) return;
      if (served === null) return;
      merge(current.language, served);
      // A day names periods whose own years are wanted to say their words.
      if (query.days)
        wantPeriods({
          years: (served.days ?? []).flatMap((day) => [
            day.annual.filing_year,
            day.quarterly.filing_year,
            day.monthly.filing_year,
          ]),
        });
    });
}

/** Asks for whatever of `wants` is not held or already asked. */
export function wantPeriods(wants: PeriodWants): void {
  if (reader === null) return;
  for (const year of new Set(wants.years ?? []))
    if (!held.years.has(year)) read({ year }, `year:${year}`);
  // Only a day that is one on the calendar is asked about: the backend
  // refuses a whole read for a day it cannot read.
  const days = [...new Set(wants.days ?? [])].filter(
    (day) =>
      parseIsoDate(day).kind === "value" &&
      !held.days.has(day) &&
      !asked.has(`day:${day}`),
  );
  for (let at = 0; at < days.length; at += DAYS_PER_READ) {
    const chunk = days.slice(at, at + DAYS_PER_READ);
    for (const day of chunk) asked.add(`day:${day}`);
    read({ days: chunk }, `days:${chunk.join(",")}`);
  }
  for (const { from, to } of wants.spans ?? [])
    if (!held.covers.has(spanKey(from, to)))
      read(
        { covering: { first_day: from, last_day: to } },
        `span:${spanKey(from, to)}`,
      );
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Reads periods through `port` for as long as the page is open for `reader`,
 * in the language the window shows. */
export function useLedgerPeriodsReader(
  port: LedgerPort | undefined,
  who: string | null,
  language: string,
): void {
  useEffect(() => {
    if (port === undefined || who === null) return;
    const said = language as OutputLanguage;
    registerPeriodsReader(said, async (periods) => {
      const answer = readAnswer(
        await port.submit("ledger.entry-options", {
          output_language: said,
          periods,
        }),
      );
      return answer.kind === "answer" ? answer.result.periods : null;
    });
    return () => registerPeriodsReader(null, null);
  }, [port, who, language]);
}

/** Draws again as periods are served, and asks for what `wants` names that is
 * not held. */
export function usePeriods(wants: PeriodWants = {}): void {
  const served = useSyncExternalStore(subscribe, () => version);
  const latest = useRef(wants);
  latest.current = wants;
  const key = JSON.stringify([
    wants.years ?? [],
    wants.days ?? [],
    wants.spans ?? [],
  ]);
  useEffect(() => {
    wantPeriods(latest.current);
  }, [key, served]);
}

// ---- What is held ----------------------------------------------------------

/** The language the held words are said in, or null while none are held. */
export const periodsLanguage = (): string | null => held.language;

/** The code that names the whole year, or null while it is not served. */
export const annualCode = (): string | null => held.annualCode;

/** A served period as the window holds one, or null where the code is not
 * one the window can hold. */
export function ledgerPeriod(period: PublicPeriod | null): LedgerPeriod | null {
  return period !== null && isPeriodCode(period.code)
    ? { year: period.filing_year, code: period.code }
    : null;
}

/** The periods of `year`, in the order served, or null while not served. */
export const servedYear = (
  year: number,
): readonly LedgerServedPeriod[] | null => held.years.get(year) ?? null;

/** The served row of `period`, or null while its year is not served or the
 * year holds no such period. */
export const servedPeriod = (period: LedgerPeriod): LedgerServedPeriod | null =>
  servedYear(period.year)?.find((row) => row.period.code === period.code) ??
  null;

/** The whole year as a period, or null while the code that names it is not
 * served. */
export function annualPeriod(year: number): LedgerPeriod | null {
  const code = held.annualCode;
  return code !== null && isPeriodCode(code) ? { year, code } : null;
}

/** The first and last day of a period, or null while it is not served. */
export function periodBounds(
  period: LedgerPeriod,
): { from: string; to: string } | null {
  const row = servedPeriod(period);
  return row ? { from: row.first_day, to: row.last_day } : null;
}

/** The period `by` steps (-1 or 1) away across year ends, as the period
 * serves its neighbours. Null where the period is not served or has none. */
export function neighbourPeriod(
  period: LedgerPeriod,
  by: -1 | 1,
): LedgerPeriod | null {
  const row = servedPeriod(period);
  return row ? ledgerPeriod(by < 0 ? row.previous : row.next) : null;
}

/** A period's name on its own and with its year, in the language the window
 * shows, or null while they are not served in that language. */
export function periodWords(
  period: LedgerPeriod,
  language: string,
): { name: string; label: string } | null {
  const row = servedPeriod(period);
  if (
    row === null ||
    row.name_words_language !== language ||
    row.label_words_language !== language
  )
    return null;
  return { name: row.name_words, label: row.label_words };
}

export type Holding = {
  annual: LedgerPeriod;
  quarterly: LedgerPeriod;
  monthly: LedgerPeriod;
};

function holding(served: LedgerServedDay | null | undefined): Holding | null {
  if (!served) return null;
  const annual = ledgerPeriod(served.annual);
  const quarterly = ledgerPeriod(served.quarterly);
  const monthly = ledgerPeriod(served.monthly);
  return annual && quarterly && monthly ? { annual, quarterly, monthly } : null;
}

/** The year, quarter and month that hold a day, or null while not served. */
export const periodsHolding = (day: string): Holding | null =>
  holding(held.days.get(day));

/** Whether today's periods were asked for and could not be read, so that
 * nothing says what today's quarter is and nothing will. */
export const periodsHoldingTodayFailed = (): boolean =>
  todayFailed && held.today === null;

/** The periods that hold today in Spain, or null while not served. */
export const periodsHoldingToday = (): Holding | null => holding(held.today);

/** The shortest period that holds every day of a span: `{ period }` for the
 * one served, with a null period where none holds it (a span that crosses a
 * year end), or null while it is not served. */
export function periodHoldingSpan(span: {
  from: string;
  to: string;
}): { period: LedgerPeriod | null } | null {
  const key = spanKey(span.from, span.to);
  if (!held.covers.has(key)) return null;
  return { period: ledgerPeriod(held.covers.get(key) ?? null) };
}

/** Reads the period that holds a span now, for a caller that acts on it and
 * not on a draw. Null where it could not be read. */
export async function readPeriodHoldingSpan(span: {
  from: string;
  to: string;
}): Promise<{ period: LedgerPeriod | null } | null> {
  const current = reader;
  if (current === null) return null;
  const served = periodHoldingSpan(span);
  if (served !== null) return served;
  const answer = await current
    .ask({ covering: { first_day: span.from, last_day: span.to } })
    .catch(() => null);
  if (answer === null || reader !== current) return null;
  merge(current.language, answer);
  return periodHoldingSpan(span);
}

/** Reads the periods that hold a day now, for a caller that acts on them and
 * not on a draw. Null where they could not be read. */
export async function readPeriodsHolding(day: string): Promise<Holding | null> {
  const current = reader;
  if (current === null) return null;
  const served = periodsHolding(day);
  if (served !== null) return served;
  const answer = await current.ask({ days: [day] }).catch(() => null);
  if (answer === null || reader !== current) return null;
  merge(current.language, answer);
  return periodsHolding(day);
}
