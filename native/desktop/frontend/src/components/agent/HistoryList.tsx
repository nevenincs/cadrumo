import { useEffect, useId, useRef, useState } from "react";
import { Empty, EmptyDescription, EmptyTitle } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { useStrings } from "../../shell/strings";
import { AgentIconAction, AgentTextAction } from "./AgentAction";
import type { ConversationGroup, ConversationSummary } from "./types";

/** A title matches a search when it holds every word of it, in any case. */
function matches(title: string, query: string): boolean {
  const words = query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const held = title.toLocaleLowerCase();
  return words.every((word) => held.includes(word));
}

/** The confirmation a Delete opens in place of its row. */
function DeleteConfirmation({
  conversation,
  onCancel,
  onDelete,
}: {
  conversation: ConversationSummary;
  onCancel: () => void;
  onDelete?: () => void;
}) {
  const t = useStrings();
  const textId = useId();
  const question =
    conversation.documentCount > 0
      ? t("desktop.agent.delete_confirm", {
          title: conversation.title,
          count: conversation.documentCount,
        })
      : t("desktop.agent.delete_confirm_bare", { title: conversation.title });
  return (
    <div
      role="group"
      aria-labelledby={textId}
      className="grid gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-2"
      onKeyDown={(event) => {
        if (event.key === "Escape" && !event.nativeEvent.isComposing) {
          event.stopPropagation();
          onCancel();
        }
      }}
    >
      <p id={textId} className="text-sm text-foreground">
        {question}
      </p>
      <div className="flex justify-end gap-1.5">
        <AgentTextAction
          variant="outline"
          size="xs"
          autoFocus
          onAction={onCancel}
        >
          {t("desktop.agent.cancel")}
        </AgentTextAction>
        <AgentTextAction variant="destructive" size="xs" onAction={onDelete}>
          {t("desktop.agent.delete")}
        </AgentTextAction>
      </div>
    </div>
  );
}

/**
 * The conversations, under the date headings the caller words, with a
 * search over their titles. A row's Archive (or Restore) and Delete show on
 * hover and on focus; Delete asks first, in the row, naming what goes. The
 * footer switches between the active and the archived conversations.
 */
export function HistoryList({
  groups,
  viewingArchived = false,
  archivedCount,
  onToggleArchived,
  onOpen,
  onArchive,
  onRestore,
  onDelete,
}: {
  groups: readonly ConversationGroup[];
  /** The list is showing archived conversations, not active ones. */
  viewingArchived?: boolean;
  archivedCount: number;
  onToggleArchived?: () => void;
  onOpen?: (id: string) => void;
  onArchive?: (id: string) => void;
  onRestore?: (id: string) => void;
  onDelete?: (id: string) => void;
}) {
  const t = useStrings();
  const [query, setQuery] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const searchId = useId();

  const shown = groups
    .map((group) => ({
      ...group,
      conversations: group.conversations.filter((conversation) =>
        matches(conversation.title, query),
      ),
    }))
    .filter((group) => group.conversations.length > 0);
  const nothing = groups.every((group) => group.conversations.length === 0);

  // Cancelling puts the keyboard back on the Delete that asked, once its
  // row is drawn again.
  const refocus = useRef<string | null>(null);
  useEffect(() => {
    const id = refocus.current;
    if (confirming !== null || id === null) return;
    refocus.current = null;
    list.current
      ?.querySelector<HTMLElement>(`[data-delete-for="${CSS.escape(id)}"]`)
      ?.focus();
  }, [confirming]);
  const cancel = (id: string) => {
    refocus.current = id;
    setConfirming(null);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 px-3 pt-3 pb-2">
        <label htmlFor={searchId} className="sr-only">
          {t("desktop.agent.search_history")}
        </label>
        <div className="relative">
          <Icon
            name="search"
            className="pointer-events-none absolute top-1/2 left-2 -translate-y-1/2 text-faint"
          />
          <Input
            id={searchId}
            type="search"
            controlSize="sm"
            value={query}
            placeholder={t("desktop.agent.search_history")}
            onChange={(event) => setQuery(event.target.value)}
            className="pl-7"
          />
        </div>
      </div>
      <div ref={list} className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {nothing ? (
          <Empty>
            <EmptyTitle>
              {viewingArchived
                ? t("desktop.agent.archived_empty")
                : t("desktop.agent.history_empty")}
            </EmptyTitle>
          </Empty>
        ) : shown.length === 0 ? (
          <Empty>
            <EmptyDescription>
              {t("desktop.agent.history_no_match", { query: query.trim() })}
            </EmptyDescription>
          </Empty>
        ) : (
          shown.map((group) => (
            <section key={group.heading} className="grid gap-0.5 pt-2">
              <h3 className="px-2 pb-0.5 text-xs font-medium text-faint">
                {group.heading}
              </h3>
              <ul className="grid gap-0.5">
                {group.conversations.map((conversation) => (
                  <li key={conversation.id}>
                    {confirming === conversation.id ? (
                      <DeleteConfirmation
                        conversation={conversation}
                        onCancel={() => cancel(conversation.id)}
                        onDelete={
                          onDelete
                            ? () => {
                                setConfirming(null);
                                onDelete(conversation.id);
                              }
                            : undefined
                        }
                      />
                    ) : (
                      <div className="group/row flex min-w-0 items-center gap-1 rounded-md pr-1 hover:bg-accent has-[[aria-current=true]]:bg-selected">
                        <AgentTextAction
                          variant="ghost"
                          aria-current={conversation.current || undefined}
                          onAction={
                            onOpen ? () => onOpen(conversation.id) : undefined
                          }
                          className="grid h-auto min-w-0 flex-1 justify-start justify-items-start gap-0 bg-transparent px-2 py-1.5 text-left font-normal whitespace-normal hover:bg-transparent"
                        >
                          <span className="w-full truncate font-medium text-foreground">
                            {conversation.title}
                          </span>
                          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <span>{conversation.lastActivityLabel}</span>
                            {conversation.documentCount > 0 && (
                              <span className="flex items-center gap-0.5">
                                <Icon name="page" size="xs" />
                                <span aria-hidden="true">
                                  {conversation.documentCount}
                                </span>
                                <span className="sr-only">
                                  {t("desktop.agent.row_documents", {
                                    count: conversation.documentCount,
                                  })}
                                </span>
                              </span>
                            )}
                          </span>
                        </AgentTextAction>
                        <div className="flex shrink-0 gap-0.5 opacity-0 group-focus-within/row:opacity-100 group-hover/row:opacity-100 pointer-coarse:opacity-100">
                          {viewingArchived ? (
                            <AgentIconAction
                              icon="unarchive"
                              label={t("desktop.agent.restore")}
                              onAction={
                                onRestore
                                  ? () => onRestore(conversation.id)
                                  : undefined
                              }
                            />
                          ) : (
                            <AgentIconAction
                              icon="archive"
                              label={t("desktop.agent.archive")}
                              onAction={
                                onArchive
                                  ? () => onArchive(conversation.id)
                                  : undefined
                              }
                            />
                          )}
                          <AgentIconAction
                            icon="trash"
                            label={t("desktop.agent.delete")}
                            data-delete-for={conversation.id}
                            onAction={
                              onDelete
                                ? () => setConfirming(conversation.id)
                                : undefined
                            }
                          />
                        </div>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}
      </div>
      <div className="flex shrink-0 justify-start border-t px-2 py-1.5">
        <AgentTextAction variant="ghost" size="xs" onAction={onToggleArchived}>
          {viewingArchived
            ? t("desktop.agent.show_active")
            : t("desktop.agent.archived_toggle", { count: archivedCount })}
        </AgentTextAction>
      </div>
    </div>
  );
}
