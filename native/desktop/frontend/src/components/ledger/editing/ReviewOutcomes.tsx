import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon, type IconName } from "@/components/ui/icon";
import { useTableView, type ViewColumn } from "@/components/ui/table-view";
import { facts, labelled, listed } from "@/shell/compose";
import type { LedgerRow } from "../../../shell/ledger";
import type { StepOutcome, StepReport } from "../../../shell/ledgerApply";
import type { PlanStep } from "../../../shell/ledgerPlan";
import {
  actionRows,
  storedFieldValue,
  type StageField,
  type StagedAction,
  type StagedContent,
} from "../../../shell/ledgerStage";
import { useStrings, type Translate } from "../../../shell/strings";
import type { ChangeGroup } from "./editingModel";
import { fieldName, valueText } from "./editingWords";
import { titleOf } from "./reviewLabels";
import { WindowedList } from "./WindowedList";

type ActionText = (
  t: Translate,
  locale: string,
  action: StagedAction,
) => string;

// ---- Outcomes --------------------------------------------------------------

export const OUTCOME_ICONS: Record<StepOutcome["kind"], IconName> = {
  applied: "check",
  unchanged: "pending",
  settled: "check",
  refused: "refused",
  unknown: "unknown",
  saved_unread: "unknown",
  not_sent: "pause",
};

/** The colour of an outcome's glyph. */
export function outcomeTone(kind: StepOutcome["kind"]): string | undefined {
  if (kind === "refused") return "text-destructive";
  if (kind === "unknown" || kind === "saved_unread") return "text-warning";
  if (kind === "applied" || kind === "settled") return "text-success";
  return undefined;
}

function stepTitle(
  t: Translate,
  step: PlanStep,
  rows: ReadonlyMap<string, LedgerRow>,
  content: StagedContent,
  actionText: ActionText,
): string {
  switch (step.kind) {
    case "bulk":
      return t("desktop.ledger.apply.step.bulk", {
        count: step.rows.length,
        part: step.part,
        parts: step.parts,
      });
    case "classify":
    case "update":
      return labelled(
        t,
        titleOf(t, rows, step.transactionId),
        listed(
          t,
          step.fields.map((field) => fieldName(t, field)),
        ),
      );
    case "add":
      return t("desktop.ledger.apply.step.add", {
        movement:
          content.drafts.find((draft) => draft.key === step.draftKey)?.fields
            .description ?? step.request.description,
      });
    case "action":
    case "answer":
      return step.action.kind === "rule_apply"
        ? actionText(t, "", step.action)
        : facts(t, [
            actionText(t, "", step.action),
            titleOf(t, rows, actionRows(step.action)[0] ?? ""),
          ]);
  }
}

/** Why a change was refused, in words; its code is under Technical
 * details. */
function refusalWords(
  t: Translate,
  outcome: Extract<StepOutcome, { kind: "refused" }>,
): string {
  if (outcome.reason === "precondition_failed")
    return t("desktop.ledger.apply.refusal.changed_elsewhere");
  return outcome.messages[0] ?? t("desktop.ledger.apply.refusal.other");
}

/** A refusal that a read of the ledger and a new review can resolve. */
export const changedElsewhere = (outcome: StepOutcome) =>
  outcome.kind === "refused" && outcome.reason === "precondition_failed";

function outcomeText(
  t: Translate,
  locale: string,
  outcome: StepOutcome,
  stored: { field: StageField; value: string | null } | null,
): string {
  switch (outcome.kind) {
    case "applied":
      return outcome.newId
        ? t("desktop.ledger.apply.outcome.applied_new_id")
        : t("desktop.ledger.apply.outcome.applied");
    case "unchanged":
      return stored
        ? t("desktop.ledger.apply.outcome.unchanged_value", {
            field: fieldName(t, stored.field),
            value: valueText(t, locale, stored.field, stored.value),
          })
        : t("desktop.ledger.apply.outcome.unchanged");
    case "settled":
      return stored
        ? t("desktop.ledger.apply.outcome.settled_value", {
            field: fieldName(t, stored.field),
            value: valueText(t, locale, stored.field, stored.value),
          })
        : t("desktop.ledger.apply.outcome.settled");
    case "refused":
      return t("desktop.ledger.apply.outcome.refused", {
        reason: refusalWords(t, outcome),
      });
    case "unknown":
      return t("desktop.ledger.apply.outcome.unknown");
    case "saved_unread":
      return t("desktop.ledger.apply.outcome.saved_unread");
    case "not_sent":
      return t(`desktop.ledger.apply.outcome.not_sent_${outcome.why}`);
  }
}

type OutcomeItem = {
  key: string;
  title: string;
  outcome: StepOutcome;
  note: string;
  head?: string;
};

/** Every step's outcome, a bulk part's row by row unless the part ended
 * whole. */
export function outcomeItems(
  t: Translate,
  locale: string,
  reports: readonly StepReport[],
  rows: ReadonlyMap<string, LedgerRow>,
  fresh: ReadonlyMap<string, LedgerRow> | null,
  content: StagedContent,
  actionText: ActionText,
): OutcomeItem[] {
  const storedOf = (
    id: string,
    fields: StageField[],
  ): { field: StageField; value: string | null } | null => {
    const row = fresh?.get(id);
    const field = fields[0];
    if (!row || !field) return null;
    return { field, value: storedFieldValue(row, field) ?? null };
  };
  const items: OutcomeItem[] = [];
  for (const report of reports) {
    const step = report.step;
    if (step.kind === "bulk") {
      const whole =
        report.rows.length > 0 &&
        report.rows.every((row) => row.outcome === report.outcome) &&
        !["applied", "unchanged", "settled"].includes(report.outcome.kind);
      if (whole)
        items.push({
          key: `${report.index}`,
          title: stepTitle(t, step, rows, content, actionText),
          outcome: report.outcome,
          head: "part",
          note:
            report.outcome.kind === "refused"
              ? t("desktop.ledger.apply.part_refused")
              : report.outcome.kind === "unknown"
                ? t("desktop.ledger.apply.part_unknown")
                : outcomeText(t, locale, report.outcome, null),
        });
      else
        step.rows.forEach((row, at) => {
          const outcome = report.rows[at]?.outcome ?? report.outcome;
          items.push({
            key: `${report.index}:${row.transactionId}`,
            title: titleOf(t, rows, row.transactionId),
            outcome,
            note: outcomeText(
              t,
              locale,
              outcome,
              storedOf(row.transactionId, row.fields),
            ),
          });
        });
      continue;
    }
    items.push({
      key: `${report.index}`,
      title: stepTitle(t, step, rows, content, actionText),
      outcome: report.outcome,
      note: outcomeText(
        t,
        locale,
        report.outcome,
        step.kind === "classify" || step.kind === "update"
          ? storedOf(step.transactionId, step.fields)
          : null,
      ),
    });
  }
  return items;
}

export function Outcomes({ items }: { items: readonly OutcomeItem[] }) {
  const t = useStrings();
  if (!items.length) return null;
  return (
    <WindowedList
      label={t("desktop.ledger.apply.outcomes")}
      className="ledger-outcomes max-h-96 rounded-md border border-border"
      items={items}
      keyOf={(item) => item.key}
      render={(item) => (
        <div
          data-outcome={item.outcome.kind}
          data-part={item.head}
          className="flex h-14 items-center gap-2 border-b border-border px-3"
        >
          <Icon
            name={OUTCOME_ICONS[item.outcome.kind]}
            size="xs"
            className={cn("shrink-0", outcomeTone(item.outcome.kind))}
          />
          <span className="grid min-w-0 flex-1">
            <span className="truncate">{item.title}</span>
            <span className="truncate text-sm text-muted-foreground">
              {item.note}
            </span>
          </span>
        </div>
      )}
    />
  );
}

/** The summary by kind of change: the field, what changes and on how many
 * movements, with its columns sortable by field and by count. */
export function SummaryTable({
  groups,
  locale,
  onShowRows,
}: {
  groups: readonly ChangeGroup[];
  locale: string;
  onShowRows(ids: string[]): void;
}) {
  const t = useStrings();
  const field = t("desktop.ledger.apply.summary_field");
  const change = t("desktop.ledger.apply.summary_change");
  const movements = t("desktop.ledger.apply.summary_movements");
  const show = t("desktop.ledger.apply.fix.show");
  const view = useTableView({
    columns: [
      {
        id: "field",
        label: field,
        name: field,
        sortValue: (group) => fieldName(t, group.field),
      },
      { id: "change", label: change, name: change },
      {
        id: "movements",
        label: movements,
        name: movements,
        align: "end",
        sortValue: (group) => group.ids.length,
      },
      {
        id: "show",
        label: show,
        name: show,
        hidden: true,
        resizable: false,
      },
    ] satisfies ViewColumn<ChangeGroup>[],
    rows: groups,
    resizeLabel: (column) => t("desktop.table.resize_column", { column }),
  });
  return (
    <table className="ledger-summary w-full text-base" {...view.tableProps}>
      <thead className="text-sm text-muted-foreground">
        <tr className="border-b border-border">{view.headers}</tr>
      </thead>
      <tbody>
        {view.rows.map((group) => (
          <tr
            key={`${group.field}:${group.ids[0]}`}
            className="border-b border-border"
          >
            <td className="py-1.5 pe-3">{fieldName(t, group.field)}</td>
            <td className="py-1.5 pe-3">
              <span className="text-muted-foreground">
                {valueText(t, locale, group.field, group.from)}
              </span>
              {" → "}
              {group.to.kind === "set"
                ? valueText(t, locale, group.field, group.to.value)
                : t("desktop.ledger.edit.cleared")}
            </td>
            <td className="py-1.5 text-end tabular-nums">{group.ids.length}</td>
            <td className="py-1.5 text-end">
              <Button
                variant="link"
                size="xs"
                onClick={() => onShowRows(group.ids)}
              >
                {t("desktop.ledger.apply.show_rows")}
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
