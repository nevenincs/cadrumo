import "./support/servedLimits";
import { expect, test } from "@playwright/test";
import {
  certificateFiguresOf,
  statedByEveryClass,
} from "../src/shell/ledgerServedVocabulary";
import {
  figuresSendable,
  readFigures,
  requestFigures,
  startingAmount,
} from "../src/components/ledger/setup/withholdingFigures";
import { SERVED } from "./support/servedVocabulary";

// The figures a withholding certificate states, as `ledger.entry-options`
// serves them: the model holds no list of its own.

const fields = (incomeClass: string) =>
  certificateFiguresOf(SERVED, incomeClass).map((figure) => figure.field);

test("a class's figures are the served options filed under it, in the served order", () => {
  expect(SERVED.certificateFigures.length).toBeGreaterThan(0);
  const classes = [...new Set(SERVED.certificateFigures.map((f) => f.group))];
  for (const incomeClass of classes)
    expect(fields(incomeClass)).toEqual(
      SERVED.certificateFigures
        .filter((figure) => figure.group === incomeClass)
        .map((figure) => figure.field),
    );
  expect(fields("trabajo")).toEqual(
    expect.arrayContaining(["reducciones_aplicables", "gastos_deducibles"]),
  );
  expect(fields("not_a_served_class")).toEqual([]);
});

test("a figure every class states starts at zero and one only some state starts blank", () => {
  expect(statedByEveryClass(SERVED, "retencion")).toBe(true);
  expect(statedByEveryClass(SERVED, "gastos_deducibles")).toBe(false);
  expect(startingAmount(SERVED, "retencion")).toBe("0");
  expect(startingAmount(SERVED, "gastos_deducibles")).toBe("");
});

test("the request carries each typed figure under its served field name and leaves a blank one out", () => {
  const readings = readFigures(SERVED, "trabajo", {
    retencion: "150.5",
    reducciones_aplicables: "1200",
  });
  expect(figuresSendable(readings)).toBe(true);
  const sent = requestFigures(readings);
  expect(sent.retencion).toEqual({ decimal: "150.5" });
  expect(sent.reducciones_aplicables).toEqual({ decimal: "1200" });
  expect(sent.importe_integro_dinerario).toEqual({ decimal: "0" });
  expect("gastos_deducibles" in sent).toBe(false);
  expect(Object.keys(sent).sort()).toEqual(
    fields("trabajo")
      .filter((field) => field !== "gastos_deducibles")
      .sort(),
  );
});

test("a figure sent for another class is not drawn, and a refused text blocks sending", () => {
  const other = fields("capital_mobiliario");
  expect(other).not.toContain("reducciones_aplicables");
  const readings = readFigures(SERVED, "capital_mobiliario", {
    reducciones_aplicables: "5",
    retencion: "abc",
  });
  expect(readings.map((reading) => reading.figure.field)).toEqual(other);
  expect(figuresSendable(readings)).toBe(false);
  expect(readFigures(SERVED, "", {})).toEqual([]);
});
