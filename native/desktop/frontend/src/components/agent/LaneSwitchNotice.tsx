import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { SelectionChangeFacts } from "../../errors";
import { effortWords } from "../../shell/agentCatalog";
import type {
  ConversationCarry,
  SelectedModel,
} from "../../shell/agentGatewayContract";
import { countWords, useStrings, type Translate } from "../../shell/strings";

/** A model as the picker names it, with its effort where one was chosen. */
function modelWords(
  t: Translate,
  model: SelectedModel,
  modelName: (model: string) => string,
): string {
  const name = modelName(model.model);
  return model.effort
    ? t("desktop.agent.model_with_effort", {
        model: name,
        effort: effortWords(t, model.effort),
      })
    : name;
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
  modelName,
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
  /** A model's name as the picker shows it, from the id a run names. */
  modelName: (model: string) => string;
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
              previous: modelWords(t, previous, modelName),
              requested: modelWords(t, requested, modelName),
            })}
          </span>
          <span className="text-muted-foreground">
            {countWords(
              t,
              history.retained_messages,
              {
                one: "desktop.agent.selection_change_retained_one",
                other: "desktop.agent.selection_change_retained",
              },
              {
                retained: counts.format(history.retained_messages),
                tokens: counts.format(history.estimated_tokens),
              },
            )}{" "}
            {countWords(
              t,
              history.omitted_messages,
              {
                one: "desktop.agent.selection_change_omitted_one",
                other: "desktop.agent.selection_change_omitted",
              },
              { omitted: counts.format(history.omitted_messages) },
            )}
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
          {countWords(
            t,
            carried.carried_turns,
            {
              one: "desktop.agent.carried_turns_one",
              other: "desktop.agent.carried_turns",
            },
            { carried: counts.format(carried.carried_turns) },
          )}{" "}
          {countWords(
            t,
            carried.omitted_turns,
            {
              one: "desktop.agent.carried_omitted_one",
              other: "desktop.agent.carried_omitted",
            },
            { omitted: counts.format(carried.omitted_turns) },
          )}
        </span>
      </p>
    );
  return null;
}
