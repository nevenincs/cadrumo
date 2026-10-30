import { useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useStrings } from "../../../shell/strings";
import { amountText, dateText } from "../movements/movementWords";
import { AssetForm, useProvisionalRead, type ActProps } from "./AssetForm";
import { staleClaims } from "./assetWrites";

/**
 * Corrects an element's tax facts or its method: a superseding revision, never
 * an edit of the last. The effective claims that no longer match the schedule
 * are offered to be recorded again under the corrected figures, in the same
 * write, so a failed correction leaves them as they were. Method changes
 * apply from a tax year the person states.
 */
export function CorrectForm(props: ActProps & { assetId: string }) {
  const { port, reader, locale, assetId } = props;
  const t = useStrings();
  const plan = useProvisionalRead(
    port,
    reader,
    "ledger.actividad-asset.plan",
    { asset_id: assetId },
    assetId,
  );
  const stale =
    plan.read?.kind === "done" ? staleClaims(plan.read.result.rows) : [];
  // Each is chosen until the person unchooses it.
  const [declined, setDeclined] = useState<ReadonlySet<string>>(new Set());
  const chosen = stale
    .map((entry) => entry.claim.claim_id)
    .filter((id) => !declined.has(id));
  return (
    <AssetForm {...props} kind="correction" supersede={chosen}>
      {stale.length > 0 && (
        <fieldset className="ledger-asset-supersede-claims flex flex-col gap-1.5">
          <legend className="mb-1 text-sm text-muted-foreground">
            {t("desktop.ledger.assets.correct.supersede")}
          </legend>
          {stale.map(({ year, claim }) => (
            <Label key={claim.claim_id} className="items-start text-foreground">
              <Checkbox
                className="mt-0.5"
                checked={!declined.has(claim.claim_id)}
                onChange={(event) =>
                  setDeclined((current) => {
                    const next = new Set(current);
                    if (event.target.checked) next.delete(claim.claim_id);
                    else next.add(claim.claim_id);
                    return next;
                  })
                }
              />
              {t("desktop.ledger.assets.correct.claim_item", {
                year,
                amount: claim.amount
                  ? amountText(locale, claim.amount.decimal)
                  : "—",
                from: dateText(locale, claim.from, true),
                until: dateText(locale, claim.until, true),
              })}
            </Label>
          ))}
        </fieldset>
      )}
    </AssetForm>
  );
}
