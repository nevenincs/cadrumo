import { expect, test } from "@playwright/test";
import exported from "@fixtures/modelo/export-130.json" with { type: "json" };
import unverified from "@fixtures/modelo/export-165-unverified.json" with { type: "json" };
import pastCutoff from "@fixtures/modelo/refusal-domiciliation-past-cutoff-es.json" with { type: "json" };
import compareRefused from "@fixtures/modelo/refusal-compare-100-0A-en.json" with { type: "json" };
import {
  exportDisclosure,
  exportWarnings,
} from "../src/components/modelo/dialogs/exportDisclosures";
import type { LedgerErrorDetail } from "../src/shell/ledger";
import { servedRefusal } from "../src/shell/refusal";
import type {
  ModeloExportDisclosure,
  ModeloExportPublicResultV3,
} from "../src/shell/modeloContract/modeloExport";

// What an export's result states beside its file: each served warning flag
// becomes the sentence the command line states for it, the disclosed
// limitations are the result's own served sentences, passed on as they are,
// and an export refusal is handed to the refusal notice with the served
// sentence and its language. No page is opened.

// A stored result written before the disclosure was served lacks it, and is
// read as one that disclosed nothing; a stored disclosure is kept.
const asResult = (stored: object): ModeloExportPublicResultV3 => ({
  disclosure: null,
  ...(stored as Omit<ModeloExportPublicResultV3, "disclosure">),
});

const filed = asResult(exported);

const withReceipt = (
  change: Partial<NonNullable<ModeloExportPublicResultV3["fichero_boe"]>>,
): ModeloExportPublicResultV3 => ({
  ...filed,
  fichero_boe: filed.fichero_boe && { ...filed.fichero_boe, ...change },
});

// Synthetic: placeholder words in the served shape.
const served: ModeloExportDisclosure = {
  lead_words: "Synthetic lead sentence.",
  limitations: [
    {
      message_locale_key: "synthetic.limit.box",
      casilla_id: "0001",
      words: "Synthetic limit on one box.",
    },
    {
      message_locale_key: "synthetic.limit.whole",
      casilla_id: null,
      words: "Synthetic limit on the whole declaration.",
    },
  ],
};

test("a result that raises no flag warns of nothing and discloses nothing", () => {
  expect(filed.completeness).toBe("not_flagged");
  expect(exportWarnings(filed)).toEqual([]);
  expect(exportDisclosure(filed)).toBeNull();
});

test("an unverified completeness is a warning", () => {
  expect(exportWarnings(asResult(unverified))).toEqual([
    { key: "workspace.modelo.filing.completeness_unverified" },
  ]);
});

test("an unchecked direct-debit cutoff is a warning", () => {
  expect(
    exportWarnings(withReceipt({ domiciliation_cutoff_unverified: true })),
  ).toEqual([{ key: "tui.modelo.export.result.warning.cutoff_unverified" }]);
});

test("a receipt flag the result did not disclose adds no limitation of the window's own", () => {
  const flagged = withReceipt({ trabajo_deductions_not_computed: true });
  expect(exportWarnings(flagged)).toEqual([]);
  expect(exportDisclosure(flagged)).toBeNull();
});

test("the served disclosure is passed on as served, in its order and words", () => {
  const disclosed = { ...filed, disclosure: served };
  expect(exportDisclosure(disclosed)).toBe(served);
  expect(exportWarnings(disclosed)).toEqual([]);
});

test("a refused export carries the served sentence and its language", () => {
  const detail = pastCutoff as LedgerErrorDetail;
  const refusal = servedRefusal(detail.refusal_words ?? null, detail);
  expect(refusal.refusal_words).toBe(detail.refusal_words);
  expect(refusal.refusal_words_language).toBe("es");
  // This refusal stored no verdict, so the notice offers no way out.
  expect(detail.precondition_verdict_json).toBeNull();
  expect(refusal.verdict).toBeNull();
});

test("a language outside the served set is not passed on", () => {
  const detail = {
    ...(pastCutoff as LedgerErrorDetail),
    refusal_words_language: "xx",
  };
  expect(servedRefusal("words", detail).refusal_words_language).toBeNull();
  expect(servedRefusal("words", null).refusal_words_language).toBeNull();
});

test("a refusal's stored verdict reaches the notice in the served snapshot's shape", () => {
  const detail = compareRefused as LedgerErrorDetail;
  const refusal = servedRefusal(detail.refusal_words ?? null, detail);
  const stored = JSON.parse(detail.precondition_verdict_json ?? "null") as {
    failed_condition_id: string;
    action: { action_id: string } | null;
    missing_argument_names: string[];
  };
  expect(refusal.verdict?.failed_condition_id).toBe(stored.failed_condition_id);
  expect(refusal.verdict?.action_id).toBe(stored.action?.action_id ?? null);
  expect(refusal.verdict?.missing_argument_names).toEqual(
    stored.missing_argument_names,
  );
});
