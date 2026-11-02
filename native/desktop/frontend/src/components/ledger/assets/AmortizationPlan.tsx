import { Alert } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icon";
import type { LedgerPort } from "../../../shell/ledger";
import type { ListDisposal } from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { CallLine, Reading } from "../setup/SetupParts";
import { AmortizationLimits } from "./AmortizationLimits";
import { AmortizationTable } from "./AmortizationTable";
import {
  ASSET_KEYS,
  bajaText,
  refusalText,
  keyedText,
  tokenWord,
} from "./assetsWords";
import { readPlan, useAssetRead } from "./planRead";
import { PLAN_KEYS } from "./planWords";

// One element's amortization plan, a row for each tax year it has. The plan
// is current: it answers what the schedule allows now and what is recorded as
// effective, every figure as the backend states it. Nothing here adds,
// subtracts or derives a date; a figure the backend does not state is a mark
// that says it is not known and why, never zero. The election's method is drawn
// once, on the divider where it starts, and the table scrolls inside its own
// frame with the year pinned, so a narrow panel loses no figure.

/**
 * One element's plan, read from the ledger, with the limits the registry puts
 * on its election above it. `year` is the year the pane stands on, which the
 * plan scrolls to and marks. The element's history is read beside it, only to
 * mark a claim in effect that no longer matches the figures.
 */
export function AmortizationPlan({
  port,
  assetId,
  locale,
  year = null,
  reader,
  onOpenLink,
  onCorrectClaim,
  onCorrectElement,
  disposal = null,
}: {
  port: LedgerPort;
  assetId: string;
  locale: string;
  /** The baja the element's current revision records, said above the plan. */
  disposal?: ListDisposal | null;
  year?: number | null;
  /** Whose ledger; null while the account withholds it. */
  reader?: string | null;
  /** Opens an official address in the system browser. */
  onOpenLink?: (url: string) => void;
  /** Asks to correct one claim of a year; offered on each claim in effect. */
  onCorrectClaim?: (claimId: string, year: number) => void;
  /** Opens the form that corrects the element, where a figure says which
   * entry to fill in. */
  onCorrectElement?: () => void;
}) {
  const t = useStrings();
  const { read } = useAssetRead(readPlan, port, reader, assetId);
  if (read === null) return <Reading label={t(PLAN_KEYS.reading)} />;
  if (read.kind !== "done") return <CallLine call={read} />;
  const { outcome, refusal, rows, limits, advisories } = read.result;
  if (outcome === "refused" || rows === null)
    return (
      <div className="p-3">
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-assets-plan-refused"
        >
          {refusalText(t, refusal)}
        </Alert>
      </div>
    );
  if (rows.length === 0)
    return (
      <p className="p-3 text-sm text-muted-foreground">
        {t(PLAN_KEYS.plan_empty)}
      </p>
    );
  const estimated = rows.some((row) => row.edition?.projected);
  const unrecorded = rows.some(
    (row) => row.claim_state === "missing" || row.claim_state === "partial",
  );
  return (
    <>
      {(advisories.length > 0 || estimated || unrecorded) && (
        <div className="flex flex-col gap-2 border-b p-3">
          {advisories.map((advisory) => (
            <Alert
              key={advisory.kind}
              icon={<Icon name="info" />}
              className="ledger-assets-advisory"
            >
              {keyedText(
                t,
                advisory.label_key,
                tokenWord(t, "plan_advisory", advisory.kind),
              )}
            </Alert>
          ))}
          {estimated && (
            <Alert
              icon={<Icon name="calendar" />}
              className="ledger-assets-estimated"
            >
              {t(ASSET_KEYS.plan.projected_summary)}
            </Alert>
          )}
          {unrecorded && (
            <Alert
              icon={<Icon name="info" />}
              className="ledger-assets-unrecorded"
            >
              {t("desktop.ledger.assets.plan.unrecorded_note")}
            </Alert>
          )}
        </div>
      )}
      {limits && (
        <AmortizationLimits
          locale={locale}
          limits={limits}
          onOpenLink={onOpenLink}
        />
      )}
      {disposal !== null && (
        <p className="ledger-assets-baja flex items-center gap-1.5 border-b px-3 py-2 text-sm">
          <Icon name="archive" size="xs" className="shrink-0" />
          {bajaText(t, locale, disposal)}
        </p>
      )}
      <AmortizationTable
        locale={locale}
        rows={rows}
        year={year}
        onCorrectClaim={onCorrectClaim}
        onCorrectElement={onCorrectElement}
      />
    </>
  );
}
