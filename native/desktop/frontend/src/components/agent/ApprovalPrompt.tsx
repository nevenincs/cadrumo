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
  "allow_session",
  "allow_once",
];

/** Localized labels for the agent's canonical choices and unnamed options. */
function kindWords(t: Translate, kind: AgentApprovalOption["kind"]): string {
  switch (kind) {
    case "allow_once":
      return t("desktop.agent.approval_allow_once");
    case "allow_session":
      return t("desktop.agent.approval_allow_session");
    case "allow_always":
      return t("desktop.agent.approval_allow_always");
    case "reject_once":
      return t("desktop.agent.approval_reject_once");
    case "reject_always":
      return t("desktop.agent.approval_reject_always");
  }
}

/** The agent owns these stable option IDs. Custom review choices retain their
 * supplied wording; their scope cannot safely be inferred from English prose. */
function optionWords(
  t: Translate,
  source: AgentApproval["source"],
  option: AgentApprovalOption,
  server?: string | null,
): string {
  if (source === "agent_tool") {
    if (
      option.option_id === "allow_server_session" &&
      option.kind === "allow_session" &&
      server
    )
      return t("desktop.agent.approval_allow_server_session", { server });
    if (option.option_id === option.kind) return kindWords(t, option.kind);
  }
  return option.name?.trim() || kindWords(t, option.kind);
}

/** Remove only the exact generated repetition. Keep custom explanations and
 * complete targets, including the agent's escaped file/attachment names. */
function descriptionWords(
  t: Translate,
  source: AgentApproval["source"],
  tool: string | null | undefined,
  description: string | null | undefined,
): string | null | undefined {
  if (source !== "agent_tool" || !tool || !description) return description;
  const repeated = `Permission required: ${tool}`;
  if (description === repeated || description === tool) return null;
  const filePrefix = `${repeated}; workspace file path: `;
  if (description.startsWith(filePrefix))
    return t("desktop.agent.approval_workspace_file", {
      target: description.slice(filePrefix.length),
    });
  const attachmentPrefix = `${repeated}; attachment: `;
  if (description.startsWith(attachmentPrefix))
    return t("desktop.agent.approval_attachment", {
      target: description.slice(attachmentPrefix.length),
    });
  const operation = /^Cadrumo operation: ([a-z][a-z0-9_.-]{0,127})$/.exec(
    description,
  );
  if (operation)
    return t("desktop.agent.approval_operation", { target: operation[1]! });
  return description;
}

/**
 * A decision a reply waits on: a tool the agent wants to use, or a Cadrumo
 * operation to review before it commits. It says what would run, and offers
 * the options the agent offers, each under its own name; an option that would
 * persist beyond the run is left out while a bounded option is
 * offered. Only a press of one of them decides: none is chosen beforehand,
 * none has the focus, and no key answers for the person. The kind of an
 * option decides its place and its emphasis: refusals come first and allowing
 * once is the primary action. Of the call, the agent says its name and little
 * else; no arguments are shown because none are served.
 */
export function ApprovalPrompt({
  source,
  toolCall,
  toolServer,
  toolKind,
  description,
  options,
  onDecide,
  title,
}: {
  source: AgentApproval["source"];
  /** What would run, as the agent names it. */
  toolCall?: string | null;
  toolServer?: string | null;
  /** What kind of tool it is, one of the agent's ten. */
  toolKind?: AgentApproval["tool_kind"];
  description?: string | null;
  options: readonly AgentApprovalOption[];
  /** The option the person chose. Without it, every option says it is not
   * available. */
  onDecide?: (optionId: string) => void;
  title?: string;
}) {
  const t = useStrings();
  const headingId = useId();
  const detail = descriptionWords(t, source, toolCall, description);
  const showKind = toolKind && toolKind !== "other";
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
          {toolCall && (
            <p id={headingId} className="text-sm text-muted-foreground">
              {title ??
                (source === "agent_tool"
                  ? t("desktop.agent.approval_tool_title")
                  : t("desktop.agent.approval_review_title"))}
            </p>
          )}
          <h3
            id={toolCall ? undefined : headingId}
            className="text-base font-semibold text-foreground wrap-anywhere"
          >
            {toolCall ||
              title ||
              (source === "agent_tool"
                ? t("desktop.agent.approval_tool_title")
                : t("desktop.agent.approval_review_title"))}
          </h3>
          {(toolServer || showKind) && (
            <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
              {toolServer && <Badge>{toolServer}</Badge>}
              {showKind && <Badge>{toolKindWords(t, toolKind)}</Badge>}
            </div>
          )}
          {detail && (
            <p className="text-sm whitespace-pre-wrap text-muted-foreground wrap-anywhere">
              {detail}
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
            {optionWords(t, source, option, toolServer)}
          </AgentTextAction>
        ))}
      </div>
    </section>
  );
}
