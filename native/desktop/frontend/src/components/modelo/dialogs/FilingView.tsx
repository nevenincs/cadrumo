import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
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
import { Icon, type IconName } from "@/components/ui/icon";
import { NativeSelect } from "@/components/ui/native-select";
import { Spinner } from "@/components/ui/spinner";
import type { FileToken, LedgerOutcome } from "../../../shell/ledger";
import {
  MODELO_ACTOR,
  type ModeloPort,
  type ModeloResult,
  type ModeloSaveFormat,
} from "../../../shell/modelo";
import type {
  ExportLayoutFormat,
  ModeloExportArtefact,
  ModeloExportRequest,
  ModeloFormArtefactOption,
  ModeloFormElection,
  ModeloWorkbenchFormProjectionV1,
  OutputLanguage,
  RecordedCalculationNote,
} from "../../../shell/modeloContract";
import { formatTime } from "../../../shared/dateFormats";
import { AEAT_SEDE } from "../../../shell/links";
import { useStrings } from "../../../shell/strings";
import type { FormSession } from "../form/session";
import { CalculationNotes } from "../workspace/CalculationNotes";
import { runOperation, type OperationRun } from "./operationRun";

// Export and record: the official file written to a place the filer picks,
// the filing recorded here, the AEAT's receipt added, and the other copies.
// Nothing here is sent to the AEAT: export writes a local file the filer
// uploads themselves, and recording the filing is local. Whether a step may
// be taken is the read model's: its export hold, its file view and its
// recorded filing. Each write is sent once; one whose outcome was not seen
// holds every write here until the declaration is read again.

type Write =
  | "export"
  | "record"
  | "receipt"
  | Exclude<ModeloExportArtefact, "fichero_boe">
  | "package";

/** What the last write on this view came to, for its notice. */
type Notice =
  | { kind: "busy"; write: Write }
  | { kind: "saved"; write: Write; name: string; unverified: boolean }
  | { kind: "recorded" }
  /** It committed, and what it answered could not be read. */
  | { kind: "done" }
  | { kind: "receipt"; matches: boolean; narrative: string }
  | { kind: "refused"; write: Write }
  | { kind: "not_sent"; write: Write }
  | { kind: "unknown"; write: Write };

type Stage = {
  word: string;
  when: string;
  detail: string;
  state: "done" | "stale" | "open";
};
const STAGE_ICON: Record<Stage["state"], IconName> = {
  done: "check",
  stale: "alert",
  open: "clock",
};
const STAGE_TONE: Record<Stage["state"], string> = {
  done: "text-success",
  stale: "text-warning",
  open: "text-faint",
};

/** The save format the filing file is written as, by its export layout. */
const FILING_FORMAT: Record<ExportLayoutFormat, ModeloSaveFormat> = {
  fixed_width: "boe",
  xml_dictionary: "xml",
};

/** The request field each election the export asks is sent in. */
const ELECTION_FIELD: Record<
  ModeloFormElection,
  Extract<keyof ModeloExportRequest, `${ModeloFormElection}_election`>
> = {
  refund: "refund_election",
  payment: "payment_election",
  prior_domiciliation: "prior_domiciliation_election",
};

/** The save format each copy is written as. */
const COPY_FORMAT: Record<
  Exclude<ModeloExportArtefact, "fichero_boe">,
  ModeloSaveFormat
> = {
  calculation_report_pdf: "pdf",
  calculation_report_csv: "csv",
  calculation_review_xlsx: "xlsx",
};
const COPY_ICON: Record<Write, IconName> = {
  export: "page",
  record: "tick",
  receipt: "paste",
  calculation_report_pdf: "page",
  calculation_report_csv: "sheet",
  calculation_review_xlsx: "sheet",
  package: "fileArchive",
};

function Card({
  icon,
  title,
  lead,
  children,
}: {
  icon: IconName;
  title: string;
  lead: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5"
    >
      <div className="flex items-start gap-3">
        <Icon name={icon} size="lg" className="mt-0.5 text-muted-foreground" />
        <div className="flex flex-1 flex-col gap-1">
          <h3 className="text-md font-medium">{title}</h3>
          <p className="text-base text-muted-foreground">{lead}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

/**
 * The Export and record view of one declaration. `onOpenCheck` shows the
 * Check view; `onReread` reads the declaration again after a write and when
 * the filer asks after an unknown outcome; `openLink` opens a public address
 * in the system browser.
 */
export function FilingView({
  envelope,
  port,
  language,
  session,
  onOpenCheck,
  onReread,
  openLink,
}: {
  envelope: ModeloWorkbenchFormProjectionV1;
  port: ModeloPort;
  language: OutputLanguage;
  session: FormSession;
  onOpenCheck: () => void;
  onReread: () => Promise<boolean>;
  openLink: (url: string) => void;
}) {
  const t = useStrings();
  const form = envelope.form.form;
  const header = envelope.header;
  const file = header.file;
  const recorded = form.filing;
  const hold = header.export_hold;
  const calculation = envelope.calculation_revision_id;
  const offer = envelope.export_offer;
  const receipt = envelope.receipt;
  const verifiedReceipt = receipt?.verified === true;
  const pending = session.stagedCount > 0;
  // Which artefacts are offered and whether each, and recording, can be
  // done now is the read model's, from the same gates the operations apply.
  const filing =
    offer?.file_format !== null
      ? (offer?.artefacts.find((option) => option.artefact === "fichero_boe") ??
        null)
      : null;
  const copies = (offer?.artefacts ?? []).filter(
    (
      option,
    ): option is ModeloFormArtefactOption & {
      artefact: Exclude<ModeloExportArtefact, "fichero_boe">;
    } => option.artefact !== "fichero_boe",
  );
  // The elections the filing file is exported with, as the filer answers
  // them; each starts at the read model's default.
  const [answers, setAnswers] = useState<
    Partial<Record<ModeloFormElection, string>>
  >({});
  const elections = offer?.asks_elections ? offer.elections : [];
  const answered = Object.fromEntries(
    elections.map((question) => [
      ELECTION_FIELD[question.election],
      answers[question.election] ?? question.default,
    ]),
  ) as Pick<
    ModeloExportRequest,
    "refund_election" | "payment_election" | "prior_domiciliation_election"
  >;
  // The file this view last saved, while it is still shown here.
  const [saved, setSaved] = useState<{ token: FileToken; write: Write } | null>(
    null,
  );

  const [notice, setNotice] = useState<Notice | null>(null);
  // What the last filing file's calculation noted, kept beside the file
  // while this view shows it, whatever is done after.
  const [notes, setNotes] = useState<readonly RecordedCalculationNote[]>([]);
  const [held, setHeld] = useState<ModeloWorkbenchFormProjectionV1 | null>(
    null,
  );
  const [confirming, setConfirming] = useState(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  // A new read of the declaration releases the hold of an unknown write.
  useEffect(() => {
    if (held && held !== envelope) setHeld(null);
  }, [held, envelope]);
  const unknown = held === envelope;
  const busy = notice?.kind === "busy";
  const quiet = busy || unknown || pending;

  const run = useCallback(
    async <Result,>(
      write: Write,
      start: () => Promise<LedgerOutcome<Result>>,
      settled: (result: Result) => Notice,
      tokens: FileToken[],
      keep: FileToken | null = null,
    ) => {
      setNotice({ kind: "busy", write });
      const outcome: OperationRun<Result> = await runOperation(
        port,
        start,
        () => alive.current,
      );
      // A file written here stays named so it can be shown in its folder.
      const written = outcome.kind === "settled" ? keep : null;
      void port.forgetFiles(tokens.filter((token) => token !== written));
      if (!alive.current) return;
      if (written)
        setSaved((before) => {
          if (before) void port.forgetFiles([before.token]);
          return { token: written, write };
        });
      if (outcome.kind === "settled") setNotice(settled(outcome.result));
      else if (outcome.kind === "saved_unread") setNotice({ kind: "done" });
      else if (outcome.kind === "refused")
        setNotice({ kind: "refused", write });
      else if (outcome.kind === "not_sent")
        setNotice({ kind: "not_sent", write });
      else {
        setHeld(envelope);
        setNotice({ kind: "unknown", write });
        return;
      }
      if (outcome.kind === "settled" || outcome.kind === "saved_unread")
        await onReread();
    },
    [port, envelope, onReread],
  );

  const stem = `modelo-${form.modelo}-${form.period.filing_year}-${form.period.code}`;
  const save = async (format: ModeloSaveFormat, name: string) => {
    const picks = await port.saveFile(
      format,
      t(`workspace.modelo.filing.filter.${format}`),
      `${name}.${format}`,
    );
    return picks.files[0] ?? null;
  };

  const exportFile = async (
    write: "export" | Exclude<ModeloExportArtefact, "fichero_boe">,
  ) => {
    if (!calculation || quiet) return;
    const artefact: ModeloExportArtefact =
      write === "export" ? "fichero_boe" : write;
    let format: ModeloSaveFormat;
    if (write === "export") {
      const layout = offer?.file_format ?? null;
      if (layout === null) return;
      format = FILING_FORMAT[layout];
    } else format = COPY_FORMAT[write];
    const picked = await save(format, stem);
    if (!picked) return;
    await run(
      write,
      () =>
        port.submit(
          "modelo.export",
          {
            calculation_revision_id: calculation,
            output_path: picked.token,
            artefact,
            report_language: language,
            ...(write === "export" ? answered : {}),
            actor: MODELO_ACTOR,
          },
          envelope.work_unit_id,
        ),
      (result: ModeloResult<"modelo.export">) => {
        if (write === "export")
          setNotes(result.fichero_boe?.calculation_notes ?? []);
        return {
          kind: "saved",
          write,
          name: picked.name,
          unverified: result.completeness === "unverified",
        };
      },
      [picked.token],
      picked.token,
    );
  };

  const buildPackage = async () => {
    if (!calculation || quiet) return;
    const picked = await save("zip", stem);
    if (!picked) return;
    await run(
      "package",
      () =>
        port.submit(
          "modelo.review_package.build",
          {
            calculation_revision_id: calculation,
            output_path: picked.token,
            actor: MODELO_ACTOR,
          },
          envelope.work_unit_id,
        ),
      () => ({
        kind: "saved",
        write: "package",
        name: picked.name,
        unverified: false,
      }),
      [picked.token],
      picked.token,
    );
  };

  const record = async () => {
    setConfirming(false);
    const report = envelope.verification_report_id;
    if (!calculation || !report || quiet) return;
    await run(
      "record",
      () =>
        port.submit(
          "modelo.work.file",
          {
            approval: {
              calculation_revision_id: calculation,
              verification_report_id: report,
            },
            actor: MODELO_ACTOR,
          },
          envelope.work_unit_id,
        ),
      () => ({ kind: "recorded" }),
      [],
    );
  };

  const addReceipt = async () => {
    if (quiet) return;
    const picks = await port.pickFile(
      "evidence",
      t("workspace.modelo.filing.filter.receipt"),
    );
    const picked = picks.files[0];
    if (!picked) return;
    await run(
      "receipt",
      () =>
        port.submit("modelo.reconcile.import", {
          work_unit_id: envelope.work_unit_id,
          calculation_revision_id: calculation,
          source_kind: "justificante",
          source_path: picked.token,
          actor: MODELO_ACTOR,
        }),
      (result: ModeloResult<"modelo.reconcile.import">) => ({
        kind: "receipt",
        matches: result.verdict === "matches",
        narrative: result.narrative,
      }),
      [picked.token],
    );
  };

  /** Shows the file this view last wrote for `write` in its folder. */
  const reveal = (write: Write) =>
    saved?.write === write && (
      <Button
        variant="ghost"
        size="sm"
        onClick={() => {
          void port.revealFile(saved.token).catch(() => {
            setSaved(null);
          });
        }}
      >
        <Icon name="folder" size="xs" />
        {t("workspace.modelo.filing.show_in_folder")}
      </Button>
    );
  // The named file is forgotten when the view goes.
  const savedToken = saved?.token ?? null;
  useEffect(
    () => () => {
      if (savedToken) void port.forgetFiles([savedToken]);
    },
    [port, savedToken],
  );

  const fileStale = file !== null && !file.current;
  const mayExport = filing?.availability.available === true;
  const recordAvailability = offer?.record ?? null;
  const mayRecord = recordAvailability?.available === true;
  const notYet = t("workspace.modelo.filing.not_yet");
  const stages: Stage[] = [
    {
      word: t("workspace.modelo.origin.calculated"),
      when: calculation ? t("workspace.modelo.legend.name.done") : notYet,
      detail:
        header.result?.short_text ??
        t("workspace.modelo.header.own_calculation"),
      state: calculation ? "done" : "open",
    },
    {
      word: t("workspace.modelo.filing.file_exported"),
      when: file ? formatTime(language, file.exported_at) : notYet,
      detail: file
        ? file.current
          ? t("workspace.modelo.filing.file_current")
          : t("workspace.modelo.filing.file_earlier")
        : t("workspace.modelo.filing.file_local"),
      state: file ? (file.current ? "done" : "stale") : "open",
    },
    {
      word: t("workspace.declarations.list.group.recorded"),
      when: recorded?.recorded_at
        ? formatTime(language, recorded.recorded_at)
        : notYet,
      detail: recorded
        ? t("workspace.modelo.filing.recorded_here")
        : t("workspace.modelo.filing.after_filing"),
      state: recorded ? "done" : "open",
    },
    {
      word: t("workspace.modelo.filing.at_aeat"),
      when: receipt?.verified_at
        ? formatTime(language, receipt.verified_at)
        : recorded
          ? t("workspace.modelo.filing.not_confirmed_yet")
          : "—",
      detail:
        receipt?.words ?? t("workspace.modelo.filing.add_receipt_to_confirm"),
      state: verifiedReceipt ? "done" : "open",
    },
  ];

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="font-serif text-lg text-foreground">
          {t("workspace.modelo.filing.title")}
        </h2>
        <p className="text-base text-muted-foreground">
          {t("workspace.modelo.filing.lead")}
        </p>
      </div>
      <ol className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border @3xl:grid-cols-4">
        {stages.map((stage) => (
          <li
            key={stage.word}
            className="flex flex-col gap-1 bg-card px-4 py-3"
          >
            <span className="flex items-center gap-1.5 text-sm font-medium">
              <Icon
                name={STAGE_ICON[stage.state]}
                size="xs"
                className={STAGE_TONE[stage.state]}
              />
              {stage.word}
            </span>
            <span className="text-sm text-muted-foreground">{stage.when}</span>
            <span className="text-xs text-faint">{stage.detail}</span>
          </li>
        ))}
      </ol>

      {notice && notice.kind !== "busy" && (
        <FilingNotice
          notice={notice}
          onReread={() => {
            void onReread();
          }}
        />
      )}
      {pending && (
        <Alert tone="warning" icon={<Icon name="edit" />}>
          {t("workspace.modelo.next.apply", { count: session.stagedCount })}
        </Alert>
      )}
      <CalculationNotes notes={notes} />

      <Card
        icon="page"
        title={t("workspace.modelo.filing.file_title")}
        lead={t("workspace.modelo.filing.file_format", {
          modelo: form.modelo,
        })}
      >
        {offer?.file_format_words && (
          <p className="text-sm text-muted-foreground">
            {offer.file_format_words}
          </p>
        )}
        {hold && !recorded && (
          <Alert tone="warning" icon={<Icon name="alert" />}>
            <span className="flex flex-col items-start gap-1">
              <span>{hold.words}</span>
              <Button
                size="xs"
                variant="link"
                className="p-0"
                onClick={onOpenCheck}
              >
                {t("workspace.modelo.filing.open_check")}
              </Button>
            </span>
          </Alert>
        )}
        {fileStale && !recorded && (
          <Alert tone="warning" icon={<Icon name="alert" />}>
            {file.words}
          </Alert>
        )}
        {elections.length > 0 && !recorded && (
          <div className="grid grid-cols-1 gap-3 @3xl:grid-cols-2">
            {elections.map((question) => {
              const id = `election-${question.election}`;
              return (
                <div key={question.election} className="flex flex-col gap-1">
                  <label htmlFor={id} className="text-sm text-muted-foreground">
                    {question.words}
                  </label>
                  <NativeSelect
                    id={id}
                    controlSize="sm"
                    disabled={quiet}
                    value={answers[question.election] ?? question.default}
                    onChange={(event) =>
                      setAnswers((now) => ({
                        ...now,
                        [question.election]: event.target.value,
                      }))
                    }
                  >
                    {question.choices.map((choice) => (
                      <option key={choice.value} value={choice.value}>
                        {choice.words}
                      </option>
                    ))}
                  </NativeSelect>
                </div>
              );
            })}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {recorded ? (
            <span className="text-sm text-muted-foreground">
              {t("workspace.modelo.filing.export_again_warning")}
            </span>
          ) : (
            <Button
              disabled={!mayExport || quiet}
              variant={file?.current ? "secondary" : "primary"}
              onClick={() => {
                void exportFile("export");
              }}
            >
              {busy && notice.write === "export" ? (
                <Spinner />
              ) : (
                <Icon name="download" size="xs" />
              )}
              {file
                ? t("workspace.modelo.filing.export_again")
                : t("workspace.modelo.filing.export_file")}
            </Button>
          )}
          {reveal("export")}
          {!recorded && !hold && !mayExport && filing?.availability.words && (
            <span className="text-sm text-muted-foreground">
              {filing.availability.words}
            </span>
          )}
          <Button
            variant="link"
            className="ml-auto"
            onClick={() => openLink(AEAT_SEDE)}
          >
            {t("workspace.modelo.filing.how_to_upload")}
            <Icon name="forward" size="xs" />
          </Button>
        </div>
      </Card>

      <Card
        icon="tick"
        title={t("workspace.modelo.filing.after_filed_title")}
        lead={t("workspace.modelo.filing.record_lead")}
      >
        <div className="flex flex-wrap items-center gap-2">
          {!recorded && (
            <Button
              variant="secondary"
              disabled={!mayRecord || quiet}
              onClick={() => setConfirming(true)}
            >
              {busy && notice.write === "record" && <Spinner />}
              {t("workspace.modelo.filing.record_as_filed")}
            </Button>
          )}
          <Button
            variant="outline"
            disabled={!recorded || verifiedReceipt || quiet}
            onClick={() => {
              void addReceipt();
            }}
          >
            {busy && notice.write === "receipt" ? (
              <Spinner />
            ) : (
              <Icon name="paste" size="xs" />
            )}
            {t("workspace.modelo.filing.add_receipt_pdf")}
          </Button>
          <span className="text-sm text-muted-foreground">
            {!recorded
              ? mayRecord
                ? t("workspace.modelo.filing.also_other_way")
                : (recordAvailability?.words ??
                  t("workspace.modelo.filing.check_first"))
              : (receipt?.words ??
                t("workspace.modelo.filing.receipt_missing"))}
          </span>
        </div>
      </Card>

      <section
        aria-label={t("workspace.modelo.filing.other_copies")}
        className="flex flex-col gap-2"
      >
        <h3 className="text-sm font-medium text-muted-foreground">
          {t("workspace.modelo.filing.other_copies")}
        </h3>
        <ul className="grid grid-cols-1 gap-3 @3xl:grid-cols-2">
          {[
            ...copies,
            ...(offer
              ? [{ artefact: "package" as const, ...offer.review_package }]
              : []),
          ].map((option) => {
            const { artefact: copy, words, availability } = option;
            // Each copy, the review package too, is offered as the read
            // model says.
            const ready = availability.available;
            return (
              <li
                key={copy}
                className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4"
              >
                <div className="flex items-center gap-2">
                  <Icon
                    name={COPY_ICON[copy]}
                    className="text-muted-foreground"
                  />
                  <span className="text-base font-medium">{words}</span>
                </div>
                <p className="text-sm text-muted-foreground">
                  {t(`workspace.modelo.filing.copy.${copy}.detail`)}
                </p>
                {availability?.words && (
                  <p className="text-xs text-faint">{availability.words}</p>
                )}
                <div className="mt-auto flex items-center gap-2 pt-1">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!ready || quiet}
                    onClick={() => {
                      void (copy === "package"
                        ? buildPackage()
                        : exportFile(copy));
                    }}
                  >
                    {busy && notice.write === copy && <Spinner />}
                    {t(`workspace.modelo.filing.copy.${copy}.action`)}
                  </Button>
                  {reveal(copy)}
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent closeLabel={t("workspace.modelo.key.close")}>
          <DialogHeader>
            <DialogTitle>
              {t("application.modelo.lifecycle.file_confirm_title")}
            </DialogTitle>
            <DialogDescription>
              {t("application.modelo.lifecycle.file_confirm_message")}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              {t("application.modelo.lifecycle.file_confirm_cancel")}
            </Button>
            <Button
              onClick={() => {
                void record();
              }}
            >
              {t("application.modelo.lifecycle.file_confirm_accept")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function FilingNotice({
  notice,
  onReread,
}: {
  notice: Exclude<Notice, { kind: "busy" }>;
  onReread: () => void;
}) {
  const t = useStrings();
  switch (notice.kind) {
    case "saved":
      return (
        <Alert tone="success" icon={<Icon name="check" />}>
          <span className="flex flex-col gap-1">
            <span>
              {t("workspace.modelo.filing.saved", { name: notice.name })}
            </span>
            {notice.unverified && (
              <span className="text-warning">
                {t("workspace.modelo.filing.completeness_unverified")}
              </span>
            )}
          </span>
        </Alert>
      );
    case "recorded":
      return (
        <Alert tone="success" icon={<Icon name="tick" />}>
          {t("workspace.modelo.filing.recorded_here")}
        </Alert>
      );
    case "done":
      return (
        <Alert tone="success" icon={<Icon name="check" />}>
          {t("workspace.modelo.operation.done")}
        </Alert>
      );
    case "receipt":
      return (
        <Alert
          tone={notice.matches ? "success" : "warning"}
          icon={<Icon name={notice.matches ? "check" : "alert"} />}
        >
          <span className="flex flex-col gap-1">
            <span>
              {notice.matches
                ? t("workspace.modelo.filing.receipt_matches")
                : t("workspace.modelo.filing.receipt_differs")}
            </span>
            <span className="text-muted-foreground">{notice.narrative}</span>
          </span>
        </Alert>
      );
    case "refused":
    case "not_sent":
      return (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {t("workspace.modelo.outcome.not_done")}
        </Alert>
      );
    case "unknown":
      return (
        <Alert tone="warning" icon={<Icon name="unknown" />} role="alert">
          <span className="flex flex-col items-start gap-1">
            <span>{t("workspace.modelo.outcome.unknown")}</span>
            <Button size="xs" variant="link" className="p-0" onClick={onReread}>
              {t("workspace.modelo.read_again")}
            </Button>
          </span>
        </Alert>
      );
  }
}
