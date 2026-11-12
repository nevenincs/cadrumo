import type {
  ModeloExportDisclosure,
  ModeloExportPublicResultV3,
} from "../../../shell/modeloContract/modeloExport";

// What one export's result states beside the file it wrote, as the result
// serves it. A warning says the export could not check something, in the
// sentence the command line and the terminal workbench state for the same
// served flag. What the file leaves out is not worked out here: the result
// serves its verification's disclosed limitations in their own sentences,
// which the window shows as they are.

/** The catalogue key of one warning the result raises. */
export type ExportWarning = { key: string };

export function exportWarnings(
  result: ModeloExportPublicResultV3,
): ExportWarning[] {
  const warnings: ExportWarning[] = [];
  if (result.completeness === "unverified")
    warnings.push({ key: "workspace.modelo.filing.completeness_unverified" });
  if (result.fichero_boe?.domiciliation_cutoff_unverified === true)
    warnings.push({
      key: "tui.modelo.export.result.warning.cutoff_unverified",
    });
  return warnings;
}

/** The limitations the result disclosed, with their lead sentence, or null
 * when it disclosed none. */
export const exportDisclosure = (
  result: ModeloExportPublicResultV3,
): ModeloExportDisclosure | null => result.disclosure;
