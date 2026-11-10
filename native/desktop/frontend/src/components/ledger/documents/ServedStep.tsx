import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import type { LedgerNextStep } from "../../../shell/ledger";
import { useModelList } from "../../../shell/agentModelList";

/** The control a refusal's served step leads to where this window answers the
 * step: the model picker of the agent column for `choose_reading_model`,
 * labelled with the words the backend served. Nothing for any other step, for
 * none, or where the window offers no model picker. */
export function ServedStep({
  step,
  className,
}: {
  step: LedgerNextStep | null | undefined;
  className?: string;
}) {
  const models = useModelList();
  if (!step || step.kind !== "choose_reading_model" || models === null)
    return null;
  return (
    <Button
      size="xs"
      variant="outline"
      className={cn("ledger-reading-model-step", className)}
      onClick={() => models.open()}
    >
      <Icon name="settings" />
      {step.words}
    </Button>
  );
}
