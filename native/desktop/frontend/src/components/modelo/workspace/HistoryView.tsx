import { useState, type FormEvent } from "react";
import { TextEditor } from "@/components/editors/TextEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon, type IconName } from "@/components/ui/icon";
import { formatTime } from "../../../shared/dateFormats";
import type {
  ModeloAmendmentCorrectionContextV1,
  ModeloWorkHistoryEntryV1,
} from "../../../shell/modeloContract";
import { useStrings } from "../../../shell/strings";
import { Heading } from "./CheckView";
import {
  CorrectionDialog,
  Labelled,
  type CorrectionAnswer,
  type CorrectionResult,
} from "./CorrectionDialog";

/** The declaration's catalogue record, as `modelo.work.metadata` reads it:
 * what a rename and a discard are bound to. */
export type HistoryUnit = {
  name: string;
  updated_at: string;
};

/** What an operation the view started answered, in the product's words;
 * null while nothing is pending. */
export type HistoryNotice = {
  tone: "warning" | "danger";
  words: string;
} | null;

const KIND_ICON: Record<string, IconName> = {
  created: "plus",
  renamed: "edit",
  calculated: "sync",
  verified: "check",
  verification_refused: "refused",
  exported: "download",
  filed: "tick",
  superseded: "swap",
  amended: "swap",
  reconciled: "shield",
  external_evidence_imported: "shield",
  observation_overridden: "edit",
  observation_override_cleared: "restore",
  discarded: "trash",
};

function RenameDialog({
  open,
  onOpenChange,
  unit,
  onRename,
}: {
  open: boolean;
  onOpenChange(open: boolean): void;
  unit: HistoryUnit | null;
  onRename(name: string): Promise<boolean>;
}) {
  const t = useStrings();
  const [name, setName] = useState(unit?.name ?? "");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    const done = await onRename(name.trim());
    setBusy(false);
    if (done) onOpenChange(false);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={t("workspace.modelo.key.close")}>
        <form onSubmit={submit} className="contents">
          <DialogHeader>
            <DialogTitle>{t("workspace.modelo.history.rename")}</DialogTitle>
          </DialogHeader>
          <Labelled label={t("desktop.modelo.rename.name")}>
            {(id) => (
              <TextEditor id={id} value={name} onChange={setName} />
            )}
          </Labelled>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
            >
              {t("workspace.modelo.editor.cancel")}
            </Button>
            <Button
              type="submit"
              disabled={
                busy || !unit || !name.trim() || name.trim() === unit.name
              }
            >
              {t("desktop.modelo.rename.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DiscardDialog({
  open,
  onOpenChange,
  unit,
  onDiscard,
}: {
  open: boolean;
  onOpenChange(open: boolean): void;
  unit: HistoryUnit | null;
  onDiscard(reason: string): Promise<boolean>;
}) {
  const t = useStrings();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const discard = async () => {
    setBusy(true);
    const done = await onDiscard(reason.trim());
    setBusy(false);
    if (done) onOpenChange(false);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={t("workspace.modelo.key.close")}>
        <DialogHeader>
          <DialogTitle>{t("workspace.modelo.history.discard")}</DialogTitle>
          <DialogDescription>
            {t("desktop.modelo.discard.lead")}
          </DialogDescription>
        </DialogHeader>
        <Labelled label={t("desktop.modelo.discard.reason")}>
          {(id) => (
            <TextEditor id={id} value={reason} onChange={setReason} />
          )}
        </Labelled>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t("workspace.modelo.editor.cancel")}
          </Button>
          <Button
            variant="destructive"
            disabled={busy || !unit}
            onClick={discard}
          >
            {t("desktop.modelo.discard.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * What happened to the declaration, newest first, with renaming it,
 * discarding it while it is not recorded as filed, and preparing a
 * correction once it is.
 */
export function HistoryView({
  entries,
  unit,
  recorded,
  locale,
  notice,
  correcting,
  onCorrectingChange,
  correction,
  onRename,
  onDiscard,
  onCorrect,
}: {
  /** Null while the history has not been read. */
  entries: ModeloWorkHistoryEntryV1[] | null;
  unit: HistoryUnit | null;
  /** Whether the declaration is recorded as filed. */
  recorded: boolean;
  locale: string;
  notice: HistoryNotice;
  correcting: boolean;
  onCorrectingChange(open: boolean): void;
  correction: ModeloAmendmentCorrectionContextV1 | null;
  onRename(name: string): Promise<boolean>;
  onDiscard(reason: string): Promise<boolean>;
  onCorrect: ((answer: CorrectionAnswer) => Promise<CorrectionResult>) | null;
}) {
  const t = useStrings();
  const [renaming, setRenaming] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const when = (iso: string) => formatTime(locale, iso);
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Heading
        title={t("workspace.modelo.history.title")}
        lead={t("workspace.modelo.history.lead")}
      />
      {notice && (
        <Alert tone={notice.tone} icon={<Icon name="alert" />}>
          {notice.words}
        </Alert>
      )}
      {entries && (
        <ol className="flex flex-col">
          {entries.map((entry) => (
            <li
              key={entry.event_id}
              className="grid grid-cols-[auto_minmax(0,1fr)_auto] gap-3 pb-4"
            >
              <span className="flex size-control-sm items-center justify-center rounded-full bg-secondary text-muted-foreground">
                <Icon name={KIND_ICON[entry.kind] ?? "clock"} size="xs" />
              </span>
              <span className="flex flex-col">
                <span className="text-base">{entry.words}</span>
                {entry.detail && (
                  <span className="text-sm text-muted-foreground">
                    {entry.detail}
                  </span>
                )}
              </span>
              <span className="text-sm text-faint tabular-nums">
                {when(entry.occurred_at)}
              </span>
            </li>
          ))}
        </ol>
      )}
      <div className="flex gap-2 border-t border-border pt-4">
        <Button
          variant="ghost"
          size="sm"
          disabled={!unit}
          onClick={() => setRenaming(true)}
        >
          <Icon name="edit" size="xs" />
          {t("workspace.modelo.history.rename")}
        </Button>
        {recorded ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onCorrectingChange(true)}
          >
            <Icon name="swap" size="xs" />
            {t("workspace.modelo.correction.title")}
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive"
            disabled={!unit}
            onClick={() => setDiscarding(true)}
          >
            <Icon name="trash" size="xs" />
            {t("workspace.modelo.history.discard")}
          </Button>
        )}
      </div>
      {renaming && (
        <RenameDialog
          open
          onOpenChange={setRenaming}
          unit={unit}
          onRename={onRename}
        />
      )}
      {discarding && (
        <DiscardDialog
          open
          onOpenChange={setDiscarding}
          unit={unit}
          onDiscard={onDiscard}
        />
      )}
      {correcting && (
        <CorrectionDialog
          open
          onOpenChange={onCorrectingChange}
          context={correction}
          onCorrect={onCorrect}
        />
      )}
    </div>
  );
}
