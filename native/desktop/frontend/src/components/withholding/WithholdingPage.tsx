import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { NativeSelect } from "@/components/ui/native-select";
import { Spinner } from "@/components/ui/spinner";
import { useScrolls } from "@/components/ui/useScrolls";
import { localDay } from "../../shared/dates";
import type { LedgerPort } from "../../shell/ledger";
import { readPeriodsHolding } from "../../shell/ledgerPeriods";
import type { RetencionSoportadaAmountColumnProjection } from "../../shell/ledgerWithholdingContract";
import { useStrings } from "../../shell/strings";
import { useSetupRead } from "../ledger/setup/SetupParts";
import { PaneHeader, type PaneControl } from "../PaneHeader";
import {
  AbsencesTable,
  Block,
  Reading,
  RecordsTable,
  Unavailable,
} from "./WithholdingTables";

const NO_COLUMNS: readonly RetencionSoportadaAmountColumnProjection[] = [];

/**
 * The withholding payers took from the person's income, one ejercicio at a
 * time, drawn from what the ledger serves and nothing else: each payer's
 * certificate figures under the words and amount columns it served, and the
 * statements that an income class had none, active and withdrawn. The
 * ejercicios on offer are the ones the list serves. Each list keeps its own
 * standing, so a failed read says so with its code and is never drawn as an
 * empty list, nor read again but by the person. Recording, removing and
 * stating a change stay with the Ledger, which the page opens.
 */
export function WithholdingPage({
  port,
  reader,
  locale,
  page,
  pane,
  withheld,
  onOpenLedger,
}: {
  port: LedgerPort;
  /** Whose withholding it is; null while the account withholds it. */
  reader: string | null;
  /** The chrome language, for amounts and dates. */
  locale: string;
  /** The page's own element, for whoever sends focus to it. */
  page?: RefObject<HTMLElement | null>;
  /** The pane's controls, which the page's header carries. */
  pane: { controls: PaneControl[]; onToggleMaximize: () => void };
  /** What stands in the page while the account withholds it: the account's
   * own account of why, and the ways on. */
  withheld?: ReactNode;
  /** Opens where the certificates are recorded and changed. */
  onOpenLedger: () => void;
}) {
  const t = useStrings();
  const own = useRef<HTMLElement>(null);
  const root = page ?? own;
  const [bodyEl, setBodyEl] = useState<HTMLElement | null>(null);
  const scrolls = useScrolls(bodyEl);

  // The ejercicio read first is the year that holds today as the ledger
  // serves it, else, where that could not be read, the calendar year the
  // window is in, as the Ledger's own withholding register opens on. Nothing
  // is read until it is known. Once the list serves the ejercicios, the
  // person chooses among them.
  const [current, setCurrent] = useState<number | null>(null);
  useEffect(() => {
    if (reader === null) return;
    let wanted = true;
    const day = localDay();
    void readPeriodsHolding(day).then((served) => {
      if (wanted)
        setCurrent(served ? served.annual.year : Number(day.slice(0, 4)));
    });
    return () => {
      wanted = false;
      setCurrent(null);
    };
  }, [reader]);
  const [chosen, setChosen] = useState<number | null>(null);
  const ejercicio = chosen ?? current;

  const { read: records, reload: readRecords } = useSetupRead(
    port,
    reader,
    "ledger.retencion_soportada.list",
    ejercicio === null ? null : { ejercicio },
    `withholding:${ejercicio}`,
  );
  const { read: absences, reload: readAbsences } = useSetupRead(
    port,
    reader,
    "ledger.retencion_soportada.list_absences",
    ejercicio === null ? null : { ejercicio },
    `withholding-absences:${ejercicio}`,
  );
  const refresh = () => {
    readRecords();
    readAbsences();
  };

  // The ejercicios the list was last served with: kept while another is
  // being read, and when a read of one is refused.
  const [ejercicios, setEjercicios] = useState<readonly number[] | null>(null);
  useEffect(() => {
    if (records?.kind === "done") setEjercicios(records.result.ejercicios);
  }, [records]);

  const rows = records?.kind === "done" ? records.result.rows : [];
  const amountColumns =
    records?.kind === "done" ? records.result.amount_columns : NO_COLUMNS;
  const attestations =
    absences?.kind === "done" ? absences.result.attestations : [];
  const active = attestations.filter((found) => found.state === "active");
  const withdrawn = attestations.filter((found) => found.state === "withdrawn");
  const reading = reader !== null && (records === null || absences === null);
  // Known to hold nothing: both lists answered and both are empty.
  const empty =
    records?.kind === "done" &&
    absences?.kind === "done" &&
    rows.length === 0 &&
    attestations.length === 0;

  const options = ejercicios ?? (ejercicio === null ? [] : [ejercicio]);
  const offered = ejercicio !== null && options.includes(ejercicio);

  return (
    <section
      ref={root}
      tabIndex={-1}
      aria-label={t("desktop.withholding.title")}
      aria-busy={reading || undefined}
      className="withholding-page @container/withholding relative flex min-h-0 flex-1 flex-col bg-background outline-none"
    >
      <PaneHeader
        title={t("desktop.withholding.title")}
        controls={pane.controls}
        onToggleMaximize={pane.onToggleMaximize}
      >
        <NativeSelect
          controlSize="sm"
          className="w-24"
          aria-label={t("desktop.withholding.ejercicio")}
          value={offered ? String(ejercicio) : ""}
          disabled={reader === null || ejercicios === null}
          onChange={(event) => setChosen(Number(event.target.value))}
        >
          {!offered && <option value="" disabled hidden />}
          {options.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </NativeSelect>
        <span className="flex-1" />
        <Button
          variant="outline"
          size="sm"
          className="withholding-open-ledger"
          disabled={reader === null}
          onClick={onOpenLedger}
        >
          <Icon name="ledger" size="sm" />
          {t("desktop.withholding.change")}
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={reader === null || reading}
          onClick={refresh}
        >
          {reading ? <Spinner /> : <Icon name="sync" size="sm" />}
          {t("desktop.withholding.refresh")}
        </Button>
      </PaneHeader>
      <div
        ref={setBodyEl}
        tabIndex={scrolls ? 0 : undefined}
        role={scrolls ? "group" : undefined}
        aria-label={scrolls ? t("desktop.withholding.title") : undefined}
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-y-auto",
          scrolls &&
            "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
        )}
      >
        {reader === null ? (
          (withheld ?? (
            <EmptyState
              icon="lock"
              heading={t("desktop.account.signed_out")}
              description={t("desktop.withholding.signed_out")}
            />
          ))
        ) : (
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-3 p-4">
            <p className="text-sm text-muted-foreground">
              {t("desktop.withholding.what")}
            </p>
            {empty ? (
              <p
                data-withholding-empty=""
                className="text-sm text-muted-foreground"
              >
                {t("desktop.withholding.empty", {
                  ejercicio: records.result.ejercicio,
                })}
              </p>
            ) : (
              <>
                <Block
                  name="records"
                  heading={t("desktop.withholding.records.title")}
                >
                  {records === null ? (
                    <Reading label={t("desktop.withholding.loading")} />
                  ) : records.kind !== "done" ? (
                    <Unavailable call={records} onReadAgain={readRecords} />
                  ) : rows.length === 0 ? (
                    <p
                      data-withholding-empty="records"
                      className="text-sm text-muted-foreground"
                    >
                      {t("desktop.withholding.records.empty", {
                        ejercicio: records.result.ejercicio,
                      })}
                    </p>
                  ) : (
                    <RecordsTable
                      rows={rows}
                      amountColumns={amountColumns}
                      locale={locale}
                    />
                  )}
                </Block>
                <Block
                  name="absences"
                  heading={t("desktop.withholding.absences.title")}
                >
                  {absences === null ? (
                    <Reading label={t("desktop.withholding.loading")} />
                  ) : absences.kind !== "done" ? (
                    <Unavailable call={absences} onReadAgain={readAbsences} />
                  ) : (
                    <>
                      {active.length === 0 ? (
                        <p
                          data-withholding-empty="absences"
                          className="text-sm text-muted-foreground"
                        >
                          {t("desktop.withholding.absences.empty", {
                            ejercicio: absences.result.ejercicio,
                          })}
                        </p>
                      ) : (
                        <AbsencesTable
                          rows={active}
                          withdrawn={false}
                          label={t("desktop.withholding.absences.title")}
                          locale={locale}
                        />
                      )}
                      {withdrawn.length > 0 && (
                        <section
                          data-withholding="withdrawn"
                          className="flex flex-col gap-2"
                        >
                          <h4 className="text-sm font-medium text-muted-foreground">
                            {t("desktop.withholding.absences.history")}
                          </h4>
                          <AbsencesTable
                            rows={withdrawn}
                            withdrawn
                            label={t("desktop.withholding.absences.history")}
                            locale={locale}
                          />
                        </section>
                      )}
                    </>
                  )}
                </Block>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
