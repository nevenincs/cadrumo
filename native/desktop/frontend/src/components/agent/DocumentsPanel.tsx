import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../shell/strings";
import { AgentIconAction, AgentTextAction } from "./AgentAction";
import { extensionLabel, formatSize, KIND_GLYPH } from "./files";
import type { ConversationDocument } from "./types";

/** The conversation's stored files. Using one selects a reference for the
 * next message; deleting it removes the stored file after confirmation. */
export function DocumentsPanel({
  documents,
  locale,
  busy = false,
  selectedIds = [],
  selectionLimit,
  onClose,
  onAddFiles,
  onRefresh,
  onUse,
  onRemove,
}: {
  documents: readonly ConversationDocument[];
  locale: string;
  busy?: boolean;
  selectedIds?: readonly string[];
  selectionLimit?: number;
  onClose?: () => void;
  onAddFiles?: () => void;
  onRefresh?: () => void;
  onUse?: (id: string) => void;
  /** Null removes every stored file. */
  onRemove?: (id: string | null) => void;
}) {
  const t = useStrings();
  const section = useRef<HTMLElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const removing = useRef<{ id: string | null } | null>(null);
  const [confirming, setConfirming] = useState<{
    id: string | null;
    name: string;
  } | null>(null);
  const askToRemove = (id: string | null, name: string) => {
    opener.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setConfirming({ id, name });
  };
  useEffect(() => {
    const pending = removing.current;
    if (
      !pending ||
      (pending.id === null
        ? documents.length > 0
        : documents.some((document) => document.id === pending.id))
    )
      return;
    removing.current = null;
    if (document.activeElement === document.body) section.current?.focus();
  }, [documents]);
  const total = documents.reduce((sum, file) => sum + file.sizeBytes, 0);
  return (
    <section
      ref={section}
      tabIndex={-1}
      aria-label={t("desktop.agent.documents")}
      className="flex min-h-0 flex-1 flex-col bg-background"
    >
      <div className="flex min-h-control-lg shrink-0 flex-wrap items-center gap-2 bg-chrome pr-1.5 pl-3">
        <h2 className="min-w-0 flex-1 truncate font-semibold">
          {t("desktop.agent.documents")}
        </h2>
        <AgentIconAction
          icon="plus"
          label={t("desktop.agent.add_files")}
          onAction={busy ? undefined : onAddFiles}
        />
        <AgentIconAction
          icon="close"
          label={t("desktop.agent.close_documents")}
          onAction={onClose}
        />
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
        <span>
          {t("desktop.agent.files_summary", {
            count: documents.length,
            size: formatSize(locale, total),
          })}
        </span>
        <span className="flex-1" />
        {onRefresh && (
          <AgentTextAction
            variant="ghost"
            size="xs"
            onAction={busy ? undefined : onRefresh}
          >
            {t("desktop.agent.refresh_documents")}
          </AgentTextAction>
        )}
        {documents.length > 0 && onRemove && (
          <AgentTextAction
            variant="ghost"
            size="xs"
            onAction={busy ? undefined : () => askToRemove(null, "")}
          >
            {t("desktop.agent.remove_all")}
          </AgentTextAction>
        )}
      </div>
      {documents.length === 0 ? (
        <EmptyState heading={t("desktop.agent.documents_empty")} />
      ) : (
        <ul className="min-h-0 flex-1 overflow-y-auto">
          {documents.map((document) => {
            const selected = selectedIds.includes(document.id);
            return (
              <li
                key={document.id}
                className="flex min-w-0 items-center gap-2 border-b px-2 py-2 last:border-b-0"
              >
                <span
                  aria-hidden="true"
                  className="flex size-control-md shrink-0 items-center justify-center rounded-md bg-accent text-muted-foreground"
                >
                  <Icon
                    name={document.kind ? KIND_GLYPH[document.kind] : "page"}
                  />
                </span>
                <div className="grid min-w-0 flex-1">
                  <span
                    className="truncate text-foreground"
                    title={document.name}
                  >
                    {document.name}
                  </span>
                  <span className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                    <span>{extensionLabel(document.extension)}</span>
                    <span className="tabular-nums">
                      {formatSize(locale, document.sizeBytes)}
                    </span>
                    <span>
                      {selected
                        ? t("desktop.agent.document_selected")
                        : t("desktop.agent.status_ready")}
                    </span>
                  </span>
                </div>
                {onUse && (
                  <AgentIconAction
                    icon={selected ? "check" : "plus"}
                    label={t("desktop.agent.use_document", {
                      name: document.name,
                    })}
                    onAction={!busy ? () => onUse(document.id) : undefined}
                    heldBy={
                      selected
                        ? t("desktop.agent.document_selected")
                        : selectionLimit !== undefined &&
                            selectedIds.length >= selectionLimit
                          ? t("desktop.agent.document_selection_limit", {
                              count: selectionLimit,
                            })
                          : undefined
                    }
                  />
                )}
                <AgentIconAction
                  icon="close"
                  label={t("desktop.agent.remove_document", {
                    name: document.name,
                  })}
                  onAction={
                    !busy && onRemove
                      ? () => askToRemove(document.id, document.name)
                      : undefined
                  }
                />
              </li>
            );
          })}
        </ul>
      )}
      <Dialog
        open={confirming !== null}
        onOpenChange={(open) => {
          if (!open) setConfirming(null);
        }}
      >
        <DialogContent
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (opener.current?.isConnected) opener.current.focus();
            else section.current?.focus();
          }}
        >
          <DialogHeader>
            <DialogTitle>{t("desktop.agent.delete")}</DialogTitle>
            <DialogDescription>
              {confirming?.id === null
                ? t("desktop.agent.remove_documents_confirm", {
                    count: documents.length,
                  })
                : t("desktop.agent.remove_document_confirm", {
                    name: confirming?.name ?? "",
                  })}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirming(null)}>
              {t("desktop.agent.cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={busy || !onRemove}
              onClick={() => {
                if (confirming) {
                  removing.current = { id: confirming.id };
                  onRemove?.(confirming.id);
                }
                setConfirming(null);
              }}
            >
              {t("desktop.agent.delete")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
