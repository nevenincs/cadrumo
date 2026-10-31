// Numbers are drawn from their exact decimal text. Only whole-number BigInts
// and the literals 1n and -1n reach `Intl`, so no value passes through a double
// at any size. Text that is not a plain decimal is returned as it came.

const formats = new Map<string, Intl.NumberFormat>();

function numberFormat(
  locale: string,
  options: Intl.NumberFormatOptions,
): Intl.NumberFormat {
  const key = `${locale} ${JSON.stringify(options)}`;
  let held = formats.get(key);
  if (!held) {
    // The fraction digits are appended as written, so the whole part must
    // be drawn in the same digits whatever the locale's default numerals.
    held = new Intl.NumberFormat(locale, {
      ...options,
      numberingSystem: "latn",
    });
    formats.set(key, held);
  }
  return held;
}

type Reading = { negative: boolean; whole: string; fraction: string };

function read(text: string): Reading | null {
  const found = /^(-?)(\d+)(?:\.(\d+))?$/.exec(text.trim());
  if (!found) return null;
  return {
    negative: found[1] === "-",
    whole: found[2] ?? "0",
    fraction: found[3] ?? "",
  };
}

/** Holds a reading to its fraction limits. A digit past `max` rounds half
 * away from zero, as `Intl` does, and a sign left on nothing but zeros goes. */
function fit(
  { negative, whole, fraction }: Reading,
  min: number,
  max: number | undefined,
): Reading {
  if (max !== undefined && max < min)
    throw new RangeError(`maxFraction ${max} is below minFraction ${min}`);
  let keptWhole = whole;
  let kept = fraction;
  if (max !== undefined && fraction.length > max) {
    const scale = 10n ** BigInt(fraction.length - max);
    const units = (BigInt(`${whole}${fraction}`) + (5n * scale) / 10n) / scale;
    const digits = units.toString().padStart(max + 1, "0");
    keptWhole = digits.slice(0, digits.length - max);
    kept = digits.slice(digits.length - max);
  }
  kept = kept.replace(/0+$/, "").padEnd(min, "0");
  return {
    negative: negative && /[1-9]/.test(`${keptWhole}${kept}`),
    whole: keptWhole,
    fraction: kept,
  };
}

/** Draws a reading in the shape `style` gives the locale: the sign, the marks
 * and the place of a currency or percent sign come from a sample of it. */
function draw(
  locale: string,
  { negative, whole, fraction }: Reading,
  style: Intl.NumberFormatOptions,
  grouping: boolean,
): string {
  // Left unset, grouping follows the locale's rule, which leaves `1234` whole
  // in Spanish; `true` would force a mark there.
  const ungrouped = grouping ? {} : { useGrouping: false };
  const shape = numberFormat(locale, {
    ...style,
    ...ungrouped,
    minimumFractionDigits: fraction ? 1 : 0,
  });
  // A percent format multiplies what it is given, so its whole part is drawn
  // by a plain one.
  const digits =
    style.style === "percent" ? numberFormat(locale, ungrouped) : shape;
  const wholeText = digits
    .formatToParts(BigInt(whole))
    .filter((part) => part.type === "integer" || part.type === "group")
    .map((part) => part.value)
    .join("");
  return shape
    .formatToParts(negative ? -1n : 1n)
    .map((part) =>
      part.type === "integer"
        ? wholeText
        : part.type === "fraction"
          ? fraction
          : part.value,
    )
    .join("");
}

/** A decimal in the locale's marks. Without `maxFraction` every digit shows. */
export function formatDecimal(
  locale: string,
  canonical: string,
  {
    minFraction = 0,
    maxFraction,
    grouping = true,
  }: { minFraction?: number; maxFraction?: number; grouping?: boolean } = {},
): string {
  const reading = read(canonical);
  if (!reading) return canonical;
  return draw(locale, fit(reading, minFraction, maxFraction), {}, grouping);
}

const CENTS = 2;

/** An amount, in the currency's own form when one is named. It shows
 * `decimals` places; without them, two, or more where the currency has more. */
export function formatAmount(
  locale: string,
  canonical: string,
  { currency, decimals }: { currency?: string; decimals?: number } = {},
): string {
  const reading = read(canonical);
  if (!reading) return canonical;
  let style: Intl.NumberFormatOptions = {};
  let places = CENTS;
  if (currency) {
    try {
      places = numberFormat(locale, {
        style: "currency",
        currency,
        minimumFractionDigits: CENTS,
      }).resolvedOptions().maximumFractionDigits as number;
      style = { style: "currency", currency };
    } catch {
      const figure = fit(reading, decimals ?? CENTS, decimals ?? CENTS);
      return `${draw(locale, figure, {}, true)} ${currency}`;
    }
  }
  const figure = fit(reading, decimals ?? CENTS, decimals ?? places);
  return draw(locale, figure, style, true);
}

const PERCENT_SHIFT = 2;

/** A percentage. `unit` says what the text holds: a fraction, where `0.21` is
 * 21%, or points, where `21` is. Each field's unit is its own to name. */
export function formatPercent(
  locale: string,
  canonical: string,
  {
    unit,
    maxFraction = 4,
  }: { unit: "fraction" | "points"; maxFraction?: number },
): string {
  const reading = read(canonical);
  if (!reading) return canonical;
  let points = reading;
  if (unit === "fraction") {
    const fraction = reading.fraction.padEnd(PERCENT_SHIFT, "0");
    points = {
      negative: reading.negative,
      whole: `${reading.whole}${fraction.slice(0, PERCENT_SHIFT)}`,
      fraction: fraction.slice(PERCENT_SHIFT),
    };
  }
  return draw(locale, fit(points, 0, maxFraction), { style: "percent" }, true);
}

/** A count of things, in the locale's grouping. */
export function formatCount(locale: string, n: number | bigint): string {
  return numberFormat(locale, {}).format(n);
}

/** The locale's grouping and decimal marks. */
export function marksOf(locale: string): { group: string; decimal: string } {
  const parts = numberFormat(locale, {
    minimumFractionDigits: 1,
  }).formatToParts(1234567n);
  const mark = (type: Intl.NumberFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";
  return { group: mark("group"), decimal: mark("decimal") };
}
