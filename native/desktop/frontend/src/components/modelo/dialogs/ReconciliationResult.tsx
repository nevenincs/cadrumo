import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import type { ModeloReconciliationImportProjection } from "../../../shell/modeloContract/modeloReconcile";
import { useStrings } from "../../../shell/strings";

export type ReconciliationReport = Pick<
  ModeloReconciliationImportProjection,
  "verdict" | "diffs" | "advisories" | "narrative"
>;

const FIELDS = new Set([
  "modelo",
  "ejercicio",
  "period",
  "tax_id",
  "total_ingresar",
  "total_devolver",
]);
const PREFIX = "workspace.modelo.filing.reconciliation.";

/** The comparison reports its scope and differences; receipt verification
 * continues to come from the declaration's authoritative read model. */
export function ReconciliationResult({
  report,
}: {
  report: ReconciliationReport;
}) {
  const t = useStrings();
  const matches = report.verdict === "matches" && report.diffs.length === 0;
  const limited = !matches || report.advisories.length > 0;
  const value = (text: string) =>
    text === "" ? t(`${PREFIX}not_present`) : text;
  return (
    <div className="modelo-reconciliation flex min-w-0 flex-col gap-4">
      <Alert
        tone={limited ? "warning" : "success"}
        icon={<Icon name={limited ? "alert" : "check"} />}
      >
        {t(`${PREFIX}${matches ? "matches" : "differs"}`)}
      </Alert>
      {report.diffs.length > 0 && (
        <section
          aria-label={t(`${PREFIX}differences`)}
          className="flex min-w-0 flex-col gap-2"
        >
          <h3 className="text-sm font-medium">{t(`${PREFIX}differences`)}</h3>
          <ul className="divide-y divide-border rounded-lg border border-border bg-card">
            {report.diffs.map((diff, index) => (
              <li
                key={`${diff.diff_kind}-${diff.field_name}-${index}`}
                className="flex min-w-0 flex-col gap-2 px-4 py-3"
              >
                <div className="flex flex-wrap gap-x-2 text-base">
                  <span className="text-muted-foreground">
                    {t(`${PREFIX}category.${diff.diff_kind}`)}
                  </span>
                  <span className="min-w-0 font-medium wrap-anywhere">
                    {diff.diff_kind !== "casilla" && FIELDS.has(diff.field_name)
                      ? t(`${PREFIX}field.${diff.field_name}`)
                      : diff.field_name}
                  </span>
                </div>
                <dl className="grid gap-3 @sm:grid-cols-2">
                  <div className="min-w-0">
                    <dt className="text-sm text-muted-foreground">
                      {t(`${PREFIX}work_value`)}
                    </dt>
                    <dd className="text-base whitespace-pre-wrap wrap-anywhere">
                      {value(diff.work_unit_value)}
                    </dd>
                  </div>
                  <div className="min-w-0">
                    <dt className="text-sm text-muted-foreground">
                      {t(`${PREFIX}evidence_value`)}
                    </dt>
                    <dd className="text-base whitespace-pre-wrap wrap-anywhere">
                      {value(diff.evidence_value)}
                    </dd>
                  </div>
                </dl>
                {(["legal_refs", "source_refs"] as const).map(
                  (kind) =>
                    diff[kind].length > 0 && (
                      <div key={kind} className="text-sm">
                        <span className="text-muted-foreground">
                          {t(`${PREFIX}${kind}`)}
                        </span>
                        <ul>
                          {diff[kind].map((ref, index) => (
                            <li
                              key={index}
                              className="select-text wrap-anywhere"
                            >
                              {ref}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ),
                )}
                <details className="text-sm">
                  <summary className="cursor-pointer text-muted-foreground">
                    {t(`${PREFIX}details`)}
                  </summary>
                  <dl className="mt-2">
                    <dt className="text-muted-foreground">
                      {t(`${PREFIX}kind`)}
                    </dt>
                    <dd className="select-text wrap-anywhere">{diff.kind}</dd>
                  </dl>
                </details>
              </li>
            ))}
          </ul>
        </section>
      )}
      {report.advisories.length > 0 && (
        <section
          aria-label={t(`${PREFIX}notices`)}
          className="flex min-w-0 flex-col gap-2"
        >
          <h3 className="text-sm font-medium">{t(`${PREFIX}notices`)}</h3>
          <ul className="divide-y divide-border rounded-lg border border-border bg-card">
            {report.advisories.map((advisory, index) => (
              <li
                key={`${advisory.code}-${index}`}
                className="flex min-w-0 flex-col gap-2 px-4 py-3"
              >
                <p className="text-base whitespace-pre-wrap wrap-anywhere">
                  {advisory.message}
                </p>
                <details className="text-sm">
                  <summary className="cursor-pointer text-muted-foreground">
                    {t(`${PREFIX}details`)}
                  </summary>
                  <dl className="mt-2">
                    <dt className="text-muted-foreground">
                      {t(`${PREFIX}code`)}
                    </dt>
                    <dd className="select-text wrap-anywhere">
                      {advisory.code}
                    </dd>
                  </dl>
                  {advisory.context.length > 0 && (
                    <dl
                      aria-label={t(`${PREFIX}context`)}
                      className="mt-2 flex flex-col gap-1"
                    >
                      {advisory.context.map(([key, text], index) => (
                        <div key={index} className="min-w-0">
                          <dt className="text-muted-foreground wrap-anywhere">
                            {key}
                          </dt>
                          <dd className="select-text whitespace-pre-wrap wrap-anywhere">
                            {text}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </details>
              </li>
            ))}
          </ul>
        </section>
      )}
      {report.narrative !== "" && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">
            {t(`${PREFIX}details`)}
          </summary>
          <p className="mt-2 select-text whitespace-pre-wrap wrap-anywhere">
            {report.narrative}
          </p>
        </details>
      )}
    </div>
  );
}
