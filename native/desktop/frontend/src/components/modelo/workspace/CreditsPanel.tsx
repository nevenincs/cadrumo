import { useMemo } from "react";
import type {
  ModeloFormAddressV1,
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../../../shell/modeloContract";
import { useStrings } from "../../../shell/strings";
import type { OpenableSurface } from "../details/Details";
import { Credits } from "./CreditsView";
import { creditFields, dependentFields } from "./creditBoxes";
import { Estimate } from "./EstimateView";
import {
  estimateFigure,
  observedValue,
  type EstimateRead,
} from "./estimateRead";
import type { FormSession } from "../form/session";

/**
 * The credits view of one declaration: the boxes a register supplies and the
 * boxes that read them, and the estimate from the quarterly declarations,
 * which is asked for here and changes nothing in the declaration.
 */
export function CreditsPanel({
  envelope,
  session,
  estimate,
  locale,
  onGo,
  onOpenSurface,
  canOpenSurface,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  session: FormSession;
  /** The estimate as asked for so far, and how to ask; held by the workspace
   * so it stays when another view is shown. */
  estimate: { read: EstimateRead; ask: (() => void) | null };
  locale: string;
  onGo(address: ModeloFormAddressV1): void;
  onOpenSurface(surface: OpenableSurface): void;
  canOpenSurface(surface: OpenableSurface): boolean;
}) {
  const t = useStrings();
  const form = envelope.form.form;
  const credits = useMemo(() => creditFields(session.placed), [session.placed]);
  const dependents = useMemo(
    () => dependentFields(session.placed, credits),
    [session.placed, credits],
  );
  const projection =
    estimate.read.phase === "ready" ? estimate.read.projection : null;
  const inEstimate = (field: PublicModeloFormField) => {
    const value = projection && observedValue(projection, field.box);
    return value === null || value === undefined ? null : (
      <span data-in-estimate="" className="text-sm text-muted-foreground">
        {t("desktop.modelo.credits.estimate.in_estimate", {
          amount: estimateFigure(locale, field, value),
        })}
      </span>
    );
  };
  return (
    <Credits
      credits={credits}
      dependents={dependents}
      lines={envelope.issue_lines}
      onGo={onGo}
      onOpenSurface={onOpenSurface}
      canOpenSurface={canOpenSurface}
      extraOf={inEstimate}
      estimate={
        <Estimate
          read={estimate.read}
          onAsk={estimate.ask}
          locale={locale}
          fieldAt={session.fieldAt}
          results={form.result_addresses}
          onOpenSurface={onOpenSurface}
          canOpenSurface={canOpenSurface}
        />
      }
    />
  );
}
