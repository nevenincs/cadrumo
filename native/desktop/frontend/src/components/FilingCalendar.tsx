import {
  useEffect,
  useId,
  useMemo,
  useRef,
  type ReactNode,
  type RefObject,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  Empty,
  EmptyDescription,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Spinner } from "@/components/ui/spinner";
import type { CalendarState } from "../shell/calendar";
import { useStrings } from "../shell/strings";
import type { CalendarEntry, CalendarUserState } from "../shell/views";

const STATE_TONE: Record<
  CalendarUserState,
  "neutral" | "danger" | "success" | "warning"
> = { due: "neutral", late: "danger", filed: "success", unknown: "warning" };

// What needs the person first comes first.
const STATE_ORDER: readonly CalendarUserState[] = [
  "late",
  "due",
  "unknown",
  "filed",
];

const DAY_MS = 86_400_000;
/** Beyond this many days ahead, a distance is said in months. */
const FAR_DAYS = 60;
const MONTH_DAYS = 365.25 / 12;

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
  onOpen?: (entry: CalendarEntry) => void;
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
  // A filed obligation has no distance left to say. Lateness is said in
  // the product's own days. A date far ahead is said in months, as it is
  // read: the day itself is beside it.
  const distance = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const relative =
    entry.user_state === "filed"
      ? null
      : entry.days_overdue === null && away > FAR_DAYS
        ? distance.format(Math.round(away / MONTH_DAYS), "month")
        : distance.format(away, "day");
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
    <li
      className={cn(
        "grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 border-b px-4 py-2",
        // A row answers the pointer only where it leads somewhere.
        onOpen && "hover:bg-accent",
      )}
    >
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
        {/* In a narrow pane the distance moves under the notes: it is what
            the person came for, and is never the thing left out. */}
        {relative && (
          <span className="calendar-distance text-sm text-muted-foreground @md:hidden">
            {relative}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span className="grid justify-items-end gap-0.5">
          <Badge variant={STATE_TONE[entry.user_state]}>
            {t(`desktop.calendar.state.${entry.user_state}`)}
          </Badge>
          {relative && (
            <span className="calendar-distance text-xs text-muted-foreground @max-md:hidden">
              {relative}
            </span>
          )}
        </span>
        {onOpen && (
          <IconButton
            label={t("desktop.calendar.open_tui")}
            accessibleName={`${t("desktop.calendar.open_tui")}: ${name} ${entry.period}`}
            side="left"
            onClick={() => onOpen(entry)}
          >
            <Icon name="arrow" />
          </IconButton>
        )}
      </div>
    </li>
  );
}

/** Why the calendar is withheld, in the account's own words. */
export type CalendarGate = {
  title: string;
  lead?: string;
  /** The account is still being read: a wait, not a refusal. */
  pending?: boolean;
};

/**
 * The filing calendar: every obligation in a range of dates, by month, with
 * the product's own reading of where each stands. It keeps apart what the
 * product keeps apart: the local filing work, what has been seen of the tax
 * agency, and what could not be determined at all.
 *
 * The page is one region that scrolls and can hold focus, so the keyboard
 * scrolls it from wherever focus is inside. A control that held focus and
 * has gone, because the read it asked for answered or the sign-in ended,
 * leaves focus on the page rather than on nothing.
 */
export function FilingCalendarView({
  state,
  gate,
  locale,
  refreshing = false,
  page,
  onRefresh,
  onSignIn,
  onOpen,
}: {
  state: CalendarState;
  /** What a withheld calendar says. Signed out, where it is left out. */
  gate?: CalendarGate;
  /** The chrome language, for dates. */
  locale: string;
  /** A newer read is in flight over what is shown. */
  refreshing?: boolean;
  /** The page's own element, for whoever sends focus to it. */
  page?: RefObject<HTMLElement | null>;
  onRefresh: () => void;
  /** Left out where a password cannot settle the account as it stands. */
  onSignIn?: () => void;
  /** Take the person to where this obligation is worked on. Left out where
   * the window cannot: no row then offers a way it does not have. */
  onOpen?: (entry: CalendarEntry) => void;
}) {
  const t = useStrings();
  const heading = useId();
  const own = useRef<HTMLElement>(null);
  const root = page ?? own;
  const calendar = state.kind === "ready" ? state.calendar : null;

  // Whether the last thing focused or pressed was in the page. Removing a
  // focused control reports nothing, so this is how its loss is known.
  const within = useRef(false);
  useEffect(() => {
    const track = (event: Event) => {
      within.current =
        event.target instanceof Node &&
        (root.current?.contains(event.target) ?? false);
    };
    document.addEventListener("focusin", track);
    document.addEventListener("pointerdown", track);
    return () => {
      document.removeEventListener("focusin", track);
      document.removeEventListener("pointerdown", track);
    };
  }, [root]);
  useEffect(() => {
    if (within.current && document.activeElement === document.body)
      root.current?.focus();
  });

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

  let body: ReactNode;
  if (state.kind === "loading") {
    body = (
      <Empty role="status">
        <Spinner />
        <EmptyDescription>{t("desktop.calendar.loading")}</EmptyDescription>
      </Empty>
    );
  } else if (state.kind === "withheld") {
    const said = gate ?? {
      title: t("desktop.account.signed_out"),
      lead: t("desktop.calendar.signed_out"),
    };
    body = said.pending ? (
      <Empty role="status">
        <Spinner />
        <EmptyDescription>{said.title}</EmptyDescription>
      </Empty>
    ) : (
      <Empty>
        <EmptyMedia>
          <Icon name="lock" />
        </EmptyMedia>
        <div className="grid gap-1">
          <EmptyTitle>{said.title}</EmptyTitle>
          {said.lead && <EmptyDescription>{said.lead}</EmptyDescription>}
        </div>
        {onSignIn && (
          <Button variant="outline" onClick={onSignIn}>
            {t("desktop.signin.submit")}
          </Button>
        )}
      </Empty>
    );
  } else if (state.kind === "failed") {
    body = (
      <Empty role="alert">
        <EmptyMedia>
          <Icon name="alert" />
        </EmptyMedia>
        <EmptyDescription>
          {t("desktop.calendar.failed", { code: state.code })}
        </EmptyDescription>
        <Button variant="outline" pending={refreshing} onClick={onRefresh}>
          {t("desktop.calendar.refresh")}
        </Button>
      </Empty>
    );
  } else {
    const { warnings, coverage, generated_at } = state.calendar;
    const asOf = generated_at
      ? new Intl.DateTimeFormat(locale, {
          dateStyle: "medium",
          timeStyle: "short",
        }).format(new Date(generated_at))
      : "—";
    // How the range stands, in the product's own four readings: counted,
    // never combined into a verdict.
    const standing = STATE_ORDER.map(
      (kind) =>
        [
          kind,
          state.calendar.entries.filter((entry) => entry.user_state === kind)
            .length,
        ] as const,
    ).filter(([, count]) => count > 0);
    body = (
      <>
        {/* The button keeps the first row's end; with nothing to count,
            the note takes the row beside it. */}
        <div className="grid shrink-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-b px-4 py-2">
          {standing.length > 0 && (
            <p className="calendar-standing col-start-1 row-start-1 flex flex-wrap gap-1.5">
              {standing.map(([kind, count]) => (
                <Badge key={kind} variant={STATE_TONE[kind]}>
                  {t(`desktop.calendar.state.${kind}`)}
                  <span className="font-semibold tabular-nums">{count}</span>
                </Badge>
              ))}
            </p>
          )}
          <IconButton
            label={t("desktop.calendar.refresh")}
            pending={refreshing}
            className="col-start-2 row-start-1"
            onClick={onRefresh}
          >
            {!refreshing && <Icon name="reset" />}
          </IconButton>
          <p className="col-start-1 text-sm text-muted-foreground">
            {t("desktop.calendar.as_of", { date: asOf })}
          </p>
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
              <h2
                id={`${heading}-${key}`}
                className={cn(
                  "sticky top-0 z-(--layer-separator) border-b bg-background px-4 pt-3 pb-1.5",
                  "text-xs font-semibold tracking-wider text-muted-foreground uppercase",
                )}
              >
                {month.title}
              </h2>
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
      </>
    );
  }

  return (
    <section
      ref={root}
      tabIndex={-1}
      aria-label={t("desktop.calendar.title")}
      aria-busy={refreshing || undefined}
      className="calendar-page @container flex min-h-0 flex-1 flex-col overflow-y-auto bg-background focus-visible:-outline-offset-2"
    >
      {body}
    </section>
  );
}
