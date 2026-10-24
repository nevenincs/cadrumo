import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/components/ui/cn";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon, type IconName } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import type {
  CatalogueInvoice,
  LedgerRow,
  OutputLanguage,
} from "../../../shell/ledger";
import type { StepOutcome, StepReport } from "../../../shell/ledgerApply";
import {
  classifyCells,
  takesExpenseCategory,
} from "../../../shell/ledgerCommands";
import { parsePercent } from "../../../shell/ledgerGrammar";
import {
  planApply,
  type LedgerPlan,
  type PlanBlocker,
  type PlanStep,
} from "../../../shell/ledgerPlan";
import {
  actionRows,
  effectiveFacts,
  storedFieldValue,
  type DraftField,
  type StageEvent,
  type StageField,
  type StagedAction,
  type StagedContent,
} from "../../../shell/ledgerStage";
import { SPENDING_CATEGORY_FAMILIES } from "../../../shell/ledgerVocabulary";
import { useStrings, type Translate } from "../../../shell/strings";
import {
  categoryLabel,
  classificationText,
  familyLabel,
  ivaCategoryLabel,
  percentText,
} from "../movements/movementWords";
import {
  changeGroups,
  heldUnits,
  linkMismatches,
  linksReady,
  outcomeTally,
  type AskedConflict,
  type LinkTicks,
  type LinkMismatch,
  type StageTally,
} from "./editingModel";
import { fieldName, valueText } from "./editingWords";
import type { useLedgerApply } from "./useLedgerApply";
import { useWritePause } from "../WritePause";
import { WindowedList } from "./WindowedList";

type Apply = ReturnType<typeof useLedgerApply>;

const minutesOf = (seconds: number) => Math.max(1, Math.round(seconds / 60));

/** The outcomes worst first: the result is titled by the first it holds. */
const WORST: readonly StepOutcome["kind"][] = [
  "unknown",
  "saved_unread",
  "refused",
  "not_sent",
];
/** Outcomes that saved: the result lists only the rest. */
const SAVED = new Set<StepOutcome["kind"]>(["applied", "settled"]);

/** A movement as the review names it. */
function titleOf(
  t: Translate,
  rows: ReadonlyMap<string, LedgerRow>,
  id: string,
): string {
  return (
    rows.get(id)?.transaction.description ??
    t("desktop.ledger.apply.gone_movement")
  );
}

/** The plan in plain words: "92 together · 40 one by one (about 2 min) ·
 * 2 new · 3 held". */
function planLine(t: Translate, plan: LedgerPlan, held: number): string {
  const summary = plan.summary;
  const actions = Object.values(summary.actions).reduce(
    (total, count) => total + (count ?? 0),
    0,
  );
  const single = summary.singleClassifications + summary.corrections + actions;
  return [
    summary.together
      ? t("desktop.ledger.apply.together", { count: summary.together })
      : "",
    single
      ? summary.seconds > 60
        ? t("desktop.ledger.apply.one_by_one", {
            count: single,
            minutes: minutesOf(summary.seconds),
          })
        : t("desktop.ledger.apply.one_by_one_quick", { count: single })
      : "",
    summary.newMovements
      ? t("desktop.ledger.apply.new", { count: summary.newMovements })
      : "",
    held ? t("desktop.ledger.apply.held", { count: held }) : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

// ---- Actions in words -------------------------------------------------------

/** An action as the review and the tray name it, in plain words. */
export function actionText(
  t: Translate,
  locale: string,
  action: StagedAction,
): string {
  switch (action.kind) {
    case "iva_derive":
      return t("desktop.ledger.apply.action.iva_derive", {
        category: ivaCategoryLabel(t, action.ivaCategory),
      });
    case "allocate":
      return t("desktop.ledger.apply.action.allocate", {
        share: percentText(locale || "en", action.businessPct),
      });
    case "attach_file":
      return t("desktop.ledger.apply.action.attach_file", {
        name: action.name,
      });
    case "rule_apply":
      return t("desktop.ledger.apply.action.rule_apply", {
        count: action.transactionIds.length,
      });
    default:
      return t(`desktop.ledger.apply.action.${action.kind}`);
  }
}

/** An action's lines in the review: a split adds each part, with the
 * classification it is given once the split has made it. */
function actionLines(
  t: Translate,
  locale: string,
  action: StagedAction,
): string[] {
  const lines = [actionText(t, locale, action)];
  if (action.kind === "split")
    for (const child of action.children)
      lines.push(
        [
          valueText(t, locale, "amount", child.amount),
          child.description,
          child.classify
            ? classificationText(t, {
                business_classification: child.classify.classification,
                business_pct: child.classify.business_pct ?? null,
              })
            : "",
          child.classify?.category_id
            ? categoryLabel(t, child.classify.category_id)
            : "",
        ]
          .filter(Boolean)
          .join(" · "),
      );
  return lines;
}

/** Rule applies, which act on movements anywhere in the ledger: each says
 * how many its dry run named, and lists them when opened. */
function RuleApplies({
  actions,
  rows,
  onDrop,
}: {
  actions: Extract<StagedAction, { kind: "rule_apply" }>[];
  rows: ReadonlyMap<string, LedgerRow>;
  onDrop: (id: string) => void;
}) {
  const t = useStrings();
  if (!actions.length) return null;
  return (
    <section className="ledger-rule-applies grid gap-2">
      {actions.map((action) => (
        <details
          key={action.id}
          data-action="rule_apply"
          className="rounded-md border border-border px-3 py-2"
        >
          <summary className="flex cursor-pointer items-center gap-2">
            <Icon name="filter" size="xs" className="text-muted-foreground" />
            <span className="flex-1 font-medium">
              {actionText(t, "", action)}
            </span>
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={t("desktop.ledger.apply.drop", {
                movement: actionText(t, "", action),
              })}
              onClick={(event) => {
                event.preventDefault();
                onDrop(action.id);
              }}
            >
              <Icon name="close" size="xs" />
            </Button>
          </summary>
          <ul className="mt-2 grid gap-0.5 text-sm text-muted-foreground">
            {action.transactionIds.map((id) => (
              <li key={id}>
                {rows.get(id)?.transaction.description ?? id.slice(0, 12)}
              </li>
            ))}
          </ul>
        </details>
      ))}
    </section>
  );
}

/** The staged movements that would end Business or Mixed with a spending
 * category on pure income, which no expense reads: the product's own
 * missing-category rule, from the other side. */
function incomeWithCategory(
  content: StagedContent,
  rows: ReadonlyMap<string, LedgerRow>,
): string[] {
  return Object.entries(content.rows).flatMap(([id, changes]) => {
    const row = rows.get(id);
    if (!row) return [];
    const after = effectiveFacts(row, changes);
    const classified =
      after.business_classification === "BUSINESS" ||
      after.business_classification === "MIXED";
    return classified && after.category_id && !takesExpenseCategory(row)
      ? [id]
      : [];
  });
}

// ---- Needs you first -------------------------------------------------------

type Held = { id: string; blocker: PlanBlocker; draft: boolean };

/** What the review offers for one kind of problem, acting on every movement
 * it holds. */
function BlockerFixes({
  kind,
  held,
  content,
  rows,
  onStage,
  onShowRows,
  onGoToDraft,
}: {
  kind: PlanBlocker["kind"];
  held: Held[];
  content: StagedContent;
  rows: ReadonlyMap<string, LedgerRow>;
  onStage: (event: StageEvent) => void;
  onShowRows: (ids: string[]) => void;
  onGoToDraft: (key: string) => void;
}) {
  const t = useStrings();
  const [share, setShare] = useState("");
  const [shareError, setShareError] = useState<string | null>(null);
  const [currency, setCurrency] = useState("");
  const ids = held.filter((entry) => !entry.draft).map((entry) => entry.id);
  const categories = useMemo<ComboboxOption[]>(
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
  const button = (label: string, run: () => void, name?: string) => (
    <Button
      key={name ?? label}
      variant="outline"
      size="xs"
      className={name ? `ledger-fix-${name}` : undefined}
      onClick={run}
    >
      {label}
    </Button>
  );
  const dropEdits = (keepActions: boolean) => () => {
    for (const id of ids) onStage({ type: "revert_movement", id, keepActions });
  };
  const revertFields = (fields: (entry: Held) => StageField[]) => () => {
    for (const entry of held)
      for (const field of fields(entry))
        if (content.rows[entry.id]?.[field])
          onStage({ type: "revert_cell", id: entry.id, field });
  };
  const dropActions = (pick: (entry: Held) => string[]) => () => {
    for (const entry of held)
      for (const action of pick(entry))
        onStage({ type: "drop_action", id: action });
  };
  const classifyAll = (kind: "business" | "personal", category?: string) => {
    const outcome = classifyCells({ kind, ids, category }, rows);
    if (outcome.kind === "staged") onStage(outcome.event);
  };
  const show = ids.length
    ? button(t("desktop.ledger.apply.fix.show"), () => onShowRows(ids), "show")
    : null;
  switch (kind) {
    case "needs_classification":
      return (
        <>
          <Combobox
            label={t("desktop.ledger.classify.category")}
            value={null}
            options={categories}
            emptyLabel={t("desktop.ledger.classify.no_category_match")}
            placeholder={t("desktop.ledger.classify.search_category")}
            onCommit={(category) => classifyAll("business", category)}
          >
            <Button variant="outline" size="xs" className="ledger-fix-business">
              {t("desktop.ledger.apply.fix.business")}
              <Icon name="chevronDown" size="xs" />
            </Button>
          </Combobox>
          {button(
            t("desktop.ledger.apply.fix.personal"),
            () => classifyAll("personal"),
            "personal",
          )}
          {show}
        </>
      );
    case "mixed_needs_share":
      return (
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            const parsed = parsePercent(share);
            if (parsed.kind !== "value") {
              setShareError(
                t("desktop.ledger.classify.share_refused", { raw: share }),
              );
              return;
            }
            for (const entry of held) {
              if (entry.draft)
                onStage({
                  type: "edit_draft",
                  key: entry.id,
                  field: "business_pct",
                  value: parsed.value,
                });
              else {
                const row = rows.get(entry.id);
                if (row)
                  onStage({
                    type: "stage",
                    label: "set",
                    cells: [
                      {
                        id: entry.id,
                        field: "business_pct",
                        value: { kind: "set", value: parsed.value },
                        stored: storedFieldValue(row, "business_pct"),
                      },
                    ],
                  });
              }
            }
          }}
        >
          <Input
            controlSize="sm"
            className="w-24"
            inputMode="decimal"
            aria-label={t("desktop.ledger.classify.share")}
            aria-invalid={shareError ? true : undefined}
            placeholder="50"
            value={share}
            onChange={(event) => {
              setShare(event.target.value);
              setShareError(null);
            }}
          />
          <Button type="submit" variant="outline" size="xs">
            {t("desktop.ledger.apply.fix.set_share")}
          </Button>
          {shareError && (
            <span className="text-sm text-foreground">{shareError}</span>
          )}
        </form>
      );
    case "share_needs_mixed":
      return button(
        t("desktop.ledger.apply.fix.drop_share"),
        revertFields(() => ["business_pct"]),
        "drop-share",
      );
    case "cannot_clear":
      return button(
        t("desktop.ledger.apply.fix.keep_stored"),
        revertFields((entry) =>
          entry.blocker.kind === "cannot_clear"
            ? (entry.blocker.fields.filter(
                (field) => field !== "m210_income_classification",
              ) as StageField[])
            : [],
        ),
        "keep-stored",
      );
    case "suggestion_and_edits":
      return (
        <>
          {button(
            t("desktop.ledger.apply.fix.drop_edits"),
            dropEdits(true),
            "drop-edits",
          )}
          {button(
            t("desktop.ledger.apply.fix.drop_approval"),
            dropActions((entry) =>
              "action" in entry.blocker ? [entry.blocker.action] : [],
            ),
            "drop-approval",
          )}
        </>
      );
    case "suggestion_and_rules":
      return (
        <>
          {button(
            t("desktop.ledger.apply.fix.drop_rules"),
            dropActions((entry) =>
              entry.blocker.kind === "suggestion_and_rules"
                ? entry.blocker.rules
                : [],
            ),
            "drop-rules",
          )}
          {button(
            t("desktop.ledger.apply.fix.drop_approval"),
            dropActions((entry) =>
              entry.blocker.kind === "suggestion_and_rules"
                ? [entry.blocker.action]
                : [],
            ),
            "drop-approval",
          )}
        </>
      );
    case "action_and_edits":
    case "exclude_and_classification":
      return (
        <>
          {button(
            t("desktop.ledger.apply.fix.drop_edits"),
            dropEdits(true),
            "drop-edits",
          )}
          {button(
            t("desktop.ledger.apply.fix.drop_action"),
            dropActions((entry) =>
              "action" in entry.blocker ? [entry.blocker.action] : [],
            ),
            "drop-action",
          )}
        </>
      );
    case "suggestion_needs_share":
      return button(
        t("desktop.ledger.apply.fix.drop_approval"),
        dropActions((entry) =>
          entry.blocker.kind === "suggestion_needs_share"
            ? [entry.blocker.action]
            : [],
        ),
        "drop-approval",
      );
    case "actions_conflict":
      return button(
        t("desktop.ledger.apply.fix.keep_first"),
        dropActions((entry) =>
          entry.blocker.kind === "actions_conflict"
            ? entry.blocker.actions.slice(1)
            : [],
        ),
        "keep-first",
      );
    case "draft_incomplete": {
      const needsCurrency = held.some(
        (entry) =>
          entry.blocker.kind === "draft_incomplete" &&
          entry.blocker.fields.includes("currency"),
      );
      return (
        <>
          {needsCurrency && (
            <form
              className="flex items-center gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                const code = currency.trim().toUpperCase();
                if (!/^[A-Z]{3}$/.test(code)) return;
                for (const entry of held)
                  onStage({
                    type: "edit_draft",
                    key: entry.id,
                    field: "currency",
                    value: code,
                  });
              }}
            >
              <Input
                controlSize="sm"
                className="w-24 uppercase"
                maxLength={3}
                aria-label={t("desktop.ledger.field.currency")}
                value={currency}
                onChange={(event) => setCurrency(event.target.value)}
              />
              <Button type="submit" variant="outline" size="xs">
                {t("desktop.ledger.apply.fix.set_currency")}
              </Button>
            </form>
          )}
          {held[0] &&
            button(
              t("desktop.ledger.apply.fix.go_to_draft"),
              () => onGoToDraft(held[0]!.id),
              "go-to-draft",
            )}
        </>
      );
    }
    default:
      return (
        <>
          {button(
            t("desktop.ledger.apply.fix.drop_changes"),
            dropEdits(false),
            "drop-changes",
          )}
          {show}
        </>
      );
  }
}

function blockerFields(t: Translate, blocker: PlanBlocker): string | null {
  const fields =
    "fields" in blocker
      ? (blocker.fields as (StageField | DraftField | string)[])
      : null;
  if (!fields?.length) return null;
  return fields
    .map((field) =>
      field === "m210_income_classification"
        ? t("desktop.ledger.field.m210_income_classification")
        : fieldName(t, field as StageField),
    )
    .join(", ");
}

function NeedsYouFirst({
  plan,
  content,
  rows,
  onStage,
  onShowRows,
  onGoToDraft,
}: {
  plan: LedgerPlan;
  content: StagedContent;
  rows: ReadonlyMap<string, LedgerRow>;
  onStage: (event: StageEvent) => void;
  onShowRows: (ids: string[]) => void;
  onGoToDraft: (key: string) => void;
}) {
  const t = useStrings();
  const byKind = new Map<PlanBlocker["kind"], Held[]>();
  for (const entry of plan.entries)
    for (const blocker of entry.blockers)
      byKind.set(blocker.kind, [
        ...(byKind.get(blocker.kind) ?? []),
        { id: entry.transactionId, blocker, draft: false },
      ]);
  for (const entry of plan.drafts)
    for (const blocker of entry.blockers)
      byKind.set(blocker.kind, [
        ...(byKind.get(blocker.kind) ?? []),
        { id: entry.key, blocker, draft: true },
      ]);
  if (byKind.size === 0) return null;
  const draftTitle = (key: string) =>
    content.drafts.find((draft) => draft.key === key)?.fields.description ??
    t("desktop.ledger.draft.untitled");
  return (
    <section
      className="ledger-blockers grid gap-3"
      aria-labelledby="ledger-blockers-heading"
    >
      <h3
        id="ledger-blockers-heading"
        className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
      >
        {t("desktop.ledger.apply.needs_you")}
      </h3>
      {[...byKind].map(([kind, held]) => {
        const fields = blockerFields(t, held[0]!.blocker);
        return (
          <div
            key={kind}
            data-blocker={kind}
            className="grid gap-1.5 border-b border-border pb-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Icon name="alert" size="xs" className="text-warning" />
              <span className="flex-1 font-medium">
                {t(`desktop.ledger.apply.blocker.${kind}`, {
                  count: held.length,
                })}
              </span>
              <BlockerFixes
                kind={kind}
                held={held}
                content={content}
                rows={rows}
                onStage={onStage}
                onShowRows={onShowRows}
                onGoToDraft={onGoToDraft}
              />
            </div>
            {fields && (
              <p className="text-sm text-muted-foreground">
                {t("desktop.ledger.apply.blocker_fields", { fields })}
              </p>
            )}
            <p className="text-sm text-muted-foreground">
              {held
                .slice(0, 4)
                .map((entry) =>
                  entry.draft
                    ? draftTitle(entry.id)
                    : titleOf(t, rows, entry.id),
                )
                .join(" · ")}
              {held.length > 4 &&
                ` · ${t("desktop.ledger.apply.more", { count: held.length - 4 })}`}
            </p>
          </div>
        );
      })}
    </section>
  );
}

// ---- Permanent links -------------------------------------------------------

function mismatchText(t: Translate, locale: string, mismatch: LinkMismatch) {
  switch (mismatch.kind) {
    case "amount":
      return t("desktop.ledger.apply.link.amount_differs", {
        amount: valueText(t, locale, "amount", mismatch.difference),
      });
    case "counterparty":
      return t("desktop.ledger.apply.link.counterparty_differs");
    case "currency":
      return t("desktop.ledger.apply.link.currency_differs", {
        movement: mismatch.movement,
        invoice: mismatch.invoice,
      });
    case "linked_elsewhere":
      return t("desktop.ledger.apply.link.linked_elsewhere", {
        count: mismatch.count,
      });
  }
}

function PermanentLinks({
  links,
  locale,
  ticks,
  onTicks,
  onRereadInvoices,
}: {
  links: {
    id: string;
    row: LedgerRow | undefined;
    invoice: CatalogueInvoice | undefined;
    invoiceId: string;
    mismatches: LinkMismatch[];
  }[];
  locale: string;
  ticks: LinkTicks;
  onTicks: (ticks: LinkTicks) => void;
  /** Reads the catalogue again where an invoice could not be read. */
  onRereadInvoices: () => void;
}) {
  const t = useStrings();
  if (!links.length) return null;
  const side = (parts: (string | null | undefined)[]) =>
    parts.filter(Boolean).join(" · ");
  return (
    <section
      className="ledger-permanent grid gap-3 rounded-lg bg-muted p-3"
      aria-labelledby="ledger-permanent-heading"
    >
      <h3
        id="ledger-permanent-heading"
        className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase"
      >
        <Icon name="lock" size="xs" />
        {t("desktop.ledger.apply.permanent")}
      </h3>
      <p className="text-sm">{t("desktop.ledger.apply.permanent_note")}</p>
      {links.map((link) => {
        const tick = ticks[link.id] ?? { sure: false, differ: false };
        const transaction = link.row?.transaction;
        return (
          <div key={link.id} data-link={link.id} className="grid gap-1.5">
            <p className="text-sm">
              {side([
                transaction &&
                  valueText(t, locale, "amount", transaction.amount),
                transaction?.counterparty || transaction?.description,
                transaction &&
                  valueText(t, locale, "booked_date", transaction.date),
              ])}
              {" ↔ "}
              {link.invoice
                ? side([
                    link.invoice.invoice_number,
                    valueText(
                      t,
                      locale,
                      "amount",
                      link.invoice.grand_total.decimal,
                    ),
                    link.invoice.counterparty_name,
                    valueText(t, locale, "booked_date", link.invoice.issued_at),
                  ])
                : link.invoiceId}
            </p>
            {!link.invoice && (
              <p
                role="alert"
                className="ledger-link-unread flex flex-wrap items-center gap-1.5 text-sm"
              >
                <Icon name="unknown" size="xs" className="text-warning" />
                {t("desktop.ledger.apply.link.unread")}
                <Button
                  variant="link"
                  size="xs"
                  className="ledger-link-reread"
                  onClick={onRereadInvoices}
                >
                  {t("desktop.ledger.paused.reread")}
                </Button>
              </p>
            )}
            {link.mismatches.length > 0 && (
              <ul className="flex flex-wrap gap-1.5">
                {link.mismatches.map((mismatch) => (
                  <li key={mismatch.kind}>
                    <Badge variant="warning">
                      {mismatchText(t, locale, mismatch)}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                className="ledger-link-sure"
                checked={tick.sure}
                disabled={!link.invoice}
                onChange={(event) =>
                  onTicks({
                    ...ticks,
                    [link.id]: { ...tick, sure: event.target.checked },
                  })
                }
              />
              {t("desktop.ledger.apply.link.sure")}
            </label>
            {link.mismatches.length > 0 && (
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  className="ledger-link-differ"
                  checked={tick.differ}
                  onChange={(event) =>
                    onTicks({
                      ...ticks,
                      [link.id]: { ...tick, differ: event.target.checked },
                    })
                  }
                />
                {t("desktop.ledger.apply.link.differ")}
              </label>
            )}
          </div>
        );
      })}
    </section>
  );
}

// ---- Model approvals -------------------------------------------------------

function Approvals({
  approvals,
  rows,
  locale,
}: {
  approvals: Extract<StagedAction, { kind: "suggestion" }>[];
  rows: ReadonlyMap<string, LedgerRow>;
  locale: string;
}) {
  const t = useStrings();
  if (!approvals.length) return null;
  return (
    <section
      className="ledger-approvals grid gap-2"
      aria-labelledby="ledger-approvals-heading"
    >
      <h3
        id="ledger-approvals-heading"
        className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
      >
        {t("desktop.ledger.apply.approvals")}
      </h3>
      {approvals.map((approval) => {
        const row = rows.get(approval.transactionId);
        return (
          <div
            key={approval.id}
            className="grid gap-1 border-b border-border pb-2"
          >
            <p className="flex items-center gap-1.5 font-medium">
              <Icon name="agent" size="xs" className="text-muted-foreground" />
              {titleOf(t, rows, approval.transactionId)}
              <span className="text-sm font-normal text-muted-foreground">
                {approval.decision === "apply"
                  ? t("desktop.ledger.apply.approve")
                  : t("desktop.ledger.apply.reject", {
                      reason: approval.reason,
                    })}
              </span>
            </p>
            {approval.decision === "apply" && (
              <ul className="grid gap-0.5 text-sm">
                {(approval.writes ?? []).map((write) => (
                  <li
                    key={write.field}
                    data-derived={write.derived || undefined}
                  >
                    {fieldName(t, write.field)}:{" "}
                    {valueText(
                      t,
                      locale,
                      write.field,
                      row ? (storedFieldValue(row, write.field) ?? null) : null,
                    )}
                    {" → "}
                    {valueText(t, locale, write.field, write.value)}
                    {write.derived && (
                      <span className="text-muted-foreground">
                        {` · ${t("desktop.ledger.edit.lock.derived")}`}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </section>
  );
}

// ---- The per-movement list -------------------------------------------------

type Entry = {
  key: string;
  draft: boolean;
  title: string;
  lines: string[];
  blocked: boolean;
};

function entriesOf(
  t: Translate,
  locale: string,
  content: StagedContent,
  plan: LedgerPlan,
  rows: ReadonlyMap<string, LedgerRow>,
): Entry[] {
  const entries: Entry[] = [];
  for (const entry of plan.entries) {
    const row = rows.get(entry.transactionId);
    const changes = content.rows[entry.transactionId] ?? {};
    const lines = entry.fields.map((field) => {
      const change = changes[field]!;
      return `${fieldName(t, field)}: ${valueText(
        t,
        locale,
        field,
        row ? (storedFieldValue(row, field) ?? null) : null,
      )} → ${
        change.kind === "set"
          ? valueText(t, locale, field, change.value)
          : t("desktop.ledger.edit.cleared")
      }`;
    });
    for (const action of content.actions)
      if (actionRows(action).includes(entry.transactionId))
        lines.push(...actionLines(t, locale, action));
    entries.push({
      key: entry.transactionId,
      draft: false,
      title: titleOf(t, rows, entry.transactionId),
      lines,
      blocked: entry.blockers.length > 0,
    });
  }
  for (const draft of content.drafts) {
    const checked = plan.drafts.find((entry) => entry.key === draft.key);
    entries.push({
      key: draft.key,
      draft: true,
      title: draft.fields.description ?? t("desktop.ledger.draft.untitled"),
      lines: [
        (Object.entries(draft.fields) as [DraftField, string][])
          .filter(([field]) => field !== "description")
          .map(([field, value]) => valueText(t, locale, field, value))
          .join(" · "),
      ],
      blocked: (checked?.blockers.length ?? 0) > 0,
    });
  }
  return entries;
}

function MovementList({
  entries,
  only,
  onOnly,
  onDrop,
  open,
  onOpen,
}: {
  entries: Entry[];
  only: string[] | null;
  onOnly: (ids: string[] | null) => void;
  onDrop: (entry: Entry) => void;
  /** The list is folded behind its count until opened. */
  open: boolean;
  onOpen: (open: boolean) => void;
}) {
  const t = useStrings();
  const [filter, setFilter] = useState("");
  const words = filter.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const shown = entries.filter(
    (entry) =>
      (only === null || only.includes(entry.key)) &&
      words.every((word) =>
        [entry.title, ...entry.lines]
          .join(" ")
          .toLocaleLowerCase()
          .includes(word),
      ),
  );
  return (
    <details
      className="ledger-review-rows grid gap-2"
      open={open}
      onToggle={(event) => onOpen(event.currentTarget.open)}
    >
      <summary className="ledger-review-rows-toggle flex cursor-pointer items-center gap-1.5 text-sm text-muted-foreground">
        {`${t("desktop.ledger.apply.summary_movements")} · ${entries.length}`}
        <Icon name={open ? "chevronDown" : "forward"} size="xs" />
      </summary>
      {open && (
        <div className="mt-2 grid gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Input
              controlSize="sm"
              className="w-field"
              type="search"
              aria-label={t("desktop.ledger.apply.filter")}
              placeholder={t("desktop.ledger.apply.filter")}
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
            <span className="text-sm text-muted-foreground">
              {t("desktop.ledger.apply.shown", {
                shown: shown.length,
                total: entries.length,
              })}
            </span>
            {only !== null && (
              <Button variant="link" size="xs" onClick={() => onOnly(null)}>
                {t("desktop.ledger.apply.show_all")}
              </Button>
            )}
          </div>
          <WindowedList
            label={t("desktop.ledger.apply.rows")}
            className="max-h-72 rounded-md border border-border"
            items={shown}
            keyOf={(entry) => entry.key}
            render={(entry) => (
              <div
                data-entry={entry.key}
                className="flex h-14 items-center gap-2 border-b border-border px-3"
              >
                {entry.blocked ? (
                  <Icon
                    name="alert"
                    size="xs"
                    className="shrink-0 text-warning"
                  />
                ) : (
                  entry.draft && (
                    <Icon name="plus" size="xs" className="shrink-0" />
                  )
                )}
                <span className="grid min-w-0 flex-1">
                  <span className="truncate font-medium">{entry.title}</span>
                  <span className="truncate text-sm text-muted-foreground">
                    {entry.lines.join(" · ")}
                  </span>
                </span>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  className="ledger-review-drop"
                  aria-label={t("desktop.ledger.apply.drop", {
                    movement: entry.title,
                  })}
                  onClick={() => onDrop(entry)}
                >
                  <Icon name="close" size="xs" />
                </Button>
              </div>
            )}
          />
        </div>
      )}
    </details>
  );
}

// ---- Outcomes --------------------------------------------------------------

const OUTCOME_ICONS: Record<StepOutcome["kind"], IconName> = {
  applied: "check",
  unchanged: "pending",
  settled: "check",
  refused: "refused",
  unknown: "unknown",
  saved_unread: "unknown",
  not_sent: "pause",
};

/** The colour of an outcome's glyph. */
function outcomeTone(kind: StepOutcome["kind"]): string | undefined {
  if (kind === "refused") return "text-destructive";
  if (kind === "unknown" || kind === "saved_unread") return "text-warning";
  if (kind === "applied" || kind === "settled") return "text-success";
  return undefined;
}

function stepTitle(
  t: Translate,
  step: PlanStep,
  rows: ReadonlyMap<string, LedgerRow>,
  content: StagedContent,
): string {
  switch (step.kind) {
    case "bulk":
      return t("desktop.ledger.apply.step.bulk", {
        count: step.rows.length,
        part: step.part,
        parts: step.parts,
      });
    case "classify":
    case "update":
      return `${titleOf(t, rows, step.transactionId)}: ${step.fields
        .map((field) => fieldName(t, field))
        .join(", ")}`;
    case "add":
      return t("desktop.ledger.apply.step.add", {
        movement:
          content.drafts.find((draft) => draft.key === step.draftKey)?.fields
            .description ?? step.request.description,
      });
    case "action":
    case "answer":
      return step.action.kind === "rule_apply"
        ? actionText(t, "", step.action)
        : `${actionText(t, "", step.action)} · ${titleOf(
            t,
            rows,
            actionRows(step.action)[0] ?? "",
          )}`;
  }
}

/** Why a change was refused, in words; its code is under Technical
 * details. */
function refusalWords(
  t: Translate,
  outcome: Extract<StepOutcome, { kind: "refused" }>,
): string {
  if (outcome.reason === "precondition_failed")
    return t("desktop.ledger.apply.refusal.changed_elsewhere");
  return outcome.messages[0] ?? t("desktop.ledger.apply.refusal.other");
}

/** A refusal that a read of the ledger and a new review can resolve. */
const changedElsewhere = (outcome: StepOutcome) =>
  outcome.kind === "refused" && outcome.reason === "precondition_failed";

function outcomeText(
  t: Translate,
  locale: string,
  outcome: StepOutcome,
  stored: { field: StageField; value: string | null } | null,
): string {
  switch (outcome.kind) {
    case "applied":
      return outcome.newId
        ? t("desktop.ledger.apply.outcome.applied_new_id")
        : t("desktop.ledger.apply.outcome.applied");
    case "unchanged":
      return stored
        ? t("desktop.ledger.apply.outcome.unchanged_value", {
            field: fieldName(t, stored.field),
            value: valueText(t, locale, stored.field, stored.value),
          })
        : t("desktop.ledger.apply.outcome.unchanged");
    case "settled":
      return stored
        ? t("desktop.ledger.apply.outcome.settled_value", {
            field: fieldName(t, stored.field),
            value: valueText(t, locale, stored.field, stored.value),
          })
        : t("desktop.ledger.apply.outcome.settled");
    case "refused":
      return t("desktop.ledger.apply.outcome.refused", {
        reason: refusalWords(t, outcome),
      });
    case "unknown":
      return t("desktop.ledger.apply.outcome.unknown");
    case "saved_unread":
      return t("desktop.ledger.apply.outcome.saved_unread");
    case "not_sent":
      return t(`desktop.ledger.apply.outcome.not_sent_${outcome.why}`);
  }
}

type OutcomeItem = {
  key: string;
  title: string;
  outcome: StepOutcome;
  note: string;
  head?: string;
};

/** Every step's outcome, a bulk part's row by row unless the part ended
 * whole. */
function outcomeItems(
  t: Translate,
  locale: string,
  reports: readonly StepReport[],
  rows: ReadonlyMap<string, LedgerRow>,
  fresh: ReadonlyMap<string, LedgerRow> | null,
  content: StagedContent,
): OutcomeItem[] {
  const storedOf = (
    id: string,
    fields: StageField[],
  ): { field: StageField; value: string | null } | null => {
    const row = fresh?.get(id);
    const field = fields[0];
    if (!row || !field) return null;
    return { field, value: storedFieldValue(row, field) ?? null };
  };
  const items: OutcomeItem[] = [];
  for (const report of reports) {
    const step = report.step;
    if (step.kind === "bulk") {
      const whole =
        report.rows.length > 0 &&
        report.rows.every((row) => row.outcome === report.outcome) &&
        !["applied", "unchanged", "settled"].includes(report.outcome.kind);
      if (whole)
        items.push({
          key: `${report.index}`,
          title: stepTitle(t, step, rows, content),
          outcome: report.outcome,
          head: "part",
          note:
            report.outcome.kind === "refused"
              ? t("desktop.ledger.apply.part_refused")
              : report.outcome.kind === "unknown"
                ? t("desktop.ledger.apply.part_unknown")
                : outcomeText(t, locale, report.outcome, null),
        });
      else
        step.rows.forEach((row, at) => {
          const outcome = report.rows[at]?.outcome ?? report.outcome;
          items.push({
            key: `${report.index}:${row.transactionId}`,
            title: titleOf(t, rows, row.transactionId),
            outcome,
            note: outcomeText(
              t,
              locale,
              outcome,
              storedOf(row.transactionId, row.fields),
            ),
          });
        });
      continue;
    }
    items.push({
      key: `${report.index}`,
      title: stepTitle(t, step, rows, content),
      outcome: report.outcome,
      note: outcomeText(
        t,
        locale,
        report.outcome,
        step.kind === "classify" || step.kind === "update"
          ? storedOf(step.transactionId, step.fields)
          : null,
      ),
    });
  }
  return items;
}

function Outcomes({ items }: { items: readonly OutcomeItem[] }) {
  const t = useStrings();
  if (!items.length) return null;
  return (
    <WindowedList
      label={t("desktop.ledger.apply.outcomes")}
      className="ledger-outcomes max-h-96 rounded-md border border-border"
      items={items}
      keyOf={(item) => item.key}
      render={(item) => (
        <div
          data-outcome={item.outcome.kind}
          data-part={item.head}
          className="flex h-14 items-center gap-2 border-b border-border px-3"
        >
          <Icon
            name={OUTCOME_ICONS[item.outcome.kind]}
            size="xs"
            className={cn("shrink-0", outcomeTone(item.outcome.kind))}
          />
          <span className="grid min-w-0 flex-1">
            <span className="truncate">{item.title}</span>
            <span className="truncate text-sm text-muted-foreground">
              {item.note}
            </span>
          </span>
        </div>
      )}
    />
  );
}

// ---- The dialog ------------------------------------------------------------

/**
 * The review and apply of everything staged on the page. It leads with one
 * line of counts in the page's unit, then what needs the person first,
 * permanent links, model approvals, a summary by kind of change and the
 * list of movements, the plan in plain words with its operations under
 * Technical details; then the apply with each part's progress and every
 * row's outcome.
 */
export function ReviewDialog({
  apply,
  content,
  tally,
  locale,
  onStage,
  onShowRows,
  onGoToDraft,
  onCloseAutoFocus,
}: {
  apply: Apply;
  content: StagedContent;
  tally: StageTally;
  locale: string;
  onStage: (event: StageEvent) => void;
  onShowRows: (ids: string[]) => void;
  onGoToDraft: (key: string) => void;
  /** Where the focus goes once the review has gone. */
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const t = useStrings();
  const pause = useWritePause();
  const state = apply.state;
  const heading = useRef<HTMLHeadingElement>(null);
  // Each step of the review, and its result, starts at its heading.
  useEffect(() => {
    heading.current?.focus();
  }, [state.phase]);
  const [ticks, setTicks] = useState<LinkTicks>({});
  const [only, setOnly] = useState<string[] | null>(null);
  const [listOpen, setListOpen] = useState<boolean | null>(null);
  const [looked, setLooked] = useState(false);
  const [choices, setChoices] = useState<Record<string, "mine" | "theirs">>({});
  const rows =
    state.phase === "closed" ||
    state.phase === "reading" ||
    state.phase === "failed"
      ? null
      : state.rows;
  const plan = useMemo(
    () =>
      state.phase === "ready"
        ? planApply(content, {
            rows: state.rows,
            sealed: state.sealed,
            outputLanguage: locale as OutputLanguage,
          })
        : null,
    [state, content, locale],
  );
  if (state.phase === "closed") return null;
  const busy = state.phase === "applying";
  const close = () => {
    if (!busy) apply.close();
  };

  let title: ReactNode = t("desktop.ledger.apply.title", {
    count: tally.units,
  });
  let description: ReactNode = null;
  let body: ReactNode = null;
  let footer: ReactNode = null;

  if (state.phase === "reading") {
    description = t("desktop.ledger.apply.reading");
    body = (
      <div
        role="status"
        className="flex items-center gap-2 text-muted-foreground"
      >
        <Spinner />
        {t("desktop.ledger.apply.reading")}
      </div>
    );
  } else if (state.phase === "failed") {
    body = (
      <Alert tone="danger" role="alert" icon={<Icon name="alert" />}>
        <AlertTitle>{t("desktop.ledger.apply.read_failed")}</AlertTitle>
      </Alert>
    );
    footer = (
      <>
        <Button variant="ghost" onClick={close}>
          {t("desktop.ledger.apply.keep_editing")}
        </Button>
        <Button onClick={() => void apply.open()}>
          {t("desktop.ledger.retry")}
        </Button>
      </>
    );
  } else if (state.phase === "ready" && state.conflicts.length > 0) {
    title = t("desktop.ledger.apply.conflicts_title");
    description = t("desktop.ledger.apply.conflicts_description");
    body = (
      <ConflictList
        conflicts={state.conflicts}
        choices={choices}
        onChoose={(id, keep) => setChoices({ ...choices, [id]: keep })}
        locale={locale}
        content={content}
      />
    );
    footer = (
      <>
        <label className="me-auto flex items-center gap-2 text-sm">
          <Checkbox
            className="ledger-conflicts-looked"
            checked={looked}
            onChange={(event) => setLooked(event.target.checked)}
          />
          {t("desktop.ledger.apply.conflicts_looked")}
        </label>
        <Button variant="ghost" onClick={close}>
          {t("desktop.ledger.apply.back")}
        </Button>
        <Button
          className="ledger-conflicts-continue"
          aria-disabled={looked ? undefined : true}
          onClick={() => {
            if (!looked) return;
            for (const conflict of state.conflicts) {
              const keep = choices[conflict.transactionId] ?? "mine";
              if (conflict.kind === "changed")
                apply.resolve(conflict.transactionId, keep, conflict.fields);
              else if (keep === "theirs")
                onStage({
                  type: "revert_movement",
                  id: conflict.transactionId,
                });
            }
            apply.resolveAll();
          }}
        >
          {t("desktop.ledger.apply.continue")}
        </Button>
      </>
    );
  } else if (state.phase === "ready" && plan && rows) {
    const held = heldUnits(content, plan);
    const savable = tally.units - held;
    const linkSteps = plan.steps.flatMap((step) =>
      step.kind === "action" && step.action.kind === "link"
        ? [step.action]
        : [],
    );
    const links = linkSteps.map((action) => {
      const row = rows.get(action.transactionId);
      const invoice = state.invoices?.find(
        (found) => found.invoice_id === action.invoiceId,
      );
      return {
        id: action.id,
        row,
        invoice,
        invoiceId: action.invoiceId,
        mismatches: row && invoice ? linkMismatches(row, invoice) : [],
      };
    });
    // A link whose invoice could not be read is held until it is read.
    const unread = links.some((link) => !link.invoice);
    const ready = !unread && linksReady(links, ticks);
    const approvals = content.actions.filter(
      (action): action is Extract<StagedAction, { kind: "suggestion" }> =>
        action.kind === "suggestion",
    );
    const groups = changeGroups(content, rows);
    const entries = entriesOf(t, locale, content, plan, rows);
    description = planLine(t, plan, held);
    const onIncome = incomeWithCategory(content, rows);
    body = (
      <div className="grid gap-5">
        {onIncome.length > 0 && (
          <ul className="ledger-review-mismatches flex flex-wrap items-center gap-1.5">
            <li data-mismatch="income_category">
              <Badge variant="warning">
                {t("desktop.ledger.apply.mismatch.income_category", {
                  count: onIncome.length,
                })}
              </Badge>
            </li>
            <li>
              <Button
                variant="link"
                size="xs"
                onClick={() => {
                  setOnly(onIncome);
                  setListOpen(true);
                }}
              >
                {t("desktop.ledger.apply.show_rows")}
              </Button>
            </li>
          </ul>
        )}
        <NeedsYouFirst
          plan={plan}
          content={content}
          rows={rows}
          onStage={onStage}
          onShowRows={onShowRows}
          onGoToDraft={onGoToDraft}
        />
        <PermanentLinks
          links={links}
          locale={locale}
          ticks={ticks}
          onTicks={setTicks}
          onRereadInvoices={() => void apply.rereadInvoices()}
        />
        <Approvals approvals={approvals} rows={rows} locale={locale} />
        {groups.length > 0 && (
          <section
            className="grid gap-2"
            aria-labelledby="ledger-summary-heading"
          >
            <h3
              id="ledger-summary-heading"
              className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
            >
              {t("desktop.ledger.apply.summary")}
            </h3>
            <table className="ledger-summary w-full text-base">
              <thead className="text-sm text-muted-foreground">
                <tr className="border-b border-border">
                  <th scope="col" className="py-1 text-start font-normal">
                    {t("desktop.ledger.apply.summary_field")}
                  </th>
                  <th scope="col" className="py-1 text-start font-normal">
                    {t("desktop.ledger.apply.summary_change")}
                  </th>
                  <th scope="col" className="py-1 text-end font-normal">
                    {t("desktop.ledger.apply.summary_movements")}
                  </th>
                  <th scope="col" className="py-1">
                    <span className="sr-only">
                      {t("desktop.ledger.apply.fix.show")}
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {groups.slice(0, 12).map((group) => (
                  <tr
                    key={`${group.field}:${group.ids[0]}`}
                    className="border-b border-border"
                  >
                    <td className="py-1.5 pe-3">{fieldName(t, group.field)}</td>
                    <td className="py-1.5 pe-3">
                      <span className="text-muted-foreground">
                        {valueText(t, locale, group.field, group.from)}
                      </span>
                      {" → "}
                      {group.to.kind === "set"
                        ? valueText(t, locale, group.field, group.to.value)
                        : t("desktop.ledger.edit.cleared")}
                    </td>
                    <td className="py-1.5 text-end tabular-nums">
                      {group.ids.length}
                    </td>
                    <td className="py-1.5 text-end">
                      <Button
                        variant="link"
                        size="xs"
                        onClick={() => {
                          setOnly(group.ids);
                          setListOpen(true);
                        }}
                      >
                        {t("desktop.ledger.apply.show_rows")}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
        <RuleApplies
          actions={content.actions.filter(
            (action): action is Extract<StagedAction, { kind: "rule_apply" }> =>
              action.kind === "rule_apply",
          )}
          rows={rows}
          onDrop={(id) => onStage({ type: "drop_action", id })}
        />
        <MovementList
          entries={entries}
          only={only}
          onOnly={setOnly}
          // With no summary by kind the list is the summary: it starts open.
          open={listOpen ?? groups.length === 0}
          onOpen={setListOpen}
          onDrop={(entry) =>
            onStage(
              entry.draft
                ? { type: "remove_draft", key: entry.key }
                : { type: "revert_movement", id: entry.key },
            )
          }
        />
        <details className="ledger-technical text-sm">
          <summary className="cursor-pointer text-muted-foreground">
            {t("desktop.ledger.apply.technical")}
          </summary>
          <ul className="mt-2 grid gap-1 font-mono text-xs">
            {plan.steps.map((step, at) => (
              <li key={at}>{technicalLine(step)}</li>
            ))}
          </ul>
        </details>
      </div>
    );
    footer = (
      <>
        <span className="me-auto text-sm text-muted-foreground">
          {apply.paused
            ? apply.paused
            : unread
              ? t("desktop.ledger.apply.link.unread")
              : !ready
                ? t("desktop.ledger.apply.tick_links")
                : held
                  ? t("desktop.ledger.apply.held_note", { count: held })
                  : ""}
        </span>
        <Button variant="ghost" onClick={close}>
          {t("desktop.ledger.apply.keep_editing")}
        </Button>
        <Button
          className="ledger-apply-save"
          aria-disabled={
            savable <= 0 ||
            !ready ||
            apply.paused !== null ||
            !plan.steps.length
              ? true
              : undefined
          }
          onClick={() => {
            if (savable <= 0 || !ready || apply.paused || !plan.steps.length)
              return;
            void apply.apply(plan);
          }}
        >
          {held
            ? t("desktop.ledger.apply.save_held", { count: savable, held })
            : t("desktop.ledger.apply.save", { count: savable })}
        </Button>
      </>
    );
  } else if (state.phase === "applying") {
    title = t("desktop.ledger.apply.saving");
    description = t("desktop.ledger.apply.saving_description");
    body = (
      <div className="grid gap-3">
        <Progress
          aria-label={t("desktop.ledger.apply.progress")}
          value={state.reports.length}
          max={state.plan.steps.length}
        />
        <p role="status" className="text-sm text-muted-foreground">
          {t("desktop.ledger.apply.progress_count", {
            done: state.reports.length,
            total: state.plan.steps.length,
          })}
        </p>
        <Outcomes
          items={outcomeItems(
            t,
            locale,
            state.reports,
            state.rows,
            null,
            content,
          )}
        />
      </div>
    );
  } else if (state.phase === "done") {
    const counts = outcomeTally(state.report.steps);
    const saved = (counts.applied ?? 0) + (counts.settled ?? 0);
    // Titled by its worst outcome; "Saved" only where every part settled.
    const worst = WORST.find((kind) => (counts[kind] ?? 0) > 0) ?? null;
    const headline: StepOutcome["kind"] =
      worst ?? (saved > 0 ? "applied" : "unchanged");
    title = (
      <span className="ledger-apply-headline flex items-center gap-2">
        <Icon
          name={OUTCOME_ICONS[headline]}
          className={outcomeTone(headline)}
        />
        {`${t(`desktop.ledger.apply.tally.${headline}`)} · ${
          worst ? counts[worst]! : saved || (counts.unchanged ?? 0)
        }`}
      </span>
    );
    const items = outcomeItems(
      t,
      locale,
      state.report.steps,
      state.rows,
      state.fresh,
      content,
    );
    const unsaved = items.filter((item) => !SAVED.has(item.outcome.kind));
    const refusals = items.filter((item) => item.outcome.kind === "refused");
    const kinds = Object.keys(counts).length;
    body = (
      <div className="grid gap-3">
        {kinds > 1 && (
          <ul className="ledger-outcome-tally flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {(Object.entries(counts) as [StepOutcome["kind"], number][]).map(
              ([kind, count]) => (
                <li
                  key={kind}
                  data-tally={kind}
                  className="flex items-center gap-1.5"
                >
                  <Icon name={OUTCOME_ICONS[kind]} size="xs" />
                  {t(`desktop.ledger.apply.tally.${kind}`)}
                  <span className="font-semibold tabular-nums">{count}</span>
                </li>
              ),
            )}
          </ul>
        )}
        {state.report.paused && (
          <Alert
            tone="warning"
            role="alert"
            icon={<Icon name="unknown" />}
            className="ledger-apply-unknown"
          >
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="min-w-0 flex-1">
                {t(
                  state.report.steps.some(
                    (step) => step.outcome.kind === "unknown",
                  )
                    ? "desktop.ledger.apply.unknown_note"
                    : "desktop.ledger.apply.outcome.saved_unread",
                )}
              </span>
              {apply.paused && (
                <Button
                  size="xs"
                  variant="outline"
                  className="ledger-apply-reread shrink-0"
                  onClick={() => {
                    if (!pause.rereading) pause.reread();
                  }}
                  aria-disabled={pause.rereading || undefined}
                >
                  <Icon name="sync" />
                  {t("desktop.ledger.paused.reread")}
                </Button>
              )}
            </div>
          </Alert>
        )}
        {state.report.stopped && (
          <Alert tone="danger" role="alert" icon={<Icon name="alert" />}>
            <AlertTitle>{t("desktop.ledger.apply.stopped")}</AlertTitle>
          </Alert>
        )}
        <Outcomes items={unsaved} />
        {refusals.length > 0 && (
          <details className="ledger-technical text-sm">
            <summary className="cursor-pointer text-muted-foreground">
              {t("desktop.ledger.apply.technical")}
            </summary>
            <ul className="mt-2 grid gap-1 font-mono text-xs">
              {refusals.map((item) => (
                <li key={item.key}>
                  {`${item.title} · ${
                    item.outcome.kind === "refused"
                      ? (item.outcome.reason ?? "refused")
                      : ""
                  }`}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    );
    footer = (
      <>
        {!apply.paused &&
          unsaved.some((item) => changedElsewhere(item.outcome)) && (
            <Button
              variant="outline"
              className="ledger-apply-refused-reread"
              onClick={() => void apply.open()}
            >
              <Icon name="sync" />
              {t("desktop.ledger.paused.reread")}
            </Button>
          )}
        <Button className="ledger-apply-done" onClick={close}>
          {t("desktop.ledger.apply.close")}
        </Button>
      </>
    );
  }

  return (
    <Dialog open onOpenChange={(open) => !open && close()}>
      <DialogContent
        placement="top"
        className="ledger-review w-dialog-xl overflow-y-auto"
        closeLabel={busy ? undefined : t("desktop.ledger.apply.close")}
        onEscapeKeyDown={(event) => {
          if (busy) event.preventDefault();
        }}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          heading.current?.focus();
        }}
        onPointerDownOutside={(event) => {
          if (busy) event.preventDefault();
        }}
        onCloseAutoFocus={onCloseAutoFocus}
        aria-busy={busy || undefined}
        {...(description ? {} : { "aria-describedby": undefined })}
      >
        <DialogHeader>
          <DialogTitle ref={heading} tabIndex={-1}>
            {title}
          </DialogTitle>
          {description && (
            <DialogDescription className="ledger-review-summary">
              {description}
            </DialogDescription>
          )}
        </DialogHeader>
        {body}
        {footer && <DialogFooter sticky>{footer}</DialogFooter>}
      </DialogContent>
    </Dialog>
  );
}

/** One operation of the plan, as Technical details lists it. */
function technicalLine(step: PlanStep): string {
  switch (step.kind) {
    case "bulk":
      return `ledger.classify.bulk · ${step.part}/${step.parts} · ${step.rows.length}`;
    case "classify":
      return `ledger.classify.single · ${step.transactionId.slice(0, 12)} · ${step.request.patch_fields.join(",")}`;
    case "update":
      return `ledger.update · ${step.transactionId.slice(0, 12)} · ${step.request.patch_fields.join(",")}`;
    case "add":
      return `ledger.add · ${step.request.idempotency_key ?? ""}`;
    case "action":
      return `${step.definition} · ${actionRows(step.action)
        .map((id) => id.slice(0, 12))
        .join(",")}`;
    case "answer":
      return `ledger.classify.review · ${step.action.operationId.slice(0, 12)} · ${step.action.reviewDigest.slice(0, 12)}`;
  }
}

function ConflictList({
  conflicts,
  choices,
  onChoose,
  locale,
  content,
}: {
  conflicts: AskedConflict[];
  choices: Record<string, "mine" | "theirs">;
  onChoose: (id: string, keep: "mine" | "theirs") => void;
  locale: string;
  content: StagedContent;
}) {
  const t = useStrings();
  return (
    <ul className="ledger-conflicts grid gap-4">
      {conflicts.map((conflict) => {
        const keep = choices[conflict.transactionId] ?? "mine";
        const toggle = (
          <div
            role="radiogroup"
            aria-label={t("desktop.ledger.apply.conflict_choice")}
            className="flex gap-1"
          >
            {(["mine", "theirs"] as const).map((choice) => (
              <Button
                key={choice}
                role="radio"
                aria-checked={keep === choice}
                variant={keep === choice ? "outline" : "ghost"}
                size="xs"
                className={`ledger-conflict-${choice}`}
                onClick={() => onChoose(conflict.transactionId, choice)}
              >
                {t(
                  conflict.kind === "gone"
                    ? `desktop.ledger.apply.gone_${choice}`
                    : `desktop.ledger.apply.${choice}`,
                )}
              </Button>
            ))}
          </div>
        );
        if (conflict.kind === "gone")
          return (
            <li
              key={conflict.transactionId}
              data-conflict="gone"
              className="grid gap-1.5 border-b border-border pb-3"
            >
              <p className="font-medium">
                {conflict.before?.transaction.description ??
                  t("desktop.ledger.apply.gone_movement")}
              </p>
              <p className="text-sm">{t("desktop.ledger.apply.gone")}</p>
              {toggle}
            </li>
          );
        const changes = content.rows[conflict.transactionId] ?? {};
        return (
          <li
            key={conflict.transactionId}
            data-conflict="changed"
            className="grid gap-1.5 border-b border-border pb-3"
          >
            <p className="font-medium">
              {conflict.after.transaction.description}
            </p>
            {conflict.fields.map((field) => {
              const change = changes[field];
              return (
                <dl
                  key={field}
                  className="grid grid-cols-[auto_1fr] gap-x-3 text-sm"
                >
                  <dt className="col-span-2 text-muted-foreground">
                    {fieldName(t, field)}
                  </dt>
                  <dt>{t("desktop.ledger.apply.when_read")}</dt>
                  <dd className="font-medium">
                    {valueText(
                      t,
                      locale,
                      field,
                      storedFieldValue(conflict.before, field) ?? null,
                    )}
                  </dd>
                  <dt>{t("desktop.ledger.apply.now_stored")}</dt>
                  <dd className="font-medium">
                    {valueText(
                      t,
                      locale,
                      field,
                      storedFieldValue(conflict.after, field) ?? null,
                    )}
                  </dd>
                  <dt>{t("desktop.ledger.apply.yours")}</dt>
                  <dd className="font-medium">
                    {change?.kind === "set"
                      ? valueText(t, locale, field, change.value)
                      : t("desktop.ledger.edit.cleared")}
                  </dd>
                </dl>
              );
            })}
            {toggle}
          </li>
        );
      })}
    </ul>
  );
}
