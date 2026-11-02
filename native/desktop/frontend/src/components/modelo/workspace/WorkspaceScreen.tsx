import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { ledgerFailure, type LedgerOutcome } from "../../../shell/ledger";
import {
  MODELO_ACTOR,
  modeloEditBody,
  type ModeloPort,
} from "../../../shell/modelo";
import type {
  ModeloAmendmentCorrectionContextV1,
  ModeloWorkHistoryEntryV1,
  ModeloFormNextAction,
  ModeloWorkbenchFormProjectionV1,
  ModeloWorkMetadataSnapshot,
  OutputLanguage,
} from "../../../shell/modeloContract";
import { useStrings, type Translate } from "../../../shell/strings";
import type { LeaveGuard } from "../../ledger/editing/LedgerEditing";
import { Details, type OpenableSurface } from "../details/Details";
import { TodoRail } from "../details/TodoRail";
import { FilingView } from "../dialogs/FilingView";
import type { OperationRun } from "../dialogs/operationRun";
import {
  createModeloWriteHolds,
  declarationWriteKey,
  type ModeloWriteHolds,
} from "../../../shell/modeloWriteHolds";
import {
  ModeloWriteScope,
  ScopedWriteHoldNotice,
  useModeloOperation,
} from "../WriteScope";
import { ReviewDialog } from "../dialogs/ReviewDialog";
import { FormView } from "../form/FormView";
import { useFormSession, type FormSession } from "../form/session";
import { CheckView } from "./CheckView";
import type { CorrectionAnswer, CorrectionResult } from "./CorrectionDialog";
import { HistoryView, type HistoryNotice } from "./HistoryView";
import { SourcesView } from "./SourcesView";
import { ModeloWorkspace, type WorkspaceView } from "./Workspace";

type Read =
  | { phase: "reading" }
  | { phase: "failed"; code: string }
  | { phase: "ready"; envelope: ModeloWorkbenchFormProjectionV1 };

/** What an operation came to, said for the person; null when it settled. */
function runNotice(t: Translate, run: OperationRun<unknown>): HistoryNotice {
  switch (run.kind) {
    case "settled":
    case "saved_unread":
      return null;
    case "refused":
      // The backend words why; the window shows it as served.
      return {
        tone: "warning",
        words: run.words ?? t("workspace.modelo.outcome.refused"),
      };
    case "not_sent":
      return {
        tone: "warning",
        words: t("workspace.modelo.outcome.failed"),
      };
    case "unknown":
      return null;
  }
}

function Ready({
  envelope,
  port,
  language,
  locale,
  reread,
  onBack,
  onOpenSurface,
  canOpenSurface,
  openLink,
  initialView,
  onLeaveGuard,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  port: ModeloPort;
  language: OutputLanguage;
  locale: string;
  /** Reads the declaration again; false when the read failed and the one
   * shown stays. */
  reread(): Promise<boolean>;
  onBack(): void;
  onOpenSurface(surface: OpenableSurface): void;
  canOpenSurface: (surface: OpenableSurface) => boolean;
  openLink(url: string): void;
  initialView: WorkspaceView;
  onLeaveGuard?: (guard: LeaveGuard | null) => void;
}) {
  const t = useStrings();
  const session: FormSession = useFormSession({ envelope, port, language });
  const [view, setView] = useState<WorkspaceView>(initialView);
  const [detailsOpen, setDetailsOpen] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [correcting, setCorrecting] = useState(false);
  const correctionGeneration = useRef(0);
  useLayoutEffect(
    () => () => {
      ++correctionGeneration.current;
    },
    [correcting, envelope, port],
  );
  const [atRisk, setAtRisk] = useState(false);
  const [prerequisiteHeld, setPrerequisiteHeld] = useState(false);
  const operation = useModeloOperation();
  const held = operation.hold !== undefined;
  const busy = operation.hold?.phase === "running";
  const [notice, setNotice] = useState<HistoryNotice>(null);
  const [unit, setUnit] = useState<ModeloWorkMetadataSnapshot | null>(null);
  const [entries, setEntries] = useState<ModeloWorkHistoryEntryV1[] | null>(
    null,
  );
  const [correction, setCorrection] =
    useState<ModeloAmendmentCorrectionContextV1 | null>(null);
  const workUnit = envelope.work_unit_id;

  // Staged edits live only in this window: leaving asks before dropping
  // them, and asks nothing while none are staged.
  const [leaving, setLeaving] = useState<{
    proceed: () => void;
    stay?: () => void;
  } | null>(null);
  const staged = session.stagedCount;
  const guard = useRef<LeaveGuard>(() => false);
  guard.current = (proceed, stay) => {
    if (!staged) return false;
    setLeaving({ proceed, stay });
    return true;
  };
  useEffect(() => {
    if (!onLeaveGuard) return;
    onLeaveGuard((proceed, stay) => guard.current(proceed, stay));
    return () => onLeaveGuard(null);
  }, [onLeaveGuard]);
  // A browser asks on its own before a page with staged edits unloads.
  useEffect(() => {
    if (!staged) return;
    const ask = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", ask);
    return () => window.removeEventListener("beforeunload", ask);
  }, [staged]);

  // Unmounted, the workspace stops following what it sent.
  const alive = useRef(true);
  const generation = useRef(0);
  useLayoutEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      generation.current += 1;
    };
  }, [operation.holds, port, workUnit]);
  /** Sends one write once; whatever it came to, the form is read again
   * unless nothing was sent. */
  const run = async <Result,>(
    send: () => Promise<LedgerOutcome<Result>>,
  ): Promise<OperationRun<Result> | null> => {
    if (held || busy) return null;
    const mine = generation.current;
    const current = () => alive.current && mine === generation.current;
    setNotice(null);
    const outcome = await operation.run(send, current);
    if (!outcome || !current()) return null;
    setNotice(runNotice(t, outcome));
    if (
      outcome.kind !== "unknown" &&
      outcome.kind !== "not_sent" &&
      !(await reread()) &&
      current()
    )
      setNotice(
        (said) =>
          said ?? {
            tone: "warning",
            words: t("workspace.modelo.outcome.failed"),
          },
      );
    return current() ? outcome : null;
  };
  const settledThenReread = async <Result,>(
    send: () => Promise<LedgerOutcome<Result>>,
  ) => (await run(send))?.kind === "settled";

  const readUnit = useCallback(async () => {
    try {
      const outcome = await port.submit("modelo.work.metadata", {
        work_unit_id: workUnit,
      });
      if (outcome.kind === "settled") setUnit(outcome.result.unit);
    } catch {
      setUnit(null);
    }
  }, [port, workUnit]);
  const readHistory = useCallback(async () => {
    try {
      const outcome = await port.submit("modelo.work.history", {
        work_unit_id: workUnit,
        output_language: language,
      });
      setEntries(outcome.kind === "settled" ? outcome.result.entries : null);
    } catch {
      setEntries(null);
    }
  }, [port, workUnit, language]);
  useEffect(() => {
    if (view !== "history") return;
    void readUnit();
    void readHistory();
  }, [view, readUnit, readHistory, envelope]);

  // What a correction of the recorded filing offers, read when it is asked
  // for.
  const filingRecord = unit?.current_filing_record_id ?? null;
  useEffect(() => {
    if (!correcting || !filingRecord) return;
    let current = true;
    port
      .submit("modelo.work.amendment_context", {
        filing_record_id: filingRecord,
        output_language: language,
      })
      .then(
        (outcome) => {
          if (current)
            setCorrection(
              outcome.kind === "settled" ? outcome.result.correction : null,
            );
        },
        () => {
          if (current) setCorrection(null);
        },
      );
    return () => {
      current = false;
    };
  }, [correcting, filingRecord, port, language]);

  /** Has the application read each corrected figure as typed, then sends
   * the correction with the figures it read. */
  const baseline = envelope.admitted_baseline;
  const correct = async (
    answer: CorrectionAnswer,
  ): Promise<CorrectionResult> => {
    // No correction may bypass the declaration's shared write hold.
    if (held) return { kind: "unknown" };
    const mine = correctionGeneration.current;
    const version = operation.holds.version(operation.target);
    if (!baseline || !correction)
      return { kind: "not_sent", code: "not_admitted" };
    let parsed;
    try {
      const outcome = await port.edit(
        "modelo.edit.preflight",
        modeloEditBody({
          input_version: 2,
          output_language: language,
          submission: {
            baseline,
            mutation_family: baseline.mutation_family,
            lexemes: answer.entries.map(({ row, lexeme }) => ({
              address: row.edit_address,
              entry_locale: language,
              lexeme,
            })),
          },
        }),
      );
      if (outcome.kind !== "settled")
        return { kind: "not_sent", code: outcome.kind };
      const read = outcome.result;
      if (read.outcome.outcome === "refused")
        return read.refusal_words
          ? { kind: "said", words: read.refusal_words }
          : { kind: "refused", code: read.outcome.refusal.kind };
      parsed = read.parsed;
    } catch (error) {
      return { kind: "not_sent", code: ledgerFailure(error).code };
    }
    if (
      !alive.current ||
      mine !== correctionGeneration.current ||
      operation.holds.version(operation.target) !== version
    )
      return { kind: "not_sent", code: "not_admitted" };
    const refused: Record<string, string> = {};
    const overrides: { casilla_id: string; value: string }[] = [];
    for (const entry of parsed) {
      if (entry.address.kind !== "correction") continue;
      if (entry.refusal || entry.value === null)
        refused[entry.address.casilla_id] =
          entry.refusal_words ?? t("workspace.modelo.editor.unreadable");
      else
        overrides.push({
          casilla_id: entry.address.casilla_id,
          value: String(entry.value),
        });
    }
    if (Object.keys(refused).length)
      return { kind: "entries", entries: refused };
    const outcome = await run(() =>
      port.submit(
        "modelo.work.amend",
        {
          baseline: {
            from_filing_record_id: correction.filed.filing_record_id,
          },
          amendment_kind: answer.kind,
          overrides,
          reason: answer.reason,
          m303_rectificativa_motive: answer.motive,
          actor: MODELO_ACTOR,
        },
        workUnit,
      ),
    );
    if (outcome === null) return { kind: "unknown" };
    switch (outcome.kind) {
      // Committed: the declaration is read again, read answer or not.
      case "settled":
      case "saved_unread":
        return { kind: "done" };
      case "refused":
        return outcome.words
          ? { kind: "said", words: outcome.words }
          : { kind: "refused", code: outcome.reason ?? "refused" };
      case "not_sent":
        return { kind: "not_sent", code: outcome.code };
      case "unknown":
        return { kind: "unknown" };
    }
  };

  const calculate = () =>
    settledThenReread(() =>
      port.submit("modelo.work.calculate", {
        work_unit_id: workUnit,
        actor: MODELO_ACTOR,
      }),
    );
  const onRun = (action: ModeloFormNextAction) => {
    if (action === "calculate" || action === "recalculate") {
      if (envelope.form.form.operator_entries_known) void calculate();
      else setAtRisk(true);
    } else if (action === "verify" && envelope.calculation_revision_id) {
      const revision = envelope.calculation_revision_id;
      void settledThenReread(() =>
        port.submit(
          "modelo.work.verify",
          { calculation_revision_id: revision, actor: MODELO_ACTOR },
          workUnit,
        ),
      );
    }
  };

  const rename = async (name: string) => {
    if (!unit) return false;
    const done = await settledThenReread(() =>
      port.submit("modelo.work.rename", {
        work_unit_id: workUnit,
        new_name: name,
        observed_name: unit.name,
        observed_updated_at: unit.updated_at,
        actor: MODELO_ACTOR,
      }),
    );
    if (done) await readUnit();
    return done;
  };
  const discard = async (reason: string) => {
    if (!unit) return false;
    const outcome = await run(() =>
      port.submit("modelo.work.discard", {
        baseline: {
          work_unit_id: workUnit,
          name: unit.name,
          observed_updated_at: unit.updated_at,
        },
        reason: reason || null,
        actor: MODELO_ACTOR,
      }),
    );
    if (outcome?.kind !== "settled") return false;
    onBack();
    return true;
  };

  const notified = notice && (
    <div className="px-6 pt-3">
      <Alert tone={notice.tone} icon={<Icon name="alert" />}>
        <span>{notice.words}</span>
      </Alert>
    </div>
  );

  return (
    <ModeloWorkspace
      envelope={envelope}
      locale={locale}
      view={view}
      onViewChange={setView}
      stagedCount={session.stagedCount}
      detailsOpen={detailsOpen}
      busy={busy}
      writeHeld={held}
      prerequisiteHeld={prerequisiteHeld}
      notice={
        operation.hold && operation.hold.phase !== "running" ? (
          <>
            <div className="px-6 pt-3">
              <ScopedWriteHoldNotice />
            </div>
            {view === "history" ? null : notified}
          </>
        ) : view === "history" ? null : (
          notified
        )
      }
      onRun={onRun}
      onReview={() => setReviewing(true)}
      onDiscardStaged={session.discardAll}
      onJumpToNext={() => session.jumpToNext("todo")}
      onCorrect={() => {
        setView("history");
        setCorrecting(true);
      }}
      onBack={onBack}
      slots={{
        form: (
          <FormView
            envelope={envelope}
            session={session}
            detailsOpen={detailsOpen}
            onDetailsOpenChange={setDetailsOpen}
          />
        ),
        rail: (
          <TodoRail
            envelope={envelope}
            session={session}
            onPicked={() => setView("form")}
          />
        ),
        details: (
          <Details
            envelope={envelope}
            port={port}
            language={language}
            session={session}
            openLink={openLink}
            onOpenSurface={onOpenSurface}
            canOpenSurface={canOpenSurface}
            onClose={() => setDetailsOpen(false)}
          />
        ),
        filing: (
          <FilingView
            envelope={envelope}
            port={port}
            language={language}
            session={session}
            openLink={openLink}
            onOpenCheck={() => setView("check")}
            onReread={reread}
          />
        ),
        check: (
          <CheckView
            verdict={envelope.verdict}
            lines={envelope.issue_lines}
            stagedCount={session.stagedCount}
            onGo={(line) => {
              if (!line.address) return;
              setView("form");
              session.selectAddress(line.address);
            }}
            onOpenSurface={onOpenSurface}
            canOpenSurface={canOpenSurface}
            onRecalculate={
              envelope.form.form.edit_closure === null && !held
                ? () => onRun("recalculate")
                : null
            }
          />
        ),
        sources: (
          <SourcesView
            groups={envelope.form.form.source_groups}
            fieldAt={session.fieldAt}
            onGo={(address) => {
              setView("form");
              session.selectAddress(address);
            }}
            onOpenSurface={onOpenSurface}
            canOpenSurface={canOpenSurface}
          />
        ),
        history: (
          <HistoryView
            entries={entries}
            unit={unit}
            recorded={envelope.form.form.edit_closure !== null}
            locale={locale}
            notice={notice}
            disabled={held}
            correcting={correcting}
            onCorrectingChange={setCorrecting}
            correction={correction}
            onRename={rename}
            onDiscard={discard}
            onCorrect={baseline && correction ? correct : null}
          />
        ),
        dialogs: (
          <>
            <ReviewDialog
              open={reviewing}
              onOpenChange={setReviewing}
              envelope={envelope}
              session={session}
              port={port}
              language={language}
              onReread={reread}
              onPrerequisiteHeld={setPrerequisiteHeld}
            />
            {leaving && (
              <Dialog
                open
                onOpenChange={(open) => {
                  if (open) return;
                  setLeaving(null);
                  leaving.stay?.();
                }}
              >
                <DialogContent
                  className="w-dialog-md"
                  closeLabel={t("desktop.ledger.leave.cancel")}
                >
                  <DialogHeader>
                    <DialogTitle>{t("desktop.ledger.leave.title")}</DialogTitle>
                    <DialogDescription>
                      {t("desktop.ledger.leave.description", { count: staged })}
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setLeaving(null);
                        leaving.stay?.();
                      }}
                    >
                      {t("desktop.ledger.leave.cancel")}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setLeaving(null);
                        session.discardAll();
                        leaving.proceed();
                      }}
                    >
                      {t("workspace.modelo.leave.discard")}
                    </Button>
                    <Button
                      autoFocus
                      onClick={() => {
                        setLeaving(null);
                        leaving.stay?.();
                        setView("form");
                        setReviewing(true);
                      }}
                    >
                      {t("workspace.modelo.next_button.apply")}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
            <Dialog open={atRisk} onOpenChange={setAtRisk}>
              <DialogContent closeLabel={t("workspace.modelo.key.close")}>
                <DialogHeader>
                  <DialogTitle>
                    {t("workspace.modelo.calculate.at_risk_title")}
                  </DialogTitle>
                  <DialogDescription>
                    {t("workspace.modelo.calculate.operator_entries_unknown")}
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="ghost" onClick={() => setAtRisk(false)}>
                    {t("workspace.modelo.calculate.at_risk_cancel")}
                  </Button>
                  <Button
                    onClick={() => {
                      setAtRisk(false);
                      void calculate();
                    }}
                  >
                    {t("workspace.modelo.calculate.at_risk_proceed")}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        ),
      }}
    />
  );
}

/**
 * One declaration's workspace over the modelo port: reads its form in the
 * page's language, mounts the form view, the details, the dialogs and the
 * views into the workspace, and reads the form again after anything that
 * may have changed it. The form and staged edits live in memory only.
 */
export function WorkspaceScreen({
  port,
  workUnitId,
  language,
  locale,
  onBack,
  onOpenSurface,
  canOpenSurface = () => false,
  openLink,
  initialView = "form",
  onLeaveGuard,
  onWritten,
  holds: suppliedHolds,
}: {
  port: ModeloPort;
  workUnitId: string;
  language: OutputLanguage;
  locale: string;
  onBack(): void;
  /** Opens the area a source is kept and corrected in. */
  onOpenSurface(surface: OpenableSurface): void;
  /** Whether the window can open an area; none is offered otherwise. */
  canOpenSurface?: (surface: OpenableSurface) => boolean;
  /** Opens a legal reference's page outside the window. */
  openLink(url: string): void;
  /** The view the declaration opens on. */
  initialView?: WorkspaceView;
  /** Hands the shell the guard that asks before staged edits are dropped. */
  onLeaveGuard?: (guard: LeaveGuard | null) => void;
  /** Told whenever the workspace sends a write, whatever its outcome. */
  onWritten?: () => void;
  holds?: ModeloWriteHolds;
}) {
  const t = useStrings();
  const [localHolds] = useState(createModeloWriteHolds);
  const holds = suppliedHolds ?? localHolds;
  const target = declarationWriteKey(workUnitId);
  const [read, setRead] = useState<Read>({ phase: "reading" });
  const latest = useRef(0);
  useLayoutEffect(
    () => () => {
      latest.current += 1;
    },
    [port, workUnitId, language, holds],
  );
  // A read that fails while a declaration is shown keeps it, with what the
  // filer staged on it, and says so to the caller; with nothing shown yet,
  // the failure is the page.
  const shown = useRef(false);
  const reread = useCallback(async () => {
    const ticket = ++latest.current;
    const before = holds.get(target);
    try {
      const envelope = await port.form(workUnitId, language);
      if (ticket !== latest.current) return false;
      shown.current = true;
      setRead({ phase: "ready", envelope });
      if (before) holds.readCompleted(before);
      return true;
    } catch (error) {
      if (ticket === latest.current && !shown.current)
        setRead({ phase: "failed", code: ledgerFailure(error).code });
      return false;
    }
  }, [port, workUnitId, language, holds, target]);
  useEffect(() => {
    shown.current = false;
    setRead({ phase: "reading" });
    void reread();
  }, [reread]);

  const content =
    read.phase === "reading" ? (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    ) : read.phase === "failed" ? (
      <div className="mx-auto flex max-w-xl flex-col gap-3 p-6">
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {t("workspace.modelo.outcome.failed")}
        </Alert>
        <Button
          variant="outline"
          className="self-start"
          onClick={() => void reread()}
        >
          {t("workspace.modelo.read_again")}
        </Button>
      </div>
    ) : (
      <Ready
        key={read.envelope.work_unit_id}
        envelope={read.envelope}
        port={port}
        language={language}
        locale={locale}
        reread={reread}
        onBack={onBack}
        onOpenSurface={onOpenSurface}
        canOpenSurface={canOpenSurface}
        openLink={openLink}
        initialView={initialView}
        onLeaveGuard={onLeaveGuard}
      />
    );
  return (
    <ModeloWriteScope
      holds={holds}
      target={target}
      port={port}
      onWritten={onWritten}
      reload={reread}
    >
      {read.phase !== "ready" && <ScopedWriteHoldNotice />}
      {content}
    </ModeloWriteScope>
  );
}
