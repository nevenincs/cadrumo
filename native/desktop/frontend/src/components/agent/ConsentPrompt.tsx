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
 * person, and nothing is sent while the question stands.
 */
export function ConsentPrompt({
  providerName,
  modelName,
  contentItems,
  onAllow,
  onDecline,
}: {
  providerName: string;
  modelName: string;
  /** What would be sent, each item worded in full by the caller. */
  contentItems: readonly ConsentItem[];
  onAllow?: () => void;
  onDecline?: () => void;
}) {
  const t = useStrings();
  const titleId = useId();
  const itemsId = useId();
  return (
    <section
      aria-labelledby={titleId}
      className="grid gap-3 rounded-xl border border-border-strong bg-card p-3.5 text-card-foreground shadow-raised"
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
      <p className="text-xs text-muted-foreground">
        {t("desktop.agent.consent_note")}
      </p>
      <div className="flex flex-wrap justify-end gap-2">
        <AgentTextAction variant="outline" size="sm" onAction={onDecline}>
          {t("desktop.agent.consent_decline")}
        </AgentTextAction>
        <AgentTextAction variant="primary" size="sm" onAction={onAllow}>
          {t("desktop.agent.consent_allow", { provider: providerName })}
        </AgentTextAction>
      </div>
    </section>
  );
}
