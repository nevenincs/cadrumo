import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { formatDay } from "../../shared/dateFormats";
import { formatCount } from "../../shared/numbers";
import { shownRows, windowProgress } from "../../shell/ledgerWindow";
import { useStrings } from "../../shell/strings";
import { HeldButton } from "./LedgerHeader";
import type { LedgerPageProps } from "./LedgerPage";
import { AssetsSection } from "./assets/AssetsSection";
import { StockPane } from "./assets/StockPane";
import { DocumentsSection } from "./documents/DocumentsSection";
import { InvoicesSection } from "./invoices/InvoicesSection";
import { SECTION_ICONS, sectionName } from "./ledgerWords";
import { MovementsSection } from "./movements/MovementsSection";
import { NO_FILTERS, TO_CLASSIFY_REASON } from "./movements/movementsModel";
import { HealthSection } from "./setup/HealthSection";
import { RegistersSection } from "./setup/RegistersSection";
import { RulesSection } from "./setup/RulesSection";
import type { LedgerPageState } from "./useLedgerPage";

/** Draws the selected ledger section without owning page state. */
export function LedgerPageBody({
  props,
  model,
}: {
  props: LedgerPageProps;
  model: LedgerPageState;
}) {
  const t = useStrings();
  const {
    port,
    reader,
    withheld,
    locale,
    shown,
    view,
    onViewChange,
    memory,
    copy,
    paste,
    onOpenLink,
  } = props;
  const {
    period,
    setPeriod,
    section,
    setSection,
    rulesArea,
    counterpartyAsk,
    openRatios,
    linkedMovement,
    linkedInvoice,
    movements,
    periodWindow,
    reread,
    readAll,
    stage,
    registerMovements,
    readiness,
    recheckReadiness,
    invoiceEditor,
    setInvoiceEditor,
    setInspectorContext,
    openInspector,
    shownImport,
    setShownImport,
    refreshYears,
    shownPeriod,
    importAction,
    sealed,
    focusDraft,
    setFocusDraft,
    shownFields,
    setShownFields,
    editing,
    setRuleTarget,
    rulesVersion,
    openRuleFromSelection,
    setupProps,
    addAction,
  } = model;
  let body: ReactNode;
  if (reader === null || periodWindow === null) body = withheld;
  else if (section === "invoices")
    body = (
      <InvoicesSection
        port={port}
        reader={reader}
        locale={locale}
        period={period}
        shown={shown}
        editor={invoiceEditor}
        onEditor={setInvoiceEditor}
        copy={copy}
        onPeriod={setPeriod}
        linked={linkedInvoice}
      />
    );
  else if (section === "rules")
    body = (
      <RulesSection
        {...setupProps}
        onOpenRule={setRuleTarget}
        rulesVersion={rulesVersion}
        initialArea={rulesArea}
        counterpartyAsk={counterpartyAsk}
      />
    );
  else if (section === "registers")
    body = (
      <RegistersSection
        {...setupProps}
        initialArea={memory.current.registersArea}
      />
    );
  else if (section === "assets")
    body = (
      <AssetsSection
        port={setupProps.port}
        reader={setupProps.reader}
        locale={setupProps.locale}
        stock={<StockPane {...setupProps} />}
        onOpenLink={onOpenLink}
      />
    );
  else if (section === "health")
    body = (
      <HealthSection
        {...setupProps}
        readiness={readiness}
        onShowReadiness={(filter) => {
          movements.setFilters({ ...NO_FILTERS, readiness: filter });
          setSection("movements");
        }}
        onShowReason={(reason) => {
          // A movement still to classify is its own filter, not a reason.
          movements.setFilters(
            reason === TO_CLASSIFY_REASON
              ? { ...NO_FILTERS, readiness: "to_classify" }
              : { ...NO_FILTERS, reason },
          );
          setSection("movements");
        }}
        onShowInvoices={() => setSection("invoices")}
        onReset={() => {
          reread();
          refreshYears();
        }}
      />
    );
  else if (section === "documents")
    body = (
      <DocumentsSection
        port={port}
        reader={reader}
        locale={locale}
        shown={shown}
        rows={shownRows(periodWindow)?.rows ?? null}
        stage={stage}
        onStage={editing.onStage}
      />
    );
  else if (section !== "movements")
    body = (
      <EmptyState
        className="ledger-placeholder"
        icon={SECTION_ICONS[section]}
        heading={sectionName(t, section)}
      />
    );
  else if (periodWindow.phase === "failed" && periodWindow.failure)
    body = (
      <EmptyState
        className="ledger-failed"
        icon="alert"
        description={
          <span key={periodWindow.generation} role="alert">
            {t("desktop.ledger.failed")}
          </span>
        }
      >
        <Button variant="outline" onClick={reread}>
          {t("desktop.ledger.retry")}
        </Button>
      </EmptyState>
    );
  else {
    const rows = shownRows(periodWindow);
    const progress = windowProgress(periodWindow);
    const reading =
      progress.total === null
        ? t("desktop.ledger.loading")
        : t("desktop.ledger.reading", {
            loaded: formatCount(locale, progress.loaded),
            total: formatCount(locale, progress.total),
          });
    if (rows === null)
      body = (
        <EmptyState
          className="ledger-loading"
          role="status"
          busy
          description={reading}
        />
      );
    else if (rows.total === 0 && stage.content.drafts.length === 0)
      body = (
        <EmptyState
          className="ledger-empty"
          icon="ledger"
          description={
            period === null
              ? t("desktop.ledger.empty_all")
              : t("desktop.ledger.empty", { period: shownPeriod })
          }
        >
          <div className="flex flex-wrap justify-center gap-2">
            <HeldButton
              action={importAction}
              name={t("desktop.ledger.action.import")}
            >
              <Icon name="upload" />
              {t("desktop.ledger.action.import")}
            </HeldButton>
            <HeldButton
              action={addAction}
              name={t("desktop.ledger.action.add_movement")}
            >
              <Icon name="plus" />
              {t("desktop.ledger.action.add")}
            </HeldButton>
          </div>
        </EmptyState>
      );
    else
      body = (
        <>
          {shownImport && (
            <p className="ledger-shown-import flex flex-wrap items-center gap-2 px-3 pt-3 text-sm">
              {t("desktop.ledger.import.shown", {
                from: formatDay(locale, shownImport.span.from),
                to: formatDay(locale, shownImport.span.to),
              })}
              <Button
                variant="link"
                size="xs"
                onClick={() => setShownImport(null)}
              >
                {t("desktop.ledger.import.shown_clear")}
              </Button>
            </p>
          )}
          <MovementsSection
            port={port}
            reader={reader}
            period={period}
            periodWindow={periodWindow}
            readAll={readAll}
            readiness={readiness}
            onCheckReadiness={recheckReadiness}
            movements={movements}
            stage={stage}
            onStage={editing.onStage}
            editing={{
              openReview: editing.openReview,
              focusDraft,
              onDraftFocused: () => setFocusDraft(null),
              shownFields,
              onFieldsShown: () => setShownFields(null),
              sealed,
            }}
            view={view}
            onViewChange={onViewChange}
            locale={locale}
            onPeriod={setPeriod}
            register={registerMovements}
            onMakeRule={openRuleFromSelection}
            onOpenRatios={openRatios}
            onOpenInspector={(at) => openInspector(at)}
            onInspector={setInspectorContext}
            shownImport={shownImport}
            onImportCleared={() => setShownImport(null)}
            linked={linkedMovement}
            copy={copy}
            paste={paste}
          />
        </>
      );
  }

  return body;
}
