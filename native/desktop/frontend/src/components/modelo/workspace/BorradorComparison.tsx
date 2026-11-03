import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { formatInstantDay } from "../../../shared/dateFormats";
import { formatDecimal } from "../../../shared/numbers";
import type {
  BorradorCompared,
  BorradorComparison as Comparison,
  BorradorScalar,
} from "../../../shell/borrador";
import { useStrings, type Translate } from "../../../shell/strings";
import { BoxNumber } from "../form/BoxNumber";
import { BoxLabel } from "./BoxLabel";
import type { BorradorComparisonRead } from "./borradorComparisonRead";

// What the AEAT printed in its draft, beside what this computer worked out for
// the same declaration, box by box. The draft is an observation of the AEAT's
// own, imported here: it never fills the declaration and it is not a filing,
// and the calculation is local. The two sides are drawn in columns that say
// which is which, and every status, classification and reason is the
// application's sentence. A box with no value on a side shows that it has none;
// it is never drawn as zero, and nothing here says the boxes agree except each
// box's own classification.

/** The order the groups of boxes are drawn in, the ones that need a look
 * first. A group the application serves that is not listed follows. */
const GROUP_ORDER = [
  "differ",
  "only_in_borrador",
  "only_in_calculation",
  "agree",
  "not_comparable",
] as const;

/** The mark of each classification, so the groups are told apart by more than
 * their words. */
const GROUP_MARK: Record<string, IconName> = {
  differ: "alert",
  only_in_borrador: "swap",
  only_in_calculation: "swap",
  agree: "check",
  not_comparable: "unknown",
};

/** A value of either side as the window writes it; a side with none says so. */
function Value({
  value,
  locale,
  t,
}: {
  value: BorradorScalar | null;
  locale: string;
  t: Translate;
}) {
  if (value === null)
    return (
      <span className="text-sm text-faint italic">
        {t("desktop.modelo.compare.borrador.no_value")}
      </span>
    );
  if (typeof value === "object")
    return (
      <span className="font-mono tabular-nums">
        {formatDecimal(locale, value.decimal, { minFraction: 2 })}
      </span>
    );
  if (typeof value === "boolean")
    return (
      <span>
        {t(value ? "desktop.ledger.form.yes" : "desktop.ledger.form.no")}
      </span>
    );
  return <span className="font-mono tabular-nums">{String(value)}</span>;
}

function Row({
  row,
  locale,
  t,
}: {
  row: BorradorCompared;
  locale: string;
  t: Translate;
}) {
  return (
    <li
      data-borrador-box={row.casilla_id}
      data-classification={row.classification.token}
      data-reason={row.reason.token}
      className="grid grid-cols-[minmax(0,1fr)_minmax(0,auto)_minmax(0,auto)] items-start gap-x-4 gap-y-1 px-4 py-3"
    >
      <span className="flex min-w-0 items-start gap-2">
        <BoxNumber box={row.box} />
        <span className="min-w-0 text-base">
          <BoxLabel text={row.label} />
        </span>
      </span>
      <span
        data-borrador-value=""
        className="min-w-24 border-l border-dashed border-border-strong pl-3 text-right text-base"
      >
        <Value value={row.borrador_value} locale={locale} t={t} />
      </span>
      <span data-calculation-value="" className="min-w-24 text-right text-base">
        <Value value={row.calculation_value} locale={locale} t={t} />
      </span>
      <span className="col-span-3 text-sm text-muted-foreground">
        {row.reason.words}
        {row.difference && (
          <span data-borrador-difference={row.difference.decimal}>
            {" "}
            {t("desktop.modelo.compare.borrador.difference", {
              amount: formatDecimal(locale, row.difference.decimal, {
                minFraction: 2,
              }),
            })}
          </span>
        )}
      </span>
    </li>
  );
}

/** The boxes, in groups by how their two values stand. A group's name is the
 * application's classification sentence, taken from its boxes. */
function Rows({
  comparison,
  locale,
  t,
}: {
  comparison: Comparison;
  locale: string;
  t: Translate;
}) {
  const groups = new Map<string, BorradorCompared[]>();
  for (const row of comparison.rows)
    groups.set(row.classification.token, [
      ...(groups.get(row.classification.token) ?? []),
      row,
    ]);
  const order = [
    ...GROUP_ORDER.filter((token) => groups.has(token)),
    ...[...groups.keys()].filter(
      (token) => !(GROUP_ORDER as readonly string[]).includes(token),
    ),
  ];
  return (
    <div className="flex flex-col gap-4">
      <div
        aria-hidden="true"
        className="grid grid-cols-[minmax(0,1fr)_minmax(0,auto)_minmax(0,auto)] gap-x-4 px-4 text-xs text-muted-foreground"
      >
        <span />
        <span className="min-w-24 pl-3 text-right">
          {t("desktop.modelo.compare.borrador.draft")}
        </span>
        <span className="min-w-24 text-right">
          {t("desktop.modelo.compare.borrador.calculation")}
        </span>
      </div>
      {order.map((token) => {
        const rows = groups.get(token) ?? [];
        const name = rows[0]?.classification.words ?? token;
        return (
          <section
            key={token}
            data-borrador-group={token}
            data-count={rows.length}
            aria-label={name}
            className="flex flex-col gap-2"
          >
            <h4 className="flex items-center gap-2 text-sm font-medium">
              <Icon
                name={GROUP_MARK[token] ?? "unknown"}
                size="xs"
                className="text-muted-foreground"
              />
              {name}
              <Badge variant="neutral">{rows.length}</Badge>
            </h4>
            <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
              {rows.map((row) => (
                <Row key={row.casilla_id} row={row} locale={locale} t={t} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

/** One side of the comparison: what kind of evidence it is, in the
 * application's words, and when it was made. */
function Side({
  side,
  title,
  mark,
  evidence,
  at,
  locale,
}: {
  side: "draft" | "calculation";
  title: string;
  mark: string | null;
  evidence: string;
  at: string;
  locale: string;
}) {
  return (
    <div
      data-borrador-side={side}
      className={
        side === "draft"
          ? "flex flex-col gap-1 rounded-lg border border-dashed border-border-strong p-3"
          : "flex flex-col gap-1 rounded-lg border border-border p-3"
      }
    >
      <span className="flex flex-wrap items-center gap-2 text-sm font-medium">
        {title}
        {mark && <Badge variant="neutral">{mark}</Badge>}
      </span>
      <span className="text-sm text-muted-foreground">{evidence}</span>
      <span className="text-xs text-faint">{formatInstantDay(locale, at)}</span>
    </div>
  );
}

function Ready({
  comparison,
  locale,
}: {
  comparison: Comparison;
  locale: string;
}) {
  const t = useStrings();
  const compared = comparison.status.token === "compared";
  return (
    <div
      data-borrador-result=""
      data-status={comparison.status.token}
      className="flex flex-col gap-4"
    >
      <Alert
        tone={compared ? "neutral" : "warning"}
        icon={<Icon name={compared ? "info" : "alert"} />}
      >
        <span data-borrador-status="">{comparison.status.words}</span>
      </Alert>
      {comparison.stale_reasons.length > 0 && (
        <ul data-borrador-stale="" className="flex flex-col gap-1.5">
          {comparison.stale_reasons.map((reason) => (
            <li
              key={reason.token}
              data-stale-reason={reason.token}
              className="flex items-start gap-2 text-sm text-muted-foreground"
            >
              <Icon name="clock" size="xs" className="mt-0.5 shrink-0" />
              {reason.words}
            </li>
          ))}
        </ul>
      )}
      {(comparison.refused_captures > 0 ||
        comparison.outdated_stored_captures > 0) && (
        <ul data-borrador-unread="" className="flex flex-col gap-1.5">
          {comparison.refused_captures > 0 && (
            <li
              data-refused-captures={comparison.refused_captures}
              className="text-sm text-muted-foreground"
            >
              {t("desktop.modelo.compare.borrador.refused", {
                count: comparison.refused_captures,
              })}
            </li>
          )}
          {comparison.outdated_stored_captures > 0 && (
            <li
              data-outdated-captures={comparison.outdated_stored_captures}
              className="text-sm text-muted-foreground"
            >
              {t("desktop.modelo.compare.borrador.outdated", {
                count: comparison.outdated_stored_captures,
              })}
            </li>
          )}
        </ul>
      )}
      {(comparison.capture || comparison.calculation) && (
        <div className="grid grid-cols-1 gap-3 @2xl:grid-cols-2">
          {comparison.capture && (
            <Side
              side="draft"
              title={t("desktop.modelo.compare.borrador.draft")}
              mark={t("desktop.modelo.compare.borrador.observation")}
              evidence={comparison.capture.evidence.words}
              at={comparison.capture.captured_at}
              locale={locale}
            />
          )}
          {comparison.calculation && (
            <Side
              side="calculation"
              title={t("desktop.modelo.compare.borrador.calculation")}
              mark={null}
              evidence={comparison.calculation.evidence.words}
              at={comparison.calculation.created_at}
              locale={locale}
            />
          )}
        </div>
      )}
      {comparison.rows.length > 0 && (
        <Rows comparison={comparison} locale={locale} t={t} />
      )}
    </div>
  );
}

/**
 * The year's AEAT draft beside the saved calculation. `onAsk` is null where
 * this window has no way to read the profile's drafts.
 */
export function BorradorComparison({
  read,
  onAsk,
  locale,
}: {
  read: BorradorComparisonRead;
  onAsk: (() => void) | null;
  locale: string;
}) {
  const t = useStrings();
  const reading = read.phase === "reading";
  return (
    <section
      aria-label={t("desktop.modelo.compare.borrador.title")}
      data-borrador-comparison=""
      data-phase={read.phase}
      className="@container flex flex-col gap-3 rounded-xl border border-border bg-card p-5"
    >
      <h3 className="text-md font-medium">
        {t("desktop.modelo.compare.borrador.title")}
      </h3>
      <p className="text-base text-muted-foreground">
        {t("desktop.modelo.compare.borrador.lead")}
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
          {read.phase === "ready"
            ? t("desktop.modelo.compare.again")
            : t("desktop.modelo.compare.borrador.ask")}
        </Button>
      )}
      {read.phase === "failed" && (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {t("desktop.modelo.compare.failed")}
        </Alert>
      )}
      {read.phase === "ready" && (
        <Ready comparison={read.comparison} locale={locale} />
      )}
    </section>
  );
}
