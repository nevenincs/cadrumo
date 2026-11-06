import { useId, useMemo, useState } from "react";
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
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import type { LedgerSplitCheckResult } from "../../../shell/ledgerMovementOperations";
import { DECIDED_CLASSIFICATIONS } from "../../../shell/ledgerContract";
import {
  keepsCategory,
  splitPartAdvisedCategory,
  takesBusinessShare,
  useLedgerClassifications,
} from "../../../shell/ledgerClassifications";
import {
  AMOUNT_RULE,
  parseDecimal,
  parseFractionPercent,
} from "../../../shell/ledgerGrammar";
import { useSplitCheck } from "../../../shell/ledgerSplitCheck";
import type {
  SplitPartClassification,
  StageEvent,
} from "../../../shell/ledgerStage";
import { useTextLimit } from "../../../shell/ledgerLimits";
import { useStrings } from "../../../shell/strings";
import { refusalText } from "../editing/editingWords";
import {
  categoryLabel,
  classificationLabel,
  vocabularyEmpty,
} from "../movements/movementWords";
import { categoryOptions } from "./inspectorWords";
import {
  useFieldSuggestions,
  useVocabulary,
} from "../suggestions/SuggestionsProvider";
import { formatAmount } from "../../../shared/numbers";

type Part = {
  amount: string;
  description: string;
  classification: "" | (typeof DECIDED_CLASSIFICATIONS)[number];
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
  port,
  row,
  locale,
  onStage,
  onClose,
  say,
}: {
  port: LedgerPort;
  row: LedgerRow;
  locale: string;
  onStage: (event: StageEvent) => void;
  onClose: () => void;
  say: (text: string) => void;
}) {
  const t = useStrings();
  // Drawn again once the backend has served what each classification takes.
  useLedgerClassifications();
  const mostParts = useTextLimit("split_parts");
  const longestDescription = useTextLimit("split_part_description");
  const reasonLimit = useTextLimit("event_payload_value");
  const reasonId = useId();
  const partId = useId();
  const tx = row.transaction;
  // A part's words: the movement's own first, then the ledger's.
  const described = useFieldSuggestions("description");
  const vocabulary = useVocabulary();
  const partWords = useMemo(
    () =>
      described.suggestions && [
        { value: tx.description, label: tx.description },
        ...described.suggestions.filter(
          (option) => option.value !== tx.description,
        ),
      ],
    [described.suggestions, tx.description],
  );
  const [parts, setParts] = useState<Part[]>(() => [
    blank(tx.description),
    blank(tx.description),
  ]);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const last = parts.length - 1;
  // The last part takes what the backend works out the others leave. An amount
  // goes as the served grammar reads it, or as typed for the backend to refuse.
  const asked = useMemo(
    () =>
      parts.map((part, at) => {
        if (at === parts.length - 1)
          return { amount: null, description: part.description };
        const parsed = parseDecimal(part.amount, AMOUNT_RULE);
        return {
          amount: parsed.kind === "value" ? parsed.value : part.amount,
          description: part.description,
        };
      }),
    [parts],
  );
  const check = useSplitCheck(port, tx.transaction_id, asked);
  const answer = check.kind === "answer" ? check.result : null;
  const remainder = answer?.remainder ?? null;
  const update = (at: number, patch: Partial<Part>) => {
    setProblem(null);
    setParts((held) =>
      held.map((part, index) => (index === at ? { ...part, ...patch } : part)),
    );
  };
  const problemText = (
    found: NonNullable<LedgerSplitCheckResult["problem"]>,
  ): string => {
    const part = (found.index ?? 0) + 1;
    switch (found.kind) {
      case "gone":
        return t("desktop.ledger.inspector.split.gone");
      case "not_active":
        return t("desktop.ledger.inspector.split.not_active");
      case "count":
        return t("desktop.ledger.inspector.split.count", {
          max: found.max ?? "",
        });
      case "amount":
        return t("desktop.ledger.inspector.split.amount", { part });
      case "description":
        return t("desktop.ledger.inspector.split.description_needed", { part });
      case "description_long":
        return t("desktop.ledger.inspector.split.description_long", {
          part,
          max: found.max ?? "",
        });
      case "sum":
        return t(
          found.over
            ? "desktop.ledger.inspector.split.over"
            : "desktop.ledger.inspector.split.under",
          { amount: formatAmount(locale, found.difference ?? "0") },
        );
    }
  };

  const stage = () => {
    if (!answer) return;
    if (answer.problem) {
      setProblem(problemText(answer.problem));
      return;
    }
    const classes: (SplitPartClassification | undefined)[] = [];
    for (const [at, part] of parts.entries()) {
      if (part.classification === "") {
        classes.push(undefined);
        continue;
      }
      let share: string | null = null;
      if (takesBusinessShare(part.classification) === true) {
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
      classes.push({
        classification: part.classification,
        ...(part.category && keepsCategory(part.classification) === true
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
        children: answer.children.map((child, at) => ({
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
                amount: formatAmount(locale, tx.amount, {
                  currency: tx.currency,
                }),
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
                  <div className="grid w-40 gap-0.5 text-sm">
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
                      maxLength={longestDescription ?? undefined}
                      value={part.description}
                      onChange={(description) => update(at, { description })}
                      suggestions={partWords}
                      onSuggestionsWanted={described.onSuggestionsWanted}
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
                      {DECIDED_CLASSIFICATIONS.map((value) => (
                        <option key={value} value={value}>
                          {classificationLabel(t, value)}
                        </option>
                      ))}
                    </NativeSelect>
                  </label>
                  {keepsCategory(part.classification) === true && (
                    <Combobox
                      label={t("desktop.ledger.inspector.split.part_category", {
                        part: at + 1,
                      })}
                      value={part.category}
                      options={categoryOptions(t, vocabulary)}
                      emptyLabel={vocabularyEmpty(
                        t,
                        vocabulary,
                        t("desktop.ledger.inspector.no_match"),
                        vocabulary.categories.length,
                      )}
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
                  {takesBusinessShare(part.classification) === true && (
                    <div className="grid w-fit gap-0.5 text-sm">
                      <Label
                        htmlFor={`${partId}-${at}-share`}
                        className="font-normal"
                      >
                        {t("desktop.ledger.inspector.share")}
                      </Label>
                      <div className="w-24">
                        <PercentEditor
                          unit="fraction"
                          id={`${partId}-${at}-share`}
                          controlSize="sm"
                          value={part.share}
                          onChange={(share) => update(at, { share })}
                        />
                      </div>
                    </div>
                  )}
                </div>
                {splitPartAdvisedCategory(part.classification) === true &&
                  !part.category && (
                    <p className="ledger-split-category-advice text-sm text-muted-foreground">
                      {t("desktop.ledger.inspector.split.category_advised", {
                        part: at + 1,
                      })}
                    </p>
                  )}
              </li>
            ))}
          </ol>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-fit"
            disabled={mostParts === null || parts.length >= mostParts}
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
              maxLength={reasonLimit ?? undefined}
              value={reason}
              onChange={setReason}
            />
          </div>
          {check.kind === "failed" && (
            <Alert
              tone="warning"
              role="alert"
              icon={<Icon name="unknown" />}
              className="ledger-split-check-failed"
            >
              <span>{t("desktop.ledger.inspector.split.check_failed")}</span>{" "}
              <Button type="button" variant="ghost" onClick={check.retry}>
                {t("desktop.ledger.inspector.split.check_retry")}
              </Button>
            </Alert>
          )}
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
            <Button type="submit" disabled={!answer}>
              {t("desktop.ledger.inspector.split.stage")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
