import { expect, test } from "@playwright/test";
import {
  AMOUNT_RULE,
  canonicalDecimal,
  compareDecimal,
  copyAmount,
  copyPercent,
  decadeYears,
  LEDGER_YEAR_MAX,
  LEDGER_YEAR_MIN,
  parseAmount,
  parseDecimal,
  parseIsoDate,
  parseLine,
  parsePercent,
  parsePeriodCode,
  parseYear,
  periodFilters,
  periodOf,
  periodSpan,
  QUANTITY_RULE,
  sameDecimal,
  stepPeriod,
  stepYear,
  TAX_AMOUNT_RULE,
  UNIT_PRICE_RULE,
  type GrammarRefusalKey,
  type LedgerPeriod,
  type Parsed,
} from "../src/shell/ledgerGrammar";

// The ledger's input grammar at its boundaries. No page is opened.

type Expected = string | GrammarRefusalKey | null;
/** A value, a refusal key, or null for nothing typed. */
function verdict(parsed: Parsed<string | number>): Expected {
  if (parsed.kind === "empty") return null;
  if (parsed.kind === "refused") return parsed.refusal.key;
  return String(parsed.value);
}

test("amounts take a dot decimal to the cent and refuse every other shape", () => {
  const cases: [string, Expected][] = [
    ["36.30", "36.3"],
    ["1234.56", "1234.56"],
    ["1000", "1000"],
    ["007.50", "7.5"],
    ["  12.5 ", "12.5"],
    ["", null],
    ["   ", null],
    // A thousands dot and a decimal dot cannot be told apart.
    ["1.000", "ambiguous_grouping"],
    ["12.500", "ambiguous_grouping"],
    ["1,000", "ambiguous_grouping"],
    ["12,50", "comma_decimal"],
    ["1.234,56", "grouping"],
    ["1,234.56", "grouping"],
    ["1.234.567", "grouping"],
    ["1 000", "grouping"],
    ["1e3", "exponent"],
    ["2.5E-2", "exponent"],
    ["-5", "signed"],
    ["+5", "signed"],
    ["0", "zero"],
    ["0.00", "zero"],
    ["0.333", "too_many_decimals"],
    ["1000.000", "too_many_decimals"],
    ["12 €", "currency_symbol"],
    ["12 EUR", "currency_symbol"],
    [".5", "not_a_number"],
    ["5.", "not_a_number"],
    ["abc", "not_a_number"],
    ["9".repeat(129), "too_long"],
  ];
  for (const [raw, expected] of cases)
    expect(verdict(parseAmount(raw)), JSON.stringify(raw)).toBe(expected);
});

test("a refusal carries the raw text and the one reading that is certain", () => {
  const comma = parseAmount("12,50");
  expect(comma).toEqual({
    kind: "refused",
    refusal: { key: "comma_decimal", raw: "12,50", suggestion: "12.50" },
  });
  const signed = parseAmount("-5");
  expect(signed.kind === "refused" && signed.refusal.suggestion).toBe("5");
  const grouped = parseAmount("1.234,56");
  expect(grouped.kind === "refused" && grouped.refusal.suggestion).toBe(
    "1234.56",
  );
  // Ambiguity names no reading: either would be a guess.
  const ambiguous = parseAmount("1.000");
  expect(ambiguous.kind === "refused" && ambiguous.refusal.suggestion).toBe(
    undefined,
  );
  const decimals = parseAmount("0.333");
  expect(decimals.kind === "refused" && decimals.refusal.limit).toBe(2);
  // No refusal is a sentence: the page words it.
  for (const raw of ["12,50", "1e3", "-5", "0", "1.000"]) {
    const parsed = parseAmount(raw);
    expect(parsed.kind).toBe("refused");
    if (parsed.kind === "refused")
      for (const key of Object.keys(parsed.refusal))
        expect(["key", "raw", "suggestion", "limit"]).toContain(key);
  }
});

test("tax amounts allow zero, quantities and prices take six decimals", () => {
  expect(verdict(parseDecimal("0", TAX_AMOUNT_RULE))).toBe("0");
  expect(verdict(parseDecimal("0", AMOUNT_RULE))).toBe("zero");
  expect(verdict(parseDecimal("2.5", QUANTITY_RULE))).toBe("2.5");
  expect(verdict(parseDecimal("0.333333", QUANTITY_RULE))).toBe("0.333333");
  expect(verdict(parseDecimal("0.3333333", QUANTITY_RULE))).toBe(
    "too_many_decimals",
  );
  expect(verdict(parseDecimal("0", QUANTITY_RULE))).toBe("zero");
  expect(verdict(parseDecimal("2,5", QUANTITY_RULE))).toBe("comma_decimal");
  expect(verdict(parseDecimal("1e3", QUANTITY_RULE))).toBe("exponent");
  // The product refuses a three-decimal shape that could be grouped, at any
  // precision.
  expect(verdict(parseDecimal("1.500", QUANTITY_RULE))).toBe(
    "ambiguous_grouping",
  );
  expect(verdict(parseDecimal("0.125", UNIT_PRICE_RULE))).toBe("0.125");
  expect(verdict(parseDecimal("0", UNIT_PRICE_RULE))).toBe("0");
});

test("one percent grammar: 50 is fifty per cent and a bare fraction is refused", () => {
  const cases: [string, Expected][] = [
    ["50", "0.5"],
    ["50%", "0.5"],
    ["50 %", "0.5"],
    ["21", "0.21"],
    ["7.5", "0.075"],
    ["5.2", "0.052"],
    ["1.75", "0.0175"],
    ["100", "1"],
    ["0", "0"],
    ["1", "0.01"],
    // Typed with its sign, half a per cent is what was meant.
    ["0.5%", "0.005"],
    ["0.21", "percent_as_fraction"],
    ["0.5", "percent_as_fraction"],
    ["101", "percent_above_100"],
    ["12,5", "comma_decimal"],
    ["-21", "signed"],
    ["1e1", "exponent"],
    ["12.34567", "too_many_decimals"],
    ["%", "not_a_number"],
    ["", null],
  ];
  for (const [raw, expected] of cases)
    expect(verdict(parsePercent(raw)), JSON.stringify(raw)).toBe(expected);
  const fraction = parsePercent("0.21");
  expect(fraction.kind === "refused" && fraction.refusal.suggestion).toBe("21");
});

test("copying writes canonical values that paste back to the same value", () => {
  expect(copyPercent("0.5")).toBe("50%");
  expect(copyPercent("0.21")).toBe("21%");
  expect(copyPercent("0.0175")).toBe("1.75%");
  expect(copyPercent(null)).toBe("");
  expect(copyAmount("36.3")).toBe("36.30");
  expect(copyAmount("0.05")).toBe("0.05");
  expect(copyAmount("1000")).toBe("1000.00");
  for (const fraction of ["0.5", "0.21", "0.075", "1", "0"]) {
    const pasted = parsePercent(copyPercent(fraction));
    expect(pasted).toEqual({ kind: "value", value: fraction });
  }
  for (const amount of ["36.3", "0.05", "1234.5"]) {
    const pasted = parseAmount(copyAmount(amount));
    expect(pasted).toEqual({ kind: "value", value: amount });
  }
});

test("decimal text compares by value, whatever its spelling", () => {
  expect(canonicalDecimal("12.50")).toBe("12.5");
  expect(canonicalDecimal("100.00")).toBe("100");
  expect(canonicalDecimal("0.000")).toBe("0");
  expect(sameDecimal("12.50", "12.5")).toBe(true);
  expect(sameDecimal("0.60", "0.6")).toBe(true);
  expect(sameDecimal("12.51", "12.5")).toBe(false);
  expect(compareDecimal("100.5", "100.49")).toBe(1);
  expect(compareDecimal("0.1", "0.10")).toBe(0);
});

test("dates are calendar days written year-month-day", () => {
  const cases: [string, Expected][] = [
    ["2026-10-21", "2026-10-21"],
    ["2024-02-29", "2024-02-29"],
    ["2026-02-29", "date_not_in_calendar"],
    ["2026-13-01", "date_not_in_calendar"],
    ["21/10/2026", "date_not_iso"],
    ["2026-1-5", "date_not_iso"],
    ["2026/10/21", "date_not_iso"],
    ["31/02/2026", "date_not_in_calendar"],
    ["yesterday", "not_a_date"],
    ["", null],
  ];
  for (const [raw, expected] of cases)
    expect(verdict(parseIsoDate(raw)), raw).toBe(expected);
  // Day first, the Spanish way, gets the same day back in ISO.
  const spanish = parseIsoDate("21/10/2026");
  expect(spanish.kind === "refused" && spanish.refusal.suggestion).toBe(
    "2026-10-21",
  );
  const loose = parseIsoDate("2026-1-5");
  expect(loose.kind === "refused" && loose.refusal.suggestion).toBe(
    "2026-01-05",
  );
});

test("one-line text refuses tabs and line breaks rather than flattening them", () => {
  expect(verdict(parseLine("  Papelería Trazo  ", 64))).toBe("Papelería Trazo");
  expect(verdict(parseLine("a\tb", 64))).toBe("line_break");
  expect(verdict(parseLine("a\nb", 64))).toBe("line_break");
  expect(verdict(parseLine("x".repeat(65), 64))).toBe("too_long");
  expect(verdict(parseLine("   ", 64))).toBe(null);
});

test("years run from 1980 to 2200 and period tokens are the product's", () => {
  const years: [string, Expected][] = [
    ["2026", "2026"],
    ["1980", "1980"],
    ["2200", "2200"],
    ["1979", "year_out_of_range"],
    ["2201", "year_out_of_range"],
    ["26", "year_not_a_number"],
    ["twenty", "year_not_a_number"],
  ];
  for (const [raw, expected] of years)
    expect(verdict(parseYear(raw)), raw).toBe(expected);
  const codes: [string, Expected][] = [
    ["0A", "0A"],
    ["0a", "0A"],
    ["3T", "3T"],
    ["01", "01"],
    ["1", "01"],
    ["12", "12"],
    ["5T", "period_unknown"],
    ["13", "period_unknown"],
    ["Q1", "period_unknown"],
    ["2026-1T", "period_unknown"],
  ];
  for (const [raw, expected] of codes)
    expect(verdict(parsePeriodCode(raw)), raw).toBe(expected);
});

test("stepping a period crosses year ends by its own size", () => {
  const at = (year: number, code: LedgerPeriod["code"]): LedgerPeriod => ({
    year,
    code,
  });
  expect(stepPeriod(at(2026, "1T"), -1)).toEqual(at(2025, "4T"));
  expect(stepPeriod(at(2025, "4T"), 1)).toEqual(at(2026, "1T"));
  expect(stepPeriod(at(2026, "01"), -1)).toEqual(at(2025, "12"));
  expect(stepPeriod(at(2025, "12"), 1)).toEqual(at(2026, "01"));
  expect(stepPeriod(at(2026, "0A"), -1)).toEqual(at(2025, "0A"));
  // Across a decade and more than one year at once.
  expect(stepPeriod(at(2020, "1T"), -1)).toEqual(at(2019, "4T"));
  expect(stepPeriod(at(2019, "3T"), 6)).toEqual(at(2021, "1T"));
  expect(stepPeriod(at(2003, "02"), -14)).toEqual(at(2001, "12"));
  // Nothing before 1980 or after 2200.
  expect(stepPeriod(at(1980, "1T"), -1)).toBeNull();
  expect(stepPeriod(at(1980, "01"), -1)).toBeNull();
  expect(stepPeriod(at(2200, "4T"), 1)).toBeNull();
  expect(stepPeriod(at(2200, "0A"), 1)).toBeNull();
  expect(stepPeriod(at(1981, "1T"), -4)).toEqual(at(1980, "1T"));
});

test("the year field steps by one and by ten within the admitted years", () => {
  expect(stepYear(2026, 1)).toBe(2027);
  expect(stepYear(2026, -10)).toBe(2016);
  expect(stepYear(1985, -10)).toBe(LEDGER_YEAR_MIN);
  expect(stepYear(2195, 10)).toBe(LEDGER_YEAR_MAX);
  expect(decadeYears(2026)).toEqual([
    2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028, 2029,
  ]);
  expect(decadeYears(2003)[0]).toBe(2000);
  expect(decadeYears(2200)).toEqual([2200]);
  expect(decadeYears(1985)).toEqual([
    1980, 1981, 1982, 1983, 1984, 1985, 1986, 1987, 1988, 1989,
  ]);
});

test("a period's span, the period a day falls in, and its list clauses", () => {
  expect(periodSpan({ year: 2026, code: "1T" })).toEqual({
    from: "2026-01-01",
    to: "2026-03-31",
  });
  expect(periodSpan({ year: 2024, code: "02" })).toEqual({
    from: "2024-02-01",
    to: "2024-02-29",
  });
  expect(periodSpan({ year: 2025, code: "02" })).toEqual({
    from: "2025-02-01",
    to: "2025-02-28",
  });
  expect(periodSpan({ year: 2026, code: "4T" })).toEqual({
    from: "2026-10-01",
    to: "2026-12-31",
  });
  expect(periodSpan({ year: 2003, code: "0A" })).toEqual({
    from: "2003-01-01",
    to: "2003-12-31",
  });
  expect(periodOf("2026-07-01", "quarter")).toEqual({ year: 2026, code: "3T" });
  expect(periodOf("2026-07-01", "month")).toEqual({ year: 2026, code: "07" });
  expect(periodOf("1975-07-01", "year")).toBeNull();
  expect(periodFilters({ year: 2026, code: "3T" })).toEqual([
    "period=3T",
    "year=2026",
  ]);
});
