import { createContext, useContext } from "react";
import catalogue from "virtual:desktop-strings";

// Chrome strings come only from the catalogue generated out of the canonical
// locale sources; there is no hand-written table here. The build refuses to
// start without it. A key the catalogue lacks is shown as the key itself,
// which the generator's own checks keep out of a release.

export const SOURCE_LOCALE = "en";

export type Translate = (
  key: string,
  values?: Record<string, string | number>,
) => string;

export function translator(locale: string): Translate {
  const own = catalogue[locale] ?? {};
  const source = catalogue[SOURCE_LOCALE] ?? {};
  return (key, values) => {
    const template = own[key] ?? source[key] ?? key;
    if (!values) return template;
    return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
      name in values ? String(values[name]) : whole,
    );
  };
}

export const StringsContext = createContext<Translate>(
  translator(SOURCE_LOCALE),
);

export function useStrings(): Translate {
  return useContext(StringsContext);
}
