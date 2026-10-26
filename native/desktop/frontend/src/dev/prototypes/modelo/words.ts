import catalogue from "virtual:desktop-strings";

// The Modelo wording the product already ships in four languages: findings,
// actions, origins, sources, periods, next steps and list states, taken from
// the locale catalogues the CLI and the TUI use, as the desktop build
// generates them for the shell.

const BY_LOCALE: Record<string, Record<string, string>> = catalogue;

/** A catalogue sentence in the reader's language, Spanish then English when
 * it is missing, with its values filled in. */
export function w(
  key: string,
  locale: string,
  values: Record<string, string | number> = {},
): string {
  const text =
    BY_LOCALE[locale]?.[key] ?? BY_LOCALE.es?.[key] ?? BY_LOCALE.en?.[key];
  if (text === undefined) {
    // A sentence the catalogue lacks is a defect to fix, never a word to show.
    console.error(`Missing catalogue key: ${key}`);
    return `⟦${key}⟧`;
  }
  return text.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in values ? String(values[name]) : whole,
  );
}

/** Whether the catalogue has a sentence for this key. */
export const has = (key: string) => key in (BY_LOCALE.en ?? {});
