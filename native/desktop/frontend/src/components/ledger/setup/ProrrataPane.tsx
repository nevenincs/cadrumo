import { useId, useMemo, useState } from "react";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Icon } from "@/components/ui/icon";
import { Label } from "@/components/ui/label";
import { facts, listed } from "@/shell/compose";
import { servedRefusalWords } from "../../../shell/ledger";
import {
  compareDecimal,
  parseDecimal,
  TAX_AMOUNT_RULE,
} from "../../../shell/ledgerGrammar";
import { servedYear, usePeriods } from "../../../shell/ledgerPeriods";
import type {
  ProrrataEntry,
  ProrrataGrossDeclaration,
  ProrrataMutationResult,
} from "../../../shell/ledgerRegisterOperations";
import { vocabularyEmpty } from "../movements/movementWords";
import { useVocabulary } from "../suggestions/SuggestionsProvider";
import { useStrings } from "../../../shell/strings";
import { WriteHold, type Landing, type LandingCheck } from "../WritePause";
import { formatAmount, formatPercent } from "../../../shared/numbers";
import { PeriodSelector } from "../PeriodSelector";
import { listOptions, textOptions } from "../suggestions/setupSuggestions";
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
import { EditorField } from "./EditorField";
import type { SetupProps } from "./setupProps";
import { parsePoints, setupCall, type SetupCall } from "./setupModel";
import { grammarText, tokenText } from "./setupWords";

const ACTIONS = [
  "seed",
  "declare_sector",
  "elect_general",
  "elect_especial",
  "revoke_especial",
  "seed_sector",
  "settle_sector",
  "declare_gross",
] as const;
type Action = (typeof ACTIONS)[number];

/**
 * The prorrata register by ejercicio: the regime, the provisional
 * percentage and where it comes from, the definitive one once settled, and
 * the differentiated sectors, and the gross cuota declared for earlier
 * liquidations. Each change is its own write, refused with the register's
 * reason where the law does not allow it.
 */
export function ProrrataPane({
  port,
  reader,
  locale,
  years,
  fallbackYear,
}: SetupProps) {
  const t = useStrings();
  const vocabulary = useVocabulary();
  const [ejercicio, setEjercicio] = useState(fallbackYear);
  // The periods a gross declaration is made for are served for its year.
  usePeriods({ years: [ejercicio] });
  const { read, reload } = useSetupRead(
    port,
    reader,
    "ledger.prorrata.list",
    {},
    "prorrata",
  );
  const write = useSetupWrite(t("desktop.ledger.prorrata.title"));
  const [action, setAction] = useState<Action | null>(null);
  const [percentage, setPercentage] = useState("");
  const [provenance, setProvenance] = useState("");
  const [reference, setReference] = useState("");
  const [sector, setSector] = useState("");
  const [evidence, setEvidence] = useState("");
  const [letra, setLetra] = useState("");
  const [codes, setCodes] = useState("");
  const [con, setCon] = useState("");
  const [sin, setSin] = useState("");
  const [grossPeriod, setGrossPeriod] = useState("");
  const [grossCuota, setGrossCuota] = useState("");
  const [replace, setReplace] = useState(false);
  /** The declaration the person is asked to confirm removing. */
  const [removing, setRemoving] = useState<ProrrataGrossDeclaration | null>(
    null,
  );
  const replaceId = useId();
  // A form with anything typed into it that is not yet written.
  useSetupDraft(
    action !== null &&
      [
        percentage,
        provenance,
        reference,
        sector,
        evidence,
        letra,
        codes,
        con,
        sin,
        grossPeriod,
        grossCuota,
      ].some(Boolean),
  );

  const register = read?.kind === "done" ? read.result : null;
  const references = useMemo(
    () =>
      textOptions(
        (register?.entries ?? []).map((entry) => entry.authorisation_reference),
      ),
    [register],
  );
  const evidences = useMemo(
    () =>
      textOptions(
        (register?.entries ?? []).map(
          (entry) => entry.especial_transition?.evidence_reference ?? null,
        ),
      ),
    [register],
  );
  const grossEvidences = useMemo(
    () =>
      textOptions(
        (register?.gross_declarations ?? []).map(
          (found) => found.evidence_reference,
        ),
      ),
    [register],
  );
  const usedCodes = (register?.sectors ?? []).flatMap(
    (found) => found.member_activity_codes,
  );
  const choose = (next: Action) => {
    write.clear();
    setAction(action === next ? null : next);
    setPercentage("");
    setProvenance("");
    setReference("");
    setSector("");
    setEvidence("");
    setLetra("");
    setCodes("");
    setCon("");
    setSin("");
    setGrossPeriod("");
    setGrossCuota("");
    setReplace(false);
    setRemoving(null);
  };
  const points = parsePoints(percentage);
  const conVolume = parseDecimal(con, TAX_AMOUNT_RULE);
  const sinVolume = parseDecimal(sin, TAX_AMOUNT_RULE);
  const grossValue = parseDecimal(grossCuota, TAX_AMOUNT_RULE);
  const refusedText = (parsed: ReturnType<typeof parsePoints>) =>
    parsed.kind === "refused" ? grammarText(t, parsed.refusal) : null;
  const sectorChoices = (register?.sectors ?? []).map((found) => ({
    value: found.sector_id,
    label: facts(t, [
      found.sector_id,
      tokenText(t, "prorrata.letra", found.letra),
    ]),
  }));

  const ready = (() => {
    switch (action) {
      case "seed":
        return true;
      case "declare_sector":
        return sector.trim() !== "" && letra !== "";
      case "elect_general":
      case "elect_especial":
        return points.kind === "value";
      case "revoke_especial":
        return points.kind === "value" && evidence.trim() !== "";
      case "seed_sector":
        return sector !== "";
      case "settle_sector":
        return (
          sector !== "" &&
          conVolume.kind === "value" &&
          sinVolume.kind === "value"
        );
      case "declare_gross":
        return (
          grossPeriod !== "" &&
          grossValue.kind === "value" &&
          evidence.trim() !== ""
        );
      default:
        return false;
    }
  })();

  /** How a register write landed, on the register listed again: each
   * write leaves its ejercicio's entry, or its sector, as it sent it. */
  const prorrataLanding = (
    sent: Action,
    election: { percentage: { decimal: string }; sector_id: string | null },
  ): LandingCheck => {
    const target = ejercicio;
    const chosen = sector.trim() || null;
    const letter = letra;
    const period = grossPeriod;
    const gross = grossValue.kind === "value" ? grossValue.value : "";
    const volumes = {
      con: conVolume.kind === "value" ? conVolume.value : "",
      sin: sinVolume.kind === "value" ? sinVolume.value : "",
    };
    const same = (stored: { decimal: string } | null, value: string) =>
      stored !== null && compareDecimal(stored.decimal, value) === 0;
    return readLanding(port, "ledger.prorrata.list", {}, (result) => {
      const entry = (sectorId: string | null) =>
        result.entries.find(
          (found) => found.ejercicio === target && found.sector_id === sectorId,
        );
      const told = (saved: boolean): Landing => (saved ? "saved" : "not_saved");
      switch (sent) {
        case "seed":
          return told(entry(null) !== undefined);
        case "declare_sector":
          return told(
            result.sectors.some(
              (found) => found.sector_id === chosen && found.letra === letter,
            ),
          );
        case "elect_general":
        case "elect_especial":
        case "revoke_especial": {
          const found = entry(election.sector_id);
          return told(
            found !== undefined &&
              found.regime ===
                (sent === "elect_especial" ? "especial" : "general") &&
              same(found.provisional_percentage, election.percentage.decimal),
          );
        }
        case "seed_sector":
          return told(entry(chosen) !== undefined);
        case "settle_sector": {
          const found = entry(chosen);
          return told(
            found !== undefined &&
              same(found.definitive_volume_con_derecho, volumes.con) &&
              same(found.definitive_volume_sin_derecho, volumes.sin),
          );
        }
        case "declare_gross":
          return told(
            result.gross_declarations.some(
              (found) =>
                found.ejercicio === target &&
                found.period === period &&
                found.sector_id === chosen &&
                same(found.gross_cuota, gross),
            ),
          );
      }
    });
  };
  const send = async () => {
    if (!action || !ready) return;
    const election = () => ({
      ejercicio,
      percentage: { decimal: points.kind === "value" ? points.value : "" },
      provenance: provenance || null,
      reference: reference.trim() || null,
      sector_id: sector || null,
    });
    const done = await write.run(
      (): Promise<SetupCall<ProrrataMutationResult>> => {
        switch (action) {
          case "seed":
            return setupCall(port, "ledger.prorrata.seed", { ejercicio }, true);
          case "declare_sector":
            return setupCall(
              port,
              "ledger.prorrata.declare_sector",
              {
                sector_id: sector.trim(),
                letra,
                member_activity_codes: codes
                  .split(",")
                  .map((code) => code.trim())
                  .filter(Boolean),
              },
              true,
            );
          case "elect_general":
            return setupCall(
              port,
              "ledger.prorrata.elect_general",
              election(),
              true,
            );
          case "elect_especial":
            return setupCall(
              port,
              "ledger.prorrata.elect_especial",
              { ...election(), evidence_reference: evidence.trim() || null },
              true,
            );
          case "revoke_especial":
            return setupCall(
              port,
              "ledger.prorrata.revoke_especial",
              { ...election(), evidence_reference: evidence.trim() },
              true,
            );
          case "seed_sector":
            return setupCall(
              port,
              "ledger.prorrata.seed_sector",
              { ejercicio, sector_id: sector },
              true,
            );
          case "settle_sector":
            return setupCall(
              port,
              "ledger.prorrata.settle_sector",
              {
                ejercicio,
                sector_id: sector,
                con_derecho_volume: {
                  decimal: conVolume.kind === "value" ? conVolume.value : "",
                },
                sin_derecho_volume: {
                  decimal: sinVolume.kind === "value" ? sinVolume.value : "",
                },
              },
              true,
            );
          case "declare_gross":
            return setupCall(
              port,
              "ledger.prorrata.declare_gross",
              {
                ejercicio,
                period: grossPeriod,
                sector_id: sector || null,
                gross_cuota: {
                  decimal: grossValue.kind === "value" ? grossValue.value : "",
                },
                evidence_reference: evidence.trim(),
                replace,
              },
              true,
            );
        }
      },
      prorrataLanding(action, election()),
    );
    if (done.kind === "done") setAction(null);
    reload();
  };

  const grossKey = (found: ProrrataGrossDeclaration) =>
    `${found.ejercicio}:${found.period}:${found.sector_id ?? ""}`;
  /** A declaration named by what identifies it: its year, period and sector. */
  const grossName = (found: ProrrataGrossDeclaration) =>
    facts(t, [found.ejercicio, found.period, found.sector_id]);
  /** Withdraws one declared gross cuota; it landed where the register,
   * listed again, no longer holds that period and sector. */
  const removeGross = async (found: ProrrataGrossDeclaration) => {
    await write.run(
      () =>
        setupCall(
          port,
          "ledger.prorrata.remove_gross",
          {
            ejercicio: found.ejercicio,
            period: found.period,
            sector_id: found.sector_id,
          },
          true,
        ),
      readLanding(port, "ledger.prorrata.list", {}, (result) =>
        result.gross_declarations.some(
          (other) => grossKey(other) === grossKey(found),
        )
          ? "not_saved"
          : "saved",
      ),
    );
    setRemoving(null);
    reload();
  };

  /** A refusal said in the words the register served for it; null where it
   * served none, which the call line says plainly. */
  const refusal = () => {
    const last = write.last;
    if (last?.kind !== "refused") return null;
    return (
      servedRefusalWords(
        (last.detail as ProrrataMutationResult | null)?.refusal,
      ) ?? servedRefusalWords(last.detail)
    );
  };
  const percent = (value: { decimal: string } | null) =>
    value ? formatPercent(locale, value.decimal, { unit: "points" }) : "—";

  const columns: Column<ProrrataEntry>[] = [
    {
      key: "ejercicio",
      label: t("desktop.ledger.prorrata.column.ejercicio"),
      numeric: true,
      sort: (entry) => entry.ejercicio,
      cell: (entry) => entry.ejercicio,
    },
    {
      key: "sector",
      label: t("desktop.ledger.prorrata.column.sector"),
      sort: (entry) => entry.sector_id,
      cell: (entry) =>
        entry.sector_id ?? (
          <span className="text-muted-foreground">
            {t("desktop.ledger.prorrata.whole")}
          </span>
        ),
    },
    {
      key: "regime",
      label: t("desktop.ledger.prorrata.column.regime"),
      sort: (entry) => tokenText(t, "prorrata.regime", entry.regime),
      cell: (entry) => tokenText(t, "prorrata.regime", entry.regime),
    },
    {
      key: "provisional",
      label: t("desktop.ledger.prorrata.column.provisional"),
      numeric: true,
      sort: (entry) => rankDecimal(entry.provisional_percentage?.decimal),
      cell: (entry) => percent(entry.provisional_percentage),
    },
    {
      key: "provenance",
      label: t("desktop.ledger.prorrata.column.provenance"),
      sort: (entry) =>
        entry.provisional_provenance
          ? tokenText(t, "prorrata.provenance", entry.provisional_provenance)
          : null,
      cell: (entry) =>
        entry.provisional_provenance
          ? tokenText(t, "prorrata.provenance", entry.provisional_provenance)
          : "—",
    },
    {
      key: "definitive",
      label: t("desktop.ledger.prorrata.column.definitive"),
      numeric: true,
      sort: (entry) => rankDecimal(entry.definitive_percentage?.decimal),
      cell: (entry) =>
        entry.definitive_percentage ? (
          percent(entry.definitive_percentage)
        ) : (
          <span className="text-muted-foreground">
            {t("desktop.ledger.prorrata.not_settled")}
          </span>
        ),
    },
    {
      key: "volumes",
      label: t("desktop.ledger.prorrata.column.volumes"),
      numeric: true,
      sort: (entry) =>
        rankDecimal(entry.definitive_volume_con_derecho?.decimal),
      cell: (entry) =>
        entry.definitive_volume_con_derecho &&
        entry.definitive_volume_sin_derecho
          ? t("desktop.ledger.prorrata.volumes_pair", {
              with_right: formatAmount(
                locale,
                entry.definitive_volume_con_derecho.decimal,
              ),
              without_right: formatAmount(
                locale,
                entry.definitive_volume_sin_derecho.decimal,
              ),
            })
          : "—",
    },
  ];

  const grossColumns: Column<ProrrataGrossDeclaration>[] = [
    {
      key: "ejercicio",
      label: t("desktop.ledger.prorrata.column.ejercicio"),
      numeric: true,
      sort: (found) => found.ejercicio,
      cell: (found) => found.ejercicio,
    },
    {
      key: "period",
      label: t("desktop.ledger.prorrata.gross.column.period"),
      sort: (found) => found.period,
      cell: (found) => found.period,
    },
    {
      key: "sector",
      label: t("desktop.ledger.prorrata.column.sector"),
      sort: (found) => found.sector_id,
      cell: (found) =>
        found.sector_id ?? (
          <span className="text-muted-foreground">
            {t("desktop.ledger.prorrata.whole")}
          </span>
        ),
    },
    {
      key: "gross_cuota",
      label: t("desktop.ledger.prorrata.gross.column.gross_cuota"),
      numeric: true,
      sort: (found) => rankDecimal(found.gross_cuota.decimal),
      cell: (found) => formatAmount(locale, found.gross_cuota.decimal),
    },
    {
      key: "evidence",
      label: t("desktop.ledger.prorrata.gross.column.evidence"),
      sort: (found) => found.evidence_reference,
      cell: (found) => found.evidence_reference,
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
          className="ledger-prorrata-gross-remove"
          aria-label={t("desktop.ledger.prorrata.gross.remove_of", {
            liquidation: grossName(found),
          })}
          onClick={() => {
            write.clear();
            setRemoving(found);
          }}
        >
          {t("desktop.ledger.prorrata.gross.remove")}
        </Button>
      ),
    },
  ];

  const electionFields = (
    <>
      <EditorField
        label={t("desktop.ledger.prorrata.percentage")}
        error={refusedText(points)}
      >
        {(control) => (
          <PercentEditor
            id={control.id}
            unit="points"
            value={percentage}
            onChange={setPercentage}
            invalid={control.invalid}
            describedBy={control.describedBy}
            required
            autoFocus
          />
        )}
      </EditorField>
      <ChoiceField
        label={t("desktop.ledger.prorrata.provenance_label")}
        value={provenance}
        onValue={setProvenance}
        placeholder={t("desktop.ledger.form.choose")}
        unserved={vocabularyEmpty(
          t,
          vocabulary,
          "",
          vocabulary.prorrataProvenances.length,
        )}
        options={vocabulary.prorrataProvenances.map((value) => ({
          value,
          label: tokenText(t, "prorrata.provenance", value),
        }))}
      />
      <EditorField
        label={t("desktop.ledger.prorrata.reference")}
        hint={t("desktop.ledger.prorrata.reference_hint")}
      >
        {(control) => (
          <TextEditor
            id={control.id}
            value={reference}
            onChange={setReference}
            invalid={control.invalid}
            describedBy={control.describedBy}
            suggestions={references}
          />
        )}
      </EditorField>
      {sectorChoices.length > 0 && (
        <ChoiceField
          label={t("desktop.ledger.prorrata.sector")}
          value={sector}
          onValue={setSector}
          options={[
            { value: "", label: t("desktop.ledger.prorrata.whole") },
            ...sectorChoices,
          ]}
        />
      )}
    </>
  );

  return (
    <Panel
      title={t("desktop.ledger.prorrata.title")}
      actions={
        <PeriodSelector
          mode="year"
          year={ejercicio}
          onYear={setEjercicio}
          label={t("desktop.ledger.prorrata.ejercicio")}
          years={years}
          locale={locale}
          fallbackYear={fallbackYear}
        />
      }
    >
      {read === null ? (
        <Reading label={t("desktop.ledger.form.reading")} />
      ) : read.kind !== "done" ? (
        <CallLine call={read} />
      ) : register!.entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.prorrata.empty")}
        </p>
      ) : (
        <SetupTable
          label={t("desktop.ledger.prorrata.title")}
          rows={register!.entries}
          rowKey={(entry) => `${entry.ejercicio}:${entry.sector_id ?? ""}`}
          selected={`${ejercicio}:`}
          columns={columns}
          className="ledger-prorrata-table"
        />
      )}
      {register && register.sectors.length > 0 && (
        <p className="text-sm">
          <span className="text-muted-foreground">
            {t("desktop.ledger.prorrata.sectors")}{" "}
          </span>
          {listed(
            t,
            sectorChoices.map((choice) => choice.label),
          )}
        </p>
      )}
      {register && (
        <div className="ledger-prorrata-gross flex flex-col gap-2">
          <h4 className="font-medium">
            {t("desktop.ledger.prorrata.gross.title")}
          </h4>
          <p className="text-sm text-muted-foreground">
            {t("desktop.ledger.prorrata.gross.what")}
          </p>
          {register.gross_declarations.length === 0 ? (
            <p className="ledger-prorrata-gross-empty text-sm text-muted-foreground">
              {t("desktop.ledger.prorrata.gross.empty")}
            </p>
          ) : (
            <SetupTable
              label={t("desktop.ledger.prorrata.gross.title")}
              rows={register.gross_declarations}
              rowKey={grossKey}
              columns={grossColumns}
              className="ledger-prorrata-gross-table"
            />
          )}
          {removing && (
            <Alert
              tone="warning"
              icon={<Icon name="alert" />}
              className="ledger-prorrata-gross-removing"
            >
              <span>
                {t("desktop.ledger.prorrata.gross.remove_what", {
                  liquidation: grossName(removing),
                })}
              </span>
              <span className="flex gap-2">
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => setRemoving(null)}
                >
                  {t("desktop.ledger.form.cancel")}
                </Button>
                <WriteHold>
                  <Button
                    size="xs"
                    variant="destructive"
                    className="ledger-prorrata-gross-remove-confirm"
                    aria-disabled={write.busy || undefined}
                    onClick={() => {
                      if (!write.busy) void removeGross(removing);
                    }}
                  >
                    {t("desktop.ledger.prorrata.gross.remove_confirm")}
                  </Button>
                </WriteHold>
              </span>
            </Alert>
          )}
        </div>
      )}
      <div
        role="group"
        aria-label={t("desktop.ledger.prorrata.changes", { ejercicio })}
        className="flex flex-wrap gap-1"
      >
        {ACTIONS.map((value) => (
          <Button
            key={value}
            size="xs"
            variant={action === value ? "secondary" : "outline"}
            aria-pressed={action === value}
            className={`ledger-prorrata-${value}`}
            onClick={() => choose(value)}
          >
            {t(`desktop.ledger.prorrata.action.${value}`)}
          </Button>
        ))}
      </div>
      {action && (
        <form
          className="ledger-prorrata-form flex flex-col gap-3 rounded-md bg-accent p-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (!write.busy) void send();
          }}
        >
          <h4 className="font-medium">
            {t(`desktop.ledger.prorrata.form.${action}`, { ejercicio })}
          </h4>
          <FormGrid>
            {action === "declare_sector" && (
              <>
                <EditorField label={t("desktop.ledger.prorrata.sector_id")}>
                  {(control) => (
                    <TextEditor
                      id={control.id}
                      value={sector}
                      onChange={setSector}
                      invalid={control.invalid}
                      describedBy={control.describedBy}
                      required
                      autoFocus
                    />
                  )}
                </EditorField>
                <ChoiceField
                  label={t("desktop.ledger.prorrata.letra_label")}
                  value={letra}
                  onValue={setLetra}
                  placeholder={t("desktop.ledger.form.choose")}
                  unserved={vocabularyEmpty(
                    t,
                    vocabulary,
                    "",
                    vocabulary.sectorLetters.length,
                  )}
                  options={vocabulary.sectorLetters.map((value) => ({
                    value,
                    label: tokenText(t, "prorrata.letra", value),
                  }))}
                />
                <EditorField
                  label={t("desktop.ledger.prorrata.codes")}
                  hint={t("desktop.ledger.prorrata.codes_hint")}
                >
                  {(control) => (
                    <TextEditor
                      id={control.id}
                      value={codes}
                      onChange={setCodes}
                      invalid={control.invalid}
                      describedBy={control.describedBy}
                      suggestions={listOptions(usedCodes, codes, ",")}
                    />
                  )}
                </EditorField>
              </>
            )}
            {(action === "elect_general" ||
              action === "elect_especial" ||
              action === "revoke_especial") &&
              electionFields}
            {(action === "elect_especial" || action === "revoke_especial") && (
              <EditorField
                label={t("desktop.ledger.prorrata.evidence")}
                hint={t("desktop.ledger.prorrata.evidence_hint")}
              >
                {(control) => (
                  <TextEditor
                    id={control.id}
                    value={evidence}
                    onChange={setEvidence}
                    invalid={control.invalid}
                    describedBy={control.describedBy}
                    suggestions={evidences}
                    required={action === "revoke_especial"}
                  />
                )}
              </EditorField>
            )}
            {action === "declare_gross" && (
              <>
                <ChoiceField
                  label={t("desktop.ledger.prorrata.gross.period")}
                  value={grossPeriod}
                  onValue={setGrossPeriod}
                  placeholder={t("desktop.ledger.form.choose")}
                  required
                  options={(servedYear(ejercicio) ?? [])
                    .filter((row) => row.kind !== "annual")
                    .map((row) => ({
                      value: row.period.code,
                      label: row.label_words,
                    }))}
                />
                {sectorChoices.length > 0 && (
                  <ChoiceField
                    label={t("desktop.ledger.prorrata.sector")}
                    value={sector}
                    onValue={setSector}
                    options={[
                      { value: "", label: t("desktop.ledger.prorrata.whole") },
                      ...sectorChoices,
                    ]}
                  />
                )}
                <EditorField
                  label={t("desktop.ledger.prorrata.gross.gross_cuota")}
                  hint={t("desktop.ledger.prorrata.gross.gross_cuota_hint")}
                  error={refusedText(grossValue)}
                >
                  {(control) => (
                    <MoneyEditor
                      id={control.id}
                      value={grossCuota}
                      onChange={setGrossCuota}
                      invalid={control.invalid}
                      describedBy={control.describedBy}
                      required
                    />
                  )}
                </EditorField>
                <EditorField
                  label={t("desktop.ledger.prorrata.gross.evidence")}
                  hint={t("desktop.ledger.prorrata.gross.evidence_hint")}
                >
                  {(control) => (
                    <TextEditor
                      id={control.id}
                      value={evidence}
                      onChange={setEvidence}
                      invalid={control.invalid}
                      describedBy={control.describedBy}
                      suggestions={grossEvidences}
                      required
                    />
                  )}
                </EditorField>
                <span className="flex items-center gap-2 self-end">
                  <Checkbox
                    id={replaceId}
                    checked={replace}
                    onChange={(event) => setReplace(event.target.checked)}
                  />
                  <Label htmlFor={replaceId}>
                    {t("desktop.ledger.prorrata.gross.replace")}
                  </Label>
                </span>
              </>
            )}
            {(action === "seed_sector" || action === "settle_sector") && (
              <ChoiceField
                label={t("desktop.ledger.prorrata.sector")}
                value={sector}
                onValue={setSector}
                placeholder={
                  sectorChoices.length
                    ? t("desktop.ledger.form.choose")
                    : t("desktop.ledger.prorrata.no_sectors")
                }
                options={sectorChoices}
              />
            )}
            {action === "settle_sector" && (
              <>
                <EditorField
                  label={t("desktop.ledger.prorrata.con_derecho")}
                  error={refusedText(conVolume)}
                >
                  {(control) => (
                    <MoneyEditor
                      id={control.id}
                      value={con}
                      onChange={setCon}
                      invalid={control.invalid}
                      describedBy={control.describedBy}
                      required
                    />
                  )}
                </EditorField>
                <EditorField
                  label={t("desktop.ledger.prorrata.sin_derecho")}
                  error={refusedText(sinVolume)}
                >
                  {(control) => (
                    <MoneyEditor
                      id={control.id}
                      value={sin}
                      onChange={setSin}
                      invalid={control.invalid}
                      describedBy={control.describedBy}
                      required
                    />
                  )}
                </EditorField>
              </>
            )}
          </FormGrid>
          {action === "seed" && (
            <Alert icon={<Icon name="info" />}>
              {t("desktop.ledger.prorrata.seed_what", {
                prior: ejercicio - 1,
                ejercicio,
              })}
            </Alert>
          )}
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setAction(null)}
            >
              {t("desktop.ledger.form.cancel")}
            </Button>
            <WriteHold>
              <Button
                type="submit"
                size="sm"
                className="ledger-prorrata-submit"
                aria-disabled={!ready || write.busy || undefined}
              >
                {write.busy
                  ? t("desktop.ledger.form.saving")
                  : t(`desktop.ledger.prorrata.action.${action}`)}
              </Button>
            </WriteHold>
          </div>
        </form>
      )}
      <CallLine call={write.last} refusal={refusal} onReread={reload} />
    </Panel>
  );
}
