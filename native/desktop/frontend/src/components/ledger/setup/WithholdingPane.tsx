import { useEffect, useMemo, useState } from "react";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { TaxIdEditor } from "@/components/editors/TaxIdEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { facts } from "@/shell/compose";
import {
  servedRefusalWords,
  type PickedFile,
  type PublicDecimal,
} from "../../../shell/ledger";
import {
  WITHHOLDING_INCOME_CLASSES,
  WITHHOLDING_ORIGINS,
  type WithholdingIncomeClass,
  type WithholdingOrigin,
} from "../../../shell/ledgerContract";
import type {
  WithholdingAbsence,
  WithholdingAmountColumn,
  WithholdingMutationResult,
  WithholdingRow,
} from "../../../shell/ledgerRegisterOperations";
import { formatAmount } from "../../../shared/numbers";
import { formatInstantDay } from "../../../shared/dateFormats";
import { useStrings } from "../../../shell/strings";
import { useVocabulary } from "../suggestions/SuggestionsProvider";
import { PeriodSelector } from "../PeriodSelector";
import { WriteHold, type Landing, type LandingCheck } from "../WritePause";
import { CertificateFilePicker } from "./CertificateFilePicker";
import { EditorField } from "./EditorField";
import { setupCall, type SetupCall } from "./setupModel";
import type { SetupProps } from "./setupProps";
import { grammarText } from "./setupWords";
import {
  figuresSendable,
  figuresTyped,
  readFigures,
  requestFigures,
} from "./withholdingFigures";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  Reading,
  readLanding,
  rankDecimal,
  SetupTable,
  useSetupDraft,
  useSetupRead,
  useSetupWrite,
  type Column,
} from "./SetupParts";

const ACTIONS = ["record", "attest"] as const;
type Action = (typeof ACTIONS)[number];

const NO_COLUMNS: readonly WithholdingAmountColumn[] = [];

/** The characters of a fingerprint or reference the table shows. */
const SHOWN_HEX = 12;

/**
 * The withholding payers took from the person's income, by ejercicio: each
 * payer's certificate figures grouped by income class, and the person's
 * statement that a class has none. The figures a certificate states, and
 * their words, are those the ledger serves for the chosen class; every one is
 * typed in and sent, and the backend checks, stores and counts them. A payer's tax identifier is sent
 * once, with the record, and is never read back: a row names its payer in the
 * words the backend serves. The list's columns, their words and the ejercicios
 * it can be read for are the backend's too.
 */
/** The amount a row holds under the field a served column names; the
 * backend names the fields, so the window does not list them. */
const servedAmount = (
  found: WithholdingRow,
  column: WithholdingAmountColumn,
): PublicDecimal | null | undefined =>
  (found as unknown as Record<string, PublicDecimal | null | undefined>)[
    column.field
  ];

export function WithholdingPane({
  port,
  reader,
  locale,
  years,
  fallbackYear,
}: SetupProps) {
  const t = useStrings();
  const vocabulary = useVocabulary();
  const [ejercicio, setEjercicio] = useState(fallbackYear);
  const { read, reload } = useSetupRead(
    port,
    reader,
    "ledger.retencion_soportada.list",
    { ejercicio },
    `withholding:${ejercicio}`,
  );
  // Every attestation of the ejercicio, active and withdrawn, as the
  // backend lists them: the revisions the changes below are sent against.
  const { read: absences, reload: reloadAbsences } = useSetupRead(
    port,
    reader,
    "ledger.retencion_soportada.list_absences",
    { ejercicio },
    `withholding-absences:${ejercicio}`,
  );
  const write = useSetupWrite(t("desktop.ledger.withholding.title"));
  const [action, setAction] = useState<Action | null>(null);
  const [incomeClass, setIncomeClass] = useState("");
  const [taxId, setTaxId] = useState("");
  const [legalName, setLegalName] = useState("");
  /** What the person typed in each served figure's box, by field name. */
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [origin, setOrigin] = useState("");
  const [fingerprint, setFingerprint] = useState("");
  /** The certificate file the person picked: sent as the host's token, so
   * the backend reads it and keeps its bytes. A stored document chosen with
   * it is only checked against the bytes read. */
  const [file, setFile] = useState<PickedFile | null>(null);
  const [note, setNote] = useState("");
  /** The row the person is asked to confirm removing. */
  const [removing, setRemoving] = useState<WithholdingRow | null>(null);
  useSetupDraft(
    action !== null &&
      ([taxId, legalName, fingerprint, note].some(Boolean) ||
        file !== null ||
        figuresTyped(vocabulary, amounts)),
  );

  // The stored documents a certificate can rest on, read only while the
  // record form is open.
  const { read: documents } = useSetupRead(
    port,
    reader,
    "ledger.evidence.list",
    action === "record" ? {} : null,
    "withholding-documents",
  );

  const rows = useMemo(
    () => (read?.kind === "done" ? read.result.rows : []),
    [read],
  );
  const listed = useMemo(
    () => (absences?.kind === "done" ? absences.result.attestations : []),
    [absences],
  );
  const active = listed.filter((found) => found.state === "active");
  const withdrawn = listed.filter((found) => found.state === "withdrawn");
  const amountColumns =
    read?.kind === "done" ? read.result.amount_columns : NO_COLUMNS;
  // The ejercicios the list was last served with: kept while another is
  // being read, and when a read of one is refused.
  const [ejercicios, setEjercicios] = useState<readonly number[] | null>(null);
  useEffect(() => {
    if (read?.kind === "done") setEjercicios(read.result.ejercicios);
  }, [read]);
  /** A class in words: as the backend served it with a payer's row or a
   * listed attestation, else its token. */
  const classWords = (value: WithholdingIncomeClass): string =>
    rows.find((row) => row.income_class === value && row.income_class_label)
      ?.income_class_label ??
    listed.find(
      (found) => found.income_class === value && found.income_class_label,
    )?.income_class_label ??
    value;

  const documentChoices = useMemo(() => {
    const seen = new Set<string>();
    const choices: { value: string; label: string }[] = [];
    for (const found of documents?.kind === "done"
      ? documents.result.rows
      : []) {
      if (seen.has(found.source_sha256)) continue;
      seen.add(found.source_sha256);
      choices.push({
        value: found.source_sha256,
        label: facts(t, [
          found.source_path,
          formatInstantDay(locale, found.created_at),
        ]),
      });
    }
    return choices;
  }, [documents, locale, t]);
  const documentsUnserved =
    documents === null
      ? t("desktop.ledger.form.reading")
      : documents.kind !== "done"
        ? t("desktop.ledger.form.failed")
        : documentChoices.length === 0
          ? t("desktop.ledger.withholding.document_none")
          : null;

  const figures = readFigures(vocabulary, incomeClass, amounts);
  const clean = () => {
    if (file) void port.forgetFiles([file.token]).catch(() => undefined);
    setFile(null);
    setIncomeClass("");
    setTaxId("");
    setLegalName("");
    setAmounts({});
    setOrigin("");
    setFingerprint("");
    setNote("");
  };
  const choose = (next: Action) => {
    write.clear();
    setAction(action === next ? null : next);
    setRemoving(null);
    clean();
  };
  const ready =
    incomeClass !== "" &&
    (action === "record"
      ? taxId.trim() !== "" && origin !== "" && figuresSendable(figures)
      : action === "attest"
        ? note.trim() !== "" && absences?.kind === "done"
        : false);

  const classRows = (value: string) =>
    rows.filter((row) => row.income_class === value);
  const told = (saved: boolean): Landing => (saved ? "saved" : "not_saved");

  /** Whether a call was turned back without its record, so that the form
   * stays for the person to fix and send again. A partial one kept the file
   * but stored no record. */
  const sendAgain = (done: SetupCall<{ outcome: string }>) =>
    done.kind === "refused" ||
    done.kind === "partial" ||
    done.kind === "failed" ||
    (done.kind === "done" && done.result.outcome === "refused");

  const send = async () => {
    if (!action || !ready) return;
    const cls = WITHHOLDING_INCOME_CLASSES.find(
      (value) => value === incomeClass,
    );
    if (!cls) return;
    if (action === "record") {
      const before = classRows(cls).length;
      const landing: LandingCheck = readLanding(
        port,
        "ledger.retencion_soportada.list",
        { ejercicio },
        (result) =>
          told(
            result.rows.filter((row) => row.income_class === cls).length >
              before,
          ),
      );
      const done = await write.run(
        (): Promise<SetupCall<WithholdingMutationResult>> =>
          setupCall(
            port,
            "ledger.retencion_soportada.record",
            {
              ejercicio,
              income_class: cls,
              payer_tax_id: taxId.trim(),
              payer_legal_name: legalName.trim() || null,
              ...requestFigures(figures),
              origin: WITHHOLDING_ORIGINS.find((value) => value === origin)!,
              evidence_fingerprint: fingerprint || null,
              source_path: file ? file.token : null,
            },
            true,
          ),
        landing,
      );
      // The payer's tax identifier leaves the form once it was sent, unless
      // the answer is one the person can fix and send again.
      if (!sendAgain(done)) {
        clean();
        if (done.kind === "done") setAction(null);
      }
      reload();
      return;
    }
    // A withdrawn statement is replaced against the revision it was left at;
    // any other for the class is refused rather than doubled.
    const prior = listed.find((found) => found.income_class === cls);
    const done = await write.run(
      () =>
        setupCall(
          port,
          "ledger.retencion_soportada.attest_absence",
          {
            ejercicio,
            income_class: cls,
            note: note.trim(),
            expected_revision_id:
              prior?.state === "withdrawn" ? prior.revision_id : null,
          },
          true,
        ),
      readLanding(
        port,
        "ledger.retencion_soportada.list_absences",
        { ejercicio },
        (result) =>
          told(
            result.attestations.some(
              (found) =>
                found.income_class === cls &&
                found.state === "active" &&
                found.revision_id !== prior?.revision_id,
            ),
          ),
      ),
    );
    if (!sendAgain(done)) {
      clean();
      if (done.kind === "done") setAction(null);
    }
    reloadAbsences();
  };
  const withdraw = async (found: WithholdingAbsence) => {
    await write.run(
      () =>
        setupCall(
          port,
          "ledger.retencion_soportada.withdraw_absence",
          {
            ejercicio: found.ejercicio,
            income_class: found.income_class,
            expected_revision_id: found.revision_id,
          },
          true,
        ),
      readLanding(
        port,
        "ledger.retencion_soportada.list_absences",
        { ejercicio: found.ejercicio },
        (result) =>
          told(
            result.attestations.some(
              (other) =>
                other.income_class === found.income_class &&
                other.state === "withdrawn",
            ),
          ),
      ),
    );
    reloadAbsences();
  };
  /** Removes one stored record; it landed where the ejercicio, listed
   * again, no longer holds that payer under that class. */
  const remove = async (found: WithholdingRow) => {
    await write.run(
      () =>
        setupCall(
          port,
          "ledger.retencion_soportada.remove",
          {
            ejercicio: found.ejercicio,
            income_class: found.income_class,
            payer_ref: found.payer_ref,
            expected_revision_id: found.revision_id,
          },
          true,
        ),
      readLanding(
        port,
        "ledger.retencion_soportada.list",
        { ejercicio: found.ejercicio },
        (result) =>
          told(
            !result.rows.some(
              (other) =>
                other.income_class === found.income_class &&
                other.payer_ref === found.payer_ref,
            ),
          ),
      ),
    );
    setRemoving(null);
    reload();
  };

  /** A refusal said in the words the backend served for it, with the
   * refusal's own or the detail's. A refusal that arrives without words (a
   * transport failure, say) gets the generic notice, never its reason. */
  const refusalIn = (detail: unknown): string | null => {
    const found = (detail as { refusal?: unknown } | null)?.refusal;
    return servedRefusalWords(found) ?? servedRefusalWords(detail);
  };
  const refusal = () =>
    write.last?.kind === "refused" ? refusalIn(write.last.detail) : null;
  /** A change the backend settled as refused, in its own result. */
  const settledRefusal =
    write.last?.kind === "done" &&
    (write.last.result as { outcome?: string }).outcome === "refused"
      ? refusalIn(write.last.result)
      : null;

  /** An amount as the record states it; blank where it states none. */
  const amountOf = (found: WithholdingRow, column: WithholdingAmountColumn) => {
    const value = servedAmount(found, column);
    return value ? formatAmount(locale, value.decimal) : "";
  };
  const originWords = (value: WithholdingOrigin) =>
    t(`desktop.ledger.withholding.origin.${value}`);
  const classChoices = WITHHOLDING_INCOME_CLASSES.map((value) => ({
    value,
    label: classWords(value),
  }));

  const columns: Column<WithholdingRow>[] = [
    {
      key: "class",
      label: t("desktop.ledger.withholding.column.class"),
      sort: (found) => found.income_class_label,
      cell: (found) => found.income_class_label,
    },
    {
      key: "payer",
      label: t("desktop.ledger.withholding.column.payer"),
      sort: (found) => found.payer_display_name,
      cell: (found) => found.payer_display_name,
    },
    {
      key: "origin",
      label: t("desktop.ledger.withholding.column.origin"),
      keepWords: true,
      sort: (found) => found.origin_label,
      cell: (found) => found.origin_label,
    },
    ...amountColumns.map((column): Column<WithholdingRow> => ({
      key: column.field,
      label: column.label,
      numeric: true,
      sort: (found) => rankDecimal(servedAmount(found, column)?.decimal),
      cell: (found) => amountOf(found, column),
    })),
    {
      key: "document",
      label: t("desktop.ledger.withholding.column.document"),
      sort: (found) => found.evidence_fingerprint,
      cell: (found) =>
        found.evidence_fingerprint ? (
          <span className="font-mono text-xs">
            {found.evidence_fingerprint.slice(0, SHOWN_HEX)}
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "actions",
      label: t("desktop.ledger.form.actions"),
      hidden: true,
      resizable: false,
      cell: (found) => (
        <Button
          size="xs"
          variant="outline"
          className="ledger-withholding-remove"
          aria-label={t("desktop.ledger.withholding.remove_of", {
            payer: found.payer_display_name,
          })}
          onClick={() => {
            write.clear();
            setRemoving(found);
          }}
        >
          {t("desktop.ledger.withholding.remove")}
        </Button>
      ),
    },
  ];

  const absenceColumns = (
    withWithdraw: boolean,
    withdrawn: boolean,
  ): Column<WithholdingAbsence>[] => [
    {
      key: "class",
      label: t("desktop.ledger.withholding.column.class"),
      sort: (found) => classWords(found.income_class),
      cell: (found) => classWords(found.income_class),
    },
    {
      key: "state",
      label: t("desktop.ledger.withholding.column.state"),
      keepWords: true,
      cell: (found) => found.state_label ?? "—",
    },
    {
      key: "stated_on",
      label: t("desktop.ledger.withholding.column.stated_on"),
      keepWords: true,
      sort: (found) => found.attested_at,
      cell: (found) => formatInstantDay(locale, found.attested_at),
    },
    ...(withdrawn
      ? [
          {
            key: "withdrawn_on",
            label: t("desktop.ledger.withholding.column.withdrawn_on"),
            keepWords: true,
            sort: (found: WithholdingAbsence) => found.withdrawn_at ?? "",
            cell: (found: WithholdingAbsence) =>
              found.withdrawn_at
                ? formatInstantDay(locale, found.withdrawn_at)
                : "—",
          },
        ]
      : []),
    {
      key: "note",
      label: t("desktop.ledger.withholding.column.note"),
      cell: (found) => found.note,
    },
    ...(withWithdraw
      ? [
          {
            key: "actions",
            label: t("desktop.ledger.form.actions"),
            hidden: true,
            resizable: false,
            cell: (found: WithholdingAbsence) => (
              <WriteHold>
                <Button
                  size="xs"
                  variant="outline"
                  className="ledger-withholding-withdraw"
                  aria-label={t("desktop.ledger.withholding.withdraw_of", {
                    class: classWords(found.income_class),
                  })}
                  aria-disabled={write.busy || undefined}
                  onClick={() => {
                    if (!write.busy) void withdraw(found);
                  }}
                >
                  {t("desktop.ledger.withholding.withdraw")}
                </Button>
              </WriteHold>
            ),
          },
        ]
      : []),
  ];
  const activeColumns = absenceColumns(true, false);
  const historyColumns = absenceColumns(false, true);

  return (
    <Panel
      title={t("desktop.ledger.withholding.title")}
      actions={
        <PeriodSelector
          mode="year"
          year={ejercicio}
          onYear={setEjercicio}
          label={t("desktop.ledger.withholding.ejercicio")}
          years={ejercicios ?? years}
          yearsKey={
            ejercicios ? "desktop.ledger.period.years_supported" : undefined
          }
          locale={locale}
          fallbackYear={fallbackYear}
        />
      }
    >
      <p className="text-sm text-muted-foreground">
        {t("desktop.ledger.withholding.what")}
      </p>
      {read === null ? (
        <Reading label={t("desktop.ledger.form.reading")} />
      ) : read.kind !== "done" ? (
        <CallLine call={read} />
      ) : rows.length === 0 ? (
        <p className="ledger-withholding-empty text-sm text-muted-foreground">
          {t("desktop.ledger.withholding.empty", { ejercicio })}
        </p>
      ) : (
        <section className="ledger-withholding-class flex flex-col gap-2">
          <SetupTable
            label={t("desktop.ledger.withholding.title")}
            rows={rows}
            rowKey={(found) => `${found.income_class}:${found.payer_ref}`}
            columns={columns}
            className="ledger-withholding-table"
          />
        </section>
      )}
      {removing && (
        <Alert
          tone="warning"
          icon={<Icon name="alert" />}
          className="ledger-withholding-removing"
        >
          <span>
            {t("desktop.ledger.withholding.remove_what", {
              payer: removing.payer_display_name,
              class: classWords(removing.income_class),
            })}{" "}
            {t("desktop.ledger.withholding.correct_hint")}
          </span>
          <span className="flex gap-2">
            <Button size="xs" variant="ghost" onClick={() => setRemoving(null)}>
              {t("desktop.ledger.form.cancel")}
            </Button>
            <WriteHold>
              <Button
                size="xs"
                variant="destructive"
                className="ledger-withholding-remove-confirm"
                aria-disabled={write.busy || undefined}
                onClick={() => {
                  if (!write.busy) void remove(removing);
                }}
              >
                {t("desktop.ledger.withholding.remove_confirm")}
              </Button>
            </WriteHold>
          </span>
        </Alert>
      )}
      <div className="ledger-withholding-absence flex flex-col gap-2">
        <h4 className="font-medium">
          {t("desktop.ledger.withholding.absence.title")}
        </h4>
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.withholding.absence.what")}
        </p>
        {absences === null ? (
          <Reading label={t("desktop.ledger.form.reading")} />
        ) : absences.kind !== "done" ? (
          <CallLine call={absences} />
        ) : (
          <>
            {active.length > 0 && (
              <SetupTable
                label={t("desktop.ledger.withholding.absence.title")}
                rows={active}
                rowKey={(found) => `${found.ejercicio}:${found.income_class}`}
                columns={activeColumns}
                className="ledger-withholding-attested"
              />
            )}
            {withdrawn.length > 0 && (
              <section className="ledger-withholding-history flex flex-col gap-2">
                <h5 className="text-sm font-medium text-muted-foreground">
                  {t("desktop.ledger.withholding.absence.history")}
                </h5>
                <SetupTable
                  label={t("desktop.ledger.withholding.absence.history")}
                  rows={withdrawn}
                  rowKey={(found) => `${found.ejercicio}:${found.income_class}`}
                  columns={historyColumns}
                  className="ledger-withholding-withdrawn"
                />
              </section>
            )}
          </>
        )}
      </div>
      <div
        role="group"
        aria-label={t("desktop.ledger.withholding.changes", { ejercicio })}
        className="flex flex-wrap gap-1"
      >
        {ACTIONS.map((value) => (
          <Button
            key={value}
            size="xs"
            variant={action === value ? "secondary" : "outline"}
            aria-pressed={action === value}
            className={`ledger-withholding-${value}`}
            onClick={() => choose(value)}
          >
            {t(`desktop.ledger.withholding.action.${value}`)}
          </Button>
        ))}
      </div>
      {action && (
        <form
          className="ledger-withholding-form flex flex-col gap-3 rounded-md bg-accent p-3"
          autoComplete="off"
          onSubmit={(event) => {
            event.preventDefault();
            if (!write.busy) void send();
          }}
        >
          <h4 className="font-medium">
            {t(`desktop.ledger.withholding.form.${action}`, { ejercicio })}
          </h4>
          <FormGrid>
            <ChoiceField
              label={t("desktop.ledger.withholding.income_class")}
              value={incomeClass}
              onValue={setIncomeClass}
              placeholder={t("desktop.ledger.form.choose")}
              required
              options={classChoices}
            />
            {action === "record" && (
              <>
                <EditorField
                  label={t("desktop.ledger.withholding.payer_tax_id")}
                  hint={t("desktop.ledger.withholding.payer_tax_id_hint")}
                >
                  {(control) => (
                    <TaxIdEditor
                      id={control.id}
                      value={taxId}
                      onChange={setTaxId}
                      invalid={control.invalid}
                      describedBy={control.describedBy}
                      required
                    />
                  )}
                </EditorField>
                <EditorField
                  label={t("desktop.ledger.withholding.payer_legal_name")}
                >
                  {(control) => (
                    <TextEditor
                      id={control.id}
                      value={legalName}
                      onChange={setLegalName}
                      invalid={control.invalid}
                      describedBy={control.describedBy}
                    />
                  )}
                </EditorField>
                {incomeClass !== "" && figures.length === 0 && (
                  <p className="ledger-withholding-figures-unserved text-sm text-muted-foreground">
                    {vocabulary.state === "loading"
                      ? t("desktop.ledger.form.reading")
                      : t("desktop.ledger.form.failed")}
                  </p>
                )}
                {figures.map(({ figure, text, parsed }) => (
                  <EditorField
                    key={`${incomeClass}:${figure.field}`}
                    label={figure.labelKey ? t(figure.labelKey) : figure.field}
                    error={
                      parsed.kind === "refused"
                        ? grammarText(t, parsed.refusal)
                        : null
                    }
                  >
                    {(control) => (
                      <MoneyEditor
                        id={control.id}
                        value={text}
                        onChange={(next) =>
                          setAmounts((held) => ({
                            ...held,
                            [figure.field]: next,
                          }))
                        }
                        invalid={control.invalid}
                        describedBy={control.describedBy}
                      />
                    )}
                  </EditorField>
                ))}
                <ChoiceField
                  label={t("desktop.ledger.withholding.origin_label")}
                  value={origin}
                  onValue={setOrigin}
                  placeholder={t("desktop.ledger.form.choose")}
                  required
                  options={WITHHOLDING_ORIGINS.map((value) => ({
                    value,
                    label: originWords(value),
                  }))}
                />
                <CertificateFilePicker
                  port={port}
                  file={file}
                  onFile={setFile}
                  disabled={write.busy}
                />
                <ChoiceField
                  label={t("desktop.ledger.withholding.document")}
                  hint={t("desktop.ledger.withholding.document_hint")}
                  value={fingerprint}
                  onValue={setFingerprint}
                  placeholder={t("desktop.ledger.withholding.document_not")}
                  unserved={documentsUnserved}
                  options={documentChoices}
                />
              </>
            )}
            {action === "attest" && (
              <EditorField
                label={t("desktop.ledger.withholding.note")}
                hint={t("desktop.ledger.withholding.note_hint")}
              >
                {(control) => (
                  <TextEditor
                    id={control.id}
                    value={note}
                    onChange={setNote}
                    invalid={control.invalid}
                    describedBy={control.describedBy}
                    required
                  />
                )}
              </EditorField>
            )}
          </FormGrid>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setAction(null);
                clean();
              }}
            >
              {t("desktop.ledger.form.cancel")}
            </Button>
            <WriteHold>
              <Button
                type="submit"
                size="sm"
                className="ledger-withholding-submit"
                aria-disabled={!ready || write.busy || undefined}
              >
                {write.busy
                  ? t("desktop.ledger.form.saving")
                  : t(`desktop.ledger.withholding.action.${action}`)}
              </Button>
            </WriteHold>
          </div>
        </form>
      )}
      {settledRefusal && (
        <Alert
          tone="danger"
          role="alert"
          icon={<Icon name="refused" />}
          className="ledger-withholding-refusal"
        >
          {settledRefusal}
        </Alert>
      )}
      <CallLine call={write.last} refusal={refusal} onReread={reload} />
    </Panel>
  );
}
