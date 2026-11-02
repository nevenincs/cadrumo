import { useMemo } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount } from "../../../shared/numbers";
import type {
  InventoryBook,
  InventoryAdvisory,
  InventoryMovement,
} from "../../../shell/ledgerSetup";
import { useStrings, type Translate } from "../../../shell/strings";
import { Panel, SetupTable } from "../setup/SetupParts";
import { historyRows, type HistoryFact } from "./stockHistory";
import { wordFrom, wordOf, type Offers } from "./stockVocabulary";
import { movementLine } from "./stockWords";

// ---- What a book holds ------------------------------------------------------------------

/** A fact of the history, in words. */
function factText(t: Translate, locale: string, fact: HistoryFact): string {
  switch (fact.kind) {
    case "opening":
      return t("desktop.ledger.stock.fact.opening", {
        value: formatAmount(locale, fact.value),
      });
    case "method":
      return t("desktop.ledger.stock.fact.method", {
        value: wordOf(t, "valuation_method", fact.value),
      });
    case "label":
      return t("desktop.ledger.stock.fact.label", { value: fact.value });
    case "description":
      return fact.value
        ? t("desktop.ledger.stock.fact.description", { value: fact.value })
        : t("desktop.ledger.stock.fact.no_description");
    case "movement":
      return movementLine(t, locale, fact.value);
    case "removed":
      return t("desktop.ledger.stock.fact.removed");
  }
}

function FactList({
  facts: list,
  locale,
}: {
  facts: readonly HistoryFact[];
  locale: string;
}) {
  const t = useStrings();
  if (list.length === 0) return <span aria-hidden="true">—</span>;
  return (
    <>
      {list.map((fact, at) => (
        <span key={at} className="block">
          {factText(t, locale, fact)}
        </span>
      ))}
    </>
  );
}

/** The changes of a book, newest first: when, what, why, and what each
 * displaced and left in its place. */
export function History({
  ledger,
  locale,
  name,
  offers,
}: {
  offers: Offers;
  ledger: InventoryBook;
  locale: string;
  name: string;
}) {
  const t = useStrings();
  const rows = useMemo(() => historyRows(ledger), [ledger]);
  if (rows.length === 0)
    return (
      <p className="ledger-stock-history-note text-sm text-muted-foreground">
        {t("desktop.ledger.stock.history_none")}
      </p>
    );
  return (
    <SetupTable
      label={t("desktop.ledger.stock.history_of", { name })}
      rows={rows}
      rowKey={(row) => String(row.position)}
      className="ledger-stock-history"
      columns={[
        {
          key: "when",
          label: t("desktop.ledger.stock.history.when"),
          sort: (row) => row.position,
          cell: (row) => formatDay(locale, row.day),
        },
        {
          key: "what",
          label: t("desktop.ledger.stock.history.what"),
          cell: (row) => wordFrom(t, offers, "history_kind", row.kind),
        },
        {
          key: "reason",
          label: t("desktop.ledger.stock.history.reason"),
          cell: (row) =>
            row.reason === null
              ? "—"
              : row.reason.family === "correction"
                ? wordFrom(t, offers, "correction_reason", row.reason.token)
                : wordFrom(t, offers, "retirement_reason", row.reason.token),
        },
        {
          key: "before",
          label: t("desktop.ledger.stock.history.before"),
          cell: (row) => <FactList facts={row.before} locale={locale} />,
        },
        {
          key: "after",
          label: t("desktop.ledger.stock.history.after"),
          cell: (row) => <FactList facts={row.after} locale={locale} />,
        },
      ]}
    />
  );
}

// ---- What a purchase came to -------------------------------------------------------

/** The family every sentence the backend serves as an advisory belongs to. */
const ADVISORY_FAMILY = "application.inventory.advisories.";

type FactLine = { key: string; label: string; value: string };

/** A purchase as the backend keeps it: the price, each extra cost, what the
 * backend added up, and the kinds of document it rests on. Every figure is
 * read from what the backend served; none is worked out here. */
export function PurchaseFacts({
  movement,
  locale,
  onClose,
}: {
  movement: InventoryMovement;
  locale: string;
  onClose(): void;
}) {
  const t = useStrings();
  const cost = movement.acquisition_cost ?? null;
  const detail = movement.acquisition_detail ?? null;
  const money = (value: { decimal: string }) =>
    formatAmount(locale, value.decimal);
  const lines: FactLine[] = [];
  if (cost !== null) {
    lines.push({
      key: "price",
      label: t("desktop.ledger.stock.facts.price"),
      value: money(cost.consideration_excluding_iva),
    });
    if (detail !== null) {
      lines.push({
        key: "iva",
        label: t("desktop.ledger.stock.facts.iva"),
        value: money(detail.consideration_iva_amount),
      });
      for (const component of detail.components)
        lines.push({
          key: component.component_id,
          label: wordOf(t, "attributable_cost_kind", component.kind),
          value: money(component.taxable_base),
        });
    }
    lines.push(
      {
        key: "extra_total",
        label: t("desktop.ledger.stock.facts.extra_total"),
        value: money(cost.directly_attributable_cost_total),
      },
      {
        key: "recoverable",
        label: t("desktop.ledger.stock.facts.recoverable"),
        value: money(cost.recoverable_iva_excluded),
      },
      {
        key: "unrecoverable",
        label: t("desktop.ledger.stock.facts.unrecoverable"),
        value: money(cost.nonrecoverable_iva_included),
      },
      {
        key: "total",
        label: t("desktop.ledger.stock.facts.total"),
        value: money(cost.total_acquisition_cost),
      },
    );
  }
  return (
    <Panel
      title={t("desktop.ledger.stock.facts.title", {
        date: formatDay(locale, movement.movement_date),
      })}
      className="ledger-stock-form ledger-stock-purchase"
    >
      <div className="flex flex-col gap-3">
        {cost === null ? (
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.stock.facts.unknown")}
          </p>
        ) : (
          <SetupTable
            label={t("desktop.ledger.stock.facts.table")}
            rows={lines}
            rowKey={(line) => line.key}
            className="ledger-stock-purchase-lines"
            columns={[
              {
                key: "what",
                label: t("desktop.ledger.stock.facts.what"),
                cell: (line) => line.label,
              },
              {
                key: "amount",
                label: t("desktop.ledger.stock.facts.amount"),
                numeric: true,
                cell: (line) => line.value,
              },
            ]}
          />
        )}
        <section className="flex flex-col gap-1">
          <h4 className="font-medium">
            {t("desktop.ledger.stock.facts.documents")}
          </h4>
          {detail === null || detail.documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.stock.facts.documents_unknown")}
            </p>
          ) : (
            <ul className="ledger-stock-documents text-sm">
              {detail.documents.map((document) => (
                <li
                  key={`${document.reference}|${document.evidence_kind}`}
                  className="flex items-center gap-1"
                >
                  <Icon name="attach" size="sm" />
                  {t("desktop.ledger.stock.facts.document", {
                    kind: wordOf(
                      t,
                      "acquisition_evidence_kind",
                      document.evidence_kind,
                    ),
                    name:
                      document.file_name ??
                      t("desktop.ledger.stock.proof.kept"),
                  })}
                </li>
              ))}
            </ul>
          )}
        </section>
        <div className="flex">
          <Button type="button" size="sm" variant="ghost" onClick={onClose}>
            {t("desktop.ledger.form.close")}
          </Button>
        </div>
      </div>
    </Panel>
  );
}

/** What the backend says about a book that the person should know, said in
 * its own sentence with the year filled in. A sentence it has no words for
 * is left out rather than shown as a key. */
export function Advisories({
  advisories,
  className,
}: {
  advisories: readonly InventoryAdvisory[] | undefined;
  className: string;
}) {
  const t = useStrings();
  const said = (advisories ?? []).flatMap((advisory) => {
    if (!advisory.key.startsWith(ADVISORY_FAMILY)) return [];
    const sentence = t(advisory.key, { year: advisory.year });
    return sentence === advisory.key ? [] : [{ advisory, sentence }];
  });
  if (said.length === 0) return null;
  return (
    <>
      {said.map(({ advisory, sentence }) => (
        <Alert
          key={`${advisory.code}|${advisory.year}`}
          tone="warning"
          icon={<Icon name="alert" />}
          className={className}
        >
          {sentence}
        </Alert>
      ))}
    </>
  );
}
