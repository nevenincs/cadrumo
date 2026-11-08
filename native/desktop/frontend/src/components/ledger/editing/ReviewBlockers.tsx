import { useMemo, useState } from "react";
import { CurrencyEditor } from "@/components/editors/CurrencyEditor";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { facts, listed } from "@/shell/compose";
import type { LedgerPort, LedgerRow } from "../../../shell/ledger";
import { classifyCells } from "../../../shell/ledgerCommands";
import { parsePercent } from "../../../shell/ledgerGrammar";
import {
  checkOnce,
  stagedCheckRequest,
} from "../../../shell/ledgerStagedCheck";
import type { LedgerPlan, PlanBlocker } from "../../../shell/ledgerPlan";
import {
  storedFieldValue,
  type DraftField,
  type StageEvent,
  type StageField,
  type StagedContent,
} from "../../../shell/ledgerStage";
import { useStrings, type Translate } from "../../../shell/strings";
import { categoryOption, vocabularyEmpty } from "../movements/movementWords";
import {
  useFieldSuggestions,
  useVocabulary,
} from "../suggestions/SuggestionsProvider";
import { pointsText } from "./editingModel";
import { fieldName } from "./editingWords";
import type { LockProgress } from "./useLedgerApply";
import { lockProgress, titleOf } from "./reviewLabels";

// ---- Needs you first -------------------------------------------------------

type Held = { id: string; blocker: PlanBlocker; draft: boolean };

/** What the review offers for one kind of problem, acting on every movement
 * it holds. */
function BlockerFixes({
  port,
  kind,
  held,
  content,
  rows,
  onStage,
  onShowRows,
  onGoToDraft,
  onRereadSealed,
  checking,
  shareRefusal,
}: {
  kind: PlanBlocker["kind"];
  held: Held[];
  content: StagedContent;
  rows: ReadonlyMap<string, LedgerRow>;
  onStage: (event: StageEvent) => void;
  onShowRows: (ids: string[], fields?: readonly string[]) => void;
  onGoToDraft: (key: string) => void;
  /** Reads again the sealed state the review could not read. */
  onRereadSealed: () => void;
  /** That read is under way. */
  checking: boolean;
  port: LedgerPort;
  /** The sentence the check served for a share no percentage reads. */
  shareRefusal: LedgerPlan["shareRefusal"];
}) {
  const t = useStrings();
  const [share, setShare] = useState("");
  const [shareRefused, setShareRefused] = useState(false);
  const shareError = shareRefused ? (shareRefusal?.words ?? null) : null;
  const [currency, setCurrency] = useState("");
  const currencies = useFieldSuggestions("currency");
  const ids = held.filter((entry) => !entry.draft).map((entry) => entry.id);
  const vocabulary = useVocabulary();
  const categories = useMemo<ComboboxOption[]>(
    () =>
      vocabulary.categoryFamilies.flatMap(([family, members]) =>
        members.map((member) => categoryOption(t, family, member)),
      ),
    [t, vocabulary],
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
  const classifyAll = async (
    kind: "business" | "personal",
    category?: string,
  ) => {
    const check = await checkOnce(
      port,
      stagedCheckRequest(content, rows, {
        ids,
        categories: category ? [category] : [],
      }),
    );
    if (!check) return;
    const outcome = classifyCells({ kind, ids, category, check }, rows);
    if (outcome.kind === "staged") onStage(outcome.event);
  };
  const show = ids.length
    ? button(t("desktop.ledger.apply.fix.show"), () => onShowRows(ids), "show")
    : null;
  /** Shows the movements the blocker holds, with the columns it names: the
   * person's own column choice, or a preset, may be hiding one of them. */
  const showFields = () => {
    const fields = held.flatMap((entry) =>
      "fields" in entry.blocker ? [...entry.blocker.fields] : [],
    );
    const draft = held.find((entry) => entry.draft);
    return (
      <>
        {ids.length
          ? button(
              t("desktop.ledger.apply.fix.show_fields"),
              () => onShowRows(ids, fields),
              "show-fields",
            )
          : null}
        {draft
          ? button(
              t("desktop.ledger.apply.fix.go_to_draft"),
              () => onGoToDraft(draft.id),
              "go-to-draft",
            )
          : null}
      </>
    );
  };
  switch (kind) {
    case "amount_signed":
    case "needs_withholding_category":
      return showFields();
    case "needs_classification":
      return (
        <>
          <Combobox
            label={t("desktop.ledger.classify.category")}
            value={null}
            options={categories}
            emptyLabel={vocabularyEmpty(
              t,
              vocabulary,
              t("desktop.ledger.classify.no_category_match"),
              categories.length,
            )}
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
            const parsed = parsePercent(pointsText(share));
            if (parsed.kind !== "value") {
              setShareRefused(true);
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
          <PercentEditor
            unit="points"
            controlSize="sm"
            className="w-24"
            aria-label={t("desktop.ledger.classify.share")}
            invalid={shareRefused ? true : undefined}
            value={share}
            onChange={(held) => {
              setShare(held);
              setShareRefused(false);
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
    case "sealed_unread":
      return (
        <>
          <Button
            key="reread-sealed"
            variant="outline"
            size="xs"
            className="ledger-fix-reread-sealed"
            aria-disabled={checking || undefined}
            onClick={() => !checking && onRereadSealed()}
          >
            {checking ? <Spinner /> : <Icon name="sync" />}
            {t("desktop.ledger.paused.reread")}
          </Button>
          {button(
            t("desktop.ledger.apply.fix.drop_changes"),
            dropEdits(false),
            "drop-changes",
          )}
        </>
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
              <CurrencyEditor
                controlSize="sm"
                className="w-24"
                aria-label={t("desktop.ledger.field.currency")}
                value={currency}
                onChange={setCurrency}
                {...currencies}
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

/** The sentence the backend served for why a blocker holds the work back,
 * for the kinds it words; null for the kinds the window words itself. */
const servedWords = (blocker: PlanBlocker): string | null =>
  "words" in blocker ? blocker.words : null;

/** The sentence the backend served for what puts the blocker right. */
const servedFix = (blocker: PlanBlocker): string | null =>
  "fixWords" in blocker ? blocker.fixWords : null;

function blockerFields(t: Translate, blocker: PlanBlocker): string | null {
  const fields =
    "fields" in blocker
      ? (blocker.fields as (StageField | DraftField | string)[])
      : null;
  if (!fields?.length) return null;
  return listed(
    t,
    fields.map((field) =>
      field === "m210_income_classification"
        ? t("desktop.ledger.field.m210_income_classification")
        : fieldName(t, field as StageField),
    ),
  );
}

export function NeedsYouFirst({
  port,
  plan,
  content,
  rows,
  onStage,
  onShowRows,
  onGoToDraft,
  onRereadSealed,
  locks,
  locale,
}: {
  port: LedgerPort;
  plan: LedgerPlan;
  content: StagedContent;
  rows: ReadonlyMap<string, LedgerRow>;
  onStage: (event: StageEvent) => void;
  onShowRows: (ids: string[], fields?: readonly string[]) => void;
  onGoToDraft: (key: string) => void;
  onRereadSealed: () => void;
  /** While the locks not read are read again, how far it has got. */
  locks: LockProgress | null;
  locale: string;
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
                {servedWords(held[0]!.blocker) ??
                  t(`desktop.ledger.apply.blocker.${kind}`, {
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
                onRereadSealed={onRereadSealed}
                port={port}
                checking={locks !== null}
                shareRefusal={plan.shareRefusal}
              />
            </div>
            {kind === "sealed_unread" && locks && (
              <p
                role="status"
                className="ledger-locks-progress flex items-center gap-2 text-sm text-muted-foreground"
              >
                <Spinner />
                {lockProgress(t, locale, locks)}
              </p>
            )}
            {servedFix(held[0]!.blocker) && (
              <p className="text-sm text-muted-foreground">
                {servedFix(held[0]!.blocker)}
              </p>
            )}
            {fields && (
              <p className="text-sm text-muted-foreground">
                {t("desktop.ledger.apply.blocker_fields", { fields })}
              </p>
            )}
            <p className="text-sm text-muted-foreground">
              {facts(t, [
                ...held
                  .slice(0, 4)
                  .map((entry) =>
                    entry.draft
                      ? draftTitle(entry.id)
                      : titleOf(t, rows, entry.id),
                  ),
                held.length > 4 &&
                  t("desktop.ledger.apply.more", { count: held.length - 4 }),
              ])}
            </p>
          </div>
        );
      })}
    </section>
  );
}
