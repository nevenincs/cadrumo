import { expect, test } from "@playwright/test";
import {
  decimalReading,
  isReadDecimal,
} from "../../src/components/editors/numberReading";
import { heldDecimal, readLocaleDecimal } from "../../src/shared/numbers";
import { sameDecimal } from "../../src/shell/ledgerGrammar";

// A number of three decimals is the one a decimal editor can show as another:
// `1.500` is one and a half written canonically and in English, one thousand
// five hundred in Spanish. The expected texts are what each language writes
// for one and a half to three places, from the language's own marks.
const ONE_AND_A_HALF = {
  en: { typed: "1.500", shown: "1.500" },
  es: { typed: "1,500", shown: "1,500" },
  hu: { typed: "1,500", shown: "1,500" },
} as const;

for (const [locale, { typed, shown }] of Object.entries(ONE_AND_A_HALF)) {
  test(`1.500 typed in ${locale} is held as one and a half and shown as typed, at rest and after leaving`, () => {
    const reading = decimalReading(locale);
    const held = reading.read(typed);
    expect(held).not.toBeNull();
    expect(sameDecimal(held!, "1.5")).toBe(true);
    // The held spelling is one the editor reads, not text it left alone.
    expect(isReadDecimal(held!)).toBe(true);
    // At rest, and again after the box is left: the held value, in the marks.
    expect(reading.shown(held!)).toBe(shown);
    // Focusing it again starts from the same digits.
    expect(reading.typed(held!)).toBe(typed);
    // What is drawn reads back as the same number, in the same language.
    const back = readLocaleDecimal(locale, reading.shown(held!));
    expect(back).not.toBeNull();
    expect(sameDecimal(back!, "1.5")).toBe(true);
  });
}

test("a stored 1.5 seeded through heldDecimal at three places is not shown as one thousand five hundred in Spanish", () => {
  const reading = decimalReading("es");
  // The canonical spelling of one and a half, written to three places.
  const held = heldDecimal("1.500");
  expect(reading.shown(held)).toBe("1,500");
  expect(reading.shown(held)).not.toBe("1.500");
  // Spanish typing of `1.500` is a thousand and a half or one and a half: the
  // editor refuses to choose, and keeps what was typed.
  expect(readLocaleDecimal("es", "1.500")).toBeNull();
  expect(reading.read("1.500")).toBeNull();
  expect(readLocaleDecimal("es", "1500")).toBe("1500");
});

test("text in the two-way shape is unread and is shown as it came", () => {
  expect(isReadDecimal("1.500")).toBe(false);
  expect(isReadDecimal("1.234")).toBe(false);
  expect(isReadDecimal("-12.345")).toBe(false);
  expect(isReadDecimal("1.5000")).toBe(true);
  expect(isReadDecimal("1234.500")).toBe(true);
  expect(isReadDecimal("0.500")).toBe(true);
  expect(isReadDecimal("1.5")).toBe(true);
  for (const locale of ["en", "es", "hu"]) {
    const reading = decimalReading(locale);
    expect(reading.shown("1.500")).toBe("1.500");
    expect(reading.typed("1.500")).toBe("1.500");
  }
});
