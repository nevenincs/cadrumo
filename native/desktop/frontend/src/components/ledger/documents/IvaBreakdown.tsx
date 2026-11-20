import { facts, labelled } from "../../../shell/compose";
import type { InvoiceDraftRateBreakdownProjectionV1 } from "../../../shell/ledgerDocumentReviewContract";
import type { Translate } from "../../../shell/strings";
import { formatAmount, formatPercent } from "../../../shared/numbers";
import { fieldLabel } from "./documentWords";

/** The IVA a reading states rate by rate: each rate with the base it applies
 * to and the cuota it gives, and any recargo, as the invoice declares them.
 * Nothing is added up or checked here. */
export function IvaBreakdown({
  t,
  locale,
  rows,
}: {
  t: Translate;
  locale: string;
  rows: readonly InvoiceDraftRateBreakdownProjectionV1[];
}) {
  const amount = (
    field: Parameters<typeof fieldLabel>[1],
    value: string | null,
  ) =>
    value === null
      ? null
      : labelled(t, fieldLabel(t, field), formatAmount(locale, value));
  return (
    <ul className="ledger-draft-breakdown grid gap-0.5 tabular-nums">
      {rows.map((row, at) => (
        <li key={at} className="ledger-draft-breakdown-rate">
          {facts(t, [
            row.iva_rate
              ? formatPercent(locale, row.iva_rate.decimal, { unit: "points" })
              : null,
            amount("taxable_base", row.taxable_base?.decimal ?? null),
            amount("iva_amount", row.iva_amount?.decimal ?? null),
            amount("recargo_amount", row.recargo_amount?.decimal ?? null),
          ])}
        </li>
      ))}
    </ul>
  );
}
