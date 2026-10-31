import { useMemo, useState, type ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Icon } from "@/components/ui/icon";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio";
import { facts } from "@/shell/compose";
import type {
  CatalogueInvoice,
  InvoiceListResult,
  LedgerRow,
} from "../../../shell/ledger";
import type { StageEvent, StagedAction } from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { seriesAndNumber } from "../invoices/invoiceModel";
import { paymentLabel } from "../invoices/invoiceWords";
import {
  linkPicker,
  reconcile,
  stageLink,
  tiedInvoices,
  tiedMovements,
  type MatchPair,
} from "../matching/matchingModel";
import { chipText, invoiceLine, settlesText } from "../matching/matchingWords";
import type { InspectorRead } from "./useInspectorReads";
import { formatAmount } from "../../../shared/numbers";
import { formatDay } from "../../../shared/dateFormats";

/**
 * The inspector's Invoice section: the invoice the movement is linked to,
 * or its one best suggestion with the evidence it stands on, a chooser when
 * candidates tie, and a picker for any other invoice. A link is permanent:
 * it cannot be removed here, so every link button says so, and staging one
 * takes its invoice from every other movement's suggestions.
 */
export function InvoiceSection({
  row,
  rows,
  invoices,
  actions,
  allActions,
  onStage,
  locale,
  onShow,
  onOpenInvoice,
  say,
}: {
  row: LedgerRow;
  /** The window's movements, for suggestions one to one. */
  rows: readonly LedgerRow[];
  invoices: InspectorRead<InvoiceListResult> | null;
  /** What is staged on this movement. */
  actions: readonly StagedAction[];
  /** What is staged on every movement. */
  allActions: readonly StagedAction[];
  onStage: (event: StageEvent) => void;
  locale: string;
  onShow: (id: string) => void;
  onOpenInvoice: (invoiceId: string) => void;
  say: (text: string) => void;
}) {
  const t = useStrings();
  const tx = row.transaction;
  const id = tx.transaction_id;
  const catalogue = useMemo(
    () => (invoices?.kind === "ready" ? invoices.result.invoices : null),
    [invoices],
  );
  const found = useMemo(
    () => (catalogue ? reconcile(rows, catalogue, allActions) : null),
    [rows, catalogue, allActions],
  );
  const [choice, setChoice] = useState<string | null>(null);
  const [others, setOthers] = useState(false);
  const staged = actions.find(
    (action): action is Extract<StagedAction, { kind: "link" }> =>
      action.kind === "link",
  );
  const byId = useMemo(
    () =>
      new Map(rows.map((entry) => [entry.transaction.transaction_id, entry])),
    [rows],
  );
  const lock =
    tx.lifecycle_state === "ACTIVE"
      ? null
      : t("desktop.ledger.inspector.invoice.active_only");

  const link = (invoice: CatalogueInvoice) => {
    onStage(stageLink(id, invoice.invoice_id));
    say(t("desktop.ledger.inspector.invoice.link_staged"));
  };
  const linkButton = (invoice: CatalogueInvoice, size: "sm" | "xs" = "sm") => (
    <Button size={size} disabled={lock !== null} onClick={() => link(invoice)}>
      <Icon name="link" />
      {t("desktop.ledger.inspector.invoice.link")}
    </Button>
  );
  const card = (pair: MatchPair, actionsSlot?: ReactNode) => (
    <div className="ledger-invoice-suggestion grid gap-1.5 rounded-md bg-accent p-2.5">
      <p className="flex flex-wrap items-baseline gap-2 text-sm">
        <span className="font-medium">{seriesAndNumber(pair.invoice)}</span>
        <span className="min-w-0 flex-1 text-muted-foreground">
          {pair.invoice.counterparty_name}
        </span>
      </p>
      <p className="text-sm text-muted-foreground">
        {invoiceLine(t, locale, pair.invoice)}
      </p>
      <p className="text-sm tabular-nums">
        {settlesText(t, locale, pair.invoice, pair.settles)}
      </p>
      <ul
        className="flex flex-wrap gap-1"
        aria-label={t("desktop.ledger.inspector.invoice.evidence")}
      >
        {pair.chips.map((chip, at) => (
          <li key={at}>
            <Badge variant="neutral">{chipText(t, chip)}</Badge>
          </li>
        ))}
      </ul>
      {actionsSlot && <div className="flex flex-wrap gap-2">{actionsSlot}</div>}
    </div>
  );

  if (tx.direction === "INTERNAL_TRANSFER")
    return (
      <p className="text-sm text-muted-foreground">
        {t("desktop.ledger.inspector.invoice.transfer")}
      </p>
    );

  const permanent = (
    <p className="flex items-center gap-1 text-xs text-muted-foreground">
      <Icon name="lock" size="xs" />
      {t("desktop.ledger.inspector.invoice.permanent")}
    </p>
  );

  if (tx.invoice_id !== null) {
    const invoice = catalogue?.find(
      (entry) => entry.invoice_id === tx.invoice_id,
    );
    return (
      <div className="grid gap-2">
        {invoice ? (
          <div className="ledger-linked-invoice grid gap-1.5 rounded-md bg-accent p-2.5">
            <p className="flex flex-wrap items-baseline gap-2 text-sm">
              <Icon name="link" size="xs" />
              <span className="font-medium">{seriesAndNumber(invoice)}</span>
              <Badge variant="neutral">
                {invoice.kind === "issued"
                  ? t("desktop.ledger.inspector.invoice.issued")
                  : t("desktop.ledger.inspector.invoice.received")}
              </Badge>
              <span className="ml-auto font-medium tabular-nums">
                {formatAmount(locale, invoice.grand_total.decimal)}{" "}
                {invoice.currency}
              </span>
            </p>
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-sm">
              <dt className="text-muted-foreground">
                {t("desktop.ledger.inspector.invoice.counterparty")}
              </dt>
              <dd className="break-words">{invoice.counterparty_name}</dd>
              <dt className="text-muted-foreground">
                {t("desktop.ledger.inspector.invoice.issued_on")}
              </dt>
              <dd>{formatDay(locale, invoice.issued_at)}</dd>
              <dt className="text-muted-foreground">
                {t("desktop.ledger.inspector.invoice.payment")}
              </dt>
              <dd>{paymentLabel(t, invoice.payment_status)}</dd>
              <dt className="text-muted-foreground">
                {t("desktop.ledger.inspector.invoice.linked")}
              </dt>
              <dd>
                {t("desktop.ledger.inspector.invoice.linked_count", {
                  count: invoice.linked_transaction_ids.length,
                })}
              </dd>
            </dl>
            <Button
              variant="outline"
              size="sm"
              className="w-fit"
              onClick={() => onOpenInvoice(invoice.invoice_id)}
            >
              {t("desktop.ledger.inspector.invoice.open")}
            </Button>
          </div>
        ) : (
          <p className="text-sm">
            {invoices?.kind === "failed"
              ? t("desktop.ledger.inspector.unread")
              : t("desktop.ledger.loading")}
          </p>
        )}
        {permanent}
      </div>
    );
  }

  const suggestion = found?.best.get(id) ?? null;
  const tied = suggestion ? tiedInvoices(suggestion) : [];
  const rivals = suggestion ? tiedMovements(suggestion) : [];
  const picker = catalogue ? linkPicker(row, catalogue, allActions) : null;
  // An invoice that settles this movement but is staged for another.
  const taken =
    !suggestion && !staged
      ? (picker?.settles.find((option) => option.stagedFor !== null) ?? null)
      : null;
  const options: ComboboxOption[] = picker
    ? [
        ...picker.settles.map((option) => ({
          option,
          group: "settles" as const,
        })),
        ...picker.other.map((option) => ({ option, group: "other" as const })),
      ].map(({ option, group }) => {
        const holder = option.stagedFor
          ? byId.get(option.stagedFor)
          : undefined;
        return {
          value: option.invoice.invoice_id,
          label: facts(t, [
            seriesAndNumber(option.invoice),
            option.invoice.counterparty_name,
            formatAmount(locale, option.invoice.grand_total.decimal),
          ]),
          group:
            group === "settles"
              ? t("desktop.ledger.inspector.invoice.group_settles")
              : t("desktop.ledger.inspector.invoice.group_other"),
          disabled: option.stagedFor !== null,
          ...(option.stagedFor
            ? {
                reason: t("desktop.ledger.inspector.invoice.staged_for", {
                  movement:
                    holder?.transaction.description ??
                    option.stagedFor.slice(0, 12),
                }),
              }
            : option.linked > 0
              ? {
                  note: t("desktop.ledger.inspector.invoice.already_linked", {
                    count: option.linked,
                  }),
                }
              : {}),
        };
      })
    : [];

  return (
    <div className="grid gap-2">
      {lock && <Alert icon={<Icon name="lock" />}>{lock}</Alert>}
      {staged ? (
        <Alert icon={<Icon name="link" />} role="status">
          <span className="grid gap-1">
            {t("desktop.ledger.inspector.invoice.staged", {
              invoice: (() => {
                const invoice = catalogue?.find(
                  (entry) => entry.invoice_id === staged.invoiceId,
                );
                return invoice
                  ? seriesAndNumber(invoice)
                  : staged.invoiceId.slice(0, 12);
              })(),
            })}
            <Button
              variant="link"
              size="xs"
              className="w-fit"
              onClick={() => onStage({ type: "drop_action", id: staged.id })}
            >
              {t("desktop.ledger.inspector.drop")}
            </Button>
          </span>
        </Alert>
      ) : found === null ? (
        <p role="status" className="text-sm text-muted-foreground">
          {invoices?.kind === "failed"
            ? t("desktop.ledger.inspector.unread")
            : t("desktop.ledger.loading")}
        </p>
      ) : tied.length > 0 ? (
        <div className="grid gap-2">
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {t("desktop.ledger.inspector.invoice.ambiguous")}
          </Alert>
          <RadioGroup
            aria-label={t("desktop.ledger.inspector.invoice.candidates")}
            className="gap-2"
            value={choice ?? ""}
            onValueChange={setChoice}
          >
            {tied.map((pair) => (
              <label
                key={pair.invoice.invoice_id}
                className="flex items-start gap-2"
              >
                <RadioGroupItem
                  value={pair.invoice.invoice_id}
                  className="mt-3"
                />
                <span className="min-w-0 flex-1">{card(pair)}</span>
              </label>
            ))}
          </RadioGroup>
          <Button
            size="sm"
            className="w-fit"
            disabled={choice === null || lock !== null}
            onClick={() => {
              const invoice = tied.find(
                (pair) => pair.invoice.invoice_id === choice,
              )?.invoice;
              if (invoice) link(invoice);
            }}
          >
            <Icon name="link" />
            {t("desktop.ledger.inspector.invoice.link")}
          </Button>
        </div>
      ) : suggestion ? (
        <div className="grid gap-2">
          {rivals.length > 0 && (
            <Alert tone="warning" icon={<Icon name="alert" />}>
              {t("desktop.ledger.inspector.invoice.rival", {
                movement: rivals[0]!.row.transaction.description,
              })}
            </Alert>
          )}
          {card(
            suggestion,
            <>
              {linkButton(suggestion.invoice)}
              {rivals[0] && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    onShow(rivals[0]!.row.transaction.transaction_id)
                  }
                >
                  {t("desktop.ledger.inspector.invoice.show_other")}
                </Button>
              )}
            </>,
          )}
          {suggestion.others.length > 0 && (
            <Button
              variant="link"
              size="xs"
              className="w-fit"
              aria-expanded={others}
              onClick={() => setOthers((open) => !open)}
            >
              {t("desktop.ledger.inspector.invoice.other_candidates", {
                count: suggestion.others.length,
              })}
            </Button>
          )}
          {others &&
            suggestion.others.map((pair) => (
              <div key={pair.invoice.invoice_id}>
                {card(pair, linkButton(pair.invoice, "xs"))}
              </div>
            ))}
        </div>
      ) : taken ? (
        <Alert icon={<Icon name="link" />}>
          <span className="grid gap-1">
            {t("desktop.ledger.inspector.invoice.taken", {
              invoice: seriesAndNumber(taken.invoice),
              movement:
                byId.get(taken.stagedFor!)?.transaction.description ??
                taken.stagedFor!.slice(0, 12),
            })}
            <Button
              variant="link"
              size="xs"
              className="w-fit"
              onClick={() => onShow(taken.stagedFor!)}
            >
              {t("desktop.ledger.inspector.show")}
            </Button>
          </span>
        </Alert>
      ) : (
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.inspector.invoice.none")}
        </p>
      )}
      {!staged && catalogue && (
        <Combobox
          label={t("desktop.ledger.inspector.invoice.pick")}
          value={null}
          className="w-dialog-md"
          options={options}
          emptyLabel={t("desktop.ledger.inspector.no_match")}
          footer={
            <p className="px-2 text-xs text-muted-foreground">
              {t("desktop.ledger.inspector.invoice.partial_hint")}
            </p>
          }
          onCommit={(chosen) => {
            const invoice = catalogue.find(
              (entry) => entry.invoice_id === chosen,
            );
            if (invoice) link(invoice);
          }}
        >
          <Button
            variant="outline"
            size="sm"
            className="w-fit"
            disabled={lock !== null}
          >
            {t("desktop.ledger.inspector.invoice.pick")}
            <Icon name="chevronDown" size="xs" />
          </Button>
        </Combobox>
      )}
      {permanent}
    </div>
  );
}
