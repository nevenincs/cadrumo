import type { RefObject } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Icon } from "@/components/ui/icon";
import { facts } from "../../../shell/compose";
import type { LedgerRow } from "../../../shell/ledger";
import type { EvidenceConfirmResult } from "../../../shell/ledgerDocumentOperations";
import type { InvoiceMatchView } from "../../../shell/ledgerInvoiceMatch";
import type { StageEvent, StagedAction } from "../../../shell/ledgerStage";
import { useStrings } from "../../../shell/strings";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount } from "../../../shared/numbers";
import { seriesAndNumber } from "../invoices/invoiceModel";
import {
  remapMatches,
  remapMovementChoices,
  stageLink,
  stagedLinks,
} from "../matching/matchingModel";
import { invoiceLine } from "../matching/matchingWords";

/**
 * A confirmed reading: the invoice it became, what differs from what was
 * printed, and its link to a movement, offered when the ledger has one and
 * otherwise found among the movements near its day.
 */
export function ConfirmedReading({
  rootRef,
  linkRef,
  confirmed,
  rows,
  linkMatches,
  actions,
  locale,
  onStage,
  onLinkStaged,
  say,
}: {
  rootRef: RefObject<HTMLDivElement | null>;
  /** The offered link's button, focused when it arrives in time. */
  linkRef(button: HTMLButtonElement | null): void;
  confirmed: EvidenceConfirmResult;
  rows: LedgerRow[] | null;
  linkMatches: InvoiceMatchView;
  actions: StagedAction[];
  locale: string;
  onStage(event: StageEvent): void;
  onLinkStaged(): void;
  say(text: string): void;
}) {
  const t = useStrings();
  const invoice = confirmed.confirmation.invoice;
  const staged = stagedLinks(actions);
  const offer =
    rows && linkMatches.kind === "answer"
      ? (remapMatches(linkMatches.result, rows, [invoice]).list[0] ?? null)
      : null;
  const linkStaged = staged.invoices.get(invoice.invoice_id);
  // With no movement that settles it, the movements near its day are
  // offered instead, those that settle its amount first.
  const nearby =
    rows &&
    !offer &&
    linkMatches.kind === "answer" &&
    linkMatches.result.movement_choices !== null
      ? remapMovementChoices(linkMatches.result.movement_choices, rows)
      : null;
  return (
    <div
      ref={rootRef}
      tabIndex={-1}
      className="ledger-draft-confirmed grid content-start gap-3 p-3"
    >
      <Alert tone="success" icon={<Icon name="check" />}>
        <AlertTitle>
          {confirmed.confirmation.created
            ? t("desktop.ledger.documents.confirmed", {
                number: seriesAndNumber(invoice),
              })
            : t("desktop.ledger.documents.already_confirmed", {
                number: seriesAndNumber(invoice),
              })}
        </AlertTitle>
        <AlertDescription>{invoiceLine(t, locale, invoice)}</AlertDescription>
      </Alert>
      {confirmed.confirmation.total_discrepancy && (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {t("desktop.ledger.documents.printed_differs", {
            printed: formatAmount(
              locale,
              confirmed.confirmation.total_discrepancy.printed_total.decimal,
            ),
            recorded: formatAmount(
              locale,
              confirmed.confirmation.total_discrepancy.recorded_total.decimal,
            ),
          })}
        </Alert>
      )}
      {confirmed.confirmation.retention_discrepancy && (
        <Alert
          tone="warning"
          icon={<Icon name="alert" />}
          className="ledger-draft-retention-differs"
        >
          {confirmed.confirmation.retention_discrepancy.recorded_amount
            ? t("desktop.ledger.documents.retention_differs", {
                read: formatAmount(
                  locale,
                  confirmed.confirmation.retention_discrepancy.read_amount
                    .decimal,
                ),
                recorded: formatAmount(
                  locale,
                  confirmed.confirmation.retention_discrepancy.recorded_amount
                    .decimal,
                ),
              })
            : t("desktop.ledger.documents.retention_unrecorded", {
                read: formatAmount(
                  locale,
                  confirmed.confirmation.retention_discrepancy.read_amount
                    .decimal,
                ),
              })}
        </Alert>
      )}
      {linkStaged ? (
        <Alert icon={<Icon name="lock" />} className="ledger-draft-link-staged">
          {t("desktop.ledger.matching.staged_toast")}
        </Alert>
      ) : nearby ? (
        <Alert icon={<Icon name="link" />} className="ledger-draft-no-match">
          <AlertTitle>{t("desktop.ledger.documents.no_movement")}</AlertTitle>
          <AlertDescription className="grid gap-2">
            <span>{t("desktop.ledger.inspector.invoice.permanent")}</span>
            <Combobox
              label={t("desktop.ledger.documents.find_movement")}
              value={null}
              className="w-dialog-md"
              options={nearby.map((option): ComboboxOption => ({
                value: option.row.transaction.transaction_id,
                label: facts(t, [
                  option.row.transaction.description,
                  formatDay(locale, option.row.transaction.date),
                  formatAmount(locale, option.row.transaction.amount),
                ]),
                group: option.settles
                  ? t("desktop.ledger.inspector.invoice.group_settles")
                  : t("desktop.ledger.documents.group_near", {
                      days:
                        linkMatches.kind === "answer"
                          ? linkMatches.result.window_days
                          : 0,
                    }),
              }))}
              emptyLabel={t("desktop.ledger.inspector.no_match")}
              onCommit={(chosen) => {
                onStage(stageLink(chosen, invoice.invoice_id));
                say(t("desktop.ledger.matching.staged_toast"));
                onLinkStaged();
              }}
            >
              <Button
                size="xs"
                variant="outline"
                className="ledger-draft-find-movement w-fit"
              >
                {t("desktop.ledger.documents.find_movement")}
                <Icon name="chevronDown" size="xs" />
              </Button>
            </Combobox>
          </AlertDescription>
        </Alert>
      ) : (
        offer && (
          <Alert
            icon={<Icon name="link" />}
            className="ledger-draft-link-offer"
          >
            <AlertTitle>{t("desktop.ledger.documents.link_offer")}</AlertTitle>
            <AlertDescription className="grid gap-2">
              <span>
                {t("desktop.ledger.documents.link_offer_note", {
                  description: offer.row.transaction.description,
                  date: formatDay(locale, offer.row.transaction.date),
                  amount: formatAmount(locale, offer.row.transaction.amount),
                })}
              </span>
              <span>
                <Button
                  size="xs"
                  variant="outline"
                  className="ledger-match-link"
                  ref={linkRef}
                  onClick={() => {
                    onStage(
                      stageLink(
                        offer.row.transaction.transaction_id,
                        invoice.invoice_id,
                      ),
                    );
                    say(t("desktop.ledger.matching.staged_toast"));
                    onLinkStaged();
                  }}
                >
                  <Icon name="lock" size="xs" />
                  {t("desktop.ledger.matching.link")}
                </Button>
              </span>
            </AlertDescription>
          </Alert>
        )
      )}
    </div>
  );
}
