// What the withholding form asks of a payer's certificate: the figures the
// ledger serves for the chosen income class, each read as typed. Which figures
// a class states, and their words, are the ledger's; this holds none of them.

import {
  certificateFiguresOf,
  statedByEveryClass,
  type CertificateFigure,
  type ServedVocabulary,
} from "../../../shell/ledgerServedVocabulary";
import {
  parseDecimal,
  TAX_AMOUNT_RULE,
  type Parsed,
} from "../../../shell/ledgerGrammar";

/** What a figure's box holds before anything is typed: zero for a figure
 * every certificate states, blank for one only some classes state, which the
 * person must therefore say. */
export const startingAmount = (
  vocabulary: ServedVocabulary,
  field: string,
): string => (statedByEveryClass(vocabulary, field) ? "0" : "");

export type FigureReading = {
  figure: CertificateFigure;
  /** The box's text. */
  text: string;
  parsed: Parsed<string>;
};

/** The chosen class's figures as typed, in the order they are served. */
export function readFigures(
  vocabulary: ServedVocabulary,
  incomeClass: string,
  typed: Readonly<Record<string, string>>,
): FigureReading[] {
  return certificateFiguresOf(vocabulary, incomeClass).map((figure) => {
    const text =
      typed[figure.field] ?? startingAmount(vocabulary, figure.field);
    return { figure, text, parsed: parseDecimal(text, TAX_AMOUNT_RULE) };
  });
}

/** Whether no figure is typed in a form the grammar refuses. A blank figure
 * is sendable: it is left out of the request and the ledger judges it. */
export const figuresSendable = (readings: readonly FigureReading[]): boolean =>
  readings.every((reading) => reading.parsed.kind !== "refused");

/** The request's figures: each typed one under its served field name; a
 * blank one is not sent. */
export function requestFigures(
  readings: readonly FigureReading[],
): Record<string, { decimal: string }> {
  const sent: Record<string, { decimal: string }> = {};
  for (const { figure, parsed } of readings)
    if (parsed.kind === "value") sent[figure.field] = { decimal: parsed.value };
  return sent;
}

/** Whether any figure differs from what the form opened with. */
export const figuresTyped = (
  vocabulary: ServedVocabulary,
  typed: Readonly<Record<string, string>>,
): boolean =>
  Object.entries(typed).some(
    ([field, text]) => text !== startingAmount(vocabulary, field),
  );
