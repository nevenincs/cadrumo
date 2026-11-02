import { useMemo } from "react";
import type { ModeloPort } from "../../../shell/modelo";
import type {
  ModeloFormAddressV1,
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../../../shell/modeloContract";
import { useStrings } from "../../../shell/strings";
import type { OpenableSurface } from "../details/Details";
import { Credits } from "./CreditsView";
import { creditFields, dependentFields } from "./credits";
import { Estimate } from "./EstimateView";
import {
  estimateFigure,
  observedValue,
  useEstimate,
  type SendWrite,
} from "./estimate";
import type { FormSession } from "../form/session";

/**
 * The credits view of one declaration: the boxes a register supplies and the
 * boxes that read them, and the estimate from the quarterly declarations,
 * which is asked for here and changes nothing in the declaration.
 */
export function CreditsPanel({
  envelope,
  session,
  port,
  run,
  readRegion,
  locale,
  onGo,
  onOpenSurface,
  canOpenSurface,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  session: FormSession;
  port: ModeloPort;
  run: SendWrite;
  /** Reads the region the profile states, or null where it states none; none
   * where this window has no profile to ask. */
  readRegion?: () => Promise<string | null>;
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
  const estimate = useEstimate({
    port,
    year: form.filing_year,
    region: readRegion,
    run,
  });
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
