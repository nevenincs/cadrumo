import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { Icon, type IconName } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { PaneControl } from "../PaneHeader";
import type { Action } from "../../shell/actions";
import {
  LEDGER_SECTIONS,
  type LedgerSection,
  type LedgerView,
} from "../../shell/layout";
import type { LedgerPort } from "../../shell/ledger";
import {
  periodOf,
  stepPeriod,
  type LedgerPeriod,
} from "../../shell/ledgerGrammar";
import { useLedgerReadiness } from "../../shell/ledgerReadiness";
import {
  readinessSnapshot,
  shownRows,
  useLedgerWindow,
  windowProgress,
  windowTruncation,
  type Readiness,
} from "../../shell/ledgerWindow";
import { useLedgerYears } from "../../shell/ledgerYears";
import { useStrings, type Translate } from "../../shell/strings";
import { localDay } from "../../shared/dates";
import {
  HeldButton,
  LedgerHeader,
  type LedgerHeaderAction,
  type SectionCount,
} from "./LedgerHeader";
import {
  SECTION_ICONS,
  TAB_SECTIONS,
  failureCode,
  periodText,
  sectionName,
  sectionTabId,
} from "./ledgerWords";
import { PeriodSelector } from "./PeriodSelector";

/** What the page keeps of itself while it is put away, for one profile:
 * the period it showed. Held in memory only. */
export type LedgerMemory = { period?: LedgerPeriod | null };

type Pill = {
  key: string;
  variant: "success" | "warning" | "neutral";
  icon: IconName;
  count?: number;
  label: string;
};

/** The readiness as it stood when it was checked: a glyph and a count for
 * each thing it counts, hidden at zero, with the sentence in its tooltip and
 * its name. One tick when nothing is left; a hollow mark while nothing
 * current has been checked. */
function readinessPills(
  t: Translate,
  locale: string,
  readiness: Readiness,
): Pill[] {
  const snapshot = readinessSnapshot(readiness);
  const unknown = (label: string): Pill[] => [
    { key: "unknown", variant: "neutral", icon: "unknown", label },
  ];
  if (!snapshot)
    return unknown(
      t(
        readiness.kind === "checking"
          ? "desktop.ledger.readiness.checking"
          : readiness.kind === "failed"
            ? "desktop.ledger.readiness.failed"
            : "desktop.ledger.readiness.not_checked",
      ),
    );
  // Staged changes leave the stored data as it was checked; saved ones do
  // not.
  if (snapshot.savedSince > 0)
    return unknown(
      t("desktop.ledger.readiness.out_of_date", {
        count: snapshot.savedSince,
      }),
    );
  const { status, preflight } = snapshot;
  const ready = preflight ? preflight.ready : status.ready;
  if (ready === null)
    return unknown(t("desktop.ledger.readiness.not_measured"));
  const issues = preflight ? preflight.issues : status.readiness_issues;
  // What is still to classify has a pill of its own.
  const fix = new Set(
    issues
      .filter((issue) => issue.reason !== "missing_business_classification")
      .map((issue) => issue.transaction_id),
  ).size;
  const toClassify = status.pending_review_count;
  const noRate = status.unconverted_currency_count;
  const pills: Pill[] = [];
  if (fix > 0 || (ready === false && toClassify === 0 && noRate === 0))
    pills.push({
      key: "issues",
      variant: "warning",
      icon: "alert",
      ...(fix > 0 ? { count: fix } : {}),
      label: t("desktop.ledger.readiness.not_ready", { count: fix }),
    });
  if (toClassify > 0)
    pills.push({
      key: "to_classify",
      variant: "neutral",
      icon: "pending",
      count: toClassify,
      label: t("desktop.ledger.count.to_classify", { count: toClassify }),
    });
  if (noRate > 0)
    pills.push({
      key: "no_rate",
      variant: "neutral",
      icon: "noRate",
      count: noRate,
      label: t("desktop.ledger.readiness.no_rate", { count: noRate }),
    });
  if (pills.length === 0)
    pills.push({
      key: "ready",
      variant: "success",
      icon: "check",
      label: t("desktop.ledger.readiness.ready", {
        time: new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(
          new Date(snapshot.checkedAt),
        ),
      }),
    });
  return pills;
}

function ReadinessPills({ pills }: { pills: Pill[] }) {
  const t = useStrings();
  return (
    <ul
      aria-label={t("desktop.ledger.readiness.title")}
      className="ledger-readiness flex flex-wrap items-center gap-1.5"
    >
      {pills.map((pill) => (
        <li key={pill.key} data-readiness={pill.key}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant={pill.variant} className="tabular-nums">
                <Icon name={pill.icon} size="xs" />
                {pill.count !== undefined && (
                  <span aria-hidden="true">{pill.count}</span>
                )}
                <span className="sr-only">{pill.label}</span>
              </Badge>
            </TooltipTrigger>
            <TooltipContent>{pill.label}</TooltipContent>
          </Tooltip>
        </li>
      ))}
    </ul>
  );
}

/**
 * The Ledger page: a period's movements, invoices and documents, and the
 * ledger's setup, under the pane's own header. What it reads lives in its
 * memory only and goes with the profile; the person's layout of it is kept
 * by the window as presentation, never with a value in it.
 */
export function LedgerPage({
  port,
  reader,
  withheld,
  locale,
  shown,
  page,
  view,
  onViewChange,
  memory,
  pane,
  contribute,
}: {
  port: LedgerPort;
  /** Whose ledger, or null while the account withholds it. */
  reader: string | null;
  /** What stands in the page while the account withholds the ledger. */
  withheld: ReactNode;
  locale: string;
  shown: boolean;
  page: RefObject<HTMLElement | null>;
  view: LedgerView;
  onViewChange(update: (current: LedgerView) => LedgerView): void;
  memory: RefObject<LedgerMemory>;
  /** The pane's title and controls, which the page's header carries. */
  pane: {
    title: string;
    controls: PaneControl[];
    onToggleMaximize(): void;
  };
  /** Hands the window's palette what the page offers, read when it opens. */
  contribute(actions: (() => Action[]) | null): void;
}) {
  const t = useStrings();
  const panel = useId();
  const today = localDay();
  const [period, setPeriodNow] = useState<LedgerPeriod | null>(() =>
    memory.current.period !== undefined
      ? memory.current.period
      : periodOf(today, "quarter"),
  );
  const setPeriod = (next: LedgerPeriod | null) => {
    memory.current.period = next;
    setPeriodNow(next);
  };
  const section = view.section;
  const setSection = (next: LedgerSection) => {
    setPeriodOpen(false);
    onViewChange((current) => ({ ...current, section: next }));
  };
  const readable = reader !== null;
  // Only the sections that show a period's records have a period to choose.
  const periodShown =
    section === "movements" || section === "invoices" || section === "health";
  const movementsShown = shown && readable && section === "movements";
  const { window: periodWindow, reread } = useLedgerWindow(
    port,
    reader,
    period,
    movementsShown,
  );
  const readiness = useLedgerReadiness(
    port,
    reader,
    period,
    periodWindow?.phase === "ready" ? periodWindow.generation : null,
  );
  const [periodOpen, setPeriodOpen] = useState(false);
  const { years } = useLedgerYears(port, reader, periodOpen);
  const numbers = useMemo(() => new Intl.NumberFormat(locale), [locale]);
  const fallbackYear = Number(today.slice(0, 4));
  const shownPeriod = periodText(t, locale, period);

  // Nothing the header offers runs yet where the page has no way to do it:
  // it says so instead of doing nothing.
  const unavailable = (): LedgerHeaderAction => ({
    reason: t("desktop.ledger.unavailable"),
  });
  const importAction = unavailable();
  const exportAction = unavailable();
  const addAction = unavailable();

  const snapshot = readinessSnapshot(readiness);
  const counts: Partial<Record<LedgerSection, SectionCount>> =
    snapshot && snapshot.status.pending_review_count > 0
      ? {
          movements: {
            count: snapshot.status.pending_review_count,
            label: t("desktop.ledger.count.to_classify", {
              count: snapshot.status.pending_review_count,
            }),
          },
        }
      : {};

  // The palette asks for these when it opens.
  const latest = useRef<() => Action[]>(() => []);
  useEffect(() => {
    const action = (
      id: string,
      label: string,
      icon: IconName,
      run: () => void,
      extra: Partial<Action> = {},
    ): Action => ({
      id: `ledger.${id}`,
      label,
      group: "ledger",
      icon,
      run,
      ...extra,
    });
    const runs = (headerAction: LedgerHeaderAction) => () =>
      headerAction.run !== undefined;
    latest.current = () =>
      shown && readable
        ? [
            action(
              "period",
              t("desktop.ledger.action.go_to_period"),
              "calendar",
              () => setPeriodOpen(true),
              { enabled: () => periodShown },
            ),
            action(
              "previous",
              t("desktop.ledger.period.previous"),
              "back",
              () => {
                const next = period && stepPeriod(period, -1);
                if (next) setPeriod(next);
              },
              { enabled: () => periodShown && period !== null },
            ),
            action(
              "next",
              t("desktop.ledger.period.next"),
              "forward",
              () => {
                const next = period && stepPeriod(period, 1);
                if (next) setPeriod(next);
              },
              { enabled: () => periodShown && period !== null },
            ),
            action(
              "import",
              t("desktop.ledger.action.import"),
              "upload",
              () => importAction.run?.(),
              { enabled: runs(importAction) },
            ),
            action(
              "export",
              t("desktop.ledger.action.export"),
              "download",
              () => exportAction.run?.(),
              { enabled: runs(exportAction) },
            ),
            action(
              "add",
              t("desktop.ledger.action.add_movement"),
              "plus",
              () => addAction.run?.(),
              { enabled: runs(addAction) },
            ),
            ...LEDGER_SECTIONS.map((value) =>
              action(
                `section.${value}`,
                t("desktop.ledger.action.section", {
                  section: sectionName(t, value),
                }),
                SECTION_ICONS[value],
                () => {
                  setSection(value);
                  page.current?.focus();
                },
                { enabled: () => value !== section },
              ),
            ),
          ]
        : [];
  });
  useEffect(() => {
    contribute(() => latest.current());
    return () => contribute(null);
  }, [contribute]);

  const isTab = (TAB_SECTIONS as readonly string[]).includes(section);
  let body: ReactNode;
  if (!readable || periodWindow === null) body = withheld;
  else if (section !== "movements")
    body = (
      <EmptyState
        className="ledger-placeholder"
        icon={SECTION_ICONS[section]}
        heading={sectionName(t, section)}
      />
    );
  else if (periodWindow.phase === "failed" && periodWindow.failure)
    body = (
      <EmptyState
        className="ledger-failed"
        icon="alert"
        description={
          <span key={periodWindow.generation} role="alert">
            {t("desktop.ledger.failed")}{" "}
            <code className="font-mono text-xs">
              {failureCode(periodWindow.failure)}
            </code>
          </span>
        }
      >
        <Button variant="outline" onClick={reread}>
          {t("desktop.ledger.retry")}
        </Button>
      </EmptyState>
    );
  else {
    const rows = shownRows(periodWindow);
    const progress = windowProgress(periodWindow);
    const reading =
      progress.total === null
        ? t("desktop.ledger.loading")
        : t("desktop.ledger.reading", {
            loaded: numbers.format(progress.loaded),
            total: numbers.format(progress.total),
          });
    if (rows === null)
      body = (
        <EmptyState
          className="ledger-loading"
          role="status"
          busy
          description={reading}
        />
      );
    else if (rows.total === 0)
      body = (
        <EmptyState
          className="ledger-empty"
          icon="ledger"
          description={
            period === null
              ? t("desktop.ledger.empty_all")
              : t("desktop.ledger.empty", { period: shownPeriod })
          }
        >
          <div className="flex flex-wrap justify-center gap-2">
            <HeldButton
              action={importAction}
              name={t("desktop.ledger.action.import")}
            >
              <Icon name="upload" />
              {t("desktop.ledger.action.import")}
            </HeldButton>
            <HeldButton
              action={addAction}
              name={t("desktop.ledger.action.add_movement")}
            >
              <Icon name="plus" />
              {t("desktop.ledger.action.add")}
            </HeldButton>
          </div>
        </EmptyState>
      );
    else {
      const truncated = windowTruncation(periodWindow);
      body = (
        <div className="ledger-movements grid content-start gap-3 p-3">
          <ReadinessPills pills={readinessPills(t, locale, readiness)} />
          <p className="text-sm text-muted-foreground">
            {truncated
              ? t("desktop.ledger.loaded_of", {
                  loaded: numbers.format(truncated.loaded),
                  total: numbers.format(truncated.total),
                })
              : t("desktop.ledger.movements_count", {
                  count: numbers.format(rows.total),
                })}
          </p>
          {periodWindow.phase === "reading" && (
            <p role="status" className="text-xs text-muted-foreground">
              {reading}
            </p>
          )}
        </div>
      );
    }
  }

  return (
    <>
      <LedgerHeader
        title={pane.title}
        controls={pane.controls}
        onToggleMaximize={pane.onToggleMaximize}
        section={readable ? section : undefined}
        onSection={setSection}
        counts={counts}
        panel={panel}
        period={
          periodShown && (
            <PeriodSelector
              value={period}
              onChange={setPeriod}
              label={t("desktop.ledger.period.label")}
              years={years}
              locale={locale}
              fallbackYear={fallbackYear}
              open={periodOpen}
              onOpenChange={setPeriodOpen}
            />
          )
        }
        importAction={importAction}
        exportAction={exportAction}
        addAction={section === "movements" ? addAction : undefined}
      />
      <section
        ref={page}
        tabIndex={-1}
        aria-label={t("desktop.ledger.title")}
        aria-busy={periodWindow?.phase === "reading" || undefined}
        className="ledger-page flex min-h-0 flex-1 flex-col overflow-y-auto bg-background focus-visible:-outline-offset-2"
      >
        <div
          id={panel}
          // Withheld, no section is shown: the page says why instead.
          role={readable ? (isTab ? "tabpanel" : "region") : undefined}
          aria-labelledby={
            readable && isTab ? sectionTabId(panel, section) : undefined
          }
          aria-label={readable && !isTab ? sectionName(t, section) : undefined}
          className="flex min-h-0 flex-1 flex-col"
        >
          {body}
        </div>
      </section>
    </>
  );
}
