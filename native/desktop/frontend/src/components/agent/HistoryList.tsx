import { useEffect, useId, useRef, useState } from "react";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { chordMatches, chordText, type ChordKeys } from "@/shared/chords";
import { useStrings } from "../../shell/strings";
import type { MenuEntry, OpenMenu } from "../ContextMenu";
import { AgentIconAction, AgentTextAction } from "./AgentAction";
import { TitleEditor } from "./TitleEditor";
import type { ConversationGroup, ConversationSummary } from "./types";

/** Renames the focused conversation: a row runs it, and the row's menu shows
 * it. */
const RENAME_CHORD: ChordKeys = { code: "F2", key: "F2" };

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
      className="grid gap-2 rounded-md bg-destructive/5 p-2"
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
 * footer switches between the active and the archived conversations. Where
 * renaming is offered, F2 on a row, or Rename in its context menu, writes
 * over its title in place.
 */
export function HistoryList({
  groups,
  busy = false,
  viewingArchived = false,
  archivedCount,
  onToggleArchived,
  onOpen,
  onArchive,
  onRestore,
  onDelete,
  onRename,
  onMenu,
}: {
  groups: readonly ConversationGroup[];
  /** A history mutation is awaiting the host's answer. */
  busy?: boolean;
  /** The list is showing archived conversations, not active ones. */
  viewingArchived?: boolean;
  archivedCount: number;
  onToggleArchived?: () => void;
  onOpen?: (id: string) => void;
  onArchive?: (id: string) => void;
  onRestore?: (id: string) => void;
  onDelete?: (id: string) => void;
  onRename?: (id: string, title: string) => void;
  /** Opens a row's context menu. */
  onMenu?: OpenMenu;
}) {
  const t = useStrings();
  const [query, setQuery] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
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

  // A rename settled puts the keyboard back on the row it renamed.
  const refocusRow = useRef<string | null>(null);
  useEffect(() => {
    const id = refocusRow.current;
    if (renaming !== null || id === null) return;
    refocusRow.current = null;
    list.current
      ?.querySelector<HTMLElement>(`[data-open-for="${CSS.escape(id)}"]`)
      ?.focus();
  }, [renaming]);
  const settleRename = (id: string, title?: string) => {
    refocusRow.current = id;
    setRenaming(null);
    if (title !== undefined) onRename?.(id, title);
  };

  const rowMenu = (conversation: ConversationSummary): MenuEntry[] => {
    if (busy) return [];
    const restore = viewingArchived ? onRestore : undefined;
    const archive = viewingArchived ? undefined : onArchive;
    const items: MenuEntry[] = [];
    if (onRename)
      items.push({
        id: "rename",
        label: t("desktop.agent.rename"),
        icon: "edit",
        chord: RENAME_CHORD,
        enabled: true,
        run: () => setRenaming(conversation.id),
      });
    if (restore)
      items.push({
        id: "restore",
        label: t("desktop.agent.restore"),
        icon: "unarchive",
        enabled: true,
        run: () => restore(conversation.id),
      });
    if (archive)
      items.push({
        id: "archive",
        label: t("desktop.agent.archive"),
        icon: "archive",
        enabled: true,
        run: () => archive(conversation.id),
      });
    if (onDelete) {
      if (items.length > 0) items.push({ separator: true });
      items.push({
        id: "delete",
        label: t("desktop.agent.delete"),
        icon: "trash",
        enabled: true,
        run: () => setConfirming(conversation.id),
      });
    }
    return items;
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
          <EmptyState
            heading={
              viewingArchived
                ? t("desktop.agent.archived_empty")
                : t("desktop.agent.history_empty")
            }
          />
        ) : shown.length === 0 ? (
          <EmptyState
            description={t("desktop.agent.history_no_match", {
              query: query.trim(),
            })}
          />
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
                          onDelete && !busy
                            ? () => {
                                setConfirming(null);
                                onDelete(conversation.id);
                              }
                            : undefined
                        }
                      />
                    ) : renaming === conversation.id ? (
                      <div className="px-1 py-1">
                        <TitleEditor
                          title={conversation.title}
                          onCommit={(title) =>
                            settleRename(conversation.id, title)
                          }
                          onCancel={() => settleRename(conversation.id)}
                        />
                      </div>
                    ) : (
                      <div
                        className="group/row flex min-w-0 items-center gap-1 rounded-md pr-1 hover:bg-accent has-[[aria-current=true]]:bg-selected"
                        onContextMenu={(event) => {
                          const items = rowMenu(conversation);
                          if (!onMenu || items.length === 0) return;
                          event.preventDefault();
                          onMenu(items, { x: event.clientX, y: event.clientY });
                        }}
                      >
                        <AgentTextAction
                          variant="ghost"
                          aria-current={conversation.current || undefined}
                          data-open-for={conversation.id}
                          aria-keyshortcuts={
                            onRename ? chordText(RENAME_CHORD) : undefined
                          }
                          onKeyDown={(event) => {
                            if (chordMatches(RENAME_CHORD, event) && onRename) {
                              event.preventDefault();
                              setRenaming(conversation.id);
                            }
                          }}
                          onAction={
                            onOpen && !busy
                              ? () => onOpen(conversation.id)
                              : undefined
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
                                onRestore && !busy
                                  ? () => onRestore(conversation.id)
                                  : undefined
                              }
                            />
                          ) : (
                            <AgentIconAction
                              icon="archive"
                              label={t("desktop.agent.archive")}
                              onAction={
                                onArchive && !busy
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
                              onDelete && !busy
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
