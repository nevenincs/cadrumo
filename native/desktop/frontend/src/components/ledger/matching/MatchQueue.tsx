import { useEffect, useId, useMemo, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Toast } from "@/components/ui/toast";
import type {
  LedgerPort,
  LedgerRow,
  LedgerStatusResult,
} from "../../../shell/ledger";
import type { StageEvent, StageState } from "../../../shell/ledgerStage";
import { useStrings, type Translate } from "../../../shell/strings";
import { figureText } from "../invoices/invoiceWords";
import { seriesAndNumber } from "../invoices/invoiceModel";
import { failureCode } from "../ledgerWords";
import { dayText } from "../transfer/transferWords";
import {
  inconsistencies,
  reconcile,
  stageLink,
  stagedLinks,
  tiedInvoices,
  tiedMovements,
  type LinkInconsistency,
  type MatchPair,
  type MatchSuggestion,
} from "./matchingModel";
import {
  chipText,
  directionText,
  invoiceLine,
  noRepairText,
  settlesText,
} from "./matchingWords";
import { useMatchingFacts, type Facts } from "./useMatchingFacts";

const TOAST_MS = 4000;
/** How many evidence chips a queue item shows; the rest are in its
 * accessible description. */
const SHOWN_CHIPS = 2;

export type AffectedDeclaration = LedgerStatusResult["stale_filings"][number];

const movementAmount = (locale: string, row: LedgerRow) =>
  `${figureText(locale, row.transaction.amount)} ${row.transaction.currency}`;

function Chips({ t, pair }: { t: Translate; pair: MatchPair }) {
  return (
    <span className="flex flex-wrap gap-1">
      {pair.chips.slice(0, SHOWN_CHIPS).map((chip) => (
        <Badge key={chip.kind} className="ledger-match-chip">
          {chipText(t, chip)}
        </Badge>
      ))}
    </span>
  );
}

function PairLine({
  t,
  locale,
  pair,
}: {
  t: Translate;
  locale: string;
  pair: MatchPair;
}) {
  return (
    <span className="grid gap-0.5 text-sm">
      <span className="text-muted-foreground">
        {invoiceLine(t, locale, pair.invoice)}
      </span>
      <span className="text-muted-foreground tabular-nums">
        {settlesText(t, locale, pair.invoice, pair.settles)}
      </span>
    </span>
  );
}

function LinkButton({
  t,
  pair,
  onLink,
  size = "xs",
}: {
  t: Translate;
  pair: MatchPair;
  onLink(pair: MatchPair): void;
  size?: "xs" | "sm";
}) {
  return (
    <Button
      size={size}
      variant="outline"
      className="ledger-match-link"
      aria-label={t("desktop.ledger.matching.link_named", {
        number: seriesAndNumber(pair.invoice),
        description: pair.row.transaction.description,
      })}
      onClick={() => onLink(pair)}
    >
      <Icon name="lock" size="xs" />
      {t("desktop.ledger.matching.link")}
    </Button>
  );
}

function MatchItem({
  t,
  locale,
  suggestion,
  onLink,
  onChoose,
}: {
  t: Translate;
  locale: string;
  suggestion: MatchSuggestion;
  onLink(pair: MatchPair): void;
  onChoose(transactionId: string): void;
}) {
  const [choosing, setChoosing] = useState(false);
  const [chosen, setChosen] = useState<string | null>(null);
  const [showOthers, setShowOthers] = useState(false);
  const group = useId();
  const row = suggestion.row;
  const id = row.transaction.transaction_id;
  const invoices = tiedInvoices(suggestion);
  const rivals = tiedMovements(suggestion);
  const others = suggestion.others.filter(
    (other) =>
      !invoices.some(
        (tie) => tie.invoice.invoice_id === other.invoice.invoice_id,
      ),
  );
  return (
    <li
      className="ledger-match-item grid gap-1.5 border-b border-border px-3 py-2"
      data-transaction={id}
      data-ambiguous={suggestion.ambiguous || undefined}
    >
      <button
        type="button"
        className="ledger-match-pick grid w-full cursor-pointer gap-1 rounded-md text-left hover-wash focus-visible:outline-offset-2"
        onClick={() => onChoose(id)}
        aria-label={t("desktop.ledger.matching.open_named", {
          description: row.transaction.description,
          amount: movementAmount(locale, row),
          number: seriesAndNumber(suggestion.invoice),
        })}
      >
        <span className="flex min-w-0 items-baseline gap-2">
          <span className="min-w-0 flex-1 truncate font-medium">
            {row.transaction.description}
          </span>
          <span className="tabular-nums">{movementAmount(locale, row)}</span>
        </span>
        <span className="text-sm text-muted-foreground tabular-nums">
          {dayText(locale, row.transaction.date)}
        </span>
        <span className="text-sm">
          {invoiceLine(t, locale, suggestion.invoice)}
        </span>
        <span className="flex flex-wrap items-center gap-1">
          {suggestion.ambiguous && (
            <Badge variant="warning" className="ledger-match-ambiguous">
              {t("desktop.ledger.matching.ambiguous")}
            </Badge>
          )}
          <Chips t={t} pair={suggestion} />
        </span>
      </button>
      {!suggestion.ambiguous && (
        <div className="flex flex-wrap items-center gap-2">
          <LinkButton t={t} pair={suggestion} onLink={onLink} />
        </div>
      )}
      {suggestion.ambiguous && invoices.length > 0 && (
        <div className="grid gap-1.5">
          <Button
            size="xs"
            variant="outline"
            className="ledger-match-choose w-fit"
            aria-expanded={choosing}
            onClick={() => setChoosing(!choosing)}
          >
            {t("desktop.ledger.matching.choose")}
          </Button>
          {choosing && (
            <fieldset className="ledger-match-chooser grid gap-1.5 rounded-md bg-muted p-2">
              <legend className="sr-only">
                {t("desktop.ledger.matching.choose_legend", {
                  description: row.transaction.description,
                })}
              </legend>
              <p className="text-sm">
                {t("desktop.ledger.matching.choose_note")}
              </p>
              {invoices.map((pair) => (
                <label
                  key={pair.invoice.invoice_id}
                  className="flex cursor-pointer items-start gap-2"
                >
                  <input
                    type="radio"
                    name={group}
                    className="mt-1 size-icon-sm shrink-0 accent-primary"
                    checked={chosen === pair.invoice.invoice_id}
                    onChange={() => setChosen(pair.invoice.invoice_id)}
                  />
                  <span className="grid gap-1">
                    <span className="font-medium">
                      {seriesAndNumber(pair.invoice)}
                    </span>
                    <PairLine t={t} locale={locale} pair={pair} />
                    <Chips t={t} pair={pair} />
                  </span>
                </label>
              ))}
              <Button
                size="xs"
                className="ledger-match-chosen w-fit"
                disabled={chosen === null}
                onClick={() => {
                  const pair = invoices.find(
                    (found) => found.invoice.invoice_id === chosen,
                  );
                  if (pair) onLink(pair);
                }}
              >
                <Icon name="lock" size="xs" />
                {t("desktop.ledger.matching.link")}
              </Button>
            </fieldset>
          )}
        </div>
      )}
      {suggestion.ambiguous && invoices.length === 0 && rivals.length > 0 && (
        <div className="grid gap-1.5">
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.matching.partial")}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <LinkButton t={t} pair={suggestion} onLink={onLink} />
            <Button
              size="xs"
              variant="ghost"
              className="ledger-match-rival"
              onClick={() =>
                onChoose(rivals[0]!.row.transaction.transaction_id)
              }
            >
              {t("desktop.ledger.matching.show_other", {
                description: rivals[0]!.row.transaction.description,
              })}
            </Button>
          </div>
        </div>
      )}
      {others.length > 0 && (
        <div className="grid gap-1">
          <Button
            size="xs"
            variant="link"
            className="ledger-match-others w-fit"
            aria-expanded={showOthers}
            onClick={() => setShowOthers(!showOthers)}
          >
            {t("desktop.ledger.matching.others", { count: others.length })}
          </Button>
          {showOthers && (
            <ul className="grid gap-1.5">
              {others.map((pair) => (
                <li
                  key={pair.invoice.invoice_id}
                  className="ledger-match-other grid gap-1 rounded-md bg-muted p-2"
                >
                  <span className="font-medium">
                    {seriesAndNumber(pair.invoice)}
                  </span>
                  <PairLine t={t} locale={locale} pair={pair} />
                  <Chips t={t} pair={pair} />
                  <div>
                    <LinkButton t={t} pair={pair} onLink={onLink} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

function Inconsistency({
  t,
  locale,
  item,
  staged,
  onRepair,
  onChoose,
}: {
  t: Translate;
  locale: string;
  item: LinkInconsistency;
  staged: boolean;
  onRepair(item: LinkInconsistency): void;
  onChoose(transactionId: string): void;
}) {
  return (
    <li
      className="ledger-match-inconsistency grid gap-1 border-b border-border px-3 py-2"
      data-direction={item.direction}
    >
      <span className="text-sm font-medium">
        {directionText(t, item.direction)}
      </span>
      <span className="text-sm">
        {item.row ? (
          <Button
            size="xs"
            variant="link"
            onClick={() => onChoose(item.transactionId)}
          >
            {item.row.transaction.description}
          </Button>
        ) : (
          <span className="font-mono text-xs">
            {item.transactionId.slice(0, 12)}
          </span>
        )}
        {" ↔ "}
        {item.invoice ? (
          invoiceLine(t, locale, item.invoice)
        ) : (
          <span className="font-mono text-xs">
            {item.invoiceId.slice(0, 12)}
          </span>
        )}
      </span>
      {staged ? (
        <span className="text-sm text-muted-foreground">
          {t("desktop.ledger.matching.repair_staged")}
        </span>
      ) : item.repair.kind === "link" ? (
        <div>
          <Button
            size="xs"
            variant="outline"
            className="ledger-match-repair"
            onClick={() => onRepair(item)}
          >
            <Icon name="lock" size="xs" />
            {t("desktop.ledger.matching.repair")}
          </Button>
        </div>
      ) : (
        <span className="ledger-match-no-repair text-sm text-muted-foreground">
          {noRepairText(t, item.repair.why)}
        </span>
      )}
    </li>
  );
}

function FailedRead({
  t,
  facts,
  onRetry,
}: {
  t: Translate;
  facts: Facts<unknown>;
  onRetry(): void;
}) {
  if (facts.phase !== "failed") return null;
  return (
    <Alert tone="danger" role="alert" icon={<Icon name="alert" />}>
      <AlertTitle>{t("desktop.ledger.matching.read_failed")}</AlertTitle>
      <AlertDescription className="flex flex-wrap items-center gap-2">
        <code className="font-mono text-xs">{failureCode(facts.failure)}</code>
        <Button size="xs" variant="outline" onClick={onRetry}>
          {t("desktop.ledger.retry")}
        </Button>
      </AlertDescription>
    </Alert>
  );
}

/**
 * The "To match" pair queue: each movement's one best invoice, the links
 * the two catalogues disagree about with a staged repair where a link
 * mends them, and the declarations the ledger has moved under. Linking
 * stages a permanent link in the page's changes; nothing is written here.
 */
export function MatchQueue({
  port,
  reader,
  shown,
  rows,
  generation,
  stage,
  onStage,
  onChoose,
  locale,
}: {
  port: LedgerPort;
  reader: string | null;
  shown: boolean;
  /** The period's movements as read, or null while they are not. */
  rows: LedgerRow[] | null;
  /** Which read of the movements `rows` is: a new one reads the rest
   * again. */
  generation: number | null;
  stage: StageState;
  onStage(event: StageEvent): void;
  /** Opens this movement's Invoice section in the same panel. */
  onChoose(transactionId: string): void;
  locale: string;
}) {
  const t = useStrings();
  const heading = useId();
  const { facts, reread } = useMatchingFacts(port, reader, shown, generation);
  const [toast, setToast] = useState<string | null>(null);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), TOAST_MS);
    return () => window.clearTimeout(timer);
  }, [toast]);
  const actions = stage.content.actions;
  const invoices = facts.invoices.value;
  const found = useMemo(
    () => (rows && invoices ? reconcile(rows, invoices, actions) : null),
    [rows, invoices, actions],
  );
  const oneSided = useMemo(
    () =>
      facts.inconsistencies.value && invoices
        ? inconsistencies(facts.inconsistencies.value, rows, invoices)
        : null,
    [facts.inconsistencies.value, rows, invoices],
  );
  const staged = stagedLinks(actions);
  const link = (transactionId: string, invoiceId: string) => {
    onStage(stageLink(transactionId, invoiceId));
    setToast(t("desktop.ledger.matching.staged_toast"));
  };
  const affected = facts.affected.value;

  let list;
  if (facts.invoices.phase === "failed")
    list = <FailedRead t={t} facts={facts.invoices} onRetry={reread} />;
  else if (found === null)
    list = (
      <EmptyState
        className="ledger-match-loading"
        role="status"
        busy
        description={t("desktop.ledger.loading")}
      />
    );
  else if (found.list.length === 0)
    list = (
      <p className="ledger-match-empty px-3 py-2 text-sm text-muted-foreground">
        {t("desktop.ledger.matching.empty")}
      </p>
    );
  else
    list = (
      <ul
        className="ledger-match-list"
        aria-label={t("desktop.ledger.matching.suggestions")}
      >
        {found.list.map((suggestion) => (
          <MatchItem
            key={suggestion.row.transaction.transaction_id}
            t={t}
            locale={locale}
            suggestion={suggestion}
            onLink={(pair) =>
              link(pair.row.transaction.transaction_id, pair.invoice.invoice_id)
            }
            onChoose={onChoose}
          />
        ))}
      </ul>
    );

  return (
    <section
      className="ledger-match-queue flex min-h-0 flex-1 flex-col"
      aria-labelledby={heading}
    >
      <div className="flex items-center gap-2 px-3 py-2">
        <h2 id={heading} className="text-base font-semibold">
          {t("desktop.ledger.matching.title")}
        </h2>
        {found && (
          <Badge
            className="ledger-match-count tabular-nums"
            aria-label={t("desktop.ledger.matching.count", {
              count: found.list.length,
            })}
          >
            {found.list.length}
          </Badge>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {staged.rows.size > 0 && (
          <p className="ledger-match-staged flex items-center gap-1 px-3 pb-1 text-sm text-muted-foreground">
            <Icon name="lock" size="xs" />
            {t("desktop.ledger.matching.staged", { count: staged.rows.size })}
          </p>
        )}
        {list}
        <section
          className="ledger-match-one-sided pt-3"
          aria-label={t("desktop.ledger.matching.one_sided")}
        >
          <h3 className="flex items-center gap-2 px-3 text-sm font-semibold">
            {t("desktop.ledger.matching.one_sided")}
            {oneSided && oneSided.length > 0 && (
              <Badge className="tabular-nums">{oneSided.length}</Badge>
            )}
          </h3>
          <FailedRead t={t} facts={facts.inconsistencies} onRetry={reread} />
          {oneSided && oneSided.length === 0 && (
            <p className="px-3 py-1 text-sm text-muted-foreground">
              {t("desktop.ledger.matching.one_sided_none")}
            </p>
          )}
          {oneSided && oneSided.length > 0 && (
            <ul>
              {oneSided.map((item) => (
                <Inconsistency
                  key={`${item.transactionId}:${item.invoiceId}`}
                  t={t}
                  locale={locale}
                  item={item}
                  staged={
                    staged.rows.get(item.transactionId) === item.invoiceId
                  }
                  onRepair={(repair) =>
                    link(repair.transactionId, repair.invoiceId)
                  }
                  onChoose={onChoose}
                />
              ))}
            </ul>
          )}
        </section>
        <section
          className="ledger-match-affected pt-3 pb-3"
          aria-label={t("desktop.ledger.matching.affected")}
        >
          <h3 className="flex items-center gap-2 px-3 text-sm font-semibold">
            {t("desktop.ledger.matching.affected")}
            {affected && affected.length > 0 && (
              <Badge className="tabular-nums">{affected.length}</Badge>
            )}
          </h3>
          <FailedRead t={t} facts={facts.affected} onRetry={reread} />
          {affected && affected.length === 0 && (
            <p className="px-3 py-1 text-sm text-muted-foreground">
              {t("desktop.ledger.matching.affected_none")}
            </p>
          )}
          {affected && affected.length > 0 && (
            <ul>
              {affected.map((declaration) => (
                <li
                  key={declaration.calculation_revision_id}
                  className="ledger-match-declaration flex flex-wrap items-center gap-2 border-b border-border px-3 py-2 text-sm"
                >
                  <span className="font-medium">
                    {t("desktop.ledger.matching.declaration", {
                      modelo: declaration.modelo,
                      year: declaration.filing_year,
                      period: declaration.period,
                    })}
                  </span>
                  <span className="text-muted-foreground tabular-nums">
                    {t("desktop.ledger.matching.declaration_changes", {
                      changed: declaration.changed_count,
                      removed: declaration.removed_count,
                    })}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      <Toast className="ledger-match-toast">{toast}</Toast>
    </section>
  );
}
