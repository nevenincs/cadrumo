import { useEffect, useState } from "react";
import { fixture, type Fixtures, type Language } from "./fixtures";

/** One fixture in the reader's language, or null while it is read. */
export function useFixture<K extends keyof Fixtures>(
  kind: K,
  language: Language,
): Fixtures[K] | null {
  const key = `${kind}-${language}`;
  const [read, setRead] = useState<{ key: string; value: Fixtures[K] } | null>(
    null,
  );
  useEffect(() => {
    let live = true;
    void fixture(kind, language).then((value) => {
      if (live) setRead({ key: `${kind}-${language}`, value });
    });
    return () => {
      live = false;
    };
  }, [kind, language]);
  return read?.key === key ? read.value : null;
}

/** The reader's language, from the Storybook locale global. */
export const languageOf = (globals: Record<string, unknown>): Language =>
  String(globals.locale ?? "en") as Language;
