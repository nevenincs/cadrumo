import { createContext, useContext } from "react";

// Chrome strings come only from the catalogues generated out of the canonical
// locale sources; there is no hand-written table here. Until the generated file
// exists the lookup shows the key itself, which no release build can ship.
type Catalogue = Record<string, Record<string, string>>;

const generated = import.meta.glob<{ default: Catalogue }>(
  "../generated/chrome-strings.json",
  { eager: true },
);
const catalogue: Catalogue =
  Object.values(generated)[0]?.default ?? ({} as Catalogue);

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
