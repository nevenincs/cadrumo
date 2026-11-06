import type { ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { formatAmount } from "../../../shared/numbers";
import type { ModeloFormAddressV1 } from "../../../shell/modeloContract/modeloEditWork";
import type { ModeloTaxationComparisonProjection } from "../../../shell/modeloContract/modeloWork";
import type { PublicModeloFormField } from "../../../shell/modeloContract/modeloWorkForm";
import { useStrings } from "../../../shell/strings";
import { BoxNumber } from "../form/BoxNumber";
import { BoxLabel } from "./BoxLabel";
import type { TaxationComparisonRead } from "./taxationComparisonRead";

// The same declaration worked out twice, filed jointly and filed individually,
// on the values it holds, as the application served it. It is a comparison and
// changes nothing. The recommendation, its reason and the scope caveat of the
// individual figure are the application's words, said in the language it said
// them in; a refusal is shown in its own words with the boxes it names as
// links to the form, and a refusal that the profile puts right leads to the
// profile. The window words only its own frame and does no arithmetic.

/** The refusals the profile puts right: what the household states decides
 * whether the declaration can be filed jointly. */
const PROFILE_REFUSALS: ReadonlySet<string> = new Set([
  "spouse_unstated",
  "family_situation_unstated",
  "no_family_unit",
]);

const CURRENCY = "EUR";

/** The name of a language, in the window's own. */
function languageName(locale: string, code: string): string {
  try {
    return (
      new Intl.DisplayNames([locale], { type: "language" }).of(code) ?? code
    );
  } catch {
    return code;
  }
}

function Mode({
  mode,
  title,
  recommended,
  tax,
  result,
  locale,
}: {
  mode: "joint" | "individual";
  title: string;
  recommended: boolean;
  tax: string;
  result: string;
  locale: string;
}) {
  const t = useStrings();
  return (
    <div
      data-comparison-mode={mode}
      data-recommended={recommended}
      className={cn(
        "flex flex-col gap-3 rounded-lg border bg-card p-4",
        recommended ? "border-primary" : "border-border",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-base font-medium">{title}</h4>
        {recommended && (
          <Badge variant="success">
            {t("desktop.modelo.compare.taxation.recommended")}
          </Badge>
        )}
      </div>
      <dl className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-sm text-muted-foreground">
            {t("desktop.modelo.compare.taxation.tax")}
          </dt>
          <dd
            data-comparison-tax=""
            className="font-mono text-base tabular-nums"
          >
            {formatAmount(locale, tax, { currency: CURRENCY })}
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-sm text-muted-foreground">
            {t("desktop.modelo.compare.taxation.result")}
          </dt>
          <dd
            data-comparison-result-amount=""
            className="font-mono text-md font-semibold tabular-nums"
          >
            {formatAmount(locale, result, { currency: CURRENCY })}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function Result({
  projection,
  locale,
}: {
  projection: ModeloTaxationComparisonProjection;
  locale: string;
}) {
  const t = useStrings();
  return (
    <div
      data-comparison-result=""
      data-recommendation={projection.recommendation}
      className="flex flex-col gap-4"
    >
      <div className="grid grid-cols-1 gap-3 @2xl:grid-cols-2">
        <Mode
          mode="joint"
          title={t("desktop.modelo.compare.taxation.joint")}
          recommended={projection.recommendation === "conjunta"}
          tax={projection.conjunta_cuota_resultante}
          result={projection.conjunta_resultado}
          locale={locale}
        />
        <Mode
          mode="individual"
          title={t("desktop.modelo.compare.taxation.individual")}
          recommended={projection.recommendation === "individual"}
          tax={projection.individual_cuota_resultante}
          result={projection.individual_resultado}
          locale={locale}
        />
      </div>
      <p data-comparison-reason="" className="text-base">
        {projection.recommendation_reason_words}
      </p>
      <p
        data-comparison-caveat=""
        className="flex items-start gap-2 text-sm text-muted-foreground"
      >
        <Icon name="info" size="xs" className="mt-0.5 shrink-0" />
        <span>{projection.individual_branch_caveat}</span>
      </p>
      {projection.words_language !== locale && (
        <p className="text-xs text-faint">
          {t("desktop.modelo.compare.words_language", {
            language: languageName(locale, projection.words_language),
          })}
        </p>
      )}
    </div>
  );
}

/** The boxes a refusal names as without a value, each a link to its place in
 * the form. A box the form does not place is named, not linked. */
function NamedBoxes({
  boxes,
  fieldAt,
  onGo,
}: {
  boxes: readonly string[];
  fieldAt(address: ModeloFormAddressV1): PublicModeloFormField | null;
  onGo(address: ModeloFormAddressV1): void;
}) {
  const t = useStrings();
  return (
    <ul
      aria-label={t("desktop.modelo.compare.taxation.boxes")}
      data-comparison-boxes=""
      className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card"
    >
      {boxes.map((id) => {
        const address: ModeloFormAddressV1 = {
          kind: "casilla",
          casilla_id: id,
        };
        const field = fieldAt(address);
        const name: ReactNode = (
          <span className="flex min-w-0 items-start gap-2">
            <BoxNumber box={field?.box ?? id} />
            {field && (
              <span className="min-w-0 text-base">
                <BoxLabel text={field.label} />
              </span>
            )}
          </span>
        );
        return (
          <li key={id} data-comparison-box={id} className="px-4 py-2.5">
            {field ? (
              <button
                type="button"
                onClick={() => onGo(address)}
                aria-label={t("workspace.modelo.sources.go_to_box", {
                  box: field.box ?? id,
                })}
                className="w-full rounded-sm text-left focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                {name}
              </button>
            ) : (
              name
            )}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * The comparison of joint and individual filing. `onAsk` is null where this
 * window cannot ask. `onGo` opens a box in the form; `onOpenProfile` opens
 * the profile, where a refusal that the household answers is put right, and is
 * null where the window has no profile page.
 */
export function TaxationComparison({
  read,
  onAsk,
  locale,
  fieldAt,
  onGo,
  onOpenProfile,
}: {
  read: TaxationComparisonRead;
  onAsk: (() => void) | null;
  locale: string;
  fieldAt(address: ModeloFormAddressV1): PublicModeloFormField | null;
  onGo(address: ModeloFormAddressV1): void;
  onOpenProfile: (() => void) | null;
}) {
  const t = useStrings();
  const reading = read.phase === "reading";
  return (
    <section
      aria-label={t("desktop.modelo.compare.taxation.title")}
      data-taxation-comparison=""
      data-phase={read.phase}
      className="@container flex flex-col gap-3 rounded-xl border border-border bg-card p-5"
    >
      <h3 className="text-md font-medium">
        {t("desktop.modelo.compare.taxation.title")}
      </h3>
      <p className="text-base text-muted-foreground">
        {t("desktop.modelo.compare.taxation.lead")}
      </p>
      {onAsk && (
        <Button
          variant="outline"
          className="self-start"
          disabled={reading}
          aria-busy={reading}
          data-comparison-ask=""
          onClick={onAsk}
        >
          {reading ? <Spinner /> : <Icon name="sync" size="xs" />}
          {read.phase === "ready" || read.phase === "refused"
            ? t("desktop.modelo.compare.again")
            : t("desktop.modelo.compare.taxation.ask")}
        </Button>
      )}
      {read.phase === "refused" && (
        <div
          data-comparison-refusal={read.refusal ?? ""}
          className="flex flex-col gap-3"
        >
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {read.words ?? t("desktop.modelo.compare.taxation.refused")}
          </Alert>
          {read.boxes.length > 0 && (
            <NamedBoxes boxes={read.boxes} fieldAt={fieldAt} onGo={onGo} />
          )}
          {read.refusal !== null &&
            PROFILE_REFUSALS.has(read.refusal) &&
            onOpenProfile && (
              <Button
                variant="outline"
                className="self-start"
                data-comparison-profile=""
                onClick={onOpenProfile}
              >
                {t("desktop.modelo.compare.taxation.open_profile")}
                <Icon name="forward" size="xs" />
              </Button>
            )}
        </div>
      )}
      {read.phase === "failed" && (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {t("desktop.modelo.compare.failed")}
        </Alert>
      )}
      {read.phase === "ready" && (
        <Result projection={read.projection} locale={locale} />
      )}
    </section>
  );
}
