import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import {
  formatAmount,
  formatCount,
  formatDecimal,
  formatPercent,
  heldDecimal,
  marksOf,
  readLocaleDecimal,
} from "../../src/shared/numbers";
import {
  parseDecimal,
  parseFractionPercent,
} from "../../src/shell/ledgerGrammar";

const NBSP = " ";
const LOCALES = ["en", "es", "ca", "hu"] as const;

// `Intl` reads a decimal string as its exact value, which the module under test
// does not use: it is an independent oracle at sizes a double cannot hold. The
// configured library types only list number and bigint.
const exactly = (text: string) => text as unknown as number;

test("decimals carry each locale's marks", () => {
  const expected = {
    en: "1,234,567.89",
    es: "1.234.567,89",
    ca: "1.234.567,89",
    hu: `1${NBSP}234${NBSP}567,89`,
  };
  for (const locale of LOCALES)
    expect(formatDecimal(locale, "1234567.89")).toBe(expected[locale]);
});

test("integers beyond 2^53 keep every digit", () => {
  // 2^53 + 1 is the first integer a double cannot hold.
  const expected = {
    en: "9,007,199,254,740,993",
    es: "9.007.199.254.740.993",
    ca: "9.007.199.254.740.993",
    hu: `9${NBSP}007${NBSP}199${NBSP}254${NBSP}740${NBSP}993`,
  };
  for (const locale of LOCALES) {
    expect(formatDecimal(locale, "9007199254740993")).toBe(expected[locale]);
    expect(formatCount(locale, 9007199254740993n)).toBe(expected[locale]);
  }
  expect(formatDecimal("en", "123456789012345678901234567890.123456")).toBe(
    "123,456,789,012,345,678,901,234,567,890.123456",
  );
  expect(formatAmount("en", "9007199254740993.125")).toBe(
    "9,007,199,254,740,993.13",
  );
});

test("six decimals and negatives stay exact", () => {
  const expected = {
    en: ["0.000001", "-12,345.000001", "-0.5"],
    es: ["0,000001", "-12.345,000001", "-0,5"],
    ca: ["0,000001", "-12.345,000001", "-0,5"],
    hu: ["0,000001", `-12${NBSP}345,000001`, "-0,5"],
  };
  for (const locale of LOCALES) {
    const [tiny, negative, belowOne] = expected[locale];
    expect(formatDecimal(locale, "0.000001")).toBe(tiny);
    expect(formatDecimal(locale, "-12345.000001")).toBe(negative);
    expect(formatDecimal(locale, "-0.5")).toBe(belowOne);
  }
});

test("exact text agrees with Intl's own exact reading in every locale", () => {
  const values = [
    "0",
    "7",
    "1234",
    "12345",
    "-1234.5",
    "0.1",
    "0.000001",
    "-0.000001",
    "999999999999.999999",
    "9007199254740993",
    "-9007199254740993.000001",
    "123456789012345678901234567890.123456",
  ];
  for (const locale of LOCALES) {
    const plain = new Intl.NumberFormat(locale, { maximumFractionDigits: 20 });
    const money = new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "EUR",
      minimumFractionDigits: 2,
      maximumFractionDigits: 6,
    });
    const percent = new Intl.NumberFormat(locale, {
      style: "percent",
      maximumFractionDigits: 20,
    });
    for (const value of values) {
      expect(formatDecimal(locale, value)).toBe(plain.format(exactly(value)));
      expect(
        formatPercent(locale, value, { unit: "fraction", maxFraction: 20 }),
      ).toBe(percent.format(exactly(value)));
    }
    for (const value of ["1234.5", "-12345.67", "0.5", "9007199254740993.25"])
      expect(formatAmount(locale, value, { currency: "EUR" })).toBe(
        money.format(exactly(value)),
      );
  }
});

test("fraction limits round half away from zero on the decimal text", () => {
  // Each of these sits on a tie that a double stores to one side or the other.
  expect(formatAmount("en", "1.005")).toBe("1.01");
  expect(formatAmount("en", "2.675")).toBe("2.68");
  expect(formatAmount("en", "-2.675")).toBe("-2.68");
  expect(formatAmount("en", "1.0049")).toBe("1.00");
  expect(formatAmount("en", "999.995")).toBe("1,000.00");
  expect(formatDecimal("en", "1.123", { minFraction: 1, maxFraction: 2 })).toBe(
    "1.12",
  );
  expect(formatDecimal("en", "1.50", { minFraction: 1, maxFraction: 2 })).toBe(
    "1.5",
  );
  expect(formatDecimal("en", "1", { minFraction: 2 })).toBe("1.00");
  expect(formatDecimal("en", "0.5", { maxFraction: 0 })).toBe("1");
  expect(() =>
    formatDecimal("en", "1", { minFraction: 3, maxFraction: 2 }),
  ).toThrow(RangeError);
});

test("a value that rounds to zero carries no sign", () => {
  expect(formatDecimal("en", "-0.001", { maxFraction: 2 })).toBe("0");
  expect(formatAmount("en", "-0.001")).toBe("0.00");
  expect(formatAmount("en", "-0.00")).toBe("0.00");
  expect(formatDecimal("en", "-0")).toBe("0");
});

test("grouping can be turned off and non-canonical spellings read the same", () => {
  expect(formatDecimal("hu", "1234567.5", { grouping: false })).toBe(
    "1234567,5",
  );
  expect(formatDecimal("en", "12.50")).toBe("12.5");
  expect(formatDecimal("en", "007")).toBe("7");
  expect(formatDecimal("en", " 1.5 ")).toBe("1.5");
});

test("amounts show cents and place a named currency by locale", () => {
  expect(formatAmount("en", "1234.5")).toBe("1,234.50");
  expect(formatAmount("es", "12345.6")).toBe("12.345,60");
  expect(formatAmount("hu", "12345.6")).toBe(`12${NBSP}345,60`);
  expect(formatAmount("en", "1234.5", { currency: "USD" })).toBe("$1,234.50");
  expect(formatAmount("en", "-1234.5", { currency: "EUR" })).toBe("-€1,234.50");
  expect(formatAmount("es", "12345.6", { currency: "EUR" })).toBe(
    `12.345,60${NBSP}€`,
  );
  expect(formatAmount("ca", "12345.6", { currency: "EUR" })).toBe(
    `12.345,60${NBSP}€`,
  );
  expect(formatAmount("hu", "12345.6", { currency: "HUF" })).toBe(
    `12${NBSP}345,60${NBSP}Ft`,
  );
  expect(formatAmount("en", "1.23456", { decimals: 4 })).toBe("1.2346");
  expect(formatAmount("en", "1234.5", { decimals: 0 })).toBe("1,235");
  // A three-place currency keeps its third place, and two remain the floor.
  expect(formatAmount("en", "1.234", { currency: "KWD" })).toBe(
    `KWD${NBSP}1.234`,
  );
  expect(formatAmount("en", "1.2", { currency: "KWD" })).toBe(`KWD${NBSP}1.20`);
  expect(formatAmount("en", "1234", { currency: "JPY" })).toBe("¥1,234.00");
  expect(formatAmount("en", "12.5", { currency: "??" })).toBe("12.50 ??");
});

test("a percentage names its unit", () => {
  const expected = {
    en: "21%",
    es: `21${NBSP}%`,
    ca: `21${NBSP}%`,
    hu: "21%",
  };
  for (const locale of LOCALES) {
    expect(formatPercent(locale, "0.21", { unit: "fraction" })).toBe(
      expected[locale],
    );
    expect(formatPercent(locale, "21", { unit: "points" })).toBe(
      expected[locale],
    );
  }
  expect(formatPercent("en", "0.21", { unit: "points" })).toBe("0.21%");
  expect(formatPercent("en", "21", { unit: "fraction" })).toBe("2,100%");
  expect(formatPercent("en", "0.012345", { unit: "fraction" })).toBe("1.2345%");
  expect(formatPercent("en", "0.0123456", { unit: "fraction" })).toBe(
    "1.2346%",
  );
  expect(
    formatPercent("en", "0.105", { unit: "fraction", maxFraction: 1 }),
  ).toBe("10.5%");
  expect(formatPercent("en", "1", { unit: "fraction" })).toBe("100%");
  expect(formatPercent("en", "0.5", { unit: "fraction" })).toBe("50%");
  expect(formatPercent("en", "-0.5", { unit: "fraction" })).toBe("-50%");
  expect(formatPercent("es", "-0.005", { unit: "fraction" })).toBe(
    `-0,5${NBSP}%`,
  );
  expect(formatPercent("en", "12345.6", { unit: "points" })).toBe("12,345.6%");
  expect(
    formatPercent("en", "100000000000000000000", { unit: "fraction" }),
  ).toBe("10,000,000,000,000,000,000,000%");
});

test("text that is not a plain decimal comes back as it came", () => {
  for (const raw of [
    "",
    "abc",
    "1e5",
    "1,5",
    "NaN",
    "Infinity",
    "1.2.3",
    "+1",
  ]) {
    expect(formatDecimal("en", raw)).toBe(raw);
    expect(formatAmount("en", raw, { currency: "EUR" })).toBe(raw);
    expect(formatPercent("en", raw, { unit: "fraction" })).toBe(raw);
  }
});

test("counts follow the locale's grouping", () => {
  expect(formatCount("en", 1234567)).toBe("1,234,567");
  expect(formatCount("es", 1234567)).toBe("1.234.567");
  expect(formatCount("ca", 1234567)).toBe("1.234.567");
  expect(formatCount("hu", 1234567)).toBe(`1${NBSP}234${NBSP}567`);
  expect(formatCount("en", 0)).toBe("0");
  for (const locale of LOCALES)
    expect(formatCount(locale, 1234)).toBe(
      new Intl.NumberFormat(locale).format(1234),
    );
});

test("marks are the locale's own", () => {
  expect(marksOf("en")).toEqual({ group: ",", decimal: "." });
  expect(marksOf("es")).toEqual({ group: ".", decimal: "," });
  expect(marksOf("ca")).toEqual({ group: ".", decimal: "," });
  expect(marksOf("hu")).toEqual({ group: NBSP, decimal: "," });
});

// Each row was written by the backend's own reader, and
// `test_edit_number_table.py` holds that reader to it.
const READINGS = JSON.parse(
  readFileSync(
    new URL("./locale-decimal-readings.json", import.meta.url),
    "utf8",
  ),
) as ({ lexeme: string } & Record<(typeof LOCALES)[number], string | null>)[];

test("typed numbers read as the backend reads them", () => {
  expect(READINGS.length).toBeGreaterThan(50);
  for (const row of READINGS)
    for (const locale of LOCALES)
      expect(
        readLocaleDecimal(locale, row.lexeme),
        `${JSON.stringify(row.lexeme)} in ${locale}`,
      ).toBe(row[locale]);
});

test("reading settles what a text alone cannot", () => {
  // Written out from the rule, not from the table.
  expect(readLocaleDecimal("es", "1,234")).toBe("1.234");
  expect(readLocaleDecimal("es", "1.234")).toBeNull();
  expect(readLocaleDecimal("en", "1.234")).toBe("1.234");
  expect(readLocaleDecimal("en", "1,234")).toBeNull();
  expect(readLocaleDecimal("hu", "1 234,5")).toBe("1234.5");
  expect(readLocaleDecimal("es", "1 234,5")).toBeNull();
  expect(readLocaleDecimal("es", "1,000")).toBe("1.000");
  expect(readLocaleDecimal("en", "9007199254740993.123456")).toBe(
    "9007199254740993.123456",
  );
});

test("a read two-way decimal passes the grammar and an unread one does not", () => {
  const six = { decimals: 6, zero: true };
  const cents = { decimals: 2, zero: true };
  expect(parseDecimal(heldDecimal("1.234"), six)).toEqual({
    kind: "value",
    value: "1.234",
  });
  expect(parseDecimal("1.234", six)).toMatchObject({
    refusal: { key: "ambiguous_grouping" },
  });
  // In Spanish `1,000` is one, typed to three places: an amount refuses it
  // rather than turning a thousand into one.
  expect(parseDecimal(heldDecimal("1.000"), cents)).toMatchObject({
    refusal: { key: "too_many_decimals", limit: 2 },
  });
  expect(heldDecimal("1234.5")).toBe("1234.5");
  expect(heldDecimal("0.333")).toBe("0.333");
});

test("a fraction percent checks what the editor holds", () => {
  expect(parseFractionPercent("0.21")).toEqual({
    kind: "value",
    value: "0.21",
  });
  expect(parseFractionPercent("")).toEqual({ kind: "empty" });
  expect(parseFractionPercent("1")).toEqual({ kind: "value", value: "1" });
  expect(parseFractionPercent("1.5")).toMatchObject({
    refusal: { key: "percent_above_100" },
  });
  expect(parseFractionPercent("1.234")).toMatchObject({
    refusal: { key: "ambiguous_grouping" },
  });
  expect(parseFractionPercent("0.1234567")).toMatchObject({
    refusal: { key: "too_many_decimals" },
  });
  expect(parseFractionPercent("abc")).toMatchObject({
    refusal: { key: "not_a_number" },
  });
});
