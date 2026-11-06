import type { LedgerRow } from "../../../shell/ledger";
import {
  CLASSIFICATION_OF,
  categoryCells,
  ratioCoverage,
  type ConfiguredRatios,
} from "../../../shell/ledgerCommands";
import { parsePercent } from "../../../shell/ledgerGrammar";
import type { DraftField, StageEvent } from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { typedPoints } from "../editing/editingModel";
import { ClassifyDialog } from "./ClassifyDialog";
import { categoryLabel } from "./movementWords";
import type { Asking, ClassifyCommand } from "./useClassifyCommand";

/**
 * The dialog the classify command asked for, and what its answer stages: a
 * new movement's classification is filled in, a category is staged on the
 * movements that take it, and a classification goes back through the
 * command.
 */
export function MovementClassifyDialog({
  asking,
  command,
  byId,
  ratios,
  onOpenRatios,
  onStage,
  onSelect,
  say,
  backToGrid,
}: {
  asking: Asking;
  command: ClassifyCommand;
  byId: ReadonlyMap<string, LedgerRow>;
  ratios: ConfiguredRatios;
  onOpenRatios?: () => void;
  onStage: (event: StageEvent) => void;
  /** Selects the movements of a cell range the dialog acts on instead. */
  onSelect: (ids: string[]) => void;
  say: (text: string) => void;
  /** Focus goes back to the grid's active cell as the dialog closes. */
  backToGrid: () => void;
}) {
  const t = useStrings();
  const { setAsking } = command;
  return (
    <ClassifyDialog
      key={asking.ids.join(" ")}
      kind={asking.kind}
      ratioOf={
        asking.kind === "mixed" && asking.check
          ? (category) =>
              ratioCoverage(asking.ids, byId, category, ratios, asking.check!)
          : undefined
      }
      onOpenRatios={onOpenRatios}
      movements={asking.draft ? 1 : asking.ids.length}
      split={asking.split}
      {...(asking.share ? { initialShare: asking.share } : {})}
      {...(asking.range
        ? {
            range: {
              count: asking.range.length,
              onSelect: () => {
                const ids = asking.range!;
                onSelect(ids);
                const kind = asking.kind;
                if (kind === "category") command.askCategory(ids);
                else command.classifySelection(kind, { ids });
              },
            },
          }
        : {})}
      onClosed={asking.draft ? undefined : backToGrid}
      skipped={asking.skipped}
      partial={asking.partial}
      error={asking.error}
      overwritten={asking.overwritten ?? 0}
      onCancel={() => setAsking(null)}
      onStage={(answer) => {
        if (asking.draft) {
          // A new movement's classification is filled in, not staged
          // over a stored one: Business with its category, Mixed with
          // its share.
          const key = asking.draft;
          const share =
            answer.share === undefined ? null : parsePercent(answer.share);
          if (share && share.kind !== "value") {
            setAsking({
              ...asking,
              error: t("desktop.ledger.classify.share_refused", {
                raw: typedPoints(answer.share ?? ""),
              }),
            });
            return;
          }
          const edit = (field: DraftField, value: string | null) =>
            onStage({ type: "edit_draft", key, field, value });
          edit(
            "business_classification",
            CLASSIFICATION_OF[asking.kind === "mixed" ? "mixed" : "business"],
          );
          if (answer.category) edit("category_id", answer.category);
          edit("business_pct", share?.kind === "value" ? share.value : null);
          setAsking(null);
          return;
        }
        if (asking.kind === "category") {
          const category = answer.category ?? "";
          void command.askCheck(asking.ids, category).then((check) => {
            if (!check) {
              setAsking({
                ...asking,
                error: t("desktop.ledger.apply.read_failed"),
              });
              return;
            }
            const outcome = categoryCells(asking.ids, category, byId, check);
            if (outcome.kind === "staged") {
              onStage(outcome.event);
              say(
                t("desktop.ledger.classify.staged_category", {
                  category: categoryLabel(t, category),
                  count: outcome.movements,
                }),
              );
            }
            setAsking(null);
          });
          return;
        }
        void command
          .stageClassified(asking.kind, asking.ids, answer)
          .then((error) => {
            if (error) setAsking({ ...asking, error });
            else setAsking(null);
          });
      }}
    />
  );
}
