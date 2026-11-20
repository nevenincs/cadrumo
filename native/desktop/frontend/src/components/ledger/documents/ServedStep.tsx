import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { isProfileStep } from "../../../shell/ledger";
import type { OperationNextStepV1 } from "../../../shell/ledgerDocumentContract";
import { useModelList } from "../../../shell/agentModelList";
import { useProfileStepDoor } from "../../../shell/profileStepDoor";

/** The control a refusal's served step leads to where this window answers the
 * step, labelled with the words the backend served: the model picker of the
 * agent column for `choose_reading_model`, the profile page for a step that
 * puts the profile right. Nothing for any other step, for none, or where the
 * window offers no door to it. */
export function ServedStep({
  step,
  className,
}: {
  step: OperationNextStepV1 | null | undefined;
  className?: string;
}) {
  const models = useModelList();
  const profile = useProfileStepDoor();
  if (!step) return null;
  if (step.kind === "choose_reading_model" && models !== null)
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
  if (isProfileStep(step) && profile !== null)
    return (
      <Button
        size="xs"
        variant="outline"
        className={cn("ledger-profile-step", className)}
        onClick={() => profile(step)}
      >
        <Icon name="person" />
        {step.words}
      </Button>
    );
  return null;
}
