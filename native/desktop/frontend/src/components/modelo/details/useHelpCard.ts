import { useEffect, useState } from "react";
import { ledgerFailure, type LedgerFailureCode } from "../../../shell/ledger";
import type { ModeloPort } from "../../../shell/modelo";
import type {
  ModeloCasillaHelpCardV1,
  ModeloWorkbenchFormProjectionV1,
  OutputLanguage,
} from "../../../shell/modeloContract";

// The help card of the chosen box, read when the box is chosen and held in
// this component's memory for the revision, calculation and language the
// form was read in, so a recalculated form reads it again.

export type HelpCardRead =
  | { kind: "reading" }
  | { kind: "ready"; card: ModeloCasillaHelpCardV1 }
  | { kind: "failed"; code: LedgerFailureCode };

/** The card for `casillaId` as the form `envelope` showed it, or null where
 * the chosen box is not a casilla (a binding has no card). */
export function useHelpCard(
  port: ModeloPort,
  envelope: ModeloWorkbenchFormProjectionV1,
  casillaId: string | null,
  language: OutputLanguage,
): HelpCardRead | null {
  const key =
    casillaId === null
      ? null
      : [
          envelope.work_unit_id,
          envelope.registry_revision_id,
          envelope.calculation_revision_id ?? "",
          language,
          casillaId,
        ].join("\u0000");
  const [held, setHeld] = useState<{ key: string; read: HelpCardRead } | null>(
    null,
  );
  const workUnitId = envelope.work_unit_id;
  const registryRevisionId = envelope.registry_revision_id;
  const calculationRevisionId = envelope.calculation_revision_id;
  useEffect(() => {
    if (key === null || casillaId === null) return;
    let active = true;
    void (async () => {
      let read: HelpCardRead;
      try {
        const projection = await port.casillaHelp({
          workUnitId,
          casillaId,
          registryRevisionId,
          calculationRevisionId,
          language,
        });
        read = { kind: "ready", card: projection.card };
      } catch (error) {
        read = { kind: "failed", code: ledgerFailure(error).code };
      }
      if (active) setHeld({ key, read });
    })();
    return () => {
      active = false;
    };
  }, [
    port,
    key,
    casillaId,
    workUnitId,
    registryRevisionId,
    calculationRevisionId,
    language,
  ]);
  if (key === null) return null;
  return held?.key === key ? held.read : { kind: "reading" };
}
