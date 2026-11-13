import { cn } from "@/components/ui/cn";
import { Icon, type IconName } from "@/components/ui/icon";
import type {
  ModeloFormStepState,
  ModeloFormStepStatus,
} from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";

// The steps of filing one declaration and how far each has got, as the read
// model serves them. The order and every status are its; this draws a glyph
// for each status and the step's name, and works out none of them.

const STATUS_ICON: Record<ModeloFormStepStatus, IconName> = {
  done: "check",
  current: "forward",
  blocked: "refused",
  pending: "pending",
};

const STATUS_TONE: Record<ModeloFormStepStatus, string> = {
  done: "text-success",
  current: "text-foreground font-medium",
  blocked: "text-destructive",
  pending: "text-faint",
};

/** The served steps in the order served; the current one is marked as the
 * current step of the list. */
export function JourneySteps({
  steps,
}: {
  steps: readonly ModeloFormStepState[];
}) {
  const t = useStrings();
  return (
    <ol data-journey="" className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {steps.map(({ step, status }) => (
        <li
          key={step}
          data-step={step}
          data-status={status}
          aria-current={status === "current" ? "step" : undefined}
          className={cn(
            "flex items-center gap-1.5 text-sm",
            STATUS_TONE[status],
          )}
        >
          <Icon name={STATUS_ICON[status]} size="xs" />
          {t(`workspace.modelo.step.${step}`)}
        </li>
      ))}
    </ol>
  );
}
