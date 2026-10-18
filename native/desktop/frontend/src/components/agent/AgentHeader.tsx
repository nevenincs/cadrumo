import { useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { useStrings } from "../../shell/strings";
import type { OpenMenu } from "../ContextMenu";
import { AgentIconAction } from "./AgentAction";
import { TitleEditor } from "./TitleEditor";

/** The largest count a badge spells out; beyond it, the count is capped. */
const BADGE_MAX = 99;

/**
 * The agent column's header: what the conversation is, and the doors to a
 * new conversation, the history and the conversation's documents. History
 * and Documents are toggles; each reports whether its panel is open. The
 * shell's own column controls, such as maximize and close, go in `trailing`,
 * so the column keeps a single header bar. Where the conversation can be
 * renamed, a double click on its title, or Rename in the title's menu, writes
 * over it in place.
 */
export function AgentHeader({
  title,
  subtitle,
  onRename,
  onMenu,
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
  /** Renames the conversation shown; absent where it cannot be renamed. */
  onRename?: (title: string) => void;
  /** Opens a menu for the title. */
  onMenu?: OpenMenu;
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
  const [editing, setEditing] = useState(false);
  const renaming = editing && onRename !== undefined;
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
        {renaming ? (
          <TitleEditor
            title={title}
            onCommit={(named) => {
              setEditing(false);
              onRename(named);
            }}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <h2
            className="truncate font-semibold text-foreground"
            title={title}
            onDoubleClick={
              onRename
                ? (event) => {
                    // The title's double click renames; the bar's maximizes.
                    event.stopPropagation();
                    setEditing(true);
                  }
                : undefined
            }
            onContextMenu={
              onRename && onMenu
                ? (event) => {
                    event.preventDefault();
                    onMenu(
                      [
                        {
                          id: "rename",
                          label: t("desktop.agent.rename"),
                          enabled: true,
                          run: () => setEditing(true),
                        },
                      ],
                      { x: event.clientX, y: event.clientY },
                      true,
                    );
                  }
                : undefined
            }
          >
            {title}
          </h2>
        )}
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
