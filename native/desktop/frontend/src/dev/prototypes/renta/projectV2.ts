// What the Renta prototypes read of the `modelo.project` result at version 2,
// typed from the generated contract so a change to the result's shape stops
// them compiling. Version 2 names an unresolved credit and every total
// computed from it by closed tokens. The words beside the tokens are the
// placeholders a prototype draws; the prototypes draw no figure from the
// totals, so none is given here.

import type { ModeloProjectOperationProjection } from "../../../shell/modeloContract";

export type ProjectV2 = Pick<
  ModeloProjectOperationProjection,
  | "result_version"
  | "year"
  | "quarters_filed"
  | "quarters_available"
  | "is_extrapolated"
  | "casilla_observations"
  | "unresolved_bindings"
  | "unresolved_casillas"
>;

/** A salaried profile with no payer record and no stated absence for its
 * three withholding classes: the credits and the totals that read them are
 * unresolved, never zero. Tokens are those the version 2 builder emits; no
 * figure is shown, so none is given. */
export const UNRESOLVED_CREDITS: ProjectV2 = {
  result_version: 2,
  year: 2025,
  quarters_filed: 4,
  quarters_available: ["1T", "2T", "3T", "4T"],
  is_extrapolated: false,
  casilla_observations: [],
  unresolved_bindings: [
    {
      binding_id: "renta-retencion-soportada-trabajo",
      casilla_id: "0596",
      source_kind: "retencion_soportada",
      reason: "unresolved_binding",
      note: "retencion_soportada_evidence_required",
      source_words: null,
      words: "Unresolved credit",
    },
    {
      binding_id: "renta-retencion-soportada-capital-mobiliario",
      casilla_id: "0597",
      source_kind: "retencion_soportada",
      reason: "unresolved_binding",
      note: "retencion_soportada_evidence_required",
      source_words: null,
      words: "Unresolved credit",
    },
    {
      binding_id: "renta-retencion-soportada-ganancia-patrimonial",
      casilla_id: "0603",
      source_kind: "retencion_soportada",
      reason: "unresolved_binding",
      note: "retencion_soportada_absence_contradicted",
      source_words: null,
      words: "Unresolved credit",
    },
  ],
  unresolved_casillas: [
    {
      casilla_id: "0609",
      reason: "unresolved_operand",
      reason_words: "An operand has no value",
      formula_id: "renta-total-pagos-a-cuenta",
      legal_refs: [],
      source_refs: [],
    },
    {
      casilla_id: "0610",
      reason: "unresolved_operand",
      reason_words: "An operand has no value",
      formula_id: "renta-cuota-diferencial",
      legal_refs: ["ley-35-2006:art-79"],
      source_refs: [],
    },
  ],
};
