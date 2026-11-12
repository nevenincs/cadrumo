import { useId } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  refusalControls,
  refusalSentences,
  type RefusalIntent,
  type ServedRefusal,
} from "../shell/refusal";
import { routeAction } from "../shell/refusalRoute";
import { useStrings } from "../shell/strings";

/**
 * One refusal, as served: the refusal words, then the primary way out as the
 * primary control and the further ways out after it in served order, or the
 * sentence saying there is none. An action the backend served no words for
 * gets no control. An action the window admits no place for is shown with its
 * words, disabled, beside one generic reason. The notice never submits: each
 * control hands `onAction` the intent to open its destination.
 */
export function RefusalNotice({
  refusal,
  onAction,
}: {
  refusal: ServedRefusal;
  onAction: (intent: RefusalIntent) => void;
}) {
  const t = useStrings();
  const reason = useId();
  const sentences = refusalSentences(refusal);
  const controls = refusalControls(refusal.verdict, routeAction);
  const unroutable = controls.some((control) => control.intent === null);
  const outcome = refusal.verdict?.no_recovery_outcome ?? undefined;
  if (!sentences.refusal && !sentences.noRecovery && controls.length === 0)
    return null;
  return (
    <Alert
      tone="warning"
      role="alert"
      icon={<Icon name="refused" />}
      data-slot="refusal-notice"
      data-no-recovery={outcome}
    >
      {sentences.refusal && (
        <p lang={sentences.refusal.language ?? undefined}>
          {sentences.refusal.words}
        </p>
      )}
      {sentences.noRecovery && (
        <p lang={sentences.noRecovery.language ?? undefined}>
          {sentences.noRecovery.words}
        </p>
      )}
      {controls.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {controls.map((control, index) => {
            const intent = control.intent;
            return (
              <Button
                key={`${control.role}-${index}`}
                size="sm"
                variant={control.role === "primary" ? "primary" : "outline"}
                lang={control.language ?? undefined}
                data-role={control.role}
                data-conditional={control.conditional || undefined}
                aria-disabled={intent === null || undefined}
                aria-describedby={intent === null ? reason : undefined}
                onClick={intent === null ? undefined : () => onAction(intent)}
              >
                {control.words}
                {control.conditional && <Icon name="more" />}
              </Button>
            );
          })}
        </div>
      )}
      {unroutable && (
        <p id={reason} className="text-sm text-muted-foreground">
          {t("desktop.refusal.action_unroutable")}
        </p>
      )}
    </Alert>
  );
}
