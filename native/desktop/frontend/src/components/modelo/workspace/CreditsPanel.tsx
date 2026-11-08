import { useMemo } from "react";
import type { LedgerWorkStep } from "../../../shell/ledger";
import type { ModeloFormAddressV1 } from "../../../shell/modeloContract/modeloEditWork";
import type {
  ModeloFormIssueLine,
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import type { OpenableSurface } from "../details/Details";
import { Credits } from "./CreditsView";
import { creditBoxes } from "./creditBoxes";
import { Estimate } from "./EstimateView";
import {
  estimateFigure,
  observedValue,
  type EstimateRead,
} from "./estimateRead";
import type { FormSession } from "../form/session";
import { hasIvaWallet } from "./ivaWalletRead";
import { IvaWallet } from "./IvaWallet";
import { ledgerPeriod } from "../../../shell/ledgerPeriods";

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
  onAnswer = null,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  session: FormSession;
  /** The estimate as asked for so far, how to ask, and how to run the step a
   * refusal names; held by the workspace so it stays when another view is
   * shown. */
  estimate: {
    read: EstimateRead;
    ask: (() => void) | null;
    take: ((step: LedgerWorkStep) => void) | null;
  };
  locale: string;
  onGo(address: ModeloFormAddressV1): void;
  onOpenSurface(surface: OpenableSurface): void;
  canOpenSurface(surface: OpenableSurface): boolean;
  /** Opens the answer a disagreement's line offers, or null while none can
   * be sent from here. */
  onAnswer?: ((line: ModeloFormIssueLine) => void) | null;
}) {
  const t = useStrings();
  const form = envelope.form.form;
  // The period the form serves, as the periods store holds one; a code it
  // cannot hold leaves the wallet unshown rather than guessed.
  const walletPeriod = ledgerPeriod(form.period);
  const served = form.withholding_credits;
  const { credits, dependents } = useMemo(
    () => creditBoxes(session.placed, served),
    [session.placed, served],
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
    <div className="flex flex-col gap-8">
      {credits.length > 0 && (
        <Credits
          credits={credits}
          dependents={dependents}
          lines={envelope.issue_lines}
          onGo={onGo}
          onOpenSurface={onOpenSurface}
          canOpenSurface={canOpenSurface}
          extraOf={inEstimate}
          onAnswer={onAnswer}
          estimate={
            <Estimate
              read={estimate.read}
              onAsk={estimate.ask}
              onStep={estimate.take}
              locale={locale}
              fieldAt={session.fieldAt}
              results={form.result_addresses}
            />
          }
        />
      )}
      {hasIvaWallet(envelope) && walletPeriod !== null && (
        <IvaWallet period={walletPeriod} locale={locale} />
      )}
    </div>
  );
}
