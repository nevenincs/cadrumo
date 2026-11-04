import { Toast } from "@/components/ui/toast";
import { readPeriodHoldingSpan } from "../../shell/ledgerPeriods";
import { useStrings } from "../../shell/strings";
import type { LedgerPageProps } from "./LedgerPage";
import { ReadinessStrip } from "./movements/ReadinessStrip";
import { NO_FILTERS, TO_CLASSIFY_REASON } from "./movements/movementsModel";
import { RuleDialog } from "./setup/RuleDialog";
import { ExportDialog } from "./transfer/ExportDialog";
import { ImportDialog } from "./transfer/ImportDialog";
import type { LedgerPageState } from "./useLedgerPage";

/** Rule, import and export dialogs retain the page's staged-work and focus callbacks. */
export function LedgerPageDialogs({
  props,
  model,
}: {
  props: LedgerPageProps;
  model: LedgerPageState;
}) {
  const t = useStrings();
  const { port, reader, locale, view, onViewChange, copy } = props;
  const {
    period,
    setPeriod,
    setSection,
    readable,
    movements,
    reread,
    readiness,
    recheckReadiness,
    transfer,
    setTransfer,
    returnTransferFocus,
    inspectorContext,
    setShownImport,
    years,
    refreshYears,
    fallbackYear,
    shownPeriod,
    editing,
    ruleTarget,
    setRuleTarget,
    setRulesVersion,
    toast,
    setToast,
    setupProps,
    shownWindow,
    pageSets,
  } = model;
  // Export shows the page's own pills for the page's period, so that both
  // count the same movements; a pill there filters the grid to them.
  const exportReadiness =
    transfer === "export" && shownWindow ? (
      <ReadinessStrip
        readiness={readiness}
        sets={pageSets}
        filters={movements.filters}
        locale={locale}
        unsaved={editing.tally.units}
        stagedClassify={0}
        periodName={shownPeriod}
        onCheck={recheckReadiness}
        onPill={(filter) => {
          if (!filter) return;
          movements.setFilters({ ...NO_FILTERS, readiness: filter });
          setSection("movements");
          setTransfer(null);
        }}
        onReason={(reason) => {
          if (!reason) return;
          movements.setFilters(
            reason === TO_CLASSIFY_REASON
              ? { ...NO_FILTERS, readiness: "to_classify" }
              : { ...NO_FILTERS, reason },
          );
          setSection("movements");
          setTransfer(null);
        }}
      />
    ) : undefined;

  return (
    <>
      {readable && editing.dock}
      {readable && ruleTarget && (
        <RuleDialog
          port={port}
          reader={reader}
          target={ruleTarget}
          rows={setupProps.rows}
          onStage={editing.onStage}
          onSaved={(_rule, place) => {
            setRulesVersion((value) => value + 1);
            setRuleTarget(null);
            setToast(t("desktop.ledger.rules.saved_toast", { place }));
          }}
          onClose={() => setRuleTarget(null)}
          // Opened from the grid, it hands the keyboard back to the grid's
          // active cell; the Rules section's own opener takes it otherwise.
          onClosed={
            ruleTarget.kind === "seed"
              ? () => inspectorContext?.focusActive()
              : undefined
          }
        />
      )}
      {readable && transfer === "import" && (
        <ImportDialog
          port={port}
          locale={locale}
          period={period}
          years={years}
          fallbackYear={fallbackYear}
          onClose={() => setTransfer(null)}
          onWritten={() => {
            reread();
            refreshYears();
          }}
          onShowImported={(shown) => {
            setShownImport(shown);
            setSection("movements");
            // The period that holds the imported days is the backend's to
            // name; where it names none, or cannot be read, every period is
            // shown rather than one made up.
            void readPeriodHoldingSpan(shown.span).then((held) =>
              setPeriod(held ? held.period : null),
            );
          }}
          onShowDocuments={() => setSection("documents")}
          onCloseAutoFocus={returnTransferFocus}
        />
      )}
      {readable && transfer === "export" && (
        <ExportDialog
          port={port}
          locale={locale}
          period={period}
          years={years}
          fallbackYear={fallbackYear}
          format={view.exportFormat}
          onFormat={(exportFormat) =>
            onViewChange((current) => ({ ...current, exportFormat }))
          }
          staged={editing.tally.units}
          onReviewStaged={editing.openReview}
          readiness={exportReadiness}
          copy={copy}
          onClose={() => setTransfer(null)}
          onCloseAutoFocus={returnTransferFocus}
        />
      )}
      <Toast className="ledger-page-toast">{toast}</Toast>
    </>
  );
}
