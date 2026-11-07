import { useEffect, useState } from "react";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import type { ModeloAmendmentCorrectionContextV1 } from "../../../shell/modeloContract/modeloWorkAmendmentContext";
import { useStrings } from "../../../shell/strings";

type Read = {
  filingId: string;
  baseId: string | null;
  language: OutputLanguage;
  port: ModeloPort;
  selected: ModeloAmendmentCorrectionContextV1 | null;
  base: ModeloAmendmentCorrectionContextV1 | null;
};

/** The existing context binds labels and saved values to an exact filing and revision. */
export function SavedFilingValues({
  port,
  filingId,
  baseId,
  language,
}: {
  port: ModeloPort;
  filingId: string;
  baseId: string | null;
  language: OutputLanguage;
}) {
  const t = useStrings();
  const [read, setRead] = useState<Read | null>(null);
  useEffect(() => {
    let active = true;
    const load = async (id: string | null) => {
      if (!id) return null;
      try {
        const outcome = await port.submit("modelo.work.amendment_context", {
          filing_record_id: id,
          output_language: language,
        });
        return outcome.kind === "settled" &&
          outcome.result.record.filing_record_id === id
          ? outcome.result.correction
          : null;
      } catch {
        return null;
      }
    };
    void Promise.all([load(filingId), load(baseId)]).then(
      ([selected, base]) => {
        if (active)
          setRead({ filingId, baseId, language, port, selected, base });
      },
    );
    return () => {
      active = false;
    };
  }, [filingId, baseId, language, port]);
  const current =
    read?.filingId === filingId &&
    read.baseId === baseId &&
    read.language === language &&
    read.port === port
      ? read
      : null;
  if (!current)
    return (
      <p role="status" className="text-sm">
        {t("workspace.declarations.related_filings.loading")}
      </p>
    );
  const selected = current.selected;
  if (!selected || (baseId && !current.base)) {
    return (
      <p className="text-sm text-muted-foreground">
        {t("workspace.declarations.related_filings.labels_unavailable")}
      </p>
    );
  }
  const baseRows = new Map(
    current.base?.rows.map((row) => [row.casilla_id, row]),
  );
  const rows = [
    ...selected.rows,
    ...(current.base?.rows.filter(
      (row) =>
        !selected.rows.some((other) => other.casilla_id === row.casilla_id),
    ) ?? []),
  ];
  const selectedRows = new Map(
    selected.rows.map((row) => [row.casilla_id, row]),
  );
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">
        {t("workspace.declarations.related_filings.saved_values")}
      </h3>
      <p className="text-xs text-muted-foreground">
        {t("workspace.declarations.related_filings.current_labels")}
      </p>
      <div className="max-h-72 overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th scope="col" className="p-2 text-left">
                {t("workspace.declarations.related_filings.field")}
              </th>
              {baseId && (
                <th scope="col" className="p-2 text-right">
                  {t("workspace.declarations.related_filings.before")}
                </th>
              )}
              <th scope="col" className="p-2 text-right">
                {t("workspace.declarations.related_filings.after")}
              </th>
              {baseId && (
                <th scope="col" className="p-2 text-left">
                  {t("workspace.declarations.related_filings.change")}
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const before = baseRows.get(row.casilla_id);
              const after = selectedRows.get(row.casilla_id);
              const changed = before?.filed_value !== after?.filed_value;
              return (
                <tr
                  key={row.casilla_id}
                  className={baseId && changed ? "bg-accent" : undefined}
                >
                  <th scope="row" className="p-2 text-left font-normal">
                    {row.box && (
                      <span className="mr-2 font-mono">{row.box}</span>
                    )}
                    {row.label}
                  </th>
                  {baseId && (
                    <td className="p-2 text-right tabular-nums">
                      {before?.filed_value_text ??
                        t("workspace.declarations.related_filings.absent")}
                    </td>
                  )}
                  <td className="p-2 text-right tabular-nums">
                    {after?.filed_value_text ??
                      t("workspace.declarations.related_filings.absent")}
                  </td>
                  {baseId && (
                    <td className="p-2">
                      {t(
                        changed
                          ? "workspace.declarations.related_filings.changed"
                          : "workspace.declarations.related_filings.unchanged",
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
