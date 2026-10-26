import { invoke } from "@tauri-apps/api/core";
import type { ShellToken, TokenHeader } from "../ipc/contract";
import type { HostCall } from "./hostCall";
import type { LedgerOutcome, LedgerReview } from "./ledger";
import type { ModeloPort, ModeloResult } from "./modelo";

const TOKEN_HEADER: TokenHeader = "x-cadrumo-token";

/** The modelo port over the desktop host's modelo commands. Nothing here
 * keeps a form, a result, a review, an edit's body or a token's file. */
export function tauriModelo(
  token: ShellToken | null,
  call: HostCall,
): ModeloPort {
  return {
    declarations: (outputLanguage) =>
      call("modelo_declarations", { outputLanguage }),
    form: (workUnitId, outputLanguage) =>
      call("modelo_form", { workUnitId, outputLanguage }),
    casillaHelp: (request) =>
      call("modelo_casilla_help", {
        workUnitId: request.workUnitId,
        casillaId: request.casillaId,
        registryRevisionId: request.registryRevisionId,
        calculationRevisionId: request.calculationRevisionId,
        outputLanguage: request.language,
      }),
    async submit(definition, payload, ...workUnit) {
      const outcome = await call("modelo_submit", {
        definition,
        payload,
        ...(workUnit.length ? { workUnit: workUnit[0] } : {}),
      });
      // The runtime decoded the request against this definition's registered
      // contract and published its result under that contract's schema.
      return outcome as LedgerOutcome<ModeloResult<typeof definition>>;
    },
    // The body is the whole raw request, with the token in a header, and is
    // overwritten as soon as the call settles.
    async edit(definition, body) {
      try {
        if (!token) throw new Error("Missing desktop launch token.");
        const command =
          definition === "modelo.edit.apply"
            ? "modelo_edit_apply"
            : "modelo_edit_preflight";
        const outcome = await invoke<LedgerOutcome>(command, body, {
          headers: { [TOKEN_HEADER]: token },
        });
        return outcome as LedgerOutcome<ModeloResult<typeof definition>>;
      } finally {
        body.fill(0);
      }
    },
    observe: (operation) => call("modelo_observe", { operation }),
    async review<Review>(operation: string) {
      const review = await call("modelo_review", { operation });
      return review as LedgerReview<Review>;
    },
    answer: (operation, reviewDigest, decision) =>
      call("modelo_answer", { operation, reviewDigest, decision }),
    cancel: (operation, revision) =>
      call("modelo_cancel", { operation, revision }),
    pickFile: (purpose, filterLabel) =>
      call("modelo_files_pick", { purpose, filterLabel }),
    saveFile: (format, filterLabel, suggestedName) =>
      call("modelo_files_save", {
        format,
        filterLabel,
        suggestedName: suggestedName ?? null,
      }),
    forgetFiles: (tokens) =>
      call("modelo_files_forget", { tokens }).then(() => undefined),
    revealFile: (token) =>
      call("modelo_files_reveal", { token }).then(() => undefined),
  };
}
