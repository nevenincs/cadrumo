import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { SelectionChangeFacts } from "../../errors";
import { effortWords } from "../../shell/agentCatalog";
import type {
  ConversationCarry,
  SelectedModel,
} from "../../shell/agentGatewayContract";
import { useStrings, type Translate } from "../../shell/strings";

/** A model as the agent named it, with its effort where one was chosen. */
function modelWords(t: Translate, model: SelectedModel): string {
  return model.effort
    ? t("desktop.agent.model_with_effort", {
        model: model.model,
        effort: effortWords(t, model.effort),
      })
    : model.model;
}

/**
 * What is said over the composer about the lane and model a conversation
 * runs with: a message held back until the person confirms its change of
 * model, a new conversation about to carry another one's newest turns, or
 * what a carried conversation took over. The agent decides each and counts
 * what it gives; the column only says it and offers the person's answer.
 */
export function LaneSwitchNotice({
  changeAsk,
  carryFrom,
  carried,
  onConfirmChange,
  onWithdrawChange,
  onBackToSource,
}: {
  /** The refused change of model, as the agent stated it. */
  changeAsk: SelectionChangeFacts | null;
  /** The conversation a first message carries from, by its title where it
   * has one. */
  carryFrom: { title: string | null } | null;
  /** What the shown conversation took over when it began. */
  carried: ConversationCarry | null;
  onConfirmChange: () => void;
  onWithdrawChange: () => void;
  onBackToSource: () => void;
}) {
  const t = useStrings();
  const counts = new Intl.NumberFormat(t.locale);
  if (changeAsk) {
    const { previous, requested, history } = changeAsk;
    return (
      <div
        role="alert"
        data-slot="selection-change"
        className="flex items-start gap-2 text-sm"
      >
        <Icon name="alert" className="mt-0.5 text-warning" />
        <span className="grid justify-items-start gap-1.5">
          <span>
            {t("desktop.agent.selection_change_asked", {
              previous: modelWords(t, previous),
              requested: modelWords(t, requested),
            })}
          </span>
          <span className="text-muted-foreground">
            {t("desktop.agent.selection_change_history", {
              retained: counts.format(history.retained_messages),
              tokens: counts.format(history.estimated_tokens),
              omitted: counts.format(history.omitted_messages),
            })}
          </span>
          <span className="flex flex-wrap gap-1.5">
            <Button size="xs" onClick={onConfirmChange}>
              {t("desktop.agent.selection_change_confirm")}
            </Button>
            <Button variant="outline" size="xs" onClick={onWithdrawChange}>
              {t("desktop.agent.selection_change_keep")}
            </Button>
          </span>
        </span>
      </div>
    );
  }
  if (carryFrom)
    return (
      <p
        role="status"
        data-slot="carry-pending"
        className="flex items-start gap-2 text-sm text-muted-foreground"
      >
        <Icon name="info" className="mt-0.5" />
        <span className="grid justify-items-start gap-1.5">
          {carryFrom.title
            ? t("desktop.agent.carry_pending", { title: carryFrom.title })
            : t("desktop.agent.carry_pending_untitled")}
          <Button variant="outline" size="xs" onClick={onBackToSource}>
            {t("desktop.agent.carry_back")}
          </Button>
        </span>
      </p>
    );
  if (carried)
    return (
      <p
        role="status"
        data-slot="carried"
        className="flex items-start gap-2 text-sm text-muted-foreground"
      >
        <Icon name="info" className="mt-0.5" />
        <span>
          {t("desktop.agent.carried_turns", {
            carried: counts.format(carried.carried_turns),
            omitted: counts.format(carried.omitted_turns),
          })}
        </span>
      </p>
    );
  return null;
}
