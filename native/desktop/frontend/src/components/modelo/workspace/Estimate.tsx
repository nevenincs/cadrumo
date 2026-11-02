import type { ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import type {
  ModeloFormAddressV1,
  ModeloProjectOperationProjection,
  PublicModeloFormField,
} from "../../../shell/modeloContract";
import { useStrings } from "../../../shell/strings";
import type { OpenableSurface } from "../details/Details";
import { BoxNumber } from "../form/BoxNumber";
import { Label } from "../form/FieldRow";
import { estimateFigure, type EstimateRead } from "./estimate";

// The estimate of the annual return from the quarterly declarations, as the
// application served it: marked as an estimate, with the boxes it could not
// give a figure for and the words of why, never a zero. The window words only
// its own frame; every explanation is the application's, in the language the
// application said it in.

type Figures = ModeloProjectOperationProjection["casilla_observations"];

/** The name of a language, in the window's own. */
function languageName(locale: string, code: string): string {
  try {
    return new Intl.DisplayNames([locale], { type: "language" }).of(code) ?? code;
  } catch {
    return code;
  }
}

/** A box named by its printed number and the form's label for it. */
function BoxName({ field, box }: { field: PublicModeloFormField | null; box: string | null }) {
  return (
    <span className="flex min-w-0 items-start gap-2">
      <BoxNumber box={box} />
      {field && (
        <span className="min-w-0 text-base">
          <Label text={field.label} />
        </span>
      )}
    </span>
  );
}

function Unresolved({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h4 className="text-sm font-medium text-muted-foreground">{title}</h4>
      {children}
    </section>
  );
}

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
  // Boxes left without a figure for one reason share the sentence that says it.
  const reasons = new Map<string, string[]>();
  for (const row of projection.unresolved_casillas)
    reasons.set(row.reason_words, [
      ...(reasons.get(row.reason_words) ?? []),
      row.casilla_id,
    ]);
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
      {projection.unresolved_bindings.length > 0 && (
        <Unresolved title={t("desktop.modelo.credits.estimate.unresolved_credits")}>
          <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
            {projection.unresolved_bindings.map((row) => (
              <li
                key={row.binding_id}
                data-unresolved-credit={row.casilla_id ?? row.binding_id}
                className="flex flex-col gap-1 px-4 py-3"
              >
                <BoxName field={named(row.casilla_id)} box={row.casilla_id} />
                {row.source_words && (
                  <span className="text-sm text-faint">{row.source_words}</span>
                )}
                <span className="text-sm text-muted-foreground">{row.words}</span>
              </li>
            ))}
          </ul>
        </Unresolved>
      )}
      {reasons.size > 0 && (
        <Unresolved title={t("desktop.modelo.credits.estimate.unresolved_boxes")}>
          {[...reasons].map(([words, boxes]) => (
            <div
              key={words}
              className="flex flex-col gap-2 rounded-lg border border-border bg-card px-4 py-3"
            >
              <ul className="flex flex-col gap-1.5">
                {boxes.map((box) => (
                  <li key={box} data-unresolved-box={box}>
                    <BoxName field={named(box)} box={box} />
                  </li>
                ))}
              </ul>
              <span className="text-sm text-muted-foreground">{words}</span>
            </div>
          ))}
        </Unresolved>
      )}
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
 * draws them under the form's own words for each box.
 */
export function Estimate({
  read,
  onAsk,
  locale,
  fieldAt,
  results,
  onOpenSurface,
  canOpenSurface,
}: {
  read: EstimateRead;
  /** Asks for the estimate, or null where this window cannot. */
  onAsk: (() => void) | null;
  locale: string;
  fieldAt(address: ModeloFormAddressV1): PublicModeloFormField | null;
  results: readonly string[];
  onOpenSurface(surface: OpenableSurface): void;
  canOpenSurface(surface: OpenableSurface): boolean;
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
          onClick={onAsk}
        >
          {reading ? (
            <Spinner />
          ) : (
            <Icon name="sync" size="xs" />
          )}
          {read.phase === "ready"
            ? t("desktop.modelo.credits.estimate.again")
            : t("desktop.modelo.credits.estimate.ask")}
        </Button>
      )}
      {read.phase === "needs_region" && (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          <span>{t("desktop.modelo.credits.estimate.needs_region")}</span>
          {canOpenSurface("profile") && (
            <Button
              size="sm"
              variant="link"
              className="justify-self-start"
              onClick={() => onOpenSurface("profile")}
            >
              {t("workspace.modelo.surface.open.profile")}
              <Icon name="forward" size="xs" />
            </Button>
          )}
        </Alert>
      )}
      {read.phase === "refused" && (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {read.words ?? t("desktop.modelo.credits.estimate.refused")}
        </Alert>
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
