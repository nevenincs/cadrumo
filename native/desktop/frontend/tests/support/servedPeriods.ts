import recorded from "../../src/dev/fixtures/ledgerEntryOptions.json" with { type: "json" };

type Row = { kind: string; name_words: string; period: { code: string } };
const years = recorded.periods.years as unknown as Record<
  string,
  Record<string, Row[]>
>;

/** The name the backend served for a period of a year, in `language`, as the
 * period dropdown draws it. */
export function servedPeriodName(
  year: number,
  code: string,
  language = "en",
): string {
  const found = years[language]?.[String(year)]?.find(
    (row) => row.period.code === code,
  );
  if (!found) throw new Error(`no recorded period ${code} of ${year}`);
  return found.name_words;
}

/** The name the backend served for a whole year, in `language`. */
export function servedYearName(year: number, language = "en"): string {
  const found = years[language]?.[String(year)]?.find(
    (row) => row.kind === "annual",
  );
  if (!found) throw new Error(`no recorded year ${year}`);
  return found.name_words;
}
