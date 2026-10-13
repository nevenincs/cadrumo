import { useId } from "react";
import { Icon } from "@/components/ui/icon";
import { useStrings, type Translate } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";

/** What a decision would let happen, once or from now on. */
export type ApprovalKind =
  "allow_once" | "allow_always" | "reject_once" | "reject_always";

export type ApprovalOption = { id: string; kind: ApprovalKind };

/** Refusals first, and allowing once last, nearest the hand. */
const ORDER: readonly ApprovalKind[] = [
  "reject_always",
  "reject_once",
  "allow_always",
  "allow_once",
];

function optionWords(t: Translate, kind: ApprovalKind): string {
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
 * operation to review before it commits. It says what would run, and only
 * a press of one of its buttons decides; none is chosen beforehand.
 */
export function ApprovalPrompt({
  source,
  title,
  description,
  options,
  onDecide,
}: {
  source: "agent_tool" | "cadrumo_review";
  /** What would run, as its source names it. */
  title: string;
  description: string;
  options: readonly ApprovalOption[];
  /** The option the person chose. Without it, every option says it is not
   * available. */
  onDecide?: (optionId: string) => void;
}) {
  const t = useStrings();
  const headingId = useId();
  const ordered = [...options].sort(
    (a, b) => ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind),
  );
  return (
    <section
      aria-labelledby={headingId}
      className="agent-approval grid gap-3 rounded-xl border border-border-strong bg-card p-3.5 text-card-foreground shadow-raised"
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
          <p className="font-medium text-foreground wrap-anywhere">{title}</p>
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
            key={option.id}
            variant={option.kind === "allow_once" ? "primary" : "outline"}
            size="sm"
            onAction={onDecide ? () => onDecide(option.id) : undefined}
          >
            {optionWords(t, option.kind)}
          </AgentTextAction>
        ))}
      </div>
    </section>
  );
}
