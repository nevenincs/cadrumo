import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { listed } from "@/shell/compose";
import {
  compareDecimal,
  parsePercent,
  percentOf,
} from "../../../shell/ledgerGrammar";
import type { OutputLanguage } from "../../../shell/ledger";
import type {
  LedgerRatiosEligibleResult,
  LedgerRatiosListResult,
  LedgerRatiosValidateResult,
} from "../../../shell/ledgerSetup";
import { useStrings } from "../../../shell/strings";
import { WriteHold, type Landing } from "../WritePause";
import { percentText } from "../movements/movementWords";
import { PeriodSelector } from "../PeriodSelector";
import {
  CallLine,
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
import type { SetupProps } from "./setupProps";
import { setupCall, type SetupCall } from "./setupModel";
import { grammarText, tokenText } from "./setupWords";

type Eligible = LedgerRatiosEligibleResult["rows"][number];

/**
 * The share of a category used for the activity, set per year: the
 * categories that take one, named and explained in the backend's own words,
 * and the override the person set. Each set and unset is its own write.
 */
export function RatiosPane({
  port,
  reader,
  locale,
  years,
  fallbackYear,
}: SetupProps) {
  const t = useStrings();
  const [year, setYear] = useState(fallbackYear);
  const list = useSetupRead(
    port,
    reader,
    "ledger.ratios.list",
    { year },
    `y${year}`,
  );
  const eligible = useSetupRead(
    port,
    reader,
    "ledger.ratios.eligible",
    { year, output_language: locale as OutputLanguage },
    `y${year}-${locale}`,
  );
  const write = useSetupWrite(t("desktop.ledger.ratios.title"));
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [refused, setRefused] = useState<Record<string, string>>({});
  const [validation, setValidation] =
    useState<SetupCall<LedgerRatiosValidateResult> | null>(null);
  const reload = () => {
    list.reload();
    eligible.reload();
  };
  const overrides = new Map(
    list.read?.kind === "done"
      ? list.read.result.rows.map((row) => [row.category, row.ratio])
      : [],
  );
  const mismatch =
    list.read?.kind === "done" && list.read.result.outcome === "censo_mismatch";
  // A category is named by the label the backend served for it; one it did
  // not serve is shown by its token.
  const served = new Map(
    eligible.read?.kind === "done"
      ? eligible.read.result.rows.map((row) => [row.category, row.label])
      : [],
  );
  const nameOf = (category: string) => served.get(category) ?? category;
  // A ratio typed but not saved differs from the one its editor opened on.
  useSetupDraft(
    Object.entries(editing).some(([category, text]) => {
      const set = overrides.get(category);
      return text !== (set ? (percentOf(set) ?? "") : "");
    }),
  );

  const save = async (category: string) => {
    const parsed = parsePercent(editing[category] ?? "");
    if (parsed.kind !== "value") {
      setRefused({
        ...refused,
        [category]:
          parsed.kind === "refused"
            ? grammarText(t, parsed.refusal)
            : t("desktop.ledger.ratios.enter"),
      });
      return;
    }
    setRefused({ ...refused, [category]: "" });
    const done = await write.run(
      () =>
        setupCall(
          port,
          "ledger.ratios.set",
          { category, ratio: parsed.value, year },
          true,
        ),
      ratioLanding((rows) => {
        const found = rows.find((row) => row.category === category);
        return found && compareDecimal(found.ratio, parsed.value) === 0
          ? "saved"
          : "not_saved";
      }),
    );
    if (done.kind === "done") {
      const next = { ...editing };
      delete next[category];
      setEditing(next);
    }
    reload();
  };
  /** How a ratio write landed, on the year's ratios listed again; a list
   * the censo withholds tells nothing. */
  const ratioLanding = (
    judge: (rows: LedgerRatiosListResult["rows"]) => Landing,
  ) =>
    readLanding(port, "ledger.ratios.list", { year }, (result) =>
      result.outcome === "available" ? judge(result.rows) : "untold",
    );
  const unset = async (category: string) => {
    await write.run(
      () => setupCall(port, "ledger.ratios.unset", { category }, true),
      ratioLanding((rows) =>
        rows.some((row) => row.category === category) ? "not_saved" : "saved",
      ),
    );
    reload();
  };

  const columns: Column<Eligible>[] = [
    {
      key: "category",
      label: t("desktop.ledger.ratios.column.category"),
      sort: (row) => row.label,
      cell: (row) => (
        <span className="flex flex-col">
          <span>{row.label}</span>
          <span className="text-xs text-muted-foreground">{row.notes}</span>
        </span>
      ),
    },
    {
      key: "kind",
      label: t("desktop.ledger.ratios.column.kind"),
      sort: (row) => tokenText(t, "ratios.kind", row.proportionality_kind),
      cell: (row) => tokenText(t, "ratios.kind", row.proportionality_kind),
    },
    {
      key: "ratio",
      label: t("desktop.ledger.ratios.column.ratio"),
      numeric: true,
      sort: (row) => rankDecimal(overrides.get(row.category)),
      cell: (row) => {
        const name = row.label;
        if (row.category in editing)
          return (
            <span className="flex flex-col items-end gap-1">
              <span className="flex items-center gap-1">
                <Input
                  controlSize="sm"
                  className="w-20 text-right tabular-nums"
                  value={editing[row.category]}
                  autoFocus
                  inputMode="decimal"
                  aria-label={t("desktop.ledger.ratios.input", {
                    category: name,
                  })}
                  aria-invalid={refused[row.category] ? true : undefined}
                  onChange={(event) =>
                    setEditing({
                      ...editing,
                      [row.category]: event.target.value,
                    })
                  }
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void save(row.category);
                    if (event.key === "Escape") {
                      const next = { ...editing };
                      delete next[row.category];
                      setEditing(next);
                    }
                  }}
                />
                <span className="text-muted-foreground">%</span>
              </span>
              {refused[row.category] && (
                <span role="alert" className="text-xs text-destructive">
                  {refused[row.category]}
                </span>
              )}
            </span>
          );
        const set = overrides.get(row.category);
        return set ? (
          <span className="font-medium">{percentText(locale, set)}</span>
        ) : (
          <span className="text-muted-foreground">
            {t("desktop.ledger.ratios.not_set")}
          </span>
        );
      },
    },
    {
      key: "actions",
      label: t("desktop.ledger.form.actions"),
      hidden: true,
      resizable: false,
      cell: (row) => {
        const name = row.label;
        if (row.category in editing)
          return (
            <span className="flex justify-end gap-1">
              <WriteHold>
                <Button
                  size="xs"
                  className="ledger-ratio-save"
                  aria-disabled={write.busy || undefined}
                  onClick={() => !write.busy && void save(row.category)}
                >
                  {t("desktop.ledger.form.save")}
                </Button>
              </WriteHold>
            </span>
          );
        const set = overrides.get(row.category);
        // The visible word leads the name; the category follows it for a
        // screen reader, and the tooltip says it in full.
        return (
          <span className="flex justify-end gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="xs"
                  variant="ghost"
                  className="ledger-ratio-set"
                  onClick={() =>
                    setEditing({
                      ...editing,
                      [row.category]: set ? (percentOf(set) ?? "") : "",
                    })
                  }
                >
                  {set
                    ? t("desktop.ledger.ratios.change")
                    : t("desktop.ledger.ratios.set")}
                  <span className="sr-only"> {name}</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {t("desktop.ledger.ratios.set_named", { category: name })}
              </TooltipContent>
            </Tooltip>
            {set && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <WriteHold>
                    <Button
                      size="xs"
                      variant="ghost"
                      className="ledger-ratio-unset"
                      aria-disabled={write.busy || undefined}
                      onClick={() => !write.busy && void unset(row.category)}
                    >
                      {t("desktop.ledger.ratios.unset")}
                      <span className="sr-only"> {name}</span>
                    </Button>
                  </WriteHold>
                </TooltipTrigger>
                <TooltipContent>
                  {t("desktop.ledger.ratios.unset_named", { category: name })}
                </TooltipContent>
              </Tooltip>
            )}
          </span>
        );
      },
    },
  ];

  const validationResult =
    validation?.kind === "done" ? validation.result : null;
  return (
    <Panel
      title={t("desktop.ledger.ratios.title")}
      actions={
        <>
          <PeriodSelector
            value={{ year, code: "0A" }}
            onChange={(next) => next && setYear(next.year)}
            label={t("desktop.ledger.ratios.year")}
            years={years}
            locale={locale}
            fallbackYear={fallbackYear}
            mode="year"
            allowAll={false}
          />
          <Button
            size="xs"
            variant="outline"
            className="ledger-ratios-validate"
            onClick={() =>
              void setupCall(port, "ledger.ratios.validate", {}, false).then(
                setValidation,
              )
            }
          >
            {t("desktop.ledger.ratios.validate")}
          </Button>
        </>
      }
    >
      {validationResult && (
        <Alert
          tone={validationResult.findings.length ? "warning" : "success"}
          icon={
            <Icon name={validationResult.findings.length ? "alert" : "check"} />
          }
          className="ledger-ratios-validation"
        >
          {validationResult.findings.length
            ? t("desktop.ledger.ratios.findings", {
                count: validationResult.findings.length,
                categories: listed(
                  t,
                  validationResult.findings.map((finding) =>
                    nameOf(finding.category),
                  ),
                ),
              })
            : t("desktop.ledger.ratios.valid", {
                count: validationResult.overrides_count,
              })}
        </Alert>
      )}
      <CallLine call={validation} />
      {mismatch && (
        <Alert tone="warning" icon={<Icon name="alert" />}>
          {t("desktop.ledger.ratios.censo_mismatch")}
        </Alert>
      )}
      {eligible.read === null || list.read === null ? (
        <Reading label={t("desktop.ledger.form.reading")} />
      ) : eligible.read.kind !== "done" ? (
        <CallLine call={eligible.read} />
      ) : (
        <SetupTable
          label={t("desktop.ledger.ratios.table", { year })}
          rows={eligible.read.result.rows}
          rowKey={(row) => row.category}
          columns={columns}
          className="ledger-ratios-table"
        />
      )}
      <CallLine
        call={write.last}
        onReread={reload}
        refusal={(reason) =>
          reason === "REFUSED_CLI_VALIDATION_BOUNDARY"
            ? t("desktop.ledger.ratios.refused")
            : null
        }
      />
    </Panel>
  );
}
