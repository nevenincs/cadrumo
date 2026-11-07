import { useEffect, useId, useState } from "react";
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
import { NativeSelect } from "@/components/ui/native-select";
import { Spinner } from "@/components/ui/spinner";
import { formatTime } from "../../../shared/dateFormats";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloDeclarationListRowV1 } from "../../../shell/modeloContract/modeloDeclarations";
import type { ModeloFilingRecordViewProjection } from "../../../shell/modeloContract/modeloFilingRecord";
import { useStrings } from "../../../shell/strings";
import { SavedFilingValues } from "./SavedFilingValues";

type Filing = ModeloDeclarationListRowV1["related_filings"][number];
type Read = {
  id: string;
  language: OutputLanguage;
  port: ModeloPort;
} & (
  | { phase: "ready"; result: ModeloFilingRecordViewProjection }
  | { phase: "failed" }
);

/** Read exact saved filings without opening a mutable work unit in their place. */
export function RelatedFilingsDialog({
  port,
  filingId,
  filings = [],
  language,
  locale,
  title,
  onClose,
  onOpenWork,
}: {
  port: ModeloPort;
  filingId: string;
  filings?: readonly Filing[];
  language: OutputLanguage;
  locale: string;
  title: string;
  onClose(): void;
  onOpenWork?: () => void;
}) {
  const t = useStrings();
  const selectId = useId();
  const [selectedId, setSelectedId] = useState(filingId);
  const [read, setRead] = useState<Read | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let current = true;
    void port
      .submit("modelo.filing_record.view", {
        filing_record_id: selectedId,
        output_language: language,
      })
      .then(
        (outcome) => {
          if (!current) return;
          const identity = { id: selectedId, language, port };
          setRead(
            outcome.kind === "settled" &&
              outcome.result.filing_record_id === selectedId
              ? { ...identity, phase: "ready", result: outcome.result }
              : { ...identity, phase: "failed" },
          );
        },
        () => {
          if (current)
            setRead({ id: selectedId, language, port, phase: "failed" });
        },
      );
    return () => {
      current = false;
    };
  }, [port, selectedId, language, attempt]);
  const current =
    read?.id === selectedId && read.language === language && read.port === port
      ? read
      : null;
  const result = current?.phase === "ready" ? current.result : null;
  const related = result?.related_filings ?? filings;
  const selected = related.find(
    (entry) => entry.filing_record_id === selectedId,
  );
  const base = related.find(
    (entry) => entry.filing_record_id === selected?.amends_filing_record_id,
  );
  const children = related.filter(
    (entry) => entry.amends_filing_record_id === selectedId,
  );
  const label = (entry: Filing) =>
    `${entry.kind_words} · ${formatTime(locale, entry.filed_at)} · ${entry.confirmation_words} · ${entry.status_words}`;
  const comparison = result?.comparison;
  const canCompare = comparison?.availability === "available";
  const savedRows = canCompare
    ? comparison.rows
    : (result?.historical_content.observations ?? []).map((row) => ({
        casilla_id: row.casilla_id,
        base_value: null,
        selected_value: row.value,
        change: "unchanged",
      }));
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        className="w-palette"
        closeLabel={t("workspace.modelo.key.close")}
      >
        <DialogHeader>
          <DialogTitle>
            {t("workspace.declarations.related_filings.title")}
          </DialogTitle>
          <DialogDescription>{title}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4" aria-busy={current === null}>
          {related.length > 0 && (
            <div className="flex flex-col gap-2">
              <label htmlFor={selectId} className="text-sm font-medium">
                {t("workspace.declarations.related_filings.select")}
              </label>
              <NativeSelect
                id={selectId}
                value={selectedId}
                onChange={(event) => setSelectedId(event.target.value)}
              >
                {related.map((entry) => (
                  <option
                    key={entry.filing_record_id}
                    value={entry.filing_record_id}
                  >
                    {label(entry)}
                  </option>
                ))}
              </NativeSelect>
            </div>
          )}
          {selected && (
            <p className="text-sm" aria-live="polite">
              {label(selected)}
            </p>
          )}
          {base && (
            <div className="flex flex-col items-start gap-1">
              <span className="text-sm text-muted-foreground">
                {t("workspace.declarations.related_filings.base")}
              </span>
              <Button
                variant="link"
                className="h-auto whitespace-normal p-0 text-left"
                onClick={() => setSelectedId(base.filing_record_id)}
              >
                {label(base)}
              </Button>
            </div>
          )}
          {children.length > 0 && (
            <div className="flex flex-col items-start gap-1">
              <span className="text-sm text-muted-foreground">
                {t("workspace.declarations.related_filings.corrections")}
              </span>
              {children.map((entry) => (
                <Button
                  key={entry.filing_record_id}
                  variant="link"
                  className="h-auto whitespace-normal p-0 text-left"
                  onClick={() => setSelectedId(entry.filing_record_id)}
                >
                  {label(entry)}
                </Button>
              ))}
            </div>
          )}
          {current === null && (
            <p role="status" className="flex items-center gap-2 text-sm">
              <Spinner />
              {t("workspace.declarations.related_filings.loading")}
            </p>
          )}
          {current?.phase === "failed" && (
            <Alert tone="warning" role="alert">
              <p>{t("workspace.declarations.related_filings.failed")}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setRead(null);
                  setAttempt((value) => value + 1);
                }}
              >
                {t("workspace.declarations.related_filings.retry")}
              </Button>
            </Alert>
          )}
          {result?.historical_display_words && (
            <p className="text-sm text-muted-foreground">
              {result.historical_display_words}
            </p>
          )}
          {comparison &&
            comparison.availability !== "available" &&
            comparison.availability !== "no_base" && (
              <Alert tone="warning">
                {t(
                  "workspace.declarations.related_filings.comparison_unavailable",
                )}
              </Alert>
            )}
          {result && (
            <SavedFilingValues
              port={port}
              filingId={selectedId}
              baseId={
                comparison?.availability === "available"
                  ? comparison.base_filing_record_id
                  : null
              }
              language={language}
            />
          )}
          {result?.historical_content.availability === "available" && (
            <details className="rounded-md border border-border p-3">
              <summary className="cursor-pointer text-sm font-medium">
                {t("workspace.declarations.related_filings.technical_values")}
              </summary>
              <div className="mt-3 max-h-72 overflow-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th scope="col" className="p-2 text-left">
                        {t("workspace.declarations.related_filings.field")}
                      </th>
                      {canCompare && (
                        <th scope="col" className="p-2 text-right">
                          {t("workspace.declarations.related_filings.before")}
                        </th>
                      )}
                      <th scope="col" className="p-2 text-right">
                        {t("workspace.declarations.related_filings.after")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {savedRows.map((row) => (
                      <tr
                        key={row.casilla_id}
                        className={
                          row.change === "unchanged"
                            ? "text-muted-foreground"
                            : "bg-accent font-medium"
                        }
                      >
                        <th scope="row" className="p-2 text-left font-mono">
                          {row.casilla_id}
                        </th>
                        {canCompare && (
                          <td className="p-2 text-right tabular-nums">
                            {row.base_value ??
                              t(
                                "workspace.declarations.related_filings.absent",
                              )}
                          </td>
                        )}
                        <td className="p-2 text-right tabular-nums">
                          {row.selected_value ??
                            t("workspace.declarations.related_filings.absent")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </div>
        <DialogFooter>
          {onOpenWork && (
            <Button variant="outline" onClick={onOpenWork}>
              {t("workspace.declarations.related_filings.open_work")}
            </Button>
          )}
          <Button onClick={onClose}>{t("workspace.modelo.key.close")}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
