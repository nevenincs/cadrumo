import { useId, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { formatDay } from "../../../shared/dateFormats";
import { formatDecimal, formatPercent } from "../../../shared/numbers";
import { facts } from "../../../shell/compose";
import type { ElectionLimits, LegalCitation } from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { ASSET_KEYS, fieldWord, tokenWord } from "./assetsWords";

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 [overflow-wrap:anywhere] tabular-nums">
        {children}
      </dd>
    </>
  );
}

/** The provisions behind the limits, behind a disclosure with their count,
 * each as its own text. Where the window can open an address, the text is a
 * link to the official publication. A list the backend could not resolve whole
 * says so, with or without a list to show. */
function Citations({
  citations,
  complete,
  onOpenLink,
}: {
  citations: readonly LegalCitation[];
  complete: boolean;
  onOpenLink?: (url: string) => void;
}) {
  const t = useStrings();
  const list = useId();
  const [open, setOpen] = useState(false);
  const text = ASSET_KEYS.plan.limits;
  const partial = !complete && (
    <p className="ledger-assets-citations-partial flex items-start gap-1 text-xs text-muted-foreground">
      <Icon name="alert" size="xs" className="mt-0.5" />
      <span>{t(text.citations_partial)}</span>
    </p>
  );
  if (citations.length === 0) return partial || null;
  return (
    <div className="ledger-assets-citations flex flex-col gap-1">
      <Button
        variant="ghost"
        size="xs"
        className="-ms-2 w-fit"
        aria-expanded={open}
        aria-controls={list}
        onClick={() => setOpen(!open)}
      >
        <Icon name={open ? "chevronUp" : "chevronDown"} size="xs" />
        {t(text.citations, { count: citations.length })}
      </Button>
      <ul id={list} hidden={!open} className="flex flex-col gap-0.5 ps-4">
        {citations.map((citation) => (
          <li
            key={`${citation.text}\u0000${citation.permalink}`}
            className="[overflow-wrap:anywhere]"
          >
            {onOpenLink ? (
              <Button
                variant="link"
                size="xs"
                className="h-auto min-w-0 p-0 text-start whitespace-normal text-primary"
                // The window never leaves the app: the address opens in the browser.
                onClick={() => onOpenLink(citation.permalink)}
              >
                {citation.text}
                <Icon name="external" size="xs" />
              </Button>
            ) : (
              citation.text
            )}
          </li>
        ))}
      </ul>
      {partial}
    </div>
  );
}

/** What the registry allows the element's election: a table method's class
 * and corridor, or the limit it has instead and why. Each figure is the
 * backend's; a limit it does not state is not drawn. */
export function AmortizationLimits({
  locale,
  limits,
  onOpenLink,
}: {
  locale: string;
  limits: ElectionLimits;
  onOpenLink?: (url: string) => void;
}) {
  const t = useStrings();
  const text = ASSET_KEYS.plan.limits;
  const why = limits.unavailable_reason_words ?? null;
  return (
    <section
      aria-label={t(text.title)}
      className="ledger-assets-limits flex flex-col gap-1 border-b px-3 py-2 text-sm"
    >
      <h4 className="font-medium">{t(text.title)}</h4>
      {limits.not_table_bound !== null && (
        <p className="text-muted-foreground">
          {facts(t, [
            tokenWord(t, "not_table_bound", limits.not_table_bound),
            why,
          ])}
        </p>
      )}
      <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-0.5">
        {limits.class_label !== null && (
          <Fact label={fieldWord(t, "amortization.authority_class_key")}>
            {limits.class_label}
          </Fact>
        )}
        {limits.maximum_coefficient !== null && (
          <Fact label={t(text.maximum_coefficient)}>
            {formatPercent(locale, limits.maximum_coefficient.decimal, {
              unit: "fraction",
            })}
          </Fact>
        )}
        {limits.minimum_coefficient !== null && (
          <Fact label={t(text.minimum_coefficient)}>
            {formatPercent(locale, limits.minimum_coefficient.decimal, {
              unit: "fraction",
            })}
          </Fact>
        )}
        {limits.maximum_period_years !== null && (
          <Fact label={t(text.maximum_period)}>
            {t(text.period_years, {
              years: formatDecimal(locale, limits.maximum_period_years.decimal),
            })}
          </Fact>
        )}
        {limits.maximum_period_last_day !== null && (
          <Fact label={t(text.ends_on)}>
            {formatDay(locale, limits.maximum_period_last_day)}
          </Fact>
        )}
      </dl>
      <Citations
        citations={limits.legal_citations}
        complete={limits.legal_citations_complete}
        onOpenLink={onOpenLink}
      />
    </section>
  );
}
