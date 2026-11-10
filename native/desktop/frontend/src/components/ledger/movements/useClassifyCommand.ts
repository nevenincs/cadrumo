import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import type { DataGridHandle } from "@/components/ui/dataGridTypes";
import { facts } from "@/shell/compose";
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import {
  CLASSIFICATION_OF,
  categorySplit,
  classifyAsksCategory,
  classifyAvailability,
  classifyCells,
  clearCategoryCells,
  type ClassifyKind,
  type ClassifyScope,
  type ConfiguredRatios,
} from "../../../shell/ledgerCommands";
import { isUndecided } from "../../../shell/ledgerContract";
import {
  checkOnce,
  stagedCheckRequest,
  type StagedCheck,
} from "../../../shell/ledgerStagedCheck";
import {
  effectiveFacts,
  type StageEvent,
  type StageState,
} from "../../../shell/ledgerStage";
import type { Translate } from "../../../shell/strings";
import { typedPoints } from "../editing/editingModel";
import { blockText, categoryLabel, classificationLabel } from "./movementWords";

/** Above this many movements classified otherwise, Personal, which asks
 * nothing else, asks once before it changes them. */
const OVERWRITE_ASK = 5;

/** A classification dialog asked for, and what it would act on. */
export type Asking = {
  /** The ledger's answer the asking was made from, where it needed one. */
  check?: StagedCheck;
  kind: ClassifyKind | "category";
  /** Of `ids`, how many are classified otherwise now. */
  overwritten?: number;
  ids: string[];
  skipped: number;
  partial: boolean;
  error: string | null;
  /** Of `ids`, those that take a spending category and the income. */
  split: { expenses: number; income: number };
  /** A share typed beside the control that asked. */
  share?: string;
  /** The rows a cell range covers, where they are not the selection. */
  range?: string[];
  /** A new movement's classification, filled in rather than staged. */
  draft?: string;
};

/**
 * The page's one classify command and the category command beside it: what
 * they act on, what they ask in a dialog, and what they stage. Business asks
 * for a category only where a movement takes one, so income alone is staged
 * at once; Mixed asks for its share and, where a movement takes one, a
 * category a share applies to.
 */
export function useClassifyCommand({
  t,
  port,
  byId,
  stage,
  ratios,
  partial,
  selected,
  hiddenSelected,
  grid,
  stageChecked,
  say,
}: {
  t: Translate;
  port: LedgerPort;
  byId: ReadonlyMap<string, LedgerRow>;
  stage: StageState;
  /** The business-use ratios configured for the window's years. */
  ratios: ConfiguredRatios;
  /** The window is read only in part. */
  partial: boolean;
  /** The selected movements the window holds. */
  selected: ReadonlySet<string>;
  /** How many of `selected` the grid does not draw. */
  hiddenSelected: number;
  grid: RefObject<DataGridHandle | null>;
  /** Stages a classify event, asking first where it costs many saves. */
  stageChecked: (
    event: Extract<StageEvent, { type: "stage" }>,
    then?: () => void,
  ) => void;
  say: (text: string) => void;
}) {
  const [asking, setAsking] = useState<Asking | null>(null);

  // A new movement's Business or Mixed asks the ledger whether it takes a
  // category; an answer for a stage since changed, or after the section
  // went, is dropped.
  const draftCheckVersion = useRef(0);
  const currentStage = useRef(stage.content);
  currentStage.current = stage.content;
  useEffect(
    () => () => {
      draftCheckVersion.current++;
    },
    [],
  );
  async function askDraftClassification(
    kind: "business" | "mixed",
    key: string,
  ) {
    const content = stage.content;
    const version = ++draftCheckVersion.current;
    const check = await checkOnce(port, stagedCheckRequest(content, byId));
    if (
      version !== draftCheckVersion.current ||
      currentStage.current !== content
    )
      return;
    const answer = check?.drafts.get(key);
    if (typeof answer?.takes_expense_category !== "boolean") {
      say(t("desktop.ledger.apply.read_failed"));
      return;
    }
    setAsking({
      kind,
      ids: [],
      skipped: 0,
      partial: false,
      error: null,
      split: answer.takes_expense_category
        ? { expenses: 1, income: 0 }
        : { expenses: 0, income: 1 },
      draft: key,
    });
  }

  const selectedTarget = useMemo(
    () => ({ ids: [...selected], hidden: hiddenSelected, partial }),
    [selected, hiddenSelected, partial],
  );
  const classifyTarget = (scope?: ClassifyScope) =>
    scope?.ids ? { ids: scope.ids, hidden: 0, partial } : selectedTarget;

  /** Of `ids`, how many classifying as `kind` would overwrite what a person
   * or a rule decided, stored or staged; advice before the change. */
  const overwrittenBy = (kind: ClassifyKind, ids: readonly string[]) => {
    const target = CLASSIFICATION_OF[kind];
    return ids.filter((id) => {
      const row = byId.get(id);
      if (!row) return false;
      const now = effectiveFacts(
        row,
        stage.content.rows[id],
      ).business_classification;
      return !!now && !isUndecided(now) && now !== target;
    }).length;
  };

  /** The ledger's answer about `ids` as they would be saved, and `category`. */
  const askCheck = (ids: readonly string[], category?: string) =>
    checkOnce(
      port,
      stagedCheckRequest(stage.content, byId, {
        ids,
        categories: category ? [category] : [],
      }),
    );

  async function stageClassified(
    kind: ClassifyKind,
    ids: readonly string[],
    answer: { category?: string; share?: string },
  ): Promise<string | null> {
    const overwritten = overwrittenBy(kind, ids);
    // A classification that carries no business figures names no category,
    // so it has nothing to ask.
    const asks = classifyAsksCategory(kind);
    const check = asks ? await askCheck(ids, answer.category) : null;
    if (asks && !check) return t("desktop.ledger.apply.read_failed");
    const outcome = classifyCells(
      { kind, ids, ...answer, ratios, check },
      byId,
    );
    if (outcome.kind === "refused")
      return t("desktop.ledger.classify.share_refused", {
        raw: typedPoints(outcome.refusal.raw),
      });
    if (outcome.kind === "needs") return null;
    const classification = classificationLabel(t, CLASSIFICATION_OF[kind]);
    const detail = facts(t, [
      answer.share ? `${answer.share.trim().replace(/\s*%$/, "")}%` : "",
      answer.category && check && categorySplit(ids, byId, check).expenses > 0
        ? categoryLabel(t, answer.category)
        : "",
    ]);
    const said = facts(t, [
      detail
        ? t("desktop.ledger.classify.staged_detail", {
            classification,
            detail,
            count: outcome.movements,
          })
        : t("desktop.ledger.classify.staged", {
            classification,
            count: outcome.movements,
          }),
      overwritten > 0
        ? t("desktop.ledger.classify.overwritten", { count: overwritten })
        : "",
    ]);
    stageChecked(outcome.event, () => say(said));
    return null;
  }

  /** The page's one classify command: every control calls it. What the
   * control already asked for is not asked again. */
  async function classifySelection(kind: ClassifyKind, scope?: ClassifyScope) {
    const availability = classifyAvailability(
      kind,
      classifyTarget(scope),
      byId,
    );
    if (availability.kind === "blocked") {
      say(blockText(t, availability.block));
      return;
    }
    if (!classifyAsksCategory(kind)) {
      // It asks nothing, so over many movements classified otherwise it asks
      // once before it changes them.
      const overwritten = overwrittenBy(kind, availability.ids);
      if (overwritten > OVERWRITE_ASK && !scope?.answer)
        setAsking({
          kind,
          ids: availability.ids,
          skipped: availability.skipped,
          partial: availability.partial,
          split: { expenses: 0, income: 0 },
          error: null,
          overwritten,
        });
      else await stageClassified(kind, availability.ids, {});
      return;
    }
    const answer = scope?.answer ?? {};
    const check = await askCheck(availability.ids, answer.category);
    if (!check) {
      say(t("desktop.ledger.apply.read_failed"));
      return;
    }
    const split = categorySplit(availability.ids, byId, check);
    const outcome = classifyCells(
      { kind, ids: availability.ids, ...answer, ratios, check },
      byId,
    );
    // What the control already asked for is not asked again, and nothing
    // is asked of income alone.
    if (outcome.kind === "staged") {
      const error = await stageClassified(kind, availability.ids, answer);
      if (error) say(error);
      return;
    }
    // A cell range over other rows than the selection is said, with the
    // way to act on the range instead.
    const drawn = scope?.ids ? null : (grid.current?.cellRange() ?? null);
    const ranged = drawn ? drawn.rows.filter((id) => byId.has(id)) : [];
    const differs =
      ranged.length > 1 &&
      (ranged.length !== selected.size ||
        ranged.some((id) => !selected.has(id)));
    setAsking({
      kind,
      ids: availability.ids,
      skipped: availability.skipped,
      partial: availability.partial,
      overwritten: overwrittenBy(kind, availability.ids),
      split,
      check,
      error:
        outcome.kind === "refused"
          ? t("desktop.ledger.classify.share_refused", {
              raw: typedPoints(outcome.refusal.raw),
            })
          : null,
      ...(answer.share ? { share: answer.share } : {}),
      ...(differs ? { range: ranged } : {}),
    });
  }
  const availabilityOf = (kind: ClassifyKind) =>
    classifyAvailability(kind, classifyTarget(), byId);

  /** Asks a spending category for those of `ids` that take one. */
  async function askCategory(ids: string[]) {
    const named = ids.filter((id) => byId.has(id));
    const check = named.length > 0 ? await askCheck(named) : null;
    if (named.length > 0 && !check) {
      say(t("desktop.ledger.apply.read_failed"));
      return;
    }
    const takes = named.filter((id) => check?.rows.get(id)?.category_askable);
    if (!check || takes.length === 0) {
      say(t("desktop.ledger.classify.category_needs_classification"));
      return;
    }
    setAsking({
      kind: "category",
      ids: takes,
      skipped: ids.length - takes.length,
      partial,
      error: null,
      split: categorySplit(takes, byId, check),
    });
  }

  /** Stages the removal of the spending category from those of `ids` that
   * hold one; the others are named in the message, never given one. */
  async function clearCategory(ids: string[]) {
    const named = ids.filter((id) => byId.has(id));
    const check = named.length > 0 ? await askCheck(named) : null;
    if (named.length > 0 && !check) {
      say(t("desktop.ledger.apply.read_failed"));
      return;
    }
    if (!check || !named.some((id) => check.rows.get(id)?.category_settable)) {
      say(t("desktop.ledger.classify.category_needs_classification"));
      return;
    }
    const outcome = clearCategoryCells(named, byId, check);
    if (outcome.kind === "nothing") {
      say(t("desktop.ledger.classify.nothing_to_clear"));
      return;
    }
    stageChecked(outcome.event, () =>
      say(
        facts(t, [
          t("desktop.ledger.classify.cleared_category", {
            count: outcome.movements,
          }),
          outcome.skipped > 0
            ? t("desktop.ledger.classify.skipped", { count: outcome.skipped })
            : "",
        ]),
      ),
    );
  }

  return {
    asking,
    setAsking,
    askDraftClassification,
    classifyTarget,
    askCheck,
    stageClassified,
    classifySelection,
    availabilityOf,
    askCategory,
    clearCategory,
  };
}

/** The classify command as the section holds it. */
export type ClassifyCommand = ReturnType<typeof useClassifyCommand>;
