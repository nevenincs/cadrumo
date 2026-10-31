import { useMemo, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { facts, factsGap } from "@/shell/compose";
import type {
  LedgerRuleApplyResult,
  LedgerRuleRow,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { categoryLabel, classificationLabel } from "../movements/movementWords";
import { formatTime } from "../../../shared/dateFormats";
import { CounterpartiesPane } from "./CounterpartiesPane";
import { DiagnosticsPane } from "./DiagnosticsPane";
import { RatiosPane } from "./RatiosPane";
import type { RuleDialogTarget } from "./RuleDialog";
import {
  CallLine,
  Panel,
  Reading,
  readLanding,
  SetupTable,
  SetupTabs,
  useSetupRead,
  useSetupWrite,
  type Column,
} from "./SetupParts";
import type { SetupProps } from "./setupProps";
import {
  patternWords,
  reorderWrites,
  ruleOrder,
  ruleStored,
  setupCall,
  type SetupCall,
} from "./setupModel";
import { ruleMatchText } from "./setupWords";

const AREAS = ["rules", "ratios", "counterparties", "diagnostics"] as const;
type Area = (typeof AREAS)[number];
/** The sub-areas of Setup › Rules. */
export type RulesArea = Area;

let stagedApplies = 0;

/**
 * Setup › Rules: the classification rules and their order, a dry run of
 * what they would classify and staging the run itself; the business-use
 * ratios by year; what the ledger answers for a counterparty; and how the
 * model has done.
 */
export function RulesSection(
  props: SetupProps & {
    onOpenRule(target: RuleDialogTarget): void;
    /** Changes when a rule was saved elsewhere, to read the list again. */
    rulesVersion: number;
    /** The sub-area it opens on, such as Business-use ratios from a Mixed
     * step that found none configured. */
    initialArea?: RulesArea;
  },
) {
  const t = useStrings();
  const [area, setArea] = useState<Area>(props.initialArea ?? "rules");
  return (
    <div className="ledger-setup-rules flex min-h-0 flex-1 flex-col">
      <SetupTabs<Area>
        label={t("desktop.ledger.rules.areas")}
        owner="ledger/rules"
        value={area}
        onValue={setArea}
        tabs={AREAS.map((value) => ({
          value,
          label: t(`desktop.ledger.rules.area.${value}`),
        }))}
      >
        {area === "rules" && <RulesPane {...props} />}
        {area === "ratios" && <RatiosPane {...props} />}
        {area === "counterparties" && <CounterpartiesPane {...props} />}
        {area === "diagnostics" && <DiagnosticsPane {...props} />}
      </SetupTabs>
    </div>
  );
}

function RulesPane({
  port,
  reader,
  locale,
  stage,
  onStage,
  onOpenRule,
  rulesVersion,
}: SetupProps & {
  onOpenRule(target: RuleDialogTarget): void;
  rulesVersion: number;
}) {
  const t = useStrings();
  const { read, reload } = useSetupRead(
    port,
    reader,
    "ledger.rule.list",
    {},
    `rules:${rulesVersion}`,
  );
  const rules = useMemo(
    () => (read?.kind === "done" ? ruleOrder(read.result.rules) : null),
    [read],
  );
  const moving = useSetupWrite(t("desktop.ledger.rules.title"));
  const [reaffirm, setReaffirm] = useState(false);
  const [preview, setPreview] =
    useState<SetupCall<LedgerRuleApplyResult> | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [stagedNote, setStagedNote] = useState<string | null>(null);
  const staged = stage.actions.filter((action) => action.kind === "rule_apply");

  const move = async (from: number, to: number) => {
    if (!rules) return;
    const writes = reorderWrites(rules, from, to);
    // The write in flight when one was not seen to settle: the earlier ones
    // settled, and the later ones were not sent.
    let sending: (typeof writes)[number] | null = null;
    await moving.run(
      async () => {
        let last: SetupCall<unknown> = { kind: "done", result: null };
        for (const write of writes) {
          sending = write;
          last = await setupCall(
            port,
            "ledger.rule.add",
            {
              description_pattern: write.rule.description_pattern,
              classification: write.rule.classification,
              category_id: write.rule.category_id,
              priority: write.priority,
            },
            true,
          );
          if (last.kind !== "done") break;
        }
        return last;
      },
      readLanding(port, "ledger.rule.list", {}, (result) => {
        const sent = sending;
        if (!sent) return "not_saved";
        return ruleStored(result.rules, {
          description_pattern: sent.rule.description_pattern,
          classification: sent.rule.classification,
          category_id: sent.rule.category_id,
          priority: sent.priority,
        })
          ? "saved"
          : "not_saved";
      }),
    );
    reload();
  };
  const runPreview = async () => {
    setPreviewing(true);
    setStagedNote(null);
    setPreview(
      await setupCall(
        port,
        "ledger.rule.apply",
        { reaffirm, dry_run: true },
        false,
      ),
    );
    setPreviewing(false);
  };
  const matched =
    preview?.kind === "done" ? (preview.result.would_match ?? []) : [];
  const stageRun = () => {
    stagedApplies += 1;
    onStage({
      type: "stage_action",
      action: {
        id: `rules-run-${stagedApplies}`,
        kind: "rule_apply",
        reaffirm,
        transactionIds: matched.map((match) => match.transaction_id),
      },
    });
    setStagedNote(
      t("desktop.ledger.rules.run_staged", { count: matched.length }),
    );
    setPreview(null);
  };

  const columns: Column<LedgerRuleRow>[] = [
    {
      key: "order",
      label: t("desktop.ledger.rules.column.order"),
      numeric: true,
      sort: (rule) => (rules ?? []).indexOf(rule) + 1,
      cell: (rule) => (rules ?? []).indexOf(rule) + 1,
    },
    {
      key: "rule",
      label: t("desktop.ledger.rules.column.rule"),
      sort: (rule) => ruleMatchText(t, rule.description_pattern),
      cell: (rule) => (
        <span className="flex flex-col gap-0.5">
          <span>{ruleMatchText(t, rule.description_pattern)}</span>
          {patternWords(rule.description_pattern) === null && (
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer">
                {t("desktop.ledger.rules.advanced")}
              </summary>
              <code className="font-mono">{rule.description_pattern}</code>
            </details>
          )}
        </span>
      ),
    },
    {
      key: "classification",
      label: t("desktop.ledger.rules.column.classification"),
      sort: (rule) => classificationLabel(t, rule.classification),
      cell: (rule) => classificationLabel(t, rule.classification),
    },
    {
      key: "category",
      label: t("desktop.ledger.rules.column.category"),
      sort: (rule) =>
        rule.category_id ? categoryLabel(t, rule.category_id) : null,
      cell: (rule) =>
        rule.category_id ? (
          categoryLabel(t, rule.category_id)
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "added",
      label: t("desktop.ledger.rules.column.added"),
      sort: (rule) => rule.created_at,
      cell: (rule) => formatTime(locale, rule.created_at),
    },
    {
      key: "actions",
      label: t("desktop.ledger.form.actions"),
      hidden: true,
      resizable: false,
      cell: (rule) => {
        const at = (rules ?? []).indexOf(rule);
        const name = ruleMatchText(t, rule.description_pattern);
        return (
          <span className="flex justify-end gap-0.5">
            <WriteHold>
              <IconButton
                size="sm"
                label={t("desktop.ledger.rules.move_up", { rule: name })}
                aria-disabled={at === 0 || moving.busy || undefined}
                onClick={() => at > 0 && !moving.busy && void move(at, at - 1)}
              >
                <Icon name="chevronUp" />
              </IconButton>
            </WriteHold>
            <WriteHold>
              <IconButton
                size="sm"
                label={t("desktop.ledger.rules.move_down", { rule: name })}
                aria-disabled={
                  at === (rules?.length ?? 0) - 1 || moving.busy || undefined
                }
                onClick={() =>
                  rules &&
                  at < rules.length - 1 &&
                  !moving.busy &&
                  void move(at, at + 1)
                }
              >
                <Icon name="chevronDown" />
              </IconButton>
            </WriteHold>
            <IconButton
              size="sm"
              label={t("desktop.ledger.rules.edit", { rule: name })}
              onClick={() => onOpenRule({ kind: "rule", rule })}
            >
              <Icon name="edit" />
            </IconButton>
          </span>
        );
      },
    },
  ];

  return (
    <>
      <Panel
        title={t("desktop.ledger.rules.title")}
        actions={
          <Button
            size="xs"
            variant="outline"
            className="ledger-rule-new"
            onClick={() => onOpenRule({ kind: "new" })}
          >
            <Icon name="plus" />
            {t("desktop.ledger.rules.new")}
          </Button>
        }
      >
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.rules.order_note")}
        </p>
        {read === null ? (
          <Reading label={t("desktop.ledger.form.reading")} />
        ) : read.kind !== "done" ? (
          <CallLine call={read} />
        ) : rules!.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.rules.empty")}
          </p>
        ) : (
          <SetupTable
            label={t("desktop.ledger.rules.title")}
            rows={rules!}
            rowKey={(rule) => rule.rule_id}
            columns={columns}
            className="ledger-rules-table"
          />
        )}
        <CallLine call={moving.last} onReread={reload} />
      </Panel>
      <Panel
        title={t("desktop.ledger.rules.run_title")}
        actions={
          <>
            <span className="flex items-center gap-2">
              <Switch
                id="ledger-rules-reaffirm"
                checked={reaffirm}
                onCheckedChange={(next) => {
                  setReaffirm(next);
                  setPreview(null);
                }}
              />
              <Label htmlFor="ledger-rules-reaffirm" className="text-sm">
                {t("desktop.ledger.rules.reaffirm")}
              </Label>
            </span>
            <Button
              size="xs"
              variant="outline"
              className="ledger-rules-preview"
              aria-disabled={previewing || undefined}
              onClick={() => !previewing && void runPreview()}
            >
              {previewing
                ? t("desktop.ledger.form.reading")
                : t("desktop.ledger.rules.preview")}
            </Button>
          </>
        }
      >
        {preview?.kind === "done" ? (
          <div className="ledger-rules-dry-run flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium tabular-nums">
                {t("desktop.ledger.rules.would_classify", {
                  count: matched.length,
                })}
              </span>
              <span className="flex-1" />
              <Button
                size="xs"
                className="ledger-rules-stage"
                aria-disabled={matched.length === 0 || undefined}
                onClick={() => matched.length > 0 && stageRun()}
              >
                {t("desktop.ledger.rules.stage_run")}
              </Button>
            </div>
            <ul className="flex flex-col gap-1 text-sm">
              {(rules ?? [])
                .map((rule) => ({
                  rule,
                  found: matched.filter(
                    (match) => match.matched_rule_id === rule.rule_id,
                  ),
                }))
                .filter(({ found }) => found.length > 0)
                .map(({ rule, found }) => (
                  <li key={rule.rule_id} className="flex flex-col">
                    <span>
                      {ruleMatchText(t, rule.description_pattern)} →{" "}
                      {classificationLabel(t, rule.classification)}
                      <span className="tabular-nums">
                        {factsGap(t)}
                        {found.length}
                      </span>
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {facts(
                        t,
                        found.slice(0, 4).map((match) => match.description),
                      )}
                      {found.length > 4 ? " …" : ""}
                    </span>
                  </li>
                ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.rules.run_note")}
          </p>
        )}
        <CallLine call={preview} />
        {(stagedNote || staged.length > 0) && (
          <Alert icon={<Icon name="pending" />} className="ledger-rules-staged">
            {stagedNote ??
              t("desktop.ledger.rules.run_staged", {
                count: staged.reduce(
                  (total, action) =>
                    total +
                    (action.kind === "rule_apply"
                      ? action.transactionIds.length
                      : 0),
                  0,
                ),
              })}
          </Alert>
        )}
      </Panel>
    </>
  );
}
