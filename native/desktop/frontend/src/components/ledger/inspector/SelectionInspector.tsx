import { useId, useMemo, useState } from "react";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Field, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import { counted, facts, listed } from "@/shell/compose";
import {
  useBackgroundTasks,
  type JobNotice,
} from "../../../shell/backgroundTasks";
import type { LedgerPort } from "../../../shell/ledger";
import {
  CLASSIFY_KINDS,
  type ClassifyKind,
  type OpenRuleFromSelection,
} from "../../../shell/ledgerCommands";
import { parseFractionPercent, percentOf } from "../../../shell/ledgerGrammar";
import {
  planApply,
  SINGLE_WRITE_SECONDS,
  type PropertySet,
} from "../../../shell/ledgerPlan";
import {
  isDecidedClassification,
  takesChanges,
} from "../../../shell/ledgerContract";
import {
  checkOnce,
  NOTHING_CHECKED,
  stagedCheckRequest,
  useStagedCheck,
} from "../../../shell/ledgerStagedCheck";
import {
  reduceStage,
  type StageEvent,
  type StageState,
} from "../../../shell/ledgerStage";
import { useTextLimit } from "../../../shell/ledgerLimits";
import { useStrings } from "../../../shell/strings";
import { COST_WARNING_WRITES } from "../editing/MovementEditing";
import { fieldName, valueText } from "../editing/editingWords";
import {
  accountLabel,
  classificationLabel,
  directionLabel,
  statusLabel,
  vocabularyEmpty,
} from "../movements/movementWords";
import { currencySums } from "../movements/movementsModel";
import { STATUS_ICONS } from "../movements/MovementCells";
import { MOVEMENT_TSV_COLUMNS, movementsTsv } from "../transfer/tsv";
import type { ActionRequest } from "./ActionDialog";
import type { SectionInspectorContext } from "./inspectorContext";
import {
  LIFECYCLE_KINDS,
  commonValue,
  completeCohort,
  noneClassified,
  selectionCounts,
  setForAll,
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
import { SelectionJobProposals } from "./JobProposal";
import { NoticeLine } from "../../shell/BackgroundTasks";
import { useLedgerRead } from "./useInspectorReads";
import {
  useFieldSuggestions,
  useServedChoices,
  useVocabulary,
} from "../suggestions/SuggestionsProvider";
import { useWritePause, WriteHold } from "../WritePause";
import { formatAmount } from "../../../shared/numbers";
import type { LedgerTransactionReviewProjection } from "../../../shell/ledgerReadContract";

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
  (row: LedgerTransactionReviewProjection) => string | null,
])[] = [
  ["category_id", (row) => row.transaction.category_id],
  ["iva_category", (row) => row.transaction.iva_category],
  ["irpf_category", (row) => row.transaction.irpf_category],
  ["direction", (row) => row.transaction.direction],
  ["own_account_id", (row) => row.own_account_id],
  ["group_label", (row) => row.group_label],
];
type Held = {
  field: SetForAllField;
  value: string;
  event: Extract<StageEvent, { type: "stage" }>;
  writes: number;
  seconds: number;
  done: string;
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
  unread,
  locale,
  onClearSelection,
  onKeepVisible,
  onAction,
  onShow,
  onMakeRule,
  onExport,
  copy,
  say,
  copied = null,
  onPasteProperties,
}: {
  port: LedgerPort;
  ids: readonly string[];
  rows: ReadonlyMap<string, LedgerTransactionReviewProjection>;
  context: SectionInspectorContext | null;
  generation: number | string;
  stage: StageState;
  onStage: (event: StageEvent) => void;
  sealed: ReadonlySet<string>;
  /** Movements whose sealed state the page could not read. */
  unread: ReadonlySet<string>;
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
  /** The properties last copied from a movement, which can be pasted onto
   * these. */
  copied?: PropertySet | null;
  onPasteProperties?: () => void;
}) {
  const t = useStrings();
  const vocabulary = useVocabulary();
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
  const checked = useStagedCheck(
    port,
    useMemo(
      () =>
        stagedCheckRequest(content, rows, {
          ids: selected.map((row) => row.transaction.transaction_id),
        }),
      [content, rows, selected],
    ),
  );
  const undecided = noneClassified(selected, checked.current);
  const sums = currencySums(selected);
  const [share, setShare] = useState("");
  const [group, setGroup] = useState("");
  const groups = useFieldSuggestions("group");
  const [notes, setNotes] = useState("");
  const [counterparty, setCounterparty] = useState("");
  const deductionKinds = useServedChoices("deduction_fact_kind");
  const [held, setHeld] = useState<Held | null>(null);
  const tasks = useBackgroundTasks();
  // What the last ask for a job over this selection came to.
  const [askNotice, setAskNotice] = useState<JobNotice | null>(null);

  const mostParts = useTextLimit("split_parts");
  const groupLimit = useTextLimit("group_label");
  const textLimit = useTextLimit("entry_text");

  // A complete split cohort can be merged: the history of one part names
  // its siblings.
  const first = ids[0] ?? "";
  const history = useLedgerRead(
    port,
    "ledger.history.typed",
    { transaction_prefix: first, include_split_siblings: true },
    `${first}:${generation}`,
    mostParts !== null && ids.length >= 2 && ids.length <= mostParts,
  );
  const cohort =
    history?.kind === "ready" &&
    completeCohort(ids, history.result.object_ids, rows);

  const common = (
    read: (row: LedgerTransactionReviewProjection) => string | null,
  ): CommonValue => commonValue(selected.map(read));
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

  const stageSet = async (
    field: SetForAllField,
    value: string,
    force = false,
  ) => {
    // The movements may reach beyond those selected and drawn.
    const check = await checkOnce(
      port,
      stagedCheckRequest(content, rows, { ids }),
    );
    if (!check) {
      say(t("desktop.ledger.apply.read_failed"));
      return;
    }
    const found = setForAll(field, value, ids, rows, {
      check,
      sealed,
      unread,
      visible,
    });
    const skipped = listed(
      t,
      Object.entries(found.skipped).map(([reason, count]) =>
        t("desktop.ledger.inspector.selection.skipped_reason", {
          count,
          reason: skipName(t, reason as Parameters<typeof skipName>[1]),
        }),
      ),
      "plain",
    );
    if (found.cells.length === 0) {
      say(skipped || t("desktop.ledger.inspector.selection.nothing"));
      return;
    }
    const event: Extract<StageEvent, { type: "stage" }> = {
      type: "stage",
      label: "bulk_set",
      cells: found.cells,
    };
    const done = facts(t, [
      t("desktop.ledger.inspector.selection.staged", {
        count: found.cells.length,
      }),
      skipped,
    ]);
    if (!force) {
      const next = reduceStage(stage, event).content;
      const after_ = await checkOnce(
        port,
        stagedCheckRequest(next, rows, { ids }),
      );
      if (!after_) {
        say(t("desktop.ledger.apply.read_failed"));
        return;
      }
      const before = planApply(content, {
        rows,
        check,
        sealed,
        unread,
      }).summary;
      const after = planApply(next, {
        rows,
        check: after_,
        sealed,
        unread,
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
      check: checked.current ?? NOTHING_CHECKED,
      sealed,
      unread,
      visible,
    });
    const skipped = Object.values(preview.skipped).reduce(
      (sum, count) => sum + count,
      0,
    );
    return (
      <div className="grid gap-0.5">
        <span className="text-sm text-muted-foreground">
          {facts(t, [
            label,
            skipped > 0 &&
              t("desktop.ledger.inspector.selection.skipped", {
                count: skipped,
              }),
          ])}
        </span>
        <Combobox
          label={label}
          value={null}
          options={options}
          emptyLabel={vocabularyEmpty(
            t,
            vocabulary,
            t("desktop.ledger.inspector.no_match"),
            options.length,
          )}
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
  // The selected movements the agent can be asked about: those shown that
  // take changes and that no job is classifying already.
  const askable = ids.filter(
    (id) =>
      visible.has(id) &&
      takesChanges(rows.get(id)?.transaction.lifecycle_state ?? "") &&
      tasks.rows.get(id)?.kind !== "classifying",
  );
  const askAgent = () => {
    // The job's ask is a write the page's pause holds.
    if (paused !== null || askable.length === 0) return;
    setAskNotice(null);
    void tasks.enqueue("selection", askable).then(setAskNotice);
  };

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
              {counted(
                t,
                selected.length,
                {
                  one: "desktop.ledger.selection.hidden_one",
                  many: "desktop.ledger.selection.hidden",
                },
                { hidden, selected: selected.length },
              )}
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
                          amount: formatAmount(locale, sum[side]!, {
                            currency: sum.currency,
                          }),
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
                isDecidedClassification(classification),
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
          {onPasteProperties && (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="ledger-paste-properties-open"
                aria-disabled={copied === null || blocked || undefined}
                aria-description={
                  copied === null
                    ? t("desktop.ledger.properties.copy_first")
                    : blocked
                      ? t("desktop.ledger.properties.none_shown")
                      : undefined
                }
                onClick={() => {
                  if (copied === null) {
                    say(t("desktop.ledger.properties.copy_first"));
                    return;
                  }
                  if (blocked) {
                    say(t("desktop.ledger.properties.none_shown"));
                    return;
                  }
                  onPasteProperties();
                }}
              >
                <Icon name="paste" />
                {t("desktop.ledger.properties.paste_open", {
                  count: ids.length,
                })}
              </Button>
              {copied !== null && (
                <span className="text-sm text-muted-foreground">
                  {t("desktop.ledger.properties.held", {
                    count: copied.fields.length,
                  })}
                </span>
              )}
            </div>
          )}
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
                // The classify command reads a share in points.
                const read = parseFractionPercent(share);
                const typed =
                  read.kind === "value"
                    ? (percentOf(read.value) ?? share.trim())
                    : share.trim();
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
            <Field className="w-fit gap-0.5">
              <FieldLabel htmlFor={`${shareId}-share`} className="font-normal">
                {t("desktop.ledger.inspector.share")}
              </FieldLabel>
              <div className="w-20">
                <PercentEditor
                  unit="fraction"
                  id={`${shareId}-share`}
                  controlSize="sm"
                  value={share}
                  disabled={blocked}
                  onChange={setShare}
                />
              </div>
            </Field>
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
                categoryOptions(t, vocabulary),
              )}
              {choice(
                "iva_category",
                fieldName(t, "iva_category"),
                ivaCategoryOptions(t, vocabulary),
              )}
              {choice(
                "irpf_category",
                fieldName(t, "irpf_category"),
                irpfCategoryOptions(t, vocabulary),
              )}
              {choice(
                "deduction_fact_kind",
                fieldName(t, "deduction_fact_kind"),
                [...(deductionKinds ?? [])],
              )}
            </>
          )}
          {(
            [
              ["counterparty", counterparty, setCounterparty, textLimit],
              ["group_label", group, setGroup, groupLimit],
              ["notes", notes, setNotes, textLimit],
            ] as const
          ).map(([field, value, setValue, max]) => {
            const preview = setForAll(field, value || "x", ids, rows, {
              check: checked.current ?? NOTHING_CHECKED,
              sealed,
              unread,
              visible,
            });
            const skipped = Object.values(preview.skipped).reduce(
              (sum, count) => sum + count,
              0,
            );
            return (
              <form
                key={field}
                className="flex items-end gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (value.trim()) stageSet(field, value.trim());
                }}
              >
                <Field className="min-w-0 flex-1 gap-0.5">
                  <FieldLabel
                    htmlFor={`${shareId}-${field}`}
                    className="font-normal"
                  >
                    {/* A disabled "set for 0" says why: the movements it
                        leaves out, as the choices above say it. */}
                    {facts(t, [
                      fieldName(t, field),
                      skipped > 0 &&
                        t("desktop.ledger.inspector.selection.skipped", {
                          count: skipped,
                        }),
                    ])}
                  </FieldLabel>
                  <TextEditor
                    id={`${shareId}-${field}`}
                    controlSize="sm"
                    maxLength={max ?? undefined}
                    value={value}
                    disabled={blocked}
                    onChange={setValue}
                    {...(field === "group_label"
                      ? { ...groups, opensEmpty: true }
                      : {})}
                  />
                </Field>
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
                data-action="ask_agent"
                disabled={
                  blocked ||
                  !tasks.offered ||
                  tasks.enqueueing ||
                  askable.length === 0
                }
                aria-description={
                  askable.length === 0
                    ? t("desktop.background_tasks.ask_agent_none")
                    : undefined
                }
                onClick={askAgent}
              >
                {tasks.enqueueing ? <Spinner /> : <Icon name="agent" />}
                {t("desktop.background_tasks.ask_agent")}
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
          {askable.length === 0 && !blocked && (
            <p className="text-xs text-muted-foreground" data-ask-agent-none>
              {t("desktop.background_tasks.ask_agent_none")}
            </p>
          )}
          {askNotice && <NoticeLine notice={askNotice} />}
          <SelectionJobProposals
            ids={ids}
            rows={rows}
            locale={locale}
            onShow={onShow}
          />
        </section>
      </div>
    </div>
  );
}
