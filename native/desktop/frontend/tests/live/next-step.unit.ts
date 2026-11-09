import assert from "node:assert/strict";
import test from "node:test";
import { servedNextStep } from "../../src/shell/ledger.ts";

// The declaration a wallet refusal names; node resolves no served year, so any
// number stands for one.
const YEAR = 1;

const openingBalance = {
  next_step: {
    kind: "open_iva_wallet_opening_balance",
    modelo: "303",
    filing_year: YEAR,
    period_code: "2T",
    words: "Registra el saldo inicial",
  },
};

test("a wallet refusal's opening-balance step is read as the backend served it", () => {
  assert.deepEqual(servedNextStep(openingBalance), {
    kind: "open_iva_wallet_opening_balance",
    modelo: "303",
    filing_year: YEAR,
    period_code: "2T",
    words: "Registra el saldo inicial",
  });
});

test("an opening-balance step missing part of its address is not read", () => {
  for (const missing of ["modelo", "period_code", "filing_year", "words"]) {
    const step: Record<string, unknown> = { ...openingBalance.next_step };
    delete step[missing];
    assert.equal(
      servedNextStep({ next_step: step }),
      null,
      `a step without ${missing} names no door`,
    );
  }
});

test("a step of a kind this window does not run is not read", () => {
  assert.equal(
    servedNextStep({
      next_step: { kind: "open_something_else", words: "x" },
    }),
    null,
  );
});
