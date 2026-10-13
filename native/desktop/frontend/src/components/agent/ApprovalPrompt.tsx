import { useId } from "react";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import type {
  AgentApproval,
  AgentApprovalOption,
} from "../../shell/agentSession";
import { offeredOptions } from "../../shell/agentPermission";
import { toolKindWords } from "../../shell/agentWords";
import { useStrings, type Translate } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";

/** Refusals first, and allowing once last, nearest the hand. The kind of an
 * option decides this, never its name or where the agent lists it. */
const ORDER: readonly AgentApprovalOption["kind"][] = [
  "reject_always",
  "reject_once",
  "allow_always",
  "allow_once",
];

/** What an option does, in our words, for an option that has no name. The
 * words for an "always" option promise no persistence: cadrumo-agent applies a
 * decision to the call it was asked about and keeps nothing (it answers an
 * "always" with the once-only option, `_narrowed_to_one_use`), so an option
 * that persists a grant is worded by the name whoever serves it gives it. */
function kindWords(t: Translate, kind: AgentApprovalOption["kind"]): string {
  switch (kind) {
    case "allow_once":
      return t("desktop.agent.approval_allow_once");
    case "allow_always":
      return t("desktop.agent.approval_allow_always");
    case "reject_once":
      return t("desktop.agent.approval_reject_once");
    case "reject_always":
      return t("desktop.agent.approval_reject_always");
  }
}

/**
 * A decision a reply waits on: a tool the agent wants to use, or a Cadrumo
 * operation to review before it commits. It says what would run, and offers
 * the options the agent offers, each under its own name; an option that would
 * be remembered is left out while one that answers this call alone is
 * offered. Only a press of one of them decides: none is chosen beforehand,
 * none has the focus, and no key answers for the person. The kind of an
 * option decides its place and its emphasis: refusals come first and allowing
 * once is the primary action. Of the call, the agent says its name and little
 * else; no arguments are shown because none are served.
 */
export function ApprovalPrompt({
  source,
  toolCall,
  toolKind,
  description,
  options,
  onDecide,
}: {
  source: AgentApproval["source"];
  /** What would run, as the agent names it. */
  toolCall?: string | null;
  /** What kind of tool it is, one of the agent's ten. */
  toolKind?: AgentApproval["tool_kind"];
  description?: string | null;
  options: readonly AgentApprovalOption[];
  /** The option the person chose. Without it, every option says it is not
   * available. */
  onDecide?: (optionId: string) => void;
}) {
  const t = useStrings();
  const headingId = useId();
  // A stable sort: options of one kind keep the order the agent gave them.
  const ordered = offeredOptions(options).sort(
    (a, b) => ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind),
  );
  return (
    <section
      aria-labelledby={headingId}
      className="agent-approval grid max-h-[60dvh] gap-3 overflow-y-auto rounded-xl border border-border-strong bg-card p-3.5 text-card-foreground shadow-raised"
    >
      <div className="flex items-start gap-2">
        <Icon
          name={source === "agent_tool" ? "agent" : "lock"}
          size="md"
          className="mt-0.5 text-muted-foreground"
        />
        <div className="grid min-w-0 gap-1">
          <h3 id={headingId} className="font-semibold text-foreground">
            {source === "agent_tool"
              ? t("desktop.agent.approval_tool_title")
              : t("desktop.agent.approval_review_title")}
          </h3>
          {(toolCall || toolKind) && (
            <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
              {toolCall && (
                <p className="font-medium text-foreground wrap-anywhere">
                  {toolCall}
                </p>
              )}
              {toolKind && <Badge>{toolKindWords(t, toolKind)}</Badge>}
            </div>
          )}
          {description && (
            <p className="text-sm whitespace-pre-wrap text-muted-foreground wrap-anywhere">
              {description}
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap justify-end gap-2">
        {ordered.map((option) => (
          <AgentTextAction
            key={option.option_id}
            variant={option.kind === "allow_once" ? "primary" : "outline"}
            size="sm"
            // An agent's own name can run to 128 characters.
            className="h-auto min-h-control-sm max-w-full py-1 text-left whitespace-normal wrap-anywhere"
            onAction={onDecide ? () => onDecide(option.option_id) : undefined}
          >
            {option.name?.trim() ? option.name : kindWords(t, option.kind)}
          </AgentTextAction>
        ))}
      </div>
    </section>
  );
}
