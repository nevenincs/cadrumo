import { useEffect, useId, useMemo, useState } from "react";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { TaxIdEditor } from "@/components/editors/TaxIdEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { Field, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { facts } from "@/shell/compose";
import type { LedgerHistoryTypedResult } from "../../../shell/ledgerMovementOperations";
import type { LedgerPort } from "../../../shell/ledger";
import {
  isIvaDerivableReason,
  READINESS_REASON_FIELD,
  lockedByDirection,
  takesClassification,
  takesM210Income,
} from "../../../shell/ledgerContract";
import {
  takesBusinessShare,
  useLedgerClassifications,
} from "../../../shell/ledgerClassifications";
import {
  CLASSIFICATION_OF,
  CLASSIFY_KINDS,
  type ClassifyKind,
  type ClassifySelection,
} from "../../../shell/ledgerCommands";
import {
  canonicalDecimal,
  parseFractionPercent,
} from "../../../shell/ledgerGrammar";
import {
  effectiveFacts,
  storedFieldValue,
  type StagedAction,
} from "../../../shell/ledgerStage";
import { useTextLimit } from "../../../shell/ledgerLimits";
import { useStrings } from "../../../shell/strings";
import { fieldName, refusalText } from "../editing/editingWords";
import {
  categoryLabel,
  classificationLabel,
  classificationText,
  ivaCategoryLabel,
  reasonDetail,
  vocabularyEmpty,
} from "../movements/movementWords";
import { InspectorField } from "./InspectorField";
import { ModelSuggestion } from "./ModelSuggestion";
import { decidedBy, eventName, ivaCategoryOptions } from "./inspectorWords";
import {
  fieldLock,
  servedChoiceField,
  stagedField,
  type FieldScope,
} from "./movementFields";
import { useLedgerRead } from "./useInspectorReads";
import {
  useFieldSuggestions,
  useServedChoices,
  useVocabulary,
} from "../suggestions/SuggestionsProvider";
import { formatTime } from "../../../shared/dateFormats";
import { formatPercent, heldDecimal } from "../../../shared/numbers";

/** The classify command of a stored classification; none for a disposition. */
const KIND_OF: Readonly<Record<string, ClassifyKind>> = Object.fromEntries(
  CLASSIFY_KINDS.map((kind) => [CLASSIFICATION_OF[kind], kind]),
);

/**
 * The inspector's Classify section: what the last check found missing and
 * where to fix it, the decision and who made it, the share, category and
 * tax fields, the model's suggestion, IVA worked out from a category, and
 * the rarer tax facts. Classifying goes through the page's one classify
 * command; every other change is staged.
 */
export function ClassifySection({
  scope,
  port,
  classify,
  issues,
  actions,
  rejectedBefore,
  history,
  onFocusField,
  say,
}: {
  scope: FieldScope;
  port: LedgerPort;
  classify: ClassifySelection | null;
  issues: readonly string[];
  /** The actions staged on this movement. */
  actions: readonly StagedAction[];
  rejectedBefore: boolean;
  history: LedgerHistoryTypedResult | null;
  onFocusField: (field: string) => void;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const vocabulary = useVocabulary();
  // Drawn again once the backend has served what each classification takes.
  useLedgerClassifications();
  const { row, changes, locale, onStage } = scope;
  const id = row.transaction.transaction_id;
  const effective = effectiveFacts(row, changes);
  const lock = fieldLock(scope, "business_classification");
  const refusesClass = CLASSIFY_KINDS.some(
    (kind) =>
      !takesClassification(effective.direction, CLASSIFICATION_OF[kind]),
  );
  const refusesDerive = lockedByDirection(effective.direction, "iva_category");
  const shareId = useId();
  const [share, setShare] = useState("");
  const [shareError, setShareError] = useState<string | null>(null);
  useEffect(() => {
    setShare(effective.business_pct ? heldDecimal(effective.business_pct) : "");
    setShareError(null);
  }, [id, effective.business_pct]);
  const [deriveCategory, setDeriveCategory] = useState<string | null>(null);

  const suggestion = actions.find(
    (action): action is Extract<StagedAction, { kind: "suggestion" }> =>
      action.kind === "suggestion",
  );
  const derivation = actions.find(
    (action): action is Extract<StagedAction, { kind: "iva_derive" }> =>
      action.kind === "iva_derive",
  );
  const field = (
    name: Parameters<typeof stagedField>[1],
    kind: Parameters<typeof stagedField>[2],
  ) => <InspectorField key={name} {...stagedField(scope, name, kind)} />;
  const deductionKinds = useServedChoices("deduction_fact_kind");

  const stageShare = () => {
    const parsed = parseFractionPercent(share);
    if (parsed.kind === "empty") {
      setShareError(t("desktop.ledger.inspector.share_required"));
      return;
    }
    if (parsed.kind === "refused") {
      setShareError(refusalText(t, parsed.refusal));
      return;
    }
    setShareError(null);
    onStage({
      type: "stage",
      label: "set",
      cells: [
        {
          id,
          field: "business_pct",
          value: { kind: "set", value: parsed.value },
          stored: storedFieldValue(row, "business_pct"),
        },
      ],
    });
  };

  const decided = KIND_OF[effective.business_classification ?? ""] ?? "";
  const stagedClass = changes?.business_classification;
  const earlier = (history?.events ?? []).filter(
    (event) =>
      event.event_type === "ledger.transaction.classified" ||
      event.event_type === "ledger.transaction.llm_suggestion.rejected" ||
      event.event_type === "ledger.transaction.reviewed_excluded" ||
      event.event_type === "ledger.transaction.allocated",
  );

  return (
    <div className="grid gap-3">
      {lock && <Alert icon={<Icon name="lock" />}>{lock}</Alert>}
      {issues.length > 0 && (
        <Alert
          tone="warning"
          icon={<Icon name="alert" />}
          className="ledger-missing"
        >
          <div className="grid gap-1.5">
            <span className="font-medium text-foreground">
              {t("desktop.ledger.inspector.missing")}
            </span>
            <ul className="grid gap-1 text-foreground">
              {issues.map((reason) => {
                const target = READINESS_REASON_FIELD[reason];
                const derive = isIvaDerivableReason(reason);
                return (
                  <li
                    key={reason}
                    className="flex flex-wrap items-center gap-2"
                  >
                    <span className="min-w-0 flex-1">
                      {reasonDetail(t, reason)}
                    </span>
                    {derive ? (
                      <Button
                        variant="outline"
                        size="xs"
                        disabled={lock !== null}
                        onClick={() => onFocusField("iva-derive")}
                      >
                        {t("desktop.ledger.inspector.fix.derive")}
                      </Button>
                    ) : target ? (
                      <Button
                        variant="outline"
                        size="xs"
                        disabled={lock !== null}
                        onClick={() => onFocusField(target)}
                      >
                        {t("desktop.ledger.inspector.fix.go")}
                      </Button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </div>
        </Alert>
      )}

      <div className="ledger-decision grid gap-2 rounded-md bg-accent p-2.5">
        <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span className="font-medium">
            {classificationText(t, locale, row.transaction)}
          </span>
          <span className="text-muted-foreground">
            {facts(t, [
              decidedBy(t, row.transaction.classified_by),
              row.transaction.classified_at &&
                formatTime(locale, row.transaction.classified_at),
            ])}
          </span>
        </p>
        <SegmentedControl
          aria-label={t("desktop.ledger.inspector.classification")}
          data-field="business_classification"
          value={decided}
          disabled={lock !== null || classify === null}
          onValueChange={(value) =>
            classify?.(value as ClassifyKind, { ids: [id] })
          }
        >
          {CLASSIFY_KINDS.map((kind) => (
            <SegmentedControlItem
              key={kind}
              value={kind}
              disabled={
                !takesClassification(
                  effective.direction,
                  CLASSIFICATION_OF[kind],
                )
              }
            >
              {classificationLabel(t, CLASSIFICATION_OF[kind])}
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
        {refusesClass && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.classify.transfers_only")}
          </p>
        )}
        {stagedClass && (
          <p className="ledger-unsaved flex items-center gap-1.5 text-sm">
            <span
              aria-hidden="true"
              className="h-4 border-l-2 border-dashed border-foreground"
            />
            {t("desktop.ledger.inspector.unsaved_classification", {
              classification: classificationText(t, locale, {
                business_classification:
                  effective.business_classification ?? "",
                business_pct: effective.business_pct ?? null,
              }),
            })}
          </p>
        )}
        {takesBusinessShare(effective.business_classification ?? "") ===
          true && (
          <div className="grid gap-1">
            <label htmlFor={shareId} className="text-sm">
              {t("desktop.ledger.inspector.share")}
            </label>
            <div className="w-24">
              <PercentEditor
                unit="fraction"
                id={shareId}
                data-field="business_pct"
                controlSize="sm"
                value={share}
                disabled={lock !== null}
                invalid={shareError !== null}
                describedBy={shareError ? `${shareId}-error` : undefined}
                onChange={(next) => {
                  setShare(next);
                  setShareError(null);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    stageShare();
                  }
                }}
                onBlur={() => {
                  const now = parseFractionPercent(share);
                  if (
                    now.kind !== "value" ||
                    canonicalDecimal(now.value) !==
                      canonicalDecimal(effective.business_pct ?? "")
                  )
                    if (share.trim() !== "") stageShare();
                }}
              />
            </div>
            {shareError && (
              <span id={`${shareId}-error`} className="text-sm">
                {shareError}
              </span>
            )}
          </div>
        )}
      </div>

      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5">
        {field("category_id", "category")}
        {field("iva_category", "iva_category")}
        {field("taxable_base", "figure")}
        {field("iva_rate", "percent")}
        {field("iva_amount", "figure")}
        {field("irpf_category", "irpf_category")}
        <dt className="pt-1 text-sm text-muted-foreground">
          {fieldName(t, "usage_ratio_id")}
        </dt>
        <dd className="px-1.5 py-1 text-sm">
          {effective.usage_ratio_id ??
            (takesBusinessShare(effective.business_classification ?? "") ===
            true
              ? t("desktop.ledger.inspector.ratio_missing")
              : t("desktop.ledger.inspector.ratio_not_needed"))}
        </dd>
      </dl>

      <ModelSuggestion
        port={port}
        row={row}
        staged={suggestion}
        onStage={onStage}
        locked={lock}
        locale={locale}
        rejectedBefore={rejectedBefore}
        say={say}
      />

      <div className="ledger-derive grid gap-2">
        <h4 className="text-sm font-medium">
          {t("desktop.ledger.inspector.derive.title")}
        </h4>
        {derivation ? (
          <Alert icon={<Icon name="tick" />} role="status">
            <span className="grid gap-1">
              {t("desktop.ledger.inspector.derive.staged", {
                category: ivaCategoryLabel(t, derivation.ivaCategory),
              })}
              <Button
                variant="link"
                size="xs"
                className="w-fit"
                onClick={() =>
                  onStage({ type: "drop_action", id: derivation.id })
                }
              >
                {t("desktop.ledger.inspector.drop")}
              </Button>
            </span>
          </Alert>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Combobox
              label={fieldName(t, "iva_category")}
              value={deriveCategory}
              options={ivaCategoryOptions(t, vocabulary)}
              emptyLabel={vocabularyEmpty(
                t,
                vocabulary,
                t("desktop.ledger.inspector.no_match"),
                vocabulary.ivaCategories.length,
              )}
              onCommit={setDeriveCategory}
            >
              <Button
                variant="outline"
                size="sm"
                data-field="iva-derive"
                disabled={lock !== null || refusesDerive}
                className="min-w-0 flex-1 justify-between"
              >
                <span className="truncate">
                  {deriveCategory
                    ? ivaCategoryLabel(t, deriveCategory)
                    : t("desktop.ledger.inspector.derive.choose")}
                </span>
                <Icon name="chevronDown" size="xs" />
              </Button>
            </Combobox>
            <Button
              variant="outline"
              size="sm"
              disabled={
                deriveCategory === null || lock !== null || refusesDerive
              }
              onClick={() => {
                if (!deriveCategory) return;
                onStage({
                  type: "stage_action",
                  action: {
                    id: `iva_derive:${id}`,
                    kind: "iva_derive",
                    transactionId: id,
                    ivaCategory: deriveCategory,
                  },
                });
                say(t("desktop.ledger.inspector.derive.staged_toast"));
              }}
            >
              {t("desktop.ledger.inspector.derive.stage")}
            </Button>
          </div>
        )}
      </div>

      <details className="ledger-more-tax grid gap-2">
        <summary className="cursor-pointer text-sm font-medium">
          {t("desktop.ledger.inspector.more_tax")}
        </summary>
        <dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5">
          {field("counterparty_country", "country")}
          {field("counterparty_identification_state", "country")}
          <InspectorField
            key="deduction_fact_kind"
            {...servedChoiceField(scope, "deduction_fact_kind", deductionKinds)}
          />
          {field("investment_asset_id", "token")}
        </dl>
        {/* Each movement's forms start from its own facts. */}
        <M210Form
          key={`m210:${id}`}
          scope={scope}
          actions={actions}
          lock={lock}
          say={say}
        />
        <AllocateForm
          key={`allocate:${id}`}
          scope={scope}
          port={port}
          actions={actions}
          lock={lock}
          say={say}
        />
      </details>

      {earlier.length > 0 && (
        <div className="grid gap-1">
          <h4 className="text-sm font-medium">
            {t("desktop.ledger.inspector.earlier")}
          </h4>
          <ul className="grid gap-1">
            {[...earlier].reverse().map((event) => (
              <li key={event.event_id} className="grid text-sm">
                <span>
                  {facts(t, [
                    eventName(t, event.event_type),
                    event.details.classification &&
                      classificationLabel(t, event.details.classification),
                  ])}
                </span>
                <span className="text-xs text-muted-foreground">
                  {facts(t, [
                    decidedBy(t, event.details.classified_by ?? event.actor),
                    formatTime(locale, event.occurred_at),
                  ])}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

const M210_FIELDS = [
  "tipo_renta_code",
  "gross_income_amount",
  "applicable_rate",
  "payer_mode",
  "payer_id",
  "asset_or_right_id",
] as const;
type M210Field = (typeof M210_FIELDS)[number];
const M210_LABELS: Record<M210Field, string> = {
  tipo_renta_code: "desktop.ledger.inspector.m210.tipo_renta_code",
  gross_income_amount: "desktop.ledger.inspector.m210.gross_income_amount",
  applicable_rate: "desktop.ledger.inspector.m210.applicable_rate",
  payer_mode: "desktop.ledger.inspector.m210.payer_mode",
  payer_id: "desktop.ledger.inspector.m210.payer_id",
  asset_or_right_id: "desktop.ledger.inspector.m210.asset_or_right_id",
};

const heldRate = (stored: string | null | undefined) =>
  stored ? heldDecimal(stored) : "";

type ServedChoices = readonly { value: string; label: string }[];

/** One served closed choice of the Modelo 210 form. Nothing chosen is a choice
 * too, since the form takes all its answers or none. A value the row already
 * holds stays on offer even where the list no longer has it. */
function M210Choice({
  entry,
  label,
  options,
}: {
  entry: {
    id: string;
    value: string;
    disabled: boolean;
    invalid: boolean;
    describedBy: string | undefined;
    onChange: (next: string) => void;
  };
  label: string;
  options: ServedChoices;
}) {
  const t = useStrings();
  const held = entry.value.trim();
  const listed = options.find((option) => option.value === held);
  return (
    <Combobox
      label={label}
      value={held}
      invalid={entry.invalid}
      describedBy={entry.describedBy}
      options={[
        { value: "", label: t("desktop.ledger.inspector.not_set") },
        ...(held && !listed ? [{ value: held, label: held }] : []),
        ...options,
      ]}
      emptyLabel={t("desktop.ledger.inspector.no_match")}
      onCommit={(chosen) => entry.onChange(chosen)}
    >
      <Button
        id={entry.id}
        variant="outline"
        disabled={entry.disabled}
        className="min-w-0 justify-between"
      >
        <span className="truncate">
          {listed?.label || held || t("desktop.ledger.inspector.not_set")}
        </span>
        <Icon name="chevronDown" size="xs" />
      </Button>
    </Combobox>
  );
}

/** The Modelo 210 facts of income a non-resident earns in Spain, sent with
 * the movement's single classification. */
function M210Form({
  scope,
  actions,
  lock,
  say,
}: {
  scope: FieldScope;
  actions: readonly StagedAction[];
  lock: string | null;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const formId = useId();
  const { row, onStage } = scope;
  const id = row.transaction.transaction_id;
  const stored = row.transaction.m210_income_classification;
  const staged = actions.find(
    (action): action is Extract<StagedAction, { kind: "m210" }> =>
      action.kind === "m210",
  );
  const initial = (): Record<M210Field, string> => ({
    tipo_renta_code:
      staged?.options.tipo_renta_code ?? stored?.official_tipo_renta_code ?? "",
    gross_income_amount:
      staged?.options.gross_income_amount ?? stored?.gross_income_amount ?? "",
    applicable_rate: heldRate(
      staged?.options.applicable_rate ?? stored?.applicable_rate,
    ),
    payer_mode: staged?.options.payer_mode ?? stored?.payer_mode ?? "",
    payer_id: staged?.options.payer_id ?? stored?.payer_id ?? "",
    asset_or_right_id:
      staged?.options.asset_or_right_id ?? stored?.asset_or_right_id ?? "",
  });
  const [values, setValues] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [rateError, setRateError] = useState<string | null>(null);
  const incoming = takesM210Income(row.transaction.direction);
  const offered = {
    payer_id: useFieldSuggestions("m210_payer"),
    asset_or_right_id: useFieldSuggestions("m210_asset"),
  };
  const choices: Partial<Record<M210Field, ServedChoices | null>> = {
    tipo_renta_code: useServedChoices("m210_tipo_renta", { withCode: true }),
    payer_mode: useServedChoices("m210_payer_mode"),
  };
  return (
    <form
      className="mt-2 grid gap-1.5"
      aria-labelledby={`${formId}-title`}
      onSubmit={(event) => {
        event.preventDefault();
        const code = values.tipo_renta_code.trim();
        if (!/^\d{2}$/.test(code)) {
          setError(t("desktop.ledger.inspector.m210.code_refused"));
          return;
        }
        const rate = parseFractionPercent(values.applicable_rate);
        if (rate.kind === "refused") {
          setError(null);
          setRateError(refusalText(t, rate.refusal));
          return;
        }
        const options: Record<string, string | null> = {};
        for (const name of M210_FIELDS) {
          const text = values[name].trim();
          options[name] = text === "" ? null : text;
        }
        options.applicable_rate = rate.kind === "value" ? rate.value : null;
        setError(null);
        setRateError(null);
        onStage({
          type: "stage_action",
          action: {
            id: `m210:${id}`,
            kind: "m210",
            transactionId: id,
            options,
          },
        });
        say(t("desktop.ledger.inspector.m210.staged"));
      }}
    >
      <h4 id={`${formId}-title`} className="text-sm font-medium">
        {t("desktop.ledger.inspector.m210.title")}
      </h4>
      {!incoming && (
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.inspector.m210.incoming_only")}
        </p>
      )}
      {M210_FIELDS.map((name) => {
        const entry = {
          id: `${formId}-${name}`,
          controlSize: "sm",
          value: values[name],
          disabled: lock !== null || !incoming,
          invalid:
            name === "applicable_rate"
              ? rateError !== null
              : error !== null && name === "tipo_renta_code",
          describedBy:
            name === "applicable_rate"
              ? rateError !== null
                ? `${formId}-rate-error`
                : undefined
              : error !== null && name === "tipo_renta_code"
                ? `${formId}-error`
                : undefined,
          onChange: (next: string) => {
            if (name === "applicable_rate") setRateError(null);
            setValues((held) => ({ ...held, [name]: next }));
          },
        } as const;
        return (
          <Field key={name} className="gap-0.5">
            <FieldLabel htmlFor={entry.id} className="font-normal">
              {t(M210_LABELS[name])}
            </FieldLabel>
            {choices[name] ? (
              <M210Choice
                entry={entry}
                label={t(M210_LABELS[name])}
                options={choices[name]}
              />
            ) : name === "gross_income_amount" ? (
              <MoneyEditor {...entry} />
            ) : name === "applicable_rate" ? (
              <PercentEditor unit="fraction" {...entry} />
            ) : name === "payer_id" ? (
              <TaxIdEditor {...entry} {...offered.payer_id} />
            ) : name === "asset_or_right_id" ? (
              <TextEditor {...entry} {...offered.asset_or_right_id} />
            ) : (
              <TextEditor {...entry} />
            )}
          </Field>
        );
      })}
      {error && (
        <p id={`${formId}-error`} className="text-sm">
          {error}
        </p>
      )}
      {rateError && (
        <p id={`${formId}-rate-error`} className="text-sm">
          {rateError}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          type="submit"
          variant="outline"
          size="sm"
          disabled={lock !== null || !incoming}
        >
          {t("desktop.ledger.inspector.m210.stage")}
        </Button>
        {staged && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onStage({ type: "drop_action", id: staged.id })}
          >
            {t("desktop.ledger.inspector.drop")}
          </Button>
        )}
      </div>
    </form>
  );
}

/** A business share set by allocation, with the usage ratio or prorrata
 * it is allocated by. */
function AllocateForm({
  scope,
  port,
  actions,
  lock,
  say,
}: {
  scope: FieldScope;
  port: LedgerPort;
  actions: readonly StagedAction[];
  lock: string | null;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const formId = useId();
  const ratioLimit = useTextLimit("usage_ratio_id");
  const { row, onStage } = scope;
  const id = row.transaction.transaction_id;
  const staged = actions.find(
    (action): action is Extract<StagedAction, { kind: "allocate" }> =>
      action.kind === "allocate",
  );
  const [share, setShare] = useState("");
  const [ratio, setRatio] = useState("");
  const [prorrata, setProrrata] = useState("");
  const [error, setError] = useState<string | null>(null);
  // The ratios configured for the movement's year, read when the field is
  // first entered. A ratio is named by its category, the row's own first.
  const [ratiosWanted, setRatiosWanted] = useState(false);
  const year = Number(row.transaction.date.slice(0, 4));
  const ratios = useLedgerRead(
    port,
    "ledger.ratios.list",
    { year },
    `ratios:${id}:${year}`,
    ratiosWanted,
  );
  const prorrataOffers = useFieldSuggestions("prorrata_reference", { year });
  const ownCategory = effectiveFacts(row, scope.changes).category_id;
  const ratioOptions = useMemo(() => {
    if (ratios?.kind !== "ready" || ratios.result.outcome !== "available")
      return null;
    const own = (category: string) => category === ownCategory;
    return [
      ...ratios.result.rows.filter((entry) => own(entry.category)),
      ...ratios.result.rows.filter((entry) => !own(entry.category)),
    ].map((entry) => ({
      value: entry.category,
      label: categoryLabel(t, entry.category),
      note: formatPercent(scope.locale, entry.ratio, { unit: "fraction" }),
      keywords: [entry.category],
    }));
  }, [ratios, ownCategory, t, scope.locale]);
  return (
    <form
      className="mt-2 grid gap-1.5"
      aria-labelledby={`${formId}-title`}
      onSubmit={(event) => {
        event.preventDefault();
        const parsed = parseFractionPercent(share);
        if (parsed.kind !== "value") {
          setError(
            parsed.kind === "refused"
              ? refusalText(t, parsed.refusal)
              : t("desktop.ledger.inspector.share_required"),
          );
          return;
        }
        setError(null);
        onStage({
          type: "stage_action",
          action: {
            id: `allocate:${id}`,
            kind: "allocate",
            transactionId: id,
            businessPct: parsed.value,
            categoryId: null,
            usageRatioId: ratio.trim() || null,
            prorrataReference: prorrata.trim() || null,
          },
        });
        say(t("desktop.ledger.inspector.allocate.staged"));
      }}
    >
      <h4 id={`${formId}-title`} className="text-sm font-medium">
        {t("desktop.ledger.inspector.allocate.title")}
      </h4>
      <Field className="gap-0.5">
        <FieldLabel htmlFor={`${formId}-share`} className="font-normal">
          {t("desktop.ledger.inspector.share")}
        </FieldLabel>
        <PercentEditor
          unit="fraction"
          id={`${formId}-share`}
          controlSize="sm"
          value={share}
          disabled={lock !== null}
          invalid={error !== null}
          describedBy={error ? `${formId}-error` : undefined}
          onChange={(next) => {
            setShare(next);
            setError(null);
          }}
        />
      </Field>
      <Field className="gap-0.5">
        <FieldLabel htmlFor={`${formId}-ratio`} className="font-normal">
          {fieldName(t, "usage_ratio_id")}
        </FieldLabel>
        <TextEditor
          id={`${formId}-ratio`}
          controlSize="sm"
          value={ratio}
          maxLength={ratioLimit ?? undefined}
          disabled={lock !== null}
          onChange={setRatio}
          suggestions={ratioOptions}
          onSuggestionsWanted={() => setRatiosWanted(true)}
        />
      </Field>
      <Field className="gap-0.5">
        <FieldLabel htmlFor={`${formId}-prorrata`} className="font-normal">
          {t("desktop.ledger.inspector.allocate.prorrata")}
        </FieldLabel>
        <TextEditor
          id={`${formId}-prorrata`}
          controlSize="sm"
          value={prorrata}
          disabled={lock !== null}
          onChange={setProrrata}
          opensEmpty
          {...prorrataOffers}
        />
      </Field>
      {error && (
        <p id={`${formId}-error`} className="text-sm">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          type="submit"
          variant="outline"
          size="sm"
          disabled={lock !== null}
        >
          {t("desktop.ledger.inspector.allocate.stage")}
        </Button>
        {staged && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onStage({ type: "drop_action", id: staged.id })}
          >
            {t("desktop.ledger.inspector.drop")}
          </Button>
        )}
      </div>
    </form>
  );
}
