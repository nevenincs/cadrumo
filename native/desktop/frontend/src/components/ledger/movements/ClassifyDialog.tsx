import { useId, useMemo, useState } from "react";
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
import { SPENDING_CATEGORY_FAMILIES } from "../../../shell/ledgerVocabulary";
import { useStrings } from "../../../shell/strings";
import { categoryLabel, familyLabel } from "./movementWords";

/**
 * What classifying as Business or Mixed asks for, in one step: a category
 * for Business, a business share for Mixed. Nothing is saved: staging is
 * the next step, and Escape leaves everything as it was.
 */
export function ClassifyDialog({
  kind,
  movements,
  skipped,
  partial,
  error,
  onStage,
  onCancel,
}: {
  /** Business or Mixed, or a category alone for movements that already
   * take one. */
  kind: Exclude<ClassifyKind, "personal"> | "category";
  /** How many movements it will stage a change on. */
  movements: number;
  /** How many named movements it leaves as they are. */
  skipped: number;
  partial: boolean;
  /** Why the share last given was refused. */
  error: string | null;
  onStage: (answer: { category?: string; share?: string }) => void;
  onCancel: () => void;
}) {
  const t = useStrings();
  const shareId = useId();
  const [category, setCategory] = useState<string | null>(null);
  const [share, setShare] = useState("");
  const options = useMemo<ComboboxOption[]>(
    () =>
      SPENDING_CATEGORY_FAMILIES.flatMap(([family, members]) =>
        members.map((member) => ({
          value: member,
          label: categoryLabel(t, member),
          group: familyLabel(t, family),
        })),
      ),
    [t],
  );
  const asksCategory = kind !== "mixed";
  const ready = asksCategory ? category !== null : share.trim() !== "";
  const notes = [
    skipped > 0 ? t("desktop.ledger.classify.skipped", { count: skipped }) : "",
    partial ? t("desktop.ledger.classify.partial") : "",
  ].filter(Boolean);
  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent
        className="ledger-classify"
        closeLabel={t("desktop.ledger.classify.cancel")}
      >
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!ready) return;
            onStage(asksCategory ? { category: category! } : { share });
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
          {asksCategory ? (
            <div className="grid gap-1.5">
              <span className="text-sm font-medium">
                {t("desktop.ledger.classify.category")}
              </span>
              <Combobox
                label={t("desktop.ledger.classify.category")}
                value={category}
                options={options}
                emptyLabel={t("desktop.ledger.classify.no_category_match")}
                placeholder={t("desktop.ledger.classify.search_category")}
                onCommit={(value) => setCategory(value)}
              >
                <Button
                  variant="outline"
                  className="ledger-classify-category justify-between"
                >
                  {category
                    ? categoryLabel(t, category)
                    : t("desktop.ledger.classify.choose_category")}
                  <Icon name="chevronDown" size="xs" />
                </Button>
              </Combobox>
            </div>
          ) : (
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
          <DialogFooter>
            <Button variant="ghost" onClick={onCancel}>
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
