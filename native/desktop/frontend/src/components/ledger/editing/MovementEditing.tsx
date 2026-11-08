import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";
import type {
  DataGridHandle,
  EditorContext,
  GridRow,
} from "@/components/ui/dataGridTypes";
import type { CellRange } from "@/components/ui/dataGridModel";
import { chordMatches, type ChordKeys } from "@/shared/chords";
import { REDO_CHORDS, REVIEW_CHORDS, UNDO_CHORD } from "../ledgerChords";
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import { classifyKindOf } from "../../../shell/ledgerCommands";
import { carriesBusinessFigures } from "../../../shell/ledgerClassifications";
import { percentOf, copyAmount } from "../../../shell/ledgerGrammar";
import { planApply } from "../../../shell/ledgerPlan";
import {
  checkOnce,
  stagedCheckRequest,
  useStagedCheck,
} from "../../../shell/ledgerStagedCheck";
import {
  effectiveFacts,
  actionRows,
  reduceStage,
  storedFieldValue,
  type Draft,
  type DraftField,
  type StageEvent,
  type StageField,
  type StagedContent,
  type StageState,
} from "../../../shell/ledgerStage";
import type { OwnAccountChoice } from "../../../shell/ledgerMovementReads";
import type { Translate } from "../../../shell/strings";
import { tsvCell } from "../transfer/tsv";
import type { ColumnEditing } from "../movements/MovementsGrid";
import type { ColumnId } from "../movements/movementsModel";
import {
  categoryLabel,
  classificationText,
  directionLabel,
  irpfCategoryLabel,
  ivaCategoryLabel,
} from "../movements/movementWords";
import {
  ChoiceEditor,
  TypedEditor,
  isTyped,
  type EditCommit,
} from "./CellEditor";
import {
  DraftStatus,
  DraftValue,
  RefusedValue,
  StagedValue,
  UnsavedEdge,
} from "./EditedCells";
import {
  DRAFT_REQUIRED,
  EDIT_KINDS,
  backendOwnsRefusal,
  clearRefusal,
  columnField,
  copyCell,
  draftEdits,
  draftField,
  draftRow,
  effectiveValue,
  lockReason,
  planFill,
  planPaste,
  rowCells,
  type CellValue,
  type DraftEdit,
  type EditRefusal,
  type EditSubject,
  type PastePlan,
  type RefusedCell,
} from "./editingModel";
import { choiceLabels, fieldName, lockText, refusalText } from "./editingWords";
import {
  useVocabulary,
  type SuggestionKind,
} from "../suggestions/SuggestionsProvider";
import { CostDialog, PasteDialog } from "./PasteDialog";
import {
  formatAmount,
  formatPercent,
  heldDecimal,
} from "../../../shared/numbers";
import { formatDay } from "../../../shared/dateFormats";

/** More saves one at a time than this, added by one change, asks first. */

/** The text a typed column may be picked from. */
const CELL_OFFERS: Partial<Record<ColumnId, SuggestionKind>> = {
  description: "description",
  counterparty: "counterparty",
  group_label: "group",
};

/** The fields whose staged value differs between two stages, over every
 * movement either stages. */
function changedFields(
  now: StagedContent,
  before: StagedContent,
): StageField[] {
  const found = new Set<StageField>();
  for (const id of new Set([
    ...Object.keys(now.rows),
    ...Object.keys(before.rows),
  ])) {
    const a = now.rows[id] ?? {};
    const b = before.rows[id] ?? {};
    for (const field of new Set([
      ...Object.keys(a),
      ...Object.keys(b),
    ]) as Set<StageField>)
      if (JSON.stringify(a[field]) !== JSON.stringify(b[field]))
        found.add(field);
  }
  return [...found];
}

export const COST_WARNING_WRITES = 10;
/** The most saves one at a time a movement can take: a classification and a
 * correction. */
const WRITES_PER_MOVEMENT = 2;

/** Takes the active cell's staged change back: this grid runs it, and the
 * movement menu that offers it shows it. */
export const REVERT_CELL_CHORD: ChordKeys = {
  code: "KeyZ",
  key: "Z",
  ctrl: true,
  alt: true,
};

const cellKey = (key: string, column: string) => `${key}\u0000${column}`;

/** What staged editing needs from the movements section. */
export type MovementEditingInput = {
  t: Translate;
  locale: string;
  grid: RefObject<DataGridHandle | null>;
  /** The ledger, which answers for what is staged. */
  port: LedgerPort;
  /** The stored movements shown, by id. */
  byId: ReadonlyMap<string, LedgerRow>;
  stage: StageState;
  onStage: (event: StageEvent) => void;
  /** Movements a finalized declaration cites, where the page knows them. */
  sealed: ReadonlySet<string>;
  /** The drawn rows' keys, new movements first, and the drawn columns. */
  drawnRows: readonly string[];
  drawnColumns: readonly ColumnId[];
  withYear: boolean;
  /** The register's own accounts, null while unread. */
  accounts: readonly OwnAccountChoice[] | null;
  /** The page's classify command, for a classification typed in a cell. */
  classify: (kind: "business" | "personal" | "mixed", ids: string[]) => void;
  /** Asks what a new movement's Business or Mixed needs. */
  askDraft: (kind: "business" | "mixed", key: string) => void;
  say: (text: string) => void;
  openReview: () => void;
  /** A new movement to focus once it is drawn. */
  focusDraft: string | null;
  onDraftFocused: () => void;
};

/**
 * Staged editing on the movements grid: the cells' editors and what each
 * draws while a change is staged, Delete, paste and fill, copy, undo and
 * redo, and the new movements at the top. Every change is staged, never
 * saved; the grid keeps drawing stored values, with the staged one beside.
 */
export function useMovementEditing(input: MovementEditingInput) {
  const {
    t,
    locale,
    grid,
    port,
    byId,
    stage,
    onStage,
    sealed,
    drawnRows,
    drawnColumns,
    withYear,
    say,
  } = input;
  const content = stage.content;
  const drafts = useMemo(
    () => new Map(content.drafts.map((draft) => [draft.key, draft])),
    [content.drafts],
  );
  const vocabulary = useVocabulary();
  const labels = useMemo(
    () => choiceLabels(t, input.accounts, vocabulary),
    [t, input.accounts, vocabulary],
  );
  const [refused, setRefused] = useState<ReadonlyMap<string, RefusedCell>>(
    () => new Map(),
  );
  const [paste, setPaste] = useState<{
    plan: PastePlan;
    singleWrites: number;
  } | null>(null);
  const [cost, setCost] = useState<{
    event: Extract<StageEvent, { type: "stage" }>;
    singleWrites: number;
    seconds: number;
    then?: () => void;
  } | null>(null);

  const subjectOf = useCallback(
    (key: string): EditSubject | undefined => {
      const draft = drafts.get(key);
      if (draft) return { kind: "draft", draft };
      const row = byId.get(key);
      return row
        ? {
            kind: "row",
            row,
            changes: content.rows[key],
            sealed: sealed.has(key),
          }
        : undefined;
    },
    [drafts, byId, content.rows, sealed],
  );

  // ---- Marks -----------------------------------------------------------------
  const mark = useCallback((cells: readonly RefusedCell[]) => {
    if (!cells.length) return;
    setRefused((current) => {
      const next = new Map(current);
      for (const cell of cells) next.set(cellKey(cell.key, cell.column), cell);
      return next;
    });
  }, []);
  const unmark = useCallback((keys: readonly [string, string][]) => {
    setRefused((current) => {
      if (!keys.some(([key, column]) => current.has(cellKey(key, column))))
        return current;
      const next = new Map(current);
      for (const [key, column] of keys) next.delete(cellKey(key, column));
      return next;
    });
  }, []);

  // What the ledger says about the staged cells as they stand, for what a cell
  // shows. While it is awaited a cell shows no mark rather than a guess.
  const checked = useStagedCheck(
    port,
    useMemo(() => stagedCheckRequest(content, byId), [content, byId]),
  );

  /** What an event would add in saves one at a time and new ids, as the ledger
   * answers for the work before and after it; null if it did not answer. */
  const weigh = useCallback(
    async (event: Extract<StageEvent, { type: "stage" }>) => {
      const next = reduceStage(stage, event).content;
      const [now, then] = await Promise.all([
        checkOnce(port, stagedCheckRequest(content, byId)),
        checkOnce(port, stagedCheckRequest(next, byId)),
      ]);
      if (!now || !then) return null;
      const before = planApply(content, { rows: byId, check: now }).summary;
      const after = planApply(next, { rows: byId, check: then }).summary;
      const newIdentity = [
        ...new Set(event.cells.map((cell) => cell.id)),
      ].filter(
        (id) => (then.rows.get(id)?.identity_fields.length ?? 0) > 0,
      ).length;
      return {
        singleWrites: after.oneAtATime - before.oneAtATime,
        seconds: after.seconds - before.seconds,
        newIdentity,
      };
    },
    [port, stage, content, byId],
  );

  /** Stages an event, asking first when it adds many saves one at a time. A
   * movement takes at most a classification and a correction, so a small event
   * cannot reach the warning and is staged at once; a larger one waits for the
   * ledger's answer and stays unstaged if there is none. */
  const stageChecked = useCallback(
    (event: Extract<StageEvent, { type: "stage" }>, then?: () => void) => {
      const movements = new Set(event.cells.map((cell) => cell.id)).size;
      if (movements * WRITES_PER_MOVEMENT <= COST_WARNING_WRITES) {
        onStage(event);
        then?.();
        return;
      }
      void weigh(event).then((weight) => {
        if (!weight) {
          say(t("desktop.ledger.apply.read_failed"));
          return;
        }
        if (weight.singleWrites > COST_WARNING_WRITES) {
          setCost({
            event,
            singleWrites: weight.singleWrites,
            seconds: weight.seconds,
            then,
          });
          return;
        }
        onStage(event);
        then?.();
      });
    },
    [weigh, onStage, say, t],
  );
  const applyDrafts = useCallback(
    (edits: readonly DraftEdit[]) => {
      for (const edit of edits)
        onStage({
          type: "edit_draft",
          key: edit.key,
          field: edit.field,
          value: edit.value,
        });
    },
    [onStage],
  );

  // ---- What a cell shows ---------------------------------------------------
  const cellText = useCallback(
    (column: ColumnId, value: string | null, share: string | null) => {
      if (value === null || value === "") return null;
      switch (EDIT_KINDS[column]) {
        case "amount":
        case "figure":
          return formatAmount(locale, value);
        case "percent":
          return formatPercent(locale, value, { unit: "fraction" });
        case "date":
          return formatDay(locale, value, { withYear });
        case "direction":
          return directionLabel(t, value);
        case "classification":
          return classificationText(t, locale, {
            business_classification: value,
            business_pct: share,
          });
        case "category":
          return categoryLabel(t, value);
        case "iva_category":
          return ivaCategoryLabel(t, value);
        case "irpf_category":
          return irpfCategoryLabel(t, value);
        default:
          return value;
      }
    },
    [locale, t, withYear],
  );

  const editing: ColumnEditing = useMemo(() => {
    const lockOf = (column: ColumnId, row: LedgerRow) => {
      const subject = subjectOf(row.transaction.transaction_id);
      return subject ? lockReason(column, subject) : null;
    };
    return {
      editor: (column) => {
        const kind = EDIT_KINDS[column];
        if (!kind) return undefined;
        return (row: LedgerRow, context: EditorContext) => {
          const subject = subjectOf(row.transaction.transaction_id);
          if (!subject || lockReason(column, subject)) return null;
          const { value } = effectiveValue(subject, column);
          const field =
            subject.kind === "draft"
              ? draftField(column)
              : columnField(column, subject.row);
          if (!field) return null;
          if (isTyped(kind))
            return (
              <TypedEditor
                context={context}
                kind={kind}
                field={field}
                value={
                  value === null
                    ? ""
                    : kind === "percent"
                      ? heldDecimal(percentOf(value) ?? value)
                      : kind === "amount" || kind === "figure"
                        ? heldDecimal(copyAmount(value))
                        : value
                }
                stored={value !== null && value !== ""}
                offers={CELL_OFFERS[column] ?? null}
                onFill={(picked) => {
                  // A new movement's empty party follows its description; a
                  // stored movement changes only the cell that was edited.
                  const party = picked.fills?.counterparty;
                  if (
                    subject.kind === "draft" &&
                    column === "description" &&
                    party &&
                    !subject.draft.fields.counterparty?.trim()
                  )
                    applyDrafts([
                      {
                        key: subject.draft.key,
                        field: "counterparty",
                        value: party,
                      },
                    ]);
                }}
              />
            );
          const direction =
            subject.kind === "draft"
              ? subject.draft.fields.direction
              : effectiveFacts(subject.row, subject.changes).direction;
          return (
            <ChoiceEditor
              context={context}
              kind={kind}
              value={value}
              direction={direction ?? null}
              accounts={input.accounts}
            />
          );
        };
      },
      readOnlyReason: (column) => {
        if (column === "select") return undefined;
        return (row: LedgerRow) => {
          const lock = lockOf(column, row);
          return lock ? lockText(t, lock) : undefined;
        };
      },
      decorate: (row, column, stored) => {
        const key = row.transaction.transaction_id;
        const draft = drafts.get(key);
        if (draft) return drawDraft(draft, column);
        const marked = refused.get(cellKey(key, column));
        const changes = content.rows[key];
        const staged =
          changes !== undefined ||
          content.actions.some((action) => actionRows(action).includes(key));
        if (column === "select")
          return (
            <>
              {stored()}
              {staged && (
                <UnsavedEdge label={t("desktop.ledger.edit.row_unsaved")} />
              )}
            </>
          );
        if (marked)
          return (
            <RefusedValue
              raw={marked.refusal.raw}
              reason={refusalText(t, marked.refusal)}
            />
          );
        const field = columnField(column, row);
        if (!field || !changes) return stored();
        const own = changes[field];
        const share =
          column === "classification" ? changes.business_pct : undefined;
        if (!own && !share) return stored();
        const before = effectiveFacts(row, undefined);
        const after = effectiveFacts(row, changes);
        const answer = checked.current?.rows.get(key);
        const identity = !!answer?.identity_fields.includes(field);
        const refusal = own
          ? answer?.routes.find((route) => route.field === field)?.refused
          : null;
        return (
          <StagedValue
            stored={cellText(
              column,
              before[field] ?? null,
              before.business_pct ?? null,
            )}
            staged={cellText(
              column,
              after[field] ?? null,
              after.business_pct ?? null,
            )}
            identity={identity}
            cannot={
              refusal ? t(`desktop.ledger.edit.held.${refusal}`) : undefined
            }
          />
        );
      },
      describeCell: (key, column) => {
        const marked = refused.get(cellKey(key, column));
        if (marked)
          return { invalid: true, text: refusalText(t, marked.refusal) };
        return undefined;
      },
      describeRow: (key) => {
        if (drafts.has(key)) return t("desktop.ledger.draft.describe");
        const changes = content.rows[key];
        return changes
          ? t("desktop.ledger.edit.row_changes", {
              count: Object.keys(changes).length,
            })
          : undefined;
      },
    };

    function drawDraft(draft: Draft, column: ColumnId): ReactNode {
      if (column === "select")
        return <UnsavedEdge label={t("desktop.ledger.draft.describe")} />;
      if (column === "status")
        return (
          <DraftStatus
            onRemove={() => onStage({ type: "remove_draft", key: draft.key })}
          />
        );
      const field = draftField(column);
      if (!field) return null;
      const marked = refused.get(cellKey(draft.key, column));
      if (marked)
        return (
          <RefusedValue
            raw={marked.refusal.raw}
            reason={refusalText(t, marked.refusal)}
          />
        );
      const value = draft.fields[field] ?? null;
      const currency = draft.fields.currency;
      const shown = cellText(column, value, draft.fields.business_pct ?? null);
      const text =
        column === "amount" && value && currency && currency !== "EUR"
          ? formatAmount(locale, value, { currency })
          : shown;
      return (
        <DraftValue text={text} required={DRAFT_REQUIRED.includes(field)} />
      );
    }
  }, [
    checked,
    subjectOf,
    applyDrafts,
    drafts,
    refused,
    content,
    t,
    locale,
    cellText,
    onStage,
    input.accounts,
  ]);

  // ---- Committing an edit --------------------------------------------------
  const pendingClears = useRef<{ key: string; column: ColumnId }[]>([]);
  const flushClears = useCallback(() => {
    const queued = pendingClears.current;
    pendingClears.current = [];
    const cells = [];
    const marks: RefusedCell[] = [];
    const cleared: [string, string][] = [];
    for (const { key, column } of queued) {
      const subject = subjectOf(key);
      if (!subject || lockReason(column, subject)) continue;
      const field =
        subject.kind === "draft"
          ? draftField(column)
          : columnField(column, subject.row);
      if (!field) continue;
      const { value } = effectiveValue(subject, column);
      if (value === null || value === "") continue;
      const refusal = clearRefusal(field);
      if (refusal) {
        marks.push({
          key,
          column,
          refusal: { ...refusal, raw: cellText(column, value, null) ?? "" },
        });
        continue;
      }
      cleared.push([key, column]);
      if (subject.kind === "draft")
        applyDrafts(draftEdits(key, draftField(column)!, null));
      else
        cells.push(
          ...rowCells(
            key,
            subject.row,
            columnField(column, subject.row)!,
            null,
          ),
        );
    }
    if (cells.length) onStage({ type: "stage", label: "clear", cells });
    unmark(cleared);
    if (marks.length) {
      mark(marks);
      say(
        t("desktop.ledger.edit.not_cleared", {
          count: marks.length,
          reason: refusalText(t, marks[0]!.refusal),
        }),
      );
    }
  }, [subjectOf, cellText, applyDrafts, onStage, unmark, mark, say, t]);

  const commitValue = (key: string, column: ColumnId, value: CellValue) => {
    const subject = subjectOf(key);
    if (!subject) return;
    unmark([[key, column]]);
    if (subject.kind === "draft") {
      const field = draftField(column);
      if (!field) return;
      if (
        field === "business_classification" &&
        carriesBusinessFigures(value.value) === true &&
        value.share === undefined
      ) {
        input.askDraft(
          classifyKindOf(value.value) as "business" | "mixed",
          key,
        );
        return;
      }
      applyDrafts(draftEdits(key, field, value));
      return;
    }
    const field = columnField(column, subject.row);
    if (!field) return;
    if (field === "business_classification" && value.share === undefined) {
      input.classify(classifyKindOf(value.value), [key]);
      return;
    }
    stageChecked({
      type: "stage",
      label: "set",
      cells: rowCells(key, subject.row, field, value),
    });
  };

  /** Stage a value the backend owns the refusal of, so the review names the
   * fact rather than reporting the cell as one nobody filled in. */
  const stageRefused = (
    key: string,
    column: ColumnId,
    refusal: EditRefusal,
  ) => {
    const subject = subjectOf(key);
    if (!subject) return;
    const field =
      subject.kind === "draft"
        ? draftField(column)
        : columnField(column, subject.row);
    if (!field || !backendOwnsRefusal(field, refusal)) return;
    const typed = refusal.raw.trim();
    if (subject.kind === "draft") {
      applyDrafts([{ key, field: field as DraftField, value: typed }]);
      return;
    }
    onStage({
      type: "stage",
      label: "set",
      cells: [
        {
          id: key,
          field: field as StageField,
          value: { kind: "set", value: typed },
          stored: storedFieldValue(subject.row, field as StageField),
        },
      ],
    });
  };

  const onCommit = (key: string, column: string, value: unknown) => {
    const id = column as ColumnId;
    const commit = value as EditCommit | null;
    if (commit === null || commit.kind === "clear") {
      pendingClears.current.push({ key, column: id });
      if (pendingClears.current.length === 1) queueMicrotask(flushClears);
      return;
    }
    if (commit.kind === "refused") {
      mark([{ key, column: id, refusal: commit.refusal }]);
      say(refusalText(t, commit.refusal));
      stageRefused(key, id, commit.refusal);
      return;
    }
    commitValue(key, id, commit.value);
  };

  // ---- Paste, fill and copy --------------------------------------------------
  const stagePaste = (plan: PastePlan) => {
    if (plan.stage.length)
      onStage({ type: "stage", label: "paste", cells: plan.stage });
    applyDrafts(plan.drafts);
    unmark(
      [
        ...plan.stage.map((cell) => cell.id),
        ...plan.drafts.map((d) => d.key),
      ].flatMap((key) =>
        plan.columns.map((column): [string, string] => [key, column]),
      ),
    );
    mark(plan.refused);
    say(
      plan.refused.length
        ? t("desktop.ledger.paste.done_refused", {
            count: plan.changes,
            refused: plan.refused.length,
          })
        : t("desktop.ledger.paste.done", { count: plan.changes }),
    );
  };
  const onPaste = (range: CellRange, text: string) => {
    const anchorKey = range.rows[0];
    const anchorColumn = range.columns[0] as ColumnId | undefined;
    if (!anchorKey || !anchorColumn) return;
    const plan = planPaste(
      text,
      { key: anchorKey, column: anchorColumn },
      { rows: range.rows, columns: range.columns as ColumnId[] },
      { rows: drawnRows, columns: drawnColumns },
      subjectOf,
      labels,
    );
    if ("kind" in plan) {
      say(t(`desktop.ledger.paste.refused_${plan.reason}`));
      return;
    }
    if (plan.needsPreview) {
      if (!plan.stage.length) {
        setPaste({ plan, singleWrites: 0 });
        return;
      }
      void weigh({ type: "stage", label: "paste", cells: plan.stage }).then(
        (weight) => {
          if (!weight) {
            say(t("desktop.ledger.apply.read_failed"));
            return;
          }
          setPaste({
            plan: { ...plan, newIdentity: weight.newIdentity },
            singleWrites: weight.singleWrites,
          });
        },
      );
      return;
    }
    stagePaste(plan);
  };
  const onFill = (range: CellRange) => {
    const plan = planFill(
      { rows: range.rows, columns: range.columns as ColumnId[] },
      subjectOf,
    );
    if (plan.kind === "too_short") {
      say(t("desktop.ledger.fill.too_short"));
      return;
    }
    const event = { type: "stage", label: "fill", cells: plan.stage } as const;
    const done = () => {
      applyDrafts(plan.drafts);
      say(
        plan.kept
          ? t("desktop.ledger.fill.done_kept", {
              count: plan.changes,
              kept: plan.kept,
            })
          : t("desktop.ledger.fill.done", { count: plan.changes }),
      );
    };
    if (plan.stage.length) stageChecked(event, done);
    else done();
  };
  const onCopy = (range: CellRange): string | null => {
    const copyLabels = labels;
    const lines = range.rows.map((key) => {
      const subject = subjectOf(key);
      return range.columns
        .map((column) =>
          tsvCell(
            subject ? copyCell(subject, column as ColumnId, copyLabels) : "",
          ),
        )
        .join("\t");
    });
    return lines.join("\n");
  };

  // ---- Reverting, undo and redo --------------------------------------------
  const revertCell = (key: string, column: ColumnId) => {
    if (refused.has(cellKey(key, column))) {
      unmark([[key, column]]);
      return;
    }
    const subject = subjectOf(key);
    if (!subject) return;
    if (subject.kind === "draft") {
      const field = draftField(column);
      if (field && subject.draft.fields[field] !== undefined)
        applyDrafts(draftEdits(key, field, null));
      return;
    }
    const field = columnField(column, subject.row);
    if (!field) return;
    onStage({ type: "revert_cell", id: key, field });
    if (field === "business_classification")
      onStage({ type: "revert_cell", id: key, field: "business_pct" });
    say(t("desktop.ledger.edit.reverted_cell", { field: fieldName(t, field) }));
  };
  const revertMovement = (key: string) => {
    if (drafts.has(key)) onStage({ type: "remove_draft", key });
    else onStage({ type: "revert_movement", id: key });
    setRefused((current) => {
      const next = new Map(
        [...current].filter(([found]) => !found.startsWith(`${key}\u0000`)),
      );
      return next.size === current.size ? current : next;
    });
    say(t("desktop.ledger.edit.reverted_movement"));
  };
  const undo = () => {
    const last = stage.undo[stage.undo.length - 1];
    if (!last) {
      say(
        stage.applied
          ? t("desktop.ledger.edit.undo_applied")
          : t("desktop.ledger.edit.undo_nothing"),
      );
      return;
    }
    onStage({ type: "undo" });
    // One field undone is named; several are the step's own name.
    const fields = changedFields(stage.content, last.content);
    say(
      t("desktop.ledger.edit.undone", {
        what:
          fields.length === 1
            ? fieldName(t, fields[0]!)
            : t(`desktop.ledger.edit.step.${last.label}`),
      }),
    );
  };
  const redo = () => {
    const next = stage.redo[stage.redo.length - 1];
    if (!next) return say(t("desktop.ledger.edit.redo_nothing"));
    onStage({ type: "redo" });
    say(
      t("desktop.ledger.edit.redone", {
        what: t(`desktop.ledger.edit.step.${next.label}`),
      }),
    );
  };

  const inField = (target: EventTarget) =>
    (target as HTMLElement).closest?.(
      "input, textarea, select, [contenteditable=true]",
    ) !== null;
  /** Revert cell, taken before the grid reads it as a typed character. A
   * layout that types something else on it is not the chord. */
  const onKeyDownCapture = (event: KeyboardEvent<HTMLElement>) => {
    if (
      chordMatches(REVERT_CELL_CHORD, event) &&
      /^z$/i.test(event.key) &&
      !inField(event.target)
    ) {
      event.preventDefault();
      event.stopPropagation();
      const at = grid.current?.activeCell();
      if (at?.key) revertCell(at.key, at.column as ColumnId);
    }
  };
  /** Undo, redo and review, wherever the section's keys reach. */
  const onKeyDown = (event: KeyboardEvent<HTMLElement>): boolean => {
    if (event.defaultPrevented || inField(event.target)) return false;
    if (chordMatches(UNDO_CHORD, event)) {
      undo();
      return true;
    }
    if (REDO_CHORDS.some((chord) => chordMatches(chord, event))) {
      redo();
      return true;
    }
    if (REVIEW_CHORDS.some((chord) => chordMatches(chord, event))) {
      input.openReview();
      return true;
    }
    return false;
  };

  // ---- New movements -------------------------------------------------------
  const draftRows = useMemo<GridRow<LedgerRow>[]>(
    () =>
      content.drafts.map((draft) => ({
        kind: "data",
        key: draft.key,
        data: draftRow(draft),
      })),
    [content.drafts],
  );
  const { focusDraft, onDraftFocused } = input;
  useEffect(() => {
    if (!focusDraft || !drafts.has(focusDraft)) return;
    if (!drawnRows.includes(focusDraft)) return;
    onDraftFocused();
    grid.current?.focusCell(focusDraft, "date");
  }, [focusDraft, drafts, drawnRows, grid, onDraftFocused]);

  // The grid opened these dialogs: closing one hands the focus back to its
  // active cell.
  const backToGrid = (event: Event) => {
    event.preventDefault();
    const at = grid.current?.activeCell();
    if (at?.key) grid.current?.focusCell(at.key, at.column);
  };
  const dialogs = (
    <>
      {paste && (
        <PasteDialog
          plan={paste.plan}
          columns={paste.plan.columns.map((column) =>
            t(`desktop.ledger.column.${column}`),
          )}
          singleWrites={paste.singleWrites}
          onCancel={() => setPaste(null)}
          onCloseAutoFocus={backToGrid}
          onPaste={() => {
            const plan = paste.plan;
            setPaste(null);
            stagePaste(plan);
          }}
        />
      )}
      {cost && (
        <CostDialog
          singleWrites={cost.singleWrites}
          seconds={cost.seconds}
          onCancel={() => setCost(null)}
          onCloseAutoFocus={backToGrid}
          onStage={() => {
            const found = cost;
            setCost(null);
            onStage(found.event);
            found.then?.();
          }}
        />
      )}
    </>
  );

  return {
    editing,
    draftRows,
    onCommit,
    onPaste,
    onFill,
    onCopy,
    onKeyDown,
    onKeyDownCapture,
    revertCell,
    revertMovement,
    stageChecked,
    undo,
    redo,
    dialogs,
    /** Whether the cell holds a staged change or a refusal to revert. */
    cellStaged: (key: string, column: string) => {
      if (refused.has(cellKey(key, column))) return true;
      const subject = subjectOf(key);
      if (!subject) return false;
      if (subject.kind === "draft") {
        const field = draftField(column as ColumnId);
        return field !== null && subject.draft.fields[field] !== undefined;
      }
      const field = columnField(column as ColumnId, subject.row);
      return field !== null && subject.changes?.[field] !== undefined;
    },
    refusedCount: refused.size,
    refusalOf: (key: string, column: string): EditRefusal | undefined =>
      refused.get(cellKey(key, column))?.refusal,
  };
}
