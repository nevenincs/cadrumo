import type {
  ModeloFormCredit,
  PublicModeloFormField,
} from "../../../shell/modeloContract/modeloWorkForm";
import { addressKey, type PlacedField } from "../form/session";

// The credits the withholding register supplies and the boxes worked out
// from them, as the form served them. The application names both; this only
// finds the boxes it named among those the form draws, in the form's order.

export type CreditBoxes = {
  /** The boxes the register supplies, in the order the form draws them. */
  credits: PublicModeloFormField[];
  /** The boxes worked out from any credit, in the order the form draws them;
   * null when the application could not say which they are, which is not
   * the same as none. */
  dependents: PublicModeloFormField[] | null;
};

export function creditBoxes(
  placed: readonly PlacedField[],
  served: readonly ModeloFormCredit[],
): CreditBoxes {
  const credited = new Set(served.map((credit) => addressKey(credit.address)));
  const known = served.every((credit) => credit.dependents !== null);
  const reading = new Set(
    served.flatMap((credit) => (credit.dependents ?? []).map(addressKey)),
  );
  const fields = placed.map(({ field }) => field);
  return {
    credits: fields.filter((field) => credited.has(addressKey(field.address))),
    dependents: known
      ? fields.filter((field) => reading.has(addressKey(field.address)))
      : null,
  };
}
