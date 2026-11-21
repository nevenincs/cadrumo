import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  askedAgain,
  modelListState,
  modelListStateWords,
} from "../../shell/modelListState";
import { useStrings } from "../../shell/strings";

/**
 * What a view that lists models says when its read did not answer with the
 * models: where the person's setup stands, with asking again where that is
 * the way on, or, for a fault, `fault` with its retry. A state that moves on
 * by itself offers no control: the view reads again on its cue.
 */
export function ModelListNotice({
  code,
  fault,
  onRetry,
  slot,
}: {
  /** The refusal the read answered. */
  code: string;
  /** What a fault is said with. */
  fault: string;
  onRetry?: () => void;
  /** The `data-slot` the notice carries. */
  slot?: string;
}) {
  const t = useStrings();
  const state = modelListState(code);
  const retry = onRetry && (state === null || askedAgain(state)) && (
    <Button
      variant="outline"
      size="sm"
      className="justify-self-start"
      onClick={onRetry}
    >
      {t("desktop.agent.retry")}
    </Button>
  );
  return state === null ? (
    <div
      role="alert"
      data-slot={slot}
      data-model-list-fault={code}
      className="grid gap-2 text-sm"
    >
      <p className="flex items-start gap-2">
        <Icon name="alert" className="mt-0.5 text-destructive" />
        <span>{fault}</span>
      </p>
      {retry}
    </div>
  ) : (
    <div
      role="status"
      data-slot={slot}
      data-model-list-state={state}
      className="grid gap-2 text-sm text-muted-foreground"
    >
      <p className="flex items-start gap-2">
        <Icon name="info" className="mt-0.5" />
        <span>{modelListStateWords(t, state)}</span>
      </p>
      {retry}
    </div>
  );
}
