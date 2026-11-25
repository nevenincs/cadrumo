import { LEDGER_DEFINITIONS } from "./ledger";
import { MODELO_DEFINITIONS } from "./modeloContract/contracts";
import { placeIn, type WindowPlace } from "./refusal";

/** The window place hosting a served action, by the first of its served
 * operations the host admits; null when the window admits none. */
export function routeAction(
  target_operation_ids: readonly string[],
): WindowPlace | null {
  return placeIn(target_operation_ids, {
    ledger: LEDGER_DEFINITIONS,
    declarations: MODELO_DEFINITIONS,
  });
}
