const names = new Map<string, Intl.DisplayNames>();

function nameOf(
  locale: string,
  type: "region" | "currency",
  code: string,
): string | null {
  const key = `${locale} ${type}`;
  let held = names.get(key);
  if (!held) {
    held = new Intl.DisplayNames(locale, { type, fallback: "none" });
    names.set(key, held);
  }
  try {
    return held.of(code) ?? null;
  } catch {
    // A code of the wrong shape names nothing.
    return null;
  }
}

/** A country's name in `locale`, or null when the platform knows no such code. */
export const countryName = (locale: string, code: string) =>
  nameOf(locale, "region", code);

/** A currency's name in `locale`, or null when the platform knows no such code. */
export const currencyName = (locale: string, code: string) =>
  nameOf(locale, "currency", code);
