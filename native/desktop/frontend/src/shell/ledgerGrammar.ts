// The one grammar every ledger value the person types or pastes goes
// through, before it is staged. It follows the product's own: a dot decimal
// with no grouping, no exponent and no sign, refused rather than guessed when
// it could be read two ways. A refusal is a key and the raw text, never a
// sentence: the page says it in the person's language. How the text is written
// is judged here; every limit on what it may say is served by the backend, and
// with none served a typed value is refused as not yet checkable.

import type { PublicPeriod } from "./ledger";
import { ledgerLimits } from "./ledgerLimits";
import type { LedgerEntryLimits } from "./ledgerSetup";

/** The canonical stored-movement handle grammar, including valid prefixes. */
export function isTransactionPrefix(id: string): boolean {
  return /^[0-9a-f]{1,64}$/.test(id);
}

export type GrammarRefusalKey =
  | "limits_unavailable"
  | "too_long"
  | "signed"
  | "exponent"
  | "currency_symbol"
  | "comma_decimal"
  | "grouping"
  | "ambiguous_grouping"
  | "too_many_decimals"
  | "zero"
  | "not_a_number"
  | "percent_as_fraction"
  | "percent_above_100"
  | "date_not_iso"
  | "date_not_in_calendar"
  | "not_a_date"
  | "year_not_a_number"
  | "line_break"
  | "not_an_iban"
  | "not_a_bic"
  | "not_a_country"
  | "not_a_currency";

/** Why a typed value was refused. `suggestion` is the canonical text the
 * person most likely meant, where one reading is certain; `limit` is the
 * bound that was crossed. */
export type GrammarRefusal = {
  key: GrammarRefusalKey;
  raw: string;
  suggestion?: string;
  limit?: number;
};

/** A typed cell: a canonical value, nothing typed, or a refusal. Nothing
 * typed is not a clear: only an explicit clear removes a stored value. */
export type Parsed<T> =
  | { kind: "value"; value: T }
  | { kind: "empty" }
  | { kind: "refused"; refusal: GrammarRefusal };

const refuse = <T>(
  key: GrammarRefusalKey,
  raw: string,
  extra: { suggestion?: string; limit?: number } = {},
): Parsed<T> => ({ kind: "refused", refusal: { key, raw, ...extra } });
const value = <T>(found: T): Parsed<T> => ({ kind: "value", value: found });

const PLAIN = /^\d+(\.\d+)?$/;

// ---- Exact decimal arithmetic over canonical text ------------------------

type Exact = { units: bigint; scale: number };
function exact(text: string): Exact | null {
  const found = /^(-?)(\d+)(?:\.(\d+))?$/.exec(text.trim());
  if (!found) return null;
  const fraction = found[3] ?? "";
  const units = BigInt(`${found[2]}${fraction}`);
  return { units: found[1] ? -units : units, scale: fraction.length };
}
function scaled(number: Exact, scale: number): bigint {
  return number.units * 10n ** BigInt(scale - number.scale);
}
function textOf(number: Exact): string {
  if (number.units === 0n) return "0";
  const negative = number.units < 0n;
  let digits = (negative ? -number.units : number.units).toString();
  let scale = number.scale;
  while (scale > 0 && digits.endsWith("0")) {
    digits = digits.slice(0, -1);
    scale -= 1;
  }
  digits = digits.padStart(scale + 1, "0");
  const whole = digits.slice(0, digits.length - scale);
  const fraction = digits.slice(digits.length - scale);
  const text = fraction ? `${whole}.${fraction}` : whole;
  return negative && text !== "0" ? `-${text}` : text;
}

/** Decimal text in the product's canonical spelling: no leading zeros, no
 * trailing fraction zeros, so `12.50` is `12.5` and `100.00` is `100`. The
 * single-row writes refuse any other spelling of the same number. */
export function canonicalDecimal(text: string): string | null {
  const number = exact(text);
  return number ? textOf(number) : null;
}

/** Whether two decimal texts name the same number, however spelled. */
export function sameDecimal(left: string, right: string): boolean {
  const a = exact(left);
  const b = exact(right);
  if (!a || !b) return false;
  const scale = Math.max(a.scale, b.scale);
  return scaled(a, scale) === scaled(b, scale);
}

/** Compares two decimal texts: negative, zero or positive. */
export function compareDecimal(left: string, right: string): number {
  const a = exact(left);
  const b = exact(right);
  if (!a || !b) return Number.NaN;
  const scale = Math.max(a.scale, b.scale);
  const difference = scaled(a, scale) - scaled(b, scale);
  return difference < 0n ? -1 : difference > 0n ? 1 : 0;
}

/** `text` times ten to the `places`, in canonical spelling. */
export function shiftDecimal(text: string, places: number): string | null {
  const number = exact(text);
  if (!number) return null;
  return places >= 0
    ? textOf({
        units: number.units * 10n ** BigInt(places),
        scale: number.scale,
      })
    : textOf({ units: number.units, scale: number.scale - places });
}

// ---- Numbers --------------------------------------------------------------

/** A kind of figure the backend serves a rule for, or a rule served by a field
 * itself: how many fraction digits it takes and whether zero is a value. */
export type DecimalRule =
  | LedgerEntryLimits["decimal_rules"][number]["rule"]
  | typeof PERCENT_POINTS_RULE
  | { decimals: number; zero: boolean };
/** A movement's amount. */
export const AMOUNT_RULE = "amount";
/** A taxable base, an IVA or recargo amount. */
export const TAX_AMOUNT_RULE = "tax_amount";
/** An invoice line's quantity. */
export const QUANTITY_RULE = "quantity";
/** An invoice line's unit price. */
export const UNIT_PRICE_RULE = "unit_price";
/** A percentage in points: its served decimals, and zero is a value. */
export const PERCENT_POINTS_RULE = "percent_points";

function ruleOf(
  rule: DecimalRule,
  limits: LedgerEntryLimits,
): { decimals: number; zero: boolean } | null {
  if (typeof rule !== "string") return rule;
  if (rule === PERCENT_POINTS_RULE)
    return { decimals: limits.percent_decimals, zero: true };
  return limits.decimal_rules.find((found) => found.rule === rule) ?? null;
}

/** Whether plain text has the shape the backend reads two ways. */
const twoWay = (limits: LedgerEntryLimits, text: string) =>
  new RegExp(limits.two_way_decimal).test(text);

/** Why text that is not a plain decimal was refused, and what it most
 * likely meant where one reading is certain. */
function shapeRefusal(text: string, raw: string): Parsed<string> {
  if (/^[+\-\u2212]/.test(text)) {
    const rest = text.slice(1).trim();
    return refuse(
      "signed",
      raw,
      PLAIN.test(rest) ? { suggestion: canonicalDecimal(rest)! } : {},
    );
  }
  if (/[€$£]|\beur\b|\beuros?\b/i.test(text))
    return refuse("currency_symbol", raw);
  if (/^\d+(\.\d+)?e[+-]?\d+$/i.test(text)) return refuse("exponent", raw);
  // `1,000` is a thousand in English and one in Spanish.
  if (/^[1-9]\d{0,2}(,\d{3})+$/.test(text) && !/^\d+,\d{3}$/.test(text))
    return refuse("grouping", raw, { suggestion: text.replace(/,/g, "") });
  if (/^[1-9]\d{0,2},\d{3}$/.test(text))
    return refuse("ambiguous_grouping", raw);
  if (/^\d+,\d+$/.test(text))
    return refuse("comma_decimal", raw, {
      suggestion: text.replace(",", "."),
    });
  if (/^[1-9]\d{0,2}(,\d{3})+\.\d+$/.test(text))
    return refuse("grouping", raw, { suggestion: text.replace(/,/g, "") });
  if (/^[1-9]\d{0,2}(\.\d{3})+,\d+$/.test(text))
    return refuse("grouping", raw, {
      suggestion: text.replace(/\./g, "").replace(",", "."),
    });
  if (/^[1-9]\d{0,2}(\.\d{3}){2,}$/.test(text))
    return refuse("grouping", raw, { suggestion: text.replace(/\./g, "") });
  if (/^[1-9]\d{0,2}([ \u00a0]\d{3})+(\.\d+)?$/.test(text))
    return refuse("grouping", raw, {
      suggestion: text.replace(/[ \u00a0]/g, ""),
    });
  if (/^\.\d+$/.test(text))
    return refuse("not_a_number", raw, {
      suggestion: canonicalDecimal(`0${text}`)!,
    });
  if (/^\d+\.$/.test(text))
    return refuse("not_a_number", raw, {
      suggestion: canonicalDecimal(text.slice(0, -1))!,
    });
  return refuse("not_a_number", raw);
}

/** A decimal in the canonical grammar, as its canonical text. */
export function parseDecimal(raw: string, asked: DecimalRule): Parsed<string> {
  const text = raw.trim();
  if (text === "") return { kind: "empty" };
  const limits = ledgerLimits();
  const rule = limits && ruleOf(asked, limits);
  if (!limits || !rule) return refuse("limits_unavailable", raw);
  if (text.length > limits.decimal_text_max)
    return refuse("too_long", raw, { limit: limits.decimal_text_max });
  if (!PLAIN.test(text)) return shapeRefusal(text, raw);
  if (twoWay(limits, text)) return refuse("ambiguous_grouping", raw);
  const decimals = text.split(".")[1]?.length ?? 0;
  if (decimals > rule.decimals)
    return refuse("too_many_decimals", raw, { limit: rule.decimals });
  const canonical = canonicalDecimal(text)!;
  if (!rule.zero && canonical === "0") return refuse("zero", raw);
  return value(canonical);
}

export const parseAmount = (raw: string) => parseDecimal(raw, AMOUNT_RULE);

/**
 * One grammar for every percentage: an IVA rate, a business share, a usage
 * ratio, a retención. `50` and `50%` mean fifty per cent, typed or pasted.
 * A bare number between zero and one is refused, because `0.5` may be the
 * fraction the product stores or half a per cent. The value is the fraction
 * the wire carries, in canonical spelling: `21` is `0.21`.
 */
export function parsePercent(raw: string): Parsed<string> {
  let text = raw.trim();
  const explicit = /\s*%$/.test(text);
  if (explicit) text = text.replace(/\s*%$/, "");
  if (text === "")
    return explicit ? refuse("not_a_number", raw) : { kind: "empty" };
  const limits = ledgerLimits();
  if (!limits) return refuse("limits_unavailable", raw);
  if (text.length > limits.decimal_text_max)
    return refuse("too_long", raw, { limit: limits.decimal_text_max });
  if (!PLAIN.test(text)) {
    if (/^\d+,\d+$/.test(text))
      return refuse("comma_decimal", raw, {
        suggestion: text.replace(",", "."),
      });
    return shapeRefusal(text, raw);
  }
  const decimals = text.split(".")[1]?.length ?? 0;
  if (decimals > limits.percent_decimals)
    return refuse("too_many_decimals", raw, { limit: limits.percent_decimals });
  if (compareDecimal(text, limits.percent_points_max) > 0)
    return refuse("percent_above_100", raw);
  if (
    !explicit &&
    compareDecimal(text, "0") > 0 &&
    compareDecimal(text, limits.percent_bare_fraction_ceiling) < 0
  )
    return refuse("percent_as_fraction", raw, {
      suggestion: shiftDecimal(text, 2)!,
    });
  return value(shiftDecimal(text, -2)!);
}

/** What a percent editor holds with a fraction as its unit: `0.21` is 21%, and
 * the value is that fraction in canonical spelling. Text the editor could not
 * read arrives as typed and is refused here for what it is. */
export function parseFractionPercent(raw: string): Parsed<string> {
  const text = raw.trim();
  if (text === "") return { kind: "empty" };
  const limits = ledgerLimits();
  if (!limits) return refuse("limits_unavailable", raw);
  if (twoWay(limits, text.replace(/^-/, "")))
    return refuse("ambiguous_grouping", raw);
  if (!PLAIN.test(text)) return parsePercent(raw);
  const canonical = canonicalDecimal(text)!;
  if ((canonical.split(".")[1]?.length ?? 0) > limits.percent_decimals + 2)
    return refuse("too_many_decimals", raw, { limit: limits.percent_decimals });
  if (compareDecimal(canonical, limits.percent_fraction_max) > 0)
    return refuse("percent_above_100", raw);
  return value(canonical);
}

/** The percentage a stored fraction names, without the sign: `0.21` is
 * `21`. Null for text that is not a decimal. */
export function percentOf(fraction: string): string | null {
  return shiftDecimal(fraction, 2);
}

/** What copying a fraction puts on the clipboard: `50%`, which pastes back
 * as the same value. */
export function copyPercent(fraction: string | null): string {
  const percent = fraction === null ? null : percentOf(fraction);
  return percent === null ? "" : `${percent}%`;
}

/** What copying an amount puts on the clipboard: canonical, to the cent. */
export function copyAmount(amount: string | null): string {
  const number = amount === null ? null : exact(amount);
  if (!number) return "";
  const cents = number.scale > 2 ? null : scaled(number, 2);
  if (cents === null) return textOf(number);
  const negative = cents < 0n;
  const digits = (negative ? -cents : cents).toString().padStart(3, "0");
  return `${negative ? "-" : ""}${digits.slice(0, -2)}.${digits.slice(-2)}`;
}

/** What copying any other decimal puts on the clipboard. */
export function copyDecimal(text: string | null): string {
  return text === null ? "" : (canonicalDecimal(text) ?? "");
}

// ---- Dates -----------------------------------------------------------------

const pad = (number: number, width = 2) => String(number).padStart(width, "0");
function calendarDay(year: number, month: number, day: number): string | null {
  if (year < 1 || month < 1 || month > 12 || day < 1) return null;
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  return date.getUTCMonth() === month - 1 && date.getUTCDate() === day
    ? `${pad(year, 4)}-${pad(month)}-${pad(day)}`
    : null;
}

/** A calendar day written year-month-day. Day-first dates, the Spanish
 * way, are refused with the ISO spelling of the same day. */
export function parseIsoDate(raw: string): Parsed<string> {
  const text = raw.trim();
  if (text === "") return { kind: "empty" };
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (iso) {
    const day = calendarDay(Number(iso[1]), Number(iso[2]), Number(iso[3]));
    return day ? value(day) : refuse("date_not_in_calendar", raw);
  }
  const loose = /^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/.exec(text);
  const dayFirst = /^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/.exec(text);
  const parts = loose
    ? [loose[1], loose[2], loose[3]]
    : dayFirst
      ? [dayFirst[3], dayFirst[2], dayFirst[1]]
      : null;
  if (parts) {
    const day = calendarDay(
      Number(parts[0]),
      Number(parts[1]),
      Number(parts[2]),
    );
    return day
      ? refuse("date_not_iso", raw, { suggestion: day })
      : refuse("date_not_in_calendar", raw);
  }
  return refuse("not_a_date", raw);
}

// ---- Single-line text -------------------------------------------------------

/** A one-line text such as a description or a counterparty. Tabs and line
 * breaks are refused rather than flattened. `max` is a limit the backend
 * served, or null where it has served none, which refuses what is typed as
 * not yet checkable; leave it out for a text with no bound. */
export function parseLine(raw: string, max?: number | null): Parsed<string> {
  if (/[\t\r\n]/.test(raw)) return refuse("line_break", raw);
  const text = raw.trim();
  if (text === "") return { kind: "empty" };
  if (max === null) return refuse("limits_unavailable", raw);
  if (max !== undefined && text.length > max)
    return refuse("too_long", raw, { limit: max });
  return value(text);
}

// ---- Periods ---------------------------------------------------------------

/** A filing period: the whole year, a quarter or a month of it. Which ones
 * exist, their days and their neighbours are served by the backend
 * (`./ledgerPeriods`); the window works none of them out. */
export type LedgerPeriod = { year: number; code: string };

/** Whether a number is written as a year is: four digits. Which years exist is
 * the registry's, and no limit on them is held here. */
export const yearAdmitted = (year: number) =>
  Number.isInteger(year) && String(year).length === 4 && year > 0;

/** A typed filing year. */
export function parseYear(raw: string): Parsed<number> {
  const text = raw.trim();
  if (text === "") return { kind: "empty" };
  const year = Number(text);
  return /^\d{4}$/.test(text) && yearAdmitted(year)
    ? value(year)
    : refuse("year_not_a_number", raw);
}

/** A year field's stepper: by one or by ten, staying put where the step would
 * leave a year that can be written. */
export function stepYear(year: number, by: number): number {
  return yearAdmitted(year + by) ? year + by : year;
}

/** The years of `year`'s decade that can be written. */
export function decadeYears(year: number): number[] {
  const first = Math.floor(year / 10) * 10;
  return Array.from({ length: 10 }, (_, at) => first + at).filter(yearAdmitted);
}

export const samePeriod = (
  left: LedgerPeriod | null,
  right: LedgerPeriod | null,
) =>
  left === right ||
  (left !== null &&
    right !== null &&
    left.year === right.year &&
    left.code === right.code);

/** The list filter clauses that select a period: the product takes the
 * token and its year as two clauses. */
export function periodFilters(period: LedgerPeriod): string[] {
  return [`period=${period.code}`, `year=${pad(period.year, 4)}`];
}

export function publicPeriod(period: LedgerPeriod): PublicPeriod {
  return { filing_year: period.year, code: period.code };
}
