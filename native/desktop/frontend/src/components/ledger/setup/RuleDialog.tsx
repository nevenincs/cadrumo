import { useId, useMemo, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import type { RuleSeed } from "../../../shell/ledgerCommands";
import type { LedgerRuleRow } from "../../../shell/ledgerSetup";
import type { StageEvent } from "../../../shell/ledgerStage";
import { SPENDING_CATEGORY_FAMILIES } from "../../../shell/ledgerVocabulary";
import { useStrings } from "../../../shell/strings";
import { useWritePause, WriteHold } from "../WritePause";
import {
  categoryLabel,
  classificationLabel,
  familyLabel,
} from "../movements/movementWords";
import { CallLine, ChoiceField, TextField, useSetupRead } from "./SetupParts";
import {
  patternHits,
  patternMatcher,
  patternMatches,
  patternWords,
  priorityAt,
  ruleOrder,
  rulePrefill,
  setupCall,
  wordsPattern,
  type SetupCall,
} from "./setupModel";
import { ruleName } from "./setupWords";

/** What a rule decides: a classification for the business, or none. */
export const RULE_CLASSIFICATIONS = [
  "BUSINESS",
  "PERSONAL",
  "SKIPPED_BY_RULE",
] as const;

/** Where the dialog opens from: a selection or a group, a stored rule, or
 * nothing. */
export type RuleDialogTarget =
  | { kind: "seed"; seed: RuleSeed }
  | { kind: "rule"; rule: LedgerRuleRow }
  | { kind: "new" };

let stagedRuleApplies = 0;

/** What the dialog starts from: the stored rule, or what the chosen
 * movements share. */
function firstValues(
  target: RuleDialogTarget,
  rows: ReadonlyMap<string, LedgerRow>,
) {
  if (target.kind === "rule") {
    const words = patternWords(target.rule.description_pattern);
    return {
      words: words ?? "",
      expression: words === null ? target.rule.description_pattern : "",
      advanced: words === null,
      classification: target.rule.classification,
      category: target.rule.category_id ?? "",
    };
  }
  const prefill =
    target.kind === "seed"
      ? rulePrefill(target.seed, rows)
      : { words: "", classification: null, categoryId: null };
  return {
    words: prefill.words,
    expression: "",
    advanced: false,
    classification:
      prefill.classification &&
      (RULE_CLASSIFICATIONS as readonly string[]).includes(
        prefill.classification,
      )
        ? prefill.classification
        : "",
    category: prefill.categoryId ?? "",
  };
}

/**
 * Makes a rule, as a dialog over whatever is shown: it matches words in a
 * description, or an expression under Advanced, decides a classification
 * and a category, and runs at a place in the order. It says how many loaded
 * movements it would classify, and can stage running the rules on them.
 * Saving the rule is its own write; running the rules is staged like every
 * other change.
 */
export function RuleDialog({
  port,
  reader,
  target,
  rows,
  onStage,
  onSaved,
  onClose,
  onClosed,
}: {
  port: LedgerPort;
  reader: string | null;
  target: RuleDialogTarget;
  /** The movements loaded on the page, or null where none are. */
  rows: readonly LedgerRow[] | null;
  onStage(event: StageEvent): void;
  onSaved(rule: LedgerRuleRow): void;
  onClose(): void;
  /** Called as the dialog closes, to hand focus back to where it was
   * opened from. */
  onClosed?: () => void;
}) {
  const t = useStrings();
  const ids = useId();
  const byId = useMemo(
    () =>
      new Map((rows ?? []).map((row) => [row.transaction.transaction_id, row])),
    [rows],
  );
  const [start] = useState(() => firstValues(target, byId));
  const { read } = useSetupRead(port, reader, "ledger.rule.list", {}, "rules");
  const rules = read?.kind === "done" ? read.result.rules : null;
  const [words, setWords] = useState(start.words);
  const [expression, setExpression] = useState(start.expression);
  const [advanced, setAdvanced] = useState(start.advanced);
  const [classification, setClassification] = useState(start.classification);
  const [category, setCategory] = useState(start.category);
  const ordered = useMemo(
    () =>
      ruleOrder(
        (rules ?? []).filter(
          (rule) =>
            target.kind !== "rule" || rule.rule_id !== target.rule.rule_id,
        ),
      ),
    [rules, target],
  );
  const [chosen, setPosition] = useState<number | null>(null);
  // A stored rule keeps its place, a new one goes last, until moved.
  const position =
    chosen ??
    (target.kind === "rule"
      ? Math.max(
          0,
          ruleOrder(rules ?? []).findIndex(
            (rule) => rule.rule_id === target.rule.rule_id,
          ),
        )
      : ordered.length);
  const [classifyNow, setClassifyNow] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<SetupCall<unknown> | null>(null);

  const pattern = advanced ? expression.trim() : wordsPattern(words);
  const patternBroken = advanced && pattern !== "" && !patternMatcher(pattern);
  const hits = rows && pattern ? patternHits(pattern, rows) : null;
  const matches = rows && pattern ? patternMatches(pattern, rows) : null;
  const categories = useMemo<ComboboxOption[]>(
    () => [
      { value: "", label: t("desktop.ledger.rules.no_category") },
      ...SPENDING_CATEGORY_FAMILIES.flatMap(([family, members]) =>
        members.map((member) => ({
          value: member,
          label: categoryLabel(t, member),
          group: familyLabel(t, family),
        })),
      ),
    ],
    [t],
  );
  const priority = priorityAt(ordered, position);
  const changesRule =
    target.kind === "rule" &&
    (pattern !== target.rule.description_pattern ||
      classification !== target.rule.classification ||
      (category || null) !== target.rule.category_id);
  const takesCategory = classification === "BUSINESS";
  const { hold, held } = useWritePause();
  const ready =
    held === null &&
    rules !== null &&
    pattern !== "" &&
    !patternBroken &&
    classification !== "" &&
    priority !== null &&
    !saving;

  const save = async () => {
    if (!ready || priority === null) return;
    setSaving(true);
    const call = await setupCall(
      port,
      "ledger.rule.add",
      {
        description_pattern: pattern,
        classification,
        category_id: takesCategory && category ? category : null,
        priority,
      },
      true,
    );
    setSaving(false);
    setSaved(call);
    // Not seen to settle: every write waits for the page's re-read, and
    // this form never sends the same rule again on its own.
    if (call.kind === "unknown" || call.kind === "saved_unread")
      hold({
        what: t("desktop.ledger.rules.title"),
        outcome: call.kind,
        onSettled: () => setSaved(null),
      });
    if (
      call.kind !== "done" ||
      call.result.outcome !== "added" ||
      !call.result.rule
    )
      return;
    if (classifyNow && matches && matches.length > 0) {
      stagedRuleApplies += 1;
      onStage({
        type: "stage_action",
        action: {
          id: `rule-apply-${stagedRuleApplies}`,
          kind: "rule_apply",
          reaffirm: false,
          transactionIds: matches,
        },
      });
    }
    onSaved(call.result.rule);
  };

  const refusal = () => {
    if (saved?.kind !== "refused") return null;
    const code = (saved.detail as { validation_code?: string } | null)
      ?.validation_code;
    return code ? t(`desktop.ledger.rules.refusal.${code}`) : null;
  };
  const positionLabel = (at: number) =>
    at === 0
      ? t("desktop.ledger.rules.order_first")
      : t("desktop.ledger.rules.order_after", {
          rule: ruleName(t, ordered[at - 1]!),
        });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="ledger-rule-dialog w-dialog-lg"
        closeLabel={t("desktop.ledger.form.close")}
        aria-describedby={`${ids}-what`}
        onCloseAutoFocus={(event) => {
          if (!onClosed) return;
          event.preventDefault();
          onClosed();
        }}
      >
        <DialogHeader>
          <DialogTitle>
            {target.kind === "rule"
              ? t("desktop.ledger.rules.edit_title")
              : t("desktop.ledger.rules.new_title")}
          </DialogTitle>
          <DialogDescription id={`${ids}-what`}>
            {t("desktop.ledger.rules.what")}
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 gap-3">
          <div className="flex items-center gap-2">
            <Switch
              id={`${ids}-advanced`}
              checked={advanced}
              onCheckedChange={(next) => {
                setAdvanced(next);
                if (next && expression === "")
                  setExpression(wordsPattern(words));
              }}
            />
            <Label htmlFor={`${ids}-advanced`}>
              {t("desktop.ledger.rules.advanced")}
            </Label>
          </div>
          {advanced ? (
            <TextField
              label={t("desktop.ledger.rules.expression")}
              value={expression}
              onValue={setExpression}
              mono
              hint={t("desktop.ledger.rules.expression_hint")}
              error={
                patternBroken
                  ? t("desktop.ledger.rules.expression_unread")
                  : null
              }
              required
            />
          ) : (
            <TextField
              label={t("desktop.ledger.rules.words")}
              value={words}
              onValue={setWords}
              hint={t("desktop.ledger.rules.words_hint")}
              required
              autoFocus
            />
          )}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <ChoiceField
              label={t("desktop.ledger.rules.classification")}
              value={classification}
              onValue={setClassification}
              placeholder={t("desktop.ledger.form.choose")}
              options={RULE_CLASSIFICATIONS.map((value) => ({
                value,
                label: classificationLabel(t, value),
              }))}
              className="ledger-rule-classification"
            />
            <Field className="ledger-rule-category">
              <FieldLabel htmlFor={`${ids}-category`}>
                {t("desktop.ledger.rules.category")}
              </FieldLabel>
              <Combobox
                label={t("desktop.ledger.rules.category")}
                value={takesCategory ? category : ""}
                options={categories}
                emptyLabel={t("desktop.ledger.classify.no_category_match")}
                placeholder={t("desktop.ledger.classify.search_category")}
                onCommit={(value) => setCategory(value)}
              >
                <Button
                  id={`${ids}-category`}
                  type="button"
                  variant="outline"
                  disabled={!takesCategory}
                  className="justify-between"
                >
                  <span className="min-w-0 truncate">
                    {takesCategory && category
                      ? categoryLabel(t, category)
                      : t("desktop.ledger.rules.no_category")}
                  </span>
                  <Icon name="chevronDown" size="xs" />
                </Button>
              </Combobox>
            </Field>
          </div>
          <ChoiceField
            label={t("desktop.ledger.rules.order")}
            value={String(position)}
            onValue={(value) => setPosition(Number(value))}
            options={Array.from({ length: ordered.length + 1 }, (_, at) => ({
              value: String(at),
              label: positionLabel(at),
            }))}
            className="ledger-rule-order"
          />
          {priority === null && (
            <Alert tone="warning" icon={<Icon name="alert" />}>
              {t("desktop.ledger.rules.order_full")}
            </Alert>
          )}
          {changesRule && (
            <Alert icon={<Icon name="info" />}>
              {t("desktop.ledger.rules.adds_new")}
            </Alert>
          )}
          <div className="ledger-rule-matches flex flex-wrap items-center gap-3 rounded-md bg-accent px-3 py-2">
            <span className="tabular-nums" aria-live="polite">
              {matches === null || hits === null
                ? t("desktop.ledger.rules.matches_unknown")
                : t("desktop.ledger.rules.matches_split", {
                    count: hits.length,
                    pending: matches.length,
                  })}
            </span>
            <span className="flex items-center gap-2">
              <Checkbox
                id={`${ids}-now`}
                checked={classifyNow}
                disabled={!matches?.length}
                onChange={(event) => setClassifyNow(event.target.checked)}
              />
              <Label htmlFor={`${ids}-now`}>
                {t("desktop.ledger.rules.classify_now")}
              </Label>
            </span>
          </div>
          <CallLine call={saved} refusal={refusal} />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            {t("desktop.ledger.form.cancel")}
          </Button>
          <WriteHold>
            <Button
              aria-disabled={!ready || undefined}
              onClick={() => void save()}
              className="ledger-rule-save"
            >
              {saving
                ? t("desktop.ledger.form.saving")
                : t("desktop.ledger.rules.save")}
            </Button>
          </WriteHold>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
