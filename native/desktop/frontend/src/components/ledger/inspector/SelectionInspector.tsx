import { useId, useMemo, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import {
  ledgerFailure,
  type LedgerLlmSuggestion,
  type LedgerPort,
  type LedgerReview,
  type LedgerRow,
} from "../../../shell/ledger";
import {
  CLASSIFY_KINDS,
  type ClassifyKind,
  type OpenRuleFromSelection,
} from "../../../shell/ledgerCommands";
import { planApply, SINGLE_WRITE_SECONDS } from "../../../shell/ledgerPlan";
import {
  reduceStage,
  type StageEvent,
  type StageState,
} from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { COST_WARNING_WRITES } from "../editing/MovementEditing";
import { fieldName, valueText } from "../editing/editingWords";
import {
  accountLabel,
  amountText,
  classificationLabel,
  directionLabel,
  statusLabel,
} from "../movements/movementWords";
import { currencySums } from "../movements/movementsModel";
import { STATUS_ICONS } from "../movements/MovementCells";
import { MOVEMENT_TSV_COLUMNS, movementsTsv } from "../transfer/tsv";
import type { ActionRequest } from "./ActionDialog";
import type { SectionInspectorContext } from "./inspectorContext";
import {
  DECIDED_CLASSIFICATIONS,
  LIFECYCLE_KINDS,
  commonValue,
  completeCohort,
  needsShare,
  noneClassified,
  selectionCounts,
  setForAll,
  suggestionWrites,
  type CommonValue,
  type SetForAllField,
} from "./inspectorModel";
import {
  categoryOptions,
  irpfCategoryOptions,
  ivaCategoryOptions,
  lifecycleName,
  skipName,
} from "./inspectorWords";
import { useLedgerRead } from "./useInspectorReads";
import { useWritePause, WriteHold } from "../WritePause";

const CLASSIFICATION_OF: Record<ClassifyKind, string> = {
  business: "BUSINESS",
  personal: "PERSONAL",
  mixed: "MIXED",
};
/** The fields whose shared value the selection shows, and how each is
 * read. The classification is counted above them instead. */
const COMMON_FIELDS: readonly (readonly [
  (
    | "category_id"
    | "iva_category"
    | "irpf_category"
    | "direction"
    | "own_account_id"
    | "group_label"
  ),
  (row: LedgerRow) => string | null,
])[] = [
  ["category_id", (row) => row.transaction.category_id],
  ["iva_category", (row) => row.transaction.iva_category],
  ["irpf_category", (row) => row.transaction.irpf_category],
  ["direction", (row) => row.transaction.direction],
  ["own_account_id", (row) => row.own_account_id],
  ["group_label", (row) => row.group_label],
];
/** The most movements one "ask the model for each" asks about. */
const ASK_EACH_MAX = 20;

type Held = {
  field: SetForAllField;
  value: string;
  event: Extract<StageEvent, { type: "stage" }>;
  writes: number;
  seconds: number;
  done: string;
};
type Asked = {
  id: string;
  review: LedgerReview<LedgerLlmSuggestion> | null;
  failed: string | null;
};

/**
 * The inspector of several movements: their totals per currency and
 * direction, counts, the values they share, fields set on all of them as
 * they are chosen, and actions on all of them. What a change skips is
 * counted, a change that would save many movements one at a time says so
 * first, and nothing reaches a movement the person cannot see without
 * saying so. Everything is staged.
 */
export function SelectionInspector({
  port,
  ids,
  rows,
  context,
  generation,
  stage,
  onStage,
  sealed,
  locale,
  onClearSelection,
  onKeepVisible,
  onAction,
  onShow,
  onMakeRule,
  onExport,
  copy,
  say,
}: {
  port: LedgerPort;
  ids: readonly string[];
  rows: ReadonlyMap<string, LedgerRow>;
  context: SectionInspectorContext | null;
  generation: number | string;
  stage: StageState;
  onStage: (event: StageEvent) => void;
  sealed: ReadonlySet<string>;
  locale: string;
  onClearSelection: () => void;
  onKeepVisible: () => void;
  onAction: (request: ActionRequest) => void;
  onShow: (id: string) => void;
  /** Opens the rule dialog prefilled from these movements, where the page
   * has one. */
  onMakeRule?: OpenRuleFromSelection;
  /** Opens the export, where the page has one. */
  onExport?: () => void;
  copy: (text: string) => Promise<void>;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const shareId = useId();
  const selected = useMemo(
    () => ids.flatMap((id) => (rows.has(id) ? [rows.get(id)!] : [])),
    [ids, rows],
  );
  const visible = context?.visible ?? new Set<string>();
  const hidden = selected.filter(
    (row) => !visible.has(row.transaction.transaction_id),
  ).length;
  const shown = selected.length - hidden;
  const blocked = shown === 0;
  const counts = selectionCounts(
    selected,
    context?.checked ? context.issues : null,
  );
  const content = stage.content;
  // While none of them is classified, or staged to be, the tax fields take
  // nothing yet.
  const undecided = noneClassified(selected, content);
  const sums = currencySums(selected);
  const [share, setShare] = useState("");
  const [group, setGroup] = useState("");
  const [notes, setNotes] = useState("");
  const [held, setHeld] = useState<Held | null>(null);
  const [asked, setAsked] = useState<Asked[] | null>(null);
  const [asking, setAsking] = useState(false);

  // A complete split cohort can be merged: the history of one part names
  // its siblings.
  const first = ids[0] ?? "";
  const history = useLedgerRead(
    port,
    "ledger.history.typed",
    { transaction_prefix: first, include_split_siblings: true },
    `${first}:${generation}`,
    ids.length >= 2 && ids.length <= 128,
  );
  const cohort =
    history?.kind === "ready" &&
    completeCohort(ids, history.result.object_ids, rows);

  const common = (read: (row: LedgerRow) => string | null): CommonValue =>
    commonValue(selected.map(read));
  const commonText = (value: CommonValue, show: (value: string) => string) =>
    value.kind === "mixed"
      ? t("desktop.ledger.inspector.selection.mixed_values", {
          count: value.count,
        })
      : value.value === null
        ? t("desktop.ledger.inspector.not_set")
        : show(value.value);

  const setLabel = (visibleCount: number, hiddenCount: number) =>
    hiddenCount > 0
      ? t("desktop.ledger.inspector.selection.set_hidden", {
          visible: visibleCount,
          hidden: hiddenCount,
        })
      : t("desktop.ledger.inspector.selection.set_for", {
          count: visibleCount,
        });

  const stageSet = (field: SetForAllField, value: string, force = false) => {
    const found = setForAll(field, value, ids, rows, {
      content,
      sealed,
      visible,
    });
    const skipped = Object.entries(found.skipped)
      .map(([reason, count]) =>
        t("desktop.ledger.inspector.selection.skipped_reason", {
          count,
          reason: skipName(t, reason as Parameters<typeof skipName>[1]),
        }),
      )
      .join(", ");
    if (found.cells.length === 0) {
      say(skipped || t("desktop.ledger.inspector.selection.nothing"));
      return;
    }
    const event: Extract<StageEvent, { type: "stage" }> = {
      type: "stage",
      label: "bulk_set",
      cells: found.cells,
    };
    const done = [
      t("desktop.ledger.inspector.selection.staged", {
        count: found.cells.length,
      }),
      skipped,
    ]
      .filter(Boolean)
      .join(" · ");
    if (!force) {
      const before = planApply(content, { rows, sealed }).summary;
      const after = planApply(reduceStage(stage, event).content, {
        rows,
        sealed,
      }).summary;
      const writes = after.oneAtATime - before.oneAtATime;
      if (writes > COST_WARNING_WRITES) {
        setHeld({
          field,
          value,
          event,
          writes,
          seconds:
            (after.oneAtATime - before.oneAtATime) * SINGLE_WRITE_SECONDS,
          done,
        });
        return;
      }
    }
    setHeld(null);
    onStage(event);
    say(done);
  };

  const choice = (
    field: SetForAllField,
    label: string,
    options: ComboboxOption[],
  ) => {
    const preview = setForAll(field, "x", ids, rows, {
      content,
      sealed,
      visible,
    });
    const skipped = Object.values(preview.skipped).reduce(
      (sum, count) => sum + count,
      0,
    );
    return (
      <div className="grid gap-0.5">
        <span className="text-sm text-muted-foreground">
          {label}
          {skipped > 0 &&
            ` · ${t("desktop.ledger.inspector.selection.skipped", { count: skipped })}`}
        </span>
        <Combobox
          label={label}
          value={null}
          options={options}
          emptyLabel={t("desktop.ledger.inspector.no_match")}
          onCommit={(value) => stageSet(field, value)}
        >
          <Button
            variant="outline"
            size="sm"
            data-set={field}
            disabled={blocked || preview.cells.length === 0}
            className="justify-between"
          >
            {setLabel(preview.visible, preview.hidden)}
            <Icon name="chevronDown" size="xs" />
          </Button>
        </Combobox>
      </div>
    );
  };

  const { held: paused } = useWritePause();
  async function askEach() {
    // Each ask runs the registered review, a write the page's pause holds.
    if (paused !== null) return;
    const targets = ids
      .filter((id) => visible.has(id))
      .filter((id) => rows.get(id)?.transaction.lifecycle_state === "ACTIVE")
      .slice(0, ASK_EACH_MAX);
    setAsking(true);
    const found: Asked[] = [];
    for (const id of targets) {
      try {
        const outcome = await port.submit("ledger.classify.review", {
          transaction_id: id,
          mode: "classification",
          origin: "classify_llm_apply",
        });
        if (outcome.kind !== "review") {
          found.push({
            id,
            review: null,
            failed:
              outcome.kind === "refused"
                ? (outcome.reason ?? "refused")
                : "no_review",
          });
          continue;
        }
        found.push({
          id,
          review: await port.review<LedgerLlmSuggestion>(outcome.operation_id),
          failed: null,
        });
      } catch (error) {
        const failure = ledgerFailure(error);
        found.push({
          id,
          review: null,
          failed: failure.reason ?? failure.code,
        });
      }
      setAsked([...found]);
    }
    setAsking(false);
  }
  const approve = (entry: Asked) => {
    if (!entry.review) return;
    onStage({
      type: "stage_action",
      action: {
        id: `suggestion:${entry.id}`,
        kind: "suggestion",
        transactionId: entry.id,
        operationId: entry.review.operation_id,
        reviewDigest: entry.review.review_digest,
        decision: "apply",
        reason: "",
        writes: suggestionWrites(entry.review.review.suggestion),
      },
    });
  };
  const approvable = (asked ?? []).filter(
    (entry) =>
      entry.review !== null &&
      !needsShare(entry.review.review.suggestion) &&
      !content.actions.some((action) => action.id === `suggestion:${entry.id}`),
  );

  return (
    <div className="ledger-selection flex min-h-0 flex-1 flex-col">
      <div className="flex items-start gap-2 border-b px-3 py-2">
        <h2 className="min-w-0 flex-1 text-base font-medium">
          {t("desktop.ledger.inspector.selection.title", {
            count: selected.length,
          })}
        </h2>
        <Button variant="ghost" size="xs" onClick={onClearSelection}>
          {t("desktop.ledger.inspector.selection.clear")}
        </Button>
      </div>
      <div
        tabIndex={0}
        aria-label={t("desktop.ledger.inspector.selection.body")}
        className="grid min-h-0 flex-1 content-start gap-4 overflow-y-auto px-3 py-3 focus-visible:-outline-offset-2"
      >
        {context?.partial && (
          <Alert icon={<Icon name="info" />}>
            {t("desktop.ledger.inspector.selection.partial")}
          </Alert>
        )}
        {hidden > 0 && (
          <Alert tone="warning" role="alert" icon={<Icon name="alert" />}>
            <span className="grid gap-1.5 text-foreground">
              {t("desktop.ledger.selection.hidden", {
                hidden,
                selected: selected.length,
              })}
              <span className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => context?.showHidden()}
                >
                  {t("desktop.ledger.selection.show")}
                </Button>
                <Button variant="ghost" size="xs" onClick={onKeepVisible}>
                  {t("desktop.ledger.selection.keep_visible")}
                </Button>
              </span>
            </span>
          </Alert>
        )}

        <section aria-labelledby={`${shareId}-totals`} className="grid gap-2">
          <h3 id={`${shareId}-totals`} className="text-sm font-semibold">
            {t("desktop.ledger.inspector.selection.totals")}
          </h3>
          <ul className="ledger-selection-sums grid gap-0.5 rounded-md bg-accent p-2.5 text-sm tabular-nums">
            {sums.flatMap((sum) =>
              (
                [
                  ["incoming", "desktop.ledger.sum.in"],
                  ["outgoing", "desktop.ledger.sum.out"],
                  ["transfer", "desktop.ledger.sum.transfer"],
                ] as const
              ).flatMap(([side, label]) =>
                sum[side] === null
                  ? []
                  : [
                      <li key={`${sum.currency}:${side}`}>
                        {t(label, {
                          amount: `${amountText(locale, sum[side]!)} ${sum.currency}`,
                        })}
                      </li>,
                    ],
              ),
            )}
          </ul>
          <ul className="ledger-selection-statuses flex flex-wrap gap-x-3 gap-y-0.5 text-sm">
            {counts.statuses.map(([word, count]) => {
              const name =
                word === "needs_fixing"
                  ? t("desktop.ledger.status.needs_fixing")
                  : statusLabel(t, word, null);
              return (
                <li
                  key={word}
                  data-status={word}
                  title={name}
                  className="inline-flex items-center gap-1 text-muted-foreground"
                >
                  <Icon name={STATUS_ICONS[word]} size="xs" />
                  <span aria-hidden="true" className="text-foreground">
                    {count}
                  </span>
                  <span className="sr-only">{`${name} ${count}`}</span>
                </li>
              );
            })}
            {counts.classifications
              .filter(([classification]) =>
                DECIDED_CLASSIFICATIONS.has(classification),
              )
              .map(([classification, count]) => (
                <li key={classification}>
                  {classificationLabel(t, classification)}{" "}
                  <span className="font-medium tabular-nums">{count}</span>
                </li>
              ))}
          </ul>
        </section>

        <section aria-labelledby={`${shareId}-common`} className="grid gap-2">
          <h3 id={`${shareId}-common`} className="text-sm font-semibold">
            {t("desktop.ledger.inspector.selection.common")}
          </h3>
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-sm">
            {COMMON_FIELDS.map(([field, read]) => (
              <div key={field} className="contents">
                <dt className="text-muted-foreground">{fieldName(t, field)}</dt>
                <dd data-common={field}>
                  {commonText(common(read), (value) =>
                    field === "direction"
                      ? directionLabel(t, value)
                      : field === "own_account_id"
                        ? accountLabel(t, context?.accounts ?? null, value)
                        : valueText(t, locale, field, value),
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <section aria-labelledby={`${shareId}-set`} className="grid gap-2">
          <h3 id={`${shareId}-set`} className="text-sm font-semibold">
            {t("desktop.ledger.inspector.selection.set_title")}
          </h3>
          {held && (
            <Alert tone="warning" role="alert" icon={<Icon name="clock" />}>
              <span className="grid gap-1.5 text-foreground">
                {t("desktop.ledger.inspector.selection.cost", {
                  count: held.writes,
                  minutes: Math.max(1, Math.ceil(held.seconds / 60)),
                })}
                <span className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="xs"
                    onClick={() => stageSet(held.field, held.value, true)}
                  >
                    {t("desktop.ledger.inspector.selection.stage_anyway")}
                  </Button>
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={() => setHeld(null)}
                  >
                    {t("desktop.ledger.inspector.selection.classify_first")}
                  </Button>
                </span>
              </span>
            </Alert>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <SegmentedControl
              aria-label={t(
                "desktop.ledger.inspector.selection.classification",
              )}
              value=""
              disabled={blocked || context === null}
              onValueChange={(value) => {
                const kind = value as ClassifyKind;
                const typed = share.trim();
                context?.classify(
                  kind,
                  kind === "mixed" && typed
                    ? { answer: { share: typed } }
                    : undefined,
                );
              }}
            >
              {CLASSIFY_KINDS.map((kind) => (
                <SegmentedControlItem key={kind} value={kind}>
                  {classificationLabel(t, CLASSIFICATION_OF[kind])}
                  {kind !== "personal" && "…"}
                </SegmentedControlItem>
              ))}
            </SegmentedControl>
            <label className="grid gap-0.5 text-sm">
              <span className="text-muted-foreground">
                {t("desktop.ledger.inspector.share")}
              </span>
              <Input
                controlSize="sm"
                inputMode="decimal"
                className="w-20"
                value={share}
                disabled={blocked}
                onChange={(event) => setShare(event.target.value)}
              />
            </label>
          </div>
          {undecided ? (
            <p className="ledger-classify-first text-sm text-muted-foreground">
              {t("desktop.ledger.inspector.selection.classify_first_hint")}
            </p>
          ) : (
            <>
              {choice(
                "category_id",
                fieldName(t, "category_id"),
                categoryOptions(t),
              )}
              {choice(
                "iva_category",
                fieldName(t, "iva_category"),
                ivaCategoryOptions(t),
              )}
              {choice(
                "irpf_category",
                fieldName(t, "irpf_category"),
                irpfCategoryOptions(t),
              )}
            </>
          )}
          {(
            [
              ["group_label", group, setGroup, 64],
              ["notes", notes, setNotes, 4096],
            ] as const
          ).map(([field, value, setValue, max]) => {
            const preview = setForAll(field, value || "x", ids, rows, {
              content,
              sealed,
              visible,
            });
            return (
              <form
                key={field}
                className="flex items-end gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (value.trim()) stageSet(field, value.trim());
                }}
              >
                <label className="grid min-w-0 flex-1 gap-0.5 text-sm">
                  <span className="text-muted-foreground">
                    {fieldName(t, field)}
                  </span>
                  <Input
                    controlSize="sm"
                    maxLength={max}
                    value={value}
                    disabled={blocked}
                    onChange={(event) => setValue(event.target.value)}
                  />
                </label>
                <Button
                  type="submit"
                  variant="outline"
                  size="sm"
                  disabled={
                    blocked || !value.trim() || preview.cells.length === 0
                  }
                >
                  {setLabel(preview.visible, preview.hidden)}
                </Button>
              </form>
            );
          })}
        </section>

        <section aria-labelledby={`${shareId}-actions`} className="grid gap-2">
          <h3 id={`${shareId}-actions`} className="text-sm font-semibold">
            {t("desktop.ledger.inspector.selection.actions")}
          </h3>
          <div className="flex flex-wrap gap-2">
            {LIFECYCLE_KINDS.map((kind) => (
              <Button
                key={kind}
                variant="outline"
                size="sm"
                disabled={blocked}
                onClick={() => onAction({ kind, ids })}
              >
                {lifecycleName(t, kind)}…
              </Button>
            ))}
            <Button
              variant="outline"
              size="sm"
              disabled={!cohort}
              aria-description={
                cohort
                  ? undefined
                  : t("desktop.ledger.inspector.selection.merge_hint")
              }
              onClick={() => onAction({ kind: "merge", ids })}
            >
              <Icon name="merge" />
              {t("desktop.ledger.inspector.action.merge")}…
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {onMakeRule && (
              <Button
                variant="outline"
                size="sm"
                disabled={blocked}
                onClick={() => onMakeRule({ ids })}
              >
                {t("desktop.ledger.inspector.selection.make_rule")}…
              </Button>
            )}
            <WriteHold>
              <Button
                variant="outline"
                size="sm"
                disabled={blocked || asking}
                onClick={() => void askEach()}
              >
                {asking ? <Spinner /> : <Icon name="agent" />}
                {t("desktop.ledger.inspector.selection.ask_each")}
              </Button>
            </WriteHold>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                void copy(
                  movementsTsv(
                    MOVEMENT_TSV_COLUMNS.map((column) =>
                      t(`desktop.ledger.export.tsv.${column}`),
                    ),
                    selected,
                  ),
                ).then(() =>
                  say(
                    t("desktop.ledger.inspector.selection.copied", {
                      count: selected.length,
                    }),
                  ),
                )
              }
            >
              <Icon name="copy" />
              {t("desktop.ledger.inspector.selection.copy")}
            </Button>
            {onExport && (
              <Button variant="outline" size="sm" onClick={onExport}>
                <Icon name="download" />
                {t("desktop.ledger.action.export")}…
              </Button>
            )}
          </div>
          {asked && (
            <div className="ledger-asked grid gap-2">
              <p className="text-sm">
                {t("desktop.ledger.inspector.selection.asked", {
                  count: asked.filter((entry) => entry.review).length,
                })}
              </p>
              <ul className="grid gap-1.5">
                {asked.map((entry) => {
                  const row = rows.get(entry.id);
                  const suggestion = entry.review?.review.suggestion;
                  const stagedAnswer = content.actions.some(
                    (action) => action.id === `suggestion:${entry.id}`,
                  );
                  return (
                    <li
                      key={entry.id}
                      className="grid gap-1 rounded-md bg-accent p-2 text-sm"
                    >
                      <span className="font-medium break-words">
                        {row?.transaction.description ?? entry.id.slice(0, 12)}
                      </span>
                      {suggestion ? (
                        <span>
                          {suggestionWrites(suggestion)
                            .filter((write) => !write.derived)
                            .map((write) =>
                              valueText(t, locale, write.field, write.value),
                            )
                            .join(" · ")}
                        </span>
                      ) : (
                        <code className="font-mono text-xs">
                          {entry.failed}
                        </code>
                      )}
                      <span className="flex flex-wrap gap-2">
                        {suggestion &&
                          !needsShare(suggestion) &&
                          !stagedAnswer && (
                            <Button
                              variant="outline"
                              size="xs"
                              onClick={() => approve(entry)}
                            >
                              {t("desktop.ledger.inspector.model.approve")}
                            </Button>
                          )}
                        {stagedAnswer && (
                          <span className="text-xs">
                            {t(
                              "desktop.ledger.inspector.model.approval_staged",
                            )}
                          </span>
                        )}
                        {suggestion && needsShare(suggestion) && (
                          <span className="text-xs">
                            {t("desktop.ledger.inspector.model.share_needed")}
                          </span>
                        )}
                        <Button
                          variant="ghost"
                          size="xs"
                          onClick={() => onShow(entry.id)}
                        >
                          {t("desktop.ledger.inspector.show")}
                        </Button>
                      </span>
                    </li>
                  );
                })}
              </ul>
              {approvable.length > 1 && (
                <Button
                  size="sm"
                  className="w-fit"
                  onClick={() => {
                    approvable.forEach(approve);
                    say(
                      t("desktop.ledger.inspector.selection.approved_all", {
                        count: approvable.length,
                      }),
                    );
                  }}
                >
                  {t("desktop.ledger.inspector.selection.approve_all", {
                    count: approvable.length,
                  })}
                </Button>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
