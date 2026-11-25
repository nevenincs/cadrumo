import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useStrings } from "../../shell/strings";
import { AttachmentWell } from "./AttachmentWell";
import type { StagedAttachment } from "./types";

export function StagedAttachmentsDialog({
  attachments,
  locale,
  onRemove,
  onRemoveAll,
  onAddFiles,
  onClose,
  onAfterClose,
}: {
  attachments: readonly StagedAttachment[];
  locale: string;
  onRemove: (id: string) => void;
  onRemoveAll: () => void;
  onAddFiles?: () => void;
  onClose: () => void;
  onAfterClose?: () => void;
}) {
  const t = useStrings();
  const [opener] = useState(() =>
    document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null,
  );
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        closeLabel={t("desktop.agent.close_documents")}
        aria-describedby={undefined}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (opener?.isConnected) opener.focus();
          else onAfterClose?.();
        }}
      >
        <DialogHeader>
          <DialogTitle>{t("desktop.agent.attachments")}</DialogTitle>
        </DialogHeader>
        <AttachmentWell
          attachments={attachments}
          locale={locale}
          expanded
          onRemove={onRemove}
          onRemoveAll={onRemoveAll}
        />
        {onAddFiles && (
          <Button variant="outline" onClick={onAddFiles}>
            {t("desktop.agent.add_files")}
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
}
