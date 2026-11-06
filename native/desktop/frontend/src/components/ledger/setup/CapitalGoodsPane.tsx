import { useMemo, useState } from "react";
import { MoneyEditor } from "@/components/editors/MoneyEditor";
import { PercentEditor } from "@/components/editors/PercentEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { YearEditor } from "@/components/editors/YearEditor";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
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
} from "../../../shell/ledgerRegisterOperations";
import { servedRefusalWords, type LedgerRow } from "../../../shell/ledger";
import { takesCapitalGoodAcquisition } from "../../../shell/ledgerContract";
import { LEDGER_PAGE_SIZE } from "../../../shell/ledgerWindow";
import { vocabularyEmpty } from "../movements/movementWords";
import { useVocabulary } from "../suggestions/SuggestionsProvider";
import { useStrings } from "../../../shell/strings";
import { WriteHold } from "../WritePause";
import { formatDay } from "../../../shared/dateFormats";
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

/**
 * Bienes de inversión: capital goods whose IVA deduction is regularised over
 * the years after their purchase, each declared once with its cuota and its
 * initial prorrata, and its disposal where there was one.
 */
export function CapitalGoodsPane({ port, reader, locale, rows }: SetupProps) {
  const t = useStrings();
  const vocabulary = useVocabulary();
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
  const [movementLabel, setMovementLabel] = useState("");
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
  // The purchases a good can name: the largest of the year typed, which is all
  // that is decrypted, or with no year yet the movements the page has loaded.
  const yearRows = useSetupRead(
    port,
    reader,
    "ledger.list",
    open && acquired !== null
      ? {
          filters: ["period=0A", `year=${acquired}`],
          sort_by: "amount",
          sort_order: "desc",
          limit: LEDGER_PAGE_SIZE,
        }
      : null,
    `capital-movements:${open ? (acquired ?? "") : ""}`,
  ).read;
  const yearResult = yearRows?.kind === "done" ? yearRows.result : null;
  const declared = read?.kind === "done" ? read.result.rows : null;
  const purchases = useMemo(() => {
    const used = new Set(declared?.map((good) => good.acquisition_ledger_id));
    const pool: readonly LedgerRow[] =
      acquired === null ? (rows ?? []) : (yearResult?.rows ?? []);
    return pool
      .map((row) => row.transaction)
      .filter(
        (found) =>
          takesCapitalGoodAcquisition(found.direction) &&
          !used.has(found.transaction_id),
      )
      .map((found) => ({
        value: found.transaction_id,
        label: facts(t, [
          found.description,
          formatDay(locale, found.date),
          formatAmount(locale, found.amount),
        ]),
        keywords: [found.counterparty],
        found,
      }));
  }, [acquired, declared, locale, rows, t, yearResult]);
  const pickPurchase = (chosen: string) => {
    const picked = purchases.find((option) => option.value === chosen);
    if (!picked) return;
    setMovement(chosen);
    setMovementLabel(picked.label);
    if (description.trim() === "") setDescription(picked.found.description);
    if (year.trim() === "") setYear(picked.found.date.slice(0, 4));
  };
  // A good is acquired in the year of its purchase, so a new year drops the pick.
  const changeYear = (next: string) => {
    setYear(next);
    setMovement("");
    setMovementLabel("");
  };
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
    return (
      servedRefusalWords(
        (last.detail as CapitalGoodDeclareResult | null)?.refusal,
      ) ?? servedRefusalWords(last.detail)
    );
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
              unserved={vocabularyEmpty(
                t,
                vocabulary,
                "",
                vocabulary.capitalKinds.length,
              )}
              options={vocabulary.capitalKinds.map((value) => ({
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
                  onChange={changeYear}
                  invalid={control.invalid}
                  describedBy={control.describedBy}
                  required
                />
              )}
            </EditorField>
            <EditorField
              label={t("desktop.ledger.capital.movement")}
              hint={
                yearResult?.truncated
                  ? t("desktop.ledger.capital.movement_cut", {
                      count: LEDGER_PAGE_SIZE,
                    })
                  : t("desktop.ledger.capital.movement_hint")
              }
            >
              {(control) => (
                <Combobox
                  label={t("desktop.ledger.capital.movement")}
                  value={movement || null}
                  options={purchases}
                  emptyLabel={t("desktop.ledger.inspector.no_match")}
                  onCommit={pickPurchase}
                >
                  <Button
                    id={control.id}
                    type="button"
                    variant="outline"
                    aria-describedby={control.describedBy}
                    className="ledger-capital-movement w-full justify-between font-normal"
                  >
                    <span className="truncate">
                      {movementLabel || t("desktop.ledger.form.choose")}
                    </span>
                    <Icon name="chevronDown" size="xs" />
                  </Button>
                </Combobox>
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
              unserved={vocabularyEmpty(
                t,
                vocabulary,
                "",
                vocabulary.capitalDisposals.length,
              )}
              options={[
                { value: "", label: t("desktop.ledger.form.none") },
                ...vocabulary.capitalDisposals.map((value) => ({
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
