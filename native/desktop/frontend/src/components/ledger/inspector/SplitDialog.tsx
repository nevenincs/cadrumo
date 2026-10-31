import { useId, useState } from "react";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import type { LedgerRow } from "../../../shell/ledger";
import { parseFractionPercent } from "../../../shell/ledgerGrammar";
import type {
  SplitPartClassification,
  StageEvent,
} from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { refusalText } from "../editing/editingWords";
import { categoryLabel, classificationLabel } from "../movements/movementWords";
import {
  SPLIT_PARTS_MAX,
  checkSplit,
  splitRemainder,
  type SplitProblem,
} from "./inspectorModel";
import { categoryOptions } from "./inspectorWords";
import { formatAmount } from "../../../shared/numbers";

type Part = {
  amount: string;
  description: string;
  classification: "" | "BUSINESS" | "PERSONAL" | "MIXED";
  category: string | null;
  share: string;
};
const blank = (description: string): Part => ({
  amount: "",
  description,
  classification: "",
  category: null,
  share: "",
});

/**
 * Splits a movement into parts whose amounts add up to its own. The last
 * part takes what the others leave. Each part may be classified here; that
 * classification is staged to run once the split has made the part. The
 * split itself is staged, not saved.
 */
export function SplitDialog({
  row,
  locale,
  onStage,
  onClose,
  say,
}: {
  row: LedgerRow;
  locale: string;
  onStage: (event: StageEvent) => void;
  onClose: () => void;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const reasonId = useId();
  const partId = useId();
  const tx = row.transaction;
  const [parts, setParts] = useState<Part[]>(() => [
    blank(tx.description),
    blank(tx.description),
  ]);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const last = parts.length - 1;
  const remainder = splitRemainder(
    tx.amount,
    parts.slice(0, last).map((part) => part.amount),
  );
  const amounts = parts.map((part, at) =>
    at === last ? (remainder ?? "") : part.amount,
  );
  const update = (at: number, patch: Partial<Part>) => {
    setProblem(null);
    setParts((held) =>
      held.map((part, index) => (index === at ? { ...part, ...patch } : part)),
    );
  };
  const problemText = (found: SplitProblem): string => {
    switch (found.kind) {
      case "count":
        return t("desktop.ledger.inspector.split.count", {
          max: SPLIT_PARTS_MAX,
        });
      case "amount":
        return t("desktop.ledger.inspector.split.amount", {
          part: found.index + 1,
        });
      case "description":
        return t("desktop.ledger.inspector.split.description_needed", {
          part: found.index + 1,
        });
      case "duplicate":
        return t("desktop.ledger.inspector.split.duplicate", {
          part: found.index + 1,
        });
      case "sum":
        return found.over
          ? t("desktop.ledger.inspector.split.over", {
              amount: formatAmount(locale, found.difference),
            })
          : t("desktop.ledger.inspector.split.under", {
              amount: formatAmount(locale, found.difference),
            });
    }
  };

  const stage = () => {
    const checked = checkSplit(
      tx.amount,
      parts.map((part, at) => ({
        amount: amounts[at]!,
        description: part.description,
      })),
    );
    if (!checked.ok) {
      setProblem(problemText(checked.problem));
      return;
    }
    const classes: (SplitPartClassification | undefined)[] = [];
    for (const [at, part] of parts.entries()) {
      if (part.classification === "") {
        classes.push(undefined);
        continue;
      }
      let share: string | null = null;
      if (part.classification === "MIXED") {
        const parsed = parseFractionPercent(part.share);
        if (parsed.kind !== "value") {
          setProblem(
            parsed.kind === "refused"
              ? refusalText(t, parsed.refusal)
              : t("desktop.ledger.inspector.split.share_needed", {
                  part: at + 1,
                }),
          );
          return;
        }
        share = parsed.value;
      }
      if (part.classification === "BUSINESS" && part.category === null) {
        setProblem(
          t("desktop.ledger.inspector.split.category_needed", { part: at + 1 }),
        );
        return;
      }
      classes.push({
        classification: part.classification,
        ...(part.category && part.classification !== "PERSONAL"
          ? { category_id: part.category }
          : {}),
        ...(share ? { business_pct: share } : {}),
      });
    }
    onStage({
      type: "stage_action",
      action: {
        id: `split:${tx.transaction_id}`,
        kind: "split",
        transactionId: tx.transaction_id,
        children: checked.children.map((child, at) => ({
          ...child,
          ...(classes[at] ? { classify: classes[at] } : {}),
        })),
        reason: reason.trim(),
      },
    });
    say(t("desktop.ledger.inspector.split.staged", { count: parts.length }));
    onClose();
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="ledger-split w-dialog-lg"
        closeLabel={t("desktop.ledger.inspector.cancel")}
      >
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            stage();
          }}
        >
          <DialogHeader>
            <DialogTitle>
              {t("desktop.ledger.inspector.split.title")}
            </DialogTitle>
            <DialogDescription>
              {t("desktop.ledger.inspector.split.description", {
                amount: formatAmount(locale, tx.amount),
                currency: tx.currency,
              })}
            </DialogDescription>
          </DialogHeader>
          <Alert icon={<Icon name="info" />}>
            {t("desktop.ledger.inspector.split.mixed_hint")}
          </Alert>
          <ol className="grid gap-3">
            {parts.map((part, at) => (
              <li key={at} className="ledger-split-part grid gap-1.5">
                <div className="flex items-end gap-2">
                  <div className="grid w-28 gap-0.5 text-sm">
                    <Label
                      htmlFor={`${partId}-${at}-amount`}
                      className="font-normal"
                    >
                      {t("desktop.ledger.inspector.split.part_amount", {
                        part: at + 1,
                      })}
                    </Label>
                    {at === last ? (
                      <output
                        id={`${partId}-${at}-amount`}
                        className="ledger-split-remainder flex h-control-sm items-center tabular-nums"
                      >
                        {remainder === null
                          ? t("desktop.ledger.inspector.split.remainder")
                          : formatAmount(locale, remainder)}
                      </output>
                    ) : (
                      <MoneyEditor
                        id={`${partId}-${at}-amount`}
                        controlSize="sm"
                        className="ledger-split-amount"
                        autoFocus={at === 0}
                        value={part.amount}
                        onChange={(amount) => update(at, { amount })}
                      />
                    )}
                  </div>
                  <div className="grid min-w-0 flex-1 gap-0.5 text-sm">
                    <Label
                      htmlFor={`${partId}-${at}-description`}
                      className="font-normal"
                    >
                      {t("desktop.ledger.inspector.split.part_description", {
                        part: at + 1,
                      })}
                    </Label>
                    <TextEditor
                      id={`${partId}-${at}-description`}
                      controlSize="sm"
                      className="ledger-split-description"
                      maxLength={4096}
                      value={part.description}
                      onChange={(description) => update(at, { description })}
                    />
                  </div>
                  <IconButton
                    label={t("desktop.ledger.inspector.split.remove_part", {
                      part: at + 1,
                    })}
                    size="sm"
                    disabled={parts.length <= 2}
                    onClick={() => {
                      setProblem(null);
                      setParts((held) =>
                        held.filter((_, index) => index !== at),
                      );
                    }}
                  >
                    <Icon name="close" />
                  </IconButton>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <label className="grid gap-0.5 text-sm">
                    <span className="text-muted-foreground">
                      {t("desktop.ledger.inspector.split.part_classification", {
                        part: at + 1,
                      })}
                    </span>
                    <NativeSelect
                      controlSize="sm"
                      value={part.classification}
                      onChange={(event) =>
                        update(at, {
                          classification: event.target
                            .value as Part["classification"],
                        })
                      }
                    >
                      <option value="">
                        {t("desktop.ledger.inspector.split.unclassified")}
                      </option>
                      {(["BUSINESS", "PERSONAL", "MIXED"] as const).map(
                        (value) => (
                          <option key={value} value={value}>
                            {classificationLabel(t, value)}
                          </option>
                        ),
                      )}
                    </NativeSelect>
                  </label>
                  {(part.classification === "BUSINESS" ||
                    part.classification === "MIXED") && (
                    <Combobox
                      label={t("desktop.ledger.inspector.split.part_category", {
                        part: at + 1,
                      })}
                      value={part.category}
                      options={categoryOptions(t)}
                      emptyLabel={t("desktop.ledger.inspector.no_match")}
                      onCommit={(chosen) => update(at, { category: chosen })}
                    >
                      <Button variant="outline" size="sm">
                        {part.category
                          ? categoryLabel(t, part.category)
                          : t("desktop.ledger.inspector.split.choose_category")}
                        <Icon name="chevronDown" size="xs" />
                      </Button>
                    </Combobox>
                  )}
                  {part.classification === "MIXED" && (
                    <div className="grid w-24 gap-0.5 text-sm">
                      <Label
                        htmlFor={`${partId}-${at}-share`}
                        className="font-normal"
                      >
                        {t("desktop.ledger.inspector.share")}
                      </Label>
                      <PercentEditor
                        unit="fraction"
                        id={`${partId}-${at}-share`}
                        controlSize="sm"
                        value={part.share}
                        onChange={(share) => update(at, { share })}
                      />
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-fit"
            disabled={parts.length >= SPLIT_PARTS_MAX}
            onClick={() => {
              setProblem(null);
              setParts((held) => [
                ...held.slice(0, -1),
                { ...held[held.length - 1]!, amount: remainder ?? "" },
                blank(tx.description),
              ]);
            }}
          >
            <Icon name="plus" />
            {t("desktop.ledger.inspector.split.add_part")}
          </Button>
          <div className="grid gap-1">
            <label htmlFor={reasonId} className="text-sm">
              {t("desktop.ledger.inspector.reason_optional")}
            </label>
            <TextEditor
              id={reasonId}
              maxLength={500}
              value={reason}
              onChange={setReason}
            />
          </div>
          {problem && (
            <p role="alert" className="flex items-center gap-1.5 text-sm">
              <Icon name="alert" size="xs" className="text-destructive" />
              {problem}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>
              {t("desktop.ledger.inspector.cancel")}
            </Button>
            <Button type="submit">
              {t("desktop.ledger.inspector.split.stage")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
