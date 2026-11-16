// The request a withholding certificate is recorded with. Field names are the
// registered Python contract's own, and the request leaves out the profile,
// which the host fills.

import type { FileToken, JsonValue } from "./ledger";
import type {
  WithholdingIncomeClass,
  WithholdingOrigin,
} from "./ledgerContract";

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
