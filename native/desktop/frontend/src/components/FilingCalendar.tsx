import { useId, useMemo } from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Empty, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Spinner } from "@/components/ui/spinner";
import { useStrings } from "../shell/strings";
import type {
  CalendarEntry,
  CalendarUserState,
  FilingCalendar,
} from "../shell/views";

/** What the page has to show: the read in flight, why there is nothing to
 * read, or the calendar. A failed read is never drawn as an empty calendar. */
export type CalendarState =
  | { kind: "loading" }
  | { kind: "signed-out" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; calendar: FilingCalendar };

const STATE_TONE: Record<
  CalendarUserState,
  "neutral" | "danger" | "success" | "warning"
> = { due: "neutral", late: "danger", filed: "success", unknown: "warning" };

const DAY_MS = 86_400_000;

/** An ISO date as a local calendar day: no time, so no zone can move it. */
function day(iso: string): Date {
  const [year = 1970, month = 1, date = 1] = iso.split("-").map(Number);
  return new Date(year, month - 1, date);
}

function Entry({
  entry,
  locale,
  onOpen,
}: {
  entry: CalendarEntry;
  locale: string;
  onOpen: (entry: CalendarEntry) => void;
}) {
  const t = useStrings();
  const closes = day(entry.adjusted_closes_on);
  const short = useMemo(
    () => new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }),
    [locale],
  );
  // How far the binding date is from the day the product evaluated: the
  // product's own count where it gives one.
  const away =
    entry.days_overdue !== null
      ? -entry.days_overdue
      : Math.round(
          (closes.getTime() - day(entry.evaluated_on).getTime()) / DAY_MS,
        );
  const relative = new Intl.RelativeTimeFormat(locale, {
    numeric: "auto",
  }).format(away, "day");
  const name = t("desktop.calendar.modelo", { modelo: entry.modelo });
  const notes = [
    t(`desktop.calendar.local.${entry.local_filing_state}`),
    t(`desktop.calendar.aeat.${entry.aeat_submission_state}`),
    entry.adjusted_closes_on !== entry.closes_on
      ? t("desktop.calendar.moved", {
          date: short.format(day(entry.closes_on)),
        })
      : null,
    entry.payment_cutoff_on
      ? t("desktop.calendar.payment_cutoff", {
          date: short.format(day(entry.payment_cutoff_on)),
        })
      : null,
  ].filter((note): note is string => note !== null);
  return (
    <li className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 border-b px-4 py-2 hover:bg-accent">
      <time
        dateTime={entry.adjusted_closes_on}
        className="grid w-10 justify-items-center"
      >
        <span className="text-md leading-tight font-semibold tabular-nums">
          {closes.getDate()}
        </span>
        <span className="text-xs text-muted-foreground">
          {new Intl.DateTimeFormat(locale, { weekday: "short" }).format(closes)}
        </span>
      </time>
      <div className="grid min-w-0 gap-0.5">
        <span className="flex flex-wrap items-baseline gap-x-2">
          <span className="font-medium">{name}</span>
          <span className="text-muted-foreground">{entry.period}</span>
        </span>
        <span className="text-sm text-muted-foreground">
          {notes.join(" · ")}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span className="grid justify-items-end gap-0.5 @max-md:hidden">
          <Badge variant={STATE_TONE[entry.user_state]}>
            {t(`desktop.calendar.state.${entry.user_state}`)}
          </Badge>
          {entry.user_state !== "filed" && (
            <span className="text-xs text-muted-foreground">{relative}</span>
          )}
        </span>
        <Badge variant={STATE_TONE[entry.user_state]} className="@md:hidden">
          {t(`desktop.calendar.state.${entry.user_state}`)}
        </Badge>
        <IconButton
          label={t("desktop.calendar.open_tui")}
          accessibleName={`${t("desktop.calendar.open_tui")}: ${name} ${entry.period}`}
          side="left"
          onClick={() => onOpen(entry)}
        >
          <Icon name="arrow" />
        </IconButton>
      </div>
    </li>
  );
}

/**
 * The filing calendar: every obligation in a range of dates, by month, with
 * the product's own reading of where each stands. It keeps apart what the
 * product keeps apart: the local filing work, what has been seen of the tax
 * agency, and what could not be determined at all.
 */
export function FilingCalendarView({
  state,
  locale,
  refreshing = false,
  onRefresh,
  onSignIn,
  onOpen,
}: {
  state: CalendarState;
  /** The chrome language, for dates. */
  locale: string;
  /** A newer read is in flight over the one shown. */
  refreshing?: boolean;
  onRefresh: () => void;
  onSignIn: () => void;
  /** Take the person to where this obligation is worked on. */
  onOpen: (entry: CalendarEntry) => void;
}) {
  const t = useStrings();
  const heading = useId();
  const calendar = state.kind === "ready" ? state.calendar : null;

  const months = useMemo(() => {
    const month = new Intl.DateTimeFormat(locale, {
      month: "long",
      year: "numeric",
    });
    const groups = new Map<
      string,
      { title: string; entries: CalendarEntry[] }
    >();
    for (const entry of [...(calendar?.entries ?? [])].sort(
      (a, b) =>
        a.adjusted_closes_on.localeCompare(b.adjusted_closes_on) ||
        a.modelo.localeCompare(b.modelo),
    )) {
      const key = entry.adjusted_closes_on.slice(0, 7);
      const group = groups.get(key) ?? {
        title: month.format(day(entry.adjusted_closes_on)),
        entries: [],
      };
      group.entries.push(entry);
      groups.set(key, group);
    }
    return [...groups];
  }, [calendar, locale]);

  if (state.kind === "loading")
    return (
      <Empty role="status">
        <Spinner />
        <EmptyDescription>{t("desktop.calendar.loading")}</EmptyDescription>
      </Empty>
    );
  if (state.kind === "signed-out")
    return (
      <Empty>
        <EmptyMedia>
          <Icon name="lock" />
        </EmptyMedia>
        <EmptyDescription>{t("desktop.calendar.signed_out")}</EmptyDescription>
        <Button onClick={onSignIn}>{t("desktop.signin.submit")}</Button>
      </Empty>
    );
  if (state.kind === "failed")
    return (
      <Empty role="alert">
        <EmptyMedia>
          <Icon name="alert" />
        </EmptyMedia>
        <EmptyDescription>
          {t("desktop.calendar.failed", { code: state.code })}
        </EmptyDescription>
        <Button variant="outline" onClick={onRefresh}>
          {t("desktop.calendar.refresh")}
        </Button>
      </Empty>
    );

  const { warnings, coverage, generated_at } = state.calendar;
  const asOf = generated_at
    ? new Intl.DateTimeFormat(locale, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(generated_at))
    : "—";
  return (
    <div
      className="calendar @container flex min-h-0 flex-1 flex-col overflow-y-auto bg-background"
      aria-busy={refreshing || undefined}
    >
      <div className="flex shrink-0 items-center gap-3 border-b px-4 py-1.5">
        <p className="flex-1 text-sm text-muted-foreground">
          {t("desktop.calendar.as_of", { date: asOf })}
        </p>
        <IconButton
          label={t("desktop.calendar.refresh")}
          pending={refreshing}
          onClick={onRefresh}
        >
          {!refreshing && <Icon name="reset" />}
        </IconButton>
      </div>
      {warnings.length > 0 && (
        <Alert
          tone="warning"
          className="mx-4 mt-3 w-auto"
          icon={<Icon name="alert" />}
        >
          <p>{t("desktop.calendar.warnings")}</p>
          <ul className="mt-1 grid gap-0.5 text-sm">
            {warnings.map((warning) => (
              <li key={warning.code + warning.affected_modelos.join()}>
                {warning.message}
              </li>
            ))}
          </ul>
        </Alert>
      )}
      {months.length === 0 ? (
        <Empty role="status">
          <EmptyMedia>
            <Icon name="calendar" />
          </EmptyMedia>
          <EmptyDescription>{t("desktop.calendar.empty")}</EmptyDescription>
        </Empty>
      ) : (
        months.map(([key, month]) => (
          <section key={key} aria-labelledby={`${heading}-${key}`}>
            <h3
              id={`${heading}-${key}`}
              className={cn(
                "sticky top-0 z-(--layer-separator) border-b bg-background px-4 pt-3 pb-1.5",
                "text-xs font-semibold tracking-wider text-muted-foreground uppercase",
              )}
            >
              {month.title}
            </h3>
            <ul>
              {month.entries.map((entry) => (
                <Entry
                  key={`${entry.modelo}:${entry.period}`}
                  entry={entry}
                  locale={locale}
                  onOpen={onOpen}
                />
              ))}
            </ul>
          </section>
        ))
      )}
      {coverage.advised.length > 0 && (
        <p className="px-4 py-3 text-sm text-muted-foreground">
          {t("desktop.calendar.undetermined", {
            modelos: coverage.advised.map((item) => item.modelo).join(", "),
          })}
        </p>
      )}
    </div>
  );
}
