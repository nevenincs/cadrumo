import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { useStrings } from "../../shell/strings";
import { AgentIconAction } from "./AgentAction";

/** The largest count a badge spells out; beyond it, the count is capped. */
const BADGE_MAX = 99;

/**
 * The agent column's header: what the conversation is, and the doors to a
 * new conversation, the history and the conversation's documents. History
 * and Documents are toggles; each reports whether its panel is open. The
 * shell's own column controls, such as maximize and close, go in `trailing`,
 * so the column keeps a single header bar.
 */
export function AgentHeader({
  title,
  subtitle,
  onNewConversation,
  historyOpen = false,
  onToggleHistory,
  documentsOpen = false,
  settingsOpen = false,
  onToggleSettings,
  documentCount = 0,
  onToggleDocuments,
  trailing,
  onToggleMaximize,
}: {
  title: string;
  subtitle?: string;
  onNewConversation?: () => void;
  historyOpen?: boolean;
  onToggleHistory?: () => void;
  documentsOpen?: boolean;
  /** The documents in the conversation, counted on the Documents toggle. */
  documentCount?: number;
  onToggleDocuments?: () => void;
  settingsOpen?: boolean;
  /** Opens the agent's settings: its providers and their keys. */
  onToggleSettings?: () => void;
  /** Controls owned by the surrounding column, drawn after a divider. */
  trailing?: ReactNode;
  /** A double click on the bar itself, not on a control, toggles maximize. */
  onToggleMaximize?: () => void;
}) {
  const t = useStrings();
  const count = Math.max(0, documentCount);
  const documents = t("desktop.agent.documents");
  const attached =
    count > 0 ? t("desktop.agent.documents_attached", { count }) : undefined;
  const shown = count > BADGE_MAX ? `${BADGE_MAX}+` : String(count);
  return (
    <div
      className="flex min-h-control-lg shrink-0 items-center gap-1 border-b bg-chrome py-1 pr-1.5 pl-3"
      onDoubleClick={(event) => {
        if (!onToggleMaximize) return;
        if ((event.target as Element).closest("button, [role='button']"))
          return;
        onToggleMaximize();
      }}
    >
      <div className="grid min-w-0 flex-1">
        <h2 className="truncate font-semibold text-foreground" title={title}>
          {title}
        </h2>
        {subtitle && (
          <p
            className="truncate text-xs text-muted-foreground"
            title={subtitle}
          >
            {subtitle}
          </p>
        )}
      </div>
      <AgentIconAction
        icon="plus"
        label={t("desktop.agent.new_conversation")}
        onAction={onNewConversation}
      />
      <AgentIconAction
        icon="clock"
        label={t("desktop.agent.history")}
        aria-pressed={historyOpen}
        onAction={onToggleHistory}
      />
      <AgentIconAction
        icon="page"
        label={documents}
        hint={attached}
        // The name holds the badge as it is drawn, then the exact count.
        accessibleName={
          attached ? `${documents}, ${shown}, ${attached}` : undefined
        }
        aria-pressed={documentsOpen}
        onAction={onToggleDocuments}
        badge={
          count > 0 ? (
            <Badge
              variant="count"
              aria-hidden="true"
              className="absolute -top-1 -right-1"
            >
              {shown}
            </Badge>
          ) : undefined
        }
      />
      <AgentIconAction
        icon="settings"
        label={t("desktop.agent.settings")}
        aria-pressed={settingsOpen}
        onAction={onToggleSettings}
      />
      {trailing && (
        <>
          <span aria-hidden="true" className="mx-1 h-4 w-px bg-border" />
          {trailing}
        </>
      )}
    </div>
  );
}
