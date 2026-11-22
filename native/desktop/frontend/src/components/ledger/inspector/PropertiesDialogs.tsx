import { useId, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { facts } from "@/shell/compose";
import type { LedgerPort } from "../../../shell/ledger";
import type { OutputLanguage } from "../../../shell/ledgerClassificationContract";
import {
  batchCounts,
  copiedProperties,
  pasteCells,
  pasteChanges,
  pasteRequests,
  PROPERTY_GROUPS,
  storedProperty,
  unwrittenRows,
  useBatchPreview,
  type CopyableField,
} from "../../../shell/ledgerBatch";
import { isPropertyField, type PropertySet } from "../../../shell/ledgerPlan";
import type { StageEvent } from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { BatchPreviewSection } from "../editing/BatchPreview";
import { batchCountsText, batchRowWords } from "../editing/batchWords";
import { fieldName, valueText } from "../editing/editingWords";
import type { LedgerTransactionReviewProjection } from "../../../shell/ledgerReadContract";

/**
 * Picks which of one movement's properties to copy, grouped as the
 * inspector shows them, each with the value it holds now. What is copied
 * is kept in the page's memory as one property set; nothing is staged.
 */
export function CopyPropertiesDialog({
  row,
  locale,
  onCopy,
  onClose,
}: {
  row: LedgerTransactionReviewProjection;
  locale: string;
  onCopy: (set: PropertySet) => void;
  onClose: () => void;
}) {
  const t = useStrings();
  const id = useId();
  // The properties the movement holds a value of start ticked; an empty one
  // is offered too, where copying it clears it.
  const [ticked, setTicked] = useState<ReadonlySet<CopyableField>>(
    () =>
      new Set(
        PROPERTY_GROUPS.flatMap((group) => group.fields).filter(
          (field) => storedProperty(row, field) !== null,
        ),
      ),
  );
  const chosen = PROPERTY_GROUPS.flatMap((group) => group.fields).filter(
    (field) => ticked.has(field),
  );
  const copy = () => {
    if (!chosen.length) return;
    console.info(`ledger properties copied: fields=${chosen.length}`);
    onCopy(copiedProperties(row, chosen));
  };
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="ledger-copy-properties w-dialog-md"
        closeLabel={t("desktop.ledger.form.close")}
      >
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            copy();
          }}
        >
          <DialogHeader>
            <DialogTitle>
              {t("desktop.ledger.properties.copy_title")}
            </DialogTitle>
            <DialogDescription>
              {t("desktop.ledger.properties.copy_description", {
                movement: row.transaction.description,
              })}
            </DialogDescription>
          </DialogHeader>
          {PROPERTY_GROUPS.map((group) => (
            <fieldset
              key={group.group}
              data-property-group={group.group}
              className="grid gap-1"
            >
              <legend className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                {t(`desktop.ledger.properties.group.${group.group}`)}
              </legend>
              {group.fields.map((field) => {
                const value = storedProperty(row, field);
                return (
                  <label
                    key={field}
                    htmlFor={`${id}-${field}`}
                    className="flex items-center gap-2 text-sm"
                  >
                    <Checkbox
                      id={`${id}-${field}`}
                      data-copy-field={field}
                      checked={ticked.has(field)}
                      onChange={(event) => {
                        const next = new Set(ticked);
                        if (event.target.checked) next.add(field);
                        else next.delete(field);
                        setTicked(next);
                      }}
                    />
                    <span className="min-w-0 flex-1 truncate">
                      {facts(t, [
                        fieldName(t, field),
                        value === null
                          ? t("desktop.ledger.inspector.not_set")
                          : valueText(t, locale, field, value),
                      ])}
                    </span>
                  </label>
                );
              })}
            </fieldset>
          ))}
          <DialogFooter>
            <span className="me-auto text-sm text-muted-foreground">
              {chosen.length === 0 &&
                t("desktop.ledger.properties.none_ticked")}
            </span>
            <Button type="button" variant="ghost" onClick={onClose}>
              {t("desktop.ledger.inspector.cancel")}
            </Button>
            <Button
              type="submit"
              className="ledger-copy-properties-copy"
              aria-disabled={chosen.length === 0 || undefined}
            >
              {t("desktop.ledger.properties.copy", { count: chosen.length })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Pastes copied properties onto the selected movements, after the ledger
 * has said what it would do to each: how many change, the first refusal
 * with its cause, and each property's value. Paste stages the changes the
 * ledger would make into the page's changes; Cancel changes nothing.
 */
export function PastePropertiesDialog({
  port,
  set,
  ids,
  rows,
  locale,
  onStage,
  onClose,
  say,
}: {
  port: LedgerPort;
  set: PropertySet;
  ids: readonly string[];
  rows: ReadonlyMap<string, LedgerTransactionReviewProjection>;
  locale: string;
  onStage: (event: StageEvent) => void;
  onClose: () => void;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const asked = useMemo(
    () => pasteRequests(set, ids, rows, locale as OutputLanguage),
    [set, ids, rows, locale],
  );
  const preview = useBatchPreview(port, asked.requests, rows);
  const results = preview.kind === "answer" ? preview.results : null;
  const cells = results ? pasteCells(set, results, rows) : [];
  const changes = results ? pasteChanges(set, results) : null;
  const firstUnwritten = results ? unwrittenRows(results)[0] : undefined;
  const reason =
    preview.kind === "waiting"
      ? t("desktop.ledger.batch.save_waits")
      : preview.kind === "failed"
        ? t("desktop.ledger.batch.preview_failed")
        : results && cells.length === 0
          ? t("desktop.ledger.properties.nothing_to_paste")
          : null;
  const paste = () => {
    if (!results || cells.length === 0) return;
    const counts = batchCounts(results);
    console.info(
      `ledger properties pasted: cells=${cells.length} applied=${counts.applied} unchanged=${counts.unchanged} refused=${counts.refused} conflict=${counts.conflict}`,
    );
    onStage({ type: "stage", label: "paste", cells });
    say(
      facts(t, [
        t("desktop.ledger.inspector.selection.staged", { count: cells.length }),
        batchCountsText(t, counts),
      ]),
    );
    onClose();
  };
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="ledger-paste-properties w-dialog-lg"
        closeLabel={t("desktop.ledger.form.close")}
      >
        <DialogHeader>
          <DialogTitle>
            {t("desktop.ledger.properties.paste_title", { count: ids.length })}
          </DialogTitle>
          <DialogDescription>
            {t("desktop.ledger.properties.paste_description")}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <dl className="ledger-paste-values grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-sm">
            {set.fields.filter(isPropertyField).map((field) => {
              const value = set[field] ?? null;
              const rowsChanged = changes?.find(
                (change) => change.field === field,
              )?.rows;
              return (
                <div key={field} className="contents">
                  <dt className="text-muted-foreground">
                    {fieldName(t, field)}
                  </dt>
                  <dd data-paste-field={field}>
                    {facts(t, [
                      value === null
                        ? t("desktop.ledger.properties.cleared")
                        : valueText(t, locale, field, value),
                      rowsChanged !== undefined &&
                        t("desktop.ledger.properties.changes_on", {
                          count: rowsChanged,
                        }),
                    ])}
                  </dd>
                </div>
              );
            })}
          </dl>
          <BatchPreviewSection preview={preview} rows={rows} />
          {firstUnwritten && (
            <p className="ledger-paste-first-refusal text-sm">
              {t("desktop.ledger.properties.first_refusal", {
                movement:
                  rows.get(firstUnwritten.transaction_id)?.transaction
                    .description ?? firstUnwritten.transaction_id,
                cause: batchRowWords(t, firstUnwritten),
              })}
            </p>
          )}
          {asked.unread > 0 && (
            <p className="ledger-paste-unread text-sm text-muted-foreground">
              {t("desktop.ledger.properties.unread", { count: asked.unread })}
            </p>
          )}
        </div>
        <DialogFooter>
          <span className="me-auto text-sm text-muted-foreground">
            {reason}
          </span>
          <Button type="button" variant="ghost" onClick={onClose}>
            {t("desktop.ledger.inspector.cancel")}
          </Button>
          <Button
            className="ledger-paste-properties-paste"
            aria-disabled={reason !== null || undefined}
            onClick={paste}
          >
            {t("desktop.ledger.properties.paste", { count: cells.length })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
