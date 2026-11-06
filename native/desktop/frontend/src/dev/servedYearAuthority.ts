// The year facts the backend serves, for the fixtures that stand in for it:
// the bounds a year field admits, the supported filing years, and for each tax
// year whether the envelope admits it, the Modelo 100 edition it falls under
// and the boxes its handoff fills, recorded in the generated
// `yearAuthority.json` by the backend's own resolvers. This decides nothing:
// every answer is looked up, and a year the recording does not hold is refused
// rather than worked out here.

import yearAuthority from "@fixtures/desktop-year-authority/yearAuthority.json" with { type: "json" };

/** The Modelo 100 edition a tax year falls under, as the register serves it. */
export type ServedEdition = {
  revision_id: string;
  authored_filing_year: number;
  projected: boolean;
};

/** A box a handoff fills: its casilla and what it is called in each language. */
export type ServedBox = { casilla: string; names: Record<string, string> };

/** A Modelo 130 period's box: one name per asset kind, in each language. */
export type ServedM130Box = {
  period: string;
  casilla: string;
  names: Record<string, Record<string, string>>;
};

/** The boxes a tax year's handoff fills. */
export type ServedHandoff = {
  m100: Record<string, ServedBox>;
  m130: ServedM130Box[];
};

type RecordedYear = {
  tax_year: number;
  admitted: boolean;
  beyond_last_admitted: boolean;
  edition: ServedEdition | null;
  handoff: ServedHandoff | null;
};

type Recording = {
  four_digit_year: { first: number; last: number };
  supported_filing_years: { floor: number; horizon: number };
  bien_inversion_minimum_acquisition_year: number;
  asset_editions: RecordedYear[];
};

const recorded: Recording = yearAuthority;

/** The bounds of a four-digit year, as the backend's year type declares them. */
export const servedYearBounds: { first: number; last: number } =
  recorded.four_digit_year;

/** The supported filing years: the floor and the horizon. */
export const servedSupport: { floor: number; horizon: number } =
  recorded.supported_filing_years;

/** The earliest acquisition year the registry admits for a capital good. */
export const servedMinimumAcquisitionYear: number =
  recorded.bien_inversion_minimum_acquisition_year;

const years = new Map<number, RecordedYear>(
  recorded.asset_editions.map((row) => [row.tax_year, row]),
);
const recordedYears = [...years.keys()];

/** The first and last tax year the recording answers for. */
export const servedEditionYears = {
  first: Math.min(...recordedYears),
  last: Math.max(...recordedYears),
};

/** The tax years the envelope admits up to the last admitted one, oldest
 * first: the years a filer can file for. */
export const servedFilingYears: readonly number[] = recorded.asset_editions
  .filter((row) => row.admitted && !row.beyond_last_admitted)
  .map((row) => row.tax_year)
  .sort((a, b) => a - b);

/** Whether the recording holds an answer for this tax year. */
export const recordsEditionFor = (taxYear: number): boolean =>
  years.has(taxYear);

function recordedYear(taxYear: number): RecordedYear {
  const year = years.get(taxYear);
  if (year === undefined) {
    throw new Error(
      `the year-authority recording holds no answer for ${taxYear}`,
    );
  }
  return year;
}

/** Whether the year lies past the last admitted one: read only as projected, and refused a claim. */
export const servedBeyondLastAdmitted = (taxYear: number): boolean =>
  recordedYear(taxYear).beyond_last_admitted;

/** The edition the backend reads for a tax year; null where it refuses the year. */
export const servedEditionOf = (taxYear: number): ServedEdition | null =>
  recordedYear(taxYear).edition;

/** Whether the support envelope admits the tax year. */
export const servedAdmits = (taxYear: number): boolean =>
  recordedYear(taxYear).admitted;

/** The boxes the tax year's handoff fills; null where the registry refuses the year. */
export const servedHandoffOf = (taxYear: number): ServedHandoff | null =>
  recordedYear(taxYear).handoff;

/** The Modelo 130 periods the registry serves for the tax year. */
export const servedM130PeriodsOf = (taxYear: number): string[] =>
  (servedHandoffOf(taxYear)?.m130 ?? []).map((box) => box.period);
