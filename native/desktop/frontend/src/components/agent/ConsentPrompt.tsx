import { useId } from "react";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";

/** One thing that would leave the computer, as the person should read it. */
export type ConsentItem = { id: string; label: string };

/**
 * The question asked before private content goes to an external provider.
 * It names the provider, the model and every item that would be sent, and
 * sending takes a deliberate press of its own: nothing is chosen for the
 * person, and nothing is sent while the question stands. Offering the wider
 * answers is the caller's: an answer without its handler is not shown.
 */
export function ConsentPrompt({
  providerName,
  modelName,
  contentItems,
  warning,
  onAllow,
  onAllowSession,
  onAllowRemember,
  onDecline,
}: {
  providerName: string;
  modelName: string;
  /** What would be sent, each item worded in full by the caller. */
  contentItems: readonly ConsentItem[];
  /** What this question adds to what would be sent, in the caller's words. */
  warning?: string;
  onAllow?: () => void;
  onAllowSession?: () => void;
  onAllowRemember?: () => void;
  onDecline?: () => void;
}) {
  const t = useStrings();
  const titleId = useId();
  const itemsId = useId();
  return (
    <section
      aria-labelledby={titleId}
      className="grid gap-3 rounded-xl bg-card p-3.5 text-card-foreground shadow-raised"
    >
      <div className="flex items-start gap-2">
        <Icon name="lock" size="md" className="mt-0.5 text-muted-foreground" />
        <div className="grid gap-1">
          <h3 id={titleId} className="font-semibold text-foreground">
            {t("desktop.agent.consent_title", { provider: providerName })}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t("desktop.agent.consent_lead", {
              model: modelName,
              provider: providerName,
            })}
          </p>
        </div>
      </div>
      <div className="grid gap-1">
        <p id={itemsId} className="text-xs font-medium text-muted-foreground">
          {t("desktop.agent.consent_items")}
        </p>
        <ul
          aria-labelledby={itemsId}
          className="grid list-disc gap-0.5 pl-5 text-sm text-foreground"
        >
          {contentItems.map((item) => (
            <li key={item.id}>{item.label}</li>
          ))}
        </ul>
      </div>
      {warning && <p className="text-sm text-foreground">{warning}</p>}
      <p className="text-xs text-muted-foreground">
        {t("desktop.agent.consent_note")} {t("desktop.agent.consent_recall")}
      </p>
      <div className="flex flex-wrap justify-end gap-2">
        <AgentTextAction variant="outline" size="sm" onAction={onDecline}>
          {t("desktop.agent.consent_decline")}
        </AgentTextAction>
        {onAllowRemember && (
          <AgentTextAction
            variant="outline"
            size="sm"
            onAction={onAllowRemember}
          >
            {t("desktop.agent.consent_allow_remember")}
          </AgentTextAction>
        )}
        {onAllowSession && (
          <AgentTextAction
            variant="outline"
            size="sm"
            onAction={onAllowSession}
          >
            {t("desktop.agent.consent_allow_session")}
          </AgentTextAction>
        )}
        <AgentTextAction variant="primary" size="sm" onAction={onAllow}>
          {t("desktop.agent.consent_allow", { provider: providerName })}
        </AgentTextAction>
      </div>
    </section>
  );
}
