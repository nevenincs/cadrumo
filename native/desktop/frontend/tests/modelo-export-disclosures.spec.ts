import { expect, test } from "@playwright/test";
import exported from "@fixtures/modelo/export-130.json" with { type: "json" };
import unverified from "@fixtures/modelo/export-165-unverified.json" with { type: "json" };
import pastCutoff from "@fixtures/modelo/refusal-domiciliation-past-cutoff-es.json" with { type: "json" };
import {
  exportDisclosures,
  servedExportRefusal,
} from "../src/components/modelo/dialogs/exportDisclosures";
import type { LedgerErrorDetail } from "../src/shell/ledger";
import type { ModeloExportPublicResultV3 } from "../src/shell/modeloContract/modeloExport";

// What an export's result states beside its file: each served flag becomes
// the sentence the command line states for it, at its own level, and an
// export refusal is handed to the refusal notice with the served sentence
// and its language. No page is opened.

const filed = exported as ModeloExportPublicResultV3;

const withReceipt = (
  change: Partial<NonNullable<ModeloExportPublicResultV3["fichero_boe"]>>,
): ModeloExportPublicResultV3 => ({
  ...filed,
  fichero_boe: filed.fichero_boe && { ...filed.fichero_boe, ...change },
});

test("a result that raises no flag discloses nothing", () => {
  expect(filed.completeness).toBe("not_flagged");
  expect(exportDisclosures(filed)).toEqual([]);
});

test("an unverified completeness is a warning", () => {
  expect(exportDisclosures(unverified as ModeloExportPublicResultV3)).toEqual([
    {
      level: "warning",
      key: "workspace.modelo.filing.completeness_unverified",
    },
  ]);
});

test("work-income deductions not computed are a limitation, never a warning", () => {
  expect(
    exportDisclosures(withReceipt({ trabajo_deductions_not_computed: true })),
  ).toEqual([
    {
      level: "limitation",
      key: "application.modelo.findings.trabajo_deduction_not_computed",
    },
  ]);
});

test("an unchecked direct-debit cutoff and a limitation keep their own levels", () => {
  const levels = exportDisclosures(
    withReceipt({
      domiciliation_cutoff_unverified: true,
      trabajo_deductions_not_computed: true,
    }),
  ).map((item) => item.level);
  expect(levels).toEqual(["warning", "limitation"]);
});

test("a refused export carries the served sentence and its language", () => {
  const detail = pastCutoff as LedgerErrorDetail;
  const refusal = servedExportRefusal(detail.refusal_words ?? null, detail);
  expect(refusal.refusal_words).toBe(detail.refusal_words);
  expect(refusal.refusal_words_language).toBe("es");
  expect(refusal.verdict).toBeNull();
});

test("a language outside the served set is not passed on", () => {
  const detail = {
    ...(pastCutoff as LedgerErrorDetail),
    refusal_words_language: "xx",
  };
  expect(
    servedExportRefusal("words", detail).refusal_words_language,
  ).toBeNull();
  expect(servedExportRefusal("words", null).refusal_words_language).toBeNull();
});
