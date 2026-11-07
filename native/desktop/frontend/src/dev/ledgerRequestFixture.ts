// What the scenario ledger's handlers share to decode a request: the
// refusal a call is rejected with, the shapes its fields take, and the
// columns and messages its answers cite. Everything it answers is synthetic.

import type {
  JsonValue,
  LedgerFailure,
  LedgerFailureCode,
} from "../shell/ledger";
import type { LedgerUpdateField } from "../shell/ledgerContract";

export const UPDATE_REQUIRED: readonly LedgerUpdateField[] = [
  "booked_date",
  "amount",
  "currency",
  "direction",
  "description",
  "notes",
];
export const DECIDED = ["BUSINESS", "PERSONAL", "MIXED"];
export const BULK_COLUMNS = [
  "transaction_id",
  "classification",
  "category_id",
  "business_pct",
  "usage_ratio_id",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "iva_category",
  "irpf_category",
  "notes",
];
/** A number with a wrong check digit, which the account register refuses; a test
 * in the owning Python package holds the backend to that answer. */
export const IBAN_THE_BACKEND_REFUSES = "ES9221000418450200051332";

export const OWN_ACCOUNT_SECRETS = [
  "iban",
  "swift_bic",
  "bank_name",
  "bank_address",
  "bank_city",
  "bank_country_code",
];
export const SEALED_MESSAGE =
  "A finalized Modelo 303 revision for 2026 1T cites this movement; correct it through an amendment.";

/** A rejected call, shaped as the host rejects one: its code, operation and
 * reason are the error's own fields, as `ledgerFailure` reads them. */
class Refusal extends Error {
  readonly code: LedgerFailureCode;
  readonly operation_id: string | null;
  readonly reason?: string;
  readonly terminal_failure?: LedgerFailure["terminal_failure"];
  constructor(readonly failure: LedgerFailure) {
    super(failure.code);
    this.code = failure.code;
    this.operation_id = failure.operation_id;
    if (failure.reason !== undefined) this.reason = failure.reason;
    if (failure.terminal_failure !== undefined)
      this.terminal_failure = failure.terminal_failure;
  }
}
export const reject = (
  code: LedgerFailureCode,
  extra: Partial<LedgerFailure> = {},
): never => {
  throw new Refusal({ code, operation_id: null, ...extra });
};
/** A request its registered contract would not decode. */
export const invalid = () => reject("refused", { reason: "invalid" });
/** A request the recordings behind the scenario hold no answer for. */
export const unrecorded = () => reject("refused", { reason: "unrecorded" });

export const text = (value: JsonValue | undefined) =>
  typeof value === "string" ? value : null;
export const AMOUNT = /^\d{1,12}(\.\d{1,2})?$/;
export const FRACTION = /^(0(\.\d{1,4})?|1(\.0{1,4})?)$/;
export const DATE = /^\d{4}-\d{2}-\d{2}$/;
// Single update and classify refuse a decimal that is not in its shortest
// spelling ("40.00", "0.50"), as their request models do; add and the bulk
// re-render what they read.
export const shortest = (value: string) => !/\.(\d*0)?$/.test(value);
