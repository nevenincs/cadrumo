import { useState } from "react";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { YearEditor } from "@/components/editors/YearEditor";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { facts } from "@/shell/compose";
import {
  parseAmount,
  TAX_AMOUNT_RULE,
  parseDecimal,
  parseYear,
} from "../../../shell/ledgerGrammar";
import type {
  CapitalGood,
  CapitalGoodDeclareResult,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { formatAmount, formatPercent } from "../../../shared/numbers";
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
import { parsePoints, setupCall, wholeYear } from "./setupModel";
import { grammarText, tokenText } from "./setupWords";

const KINDS = ["mueble", "inmueble"] as const;
const DISPOSALS = ["sujeta_no_exenta", "exenta_o_no_sujeta"] as const;

/**
 * Bienes de inversión: capital goods whose IVA deduction is regularised over
 * the years after their purchase, each declared once with its cuota and its
 * initial prorrata, and its disposal where there was one.
 */
export function CapitalGoodsPane({ port, reader, locale }: SetupProps) {
  const t = useStrings();
  const { read, reload } = useSetupRead(
    port,
    reader,
    "ledger.bienes_inversion.list",
    {},
    "capital",
  );
  const write = useSetupWrite(t("desktop.ledger.capital.title"));
  const [open, setOpen] = useState(false);
  const [identifier, setIdentifier] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState("");
  const [year, setYear] = useState("");
  const [movement, setMovement] = useState("");
  const [cuota, setCuota] = useState("");
  const [pct, setPct] = useState("");
  const [art108, setArt108] = useState("");
  const [disposalYear, setDisposalYear] = useState("");
  const [disposalRegime, setDisposalRegime] = useState("");
  // A form with anything typed into it that is not yet written.
  useSetupDraft(
    [
      identifier,
      description,
      kind,
      movement,
      cuota,
      pct,
      art108,
      disposalYear,
      disposalRegime,
    ].some(Boolean),
  );

  const cuotaParsed = parseDecimal(cuota, TAX_AMOUNT_RULE);
  const pctParsed = parsePoints(pct);
  const acquired = wholeYear(year);
  const disposed = disposalYear.trim() ? wholeYear(disposalYear) : null;
  const ready =
    identifier.trim() !== "" &&
    description.trim() !== "" &&
    kind !== "" &&
    acquired !== null &&
    movement.trim() !== "" &&
    cuotaParsed.kind === "value" &&
    pctParsed.kind === "value" &&
    art108 !== "" &&
    (disposalYear.trim() === "" || disposed !== null);

  const declare = async () => {
    if (!ready || acquired === null) return;
    const done = await write.run(
      () =>
        setupCall(
          port,
          "ledger.bienes_inversion.declare",
          {
            identifier: identifier.trim(),
            description: description.trim(),
            acquisition_year: acquired,
            acquisition_ledger_id: movement.trim(),
            cuota_soportada: {
              decimal: cuotaParsed.kind === "value" ? cuotaParsed.value : "",
            },
            prorrata_inicial_pct: {
              decimal: pctParsed.kind === "value" ? pctParsed.value : "",
            },
            kind,
            art108_elegible: art108 === "yes",
            disposal_year: disposed,
            disposal_regime: disposalRegime || null,
          },
          true,
        ),
      // A good is declared once under its identifier, which the list shows.
      readLanding(port, "ledger.bienes_inversion.list", {}, (result) =>
        result.rows.some((found) => found.identifier === identifier.trim())
          ? "saved"
          : "not_saved",
      ),
    );
    if (done.kind === "done") setOpen(false);
    reload();
  };
  const refusal = () => {
    const last = write.last;
    if (last?.kind !== "refused") return null;
    const found = (last.detail as CapitalGoodDeclareResult | null)?.refusal;
    return found ? t(`desktop.ledger.capital.refusal.${found.reason}`) : null;
  };

  const columns: Column<CapitalGood>[] = [
    {
      key: "identifier",
      label: t("desktop.ledger.capital.column.identifier"),
      sort: (good) => good.identifier,
      cell: (good) => <code className="font-mono">{good.identifier}</code>,
    },
    {
      key: "description",
      label: t("desktop.ledger.capital.column.description"),
      sort: (good) => good.description,
      cell: (good) => good.description,
    },
    {
      key: "kind",
      label: t("desktop.ledger.capital.column.kind"),
      sort: (good) => tokenText(t, "capital.kind", good.kind),
      cell: (good) => tokenText(t, "capital.kind", good.kind),
    },
    {
      key: "year",
      label: t("desktop.ledger.capital.column.year"),
      numeric: true,
      sort: (good) => good.acquisition_year,
      cell: (good) => good.acquisition_year,
    },
    {
      key: "cuota",
      label: t("desktop.ledger.capital.column.cuota"),
      numeric: true,
      sort: (good) => rankDecimal(good.cuota_soportada.decimal),
      cell: (good) => formatAmount(locale, good.cuota_soportada.decimal),
    },
    {
      key: "pct",
      label: t("desktop.ledger.capital.column.prorrata"),
      numeric: true,
      sort: (good) => rankDecimal(good.prorrata_inicial_pct.decimal),
      cell: (good) =>
        formatPercent(locale, good.prorrata_inicial_pct.decimal, {
          unit: "points",
        }),
    },
    {
      key: "deducted",
      label: t("desktop.ledger.capital.column.deducted"),
      numeric: true,
      sort: (good) => rankDecimal(good.deduccion_efectuada.decimal),
      cell: (good) => formatAmount(locale, good.deduccion_efectuada.decimal),
    },
    {
      key: "disposal",
      label: t("desktop.ledger.capital.column.disposal"),
      sort: (good) => good.disposal?.year ?? null,
      cell: (good) =>
        good.disposal
          ? facts(t, [
              good.disposal.year,
              tokenText(t, "capital.disposal", good.disposal.regime),
            ])
          : "—",
    },
  ];

  const amountError = (parsed: ReturnType<typeof parseAmount>) =>
    parsed.kind === "refused" ? grammarText(t, parsed.refusal) : null;
  const yearError = (typed: string, read: number | null) => {
    if (!typed.trim() || read !== null) return null;
    const refused = parseYear(typed);
    return refused.kind === "refused" ? grammarText(t, refused.refusal) : null;
  };
  return (
    <Panel
      title={t("desktop.ledger.capital.title")}
      actions={
        <Button
          size="xs"
          className="ledger-capital-add"
          aria-expanded={open}
          onClick={() => {
            write.clear();
            setOpen(!open);
          }}
        >
          <Icon name="plus" />
          {t("desktop.ledger.capital.declare")}
        </Button>
      }
    >
      {read === null ? (
        <Reading label={t("desktop.ledger.form.reading")} />
      ) : read.kind !== "done" ? (
        <CallLine call={read} />
      ) : read.result.rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t("desktop.ledger.capital.empty")}
        </p>
      ) : (
        <SetupTable
          label={t("desktop.ledger.capital.title")}
          rows={read.result.rows}
          rowKey={(good) => good.identifier}
          columns={columns}
          className="ledger-capital-table"
        />
      )}
      {open && (
        <form
          className="ledger-capital-form flex flex-col gap-3 rounded-md bg-accent p-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (!write.busy) void declare();
          }}
        >
          <FormGrid>
            <EditorField label={t("desktop.ledger.capital.identifier")}>
              {(control) => (
                <TextEditor
                  id={control.id}
                  value={identifier}
                  onChange={setIdentifier}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  required
                  autoFocus
                />
              )}
            </EditorField>
            <EditorField label={t("desktop.ledger.capital.description")}>
              {(control) => (
                <TextEditor
                  id={control.id}
                  value={description}
                  onChange={setDescription}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  required
                />
              )}
            </EditorField>
            <ChoiceField
              label={t("desktop.ledger.capital.kind_label")}
              value={kind}
              onValue={setKind}
              placeholder={t("desktop.ledger.form.choose")}
              options={KINDS.map((value) => ({
                value,
                label: tokenText(t, "capital.kind", value),
              }))}
            />
            <EditorField
              label={t("desktop.ledger.capital.year")}
              error={yearError(year, acquired)}
            >
              {(control) => (
                <YearEditor
                  id={control.id}
                  value={year}
                  onChange={setYear}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  required
                />
              )}
            </EditorField>
            <EditorField
              label={t("desktop.ledger.capital.movement")}
              hint={t("desktop.ledger.capital.movement_hint")}
            >
              {(control) => (
                <TextEditor
                  id={control.id}
                  value={movement}
                  onChange={setMovement}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  mono
                  required
                />
              )}
            </EditorField>
            <EditorField
              label={t("desktop.ledger.capital.cuota")}
              error={amountError(cuotaParsed)}
            >
              {(control) => (
                <MoneyEditor
                  id={control.id}
                  value={cuota}
                  onChange={setCuota}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  required
                />
              )}
            </EditorField>
            <EditorField
              label={t("desktop.ledger.capital.prorrata")}
              error={amountError(pctParsed)}
            >
              {(control) => (
                <PercentEditor
                  id={control.id}
                  unit="points"
                  value={pct}
                  onChange={setPct}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  required
                />
              )}
            </EditorField>
            <ChoiceField
              label={t("desktop.ledger.capital.art108")}
              value={art108}
              onValue={setArt108}
              placeholder={t("desktop.ledger.form.choose")}
              options={[
                { value: "yes", label: t("desktop.ledger.form.yes") },
                { value: "no", label: t("desktop.ledger.form.no") },
              ]}
            />
            <EditorField
              label={t("desktop.ledger.capital.disposal_year")}
              hint={t("desktop.ledger.capital.disposal_hint")}
              error={yearError(disposalYear, disposed)}
            >
              {(control) => (
                <YearEditor
                  id={control.id}
                  value={disposalYear}
                  onChange={setDisposalYear}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                />
              )}
            </EditorField>
            <ChoiceField
              label={t("desktop.ledger.capital.disposal_regime")}
              value={disposalRegime}
              onValue={setDisposalRegime}
              options={[
                { value: "", label: t("desktop.ledger.form.none") },
                ...DISPOSALS.map((value) => ({
                  value,
                  label: tokenText(t, "capital.disposal", value),
                })),
              ]}
            />
          </FormGrid>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setOpen(false)}
            >
              {t("desktop.ledger.form.cancel")}
            </Button>
            <WriteHold>
              <Button
                type="submit"
                size="sm"
                className="ledger-capital-submit"
                aria-disabled={!ready || write.busy || undefined}
              >
                {write.busy
                  ? t("desktop.ledger.form.saving")
                  : t("desktop.ledger.capital.declare")}
              </Button>
            </WriteHold>
          </div>
        </form>
      )}
      <CallLine call={write.last} refusal={refusal} onReread={reload} />
    </Panel>
  );
}
