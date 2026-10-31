import { useMemo, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { LedgerCheckResult } from "../../../shell/ledger";
import { publicPeriod } from "../../../shell/ledgerGrammar";
import type {
  LedgerParticipationRebuildResult,
  LedgerResetResult,
} from "../../../shell/ledgerSetup";
import {
  checkReadiness,
  readinessSnapshot,
  type Readiness,
} from "../../../shell/ledgerWindow";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { stageTally } from "../editing/editingModel";
import { periodText } from "../ledgerWords";
import {
  NO_FILTERS,
  TO_CLASSIFY_REASON,
  readinessSets,
  stagedClassifyCount,
  type ReadinessFilter,
} from "../movements/movementsModel";
import { reasonShort } from "../movements/movementWords";
import { formatAmount, formatCount } from "../../../shared/numbers";
import { ReadinessStrip } from "../movements/ReadinessStrip";
import {
  CallLine,
  Panel,
  Reading,
  readLanding,
  TextField,
  useSetupRead,
  useSetupWrite,
} from "./SetupParts";
import type { SetupProps } from "./setupProps";
import { setupCall, type SetupCall } from "./setupModel";

const RESET_REASON_LIMIT = 500;
const NOT_CHECKED: Readiness = { kind: "not_checked" };
/** A group of counts: each label sits beside its number. */
const COUNTS = "grid grid-cols-[max-content_max-content] gap-x-4 gap-y-1";

/** The later of two readiness checks; one still running wins. */
function later(own: Readiness, page: Readiness): Readiness {
  if (own.kind === "checking") return own;
  const at = (readiness: Readiness) =>
    readinessSnapshot(readiness)?.checkedAt ?? -Infinity;
  return at(own) >= at(page) ? own : page;
}

/** How many issues name each reason, most first. */
function byReason(issues: readonly { reason: string }[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const issue of issues)
    counts.set(issue.reason, (counts.get(issue.reason) ?? 0) + 1);
  return [...counts].sort((a, b) => b[1] - a[1]);
}

/**
 * Setup › Health for the page's period: its counts and totals; what is
 * still missing before it can be calculated, said as the readiness strip
 * says it and opening on the page's last check, each pill and reason
 * opening the movements it counts; a check of the whole ledger; the
 * declarations calculated before their movements changed; rebuilding the
 * declaration links; and, set apart, resetting the ledger after a dry run.
 */
export function HealthSection({
  port,
  reader,
  locale,
  rows,
  stage,
  period,
  readiness,
  onShowReason,
  onShowReadiness,
  onShowInvoices,
  onReset,
}: SetupProps & {
  /** The page's readiness, as its strip shows it. */
  readiness?: Readiness;
  /** Opens Movements on the movements a readiness reason names. */
  onShowReason(reason: string): void;
  /** Opens Movements on the movements a readiness pill counts. */
  onShowReadiness?(filter: ReadinessFilter): void;
  onShowInvoices(): void;
  /** The ledger was reset, or may have been: the page reads it again. */
  onReset(): void;
}) {
  const t = useStrings();
  const count = (value: number) => formatCount(locale, value);
  const shown = periodText(t, locale, period);
  const key = period ? `${period.year}:${period.code}` : "all";
  const status = useSetupRead(
    port,
    reader,
    "ledger.status",
    { period: period ? publicPeriod(period) : null },
    key,
  );
  // A check asked for here, for this reader and period.
  const [own, setOwn] = useState<{ key: string; readiness: Readiness } | null>(
    null,
  );
  const [check, setCheck] = useState<SetupCall<LedgerCheckResult> | null>(null);
  const [checking, setChecking] = useState(false);
  const rebuild = useSetupWrite(
    t("desktop.ledger.health.links"),
    "ledger/health",
  );
  const [rebuilt, setRebuilt] =
    useState<LedgerParticipationRebuildResult | null>(null);
  const [reason, setReason] = useState("");
  // Resetting is rare and cannot be taken back: it stays folded until asked.
  const [resetOpen, setResetOpen] = useState(false);
  const [dryRun, setDryRun] = useState<{
    reason: string;
    call: SetupCall<LedgerResetResult>;
  } | null>(null);
  const resetting = useSetupWrite(
    t("desktop.ledger.section.health"),
    "ledger/health",
  );

  const ownKey = `${reader}:${key}`;
  const shownReadiness = later(
    own?.key === ownKey ? own.readiness : NOT_CHECKED,
    readiness ?? NOT_CHECKED,
  );
  const snapshot = readinessSnapshot(shownReadiness);
  const sets = useMemo(
    () => readinessSets(rows ?? [], snapshot),
    [rows, snapshot],
  );
  const checkingNow = shownReadiness.kind === "checking";
  const runReadiness = async () => {
    const asked = ownKey;
    const held = snapshot;
    setOwn({ key: asked, readiness: { kind: "checking", held } });
    const answer = await checkReadiness(port, period, Date.now);
    setOwn((current) =>
      current?.key !== asked
        ? current
        : {
            key: asked,
            readiness:
              answer.kind === "checked"
                ? answer
                : { kind: "failed", failure: answer.failure, held },
          },
    );
  };
  const runCheck = async () => {
    setChecking(true);
    setCheck(await setupCall(port, "ledger.check", {}, false));
    setChecking(false);
  };
  const runRebuild = async () => {
    const done = await rebuild.run(
      () => setupCall(port, "ledger.participation.rebuild", {}, true),
      // No read says whether a rebuild ran; it recomputes the declaration
      // links from what is stored, so run again it builds the same links.
      async () => "repeatable",
    );
    setRebuilt(done.kind === "done" ? done.result : null);
  };
  const runDryRun = async () => {
    const asked = reason.trim();
    resetting.clear();
    setDryRun({
      reason: asked,
      call: await setupCall(
        port,
        "ledger.reset",
        { reason: asked, dry_run: true },
        false,
      ),
    });
  };
  const runReset = async () => {
    if (!dryRun) return;
    const done = await resetting.run(
      () =>
        setupCall(
          port,
          "ledger.reset",
          { reason: dryRun.reason, dry_run: false },
          true,
        ),
      // A reset removes every movement: the whole ledger's count tells.
      readLanding(port, "ledger.status", { period: null }, (result) =>
        result.total_count === 0 ? "saved" : "not_saved",
      ),
    );
    if (done.kind !== "failed") onReset();
    setDryRun(null);
  };

  const read = status.read?.kind === "done" ? status.read.result : null;
  // The review states count the active movements; the state the status
  // does not count on its own is what they leave.
  const excluded = read
    ? read.active_count -
      read.pending_review_count -
      read.reviewed_count -
      read.skipped_count
    : 0;
  const whole = check?.kind === "done" ? check.result : null;
  const report =
    dryRun?.call.kind === "done" ? dryRun.call.result.report : null;
  const blocked = report ? report.blocking_modelo_references.length > 0 : false;
  const dryRunCurrent = dryRun !== null && dryRun.reason === reason.trim();

  return (
    <div className="ledger-setup-health flex flex-col gap-3 overflow-y-auto p-3">
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Panel title={t("desktop.ledger.health.status", { period: shown })}>
          {status.read === null ? (
            <Reading label={t("desktop.ledger.form.reading")} />
          ) : !read ? (
            <CallLine call={status.read} />
          ) : (
            <dl
              className={`ledger-health-status text-sm ${COUNTS}`}
              data-scope="period"
            >
              <dt>{t("desktop.ledger.health.income")}</dt>
              <dd className="text-right tabular-nums">
                {formatAmount(locale, read.business_income_total)}
              </dd>
              <dt>{t("desktop.ledger.health.expense")}</dt>
              <dd className="text-right tabular-nums">
                {formatAmount(locale, read.business_expense_total)}
              </dd>
              <dt>{t("desktop.ledger.health.net")}</dt>
              <dd className="text-right font-medium tabular-nums">
                {formatAmount(locale, read.business_net_total)}
              </dd>
              <dt>{t("desktop.ledger.health.unconverted")}</dt>
              <dd className="text-right tabular-nums">
                {count(read.unconverted_currency_count)}
              </dd>
            </dl>
          )}
        </Panel>
        <Panel
          title={t("desktop.ledger.health.missing", { period: shown })}
          actions={
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="xs"
                  variant="outline"
                  className="ledger-health-preflight"
                  aria-disabled={checkingNow || undefined}
                  onClick={() => !checkingNow && void runReadiness()}
                >
                  <Icon name="sync" />
                  {snapshot
                    ? t("desktop.ledger.health.check_again")
                    : t("desktop.ledger.health.check")}
                </Button>
              </TooltipTrigger>
              {snapshot && (
                <TooltipContent className="ledger-health-checked-at">
                  {t("desktop.ledger.health.checked_at", {
                    time: new Intl.DateTimeFormat(locale, {
                      timeStyle: "short",
                    }).format(new Date(snapshot.checkedAt)),
                  })}
                </TooltipContent>
              )}
            </Tooltip>
          }
        >
          <ReadinessStrip
            readiness={shownReadiness}
            sets={sets}
            filters={NO_FILTERS}
            locale={locale}
            unsaved={stageTally(stage).units}
            stagedClassify={stagedClassifyCount(sets.toClassify, stage)}
            periodName={shown}
            onCheck={() => !checkingNow && void runReadiness()}
            onPill={(filter) => {
              if (filter === null) return;
              if (onShowReadiness) onShowReadiness(filter);
              else if (filter === "to_classify")
                onShowReason(TO_CLASSIFY_REASON);
            }}
            onReason={(reason) => {
              if (reason !== null) onShowReason(reason);
            }}
          />
        </Panel>
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Panel title={t("desktop.ledger.health.whole_counts")}>
          {/* The status read counts these over the whole ledger, whatever
            period it is asked for. */}
          {status.read === null ? (
            <Reading label={t("desktop.ledger.form.reading")} />
          ) : !read ? null : read.total_count === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.empty_all")}
            </p>
          ) : (
            <div
              className="ledger-health-ledger flex flex-wrap items-start gap-x-10 gap-y-3 text-sm"
              data-scope="ledger"
            >
              <dl className={COUNTS}>
                {(
                  [
                    ["active", read.active_count],
                    ["archived", read.archived_count],
                    ["stashed", read.stashed_count],
                    ["split", read.split_count],
                  ] as const
                ).map(([name, value]) => (
                  <div key={name} className="contents">
                    <dt>{t(`desktop.ledger.health.count.${name}`)}</dt>
                    <dd className="text-right tabular-nums">{count(value)}</dd>
                  </div>
                ))}
              </dl>
              <div className="grid gap-1">
                <p className="text-xs text-muted-foreground">
                  {t("desktop.ledger.health.of_active")}
                </p>
                <dl className={COUNTS}>
                  {(
                    [
                      ["pending", read.pending_review_count],
                      ["reviewed", read.reviewed_count],
                      ["skipped", read.skipped_count],
                    ] as const
                  ).map(([name, value]) => (
                    <div key={name} className="contents">
                      <dt>{t(`desktop.ledger.health.count.${name}`)}</dt>
                      <dd className="text-right tabular-nums">
                        {count(value)}
                      </dd>
                    </div>
                  ))}
                  {excluded > 0 && (
                    <div className="contents" data-count="excluded">
                      <dt>{t("desktop.ledger.status.excluded")}</dt>
                      <dd className="text-right tabular-nums">
                        {count(excluded)}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
            </div>
          )}
        </Panel>
        <Panel
          title={t("desktop.ledger.health.whole")}
          actions={
            <Button
              size="xs"
              variant="outline"
              className="ledger-health-check"
              aria-disabled={checking || undefined}
              onClick={() => !checking && void runCheck()}
            >
              {t("desktop.ledger.health.run_check")}
            </Button>
          }
        >
          {checking ? (
            <Reading label={t("desktop.ledger.form.reading")} />
          ) : whole ? (
            <ul className="ledger-health-whole flex flex-col text-sm">
              {byReason(whole.issues).map(([found, n]) => (
                <li
                  key={found}
                  className="flex gap-2 border-t border-border py-1 first:border-t-0"
                >
                  <span className="flex-1">{reasonShort(t, found)}</span>
                  <span className="tabular-nums">{count(n)}</span>
                </li>
              ))}
              <li className="flex items-center gap-2 border-t border-border py-1 first:border-t-0">
                <span className="flex-1">
                  {t("desktop.ledger.health.one_sided")}
                </span>
                <span className="tabular-nums">
                  {count(whole.link_inconsistencies.length)}
                </span>
                {whole.link_inconsistencies.length > 0 && (
                  <Button size="xs" variant="ghost" onClick={onShowInvoices}>
                    {t("desktop.ledger.section.invoices")}
                  </Button>
                )}
              </li>
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.health.not_run")}
            </p>
          )}
          <CallLine call={check} />
        </Panel>
      </div>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Panel title={t("desktop.ledger.health.stale")}>
          {!read ? null : read.stale_filings.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("desktop.ledger.health.stale_none")}
            </p>
          ) : (
            <ul className="ledger-health-stale flex flex-col text-sm">
              {read.stale_filings.map((filing) => (
                <li
                  key={filing.calculation_revision_id}
                  className="flex items-center gap-2 border-t border-border py-1 first:border-t-0"
                >
                  <Icon name="clock" size="sm" className="text-warning" />
                  <span className="flex-1">
                    {t("desktop.ledger.health.stale_row", {
                      modelo: filing.modelo,
                      year: filing.filing_year,
                      period: filing.period,
                      changed: filing.changed_count,
                      removed: filing.removed_count,
                    })}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel
          title={t("desktop.ledger.health.links")}
          actions={
            <WriteHold>
              <Button
                size="xs"
                variant="outline"
                className="ledger-health-rebuild"
                aria-disabled={rebuild.busy || undefined}
                onClick={() => !rebuild.busy && void runRebuild()}
              >
                {rebuild.busy
                  ? t("desktop.ledger.form.saving")
                  : t("desktop.ledger.health.rebuild")}
              </Button>
            </WriteHold>
          }
        >
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.health.links_what")}
          </p>
          {rebuilt && (
            <Alert tone="success" icon={<Icon name="check" />}>
              {t("desktop.ledger.health.rebuilt", {
                links: rebuilt.participation_count,
              })}
            </Alert>
          )}
          <CallLine call={rebuild.last} />
        </Panel>
      </div>
      <Panel
        title={t("desktop.ledger.health.reset")}
        tone="danger"
        className="ledger-health-reset"
        open={resetOpen}
        onOpen={setResetOpen}
      >
        <p className="text-sm">{t("desktop.ledger.health.reset_what")}</p>
        <TextField
          label={t("desktop.ledger.health.reset_reason")}
          value={reason}
          onValue={setReason}
          hint={t("desktop.ledger.health.reset_reason_hint", {
            limit: RESET_REASON_LIMIT,
          })}
          maxLength={RESET_REASON_LIMIT}
          required
          className="max-w-xl"
        />
        <div>
          <Button
            size="sm"
            variant="outline"
            className="ledger-health-dry-run"
            aria-disabled={!reason.trim() || undefined}
            onClick={() => reason.trim() && void runDryRun()}
          >
            {t("desktop.ledger.health.dry_run")}
          </Button>
        </div>
        {dryRun && <CallLine call={dryRun.call} />}
        {report && blocked && (
          <Alert
            tone="danger"
            role="alert"
            icon={<Icon name="lock" />}
            className="ledger-health-reset-blocked"
          >
            <span className="font-medium">
              {t("desktop.ledger.health.reset_blocked")}
            </span>
            <span>
              {t("desktop.ledger.health.reset_would", {
                movements: report.removed_transaction_ids.length,
                documents: report.cascaded_purchase_invoice_evidence_ids.length,
              })}
            </span>
            <ul className="list-disc pl-4">
              {report.blocking_modelo_references.map((found) => (
                <li key={found.calculation_revision_id}>
                  {t("desktop.ledger.health.reset_blocker", {
                    modelo: found.modelo,
                    year: found.filing_year,
                    period: found.period,
                    state: found.revision_state,
                  })}
                </li>
              ))}
            </ul>
          </Alert>
        )}
        {report && !blocked && (
          <Alert tone="warning" icon={<Icon name="alert" />}>
            <span>
              {t("desktop.ledger.health.reset_would", {
                movements: report.removed_transaction_ids.length,
                documents: report.cascaded_purchase_invoice_evidence_ids.length,
              })}
            </span>
            <span>
              <WriteHold>
                <Button
                  size="sm"
                  variant="destructive"
                  className="ledger-health-reset-confirm"
                  aria-disabled={!dryRunCurrent || resetting.busy || undefined}
                  onClick={() =>
                    dryRunCurrent && !resetting.busy && void runReset()
                  }
                >
                  {t("desktop.ledger.health.reset_confirm", {
                    movements: report.removed_transaction_ids.length,
                  })}
                </Button>
              </WriteHold>
            </span>
          </Alert>
        )}
        <CallLine call={resetting.last} />
      </Panel>
    </div>
  );
}
