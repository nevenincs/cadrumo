import { expect, test } from "@playwright/test";
import servedWords from "@fixtures/ledger-served-words/ledgerServedWords.json" with { type: "json" };
import type { LedgerRow } from "../src/shell/ledger";
import type { Translate } from "../src/shell/strings";
import { movementOverview } from "../src/components/ledger/overview/movementOverviewModel";
import "./support/servedClassifications";
import { movement } from "./support/ledger";
import { label } from "./support/strings";

// The Reason line of a movement's overview says what the ledger serves for
// it: the person's own words as stored, the served word where a command wrote
// the classification, and no line where no reason is stored. No page is
// opened.

const t: Translate = Object.assign(
  (key: string, values?: Record<string, string | number>) => label(key, values),
  { locale: "en" },
);

const COMMAND_NAME = "aeat app ledger classify";
const WORD = servedWords.classification_reason.command.en;

function reasonOf(row: LedgerRow) {
  const model = movementOverview({
    t,
    locale: "en",
    row,
    issues: null,
    duplicate: false,
    accounts: null,
    unsaved: 0,
    track: null,
  });
  const group = model.groups.find((found) => found.id === "classification");
  return group?.facts.find((fact) => fact.id === "classification_reason");
}

const classified = {
  business_classification: "BUSINESS",
  classified_by: "manual",
} as const;

test("a reason the person stated is shown as they wrote it", () => {
  const row = {
    ...movement("a", {
      ...classified,
      classification_reason: "Reparto acordado con la asesoría",
    }),
    classification_reason_source: "stated",
  } satisfies LedgerRow;
  expect(reasonOf(row)?.value).toMatchObject({
    kind: "value",
    text: "Reparto acordado con la asesoría",
  });
});

test("a command's name is replaced by the word the ledger serves, and the name is never shown", () => {
  const row = {
    ...movement("b", { ...classified, classification_reason: COMMAND_NAME }),
    classification_reason_source: "command",
    classification_reason_words: WORD,
    classification_reason_words_language: "en",
  } satisfies LedgerRow;
  const value = reasonOf(row)?.value;
  expect(value).toMatchObject({ kind: "value", text: WORD });
  expect(JSON.stringify(value)).not.toContain(COMMAND_NAME);
});

test("a movement with no stored reason has no Reason line", () => {
  expect(reasonOf(movement("c"))).toBeUndefined();
});
