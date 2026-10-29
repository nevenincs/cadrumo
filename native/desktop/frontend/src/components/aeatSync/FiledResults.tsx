import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { aeatSyncDay } from "../../shell/aeatSync";
import type { FiledMatch, FiledRow } from "../../shell/aeatSyncResults";
import { useStrings, type Translate } from "../../shell/strings";

const GROUPS: readonly FiledMatch[] = [
  "aeat_only",
  "differing",
  "local_only",
  "matched",
];

function title(t: Translate, row: FiledRow): string {
  return row.period
    ? t("desktop.aeat_sync.results.filed.title_period", {
        form: row.form,
        period: row.period,
        year: row.year,
      })
    : t("desktop.aeat_sync.results.filed.title_year", {
        form: row.form,
        year: row.year,
      });
}

/** One declaration with its three separate facts: the profile's own record,
 * what AEAT shows, and whether AEAT's receipt was confirmed. */
function Row({ row, language }: { row: FiledRow; language: string }) {
  const t = useStrings();
  const day = (value: string) => aeatSyncDay(language, value) ?? value;
  const record = row.record
    ? t(`desktop.aeat_sync.results.filed.record.${row.record.status}`, {
        date: day(row.record.on),
      })
    : t("desktop.aeat_sync.results.filed.record.none");
  const aeat = row.aeat
    ? t("desktop.aeat_sync.results.filed.aeat.shown", {
        date: day(row.aeat.seen_on),
      })
    : t("desktop.aeat_sync.results.filed.aeat.none");
  const confirmed = row.receipt === "confirmed";
  return (
    <li
      data-match={row.match}
      className="flex flex-col gap-1 border-t py-2 first:border-t-0"
    >
      <span className="flex flex-wrap items-center gap-2">
        <span className="text-base font-medium text-foreground">
          {title(t, row)}
        </span>
        {row.differences.map((difference) => (
          <Badge key={difference} variant="warning">
            {t(`desktop.aeat_sync.results.filed.differs.${difference}`)}
          </Badge>
        ))}
      </span>
      <dl className="grid gap-x-4 gap-y-1 text-sm @lg/aeat:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">
            {t("desktop.aeat_sync.results.filed.column.record")}
          </dt>
          <dd className="text-foreground">{record}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t("desktop.aeat_sync.results.filed.column.aeat")}
          </dt>
          <dd className="text-foreground">{aeat}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t("desktop.aeat_sync.results.filed.column.receipt")}
          </dt>
          <dd className="flex items-center gap-1 text-foreground">
            <Icon name={confirmed ? "check" : "pending"} size="xs" />
            {t(
              confirmed
                ? "desktop.aeat_sync.results.filed.receipt.confirmed"
                : "desktop.aeat_sync.results.filed.receipt.not_confirmed",
            )}
          </dd>
        </div>
      </dl>
    </li>
  );
}

/**
 * Filed declarations as AEAT shows them, set against the profile's own
 * records: the ones only AEAT shows, the ones that differ, the ones only the
 * profile has, and the ones that match. The three facts of a declaration are
 * kept apart, so a matching record is never read as a confirmed receipt.
 */
export function FiledResults({
  rows,
  language,
}: {
  rows: readonly FiledRow[];
  language: string;
}) {
  const t = useStrings();
  if (rows.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        {t("desktop.aeat_sync.results.filed.empty")}
      </p>
    );
  return (
    <div className="flex flex-col gap-3">
      {GROUPS.map((match) => {
        const group = rows.filter((row) => row.match === match);
        if (group.length === 0) return null;
        const heading = t(`desktop.aeat_sync.results.filed.group.${match}`, {
          count: group.length,
        });
        const list = (
          <ul>
            {group.map((row) => (
              <Row
                key={`${row.form}:${row.year}:${row.period ?? ""}`}
                row={row}
                language={language}
              />
            ))}
          </ul>
        );
        return match === "matched" ? (
          <details key={match} data-group={match} className="group">
            <summary className="cursor-pointer text-base font-medium text-foreground">
              {heading}
            </summary>
            {list}
          </details>
        ) : (
          <section key={match} data-group={match} aria-label={heading}>
            <h4 className="text-base font-medium text-foreground">{heading}</h4>
            {list}
          </section>
        );
      })}
    </div>
  );
}
