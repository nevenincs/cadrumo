import type { PublicModeloFormField } from "../../../shell/modeloContract";
import type { PlacedField } from "../form/session";

// Which boxes of a form are credits a register supplies, and which boxes
// read them. Both come from what the form served: a box's source policy names
// the area it is corrected in, and a calculated box names the boxes its
// formula reads. Nothing here knows a box number or what a credit is.

/** The area the withholding records are kept and corrected in. */
const REGISTER_SURFACE = "withholding";

/** The boxes whose figure the withholding register supplies, in the order the
 * form draws them. */
export function creditFields(
  placed: readonly PlacedField[],
): PublicModeloFormField[] {
  return placed
    .map(({ field }) => field)
    .filter((field) =>
      field.bindings.some((b) => b.policy.surface === REGISTER_SURFACE),
    );
}

/** The calculated boxes that read a credit, directly or through another
 * calculated box, in the order the form draws them. A box with no printed
 * number is not listed: there is nothing to name it by. */
export function dependentFields(
  placed: readonly PlacedField[],
  credits: readonly PublicModeloFormField[],
): PublicModeloFormField[] {
  const reading = new Set(
    credits.flatMap((field) => (field.box ? [field.box] : [])),
  );
  const found: PublicModeloFormField[] = [];
  // A box can read one that is drawn after it, so repeat until nothing joins.
  for (let joined = true; joined; ) {
    joined = false;
    for (const { field } of placed) {
      if (!field.box || reading.has(field.box)) continue;
      if (!field.formula_operands.some((operand) => reading.has(operand)))
        continue;
      reading.add(field.box);
      found.push(field);
      joined = true;
    }
  }
  const order = new Map(placed.map(({ field }, at) => [field, at]));
  return found.sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0));
}
