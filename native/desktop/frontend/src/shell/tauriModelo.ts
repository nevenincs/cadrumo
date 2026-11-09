import { invoke } from "@tauri-apps/api/core";
import type { ShellToken, TokenHeader } from "../ipc/contract";
import type { HostCall } from "./hostCall";
import { refuseIfEnded, sessionBound } from "./sessionGate";
import type { LedgerOutcome, LedgerReview } from "./ledger";
import type { ModeloPort, ModeloResult } from "./modelo";

const TOKEN_HEADER: TokenHeader = "x-cadrumo-token";

/** The modelo port over the desktop host's modelo commands. Nothing here
 * keeps a form, a result, a review, an edit's body or a token's file. */
export function tauriModelo(
  token: ShellToken | null,
  call: HostCall,
): ModeloPort {
  // Only a signed-in session can ask these; files are forgotten whatever
  // the session's state.
  const bound = sessionBound(call);
  return {
    declarations: (outputLanguage) =>
      bound("modelo_declarations", { outputLanguage }),
    search: (query, outputLanguage, limit) =>
      bound("modelo_declarations_search", { query, outputLanguage, limit }),
    form: (workUnitId, outputLanguage) =>
      bound("modelo_form", { workUnitId, outputLanguage }),
    casillaHelp: (request) =>
      bound("modelo_casilla_help", {
        workUnitId: request.workUnitId,
        casillaId: request.casillaId,
        registryRevisionId: request.registryRevisionId,
        calculationRevisionId: request.calculationRevisionId,
        outputLanguage: request.language,
      }),
    async submit(definition, payload, ...workUnit) {
      const outcome = await bound("modelo_submit", {
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
        refuseIfEnded();
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
    observe: (operation) => bound("modelo_observe", { operation }),
    async review<Review>(operation: string) {
      const review = await bound("modelo_review", { operation });
      return review as LedgerReview<Review>;
    },
    answer: (operation, reviewDigest, decision) =>
      bound("modelo_answer", { operation, reviewDigest, decision }),
    cancel: (operation, revision) =>
      bound("modelo_cancel", { operation, revision }),
    pickFile: (purpose, filterLabel) =>
      bound("modelo_files_pick", { purpose, filterLabel }),
    saveFile: (format, filterLabel, suggestedName) =>
      bound("modelo_files_save", {
        format,
        filterLabel,
        suggestedName: suggestedName ?? null,
      }),
    forgetFiles: (tokens) =>
      call("modelo_files_forget", { tokens }).then(() => undefined),
    revealFile: (token) =>
      bound("modelo_files_reveal", { token }).then(() => undefined),
  };
}
