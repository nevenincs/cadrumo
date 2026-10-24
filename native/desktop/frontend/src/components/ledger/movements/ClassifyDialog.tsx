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
import type { ClassifyKind } from "../../../shell/ledgerCommands";
import {
  SHARE_CATEGORY_FAMILIES,
  SPENDING_CATEGORY_FAMILIES,
} from "../../../shell/ledgerVocabulary";
import { useStrings } from "../../../shell/strings";
import { categoryLabel, familyLabel } from "./movementWords";

/**
 * What classifying as Business or Mixed asks for, in one step: a category
 * for the movements that take one, and a business share for Mixed. Income
 * takes no spending category, so a selection of income alone is never
 * asked for one, and Mixed offers only the categories a share applies to.
 * Nothing is saved: staging is the next step, and Escape leaves everything
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
          members.map((member) => ({
            value: member,
            label: categoryLabel(t, member),
            group: familyLabel(t, family),
          })),
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
  const submit = () => form.current?.requestSubmit();
  // Once what it asks for is filled in, Enter on the category stages
  // rather than opening the list again.
  const enterStages = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== "Enter" || !ready) return;
    event.preventDefault();
    submit();
  };
  const categoryLabelText = t("desktop.ledger.classify.category");
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
              {t(`desktop.ledger.classify.title_${kind}`, {
                count: movements,
              })}
            </DialogTitle>
            <DialogDescription>
              {[t("desktop.ledger.classify.not_saved"), ...notes].join(" · ")}
            </DialogDescription>
          </DialogHeader>
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
