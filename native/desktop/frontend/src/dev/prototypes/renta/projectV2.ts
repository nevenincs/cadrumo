// The `modelo.project` result at version 2, as feature/renta-withholding
// declares it (`ModeloProjectOperationProjection` in
// src/cadrumo/application/modelo/projection_operation.py at 009999acb4). This
// branch still generates version 1, so the shape is mirrored here until the
// contract generator carries it. Version 2 names an unresolved credit and every
// total computed from it by closed tokens only, and serves no words for them.

export type ProjectUnresolvedBinding = {
  binding_id: string;
  casilla_id: string | null;
  source_kind: string;
  reason: string;
  note: string | null;
};

export type ProjectUnresolvedCasilla = {
  casilla_id: string;
  reason: string;
  formula_id: string;
  legal_refs: string[];
  source_refs: string[];
};

export type ProjectV2 = {
  result_version: 2;
  year: number;
  quarters_filed: number;
  quarters_available: string[];
  is_extrapolated: boolean;
  casilla_observations: {
    casilla_id: string;
    value: string;
    formula_id: string | null;
    legal_refs: string[];
    source_refs: string[];
  }[];
  unresolved_bindings: ProjectUnresolvedBinding[];
  unresolved_casillas: ProjectUnresolvedCasilla[];
};

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
    },
    {
      binding_id: "renta-retencion-soportada-capital-mobiliario",
      casilla_id: "0597",
      source_kind: "retencion_soportada",
      reason: "unresolved_binding",
      note: "retencion_soportada_evidence_required",
    },
    {
      binding_id: "renta-retencion-soportada-ganancia-patrimonial",
      casilla_id: "0603",
      source_kind: "retencion_soportada",
      reason: "unresolved_binding",
      note: "retencion_soportada_absence_contradicted",
    },
  ],
  unresolved_casillas: [
    {
      casilla_id: "0609",
      reason: "unresolved_operand",
      formula_id: "renta-total-pagos-a-cuenta",
      legal_refs: [],
      source_refs: [],
    },
    {
      casilla_id: "0610",
      reason: "unresolved_operand",
      formula_id: "renta-cuota-diferencial",
      legal_refs: ["ley-35-2006:art-79"],
      source_refs: [],
    },
  ],
};
