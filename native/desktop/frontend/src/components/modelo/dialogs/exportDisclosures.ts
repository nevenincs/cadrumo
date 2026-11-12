import type { LedgerErrorDetail } from "../../../shell/ledger";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloExportPublicResultV3 } from "../../../shell/modeloContract/modeloExport";
import type { ServedRefusal } from "../../../shell/refusal";

// The languages a served sentence may be in, checked against the generated
// union so a language the contract gains fails the type check here.
const SERVED_LANGUAGE: Record<OutputLanguage, true> = {
  es: true,
  en: true,
  ca: true,
  hu: true,
};
const isOutputLanguage = (value: string): value is OutputLanguage =>
  Object.hasOwn(SERVED_LANGUAGE, value);

// What one export's result states beside the file it wrote, as the result
// serves it. A warning says the export could not check something; a
// limitation discloses what the file leaves out, which can only raise the tax
// it states, so it is shown as a disclosure: neither a fault nor hidden. Each
// sentence is the one the command line and the terminal workbench state for
// the same served fact.

export type ExportDisclosure = {
  level: "warning" | "limitation";
  /** The catalogue key of the sentence that states it. */
  key: string;
};

export function exportDisclosures(
  result: ModeloExportPublicResultV3,
): ExportDisclosure[] {
  const receipt = result.fichero_boe;
  const disclosures: ExportDisclosure[] = [];
  if (result.completeness === "unverified")
    disclosures.push({
      level: "warning",
      key: "workspace.modelo.filing.completeness_unverified",
    });
  if (receipt?.domiciliation_cutoff_unverified === true)
    disclosures.push({
      level: "warning",
      key: "tui.modelo.export.result.warning.cutoff_unverified",
    });
  if (receipt?.trabajo_deductions_not_computed === true)
    disclosures.push({
      level: "limitation",
      key: "application.modelo.findings.trabajo_deduction_not_computed",
    });
  return disclosures;
}

/** A refused write as the window's one refusal notice takes it: the sentence
 * the backend served and its language. The verdict is left out until the
 * window reads the served verdict, so the notice offers no way out of its
 * own. */
export function servedExportRefusal(
  words: string | null,
  detail: LedgerErrorDetail | null,
): ServedRefusal {
  const language = detail?.refusal_words_language ?? null;
  return {
    refusal_words: words,
    refusal_words_language:
      language !== null && isOutputLanguage(language) ? language : null,
    verdict: null,
  };
}
