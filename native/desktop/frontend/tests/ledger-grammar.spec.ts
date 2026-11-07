import { servedLimits } from "./support/servedLimits";
import { holdLedgerLimits, textLimit } from "../src/shell/ledgerLimits";
import recorded from "@fixtures/ledger-entry-options/ledgerEntryOptions.json" with { type: "json" };
import { answerPeriods, holdRecordedPeriods } from "../src/dev/periodRecording";
import {
  holdLedgerPeriods,
  ledgerPeriod,
  neighbourPeriod,
  periodBounds,
  periodHoldingSpan,
  periodsHolding,
  periodWords,
  servedYear,
} from "../src/shell/ledgerPeriods";
import { expect, test } from "@playwright/test";
import {
  AMOUNT_RULE,
  canonicalDecimal,
  compareDecimal,
  copyAmount,
  copyPercent,
  decadeYears,
  parseAmount,
  parseDecimal,
  parseFractionPercent,
  parseIsoDate,
  parseLine,
  parsePercent,
  parseYear,
  periodFilters,
  QUANTITY_RULE,
  sameDecimal,
  stepYear,
  TAX_AMOUNT_RULE,
  UNIT_PRICE_RULE,
  type GrammarRefusalKey,
  type Parsed,
} from "../src/shell/ledgerGrammar";
import { label } from "./support/strings";
import {
  servedSupport,
  servedYearBounds,
} from "../src/dev/servedYearAuthority";
import { fixtureDay, fixtureYear } from "../src/dev/fixtureDates";

// The ledger's input grammar at its boundaries. No page is opened.

/** The first year from the fixtures' own on that has, or lacks, a 29th of February. */
const yearWithFebruary29 = (leap: boolean): number => {
  let year = fixtureYear;
  while ((new Date(Date.UTC(year, 1, 29)).getUTCMonth() === 1) !== leap)
    year += 1;
  return year;
};
const LEAP_YEAR = yearWithFebruary29(true);
const COMMON_YEAR = yearWithFebruary29(false);

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
    [fixtureDay(10, 21), fixtureDay(10, 21)],
    [`${LEAP_YEAR}-02-29`, `${LEAP_YEAR}-02-29`],
    [`${COMMON_YEAR}-02-29`, "date_not_in_calendar"],
    [`${fixtureYear}-13-01`, "date_not_in_calendar"],
    [`21/10/${fixtureYear}`, "date_not_iso"],
    [`${fixtureYear}-1-5`, "date_not_iso"],
    [`${fixtureYear}/10/21`, "date_not_iso"],
    [`31/02/${fixtureYear}`, "date_not_in_calendar"],
    ["yesterday", "not_a_date"],
    ["", null],
  ];
  for (const [raw, expected] of cases)
    expect(verdict(parseIsoDate(raw)), raw).toBe(expected);
  // Day first, the Spanish way, gets the same day back in ISO.
  const spanish = parseIsoDate(`21/10/${fixtureYear}`);
  expect(spanish.kind === "refused" && spanish.refusal.suggestion).toBe(
    fixtureDay(10, 21),
  );
  const loose = parseIsoDate(`${fixtureYear}-1-5`);
  expect(loose.kind === "refused" && loose.refusal.suggestion).toBe(
    fixtureDay(1, 5),
  );
});

test("one-line text refuses tabs and line breaks rather than flattening them", () => {
  expect(verdict(parseLine("  Papelería Trazo  ", 64))).toBe("Papelería Trazo");
  expect(verdict(parseLine("a\tb", 64))).toBe("line_break");
  expect(verdict(parseLine("a\nb", 64))).toBe("line_break");
  expect(verdict(parseLine("x".repeat(65), 64))).toBe("too_long");
  expect(verdict(parseLine("   ", 64))).toBe(null);
});

test("one-line text is held to the limit it is handed, and refused while none is served", () => {
  expect(verdict(parseLine("x".repeat(65), null))).toBe("limits_unavailable");
  expect(verdict(parseLine("  ", null))).toBe(null);
  // Left out, the text has no bound of its own.
  expect(verdict(parseLine("x".repeat(5000)))).toBe("x".repeat(5000));
});

test("a text limit is the one served, and none is assumed", () => {
  const served = (name: string) =>
    servedLimits.text_limits.find((found) => found.name === name)?.max;
  expect(textLimit("split_parts")).toBe(served("split_parts"));
  expect(textLimit("evidence_note")).toBe(served("evidence_note"));
  holdLedgerLimits({
    ...servedLimits,
    text_limits: [{ name: "split_parts", max: 3 }],
  });
  try {
    expect(textLimit("split_parts")).toBe(3);
    // A limit the backend did not serve is not assumed.
    expect(textLimit("entry_text")).toBeNull();
  } finally {
    holdLedgerLimits(null);
    expect(textLimit("split_parts")).toBeNull();
    holdLedgerLimits(servedLimits);
  }
});

test("a year is four digits, whichever it is, and period tokens are the product's", () => {
  const years: [string, Expected][] = [
    [String(fixtureYear), String(fixtureYear)],
    ["1000", "1000"],
    ["1979", "1979"],
    ["2201", "2201"],
    ["9999", "9999"],
    ["0999", "year_not_a_number"],
    ["10000", "year_not_a_number"],
    ["26", "year_not_a_number"],
    ["twenty", "year_not_a_number"],
  ];
  for (const [raw, expected] of years)
    expect(verdict(parseYear(raw)), raw).toBe(expected);
});

test("the periods held are the ones served, with their neighbours across year ends", () => {
  holdRecordedPeriods("en");
  try {
    let checked = 0;
    for (const [year, rows] of Object.entries(recorded.periods.years.en)) {
      for (const row of rows) {
        const period = ledgerPeriod(row.period)!;
        expect(period.year, year).toBe(Number(year));
        expect(neighbourPeriod(period, -1)).toEqual(ledgerPeriod(row.previous));
        expect(neighbourPeriod(period, 1)).toEqual(ledgerPeriod(row.next));
        expect(periodBounds(period)).toEqual({
          from: row.first_day,
          to: row.last_day,
        });
        expect(periodWords(period, "en")).toEqual({
          name: row.name_words,
          label: row.label_words,
        });
        checked += 1;
      }
    }
    expect(checked).toBeGreaterThan(100);
    // A quarter's neighbour in the next year is the one the backend names.
    expect(neighbourPeriod({ year: fixtureYear, code: "4T" }, 1)).toEqual({
      year: fixtureYear + 1,
      code: "1T",
    });
    expect(neighbourPeriod({ year: fixtureYear, code: "01" }, -1)).toEqual({
      year: fixtureYear - 1,
      code: "12",
    });
  } finally {
    holdLedgerPeriods(null, null);
  }
});

test("a period that was not served is unknown, never made up", () => {
  holdRecordedPeriods("en");
  try {
    // A year far before any the registry supports, which no recording serves.
    const unserved = servedSupport.floor - 50;
    expect(servedYear(unserved)).toBeNull();
    expect(periodBounds({ year: unserved, code: "3T" })).toBeNull();
    expect(neighbourPeriod({ year: unserved, code: "3T" }, 1)).toBeNull();
    expect(periodWords({ year: unserved, code: "3T" }, "en")).toBeNull();
    expect(periodsHolding(`${unserved}-07-01`)).toBeNull();
    expect(
      periodHoldingSpan({ from: `${unserved}-07-01`, to: `${unserved}-07-31` }),
    ).toBeNull();
    // Words served in one language are not shown in another.
    expect(periodWords({ year: fixtureYear, code: "3T" }, "es")).toBeNull();
    expect(periodWords({ year: fixtureYear, code: "3T" }, "en")).not.toBeNull();
  } finally {
    holdLedgerPeriods(null, null);
  }
});

test("the periods that hold a day and a span are the ones the backend answered", () => {
  holdRecordedPeriods("en");
  try {
    const days = recorded.periods.probes.days;
    expect(days.length).toBeGreaterThan(5);
    for (const probe of days) {
      const served = answerPeriods("en", { days: [probe.day] });
      expect(served, probe.day).not.toBeNull();
      holdLedgerPeriods("en", served!);
      expect(periodsHolding(probe.day), probe.day).toEqual({
        annual: ledgerPeriod(probe.annual),
        quarterly: ledgerPeriod(probe.quarterly),
        monthly: ledgerPeriod(probe.monthly),
      });
    }
    const spans = recorded.periods.probes.covering;
    expect(spans.length).toBeGreaterThan(3);
    for (const probe of spans) {
      const served = answerPeriods("en", {
        covering: { first_day: probe.first_day, last_day: probe.last_day },
      });
      expect(served, probe.first_day).not.toBeNull();
      holdLedgerPeriods("en", served!);
      expect(
        periodHoldingSpan({ from: probe.first_day, to: probe.last_day }),
        `${probe.first_day}/${probe.last_day}`,
      ).toEqual({ period: ledgerPeriod(probe.period) });
    }
    // A span that crosses a year end has no period: served as none.
    expect(
      periodHoldingSpan({
        from: fixtureDay(12, 30, -1),
        to: fixtureDay(1, 2),
      }),
    ).toEqual({ period: null });
  } finally {
    holdLedgerPeriods(null, null);
  }
});

test("the year field steps by one and by ten and stays on years that can be written", () => {
  // Stepping is arithmetic on any written year, inside the support envelope or
  // far from it; only the four-digit edges hold it.
  const inside = servedSupport.horizon;
  const outside = servedSupport.horizon + 169;
  expect(stepYear(inside, 1)).toBe(inside + 1);
  expect(stepYear(inside, -10)).toBe(inside - 10);
  expect(stepYear(servedSupport.floor - 37, -10)).toBe(
    servedSupport.floor - 47,
  );
  expect(stepYear(outside, 10)).toBe(outside + 10);
  const { first, last } = servedYearBounds;
  expect(stepYear(first + 5, -10)).toBe(first + 5);
  expect(stepYear(last - 4, 10)).toBe(last - 4);
  const decade = inside - (inside % 10);
  expect(decadeYears(inside)).toEqual(
    Array.from({ length: 10 }, (_, at) => decade + at),
  );
  expect(decadeYears(decade + 3)[0]).toBe(decade);
  expect(decadeYears(last - 4).at(-1)).toBe(last);
  expect(decadeYears(first)[0]).toBe(first);
  expect(decadeYears(outside - (outside % 10))).toHaveLength(10);
});

test("a period's list clauses are its token and its year", () => {
  expect(periodFilters({ year: fixtureYear, code: "3T" })).toEqual([
    "period=3T",
    `year=${fixtureYear}`,
  ]);
});

test("a refusal's example amount is written with the language's own decimal mark", () => {
  // English writes 1.5; Spanish, Catalan and Hungarian write 1,5.
  for (const locale of ["es", "ca", "hu"])
    for (const key of [
      "desktop.ledger.edit.refusal.ambiguous_grouping",
      "desktop.ledger.invoices.refusal.ambiguous_grouping",
      "desktop.ledger.documents.record_refused",
    ]) {
      const text = label(key, { raw: "x" }, locale);
      expect(text, `${locale} ${key}`).not.toMatch(/\d\.\d/);
      expect(text, `${locale} ${key}`).toMatch(/\d,\d/);
    }
});

test("with no limits served a typed number is not taken and what it says is kept", () => {
  holdLedgerLimits(null);
  try {
    for (const parsed of [
      parseDecimal("12.50", AMOUNT_RULE),
      parsePercent("21"),
      parseFractionPercent("0.21"),
    ])
      expect(parsed).toMatchObject({
        kind: "refused",
        refusal: { key: "limits_unavailable" },
      });
    expect(parseDecimal("12.50", AMOUNT_RULE)).toMatchObject({
      refusal: { raw: "12.50" },
    });
    // Nothing typed needs no limit, and a date none.
    expect(parseDecimal("", AMOUNT_RULE)).toEqual({ kind: "empty" });
    expect(parsePercent("").kind).toBe("empty");
    expect(parseIsoDate(fixtureDay(2, 1)).kind).toBe("value");
  } finally {
    holdLedgerLimits(servedLimits);
  }
});

test("a limit is the one served, not one of the window's", () => {
  holdLedgerLimits({
    ...servedLimits,
    percent_decimals: 1,
    decimal_rules: [{ rule: "amount", decimals: 3, zero: true }],
  });
  try {
    expect(parseDecimal("0", AMOUNT_RULE)).toEqual({
      kind: "value",
      value: "0",
    });
    expect(parseDecimal("1.2345", AMOUNT_RULE)).toMatchObject({
      refusal: { key: "too_many_decimals", limit: 3 },
    });
    expect(parsePercent("21.25")).toMatchObject({
      refusal: { key: "too_many_decimals", limit: 1 },
    });
    // A rule the backend did not serve is not assumed.
    expect(parseDecimal("1", TAX_AMOUNT_RULE)).toMatchObject({
      refusal: { key: "limits_unavailable" },
    });
  } finally {
    holdLedgerLimits(servedLimits);
  }
});
