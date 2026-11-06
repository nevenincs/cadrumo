import { useMemo, type RefObject } from "react";
import type { GridRow } from "@/components/ui/dataGridTypes";
import type { LedgerRow } from "../../../shell/ledger";
import { CLASSIFICATION_OF } from "../../../shell/ledgerCommands";
import { takesClassification } from "../../../shell/ledgerContract";
import type { ServedVocabulary } from "../../../shell/ledgerServedVocabulary";
import { useStrings, type Translate } from "../../../shell/strings";
import { formatMonth } from "../../../shared/dateFormats";
import { formatAmount } from "../../../shared/numbers";
import { GroupActions, type GroupCommands } from "./ClassifyMenus";
import {
  currencySums,
  groupRows,
  groupValue,
  type CurrencySum,
  type GroupingId,
  type MovementSort,
  type SavedViewId,
} from "./movementsModel";
import {
  accountLabel,
  categoryLabel,
  classificationLabel,
  directionLabel,
  familyLabel,
  ivaCategoryLabel,
} from "./movementWords";

const idOf = (row: LedgerRow) => row.transaction.transaction_id;

function SumLine({ sums, locale }: { sums: CurrencySum[]; locale: string }) {
  const t = useStrings();
  return (
    <span className="flex flex-wrap items-center gap-x-3 tabular-nums">
      {sums.map((sum) => (
        <span key={sum.currency} className="flex items-center gap-2">
          {(
            [
              ["incoming", "desktop.ledger.sum.in"],
              ["outgoing", "desktop.ledger.sum.out"],
              ["transfer", "desktop.ledger.sum.transfer"],
            ] as const
          ).map(([side, key]) =>
            sum[side] === null ? null : (
              <span key={side}>
                {t(key, {
                  amount: formatAmount(
                    locale,
                    sum[side],
                    sum.currency === "EUR" ? {} : { currency: sum.currency },
                  ),
                })}
              </span>
            ),
          )}
        </span>
      ))}
    </span>
  );
}

/** A group's name: the label of what it groups by, or what it lacks. */
function groupLabelOf(
  t: Translate,
  locale: string,
  by: GroupingId,
  value: string,
  first: LedgerRow,
): string {
  if (value === "") return t(`desktop.ledger.group.empty.${by}`);
  switch (by) {
    case "category":
      return categoryLabel(t, value);
    case "category_family":
      return familyLabel(t, value);
    case "classification":
      return classificationLabel(t, value);
    case "status":
      return t(`desktop.ledger.review.${value}`);
    case "direction":
      return directionLabel(t, value);
    case "month":
      return formatMonth(locale, value);
    case "iva_category":
      return ivaCategoryLabel(t, value);
    case "counterparty":
      return first.transaction.counterparty.trim();
    default:
      return value;
  }
}

/** The account grouping's labels come from the register, read once. */
function accountGroupLabel(
  t: Translate,
  accounts: readonly { id: string; label: string }[] | null,
  value: string,
): string {
  return accountLabel(t, accounts, value === "" ? null : value);
}

/**
 * The movements shown, in groups where a grouping applies: each group a
 * header row with its count and, over a window read whole, its sums and
 * quick actions, then its rows unless folded.
 */
export function useMovementGroupRows({
  sorted,
  grouping,
  collapsed,
  complete,
  savedView,
  sort,
  locale,
  accounts,
  vocabulary,
  commands,
}: {
  sorted: LedgerRow[];
  grouping: GroupingId | null;
  collapsed: ReadonlySet<string>;
  /** The window is read whole, so a group's sums and actions are whole. */
  complete: boolean;
  savedView: SavedViewId | null;
  /** The sort the rows are drawn in. */
  sort: MovementSort;
  locale: string;
  accounts: readonly { id: string; label: string }[] | null;
  vocabulary: ServedVocabulary;
  /** What a group header's buttons do at the moment they are pressed. */
  commands: RefObject<GroupCommands>;
}) {
  const t = useStrings();
  const groups = useMemo(() => {
    if (!grouping) return null;
    const firstOf = new Map<string, LedgerRow>();
    for (const row of sorted) {
      const value = groupValue(row, grouping, vocabulary);
      if (!firstOf.has(value)) firstOf.set(value, row);
    }
    return groupRows(sorted, grouping, {
      label: (value) =>
        grouping === "account"
          ? accountGroupLabel(t, accounts, value)
          : groupLabelOf(t, locale, grouping, value, firstOf.get(value)!),
      pendingFirst: savedView === "to_classify",
      descending: sort.key === "date" && sort.direction === "desc",
      vocabulary,
    });
  }, [grouping, sorted, savedView, sort, t, locale, accounts, vocabulary]);

  const gridRows = useMemo<GridRow<LedgerRow>[]>(() => {
    if (!groups)
      return sorted.map((row) => ({ kind: "data", key: idOf(row), data: row }));
    const out: GridRow<LedgerRow>[] = [];
    for (const group of groups) {
      const first = group.rows[0]!;
      const folded = collapsed.has(group.key);
      out.push({
        kind: "section",
        key: group.key,
        label:
          grouping === "account"
            ? accountGroupLabel(t, accounts, group.value)
            : groupLabelOf(t, locale, grouping!, group.value, first),
        hint: t("desktop.ledger.group.count", { count: group.rows.length }),
        collapsed: folded,
        summary: complete ? (
          <span className="flex items-center gap-3">
            <SumLine sums={currencySums(group.rows)} locale={locale} />
            <GroupActions
              ids={group.rows.map(idOf)}
              transfers={group.rows.every(
                (row) =>
                  !takesClassification(
                    row.transaction.direction,
                    CLASSIFICATION_OF.business,
                  ),
              )}
              commands={commands}
            />
          </span>
        ) : undefined,
      });
      if (!folded)
        for (const row of group.rows)
          out.push({ kind: "data", key: idOf(row), data: row });
    }
    return out;
  }, [
    groups,
    grouping,
    sorted,
    collapsed,
    complete,
    locale,
    t,
    accounts,
    commands,
  ]);
  return { groups, gridRows };
}
