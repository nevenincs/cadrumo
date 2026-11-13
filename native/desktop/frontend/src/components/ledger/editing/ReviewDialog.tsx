import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { facts, factsGap, labelled } from "@/shell/compose";
import type {
  CatalogueInvoiceSnapshot,
  LedgerInvoiceMatchJudgement,
} from "../../../shell/ledgerInvoiceContract";
import type {
  LedgerPort,
  LedgerRow,
  OutputLanguage,
} from "../../../shell/ledger";
import { useInvoiceMatches } from "../../../shell/ledgerInvoiceMatch";
import {
  plannedStepsReported,
  type StepOutcome,
} from "../../../shell/ledgerApply";
import {
  stagedCheckRequest,
  useStagedCheck,
  type StagedCheck,
} from "../../../shell/ledgerStagedCheck";
import { planApply, type LedgerPlan } from "../../../shell/ledgerPlan";
import {
  actionRows,
  storedFieldValue,
  type DraftField,
  type StageEvent,
  type StagedAction,
  type StagedContent,
} from "../../../shell/ledgerStage";
import { useStrings, type Translate } from "../../../shell/strings";
import {
  categoryLabel,
  classificationText,
  ivaCategoryLabel,
} from "../movements/movementWords";
import {
  changeGroups,
  heldUnits,
  linksReady,
  outcomeTally,
  type AskedConflict,
  type LinkTicks,
  type LinkMismatch,
  type StageTally,
} from "./editingModel";
import { fieldName, valueText } from "./editingWords";
import type { useLedgerApply } from "./useLedgerApply";
import { useWritePause } from "../WritePause";
import { WindowedList } from "./WindowedList";
import { formatPercent } from "../../../shared/numbers";
import { NeedsYouFirst } from "./ReviewBlockers";
import {
  changedElsewhere,
  OUTCOME_ICONS,
  outcomeItems,
  outcomeTone,
  Outcomes,
  SummaryTable,
} from "./ReviewOutcomes";
import { lockProgress, titleOf } from "./reviewLabels";

type Apply = ReturnType<typeof useLedgerApply>;

const minutesOf = (seconds: number) => Math.max(1, Math.round(seconds / 60));

/** The outcomes worst first: the result is titled by the first it holds. */
const WORST: readonly StepOutcome["kind"][] = [
  "unknown",
  "saved_unread",
  "refused",
  "not_sent",
];
/** Outcomes that saved: the result lists only the rest. */
const SAVED = new Set<StepOutcome["kind"]>(["applied", "settled"]);

/** The plan in plain words: "92 together · 40 one by one (about 2 min) ·
 * 2 new · 3 held". */
function planLine(t: Translate, plan: LedgerPlan, held: number): string {
  const summary = plan.summary;
  const actions = Object.values(summary.actions).reduce(
    (total, count) => total + (count ?? 0),
    0,
  );
  const single = summary.singleClassifications + summary.corrections + actions;
  return facts(t, [
    summary.together
      ? t("desktop.ledger.apply.together", { count: summary.together })
      : "",
    single
      ? summary.seconds > 60
        ? t("desktop.ledger.apply.one_by_one", {
            count: single,
            minutes: minutesOf(summary.seconds),
          })
        : t("desktop.ledger.apply.one_by_one_quick", { count: single })
      : "",
    summary.newMovements
      ? t("desktop.ledger.apply.new", { count: summary.newMovements })
      : "",
    held ? t("desktop.ledger.apply.held", { count: held }) : "",
  ]);
}

// ---- Actions in words -------------------------------------------------------

/** An action as the review and the tray name it, in plain words. */
export function actionText(
  t: Translate,
  locale: string,
  action: StagedAction,
): string {
  switch (action.kind) {
    case "iva_derive":
      return t("desktop.ledger.apply.action.iva_derive", {
        category: ivaCategoryLabel(t, action.ivaCategory),
      });
    case "allocate":
      return t("desktop.ledger.apply.action.allocate", {
        share: formatPercent(locale || "en", action.businessPct, {
          unit: "fraction",
        }),
      });
    case "attach_file":
      return t("desktop.ledger.apply.action.attach_file", {
        name: action.name,
      });
    case "rule_apply":
      return t("desktop.ledger.apply.action.rule_apply", {
        count: action.transactionIds.length,
      });
    default:
      return t(`desktop.ledger.apply.action.${action.kind}`);
  }
}

/** An action's lines in the review: a split adds each part, with the
 * classification it is given once the split has made it. */
function actionLines(
  t: Translate,
  locale: string,
  action: StagedAction,
): string[] {
  const lines = [actionText(t, locale, action)];
  if (action.kind === "split")
    for (const child of action.children)
      lines.push(
        facts(t, [
          valueText(t, locale, "amount", child.amount),
          child.description,
          child.classify
            ? classificationText(t, locale, {
                business_classification: child.classify.classification,
                business_pct: child.classify.business_pct ?? null,
              })
            : "",
          child.classify?.category_id
            ? categoryLabel(t, child.classify.category_id)
            : "",
        ]),
      );
  return lines;
}

/** Rule applies, which act on movements anywhere in the ledger: each says
 * how many its dry run named, and lists them when opened. */
function RuleApplies({
  actions,
  rows,
  onDrop,
}: {
  actions: Extract<StagedAction, { kind: "rule_apply" }>[];
  rows: ReadonlyMap<string, LedgerRow>;
  onDrop: (id: string) => void;
}) {
  const t = useStrings();
  if (!actions.length) return null;
  return (
    <section className="ledger-rule-applies grid gap-2">
      {actions.map((action) => (
        <details
          key={action.id}
          data-action="rule_apply"
          className="rounded-md border border-border px-3 py-2"
        >
          <summary className="flex cursor-pointer items-center gap-2">
            <Icon name="filter" size="xs" className="text-muted-foreground" />
            <span className="flex-1 font-medium">
              {actionText(t, "", action)}
            </span>
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={t("desktop.ledger.apply.drop", {
                movement: actionText(t, "", action),
              })}
              onClick={(event) => {
                event.preventDefault();
                onDrop(action.id);
              }}
            >
              <Icon name="close" size="xs" />
            </Button>
          </summary>
          <ul className="mt-2 grid gap-0.5 text-sm text-muted-foreground">
            {action.transactionIds.map((id) => (
              <li key={id}>
                {rows.get(id)?.transaction.description ?? id.slice(0, 12)}
              </li>
            ))}
          </ul>
        </details>
      ))}
    </section>
  );
}

/** The staged movements that would end Business or Mixed with a spending
 * category on pure income, which no expense reads: the product's own
 * missing-category rule, from the other side. */
function incomeWithCategory(check: StagedCheck | null): string[] {
  return [...(check?.rows.values() ?? [])]
    .filter((answer) => answer.category_on_income)
    .map((answer) => answer.transaction_id);
}

// ---- Permanent links -------------------------------------------------------

function mismatchText(t: Translate, locale: string, mismatch: LinkMismatch) {
  switch (mismatch.kind) {
    case "amount":
      return t("desktop.ledger.apply.link.amount_differs", {
        amount: valueText(
          t,
          locale,
          "amount",
          mismatch.difference?.decimal ?? "",
        ),
      });
    case "counterparty":
      return t("desktop.ledger.apply.link.counterparty_differs");
    case "currency":
      return t("desktop.ledger.apply.link.currency_differs", {
        movement: mismatch.movement ?? "",
        invoice: mismatch.invoice ?? "",
      });
    case "linked_elsewhere":
      return t("desktop.ledger.apply.link.linked_elsewhere", {
        count: mismatch.count ?? 0,
      });
  }
}

/** The mismatches the ledger found against a link, or null where it has not
 * judged it or the movement or invoice is gone. */
const judgementOf = (judgement: LedgerInvoiceMatchJudgement | undefined) =>
  judgement?.found ? judgement.mismatches : null;

function PermanentLinks({
  links,
  locale,
  ticks,
  onTicks,
  onRereadInvoices,
  onRetryJudgement,
}: {
  links: {
    id: string;
    row: LedgerRow | undefined;
    invoice: CatalogueInvoiceSnapshot | undefined;
    invoiceId: string;
    /** What the ledger found against the link; null until it has said. */
    mismatches: readonly LinkMismatch[] | null;
  }[];
  locale: string;
  ticks: LinkTicks;
  onTicks: (ticks: LinkTicks) => void;
  /** Reads the catalogue again where an invoice could not be read. */
  onRereadInvoices: () => void;
  /** Asks the ledger again to compare the links. */
  onRetryJudgement: () => void;
}) {
  const t = useStrings();
  if (!links.length) return null;
  return (
    <section
      className="ledger-permanent grid gap-3 rounded-lg bg-muted p-3"
      aria-labelledby="ledger-permanent-heading"
    >
      <h3
        id="ledger-permanent-heading"
        className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase"
      >
        <Icon name="lock" size="xs" />
        {t("desktop.ledger.apply.permanent")}
      </h3>
      <p className="text-sm">{t("desktop.ledger.apply.permanent_note")}</p>
      {links.map((link) => {
        const tick = ticks[link.id] ?? { sure: false, differ: false };
        const transaction = link.row?.transaction;
        return (
          <div key={link.id} data-link={link.id} className="grid gap-1.5">
            <p className="text-sm">
              {facts(t, [
                transaction &&
                  valueText(t, locale, "amount", transaction.amount),
                transaction?.counterparty || transaction?.description,
                transaction &&
                  valueText(t, locale, "booked_date", transaction.date),
              ])}
              {" ↔ "}
              {link.invoice
                ? facts(t, [
                    link.invoice.invoice_number,
                    valueText(
                      t,
                      locale,
                      "amount",
                      link.invoice.grand_total.decimal,
                    ),
                    link.invoice.counterparty_name,
                    valueText(t, locale, "booked_date", link.invoice.issued_at),
                  ])
                : link.invoiceId}
            </p>
            {!link.invoice && (
              <p
                role="alert"
                className="ledger-link-unread flex flex-wrap items-center gap-1.5 text-sm"
              >
                <Icon name="unknown" size="xs" className="text-warning" />
                {t("desktop.ledger.apply.link.unread")}
                <Button
                  variant="link"
                  size="xs"
                  className="ledger-link-reread"
                  onClick={onRereadInvoices}
                >
                  {t("desktop.ledger.paused.reread")}
                </Button>
              </p>
            )}
            {link.invoice && link.mismatches === null && (
              <p
                role="status"
                className="ledger-link-unjudged flex flex-wrap items-center gap-1.5 text-sm"
              >
                <Icon name="unknown" size="xs" className="text-warning" />
                {t("desktop.ledger.apply.link.unjudged")}
                <Button
                  variant="link"
                  size="xs"
                  className="ledger-link-rejudge"
                  onClick={onRetryJudgement}
                >
                  {t("desktop.ledger.retry")}
                </Button>
              </p>
            )}
            {link.mismatches && link.mismatches.length > 0 && (
              <ul className="flex flex-wrap gap-1.5">
                {link.mismatches.map((mismatch) => (
                  <li key={mismatch.kind}>
                    <Badge variant="warning">
                      {mismatchText(t, locale, mismatch)}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                className="ledger-link-sure"
                checked={tick.sure}
                disabled={!link.invoice || link.mismatches === null}
                onChange={(event) =>
                  onTicks({
                    ...ticks,
                    [link.id]: { ...tick, sure: event.target.checked },
                  })
                }
              />
              {t("desktop.ledger.apply.link.sure")}
            </label>
            {link.mismatches && link.mismatches.length > 0 && (
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  className="ledger-link-differ"
                  checked={tick.differ}
                  onChange={(event) =>
                    onTicks({
                      ...ticks,
                      [link.id]: { ...tick, differ: event.target.checked },
                    })
                  }
                />
                {t("desktop.ledger.apply.link.differ")}
              </label>
            )}
          </div>
        );
      })}
    </section>
  );
}

// ---- Model approvals -------------------------------------------------------

function Approvals({
  approvals,
  rows,
  locale,
}: {
  approvals: Extract<StagedAction, { kind: "suggestion" }>[];
  rows: ReadonlyMap<string, LedgerRow>;
  locale: string;
}) {
  const t = useStrings();
  if (!approvals.length) return null;
  return (
    <section
      className="ledger-approvals grid gap-2"
      aria-labelledby="ledger-approvals-heading"
    >
      <h3
        id="ledger-approvals-heading"
        className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
      >
        {t("desktop.ledger.apply.approvals")}
      </h3>
      {approvals.map((approval) => {
        const row = rows.get(approval.transactionId);
        return (
          <div
            key={approval.id}
            className="grid gap-1 border-b border-border pb-2"
          >
            <p className="flex items-center gap-1.5 font-medium">
              <Icon name="agent" size="xs" className="text-muted-foreground" />
              {titleOf(t, rows, approval.transactionId)}
              <span className="text-sm font-normal text-muted-foreground">
                {approval.decision === "apply"
                  ? t("desktop.ledger.apply.approve")
                  : t("desktop.ledger.apply.reject", {
                      reason: approval.reason,
                    })}
              </span>
            </p>
            {approval.decision === "apply" && (
              <ul className="grid gap-0.5 text-sm">
                {(approval.writes ?? []).map((write) => (
                  <li
                    key={write.field}
                    data-derived={write.derived || undefined}
                  >
                    {labelled(
                      t,
                      fieldName(t, write.field),
                      `${valueText(
                        t,
                        locale,
                        write.field,
                        row
                          ? (storedFieldValue(row, write.field) ?? null)
                          : null,
                      )} → ${valueText(t, locale, write.field, write.value)}`,
                    )}
                    {write.derived && (
                      <span className="text-muted-foreground">
                        {`${factsGap(t)}${t("desktop.ledger.edit.lock.derived")}`}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </section>
  );
}

// ---- The per-movement list -------------------------------------------------

type Entry = {
  key: string;
  draft: boolean;
  title: string;
  lines: string[];
  blocked: boolean;
};

function entriesOf(
  t: Translate,
  locale: string,
  content: StagedContent,
  plan: LedgerPlan,
  rows: ReadonlyMap<string, LedgerRow>,
): Entry[] {
  const entries: Entry[] = [];
  for (const entry of plan.entries) {
    const row = rows.get(entry.transactionId);
    const changes = content.rows[entry.transactionId] ?? {};
    const lines = entry.fields.map((field) => {
      const change = changes[field]!;
      return labelled(
        t,
        fieldName(t, field),
        `${valueText(
          t,
          locale,
          field,
          row ? (storedFieldValue(row, field) ?? null) : null,
        )} → ${
          change.kind === "set"
            ? valueText(t, locale, field, change.value)
            : t("desktop.ledger.edit.cleared")
        }`,
      );
    });
    for (const action of content.actions)
      if (actionRows(action).includes(entry.transactionId))
        lines.push(...actionLines(t, locale, action));
    entries.push({
      key: entry.transactionId,
      draft: false,
      title: titleOf(t, rows, entry.transactionId),
      lines,
      blocked: entry.blockers.length > 0,
    });
  }
  for (const draft of content.drafts) {
    const checked = plan.drafts.find((entry) => entry.key === draft.key);
    entries.push({
      key: draft.key,
      draft: true,
      title: draft.fields.description ?? t("desktop.ledger.draft.untitled"),
      lines: [
        facts(
          t,
          (Object.entries(draft.fields) as [DraftField, string][])
            .filter(([field]) => field !== "description")
            .map(([field, value]) => valueText(t, locale, field, value)),
        ),
      ],
      blocked: (checked?.blockers.length ?? 0) > 0,
    });
  }
  return entries;
}

function MovementList({
  entries,
  only,
  onOnly,
  onDrop,
  open,
  onOpen,
}: {
  entries: Entry[];
  only: string[] | null;
  onOnly: (ids: string[] | null) => void;
  onDrop: (entry: Entry) => void;
  /** The list is folded behind its count until opened. */
  open: boolean;
  onOpen: (open: boolean) => void;
}) {
  const t = useStrings();
  const [filter, setFilter] = useState("");
  const words = filter.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const shown = entries.filter(
    (entry) =>
      (only === null || only.includes(entry.key)) &&
      words.every((word) =>
        [entry.title, ...entry.lines]
          .join(" ")
          .toLocaleLowerCase()
          .includes(word),
      ),
  );
  return (
    <details
      className="ledger-review-rows grid gap-2"
      open={open}
      onToggle={(event) => onOpen(event.currentTarget.open)}
    >
      <summary className="ledger-review-rows-toggle flex cursor-pointer items-center gap-1.5 text-sm text-muted-foreground">
        {facts(t, [
          t("desktop.ledger.apply.summary_movements"),
          entries.length,
        ])}
        <Icon name={open ? "chevronDown" : "forward"} size="xs" />
      </summary>
      {open && (
        <div className="mt-2 grid gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Input
              controlSize="sm"
              className="w-field"
              type="search"
              aria-label={t("desktop.ledger.apply.filter")}
              placeholder={t("desktop.ledger.apply.filter")}
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
            <span className="text-sm text-muted-foreground">
              {t("desktop.ledger.apply.shown", {
                shown: shown.length,
                total: entries.length,
              })}
            </span>
            {only !== null && (
              <Button variant="link" size="xs" onClick={() => onOnly(null)}>
                {t("desktop.ledger.apply.show_all")}
              </Button>
            )}
          </div>
          <WindowedList
            label={t("desktop.ledger.apply.rows")}
            className="max-h-72 rounded-md border border-border"
            items={shown}
            keyOf={(entry) => entry.key}
            render={(entry) => (
              <div
                data-entry={entry.key}
                className="flex h-14 items-center gap-2 border-b border-border px-3"
              >
                {entry.blocked ? (
                  <Icon
                    name="alert"
                    size="xs"
                    className="shrink-0 text-warning"
                  />
                ) : (
                  entry.draft && (
                    <Icon name="plus" size="xs" className="shrink-0" />
                  )
                )}
                <span className="grid min-w-0 flex-1">
                  <span className="truncate font-medium">{entry.title}</span>
                  <span className="truncate text-sm text-muted-foreground">
                    {facts(t, entry.lines)}
                  </span>
                </span>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  className="ledger-review-drop"
                  aria-label={t("desktop.ledger.apply.drop", {
                    movement: entry.title,
                  })}
                  onClick={() => onDrop(entry)}
                >
                  <Icon name="close" size="xs" />
                </Button>
              </div>
            )}
          />
        </div>
      )}
    </details>
  );
}

// ---- The dialog ------------------------------------------------------------

/**
 * The review and apply of everything staged on the page. It leads with one
 * line of counts in the page's unit, then what needs the person first,
 * permanent links, model approvals, a summary by kind of change and the
 * list of movements, the plan in plain words with its operations under
 * Technical details; then the apply with each part's progress and every
 * row's outcome.
 */
const NO_ROWS: ReadonlyMap<string, LedgerRow> = new Map();

export function ReviewDialog({
  apply,
  port,
  content,
  tally,
  locale,
  onStage,
  onShowRows,
  onGoToDraft,
  onCloseAutoFocus,
}: {
  apply: Apply;
  port: LedgerPort;
  content: StagedContent;
  tally: StageTally;
  locale: string;
  onStage: (event: StageEvent) => void;
  onShowRows: (ids: string[], fields?: readonly string[]) => void;
  onGoToDraft: (key: string) => void;
  /** Where the focus goes once the review has gone. */
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const t = useStrings();
  const pause = useWritePause();
  const state = apply.state;
  const heading = useRef<HTMLHeadingElement>(null);
  // Each step of the review, and its result, starts at its heading.
  useEffect(() => {
    heading.current?.focus();
  }, [state.phase]);
  const [ticks, setTicks] = useState<LinkTicks>({});
  const [only, setOnly] = useState<string[] | null>(null);
  const [listOpen, setListOpen] = useState<boolean | null>(null);
  const [looked, setLooked] = useState(false);
  const [choices, setChoices] = useState<Record<string, "mine" | "theirs">>({});
  const rows =
    state.phase === "closed" ||
    state.phase === "reading" ||
    state.phase === "failed"
      ? null
      : state.rows;
  // A plan is made from the backend's answer about the content as it stands:
  // with none yet there is no plan, and with none at all nothing to apply.
  const checked = useStagedCheck(
    port,
    useMemo(
      () => stagedCheckRequest(content, rows ?? NO_ROWS),
      [content, rows],
    ),
  );
  const plan = useMemo(
    () =>
      state.phase === "ready" && checked.current
        ? planApply(content, {
            rows: state.rows,
            check: checked.current,
            sealed: state.sealed,
            unread: state.unread,
            outputLanguage: locale as OutputLanguage,
          })
        : null,
    [state, content, locale, checked],
  );
  const linkSteps = useMemo(
    () =>
      plan
        ? plan.steps.flatMap((step) =>
            step.kind === "action" && step.action.kind === "link"
              ? [step.action]
              : [],
          )
        : [],
    [plan],
  );
  // The ledger states where each link's two sides differ; the window judges
  // nothing, and a link not yet judged is held.
  const judging = useInvoiceMatches(
    port,
    useMemo(
      () =>
        linkSteps.length > 0
          ? {
              staged: [],
              judge: linkSteps.map((action) => ({
                transaction_id: action.transactionId,
                invoice_id: action.invoiceId,
              })),
            }
          : null,
      [linkSteps],
    ),
    rows,
  );
  if (state.phase === "closed") return null;
  const busy = state.phase === "applying";
  const close = () => {
    if (!busy) apply.close();
  };

  let title: ReactNode = t("desktop.ledger.apply.title", {
    count: tally.units,
  });
  let description: ReactNode = null;
  let body: ReactNode = null;
  let footer: ReactNode = null;

  const checking =
    state.phase === "ready" && !checked.current && !checked.failed;
  if (state.phase === "reading" || checking) {
    description = t("desktop.ledger.apply.reading");
    body = (
      <div
        role="status"
        className="ledger-apply-reading flex items-center gap-2 text-muted-foreground"
      >
        <Spinner />
        {state.phase === "reading" && state.locks
          ? lockProgress(t, locale, state.locks)
          : t("desktop.ledger.apply.reading")}
      </div>
    );
  } else if (state.phase === "failed" || (state.phase === "ready" && !plan)) {
    body = (
      <Alert tone="danger" role="alert" icon={<Icon name="alert" />}>
        <AlertTitle>{t("desktop.ledger.apply.read_failed")}</AlertTitle>
      </Alert>
    );
    footer = (
      <>
        <Button variant="ghost" onClick={close}>
          {t("desktop.ledger.apply.keep_editing")}
        </Button>
        <Button
          onClick={() =>
            state.phase === "failed" ? void apply.open() : checked.retry()
          }
        >
          {t("desktop.ledger.retry")}
        </Button>
      </>
    );
  } else if (state.phase === "ready" && state.conflicts.length > 0) {
    title = t("desktop.ledger.apply.conflicts_title");
    description = t("desktop.ledger.apply.conflicts_description");
    body = (
      <ConflictList
        conflicts={state.conflicts}
        choices={choices}
        onChoose={(id, keep) => setChoices({ ...choices, [id]: keep })}
        locale={locale}
        content={content}
      />
    );
    footer = (
      <>
        <label className="me-auto flex items-center gap-2 text-sm">
          <Checkbox
            className="ledger-conflicts-looked"
            checked={looked}
            onChange={(event) => setLooked(event.target.checked)}
          />
          {t("desktop.ledger.apply.conflicts_looked")}
        </label>
        <Button variant="ghost" onClick={close}>
          {t("desktop.ledger.apply.back")}
        </Button>
        <Button
          className="ledger-conflicts-continue"
          aria-disabled={looked ? undefined : true}
          onClick={() => {
            if (!looked) return;
            for (const conflict of state.conflicts) {
              const keep = choices[conflict.transactionId] ?? "mine";
              if (conflict.kind === "changed")
                apply.resolve(conflict.transactionId, keep, conflict.fields);
              else if (keep === "theirs")
                onStage({
                  type: "revert_movement",
                  id: conflict.transactionId,
                });
            }
            apply.resolveAll();
          }}
        >
          {t("desktop.ledger.apply.continue")}
        </Button>
      </>
    );
  } else if (state.phase === "ready" && plan && rows) {
    const held = heldUnits(content, plan);
    const savable = tally.units - held;
    const judgements = new Map(
      (judging.kind === "answer" ? judging.result.judgements : []).map(
        (judgement) => [
          `${judgement.transaction_id}:${judgement.invoice_id}`,
          judgement,
        ],
      ),
    );
    const links = linkSteps.map((action) => {
      const row = rows.get(action.transactionId);
      const invoice = state.invoices?.find(
        (found) => found.invoice_id === action.invoiceId,
      );
      return {
        id: action.id,
        row,
        invoice,
        invoiceId: action.invoiceId,
        mismatches: judgementOf(
          judgements.get(`${action.transactionId}:${action.invoiceId}`),
        ),
      };
    });
    // A link whose invoice could not be read is held until it is read.
    const unread = links.some((link) => !link.invoice);
    const unjudged = links.some((link) => link.mismatches === null);
    const ready = !unread && linksReady(links, ticks);
    const approvals = content.actions.filter(
      (action): action is Extract<StagedAction, { kind: "suggestion" }> =>
        action.kind === "suggestion",
    );
    const groups = changeGroups(content, rows);
    const entries = entriesOf(t, locale, content, plan, rows);
    description = planLine(t, plan, held);
    const onIncome = incomeWithCategory(checked.current);
    body = (
      <div className="grid gap-5">
        {onIncome.length > 0 && (
          <ul className="ledger-review-mismatches flex flex-wrap items-center gap-1.5">
            <li data-mismatch="income_category">
              <Badge variant="warning">
                {t("desktop.ledger.apply.mismatch.income_category", {
                  count: onIncome.length,
                })}
              </Badge>
            </li>
            <li>
              <Button
                variant="link"
                size="xs"
                onClick={() => {
                  setOnly(onIncome);
                  setListOpen(true);
                }}
              >
                {t("desktop.ledger.apply.show_rows")}
              </Button>
            </li>
          </ul>
        )}
        <NeedsYouFirst
          plan={plan}
          content={content}
          rows={rows}
          onStage={onStage}
          onShowRows={onShowRows}
          onGoToDraft={onGoToDraft}
          onRereadSealed={() => void apply.rereadSealed()}
          port={port}
          locks={state.phase === "ready" ? state.locks : null}
          locale={locale}
        />
        <PermanentLinks
          links={links}
          locale={locale}
          ticks={ticks}
          onTicks={setTicks}
          onRereadInvoices={() => void apply.rereadInvoices()}
          onRetryJudgement={judging.retry}
        />
        <Approvals approvals={approvals} rows={rows} locale={locale} />
        {groups.length > 0 && (
          <section
            className="grid gap-2"
            aria-labelledby="ledger-summary-heading"
          >
            <h3
              id="ledger-summary-heading"
              className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
            >
              {t("desktop.ledger.apply.summary")}
            </h3>
            <SummaryTable
              groups={groups.slice(0, 12)}
              locale={locale}
              onShowRows={(ids) => {
                setOnly(ids);
                setListOpen(true);
              }}
            />
          </section>
        )}
        <RuleApplies
          actions={content.actions.filter(
            (action): action is Extract<StagedAction, { kind: "rule_apply" }> =>
              action.kind === "rule_apply",
          )}
          rows={rows}
          onDrop={(id) => onStage({ type: "drop_action", id })}
        />
        <MovementList
          entries={entries}
          only={only}
          onOnly={setOnly}
          // With no summary by kind the list is the summary: it starts open.
          open={listOpen ?? groups.length === 0}
          onOpen={setListOpen}
          onDrop={(entry) =>
            onStage(
              entry.draft
                ? { type: "remove_draft", key: entry.key }
                : { type: "revert_movement", id: entry.key },
            )
          }
        />
      </div>
    );
    footer = (
      <>
        <span className="me-auto text-sm text-muted-foreground">
          {apply.paused
            ? apply.paused
            : unread
              ? t("desktop.ledger.apply.link.unread")
              : unjudged
                ? t("desktop.ledger.apply.link.unjudged")
                : !ready
                  ? t("desktop.ledger.apply.tick_links")
                  : held
                    ? t("desktop.ledger.apply.held_note", { count: held })
                    : ""}
        </span>
        <Button variant="ghost" onClick={close}>
          {t("desktop.ledger.apply.keep_editing")}
        </Button>
        <Button
          className="ledger-apply-save"
          aria-disabled={
            savable <= 0 ||
            !ready ||
            apply.paused !== null ||
            !plan.steps.length
              ? true
              : undefined
          }
          onClick={() => {
            if (savable <= 0 || !ready || apply.paused || !plan.steps.length)
              return;
            void apply.apply(plan);
          }}
        >
          {held
            ? t("desktop.ledger.apply.save_held", { count: savable, held })
            : t("desktop.ledger.apply.save", { count: savable })}
        </Button>
      </>
    );
  } else if (state.phase === "applying") {
    title = t("desktop.ledger.apply.saving");
    description = t("desktop.ledger.apply.saving_description");
    body = (
      <div className="grid gap-3">
        <Progress
          aria-label={t("desktop.ledger.apply.progress")}
          value={plannedStepsReported(state.reports)}
          max={state.plan.steps.length}
        />
        <p role="status" className="text-sm text-muted-foreground">
          {t("desktop.ledger.apply.progress_count", {
            done: plannedStepsReported(state.reports),
            total: state.plan.steps.length,
          })}
        </p>
        <Outcomes
          items={outcomeItems(
            t,
            locale,
            state.reports,
            state.rows,
            null,
            content,
            actionText,
          )}
        />
      </div>
    );
  } else if (state.phase === "done") {
    const counts = outcomeTally(state.report.steps);
    const saved = (counts.applied ?? 0) + (counts.settled ?? 0);
    // Titled by its worst outcome; "Saved" only where every part settled.
    const worst = WORST.find((kind) => (counts[kind] ?? 0) > 0) ?? null;
    const headline: StepOutcome["kind"] =
      worst ?? (saved > 0 ? "applied" : "unchanged");
    title = (
      <span className="ledger-apply-headline flex items-center gap-2">
        <Icon
          name={OUTCOME_ICONS[headline]}
          className={outcomeTone(headline)}
        />
        {facts(t, [
          t(`desktop.ledger.apply.tally.${headline}`),
          worst ? counts[worst]! : saved || (counts.unchanged ?? 0),
        ])}
      </span>
    );
    const items = outcomeItems(
      t,
      locale,
      state.report.steps,
      state.rows,
      state.fresh,
      content,
      actionText,
    );
    const unsaved = items.filter((item) => !SAVED.has(item.outcome.kind));
    const kinds = Object.keys(counts).length;
    body = (
      <div className="grid gap-3">
        {kinds > 1 && (
          <ul className="ledger-outcome-tally flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {(Object.entries(counts) as [StepOutcome["kind"], number][]).map(
              ([kind, count]) => (
                <li
                  key={kind}
                  data-tally={kind}
                  className="flex items-center gap-1.5"
                >
                  <Icon name={OUTCOME_ICONS[kind]} size="xs" />
                  {t(`desktop.ledger.apply.tally.${kind}`)}
                  <span className="font-semibold tabular-nums">{count}</span>
                </li>
              ),
            )}
          </ul>
        )}
        {state.report.paused && (
          <Alert
            tone="warning"
            role="alert"
            icon={<Icon name="unknown" />}
            className="ledger-apply-unknown"
          >
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="min-w-0 flex-1">
                {t(
                  state.report.steps.some(
                    (step) => step.outcome.kind === "unknown",
                  )
                    ? "desktop.ledger.apply.unknown_note"
                    : "desktop.ledger.apply.outcome.saved_unread",
                )}
              </span>
              {apply.paused && (
                <Button
                  size="xs"
                  variant="outline"
                  className="ledger-apply-reread shrink-0"
                  onClick={() => {
                    if (!pause.rereading) pause.reread();
                  }}
                  aria-disabled={pause.rereading || undefined}
                >
                  <Icon name="sync" />
                  {t("desktop.ledger.paused.reread")}
                </Button>
              )}
            </div>
          </Alert>
        )}
        {state.report.stopped && (
          <Alert tone="danger" role="alert" icon={<Icon name="alert" />}>
            <AlertTitle>{t("desktop.ledger.apply.stopped")}</AlertTitle>
          </Alert>
        )}
        <Outcomes items={unsaved} />
      </div>
    );
    footer = (
      <>
        {!apply.paused &&
          unsaved.some((item) => changedElsewhere(item.outcome)) && (
            <Button
              variant="outline"
              className="ledger-apply-refused-reread"
              onClick={() => void apply.open()}
            >
              <Icon name="sync" />
              {t("desktop.ledger.paused.reread")}
            </Button>
          )}
        <Button className="ledger-apply-done" onClick={close}>
          {t("desktop.ledger.apply.close")}
        </Button>
      </>
    );
  }

  return (
    <Dialog open onOpenChange={(open) => !open && close()}>
      <DialogContent
        placement="top"
        className="ledger-review w-dialog-xl overflow-y-auto"
        closeLabel={busy ? undefined : t("desktop.ledger.apply.close")}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          heading.current?.focus();
        }}
        onPointerDownOutside={(event) => {
          if (busy) event.preventDefault();
        }}
        onCloseAutoFocus={onCloseAutoFocus}
        aria-busy={busy || undefined}
        {...(description ? {} : { "aria-describedby": undefined })}
      >
        <DialogHeader>
          <DialogTitle ref={heading} tabIndex={-1}>
            {title}
          </DialogTitle>
          {description && (
            <DialogDescription className="ledger-review-summary">
              {description}
            </DialogDescription>
          )}
        </DialogHeader>
        {body}
        {footer && <DialogFooter sticky>{footer}</DialogFooter>}
      </DialogContent>
    </Dialog>
  );
}

function ConflictList({
  conflicts,
  choices,
  onChoose,
  locale,
  content,
}: {
  conflicts: AskedConflict[];
  choices: Record<string, "mine" | "theirs">;
  onChoose: (id: string, keep: "mine" | "theirs") => void;
  locale: string;
  content: StagedContent;
}) {
  const t = useStrings();
  return (
    <ul className="ledger-conflicts grid gap-4">
      {conflicts.map((conflict) => {
        const keep = choices[conflict.transactionId] ?? "mine";
        const toggle = (
          <div
            role="radiogroup"
            aria-label={t("desktop.ledger.apply.conflict_choice")}
            className="flex gap-1"
          >
            {(["mine", "theirs"] as const).map((choice) => (
              <Button
                key={choice}
                role="radio"
                aria-checked={keep === choice}
                variant={keep === choice ? "outline" : "ghost"}
                size="xs"
                className={`ledger-conflict-${choice}`}
                onClick={() => onChoose(conflict.transactionId, choice)}
              >
                {t(
                  conflict.kind === "gone"
                    ? `desktop.ledger.apply.gone_${choice}`
                    : `desktop.ledger.apply.${choice}`,
                )}
              </Button>
            ))}
          </div>
        );
        if (conflict.kind === "gone")
          return (
            <li
              key={conflict.transactionId}
              data-conflict="gone"
              className="grid gap-1.5 border-b border-border pb-3"
            >
              <p className="font-medium">
                {conflict.before?.transaction.description ??
                  t("desktop.ledger.apply.gone_movement")}
              </p>
              <p className="text-sm">{t("desktop.ledger.apply.gone")}</p>
              {toggle}
            </li>
          );
        const changes = content.rows[conflict.transactionId] ?? {};
        return (
          <li
            key={conflict.transactionId}
            data-conflict="changed"
            className="grid gap-1.5 border-b border-border pb-3"
          >
            <p className="font-medium">
              {conflict.after.transaction.description}
            </p>
            {conflict.fields.map((field) => {
              const change = changes[field];
              return (
                <dl
                  key={field}
                  className="grid grid-cols-[auto_1fr] gap-x-3 text-sm"
                >
                  <dt className="col-span-2 text-muted-foreground">
                    {fieldName(t, field)}
                  </dt>
                  <dt>{t("desktop.ledger.apply.when_read")}</dt>
                  <dd className="font-medium">
                    {valueText(
                      t,
                      locale,
                      field,
                      storedFieldValue(conflict.before, field) ?? null,
                    )}
                  </dd>
                  <dt>{t("desktop.ledger.apply.now_stored")}</dt>
                  <dd className="font-medium">
                    {valueText(
                      t,
                      locale,
                      field,
                      storedFieldValue(conflict.after, field) ?? null,
                    )}
                  </dd>
                  <dt>{t("desktop.ledger.apply.yours")}</dt>
                  <dd className="font-medium">
                    {change?.kind === "set"
                      ? valueText(t, locale, field, change.value)
                      : t("desktop.ledger.edit.cleared")}
                  </dd>
                </dl>
              );
            })}
            {toggle}
          </li>
        );
      })}
    </ul>
  );
}
