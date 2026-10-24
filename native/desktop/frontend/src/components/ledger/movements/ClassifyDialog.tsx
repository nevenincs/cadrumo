import { useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
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
import type {
  ClassifyKind,
  RatioCoverage,
} from "../../../shell/ledgerCommands";
import {
  SHARE_CATEGORY_FAMILIES,
  SPENDING_CATEGORY_FAMILIES,
} from "../../../shell/ledgerVocabulary";
import { useStrings } from "../../../shell/strings";
import { categoryLabel, categoryOption } from "./movementWords";

/**
 * What classifying as Business or Mixed asks for, in one step: a category
 * for the movements that take one, and a business share for Mixed. Income
 * takes no spending category, so a selection of income alone is never
 * asked for one, and Mixed offers only the categories a share applies to.
 * Mixed says, for the category chosen, on how many movements it names the
 * configured usage ratio and on how many none is configured, with the way
 * to Business-use ratios. Nothing is saved: staging is the next step, and Escape leaves everything
 * as it was.
 */
export function ClassifyDialog({
  kind,
  movements,
  split,
  skipped,
  partial,
  error,
  initialShare = "",
  range,
  ratioOf,
  onOpenRatios,
  onStage,
  onCancel,
  onClosed,
}: {
  /** Business or Mixed, or a category alone for movements that already
   * take one. */
  kind: Exclude<ClassifyKind, "personal"> | "category";
  /** How many movements it will stage a change on. */
  movements: number;
  /** Of those, how many take a spending category and how many are income,
   * which takes none. */
  split: { expenses: number; income: number };
  /** How many named movements it leaves as they are. */
  skipped: number;
  partial: boolean;
  /** Why the share last given was refused. */
  error: string | null;
  /** A share typed beside the control that asked. */
  initialShare?: string;
  /** A cell range over other rows than the selection, which the person can
   * make the selection instead. */
  range?: { count: number; onSelect: () => void };
  /** For Mixed, how the category chosen stands against the configured
   * usage ratios of the movements' years. */
  ratioOf?: (category: string) => RatioCoverage;
  /** Opens Setup › Business-use ratios. */
  onOpenRatios?: () => void;
  onStage: (answer: { category?: string; share?: string }) => void;
  onCancel: () => void;
  /** Called as the dialog closes, to hand focus back. */
  onClosed?: () => void;
}) {
  const t = useStrings();
  const shareId = useId();
  const form = useRef<HTMLFormElement>(null);
  const [category, setCategory] = useState<string | null>(null);
  const [share, setShare] = useState(initialShare);
  const mixed = kind === "mixed";
  const options = useMemo<ComboboxOption[]>(
    () =>
      (mixed ? SHARE_CATEGORY_FAMILIES : SPENDING_CATEGORY_FAMILIES).flatMap(
        ([family, members]) =>
          members.map((member) => categoryOption(t, family, member)),
      ),
    [t, mixed],
  );
  const asksCategory = kind === "category" || split.expenses > 0;
  const asksShare = mixed;
  const ready =
    (!asksCategory || category !== null) && (!asksShare || share.trim() !== "");
  const notes = [
    skipped > 0 ? t("desktop.ledger.classify.skipped", { count: skipped }) : "",
    partial ? t("desktop.ledger.classify.partial") : "",
  ].filter(Boolean);
  const both = kind === "business" && split.expenses > 0 && split.income > 0;
  const submit = () => form.current?.requestSubmit();
  // Once what it asks for is filled in, Enter on the category stages
  // rather than opening the list again.
  const enterStages = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== "Enter" || !ready) return;
    event.preventDefault();
    submit();
  };
  const categoryLabelText =
    split.income > 0 && kind !== "category"
      ? t("desktop.ledger.classify.expense_category", {
          count: split.expenses,
        })
      : t("desktop.ledger.classify.category");
  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent
        className="ledger-classify"
        closeLabel={t("desktop.ledger.classify.cancel")}
        onCloseAutoFocus={(event) => {
          if (!onClosed) return;
          event.preventDefault();
          onClosed();
        }}
      >
        <form
          ref={form}
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!ready) return;
            onStage({
              ...(asksCategory && category ? { category } : {}),
              ...(asksShare ? { share } : {}),
            });
          }}
        >
          <DialogHeader>
            <DialogTitle>
              {both
                ? t("desktop.ledger.classify.title_business_split", {
                    expenses: split.expenses,
                    income: split.income,
                  })
                : t(`desktop.ledger.classify.title_${kind}`, {
                    count: movements,
                  })}
            </DialogTitle>
            <DialogDescription>
              {[t("desktop.ledger.classify.not_saved"), ...notes].join(" · ")}
            </DialogDescription>
          </DialogHeader>
          {range && (
            <p className="ledger-classify-range flex flex-wrap items-center gap-2 text-sm">
              <Icon name="alert" size="xs" className="text-warning" />
              {t("desktop.ledger.classify.range_differs", {
                selected: movements,
                range: range.count,
              })}
              <Button
                type="button"
                variant="outline"
                size="xs"
                className="ledger-classify-select-range"
                onClick={range.onSelect}
              >
                {t("desktop.ledger.classify.select_range")}
              </Button>
            </p>
          )}
          {asksShare && (
            <div className="grid gap-1.5">
              <label htmlFor={shareId} className="text-sm font-medium">
                {t("desktop.ledger.classify.share")}
              </label>
              <Input
                id={shareId}
                autoFocus
                inputMode="decimal"
                value={share}
                aria-invalid={error ? true : undefined}
                aria-describedby={`${shareId}-note`}
                onChange={(event) => setShare(event.target.value)}
              />
              <p
                id={`${shareId}-note`}
                className="flex items-center gap-1.5 text-sm text-muted-foreground"
              >
                {error && (
                  <Icon name="alert" size="xs" className="text-destructive" />
                )}
                {error ?? t("desktop.ledger.classify.share_hint")}
              </p>
            </div>
          )}
          {asksCategory && (
            <div className="grid gap-1.5">
              <span className="text-sm font-medium">{categoryLabelText}</span>
              <Combobox
                label={categoryLabelText}
                value={category}
                options={options}
                emptyLabel={t("desktop.ledger.classify.no_category_match")}
                placeholder={t("desktop.ledger.classify.search_category")}
                hint={
                  mixed
                    ? t("desktop.ledger.classify.share_categories")
                    : undefined
                }
                onCommit={(value) => setCategory(value)}
              >
                <Button
                  type="button"
                  variant="outline"
                  className="ledger-classify-category justify-between"
                  autoFocus={!asksShare}
                  onKeyDown={enterStages}
                >
                  {category
                    ? categoryLabel(t, category)
                    : t("desktop.ledger.classify.choose_category")}
                  <Icon name="chevronDown" size="xs" />
                </Button>
              </Combobox>
            </div>
          )}
          {mixed && category !== null && ratioOf && (
            <RatioLine
              coverage={ratioOf(category)}
              onOpenRatios={onOpenRatios}
            />
          )}
          {kind !== "category" && split.income > 0 && (
            <p className="ledger-classify-income text-sm text-muted-foreground">
              {t("desktop.ledger.classify.income_no_category", {
                count: split.income,
              })}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onCancel}>
              {t("desktop.ledger.classify.cancel")}
            </Button>
            <Button
              type="submit"
              aria-disabled={ready ? undefined : true}
              className="ledger-classify-stage"
            >
              {t("desktop.ledger.classify.stage", { count: movements })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Where Mixed names a usage ratio with the category, and where it cannot:
 * none configured for the movement's year, or not read. */
function RatioLine({
  coverage,
  onOpenRatios,
}: {
  coverage: RatioCoverage;
  onOpenRatios?: () => void;
}) {
  const t = useStrings();
  if (coverage.staged + coverage.missing + coverage.unread === 0) return null;
  return (
    <div className="ledger-classify-ratio grid gap-1 text-sm">
      {coverage.staged > 0 && (
        <p className="ledger-classify-ratio-staged text-muted-foreground">
          {t("desktop.ledger.classify.ratio_staged", {
            count: coverage.staged,
          })}
        </p>
      )}
      {coverage.missing > 0 && (
        <p className="ledger-classify-ratio-missing flex flex-wrap items-center gap-2">
          <Icon name="alert" size="xs" className="text-warning" />
          {t("desktop.ledger.classify.ratio_missing", {
            count: coverage.missing,
          })}
          {onOpenRatios && (
            <Button
              type="button"
              variant="link"
              size="xs"
              className="ledger-classify-open-ratios"
              onClick={onOpenRatios}
            >
              {t("desktop.ledger.ratios.title")}
            </Button>
          )}
        </p>
      )}
      {coverage.unread > 0 && (
        <p className="ledger-classify-ratio-unread flex items-center gap-2 text-muted-foreground">
          <Icon name="unknown" size="xs" />
          {t("desktop.ledger.classify.ratio_unread")}
        </p>
      )}
    </div>
  );
}
