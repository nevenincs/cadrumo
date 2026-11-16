// The request and result shapes of the own account, withholding and capital
// goods registers the Setup sections keep. Field names are the
// registered Python contracts' own, and a request leaves out the profile,
// which the host fills. A refused mutation comes back as the refusal's
// detail, in the same shape.

import type { FileToken, JsonValue, PublicDecimal } from "./ledger";
import type {
  WithholdingIncomeClass,
  WithholdingOrigin,
} from "./ledgerContract";

// ---- Own accounts --------------------------------------------------------

export type OwnAccountRole = "charge" | "refund";

export type OwnAccountHolding = "titular" | "cotitular";

/** An own account action without account details. Adding an account or
 * changing its details travels only as `changeOwnAccount`'s raw bytes. */
export type LedgerOwnAccountRequest =
  | { action: "list" }
  | { action: "show"; own_account_id: string }
  | { action: "update"; own_account_id: string; label: string }
  | { action: "close"; own_account_id: string; closed_on: string }
  | { action: "remove"; own_account_id: string }
  | {
      action: "designate";
      own_account_id: string;
      role: OwnAccountRole;
      modelo?: string | null;
    }
  | { action: "undesignate"; role: OwnAccountRole; modelo?: string | null };

/** An account as the product publishes it: its number masked, its bank
 * block only as whether there is one. */
export type OwnAccount = {
  own_account_id: string;
  label: string;
  holding: OwnAccountHolding;
  masked_iban: string;
  country_code: string;
  sepa_marca: string;
  has_swift_bic: boolean;
  has_bank_block: boolean;
  currency: string;
  opened_on: string | null;
  closed_on: string | null;
};

/** A designation without a modelo covers every modelo. */
export type OwnAccountDesignation = {
  role: OwnAccountRole;
  modelo: string | null;
  own_account_id: string;
};

export type LedgerOwnAccountResult = {
  profile_id: string;
  action: string;
  own_account_id: string | null;
  accounts: OwnAccount[];
  designations: OwnAccountDesignation[];
  changed: boolean;
};

// ---- Withholding certificates --------------------------------------------

/** One payer's certificate figures for an ejercicio and income class. The
 * payer is named by `payer_ref`, never by their tax identifier, which the
 * backend does not give back. The class, the payer and the origin are served
 * in the person's language; an amount the certificate does not state is null
 * or absent. */
export type WithholdingRow = {
  ejercicio: number;
  income_class: WithholdingIncomeClass;
  income_class_label: string;
  payer_ref: string;
  payer_legal_name: string | null;
  /** The legal name, or the words saying the record states none. */
  payer_display_name: string;
  importe_integro_dinerario: PublicDecimal;
  valoracion_especie: PublicDecimal;
  retencion: PublicDecimal;
  ingreso_a_cuenta: PublicDecimal;
  ingreso_a_cuenta_repercutido: PublicDecimal;
  reducciones_aplicables?: PublicDecimal | null;
  gastos_deducibles?: PublicDecimal | null;
  pago_a_cuenta: PublicDecimal;
  origin: WithholdingOrigin;
  origin_label: string;
  evidence_fingerprint: string | null;
  revision_id: string;
};

export type WithholdingListRequest = { ejercicio: number };

/** One amount field of a listed row and the words naming it. */
export type WithholdingAmountColumn = {
  /** The row field holding the amount, as the backend names it. */
  field: string;
  label: string;
};

export type WithholdingListResult = {
  profile_id: string;
  ejercicio: number;
  rows: WithholdingRow[];
  /** The amount fields of a row, in row order, each with its words. */
  amount_columns: WithholdingAmountColumn[];
  /** Every ejercicio the pinned authority supports, oldest first. */
  ejercicios: number[];
};

/** Why a certificate change was refused before anything was stored. */
export type WithholdingRefusalReason =
  | "own_tax_id"
  | "ejercicio_unsupported"
  | "family_not_declared"
  | "identity_mismatch"
  | "stale_revision"
  | "repercutido_exceeds_ingreso_a_cuenta"
  | "certificate_fingerprint_required"
  | "certificate_not_in_custody"
  | "certificate_file_unreadable"
  | "certificate_fingerprint_mismatch"
  | "trabajo_certificate_figure_missing"
  | "taxpayer_tax_id_unknown"
  | "not_found"
  | "validation";

/** What a certificate change did; a refused one is the refusal's detail. */
export type WithholdingMutationResult = {
  outcome: "recorded" | "removed" | "refused";
  profile_id: string;
  ejercicio: number;
  row: WithholdingRow | null;
  count: number | null;
  refusal: {
    code:
      | "REFUSED_RETENCION_SOPORTADA_WRITE"
      | "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT";
    reason: WithholdingRefusalReason;
    ejercicio: number;
    /** The finished sentence the backend serves with every refusal, in its
     * own language. */
    refusal_words?: string | null;
    refusal_words_language?: string | null;
  } | null;
};

/** Records a payer's certificate. `payer_tax_id` is private input: it goes
 * in this request only and the backend never returns it. The certificate is
 * named by `source_path`, a token for the file the person picked, which the
 * backend reads and keeps in the profile's encrypted custody (the host fills
 * `source_directory`), or by `evidence_fingerprint` alone for bytes custody
 * already holds. Given with a file, the fingerprint only cross-checks the
 * bytes read. A refusal can leave the kept bytes behind: the operation
 * settles refused with a partial effect. */
export type WithholdingRecordRequest = {
  ejercicio: number;
  income_class: WithholdingIncomeClass;
  payer_tax_id: string;
  payer_legal_name?: string | null;
  origin: WithholdingOrigin;
  evidence_fingerprint?: string | null;
  source_path?: FileToken | null;
  expected_revision_id?: string | null;
  /** The certificate's figures, each under the field name the ledger serves
   * in its `withholding_certificate_figure` options for the class: the
   * request holds none of them by name. */
  [figure: string]: JsonValue | undefined;
};

export type WithholdingRemoveRequest = {
  ejercicio: number;
  income_class: WithholdingIncomeClass;
  payer_ref: string;
  expected_revision_id: string;
};

/** The person's attestation that no payer withheld on a class. A change's
 * answer carries the attestation as stored; only the listing words its
 * income class and its state, in the person's language. */
export type WithholdingAbsence = {
  ejercicio: number;
  income_class: WithholdingIncomeClass;
  note: string;
  state: "active" | "withdrawn";
  attested_at: string;
  withdrawn_at: string | null;
  revision_id: string;
  income_class_label?: string | null;
  state_label?: string | null;
};

/** Every attestation of an ejercicio, active and withdrawn. */
export type WithholdingAbsenceListRequest = { ejercicio: number };

export type WithholdingAbsenceListResult = {
  profile_id: string;
  ejercicio: number;
  attestations: WithholdingAbsence[];
};

export type WithholdingAbsenceReason =
  | "ejercicio_unsupported"
  | "family_not_declared"
  | "records_present"
  | "already_attested"
  | "not_attested"
  | "stale_revision";

export type WithholdingAbsenceResult = {
  outcome: "attested" | "withdrawn" | "refused";
  profile_id: string;
  ejercicio: number;
  attestation: WithholdingAbsence | null;
  refusal: {
    code:
      | "REFUSED_RETENCION_SOPORTADA_ABSENCE"
      | "REFUSED_RETENCION_SOPORTADA_REVISION_CONFLICT";
    reason: WithholdingAbsenceReason;
    ejercicio: number;
    income_class: WithholdingIncomeClass;
    /** The finished sentence the backend serves with every refusal, in its
     * own language. */
    refusal_words?: string | null;
    refusal_words_language?: string | null;
  } | null;
};

export type WithholdingAttestRequest = {
  ejercicio: number;
  income_class: WithholdingIncomeClass;
  note: string;
  expected_revision_id?: string | null;
};

export type WithholdingWithdrawRequest = {
  ejercicio: number;
  income_class: WithholdingIncomeClass;
  expected_revision_id: string;
};

// ---- Bienes de inversión -------------------------------------------------

export type CapitalGood = {
  identifier: string;
  description: string;
  acquisition_year: number;
  cuota_soportada: PublicDecimal;
  prorrata_inicial_pct: PublicDecimal;
  kind: string;
  art108_elegible: boolean;
  acquisition_ledger_id: string;
  prorrata_sector_id: string | null;
  disposal: { year: number; regime: string } | null;
  deduccion_efectuada: PublicDecimal;
  schema_version: string;
};

export type CapitalGoodsListResult = {
  profile_id: string;
  rows: CapitalGood[];
};

export type CapitalGoodDeclareRequest = {
  identifier: string;
  description: string;
  acquisition_year: number;
  acquisition_ledger_id: string;
  cuota_soportada: PublicDecimal;
  prorrata_inicial_pct: PublicDecimal;
  kind: string;
  art108_elegible?: boolean;
  prorrata_sector_id?: string | null;
  disposal_year?: number | null;
  disposal_regime?: string | null;
};

export type CapitalGoodDeclareResult = {
  outcome: "declared" | "refused";
  profile_id: string;
  record: CapitalGood | null;
  count: number | null;
  refusal: {
    code: string;
    reason: "validation" | "disposal_incomplete" | "duplicate_identifier";
    missing: "year" | "regime" | null;
    identifier: string | null;
  } | null;
};
