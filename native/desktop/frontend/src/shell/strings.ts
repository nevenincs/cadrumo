import { createContext, useContext } from "react";
import catalogue from "virtual:desktop-strings";

// Chrome strings come only from the catalogue generated out of the canonical
// locale sources; there is no hand-written table here. The build refuses to
// start without it. A key the catalogue lacks is shown as the key itself,
// which the generator's own checks keep out of a release.

export const SOURCE_LOCALE = "en";
export const OUTPUT_LANGUAGES: readonly string[] = Object.keys(catalogue);

export type Translate = {
  (key: string, values?: Record<string, string | number>): string;
  /** The locale this translates into, set by `translator`. Lists and other
   * text composed from several pieces take their wording from it. A function
   * that only forwards to a translator carries none, and the host's own
   * language then applies. */
  readonly locale?: string;
};

export function translator(locale: string): Translate {
  const own = catalogue[locale] ?? {};
  const source = catalogue[SOURCE_LOCALE] ?? {};
  const translate = (
    key: string,
    values?: Record<string, string | number>,
  ): string => {
    const template = own[key] ?? source[key] ?? key;
    if (!values) return template;
    return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
      name in values ? String(values[name]) : whole,
    );
  };
  return Object.assign(translate, { locale });
}

export const StringsContext = createContext<Translate>(
  translator(SOURCE_LOCALE),
);

export function useStrings(): Translate {
  return useContext(StringsContext);
}

/** The tokens a key family carries in the generated strings: the part of each
 * key after `prefix`, in order. A family generated from a backend enum lists
 * that enum's members, so a view that offers them lists none of its own. */
export function tokensOf(prefix: string): string[] {
  return Object.keys(catalogue[SOURCE_LOCALE] ?? {})
    .filter((key) => key.startsWith(prefix))
    .map((key) => key.slice(prefix.length))
    .sort();
}
