import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import type { LedgerNextStep } from "../../../shell/ledger";
import type { ModeloFormAddressV1 } from "../../../shell/modeloContract/modeloEditWork";
import type { ModeloProjectOperationProjection } from "../../../shell/modeloContract/modeloProject";
import type { PublicModeloFormField } from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import {
  estimateAmount,
  estimateFigure,
  estimateFigures,
  type EstimateRead,
} from "./estimateRead";
import { BoxName } from "./BoxName";
import { languageName, UnresolvedFindings } from "./UnresolvedFindings";

// The estimate of the annual return from the quarterly declarations, as the
// application served it: marked as an estimate, with the boxes it could not
// give a figure for and the words of why, never a zero. The window words only
// its own frame; every explanation is the application's, in the language the
// application said it in.

type Figures = ModeloProjectOperationProjection["casilla_observations"];

function Result({
  projection,
  locale,
  fieldAt,
  results,
}: {
  projection: ModeloProjectOperationProjection;
  locale: string;
  fieldAt(address: ModeloFormAddressV1): PublicModeloFormField | null;
  /** The boxes the form states its result in. */
  results: readonly string[];
}) {
  const t = useStrings();
  const named = (box: string | null) =>
    box ? fieldAt({ kind: "casilla", casilla_id: box }) : null;
  const given: Figures = projection.casilla_observations.filter((row) =>
    results.includes(row.casilla_id),
  );
  const nothingLeft =
    projection.unresolved_bindings.length === 0 &&
    projection.unresolved_casillas.length === 0;
  return (
    <div data-estimate-result className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        {t("desktop.modelo.credits.estimate.quarters", {
          count: projection.quarters_filed,
        })}
        {projection.is_extrapolated &&
          ` ${t("desktop.modelo.credits.estimate.extrapolated")}`}
      </p>
      <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
        {estimateFigures(projection).map((figure) => (
          <li
            key={figure.id}
            data-estimate-figure={figure.id}
            className="flex items-center justify-between gap-3 px-4 py-3"
          >
            <span className="min-w-0 text-base">{figure.label}</span>
            <span className="font-mono text-base tabular-nums">
              {estimateAmount(locale, figure.value)}
            </span>
          </li>
        ))}
      </ul>
      {given.length > 0 && (
        <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
          {given.map((row) => {
            const field = named(row.casilla_id);
            return (
              <li
                key={row.casilla_id}
                data-estimate-box={row.casilla_id}
                className="flex items-center justify-between gap-3 px-4 py-3"
              >
                <BoxName field={field} box={row.casilla_id} />
                <span className="font-mono text-base tabular-nums">
                  {estimateFigure(locale, field, row.value)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      <UnresolvedFindings
        bindings={projection.unresolved_bindings}
        casillas={projection.unresolved_casillas}
        bindingsTitle={t("desktop.modelo.credits.estimate.unresolved_credits")}
        casillasTitle={t("desktop.modelo.credits.estimate.unresolved_boxes")}
        boxName={(box) => <BoxName field={named(box)} box={box} />}
      />
      {nothingLeft && (
        <p className="text-sm text-muted-foreground">
          {t("desktop.modelo.credits.estimate.nothing_left")}
        </p>
      )}
      {projection.words_language !== locale && (
        <p className="text-xs text-faint">
          {t("desktop.modelo.credits.estimate.words_language", {
            language: languageName(locale, projection.words_language),
          })}
        </p>
      )}
    </div>
  );
}

/**
 * The estimate asked for on request: what it is, what to do to get one, and
 * what came back. The figures and the reasons are the application's; this
 * draws them under the form's own words for each box. A refusal can name the
 * step that puts it right, which is offered in the application's words and
 * run by the workspace.
 */
export function Estimate({
  read,
  onAsk,
  onStep,
  locale,
  fieldAt,
  results,
}: {
  read: EstimateRead;
  /** Asks for the estimate, or null where this window cannot. */
  onAsk: (() => void) | null;
  /** Runs the step a refusal names, or null where this window cannot. */
  onStep: ((step: LedgerNextStep) => void) | null;
  locale: string;
  fieldAt(address: ModeloFormAddressV1): PublicModeloFormField | null;
  results: readonly string[];
}) {
  const t = useStrings();
  const reading = read.phase === "reading";
  return (
    <section
      aria-label={t("desktop.modelo.credits.estimate.title")}
      data-estimate=""
      className="flex flex-col gap-3 rounded-xl border border-dashed border-border-strong p-5"
    >
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-md font-medium">
          {t("desktop.modelo.credits.estimate.title")}
        </h3>
        <Badge variant="warning">
          {t("desktop.modelo.credits.estimate.mark")}
        </Badge>
      </div>
      <p className="text-base text-muted-foreground">
        {t("desktop.modelo.credits.estimate.lead")}
      </p>
      {onAsk && (
        <Button
          variant="outline"
          className="self-start"
          disabled={reading}
          aria-busy={reading}
          data-estimate-ask=""
          onClick={onAsk}
        >
          {reading ? <Spinner /> : <Icon name="sync" size="xs" />}
          {read.phase === "ready"
            ? t("desktop.modelo.credits.estimate.again")
            : t("desktop.modelo.credits.estimate.ask")}
        </Button>
      )}
      {read.phase === "refused" && (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {read.words ?? t("desktop.modelo.credits.estimate.refused")}
        </Alert>
      )}
      {read.phase === "refused" && read.step && onStep && (
        <Button
          className="self-start"
          data-estimate-step={read.step.kind}
          onClick={() => read.step && onStep(read.step)}
        >
          {read.step.words}
          <Icon name="forward" size="xs" />
        </Button>
      )}
      {read.phase === "failed" && (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {t("desktop.modelo.credits.estimate.failed")}
        </Alert>
      )}
      {read.phase === "ready" && (
        <Result
          projection={read.projection}
          locale={locale}
          fieldAt={fieldAt}
          results={results}
        />
      )}
    </section>
  );
}
