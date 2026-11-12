import { LEDGER_DEFINITIONS } from "./ledger";
import { MODELO_DEFINITIONS } from "./modeloContract/contracts";
import { placeIn, type WindowPlace } from "./refusal";

/** The window place hosting a served action's operation, over the closed
 * lists of definitions the host admits; null when the window admits none. */
export function routeAction(
  target_command_key: string | null | undefined,
): WindowPlace | null {
  return placeIn(target_command_key, {
    ledger: LEDGER_DEFINITIONS,
    declarations: MODELO_DEFINITIONS,
  });
}
