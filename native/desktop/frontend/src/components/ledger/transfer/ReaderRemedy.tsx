import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import type { OperationNextStepV1 } from "../../../shell/ledgerDocumentContract";
import { useProvisioning } from "../../../shell/provisioning";
import { setupActionOf } from "../../../shell/provisioningRecovery";
import { useStrings } from "../../../shell/strings";
import { ServedStep } from "../documents/ServedStep";
import { SetupOffer } from "../../setup/SetupOffer";
import { itemName } from "../../setup/setupWords";

/** Beside a file the import could not read: the way to put its reader
 * right. The step the backend served leads where it says, such as to the
 * agent's model picker; a setup the provisioning panel can act on is
 * offered from its row. A local AI that is set up yet could not read the
 * file still leads to its element of the panel, where its program, its
 * models and their states are shown, so a reader that is not ready is never
 * left without a way in. Nothing is offered where the window offers no
 * setup or the status cannot be read. */
export function ReaderRemedy({
  setup,
  step,
  className,
}: {
  /** The setup action the refusal names; null for none. */
  setup: string | null;
  /** The step the backend served for the refusal; null for none. */
  step: OperationNextStepV1 | null;
  className?: string;
}) {
  const t = useStrings();
  const recovery = useProvisioning();
  if (step) return <ServedStep step={step} className={className} />;
  if (setup === null) return null;
  if (recovery.targetOf(setup) !== null)
    return <SetupOffer action={setup} className={className} />;
  const row = recovery.localAiRow;
  if (!recovery.offered || row === null || setup !== setupActionOf("local_ai"))
    return null;
  return (
    <span
      className={cn(
        "ledger-reader-setup inline-flex flex-wrap items-center gap-2",
        className,
      )}
    >
      <span className="font-medium text-foreground">
        {itemName(t, row.item)}
      </span>
      <Button
        size="xs"
        variant="outline"
        onClick={() => recovery.open(row.item)}
      >
        <Icon name="settings" />
        {t("desktop.setup.open")}
      </Button>
    </span>
  );
}
