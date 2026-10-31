import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { facts, listed } from "@/shell/compose";
import {
  compareDecimal,
  parseDecimal,
  TAX_AMOUNT_RULE,
} from "../../../shell/ledgerGrammar";
import type {
  ProrrataEntry,
  ProrrataMutationResult,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold, type Landing, type LandingCheck } from "../WritePause";
import { formatAmount, formatPercent } from "../../../shared/numbers";
import { PeriodSelector } from "../PeriodSelector";
import {
  CallLine,
  ChoiceField,
  FormGrid,
  Panel,
  Reading,
  readLanding,
  rankDecimal,
  SetupTable,
  TextField,
  useSetupDraft,
  useSetupRead,
  useSetupWrite,
  type Column,
} from "./SetupParts";
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
] as const;
type Action = (typeof ACTIONS)[number];

/** The provisional provenances the registry names; the register decides
 * which of them an election may declare. */
const PROVENANCES = [
  "aeat_autorizada",
  "inicio_actividad",
  "carried_prior_definitiva",
  "interrumpida_tres_ultimos",
] as const;
const LETTERS = ["a", "b", "c", "d"] as const;

/**
 * The prorrata register by ejercicio: the regime, the provisional
 * percentage and where it comes from, the definitive one once settled, and
 * the differentiated sectors. Each change is its own write, refused with
 * the register's reason where the law does not allow it.
 */
export function ProrrataPane({
  port,
  reader,
  locale,
  years,
  fallbackYear,
}: SetupProps) {
  const t = useStrings();
  const [ejercicio, setEjercicio] = useState(fallbackYear);
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
      ].some(Boolean),
  );

  const register = read?.kind === "done" ? read.result : null;
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
  };
  const points = parsePoints(percentage);
  const conVolume = parseDecimal(con, TAX_AMOUNT_RULE);
  const sinVolume = parseDecimal(sin, TAX_AMOUNT_RULE);
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
        }
      },
      prorrataLanding(action, election()),
    );
    if (done.kind === "done") setAction(null);
    reload();
  };

  /** A refusal said in the register's own reason, with what it accepts. */
  const refusal = () => {
    const last = write.last;
    if (last?.kind !== "refused") return null;
    const found = (last.detail as ProrrataMutationResult | null)?.refusal;
    if (!found) return null;
    const said = t(`desktop.ledger.prorrata.refusal.${found.reason}`);
    return found.accepted_provenances.length
      ? `${said} ${t("desktop.ledger.prorrata.accepted", {
          provenances: listed(
            t,
            found.accepted_provenances.map((value) =>
              tokenText(t, "prorrata.provenance", value),
            ),
          ),
        })}`
      : said;
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

  const electionFields = (
    <>
      <TextField
        label={t("desktop.ledger.prorrata.percentage")}
        value={percentage}
        onValue={setPercentage}
        inputMode="decimal"
        hint={t("desktop.ledger.form.points_hint")}
        error={refusedText(points)}
        required
        autoFocus
      />
      <ChoiceField
        label={t("desktop.ledger.prorrata.provenance_label")}
        value={provenance}
        onValue={setProvenance}
        placeholder={t("desktop.ledger.form.choose")}
        options={PROVENANCES.map((value) => ({
          value,
          label: tokenText(t, "prorrata.provenance", value),
        }))}
      />
      <TextField
        label={t("desktop.ledger.prorrata.reference")}
        value={reference}
        onValue={setReference}
        hint={t("desktop.ledger.prorrata.reference_hint")}
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
    </>
  );

  return (
    <Panel
      title={t("desktop.ledger.prorrata.title")}
      actions={
        <PeriodSelector
          value={{ year: ejercicio, code: "0A" }}
          onChange={(next) => next && setEjercicio(next.year)}
          label={t("desktop.ledger.prorrata.ejercicio")}
          years={years}
          locale={locale}
          fallbackYear={fallbackYear}
          mode="year"
          allowAll={false}
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
                <TextField
                  label={t("desktop.ledger.prorrata.sector_id")}
                  value={sector}
                  onValue={setSector}
                  required
                  autoFocus
                />
                <ChoiceField
                  label={t("desktop.ledger.prorrata.letra_label")}
                  value={letra}
                  onValue={setLetra}
                  placeholder={t("desktop.ledger.form.choose")}
                  options={LETTERS.map((value) => ({
                    value,
                    label: tokenText(t, "prorrata.letra", value),
                  }))}
                />
                <TextField
                  label={t("desktop.ledger.prorrata.codes")}
                  value={codes}
                  onValue={setCodes}
                  hint={t("desktop.ledger.prorrata.codes_hint")}
                />
              </>
            )}
            {(action === "elect_general" ||
              action === "elect_especial" ||
              action === "revoke_especial") &&
              electionFields}
            {(action === "elect_especial" || action === "revoke_especial") && (
              <TextField
                label={t("desktop.ledger.prorrata.evidence")}
                value={evidence}
                onValue={setEvidence}
                required={action === "revoke_especial"}
                hint={t("desktop.ledger.prorrata.evidence_hint")}
              />
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
                <TextField
                  label={t("desktop.ledger.prorrata.con_derecho")}
                  value={con}
                  onValue={setCon}
                  inputMode="decimal"
                  hint={t("desktop.ledger.form.amount_hint")}
                  error={refusedText(conVolume)}
                  required
                />
                <TextField
                  label={t("desktop.ledger.prorrata.sin_derecho")}
                  value={sin}
                  onValue={setSin}
                  inputMode="decimal"
                  hint={t("desktop.ledger.form.amount_hint")}
                  error={refusedText(sinVolume)}
                  required
                />
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
