import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloWorkbenchFormProjectionV1 } from "../../../shell/modeloContract/modeloWorkForm";

/** The last form read of the open declaration, kept by the caller while
 * the workspace is put away, in memory only. */
export type KeptWorkspaceRead = {
  form?: {
    workUnitId: string;
    language: OutputLanguage;
    envelope: ModeloWorkbenchFormProjectionV1;
  };
};

/** The read to draw at once: the kept one of the same declaration in the
 * same language, or none yet. */
export function keptRead(
  kept: KeptWorkspaceRead | undefined,
  workUnitId: string,
  language: OutputLanguage,
):
  | { phase: "ready"; envelope: ModeloWorkbenchFormProjectionV1 }
  | { phase: "reading" } {
  const form = kept?.form;
  return form && form.workUnitId === workUnitId && form.language === language
    ? { phase: "ready", envelope: form.envelope }
    : { phase: "reading" };
}
